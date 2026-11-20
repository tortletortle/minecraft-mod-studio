"""Regression tests for trusted H0 research fixture materialization only."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile
import zlib

from materialize import build

FIXTURE = Path(__file__).parent / "fixtures/static-content-v1.json"
TEXTURE = "assets/rd001/textures/item/coil.png"
LANG = "assets/rd001/lang/en_us.json"


def digest(data):
    return hashlib.sha256(data).hexdigest()


class MaterializeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = json.loads(FIXTURE.read_bytes())

    def generate(self, name="out"):
        out = self.root / name
        build(FIXTURE, out)
        return out

    def reject(self, expected=ValueError):
        fixture = self.root / "mutated.json"
        fixture.write_text(json.dumps(self.data), encoding="utf-8")
        out = self.root / "rejected"
        with self.assertRaises(expected):
            build(fixture, out)
        self.assertFalse(out.exists())

    def test_repeated_builds_identical(self):
        a, b = self.generate("a"), self.generate("b")
        self.assertEqual({p.name: p.read_bytes() for p in a.iterdir()},
                         {p.name: p.read_bytes() for p in b.iterdir()})

    def test_archive_integrity_and_manifest(self):
        out = self.generate()
        manifest = json.loads((out / "manifest.json").read_bytes())
        self.assertEqual(manifest["fixtureSHA256"], digest(FIXTURE.read_bytes()))
        self.assertEqual(set(manifest["archives"]), {"rd001-base.zip", "rd001-conflict.zip", "rd001-missing.zip"})
        for name, record in manifest["archives"].items():
            with self.subTest(archive=name), zipfile.ZipFile(out / name) as z:
                self.assertEqual(digest((out / name).read_bytes()), record["sha256"])
                self.assertIsNone(z.testzip())
                self.assertEqual(z.namelist(), sorted(record["entries"]))
                for p in z.namelist():
                    self.assertEqual(digest(z.read(p)), record["entries"][p])
                    self.assertNotIn("..", p.split("/"))
        self.assertEqual(manifest["gameVerification"], "NOT_RUN")
        self.assertEqual(manifest["caseArchiveOverrides"], {"C04-MISSING": ["rd001-missing"]})

    def test_png_structure_and_pixels(self):
        with zipfile.ZipFile(self.generate() / "rd001-base.zip") as z:
            image = z.read(TEXTURE)
        self.assertEqual(image[:8], b"\x89PNG\r\n\x1a\n")
        pos, chunks = 8, []
        while pos < len(image):
            n, = struct.unpack_from(">I", image, pos)
            kind, data = image[pos+4:pos+8], image[pos+8:pos+8+n]
            crc, = struct.unpack_from(">I", image, pos+8+n)
            self.assertEqual(crc, zlib.crc32(kind + data))
            chunks.append((kind, data))
            pos += n + 12
        self.assertEqual(pos, len(image))
        self.assertEqual([k for k, _ in chunks], [b"IHDR", b"IDAT", b"IEND"])
        self.assertEqual(struct.unpack(">IIBBBBB", chunks[0][1]), (16, 16, 8, 6, 0, 0, 0))
        self.assertEqual(zlib.decompress(chunks[1][1]), (b"\0" + bytes([180, 100, 45, 255]) * 16) * 16)
        self.assertEqual(chunks[2][1], b"")

    def test_negative_archives_isolated(self):
        out = self.generate()
        with zipfile.ZipFile(out / "rd001-base.zip") as z:
            base = {p: z.read(p) for p in z.namelist()}
        with zipfile.ZipFile(out / "rd001-missing.zip") as z:
            self.assertEqual({p: z.read(p) for p in z.namelist()},
                             {p: b for p, b in base.items() if p != TEXTURE})
        with zipfile.ZipFile(out / "rd001-conflict.zip") as z:
            self.assertEqual(z.namelist(), [LANG])
            self.assertNotEqual(z.read(LANG), base[LANG])

    def test_unsafe_paths(self):
        entry = self.data["archives"][0]["entries"][0]
        for path in ("../escape.json", "/absolute.json", "a\\b.json", "a//b.json", "a/CON.json", "a/trailing.", "x" * 241):
            with self.subTest(path=path):
                entry["path"] = path
                self.reject()

    def test_casefold_collision(self):
        entries = self.data["archives"][0]["entries"]
        entries.append({"path": entries[0]["path"].upper(), "json": {}})
        self.reject()

    def test_invalid_texture(self):
        t = self.data["archives"][0]["syntheticTexture"]
        for key, value in (("width", 65), ("height", True), ("rgba", [0, 0, 0, 256])):
            with self.subTest(key=key):
                old = t[key]
                t[key] = value
                self.reject()
                t[key] = old

    def test_duplicate_archive(self):
        self.data["archives"].append(self.data["archives"][0])
        self.reject()

    def test_unknown_archive(self):
        self.data["cases"][0]["archives"] = ["unknown"]
        self.reject()

    def test_duplicate_case(self):
        self.data["cases"].append(self.data["cases"][0])
        self.reject()

    def test_existing_directory_unchanged(self):
        out = self.root / "existing"
        out.mkdir()
        sentinel = out / "keep.txt"
        sentinel.write_bytes(b"preserve")
        with self.assertRaises(FileExistsError):
            build(FIXTURE, out)
        self.assertEqual(list(out.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_bytes(), b"preserve")


if __name__ == "__main__":
    unittest.main()
