#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
if [[ $# -ge 1 ]]; then MODS_DIR="$1"; else MODS_DIR="$HOME/.minecraft/mods"; fi
if [[ $# -ge 2 ]]; then REPORT="$2"; else REPORT="$SCRIPT_DIR/build/reports/umpd-$(date +%Y%m%d-%H%M%S).json"; fi
if [[ $# -ge 3 ]]; then MAPPINGS="$3"; else MAPPINGS=""; fi
BUILD_DIR="$SCRIPT_DIR/build/umpd"
MAIN_OUT="$BUILD_DIR/classes/main"
TEST_OUT="$BUILD_DIR/classes/test"

if [[ ! -d "$MODS_DIR" ]]; then
  echo "Mods directory not found: $MODS_DIR" >&2
  exit 2
fi
command -v javac >/dev/null || { echo "JDK 21+ is required (javac not found)." >&2; exit 2; }
command -v java >/dev/null || { echo "JDK 21+ is required (java not found)." >&2; exit 2; }
if [[ -n "$MAPPINGS" && ! -f "$MAPPINGS" ]]; then
  echo "Tiny v2 mapping file not found: $MAPPINGS" >&2
  exit 2
fi

MODS_DIR="$(cd -- "$MODS_DIR" && pwd)"
mkdir -p "$MAIN_OUT" "$TEST_OUT" "$(dirname -- "$REPORT")"
REPORT="$(cd -- "$(dirname -- "$REPORT")" && pwd)/$(basename -- "$REPORT")"
case "$REPORT" in "$MODS_DIR"/*) echo "Report output must be outside the mods directory." >&2; exit 2 ;; esac

find "$SCRIPT_DIR/src/main/java" -type f -name '*.java' -print0 | xargs -0 javac --release 21 -encoding UTF-8 -d "$MAIN_OUT"
find "$SCRIPT_DIR/src/test/java" -type f -name '*.java' -print0 | xargs -0 javac --release 21 -encoding UTF-8 -cp "$MAIN_OUT" -d "$TEST_OUT"
java -cp "$MAIN_OUT:$TEST_OUT" dev.tortletortle.mms.umpd.ProtocolScannerSelfTest

SCAN_ARGS=(scan "$MODS_DIR" --out "$REPORT")
if [[ -n "$MAPPINGS" ]]; then
  SCAN_ARGS+=(--mappings "$MAPPINGS" --from-namespace intermediary --to-namespace named)
fi
java -cp "$MAIN_OUT" dev.tortletortle.mms.umpd.ProtocolScanner "${SCAN_ARGS[@]}"
echo "UMPD report: $REPORT"
