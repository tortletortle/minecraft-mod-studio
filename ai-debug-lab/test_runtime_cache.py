import json
import multiprocessing
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
        self.assertTrue((self.cache.entry / "cache-manifest.json").is_file())

        second = self.base / "second-instance"
        second.mkdir()
        restored = self.cache.restore(second)
        self.assertEqual(restored["status"], "hit")
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
