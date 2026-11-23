import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from asm_oracle import compare_jar


@unittest.skipUnless(
    shutil.which("javac") and os.environ.get("ASM_ORACLE_CLASSPATH"),
    "javac and ASM_ORACLE_CLASSPATH are required",
)
class AsmOracleIntegrationTests(unittest.TestCase):
    def test_javac_classfiles_match_asm_and_extract_class_retained_mixin_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "src"
            classes = root / "classes"
            (source / "org" / "spongepowered" / "asm" / "mixin").mkdir(parents=True)
            (source / "demo" / "mixin").mkdir(parents=True)
            classes.mkdir()

            (source / "org" / "spongepowered" / "asm" / "mixin" / "Mixin.java").write_text(
                """
package org.spongepowered.asm.mixin;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;
@Retention(RetentionPolicy.CLASS)
@Target(ElementType.TYPE)
public @interface Mixin {
    Class<?>[] value() default {};
    String[] targets() default {};
}
""",
                encoding="utf-8",
            )
            (source / "demo" / "mixin" / "TargetStub.java").write_text(
                "package demo.mixin; public class TargetStub {}\n", encoding="utf-8"
            )
            (source / "demo" / "mixin" / "SampleMixin.java").write_text(
                """
package demo.mixin;
import org.spongepowered.asm.mixin.Mixin;
import java.util.function.IntUnaryOperator;
@Mixin(value={TargetStub.class}, targets={"net.minecraft.world.entity.Entity"})
public class SampleMixin {
    public static int calculate(int x) {
        switch (x) {
            case 1: return x + 2;
            case 2: return x * 3;
            default: return x - 1;
        }
    }
    public static void inspect(String className) throws Exception {
        Class<?> found = Class.forName(className);
        IntUnaryOperator operation = n -> n + 1;
        if (found != null) System.out.println(operation.applyAsInt(calculate(2)));
    }
}
""",
                encoding="utf-8",
            )

            java_files = [str(path) for path in source.rglob("*.java")]
            compiled = subprocess.run(
                ["javac", "-g", "-d", str(classes), *java_files],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)

            jar = root / "sample-mod.jar"
            with zipfile.ZipFile(jar, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(
                    "fabric.mod.json",
                    '{"schemaVersion":1,"id":"asm_fixture","version":"1","mixins":["sample.mixins.json"]}',
                )
                archive.writestr(
                    "sample.mixins.json",
                    '{"package":"demo.mixin","mixins":["SampleMixin"]}',
                )
                for class_file in classes.rglob("*.class"):
                    archive.write(class_file, class_file.relative_to(classes).as_posix())

            result = compare_jar(jar, os.environ["ASM_ORACLE_CLASSPATH"])
            summary = result["summary"]
            self.assertTrue(summary["passed"], summary)
            self.assertEqual(summary["classIdentityMismatches"], 0)
            self.assertEqual(summary["methodSignatureMismatches"], 0)
            self.assertEqual(summary["invocationMismatches"], 0)
            self.assertEqual(summary["invokedynamicMismatches"], 0)

            sample = next(
                item for item in result["classes"]
                if item["path"] == "demo/mixin/SampleMixin.class"
            )
            self.assertEqual(
                sample["asmMixinTargets"],
                ["demo/mixin/TargetStub", "net/minecraft/world/entity/Entity"],
            )


if __name__ == "__main__":
    unittest.main()
