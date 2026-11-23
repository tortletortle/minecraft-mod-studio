#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3.11+ is required (missing: $PYTHON_BIN)." >&2
  exit 2
fi
"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 or newer is required.")
PY

for command in java javac curl sha256sum; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Required command not found: $command" >&2
    exit 2
  fi
done

JAVAC_VERSION="$(javac -version 2>&1 | awk '{print $2}')"
JAVAC_MAJOR="${JAVAC_VERSION%%.*}"
if [[ ! "$JAVAC_MAJOR" =~ ^[0-9]+$ ]] || (( JAVAC_MAJOR < 21 )); then
  echo "JDK 21 or newer is required; found javac ${JAVAC_VERSION:-unknown}." >&2
  exit 2
fi

VENV_DIR="${VENV_DIR:-$SCRIPT_DIR/.venv}"
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
TEST_PYTHON="$VENV_DIR/bin/python"
"$TEST_PYTHON" -m pip install --disable-pip-version-check -r "$SCRIPT_DIR/requirements-dev.txt"

ASM_VERSION="9.11.1"
ASM_DIR="$SCRIPT_DIR/asm-oracle/lib"
ASM_JAR="$ASM_DIR/asm-${ASM_VERSION}.jar"
ASM_CHECKSUM="$ASM_JAR.sha256"
mkdir -p "$ASM_DIR"

if [[ ! -s "$ASM_JAR" || ! -s "$ASM_CHECKSUM" ]]; then
  rm -f "$ASM_JAR.tmp" "$ASM_CHECKSUM.tmp"
  curl --fail --silent --show-error --location \
    "https://repo.maven.apache.org/maven2/org/ow2/asm/asm/${ASM_VERSION}/asm-${ASM_VERSION}.jar" \
    -o "$ASM_JAR.tmp"
  curl --fail --silent --show-error --location \
    "https://maven.fabricmc.net/org/ow2/asm/asm/${ASM_VERSION}/asm-${ASM_VERSION}.jar.sha256" \
    -o "$ASM_CHECKSUM.tmp"
  EXPECTED="$(tr -d '[:space:]' < "$ASM_CHECKSUM.tmp")"
  if [[ ! "$EXPECTED" =~ ^[0-9a-fA-F]{64}$ ]]; then
    echo "Invalid SHA-256 checksum document for ASM ${ASM_VERSION}." >&2
    exit 2
  fi
  (cd "$ASM_DIR" && printf '%s  %s\n' "$EXPECTED" "asm-${ASM_VERSION}.jar.tmp" | sha256sum --check -)
  mv "$ASM_JAR.tmp" "$ASM_JAR"
  mv "$ASM_CHECKSUM.tmp" "$ASM_CHECKSUM"
fi

EXPECTED="$(tr -d '[:space:]' < "$ASM_CHECKSUM")"
if [[ ! "$EXPECTED" =~ ^[0-9a-fA-F]{64}$ ]]; then
  echo "Invalid SHA-256 checksum document for ASM ${ASM_VERSION}." >&2
  exit 2
fi
(cd "$ASM_DIR" && printf '%s  %s\n' "$EXPECTED" "asm-${ASM_VERSION}.jar" | sha256sum --check -)

BUILD_DIR="$SCRIPT_DIR/build/asm-oracle"
mkdir -p "$BUILD_DIR"
javac -encoding UTF-8 \
  -cp "$ASM_JAR" \
  -d "$BUILD_DIR" \
  "$SCRIPT_DIR/asm-oracle/AsmOracle.java"

export ASM_ORACLE_CLASSPATH="$BUILD_DIR:$ASM_JAR"
cd "$SCRIPT_DIR"
"$TEST_PYTHON" -m unittest discover -s . -p "test_*.py" -v
