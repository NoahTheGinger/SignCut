#!/bin/bash
# Write the list of Shortcuts-related framework binaries to load. Usage: frameworks.sh OUT_FILE
# (The binaries live in the dyld shared cache, so dlopen by path works even though the files are not on disk.)
PF=/System/Library/PrivateFrameworks
FW=/System/Library/Frameworks
PATTERN='Workflow|ToolKit|ActionKit|Shortcut|LinkMetadata|LinkServices|AppIntents|Intents|Siri.*Action|VoiceShortcut|BackgroundShortcut'
: > "$1"
for d in "$PF" "$FW"; do
  for f in "$d"/*.framework; do
    n=$(basename "$f" .framework)
    echo "$n" | grep -Eq "$PATTERN" && echo "$f/$n" >> "$1"
  done
done
echo "$(wc -l < "$1") frameworks listed in $1"
