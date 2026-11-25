"""Versioned, integrity-checked shared Fabric runtime cache for disposable playtests.

Only Fabric runtime directories are cached. World data, mods, server properties,
EULA files, credentials, logs, and user saves are never copied into this cache.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import time
from pathlib import Path, PurePosixPath
from typing import Any

CACHE_SCHEMA_VERSION = 1
CACHE_MANIFEST = "cache-manifest.json"
STAGE_MARKER = ".mms-runtime-cache-stage.json"
STAGE_MARKER_FORMAT = "mms-runtime-cache-stage"
RUNTIME_DIRS = (".fabric", "libraries", "versions")
ASSET_NAMES = ("fabric-server.jar", "server.jar", "fabric-api.jar", "probe.jar")
MINECRAFT_VERSION = "26.2"
FABRIC_LOADER_VERSION = "0.20.1"
FABRIC_INSTALLER_VERSION = "1.1.2"
CACHE_ENV_VAR = "MMS_AI_RUNTIME_CACHE_DIR"
CACHE_MAX_ENTRIES = 3
CACHE_MAX_BYTES = 4 * 1024 * 1024 * 1024
MAINTENANCE_LOCK = ".maintenance.lock"


class RuntimeCacheError(RuntimeError):
    """Invalid runtime-cache input or entry."""


class CacheLockTimeout(TimeoutError):
    """Another process held a cache lock for too long."""


def _is_link_or_junction(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction()) if is_junction is not None else False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class FileLock:
    """Cross-process advisory lock implemented with the standard library."""

    def __init__(self, path: Path, timeout: float = 30.0, poll_interval: float = 0.05):
        self.path = Path(path)
        self.timeout = max(0.0, float(timeout))
        self.poll_interval = max(0.01, float(poll_interval))
        self.fd: int | None = None
        self.locked = False

    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if _is_link_or_junction(self.path):
            raise RuntimeCacheError("cache lock path must not be a symlink or junction")
        flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        self.fd = os.open(str(self.path), flags, 0o600)
        try:
            if os.name == "nt":
                import msvcrt
                if os.fstat(self.fd).st_size == 0:
                    os.write(self.fd, b"\0")
                    os.fsync(self.fd)
                deadline = time.monotonic() + self.timeout
                while True:
                    os.lseek(self.fd, 0, os.SEEK_SET)
                    try:
                        msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)
                        self.locked = True
                        return self
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise CacheLockTimeout("runtime cache lock timed out")
                        time.sleep(self.poll_interval)
            else:
                import fcntl
                deadline = time.monotonic() + self.timeout
                while True:
                    try:
                        fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        self.locked = True
                        return self
                    except BlockingIOError:
                        if time.monotonic() >= deadline:
                            raise CacheLockTimeout("runtime cache lock timed out")
                        time.sleep(self.poll_interval)
        except Exception:
            os.close(self.fd)
            self.fd = None
            raise

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self.fd is None:
            return
        try:
            if self.locked:
                if os.name == "nt":
                    import msvcrt
                    os.lseek(self.fd, 0, os.SEEK_SET)
                    msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.fd, fcntl.LOCK_UN)
        finally:
            os.close(self.fd)
            self.fd = None
            self.locked = False


class RuntimeCache:
    """Restore/publish an immutable, content-verified Fabric runtime snapshot."""

    @staticmethod
    def _positive_limit(value: int | None, env_name: str, default: int) -> int:
        if value is None:
            raw = os.environ.get(env_name)
            if raw is None:
                value = default
            else:
                try:
                    value = int(raw)
                except ValueError:
                    value = default
                if value < 1:
                    value = default
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise RuntimeCacheError(env_name + " must be a positive integer")
        return value

    def __init__(
        self,
        assets_dir: Path,
        cache_dir: Path | None = None,
        lock_timeout: float = 10.0,
        max_entries: int | None = None,
        max_bytes: int | None = None,
    ):
        self.assets_dir = Path(assets_dir).expanduser().resolve()
        manifest_path = self.assets_dir / "hashes.json"
        if _is_link_or_junction(manifest_path) or not manifest_path.is_file():
            raise RuntimeCacheError("asset hash manifest is missing or unsafe")
        try:
            asset_hashes = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeCacheError("asset hash manifest is unreadable") from exc
        if not isinstance(asset_hashes, dict) or set(asset_hashes) != set(ASSET_NAMES):
            raise RuntimeCacheError("asset hash manifest has unexpected entries")
        for value in asset_hashes.values():
            if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value.lower()):
                raise RuntimeCacheError("asset hash manifest contains an invalid SHA-256")
        self.asset_hashes = dict(sorted(asset_hashes.items()))
        identity = {
            "cache_schema": CACHE_SCHEMA_VERSION,
            "minecraft": MINECRAFT_VERSION,
            "fabric_loader": FABRIC_LOADER_VERSION,
            "fabric_installer": FABRIC_INSTALLER_VERSION,
            "assets": self.asset_hashes,
        }
        encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.key = hashlib.sha256(encoded).hexdigest()
        self.lock_timeout = lock_timeout
        self.max_entries = self._positive_limit(max_entries, "MMS_AI_RUNTIME_CACHE_MAX_ENTRIES", CACHE_MAX_ENTRIES)
        self.max_bytes = self._positive_limit(max_bytes, "MMS_AI_RUNTIME_CACHE_MAX_BYTES", CACHE_MAX_BYTES)
        self.cache_root = self._select_cache_root(cache_dir)

    @staticmethod
    def _select_cache_root(cache_dir: Path | None) -> Path:
        if cache_dir is not None:
            selected = Path(cache_dir).expanduser()
        elif os.environ.get(CACHE_ENV_VAR):
            selected = Path(os.environ[CACHE_ENV_VAR]).expanduser()
        elif os.name == "nt":
            selected = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
            selected = selected / "MinecraftModStudio" / "AI-Debug-Lab" / "runtime-cache"
        else:
            base = Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")).expanduser()
            selected = base / "minecraft-mod-studio" / "ai-debug-lab" / "runtime-cache"
        return selected if selected.is_absolute() else Path.cwd() / selected

    @property
    def entry(self) -> Path:
        return self.cache_root / self.key

    @property
    def lock_path(self) -> Path:
        return self.cache_root / (self.key + ".lock")

    @property
    def maintenance_lock_path(self) -> Path:
        return self.cache_root / MAINTENANCE_LOCK

    def _ensure_root(self) -> None:
        if _is_link_or_junction(self.cache_root):
            raise RuntimeCacheError("cache root must not be a symlink or junction")
        self.cache_root.mkdir(parents=True, exist_ok=True)
        if _is_link_or_junction(self.cache_root):
            raise RuntimeCacheError("cache root must not be a symlink or junction")

    @staticmethod
    def _inventory(runtime_root: Path) -> dict[str, dict[str, Any]]:
        inventory: dict[str, dict[str, Any]] = {}
        for dirname in RUNTIME_DIRS:
            base = runtime_root / dirname
            if _is_link_or_junction(base) or not base.is_dir():
                raise RuntimeCacheError("required runtime directory is missing or unsafe: " + dirname)
            if dirname == ".fabric" and not (base / "server").is_dir():
                raise RuntimeCacheError("Fabric server runtime directory is missing")
            count = 0
            for current, dirnames, filenames in os.walk(base, topdown=True, followlinks=False):
                current_path = Path(current)
                for directory in list(dirnames):
                    if _is_link_or_junction(current_path / directory):
                        raise RuntimeCacheError("runtime directory contains a symlink or junction")
                dirnames.sort()
                for filename in sorted(filenames):
                    candidate = current_path / filename
                    if _is_link_or_junction(candidate) or not candidate.is_file():
                        raise RuntimeCacheError("runtime tree contains a non-regular file")
                    relative = candidate.relative_to(runtime_root).as_posix()
                    inventory[relative] = {"size": candidate.stat().st_size, "sha256": _sha256(candidate)}
                    count += 1
            if count == 0 and dirname == ".fabric":
                raise RuntimeCacheError("Fabric server runtime directory is empty")
        if not inventory:
            raise RuntimeCacheError("runtime tree is empty")
        return dict(sorted(inventory.items()))

    def _manifest(self, runtime_root: Path) -> dict[str, Any]:
        return {
            "schema_version": CACHE_SCHEMA_VERSION,
            "cache_key": self.key,
            "minecraft_version": MINECRAFT_VERSION,
            "fabric_loader_version": FABRIC_LOADER_VERSION,
            "fabric_installer_version": FABRIC_INSTALLER_VERSION,
            "asset_hashes": self.asset_hashes,
            "runtime_directories": list(RUNTIME_DIRS),
            "files": self._inventory(runtime_root),
        }

    def _validate_entry(self, entry: Path) -> tuple[bool, str | None]:
        try:
            if _is_link_or_junction(entry) or not entry.is_dir():
                return False, "entry_missing_or_unsafe"
            manifest_path = entry / CACHE_MANIFEST
            if _is_link_or_junction(manifest_path) or not manifest_path.is_file():
                return False, "manifest_missing_or_unsafe"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                return False, "manifest_not_object"
            if (
                manifest.get("schema_version") != CACHE_SCHEMA_VERSION
                or manifest.get("cache_key") != self.key
                or manifest.get("minecraft_version") != MINECRAFT_VERSION
                or manifest.get("fabric_loader_version") != FABRIC_LOADER_VERSION
                or manifest.get("fabric_installer_version") != FABRIC_INSTALLER_VERSION
                or manifest.get("asset_hashes") != self.asset_hashes
                or manifest.get("runtime_directories") != list(RUNTIME_DIRS)
                or not isinstance(manifest.get("files"), dict)
            ):
                return False, "manifest_identity_mismatch"
            expected = manifest["files"]
            for relative in expected:
                pure = PurePosixPath(relative)
                if (
                    not isinstance(relative, str)
                    or chr(92) in relative
                    or pure.is_absolute()
                    or not pure.parts
                    or any(part in ("", ".", "..") or ":" in part or chr(0) in part for part in pure.parts)
                    or pure.parts[0] not in RUNTIME_DIRS
                ):
                    return False, "manifest_path_rejected"
            if self._inventory(entry) != expected:
                return False, "file_inventory_or_hash_mismatch"
            return True, None
        except (OSError, ValueError, TypeError, AttributeError, json.JSONDecodeError, RuntimeCacheError):
            return False, "entry_unreadable_or_invalid"

    @staticmethod
    def _remove_entry(entry: Path) -> None:
        if entry.is_symlink():
            entry.unlink()
        elif getattr(entry, "is_junction", lambda: False)():
            os.rmdir(entry)
        elif entry.is_dir():
            shutil.rmtree(entry)
        elif entry.exists():
            entry.unlink()

    @staticmethod
    def _valid_stage_marker(path: Path, key: str) -> bool:
        marker = path / STAGE_MARKER
        try:
            if _is_link_or_junction(path) or not path.is_dir() or _is_link_or_junction(marker) or not marker.is_file():
                return False
            value = json.loads(marker.read_text(encoding="utf-8"))
            return (
                isinstance(value, dict)
                and value.get("format") == STAGE_MARKER_FORMAT
                and type(value.get("schema_version")) is int
                and value["schema_version"] == CACHE_SCHEMA_VERSION
                and value.get("cache_key") == key
                and value.get("stage_name") == path.name
            )
        except (OSError, ValueError, TypeError, AttributeError, json.JSONDecodeError):
            return False

    @staticmethod
    def _write_manifest(stage: Path, manifest: dict[str, Any]) -> None:
        target = stage / CACHE_MANIFEST
        temporary = stage / (CACHE_MANIFEST + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(manifest, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)

    @staticmethod
    def _touch_entry(entry: Path) -> None:
        # Directory mtime is a best-effort LRU signal. Cache correctness never
        # depends on it, and filesystems may deny timestamp updates.
        try:
            os.utime(entry, None)
        except OSError:
            pass

    @staticmethod
    def _tree_size(root: Path) -> int | None:
        total = 0

        def raise_walk_error(error: OSError) -> None:
            raise error

        try:
            for current, dirnames, filenames in os.walk(
                root, topdown=True, followlinks=False, onerror=raise_walk_error
            ):
                current_path = Path(current)
                for directory in list(dirnames):
                    if _is_link_or_junction(current_path / directory):
                        return None
                for filename in filenames:
                    candidate = current_path / filename
                    if _is_link_or_junction(candidate) or not candidate.is_file():
                        return None
                    total += candidate.stat().st_size
        except OSError:
            return None
        return total

    def _managed_entry_info(self, entry: Path) -> dict[str, Any] | None:
        # Prune only entries whose manifest identity reproduces the directory
        # key and whose on-disk files are all listed by that manifest. A user
        # file added to a cache tree makes it unmanaged rather than deletable.
        if re.fullmatch(r"[0-9a-f]{64}", entry.name) is None:
            return None
        if _is_link_or_junction(entry) or not entry.is_dir():
            return None
        manifest_path = entry / CACHE_MANIFEST
        if _is_link_or_junction(manifest_path) or not manifest_path.is_file():
            return None
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                return None

            schema = manifest.get("schema_version")
            minecraft = manifest.get("minecraft_version")
            loader = manifest.get("fabric_loader_version")
            installer = manifest.get("fabric_installer_version")
            asset_hashes = manifest.get("asset_hashes")
            runtime_dirs = manifest.get("runtime_directories")
            files = manifest.get("files")
            if (
                isinstance(schema, bool)
                or not isinstance(schema, int)
                or schema < 1
                or not all(isinstance(value, str) and value for value in (minecraft, loader, installer))
                or not isinstance(asset_hashes, dict)
                or set(asset_hashes) != set(ASSET_NAMES)
                or not isinstance(runtime_dirs, list)
                or runtime_dirs != list(RUNTIME_DIRS)
                or not isinstance(files, dict)
                or not files
            ):
                return None
            if any(
                not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None
                for digest in asset_hashes.values()
            ):
                return None

            identity = {
                "cache_schema": schema,
                "minecraft": minecraft,
                "fabric_loader": loader,
                "fabric_installer": installer,
                "assets": dict(sorted(asset_hashes.items())),
            }
            encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
            if hashlib.sha256(encoded).hexdigest() != entry.name:
                return None

            expected_paths: set[str] = set()
            for relative, record in files.items():
                if not isinstance(relative, str) or not isinstance(record, dict):
                    return None
                pure = PurePosixPath(relative)
                if (
                    pure.is_absolute()
                    or pure.as_posix() != relative
                    or chr(92) in relative
                    or any(part in ("", ".", "..") or ":" in part or chr(0) in part for part in pure.parts)
                    or not pure.parts
                    or pure.parts[0] not in RUNTIME_DIRS
                ):
                    return None
                size = record.get("size")
                digest = record.get("sha256")
                if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                    return None
                if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                    return None
                expected_paths.add(relative)

            stage_marker = entry / STAGE_MARKER
            if _is_link_or_junction(stage_marker):
                return None
            if stage_marker.exists() and not self._valid_stage_marker(entry, entry.name):
                return None
            allowed_top_level = set(RUNTIME_DIRS) | {CACHE_MANIFEST, STAGE_MARKER}
            if any(child.name not in allowed_top_level for child in entry.iterdir()):
                return None

            # Missing files indicate a damaged but still app-owned entry that
            # can safely be evicted. Unlisted files may be user data, so leave
            # that entire directory untouched.
            for dirname in RUNTIME_DIRS:
                base = entry / dirname
                if not base.exists():
                    continue
                if _is_link_or_junction(base) or not base.is_dir():
                    return None
                for current, dirnames, filenames in os.walk(base, topdown=True, followlinks=False):
                    current_path = Path(current)
                    for child_dir in list(dirnames):
                        if _is_link_or_junction(current_path / child_dir):
                            return None
                    for filename in filenames:
                        candidate = current_path / filename
                        if _is_link_or_junction(candidate) or not candidate.is_file():
                            return None
                        relative = candidate.relative_to(entry).as_posix()
                        if relative not in expected_paths:
                            return None

            size_bytes = self._tree_size(entry)
            if size_bytes is None:
                return None
            return {
                "key": entry.name,
                "path": entry,
                "size_bytes": size_bytes,
                "last_used_ns": entry.stat().st_mtime_ns,
            }
        except (OSError, ValueError, TypeError, AttributeError):
            return None

    def prune(self, protect_key: str | None = None) -> dict[str, Any]:
        """Best-effort LRU maintenance with entry/byte bounds and lock safety."""
        started = time.perf_counter()
        result: dict[str, Any] = {
            "status": "skipped",
            "reason": "maintenance_not_run",
            "max_entries": self.max_entries,
            "max_bytes": self.max_bytes,
            "entry_count_before": 0,
            "entry_count_after": 0,
            "bytes_before": 0,
            "bytes_after": 0,
            "removed_entries": [],
            "removed_staging": 0,
            "skipped_entries": [],
            "skipped_staging": 0,
        }
        try:
            self._ensure_root()
            with FileLock(self.maintenance_lock_path, timeout=0):
                # A process killed during publication can leave a staging
                # directory. The per-key lock proves no writer still owns it.
                for candidate in list(self.cache_root.iterdir()):
                    match = re.fullmatch(r"\.([0-9a-f]{64})\.tmp-.+", candidate.name)
                    if match is None:
                        continue
                    key = match.group(1)
                    if not self._valid_stage_marker(candidate, key):
                        result["skipped_staging"] += 1
                        continue
                    try:
                        with FileLock(self.cache_root / (key + ".lock"), timeout=0):
                            if self._valid_stage_marker(candidate, key):
                                shutil.rmtree(candidate)
                                result["removed_staging"] += 1
                            else:
                                result["skipped_staging"] += 1
                    except (CacheLockTimeout, OSError, RuntimeCacheError):
                        result["skipped_staging"] += 1

                initial = [
                    info for child in list(self.cache_root.iterdir())
                    if (info := self._managed_entry_info(child)) is not None
                ]
                result["entry_count_before"] = len(initial)
                result["bytes_before"] = sum(item["size_bytes"] for item in initial)

                protected: list[dict[str, Any]] = []
                blocked: list[dict[str, Any]] = []
                locked: list[tuple[dict[str, Any], FileLock]] = []
                try:
                    for info in initial:
                        if info["key"] == protect_key:
                            protected.append(info)
                            continue
                        lock = FileLock(self.cache_root / (info["key"] + ".lock"), timeout=0)
                        try:
                            lock.__enter__()
                        except (CacheLockTimeout, OSError, RuntimeCacheError):
                            blocked.append(info)
                            result["skipped_entries"].append(info["key"])
                            continue
                        current = self._managed_entry_info(info["path"])
                        if current is None:
                            lock.__exit__(None, None, None)
                            continue
                        locked.append((current, lock))

                    remaining = {
                        item["key"]: item for item in protected + blocked
                    }
                    remaining.update({item["key"]: item for item, _ in locked})
                    ordered = sorted(locked, key=lambda pair: (pair[0]["last_used_ns"], pair[0]["key"]))
                    for info, _lock in ordered:
                        total_bytes = sum(item["size_bytes"] for item in remaining.values())
                        if len(remaining) <= self.max_entries and total_bytes <= self.max_bytes:
                            break
                        key = info["key"]
                        path = info["path"]
                        try:
                            if _is_link_or_junction(path) or not path.is_dir():
                                remaining.pop(key, None)
                                continue
                            shutil.rmtree(path)
                            remaining.pop(key, None)
                            result["removed_entries"].append(key)
                        except OSError:
                            result["skipped_entries"].append(key)
                finally:
                    for _info, lock in reversed(locked):
                        try:
                            lock.__exit__(None, None, None)
                        except OSError:
                            pass

                final = [
                    info for child in list(self.cache_root.iterdir())
                    if (info := self._managed_entry_info(child)) is not None
                ]
                result["entry_count_after"] = len(final)
                result["bytes_after"] = sum(item["size_bytes"] for item in final)
                over_budget = (
                    result["entry_count_after"] > self.max_entries
                    or result["bytes_after"] > self.max_bytes
                )
                if over_budget:
                    result["status"] = "over_budget"
                    result["reason"] = "protected_or_active_entries_exceed_limits"
                elif result["removed_entries"] or result["removed_staging"]:
                    result["status"] = "pruned"
                    result["reason"] = None
                else:
                    result["status"] = "clean"
                    result["reason"] = None
        except CacheLockTimeout:
            result["reason"] = "maintenance_lock_busy"
        except (OSError, RuntimeCacheError) as exc:
            result["reason"] = "maintenance_failed"
            result["detail"] = type(exc).__name__
        result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
        return result

    def restore(self, instance_root: Path) -> dict[str, Any]:
        started = time.perf_counter()
        result = self._restore(instance_root)
        result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
        result["maintenance"] = self.prune(protect_key=self.key)
        return result

    def _restore(self, instance_root: Path) -> dict[str, Any]:
        instance_root = Path(instance_root)
        result = {"status": "miss", "reason": "cache_not_found", "cache_key": self.key}
        try:
            self._ensure_root()
            with FileLock(self.lock_path, timeout=self.lock_timeout):
                entry = self.entry
                if not entry.exists() and not _is_link_or_junction(entry):
                    return result
                valid, reason = self._validate_entry(entry)
                if not valid:
                    if self._managed_entry_info(entry) is None:
                        return {**result, "reason": "invalid_cache_unmanaged_preserved", "detail": reason}
                    try:
                        self._remove_entry(entry)
                    except OSError:
                        return {**result, "reason": "invalid_cache_could_not_be_removed", "detail": reason}
                    return {**result, "reason": "invalid_cache_removed", "detail": reason}
                copied: list[Path] = []
                try:
                    for dirname in RUNTIME_DIRS:
                        destination = instance_root / dirname
                        if destination.exists() or _is_link_or_junction(destination):
                            raise RuntimeCacheError("instance runtime directory already exists")
                        copied.append(destination)
                        shutil.copytree(entry / dirname, destination, symlinks=False)
                    self._touch_entry(entry)
                    return {"status": "hit", "reason": None, "cache_key": self.key}
                except (OSError, RuntimeCacheError) as exc:
                    for destination in reversed(copied):
                        shutil.rmtree(destination, ignore_errors=True)
                    return {**result, "reason": "cache_restore_failed", "detail": type(exc).__name__}
        except CacheLockTimeout:
            return {**result, "reason": "cache_lock_timeout"}
        except (OSError, RuntimeCacheError) as exc:
            return {"status": "disabled", "reason": "cache_unavailable", "detail": type(exc).__name__, "cache_key": self.key}

    def publish(self, instance_root: Path) -> dict[str, Any]:
        started = time.perf_counter()
        result = self._publish(instance_root)
        result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
        result["maintenance"] = self.prune(protect_key=self.key)
        return result

    def _publish(self, instance_root: Path) -> dict[str, Any]:
        instance_root = Path(instance_root)
        result = {"status": "skipped", "reason": "cache_not_published", "cache_key": self.key}
        try:
            try:
                manifest = self._manifest(instance_root)
            except RuntimeCacheError as exc:
                return {**result, "reason": "runtime_incomplete_or_unsafe", "detail": str(exc)}
            self._ensure_root()
            with FileLock(self.lock_path, timeout=self.lock_timeout):
                entry = self.entry
                if entry.exists() or _is_link_or_junction(entry):
                    valid, _ = self._validate_entry(entry)
                    if valid:
                        self._touch_entry(entry)
                        return {
                            "status": "already_valid",
                            "reason": None,
                            "cache_key": self.key,
                            "file_count": len(manifest["files"]),
                        }
                    if self._managed_entry_info(entry) is None:
                        return {**result, "reason": "cache_entry_unmanaged_preserved"}
                    self._remove_entry(entry)
                stage = Path(tempfile.mkdtemp(prefix="." + self.key + ".tmp-", dir=self.cache_root))
                try:
                    marker = {
                        "format": STAGE_MARKER_FORMAT,
                        "schema_version": CACHE_SCHEMA_VERSION,
                        "cache_key": self.key,
                        "stage_name": stage.name,
                    }
                    marker_path = stage / STAGE_MARKER
                    with marker_path.open("x", encoding="utf-8", newline="\n") as stream:
                        json.dump(marker, stream, sort_keys=True)
                        stream.write("\n")
                        stream.flush()
                        os.fsync(stream.fileno())
                    for dirname in RUNTIME_DIRS:
                        shutil.copytree(instance_root / dirname, stage / dirname, symlinks=False)
                    staged_manifest = self._manifest(stage)
                    self._write_manifest(stage, staged_manifest)
                    valid, reason = self._validate_entry(stage)
                    if not valid:
                        raise RuntimeCacheError("staged cache failed validation: " + str(reason))
                    os.replace(stage, entry)
                    try:
                        (entry / STAGE_MARKER).unlink()
                    except OSError:
                        pass
                    self._touch_entry(entry)
                except Exception:
                    shutil.rmtree(stage, ignore_errors=True)
                    raise
                return {
                    "status": "stored",
                    "reason": None,
                    "cache_key": self.key,
                    "file_count": len(staged_manifest["files"]),
                }
        except CacheLockTimeout:
            return {**result, "reason": "cache_lock_timeout"}
        except (OSError, RuntimeCacheError) as exc:
            return {**result, "reason": "cache_publish_failed", "detail": type(exc).__name__}
