import json
import multiprocessing
import os
import tempfile
import unittest
from pathlib import Path

from runtime_cache import FileLock, RuntimeCache, CacheLockTimeout


def _contend_for_lock(path, queue):
    try:
        with FileLock(Path(path), timeout=0.35, poll_interval=0.02):
            queue.put("acquired")
    except CacheLockTimeout:
        queue.put("blocked")


def _hold_lock(path, ready, release):
    with FileLock(Path(path), timeout=3):
        ready.set()
        release.wait(8)


class RuntimeCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.assets = self.base / "assets"
        self.assets.mkdir()
        hashes = {
            "fabric-server.jar": "1" * 64,
            "server.jar": "2" * 64,
            "fabric-api.jar": "3" * 64,
            "probe.jar": "4" * 64,
        }
        (self.assets / "hashes.json").write_text(json.dumps(hashes), encoding="utf-8")
        self.cache_dir = self.base / "shared-cache"
        self.cache = RuntimeCache(self.assets, self.cache_dir)

    def tearDown(self):
        self.temp.cleanup()

    def make_runtime(self, root):
        root.mkdir(parents=True, exist_ok=True)
        files = {
            ".fabric/server/26.2-server.jar": b"fabric-server-runtime",
            ".fabric/server/loader.json": b'{"loader":"0.20.1"}',
            "libraries/net/fabricmc/fabric-loader/0.20.1/loader.jar": b"fabric-loader",
            "versions/26.2/26.2.json": b'{"id":"26.2"}',
        }
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        return files

    def test_publish_and_restore_verified_runtime(self):
        first = self.base / "first-instance"
        files = self.make_runtime(first)
        published = self.cache.publish(first)
        self.assertEqual(published["status"], "stored")
        self.assertEqual(published["file_count"], len(files))
        self.assertGreaterEqual(published["elapsed_ms"], 0)
        self.assertIn(published["maintenance"]["status"], ("clean", "pruned"))
        self.assertTrue((self.cache.entry / "cache-manifest.json").is_file())

        second = self.base / "second-instance"
        second.mkdir()
        restored = self.cache.restore(second)
        self.assertEqual(restored["status"], "hit")
        self.assertGreaterEqual(restored["elapsed_ms"], 0)
        self.assertIn(restored["maintenance"]["status"], ("clean", "pruned"))
        for relative, expected in files.items():
            self.assertEqual((second / relative).read_bytes(), expected)
        self.assertFalse((second / "mods").exists())

    def test_cache_key_changes_when_an_asset_changes(self):
        changed = dict(self.cache.asset_hashes)
        changed["fabric-server.jar"] = "a" * 64
        (self.assets / "hashes.json").write_text(json.dumps(changed), encoding="utf-8")
        other = RuntimeCache(self.assets, self.cache_dir)
        self.assertNotEqual(self.cache.key, other.key)

    def test_corrupt_cache_is_rejected_and_removed(self):
        first = self.base / "first-instance"
        self.make_runtime(first)
        self.assertEqual(self.cache.publish(first)["status"], "stored")
        target = self.cache.entry / "libraries/net/fabricmc/fabric-loader/0.20.1/loader.jar"
        target.write_bytes(b"corrupt")

        second = self.base / "second-instance"
        second.mkdir()
        restored = self.cache.restore(second)
        self.assertEqual(restored["status"], "miss")
        self.assertEqual(restored["reason"], "invalid_cache_removed")
        self.assertFalse(self.cache.entry.exists())
        self.assertFalse((second / "libraries").exists())

    def test_incomplete_runtime_is_not_published(self):
        first = self.base / "incomplete"
        (first / ".fabric/server").mkdir(parents=True)
        (first / ".fabric/server/runtime.jar").write_bytes(b"partial")
        result = self.cache.publish(first)
        self.assertEqual(result["status"], "skipped")
        self.assertFalse(self.cache.entry.exists())

    def test_empty_optional_runtime_dirs_are_allowed(self):
        first = self.base / "runtime-with-empty-optional-dirs"
        (first / ".fabric/server").mkdir(parents=True)
        (first / ".fabric/server/loader.jar").write_bytes(b"fabric-loader-runtime")
        (first / "libraries").mkdir()
        (first / "versions").mkdir()
        published = self.cache.publish(first)
        self.assertEqual(published["status"], "stored")
        second = self.base / "restored-empty-optional-dirs"
        second.mkdir()
        self.assertEqual(self.cache.restore(second)["status"], "hit")
        self.assertTrue((second / "libraries").is_dir())
        self.assertTrue((second / "versions").is_dir())

    def test_symlink_in_runtime_is_rejected_when_supported(self):
        first = self.base / "unsafe"
        self.make_runtime(first)
        outside = self.base / "outside.jar"
        outside.write_bytes(b"outside")
        try:
            (first / "libraries/outside.jar").symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation is not permitted on this runner")
        result = self.cache.publish(first)
        self.assertEqual(result["status"], "skipped")
        self.assertFalse(self.cache.entry.exists())


    def publish_variant(self, index):
        hashes = json.loads((self.assets / "hashes.json").read_text(encoding="utf-8"))
        hashes["probe.jar"] = format(index, "064x")
        (self.assets / "hashes.json").write_text(json.dumps(hashes), encoding="utf-8")
        cache = RuntimeCache(self.assets, self.cache_dir, max_entries=10, max_bytes=10**9)
        instance = self.base / ("variant-" + str(index))
        self.make_runtime(instance)
        self.assertEqual(cache.publish(instance)["status"], "stored")
        return cache

    def test_restore_updates_lru_timestamp(self):
        first = self.base / "first-instance"
        self.make_runtime(first)
        self.cache.publish(first)
        old_ns = 1_000_000_000
        os.utime(self.cache.entry, ns=(old_ns, old_ns))
        second = self.base / "second-instance"
        second.mkdir()
        self.assertEqual(self.cache.restore(second)["status"], "hit")
        self.assertGreater(self.cache.entry.stat().st_mtime_ns, old_ns)

    def test_prune_evicts_least_recently_used_and_protects_current_key(self):
        older = self.publish_variant(10)
        newer = self.publish_variant(11)
        current = self.publish_variant(12)
        for index, item in enumerate((older, newer, current), start=1):
            timestamp = index * 1_000_000_000
            os.utime(item.entry, ns=(timestamp, timestamp))
        manager = RuntimeCache(self.assets, self.cache_dir, max_entries=2, max_bytes=10**9)
        result = manager.prune(protect_key=current.key)
        self.assertEqual(result["status"], "pruned")
        self.assertEqual(result["removed_entries"], [older.key])
        self.assertFalse(older.entry.exists())
        self.assertTrue(newer.entry.exists())
        self.assertTrue(current.entry.exists())
        self.assertEqual(result["entry_count_after"], 2)

    def test_prune_enforces_byte_budget_but_never_deletes_protected_entry(self):
        older = self.publish_variant(20)
        current = self.publish_variant(21)
        manager = RuntimeCache(self.assets, self.cache_dir, max_entries=10, max_bytes=1)
        result = manager.prune(protect_key=current.key)
        self.assertEqual(result["status"], "over_budget")
        self.assertIn(older.key, result["removed_entries"])
        self.assertFalse(older.entry.exists())
        self.assertTrue(current.entry.exists())
        self.assertGreater(result["bytes_after"], 1)

    def test_prune_skips_entry_locked_by_another_process(self):
        older = self.publish_variant(30)
        current = self.publish_variant(31)
        manager = RuntimeCache(self.assets, self.cache_dir, max_entries=1, max_bytes=10**9)
        context = multiprocessing.get_context("spawn")
        ready, release = context.Event(), context.Event()
        child = context.Process(target=_hold_lock, args=(str(older.lock_path), ready, release))
        child.start()
        try:
            self.assertTrue(ready.wait(5), "lock holder did not start")
            result = manager.prune(protect_key=current.key)
            self.assertEqual(result["status"], "over_budget")
            self.assertIn(older.key, result["skipped_entries"])
            self.assertTrue(older.entry.exists())
            self.assertTrue(current.entry.exists())
        finally:
            release.set()
            child.join(10)
            if child.is_alive():
                child.terminate()
                child.join(5)
        self.assertEqual(child.exitcode, 0)

    def test_prune_removes_orphaned_staging_directory(self):
        stage = self.cache_dir / ("." + self.cache.key + ".tmp-crashed-writer")
        stage.mkdir(parents=True)
        (stage / "partial.bin").write_bytes(b"partial")
        result = self.cache.prune(protect_key=self.cache.key)
        self.assertEqual(result["status"], "pruned")
        self.assertEqual(result["removed_staging"], 1)
        self.assertFalse(stage.exists())

    def test_prune_does_not_delete_unmanaged_directory(self):
        unmanaged = self.cache_dir / ("f" * 64)
        unmanaged.mkdir(parents=True)
        (unmanaged / "user-data.txt").write_text("keep", encoding="utf-8")
        result = self.cache.prune(protect_key=self.cache.key)
        self.assertEqual(result["status"], "clean")
        self.assertTrue((unmanaged / "user-data.txt").is_file())

    def test_cross_process_lock_excludes_second_writer(self):
        lock_path = self.cache_dir / "test.lock"
        context = multiprocessing.get_context("spawn")
        queue = context.Queue()
        with FileLock(lock_path, timeout=2):
            child = context.Process(target=_contend_for_lock, args=(str(lock_path), queue))
            child.start()
            child.join(10)
            if child.is_alive():
                child.terminate()
                child.join(5)
                self.fail("lock contender did not exit")
            self.assertEqual(queue.get(timeout=2), "blocked")
        queue.close()
        queue.join_thread()


if __name__ == "__main__":
    unittest.main()
