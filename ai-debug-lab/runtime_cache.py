"""Versioned, integrity-checked shared Fabric runtime cache for disposable playtests.

Only Fabric runtime directories are cached. World data, mods, server properties,
EULA files, credentials, logs, and user saves are never copied into this cache.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
from pathlib import Path, PurePosixPath
from typing import Any

CACHE_SCHEMA_VERSION = 1
CACHE_MANIFEST = "cache-manifest.json"
RUNTIME_DIRS = (".fabric", "libraries", "versions")
ASSET_NAMES = ("fabric-server.jar", "server.jar", "fabric-api.jar", "probe.jar")
MINECRAFT_VERSION = "26.2"
FABRIC_LOADER_VERSION = "0.20.1"
FABRIC_INSTALLER_VERSION = "1.1.2"
CACHE_ENV_VAR = "MMS_AI_RUNTIME_CACHE_DIR"


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

    def __init__(self, assets_dir: Path, cache_dir: Path | None = None, lock_timeout: float = 30.0):
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
            if count == 0:
                raise RuntimeCacheError("required runtime directory is empty: " + dirname)
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
                    or "\\" in relative
                    or pure.is_absolute()
                    or not pure.parts
                    or any(part in ("", ".", "..") for part in pure.parts)
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
    def _write_manifest(stage: Path, manifest: dict[str, Any]) -> None:
        target = stage / CACHE_MANIFEST
        temporary = stage / (CACHE_MANIFEST + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(manifest, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)

    def restore(self, instance_root: Path) -> dict[str, Any]:
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
                        shutil.copytree(entry / dirname, destination, symlinks=False)
                        copied.append(destination)
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
                        return {
                            "status": "already_valid",
                            "reason": None,
                            "cache_key": self.key,
                            "file_count": len(manifest["files"]),
                        }
                    self._remove_entry(entry)
                stage = Path(tempfile.mkdtemp(prefix="." + self.key + ".tmp-", dir=self.cache_root))
                try:
                    for dirname in RUNTIME_DIRS:
                        shutil.copytree(instance_root / dirname, stage / dirname, symlinks=False)
                    staged_manifest = self._manifest(stage)
                    self._write_manifest(stage, staged_manifest)
                    valid, reason = self._validate_entry(stage)
                    if not valid:
                        raise RuntimeCacheError("staged cache failed validation: " + str(reason))
                    os.replace(stage, entry)
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
