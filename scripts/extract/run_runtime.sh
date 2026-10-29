#!/bin/bash
# Run runtime.py under Apple's platform-binary Python, retrying past native crashes.
# Usage: run_runtime.sh extract OUT_DIR
#        run_runtime.sh lint    OUT_DIR SHORTCUTS_DIR
# Each crash is recorded in OUT_DIR/progress.log; the retry skips the call that crashed.
HERE="$(cd "$(dirname "$0")" && pwd)"
MODE="$1"; OUT="$2"; TARGET="$3"
mkdir -p "$OUT"
bash "$HERE/frameworks.sh" "$OUT/frameworks.txt"
for i in $(seq 1 60); do
  /usr/bin/python3 "$HERE/runtime.py" "$MODE" "$OUT/frameworks.txt" "$OUT" $TARGET \
    > "$OUT/attempt.stdout" 2> "$OUT/attempt-$i.stderr"
  if grep -q "probe finished" "$OUT/probe.log" 2>/dev/null; then
    echo "finished after $i attempt(s)"
    exit 0
  fi
  echo "attempt $i ended early; retrying (the call that crashed will be skipped)"
done
echo "gave up after 60 attempts"
exit 1
