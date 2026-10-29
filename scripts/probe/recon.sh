#!/bin/bash
# Deep filesystem recon of the Shortcuts stack on a macOS runner.
# Usage: recon.sh OUT_DIR
# Never aborts: every step is best-effort so a failure in one doesn't lose the rest.
OUT="${1:-out}"
mkdir -p "$OUT/recon" "$OUT/resources"
R="$OUT/recon"

PF=/System/Library/PrivateFrameworks
FW=/System/Library/Frameworks
PATTERN='Workflow|ToolKit|ActionKit|Shortcut|LinkMetadata|LinkServices|AppIntents|Intents|Siri.*Action|VoiceShortcut|BackgroundShortcut'

echo "== candidate frameworks ==" | tee "$R/frameworks.txt"
ls "$PF" "$FW" 2>/dev/null | grep -E "$PATTERN" | tee -a "$R/frameworks.txt"

# Everything a Swift probe should try to dlopen (framework binaries resolve via the dyld shared cache)
: > "$R/dlopen-list.txt"
for d in "$PF" "$FW"; do
  for f in "$d"/*.framework; do
    n=$(basename "$f" .framework)
    echo "$n" | grep -Eq "$PATTERN" && echo "$f/$n" >> "$R/dlopen-list.txt"
  done
done
wc -l "$R/dlopen-list.txt"

echo "== full tree of the key bundles =="
for b in "$PF/WorkflowKit.framework" "$PF/ToolKit.framework" "$PF/ActionKit.framework" \
         /System/Applications/Shortcuts.app "$PF/WorkflowUI.framework" "$PF/ShortcutsUI.framework"; do
  [ -e "$b" ] || continue
  tag=$(basename "$b")
  find "$b" \( -type f -o -type l \) -not -name "*.strings" -not -path "*.lproj/*" -exec ls -ld {} + > "$R/tree-$tag.txt" 2>&1
  echo "$tag: $(wc -l < "$R/tree-$tag.txt") entries"
done

echo "== name-based search for definition/gallery files =="
find / -xdev \( -iname "*.shortcut" -o -iname "*WFActions*" -o -iname "*ActionDefinition*" \
                -o -iname "*.wflow" -o -iname "*Gallery*" -o -iname "*WorkflowKit*" \) \
     -not -path "/Users/runner/hostedtoolcache/*" 2>/dev/null > "$R/name-hits.txt"
wc -l "$R/name-hits.txt"

echo "== content search for control-flow serialization keys =="
# Plain-file search (resources, plists, strings, json, loctables). Binaries in the dyld cache are handled by the Swift probe.
ROOTS="$PF/WorkflowKit.framework $PF/ToolKit.framework $PF/ActionKit.framework /System/Applications/Shortcuts.app $PF/WorkflowUI.framework"
for root in $ROOTS; do
  [ -e "$root" ] || continue
  grep -rIlE "WFControlFlowMode|GroupingIdentifier|WFMenuItems|is\.workflow\.actions\.conditional|choosefrommenu" "$root" 2>/dev/null
  grep -rlaE "WFControlFlowMode|GroupingIdentifier|WFMenuItems|is\.workflow\.actions\.conditional|choosefrommenu" "$root" 2>/dev/null
done | sort -u > "$R/content-hits.txt"
wc -l "$R/content-hits.txt"
# Broader sweep of every framework resources dir (not binaries) in case definitions live elsewhere
grep -rlaE "WFControlFlowMode|WFMenuItems|is\.workflow\.actions\.conditional" "$PF" "$FW" /System/Applications 2>/dev/null \
  --include="*.plist" --include="*.json" --include="*.strings" --include="*.loctable" --include="*.stringsdict" \
  --include="*.mom" --include="*.omo" --include="*.shortcut" --include="*.txt" > "$R/content-hits-broad.txt"
wc -l "$R/content-hits-broad.txt"

echo "== copy WorkflowKit resources (no localization dirs) =="
if [ -d "$PF/WorkflowKit.framework/Resources" ]; then
  rsync -a --exclude='*.lproj' "$PF/WorkflowKit.framework/Resources/" "$OUT/resources/WorkflowKit/" 2>&1 | tail -3
  cp "$PF/WorkflowKit.framework/Resources/Info.plist" "$R/WorkflowKit-Info.plist" 2>/dev/null
  cp "$PF/WorkflowKit.framework/Resources/version.plist" "$R/WorkflowKit-version.plist" 2>/dev/null
fi
# Copy any content-search hit that is a reasonably small regular file
while read -r f; do
  [ -f "$f" ] || continue
  sz=$(stat -f%z "$f" 2>/dev/null || echo 0)
  [ "$sz" -lt 20000000 ] || continue
  dest="$OUT/resources/hits$f"
  mkdir -p "$(dirname "$dest")" && cp "$f" "$dest" 2>/dev/null
done < <(cat "$R/content-hits.txt" "$R/content-hits-broad.txt" "$R/name-hits.txt" | sort -u)

echo "== decode Gallery / loctable / momd where possible =="
find "$OUT/resources" \( -name "*.plist" -o -name "*.loctable" -o -name "*.strings" -o -name "*.shortcut" \) 2>/dev/null | while read -r f; do
  plutil -convert xml1 -o "$f.xml" "$f" 2>/dev/null || rm -f "$f.xml"
done
for m in "$PF/WorkflowKit.framework/Resources/Shortcuts.momd"; do
  [ -d "$m" ] && cp -R "$m" "$OUT/resources/Shortcuts.momd" 2>/dev/null
done
echo "recon done"
