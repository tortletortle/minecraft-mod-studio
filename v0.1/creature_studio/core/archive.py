from __future__ import annotations

import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
import io


MAX_ARCHIVE = 64 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED = 64 * 1024 * 1024
MAX_FILE_UNCOMPRESSED = 8 * 1024 * 1024
MAX_ENTRIES = 12_000
_ALLOWED_METHODS = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
_EOCD = b"PK\\x05\\x06"
_LOCAL = b"PK\\x03\\x04"
_CENTRAL = b"PK\\x01\\x02"
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
    skipped_entries: int


def _safe_name(name: str) -> bool:
    if not isinstance(name, str) or not name or len(name) > 512:
        return False
    if name.startswith("/") or chr(92) in name or chr(0) in name:
        return False
    if len(name) >= 2 and name[1] == ":":
        return False
    normalized = name[:-1] if name.endswith("/") else name
    parts = normalized.split("/")
    return bool(normalized) and all(part not in ("", ".", "..") for part in parts)
    data_end = data_start + info.compress_size
    if data_end > central_offset:
        raise ArchiveSecurityError(f"Compressed data overlaps central directory: {info.filename}")
    if not (flags & 0x08) and (crc != info.CRC or packed != info.compress_size or size != info.file_size):
        raise ArchiveSecurityError(f"Local/central size or CRC mismatch: {info.filename}")
    if flags & 0x08:
        descriptor = raw[data_end:data_end + 16]
        if len(descriptor) >= 16 and descriptor[:4] == bytes((0x50, 0x4B, 0x07, 0x08)):
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

