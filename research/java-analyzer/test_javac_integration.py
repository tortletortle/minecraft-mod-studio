import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from analyze_jar import analyze_jar

@unittest.skipUnless(shutil.which("javac"), "javac is not installed")
class JavacIntegrationTests(unittest.TestCase):
    def test_compiled_java_class_with_switch_lambda_and_reflection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src" / "demo"
            classes = root / "classes"
            src.mkdir(parents=True)
            classes.mkdir()
            source = r"""
package demo;
import java.util.function.IntUnaryOperator;
public class RealSample {
  public static int calc(int x) {
    switch (x) {
      case 1: return x + 2;
      case 2: return x * 3;
      default: return x - 1;
    }
  }
  public static void run(String name) throws Exception {
    Class<?> c = Class.forName(name);
    IntUnaryOperator f = n -> n + 1;
    for (int i=0; i<4; i++) System.out.println(f.applyAsInt(calc(i)));
    if (c != null) System.out.println(c.getDeclaredMethods().length);
  }
}
"""
            java_file = src / "RealSample.java"
            java_file.write_text(source, encoding="utf-8")
            built = subprocess.run(
                ["javac", "-g", "-d", str(classes), str(java_file)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            jar = root / "javac-sample.jar"
            with zipfile.ZipFile(jar, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.write(classes / "demo" / "RealSample.class", "demo/RealSample.class")
            report = analyze_jar(jar)
            self.assertEqual(report["diagnostics"], [])
            self.assertEqual(report["summary"]["classEntries"], 1)
            self.assertGreater(report["summary"]["methodInvocationInstructions"], 0)
            self.assertGreater(report["summary"]["invokedynamicInstructions"], 0)
            self.assertIn(
                "REFLECTION_OR_METHOD_HANDLES",
                {flag["id"] for flag in report["riskFlags"]},
            )

if __name__ == "__main__":
    unittest.main()
