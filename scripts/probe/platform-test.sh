#!/bin/bash
# Which Apple-signed host processes can load ActionKit/WorkflowKit? (ActionKit asserts the host is a platform binary.)
# Usage: platform-test.sh OUT_DIR
OUT="${1:-out}/platform-test"
mkdir -p "$OUT"
WK=/System/Library/PrivateFrameworks/WorkflowKit.framework

echo "== osascript / JXA (Apple platform binary) ==" | tee "$OUT/jxa.txt"
osascript -l JavaScript <<'EOF' 2>&1 | tee -a "$OUT/jxa.txt"
ObjC.import('Foundation');
var out = [];
['WorkflowKit','ActionKit','ToolKit'].forEach(function (n) {
  var b = $.NSBundle.bundleWithPath('/System/Library/PrivateFrameworks/' + n + '.framework');
  var ok = b && b.load;   // property access in JXA invokes the getter-less method; see next line
  out.push(n + ' bundle=' + (b ? 'found' : 'nil'));
  try { out.push(n + ' loadAndReturnError=' + b.loadAndReturnError($())); } catch (e) { out.push(n + ' load threw ' + e); }
});
['WFActionRegistry','WFAction','WFControlFlowAction','WFConditionalAction','WFWorkflow','WFWorkflowRecord'].forEach(function (c) {
  var k = $.NSClassFromString(c);
  out.push(c + ' -> ' + (k && !k.isNil && !k.isNil() ? 'present' : 'absent'));
});
out.join('\n');
EOF

echo "== Xcode swift interpreter ==" | tee "$OUT/swift-interp.txt"
cat > "$OUT/t.swift" <<'EOF'
import Foundation
print(dlopen("/System/Library/PrivateFrameworks/WorkflowKit.framework/WorkflowKit", RTLD_NOW) != nil ? "swift-interp: WorkflowKit loaded" : "swift-interp: load failed: \(String(cString: dlerror()))")
print(NSClassFromString("WFActionRegistry") != nil ? "WFActionRegistry present" : "WFActionRegistry absent")
EOF
timeout 120 swift "$OUT/t.swift" 2>&1 | tee -a "$OUT/swift-interp.txt"

echo "== /usr/bin/python3 + ctypes ==" | tee "$OUT/python.txt"
/usr/bin/python3 - <<'EOF' 2>&1 | tee -a "$OUT/python.txt"
import ctypes, sys
print(sys.executable, sys.version.split()[0])
for n in ("WorkflowKit", "ActionKit"):
    try:
        ctypes.CDLL(f"/System/Library/PrivateFrameworks/{n}.framework/{n}")
        print(n, "loaded")
    except OSError as e:
        print(n, "FAILED:", e)
objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
objc.objc_getClass.restype = ctypes.c_void_p
objc.objc_getClass.argtypes = [ctypes.c_char_p]
for c in (b"WFActionRegistry", b"WFConditionalAction", b"WFControlFlowAction", b"WFAction"):
    print(c.decode(), "present" if objc.objc_getClass(c) else "absent")
EOF

echo "== csops: is the compiled probe a platform binary? ==" | tee "$OUT/codesign.txt"
for b in /usr/bin/osascript /usr/bin/python3 "$(xcrun -f swift-frontend 2>/dev/null)" ./probe; do
  [ -e "$b" ] && { echo "-- $b"; codesign -dv --verbose=4 "$b" 2>&1 | grep -Ei "platform|flags|identifier|TeamIdentifier|Authority" | head -6; } | tee -a "$OUT/codesign.txt"
done
echo "platform-test done"
