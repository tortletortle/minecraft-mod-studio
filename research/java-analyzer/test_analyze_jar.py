import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from analyze_jar import analyze_jar, AnalysisError, instruction_size

def class_bytes(name="com/example/TestMod", method_calls=(), major=61):
    cp = []
    def utf(value):
        raw = value.encode("utf-8")
        cp.append((1, raw)); return len(cp)
    def cls(value):
        i = utf(value); cp.append((7, i)); return len(cp)
    def name_type(n, d):
        ni, di = utf(n), utf(d); cp.append((12, ni, di)); return len(cp)
    def method_ref(owner, n, d):
        ci, nti = cls(owner), name_type(n, d)
        cp.append((10, ci, nti)); return len(cp)
    this_idx, super_idx = cls(name), cls("java/lang/Object")
    init_ref = method_ref("java/lang/Object", "<init>", "()V")
    call_refs = [method_ref(*item) for item in method_calls]
    code_name = utf("Code")
    init_name, void_desc = utf("<init>"), utf("()V")
    run_name = utf("run")
    code = bytearray([0x2A, 0xB7, init_ref >> 8, init_ref & 255, 0xB1])
    for ref in call_refs:
        code.extend([0xB8, ref >> 8, ref & 255])
    code.append(0xB1)
    cp_blob = bytearray()
    for e in cp:
        tag = e[0]; cp_blob.append(tag)
        if tag == 1:
            raw = e[1]; cp_blob.extend(struct.pack(">H", len(raw))); cp_blob.extend(raw)
        elif tag == 7:
            cp_blob.extend(struct.pack(">H", e[1]))
        elif tag == 12:
            cp_blob.extend(struct.pack(">HH", e[1], e[2]))
        elif tag == 10:
            cp_blob.extend(struct.pack(">HH", e[1], e[2]))
    out = bytearray(struct.pack(">IHHH", 0xCAFEBABE, 0, major, len(cp)+1))
    out.extend(cp_blob)
    out.extend(struct.pack(">HHHH", 0x0021, this_idx, super_idx, 0))
    out.extend(struct.pack(">H", 0))  # fields
    out.extend(struct.pack(">H", 2))  # methods
    constructor = bytes([0x2A,0xB7,init_ref>>8,init_ref&255,0xB1])
    for access, method_name, body in ((0x0001,init_name,constructor),(0x0009,run_name,bytes(code[5:]))):
        attr = struct.pack(">HHI",0,0,len(body))+body+struct.pack(">HH",0,0)
        out.extend(struct.pack(">HHHH",access,method_name,void_desc,1))
        out.extend(struct.pack(">HI",code_name,len(attr))); out.extend(attr)
    out.extend(struct.pack(">H",0))  # class attrs
    return bytes(out)

class AnalyzerTests(unittest.TestCase):
    def make_jar(self, entries):
        tmp = tempfile.NamedTemporaryFile(suffix=".jar", delete=False)
        tmp.close()
        with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as z:
            for name, payload in entries.items():
                z.writestr(name, payload)
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return Path(tmp.name)

    def test_fabric_metadata_and_mixin_inventory(self):
        jar = self.make_jar({
            "fabric.mod.json": json.dumps({
                "schemaVersion":1,"id":"sample_mod","version":"1.2.3","name":"Sample",
                "entrypoints":{"main":["com.example.TestMod"]},
                "depends":{"fabricloader":">=0.15.0","minecraft":"1.21.x"},
                "mixins":["sample.mixins.json"]
            }).encode(),
            "sample.mixins.json": json.dumps({
                "package":"com.example.mixin","mixins":["TargetMixin"],"client":["ClientMixin"]
            }).encode(),
            "com/example/TestMod.class": class_bytes(),
            "assets/sample_mod/textures/item/test.png": b"fake-resource",
        })
        report = analyze_jar(jar)
        self.assertEqual(report["metadata"]["loaderCandidates"], ["fabric"])
        self.assertEqual(report["metadata"]["mods"][0]["id"], "sample_mod")
        self.assertEqual(len(report["metadata"]["dependencies"]), 2)
        self.assertEqual(report["mixins"][0]["targets"], [
            "com.example.mixin.ClientMixin","com.example.mixin.TargetMixin"
        ])
        self.assertEqual(report["summary"]["classEntries"], 1)
        self.assertEqual(report["migrationAssessment"]["overallStatus"], "UNASSESSED")
        self.assertFalse(report["analyzer"]["executesInputCode"])

    def test_invocation_and_high_risk_symbol_detection(self):
        jar = self.make_jar({
            "fabric.mod.json": b'{"schemaVersion":1,"id":"sample_mod","version":"1"}',
            "com/example/TestMod.class": class_bytes(method_calls=[
                ("java/lang/Class","forName","(Ljava/lang/String;)Ljava/lang/Class;"),
                ("org/spongepowered/asm/mixin/Mixin","value","()Ljava/lang/Class;"),
                ("net/minecraft/world/entity/Entity","discard","()V"),
            ]),
            "META-INF/versions/17/com/example/TestMod.class": class_bytes("com/example/TestMod", major=61),
            "META-INF/native/linux-x86_64/libsample.so": b"native",
        })
        report = analyze_jar(jar)
        ids = {x["id"] for x in report["riskFlags"]}
        self.assertIn("REFLECTION_OR_METHOD_HANDLES", ids)
        self.assertIn("MULTI_RELEASE_JAR", ids)
        self.assertIn("NATIVE_LIBRARIES", ids)
        signals = {x["id"] for x in report["signals"]}
        self.assertIn("minecraft-api-reference", signals)
        self.assertGreaterEqual(report["summary"]["methodInvocationInstructions"], 3)

    def test_rejects_path_traversal(self):
        jar = self.make_jar({"../escape.class": class_bytes()})
        with self.assertRaises(AnalysisError):
            analyze_jar(jar)

    def test_class_parse_failure_is_visible_not_silent(self):
        jar = self.make_jar({
            "fabric.mod.json": b'{"schemaVersion":1,"id":"broken","version":"1"}',
            "Broken.class": b"not a class",
        })
        report = analyze_jar(jar)
        self.assertEqual(report["summary"]["classEntries"], 1)
        self.assertEqual(report["summary"]["uniqueLogicalClasses"], 0)
        self.assertIn("PARTIAL_BYTECODE_ANALYSIS", {x["id"] for x in report["riskFlags"]})
        self.assertEqual(report["diagnostics"][0]["code"], "CLASS_PARSE_FAILED")

    def test_manifest_continuation_and_multi_release_java_version(self):
        jar = self.make_jar({
            "META-INF/MANIFEST.MF": b"Manifest-Version: 1.0\r\nMain-Class: com.example.\r\n Test\r\nMulti-Release: true\r\n\r\n",
            "com/example/Test.class": class_bytes(major=65),
        })
        report = analyze_jar(jar)
        self.assertEqual(report["metadata"]["manifest"]["main-class"], "com.example.Test")
        self.assertEqual(report["bytecode"]["classes"][0]["javaVersion"], "Java 21")

    def test_rejects_duplicate_entries_case_insensitively(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".jar", delete=False)
        tmp.close()
        with zipfile.ZipFile(tmp.name, "w") as z:
            z.writestr("assets/test/a.json", b"{}")
            z.writestr("ASSETS/test/A.JSON", b"{}")
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        with self.assertRaises(AnalysisError):
            analyze_jar(Path(tmp.name))

    def test_rejects_excessive_compression_ratio(self):
        from unittest.mock import patch
        jar = self.make_jar({"META-INF/notice.txt": b"A" * 20_000})
        with patch("analyze_jar.MAX_RATIO", 2):
            with self.assertRaises(AnalysisError):
                analyze_jar(jar)

    def test_resource_inventory_is_categorized_and_original_is_not_extracted(self):
        jar = self.make_jar({
            "fabric.mod.json": b'{"schemaVersion":1,"id":"sample_mod","version":"1"}',
            "assets/sample_mod/textures/item/coil.png": b"not-decoded",
            "assets/sample_mod/models/item/coil.json": b"{}",
            "data/sample_mod/recipes/coil.json": b"{}",
        })
        before = set(jar.parent.iterdir())
        report = analyze_jar(jar)
        after = set(jar.parent.iterdir())
        self.assertEqual(before, after)
        categories = {x["category"] for x in report["resources"]["inventory"]}
        self.assertTrue({"texture","model","recipe"}.issubset(categories))

    def test_switch_and_wide_instruction_lengths(self):
        tableswitch = bytes([0xAA,0,0,0]) + struct.pack(">iii",0,0,1) + struct.pack(">ii",4,8)
        lookupswitch = bytes([0xAB,0,0,0]) + struct.pack(">ii",0,1) + struct.pack(">ii",7,12)
        self.assertEqual(instruction_size(tableswitch,0),len(tableswitch))
        self.assertEqual(instruction_size(lookupswitch,0),len(lookupswitch))
        self.assertEqual(instruction_size(bytes([0xC4,0x84,0,1,0,1]),0),6)
        self.assertEqual(instruction_size(bytes([0xC4,0x15,0,1]),0),4)

    def test_rejects_windows_drive_style_archive_path(self):
        jar = self.make_jar({"C:/escape.class": class_bytes()})
        with self.assertRaises(AnalysisError):
            analyze_jar(jar)

    def test_unlisted_mixin_config_is_flagged(self):
        jar = self.make_jar({
            "fabric.mod.json": b'{"schemaVersion":1,"id":"sample_mod","version":"1"}',
            "orphan.mixins.json": b'{"package":"demo.mixin","mixins":["TargetMixin"]}',
        })
        report = analyze_jar(jar)
        self.assertEqual(report["mixins"][0]["path"], "orphan.mixins.json")
        self.assertIn("MIXIN", {flag["id"] for flag in report["riskFlags"]})

if __name__ == "__main__":
    unittest.main()
