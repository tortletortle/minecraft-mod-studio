from __future__ import annotations

import io
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

MAX_ARCHIVE = 64 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED = 64 * 1024 * 1024
MAX_FILE_UNCOMPRESSED = 8 * 1024 * 1024
MAX_ENTRIES = 12_000
_ALLOWED_METHODS = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
_EOCD = bytes((0x50, 0x4B, 0x05, 0x06))
_DATA_DESCRIPTOR = bytes((0x50, 0x4B, 0x07, 0x08))
_LOCAL_HEADER = struct.Struct("<IHHHHHIIIHH")
_EOCD_STRUCT = struct.Struct("<IHHHHIIH")


class ArchiveSecurityError(ValueError):
    """Raised when an archive violates the resource-import security policy."""


@dataclass(frozen=True, slots=True)
class ArchiveEntry:
    path: str
    data: bytes
    crc32: int
    compressed_size: int
    size: int


@dataclass(frozen=True, slots=True)
class ArchiveResult:
    entries: tuple[ArchiveEntry, ...]
    total_size: int
    skipped_entries: int = 0


def _safe_name(name: str) -> bool:
    if not isinstance(name, str) or not name or len(name) > 512:
        return False
    if name.startswith("/") or chr(92) in name or chr(0) in name:
        return False
    if len(name) >= 2 and name[1] == ":":
        return False
    normalized = name[:-1] if name.endswith("/") else name
    return bool(normalized) and all(part not in ("", ".", "..") for part in normalized.split("/"))


def _find_eocd(raw: bytes) -> tuple[int, tuple[int, ...]]:
    start = max(0, len(raw) - 65_557)
    pos = raw.rfind(_EOCD, start)
    while pos >= start:
        if pos + _EOCD_STRUCT.size <= len(raw):
            fields = _EOCD_STRUCT.unpack_from(raw, pos)
            if pos + _EOCD_STRUCT.size + fields[-1] == len(raw):
                return pos, fields
        pos = raw.rfind(_EOCD, start, pos)
    raise ArchiveSecurityError("Missing or malformed ZIP end-of-central-directory record")


def _extra_field_ids(extra: bytes) -> set[int]:
    ids: set[int] = set()
    offset = 0
    while offset < len(extra):
        if offset + 4 > len(extra):
            raise ArchiveSecurityError("Malformed ZIP extra field")
        field_id, length = struct.unpack_from("<HH", extra, offset)
        offset += 4
        if offset + length > len(extra):
            raise ArchiveSecurityError("Malformed ZIP extra field length")
        ids.add(field_id)
        offset += length
    return ids


def _local_record_end(raw: bytes, info: zipfile.ZipInfo, central_offset: int) -> int:
    offset = info.header_offset
    if offset < 0 or offset + _LOCAL_HEADER.size > central_offset:
        raise ArchiveSecurityError(f"Local header outside archive: {info.filename}")
    (signature, _version, flags, method, _mtime, _mdate, crc, packed, size,
     name_len, extra_len) = _LOCAL_HEADER.unpack_from(raw, offset)
    if signature != 0x04034B50:
        raise ArchiveSecurityError(f"Invalid local header: {info.filename}")
    if flags != info.flag_bits or method != info.compress_type:
        raise ArchiveSecurityError(f"Local/central header mismatch: {info.filename}")
    name_start = offset + _LOCAL_HEADER.size
    data_start = name_start + name_len + extra_len
    local_extra = raw[name_start + name_len:data_start]
    if 0x0001 in _extra_field_ids(local_extra):
        raise ArchiveSecurityError(f"ZIP64 local extra field is not supported: {info.filename}")
    local_name = raw[name_start:name_start + name_len]
    try:
        decoded_name = local_name.decode("utf-8" if flags & 0x800 else "cp437")
    except UnicodeDecodeError as exc:
        raise ArchiveSecurityError(f"Invalid local filename encoding: {info.filename}") from exc
    if decoded_name != info.filename:
        raise ArchiveSecurityError(f"Local/central path mismatch: {info.filename}")
    data_end = data_start + info.compress_size
    if data_end > central_offset:
        raise ArchiveSecurityError(f"Compressed data overlaps central directory: {info.filename}")
    if not (flags & 0x08) and (crc != info.CRC or packed != info.compress_size or size != info.file_size):
        raise ArchiveSecurityError(f"Local/central size or CRC mismatch: {info.filename}")
    if flags & 0x08:
        descriptor = raw[data_end:data_end + 16]
        if len(descriptor) >= 16 and descriptor[:4] == _DATA_DESCRIPTOR:
            desc_crc, desc_packed, desc_size = struct.unpack_from("<III", descriptor, 4)
            data_end += 16
        else:
            if len(descriptor) < 12:
                raise ArchiveSecurityError(f"Truncated ZIP data descriptor: {info.filename}")
            desc_crc, desc_packed, desc_size = struct.unpack_from("<III", descriptor, 0)
            data_end += 12
        if (desc_crc, desc_packed, desc_size) != (info.CRC, info.compress_size, info.file_size):
            raise ArchiveSecurityError(f"ZIP data descriptor mismatch: {info.filename}")
    if data_end > central_offset:
        raise ArchiveSecurityError(f"ZIP data descriptor overlaps central directory: {info.filename}")
    return data_end


def read_archive(source: bytes | bytearray | memoryview | str | Path | BinaryIO) -> ArchiveResult:
    """Read a bounded ZIP/JAR without extracting paths to the filesystem.

    Rejects traversal and absolute paths, backslashes, duplicate case-folded
    paths, symlinks, encryption, unsupported compression, ZIP64 and multi-disk
    archives, overlapping local records, header disagreement, oversized data,
    and CRC failures. Only stored and deflated entries are accepted.
    """
    if isinstance(source, (bytes, bytearray, memoryview)):
        raw = bytes(source)
    elif isinstance(source, (str, Path)):
        try:
            raw = Path(source).read_bytes()
        except OSError as exc:
            raise ArchiveSecurityError(f"Cannot read archive: {exc}") from exc
    else:
        raw = source.read(MAX_ARCHIVE + 1)
    if len(raw) < 22 or len(raw) > MAX_ARCHIVE:
        raise ArchiveSecurityError("ZIP/JAR exceeds 64 MiB or has an invalid size")

    eocd_pos, eocd = _find_eocd(raw)
    (_signature, disk_no, central_disk, disk_entries, total_entries,
     central_size, central_offset, _comment_len) = eocd
    if disk_no or central_disk or disk_entries != total_entries:
        raise ArchiveSecurityError("Multi-disk ZIP archives are not supported")
    if (disk_entries == 0xFFFF or total_entries == 0xFFFF
            or central_size == 0xFFFFFFFF or central_offset == 0xFFFFFFFF):
        raise ArchiveSecurityError("ZIP64 archives are not supported")
    if total_entries > MAX_ENTRIES or central_offset + central_size != eocd_pos:
        raise ArchiveSecurityError("Invalid or oversized ZIP central directory")

    try:
        with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
            infos = archive.infolist()
            if len(infos) != total_entries:
                raise ArchiveSecurityError("Central-directory entry count mismatch")
            seen: set[str] = set()
            records: list[tuple[int, int, zipfile.ZipInfo]] = []
            total = 0
            for info in infos:
                name = info.filename
                if not _safe_name(name):
                    raise ArchiveSecurityError(f"Unsafe ZIP path: {name!r}")
                key = name.casefold()
                if key in seen:
                    raise ArchiveSecurityError(f"Duplicate ZIP path (case-insensitive): {name}")
                seen.add(key)
                if info.flag_bits & 0x01:
                    raise ArchiveSecurityError(f"Encrypted ZIP entry is not supported: {name}")
                if info.compress_type not in _ALLOWED_METHODS:
                    raise ArchiveSecurityError(f"Unsupported compression method: {name}")
                if info.file_size < 0 or info.compress_size < 0:
                    raise ArchiveSecurityError(f"Invalid ZIP entry size: {name}")
                if info.file_size > MAX_FILE_UNCOMPRESSED or info.compress_size > MAX_FILE_UNCOMPRESSED:
                    raise ArchiveSecurityError(f"ZIP entry exceeds 8 MiB: {name}")
                total += info.file_size
                if total > MAX_TOTAL_UNCOMPRESSED:
                    raise ArchiveSecurityError("ZIP uncompressed total exceeds 64 MiB")
                mode = (info.external_attr >> 16) & 0xFFFF
                if (mode & 0xF000) == 0xA000:
                    raise ArchiveSecurityError(f"Symbolic links are not supported: {name}")
                if 0x0001 in _extra_field_ids(info.extra):
                    raise ArchiveSecurityError(f"ZIP64 extra fields are not supported: {name}")
                end = _local_record_end(raw, info, central_offset)
                records.append((info.header_offset, end, info))

            records.sort(key=lambda item: item[0])
            previous_end = 0
            for start, end, info in records:
                if start < previous_end:
                    raise ArchiveSecurityError(f"Overlapping local ZIP records: {info.filename}")
                previous_end = end

            entries: list[ArchiveEntry] = []
            for _start, _end, info in records:
                try:
                    data = archive.read(info)
                except (OSError, RuntimeError, zipfile.BadZipFile, EOFError) as exc:
                    raise ArchiveSecurityError(f"ZIP integrity check failed: {info.filename}") from exc
                if len(data) != info.file_size:
                    raise ArchiveSecurityError(f"ZIP size mismatch: {info.filename}")
                entries.append(ArchiveEntry(info.filename, data, info.CRC, info.compress_size, info.file_size))
            return ArchiveResult(tuple(entries), total)
    except ArchiveSecurityError:
        raise
    except (OSError, zipfile.BadZipFile, struct.error, ValueError) as exc:
        raise ArchiveSecurityError(f"Invalid ZIP/JAR archive: {exc}") from exc
