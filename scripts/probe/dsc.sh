#!/bin/bash
# Pull the Shortcuts-related dylibs out of the dyld shared cache and dump them with static tools
# (no code execution, so ActionKit's platform-binary assertion never fires).
# Usage: dsc.sh OUT_DIR
OUT="${1:-out}"
D="$OUT/static"
mkdir -p "$D"
WORK="${RUNNER_TEMP:-/tmp}/dsc-extract"
rm -rf "$WORK"; mkdir -p "$WORK"

# ---- 1. find the cache and the extractor
CACHE=$(ls /System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_arm64e \
           /System/Library/dyld/dyld_shared_cache_arm64e 2>/dev/null | head -1)
EXTRACTOR=$(find /Applications/Xcode*.app /Library/Developer /usr/lib /Applications/Xcode*.app/Contents/Developer/Platforms/MacOSX.platform/usr/lib \
              -name dsc_extractor.bundle 2>/dev/null | head -1)
echo "cache=$CACHE"      | tee "$D/dsc-info.txt"
echo "extractor=$EXTRACTOR" | tee -a "$D/dsc-info.txt"
ls -la "$(dirname "$CACHE")" 2>/dev/null | head -20 | tee -a "$D/dsc-info.txt"
df -h / | tee -a "$D/dsc-info.txt"

# ---- 2. extract (all dylibs; the API has no filter)
if [ -n "$CACHE" ] && [ -n "$EXTRACTOR" ]; then
  cat > "$WORK/ext.c" <<'EOF'
#include <dlfcn.h>
#include <stdio.h>
typedef int (*extract_fn)(const char*, const char*, void (^)(unsigned, unsigned));
int main(int argc, char** argv) {
  void* h = dlopen(argv[1], RTLD_NOW);
  if (!h) { fprintf(stderr, "dlopen: %s\n", dlerror()); return 2; }
  extract_fn f = (extract_fn)dlsym(h, "dyld_shared_cache_extract_dylibs_progress");
  if (!f) { fprintf(stderr, "dlsym failed\n"); return 3; }
  int rc = f(argv[2], argv[3], ^(unsigned c, unsigned t) { if (c % 500 == 0) fprintf(stderr, "extract %u/%u\n", c, t); });
  fprintf(stderr, "extract rc=%d\n", rc);
  return rc;
}
EOF
  clang -fblocks -o "$WORK/ext" "$WORK/ext.c" 2>&1 | tee -a "$D/dsc-info.txt"
  "$WORK/ext" "$EXTRACTOR" "$CACHE" "$WORK/root" 2>&1 | tail -5 | tee -a "$D/dsc-info.txt"
fi

ROOT="$WORK/root"
[ -d "$ROOT" ] || { echo "extraction produced no tree"; ls "$WORK" | tee -a "$D/dsc-info.txt"; }

# ---- 3. static dumps of the interesting images
TARGETS="WorkflowKit ActionKit ToolKit WorkflowEditor ActionKitUI WorkflowUI VoiceShortcuts VoiceShortcutClient ShortcutsUI Shortcut LinkMetadata LinkServices AppIntents"
for n in $TARGETS; do
  bin=$(find "$ROOT" -type f \( -path "*/$n.framework/$n" -o -path "*/$n.framework/Versions/A/$n" \) 2>/dev/null | head -1)
  [ -n "$bin" ] || { echo "not found in extracted cache: $n" | tee -a "$D/dsc-info.txt"; continue; }
  echo "== $n -> $bin ($(stat -f%z "$bin") bytes)" | tee -a "$D/dsc-info.txt"
  strings -a "$bin" | gzip -9 > "$D/$n.strings.gz"
  otool -ov "$bin" 2>/dev/null | gzip -9 > "$D/$n.objc.txt.gz"
  otool -L "$bin" 2>/dev/null > "$D/$n.libs.txt"
done

# ---- 4. cheap focused extracts so the answers are readable without unpacking 100MB
if [ -f "$D/WorkflowKit.strings.gz" ]; then
  gunzip -c "$D/WorkflowKit.strings.gz" | grep -E '^(WF[A-Za-z]+|is\.workflow\.[A-Za-z0-9._]+|Grouping[A-Za-z]*|UUID|OutputUUID|OutputName|VariableName|Variable|Value|Type|string|attachmentsByRange|Aggrandizements|[A-Za-z]*Serialization[A-Za-z]*)$' | sort -u > "$D/WorkflowKit.keys-candidates.txt"
  wc -l "$D/WorkflowKit.keys-candidates.txt"
fi
echo "dsc.sh done"
