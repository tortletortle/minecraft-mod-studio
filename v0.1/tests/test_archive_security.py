from __future__ import annotations

import io
import stat
import struct
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from creature_studio.core.archive import ArchiveSecurityError, MAX_ARCHIVE, read_archive, _safe_name


def make_zip(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries:
            archive.writestr(name, data)
    return buffer.getvalue()


class ArchiveSecurityTests(unittest.TestCase):
    def test_reads_stored_and_deflated_entries_and_checks_crc(self):
        raw = make_zip([("assets/demo/a.json", b'{"ok":true}'), ("data/demo/b.txt", b"hello")])
        result = read_archive(raw)
        self.assertEqual([item.path for item in result.entries], ["assets/demo/a.json", "data/demo/b.txt"])
        self.assertEqual(result.total_size, 16)
        self.assertEqual(result.entries[0].data, b'{"ok":true}')

    def test_rejects_parent_traversal(self):
        with self.assertRaises(ArchiveSecurityError):
            read_archive(make_zip([("../escape.txt", b"x")]))

    def test_rejects_absolute_and_backslash_paths(self):
        for name in ("/absolute.txt", "C:/drive.txt", "assets\\demo\\file.png"):
            with self.subTest(name=name), self.assertRaises(ArchiveSecurityError):
                read_archive(make_zip([(name, b"x")]))

    def test_rejects_case_insensitive_duplicate_paths(self):
        with self.assertRaises(ArchiveSecurityError):
            read_archive(make_zip([("assets/demo/a.png", b"a"), ("ASSETS/DEMO/A.PNG", b"b")]))

    def test_rejects_file_directory_name_collision(self):
        with self.assertRaises(ArchiveSecurityError):
            read_archive(make_zip([("assets/foo", b"file"), ("assets/foo/", b"")]))

    def test_rejects_non_empty_directory_entries(self):
        with self.assertRaises(ArchiveSecurityError):
            read_archive(make_zip([("assets/foo/", b"payload")]))

    def test_checks_disk_archive_size_before_reading(self):
        fake_path = Path("oversized.zip")
        with patch.object(Path, "stat", return_value=SimpleNamespace(st_size=MAX_ARCHIVE + 1)):
            with patch.object(Path, "read_bytes", side_effect=AssertionError("read_bytes must not be called")):
                with self.assertRaises(ArchiveSecurityError):
                    read_archive(fake_path)

    def test_rejects_lied_about_file_size_zip_bomb_with_bounded_reads(self):
        payload = b"x" * (8 * 1024 * 1024 + 1)
        raw = bytearray(make_zip([("assets/demo/bomb.bin", payload)]))
        local = raw.find(b"PK\x03\x04")
        central = raw.find(b"PK\x01\x02")
        self.assertGreaterEqual(local, 0)
        self.assertGreaterEqual(central, 0)
        struct.pack_into("<I", raw, local + 22, 10)
        struct.pack_into("<I", raw, central + 24, 10)

        read_sizes = []
        original_read = zipfile.ZipExtFile.read

        def tracked_read(stream, size=-1):
            read_sizes.append(size)
            return original_read(stream, size)

        with patch.object(zipfile.ZipExtFile, "read", tracked_read):
            with self.assertRaises(ArchiveSecurityError):
                read_archive(bytes(raw))
        self.assertTrue(read_sizes)
        self.assertLessEqual(max(read_sizes), 11)

    def test_rejects_symlink_entries(self):
        buffer = io.BytesIO()
        info = zipfile.ZipInfo("assets/demo/link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(info, b"target")
        with self.assertRaises(ArchiveSecurityError):
            read_archive(buffer.getvalue())

    def test_rejects_archive_over_limit(self):
        with self.assertRaises(ArchiveSecurityError):
            read_archive(b"x" * (64 * 1024 * 1024 + 1))


    def test_rejects_crc_corruption(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("assets/demo/a.txt", b"integrity")
        raw = bytearray(buffer.getvalue())
        local_name_len = int.from_bytes(raw[26:28], "little")
        local_extra_len = int.from_bytes(raw[28:30], "little")
        raw[30 + local_name_len + local_extra_len + 1] ^= 0x01
        with self.assertRaises(ArchiveSecurityError):
            read_archive(raw)

    def test_rejects_local_header_disagreement(self):
        raw = bytearray(make_zip([("assets/demo/a.txt", b"content")]))
        raw[6] ^= 0x01
        with self.assertRaises(ArchiveSecurityError):
            read_archive(raw)

    def test_rejects_unsupported_compression(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_BZIP2) as archive:
            archive.writestr("assets/demo/a.txt", b"content")
        with self.assertRaises(ArchiveSecurityError):
            read_archive(buffer.getvalue())

    def test_rejects_single_file_over_limit(self):
        with self.assertRaises(ArchiveSecurityError):
            read_archive(make_zip([("assets/demo/large.bin", b"x" * (8 * 1024 * 1024 + 1))]))


    def test_rejects_overlapping_local_records(self):
        raw = bytearray(make_zip([("assets/demo/a.txt", b"a"), ("assets/demo/b.txt", b"b")]))
        signature = bytes((0x50, 0x4B, 0x01, 0x02))
        central = []
        offset = 0
        while True:
            found = raw.find(signature, offset)
            if found < 0:
                break
            central.append(found)
            offset = found + 4
        self.assertEqual(len(central), 2)
        first_local = int.from_bytes(raw[central[0] + 42:central[0] + 46], "little")
        raw[central[1] + 42:central[1] + 46] = first_local.to_bytes(4, "little")
        with self.assertRaises(ArchiveSecurityError):
            read_archive(raw)

    def test_rejects_nul_and_empty_path_segments(self):
        self.assertFalse(_safe_name("assets/demo/evil" + chr(0) + ".txt"))
        self.assertFalse(_safe_name("assets//demo/file.png"))


if __name__ == "__main__":
    unittest.main()
