#!/bin/bash
# Copy Apple's own shipped example shortcuts (WorkflowKit's Gallery) as XML plists. Usage: gallery.sh DEST_DIR
G=/System/Library/PrivateFrameworks/WorkflowKit.framework/Resources/Gallery.bundle/Contents/Resources
mkdir -p "$1"
for f in "$G"/*.wflow; do
  [ -e "$f" ] && plutil -convert xml1 -o "$1/$(basename "$f" .wflow).xml" "$f"
done
[ -e "$G/gallery.plist" ] && plutil -convert xml1 -o "$1/gallery-index.xml" "$G/gallery.plist"
ls "$1"
