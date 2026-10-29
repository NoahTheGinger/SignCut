#!/usr/bin/python3
"""Runtime introspection of Apple's Shortcuts frameworks on macOS.

Must run under Apple's /usr/bin/python3 (a platform binary): ActionKit asserts that its host process is
one, so a self-compiled probe cannot load it.

    /usr/bin/python3 runtime.py DLOPEN_LIST OUT_DIR

Stage 1 dumps every class from the Workflow/ActionKit/ToolKit images (class-dump style).
Stage 2 finds action-registry singletons, calls zero-argument getters and dumps what they return,
        including each returned object's `identifier` and `definition` when it has them.
Stage 3 (the real prize) asks the registry for each action by identifier and dumps its definition,
        including control flow (conditional / choosefrommenu / repeat.*), which ToolKit doesn't list.

ObjC exceptions kill the process. Every call is logged to progress.log first, and the driver re-runs this
script, skipping calls that never finished.
"""
import ctypes
import os
import re
import sys
from ctypes import (CFUNCTYPE, POINTER, c_bool, c_char_p, c_int64, c_uint, c_ulong, c_void_p, cast)

list_path, out_dir = sys.argv[1], sys.argv[2]
os.makedirs(out_dir, exist_ok=True)
LOG, PROGRESS = f"{out_dir}/probe.log", f"{out_dir}/progress.log"

libc = ctypes.CDLL("/usr/lib/libc.dylib")
libc.free.argtypes = [c_void_p]
objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
ctypes.CDLL("/System/Library/Frameworks/Foundation.framework/Foundation")

def sig(name, restype, *argtypes):
    f = getattr(objc, name)
    f.restype, f.argtypes = restype, list(argtypes)
    return f

getClass = sig("objc_getClass", c_void_p, c_char_p)
selReg = sig("sel_registerName", c_void_p, c_char_p)
selName = sig("sel_getName", c_char_p, c_void_p)
copyClassList = sig("objc_copyClassList", POINTER(c_void_p), POINTER(c_uint))
className = sig("class_getName", c_char_p, c_void_p)
classImage = sig("class_getImageName", c_char_p, c_void_p)
superclass = sig("class_getSuperclass", c_void_p, c_void_p)
objGetClass = sig("object_getClass", c_void_p, c_void_p)
copyMethods = sig("class_copyMethodList", POINTER(c_void_p), c_void_p, POINTER(c_uint))
methodSel = sig("method_getName", c_void_p, c_void_p)
methodEnc = sig("method_getTypeEncoding", c_char_p, c_void_p)
methodRet = sig("method_copyReturnType", c_void_p, c_void_p)
copyIvars = sig("class_copyIvarList", POINTER(c_void_p), c_void_p, POINTER(c_uint))
ivarName = sig("ivar_getName", c_char_p, c_void_p)
ivarEnc = sig("ivar_getTypeEncoding", c_char_p, c_void_p)
copyProps = sig("class_copyPropertyList", POINTER(c_void_p), c_void_p, POINTER(c_uint))
propName = sig("property_getName", c_char_p, c_void_p)
propAttrs = sig("property_getAttributes", c_char_p, c_void_p)
copyProtos = sig("class_copyProtocolList", POINTER(c_void_p), c_void_p, POINTER(c_uint))
protoName = sig("protocol_getName", c_char_p, c_void_p)
respondsCls = sig("class_respondsToSelector", c_bool, c_void_p, c_void_p)

def S(b):
    return b.decode("utf-8", "replace") if b else "?"

def log(msg):
    print(msg, file=sys.stderr, flush=True)
    with open(LOG, "a") as f:
        f.write(msg + "\n")

def raw(restype, *argtypes):
    return CFUNCTYPE(restype, *argtypes)(("objc_msgSend", objc))

_send0 = raw(c_void_p, c_void_p, c_void_p)
_sendp = raw(c_void_p, c_void_p, c_void_p, c_void_p)
_sendu = raw(c_void_p, c_void_p, c_void_p, c_ulong)
_sendstr = raw(c_char_p, c_void_p, c_void_p)
_sendul = raw(c_ulong, c_void_p, c_void_p)

def sel(name):
    return selReg(name.encode())

def responds(obj, name):
    return bool(obj) and respondsCls(objGetClass(obj), sel(name))

def msg(obj, name, arg=None):
    return _send0(obj, sel(name)) if arg is None else _sendp(obj, sel(name), arg)

def nsstr(s):
    return _sendp(getClass(b"NSString"), sel("stringWithUTF8String:"), ctypes.cast(ctypes.c_char_p(s.encode()), c_void_p))

def desc(obj):
    if not obj:
        return "nil"
    d = msg(obj, "description")
    return S(_sendstr(d, sel("UTF8String"))) if d else "?"

# ---------------------------------------------------------------- stage 1
for p in open(list_path).read().split():
    try:
        ctypes.CDLL(p, mode=ctypes.RTLD_GLOBAL)   # binaries live in the dyld cache, so no os.path.exists check
        log(f"dlopen ok   {p}")
    except OSError as e:
        log(f"dlopen FAIL {p}: {e}")

FILTER = ("Workflow", "ToolKit", "ActionKit", "Shortcut", "LinkMetadata", "LinkServices", "AppIntents")

def methods(cls, prefix):
    n = c_uint(0)
    arr = copyMethods(cls, ctypes.byref(n))
    out = [f"  {prefix} {S(selName(methodSel(arr[i])))} {S(methodEnc(arr[i]))}" for i in range(n.value)]
    if arr:
        libc.free(arr)
    return out

def dump_class(cls):
    lines = [f"@interface {S(className(cls))}" + (f" : {S(className(superclass(cls)))}" if superclass(cls) else "")]
    n = c_uint(0)
    pl = copyProtos(cls, ctypes.byref(n))
    if pl:
        lines[0] += " <" + ", ".join(S(protoName(pl[i])) for i in range(n.value)) + ">"
        libc.free(pl)
    il = copyIvars(cls, ctypes.byref(n))
    if il:
        lines += [f"  ivar {S(ivarName(il[i]))} {S(ivarEnc(il[i]))}" for i in range(n.value)]
        libc.free(il)
    pr = copyProps(cls, ctypes.byref(n))
    if pr:
        lines += [f"  prop {S(propName(pr[i]))} {S(propAttrs(pr[i]))}" for i in range(n.value)]
        libc.free(pr)
    lines += methods(objGetClass(cls), "+") + methods(cls, "-") + ["@end", ""]
    return "\n".join(lines)

if not os.path.exists(f"{out_dir}/classes.txt"):
    n = c_uint(0)
    allc = copyClassList(ctypes.byref(n))
    by_image = {}
    for i in range(n.value):
        img = classImage(allc[i])
        if img and any(f in S(img) for f in FILTER):
            by_image.setdefault(S(img), []).append(allc[i])
    total = 0
    with open(f"{out_dir}/classes.txt", "w") as f:
        for img in sorted(by_image):
            f.write(f"// ===== IMAGE {img} ({len(by_image[img])} classes)\n")
            for c in sorted(by_image[img], key=lambda c: S(className(c))):
                f.write(dump_class(c) + "\n")
                total += 1
    log(f"stage 1: {total} classes dumped from {n.value} total")

# ---------------------------------------------------------------- stage 2/3
done, began = set(), set()
if os.path.exists(PROGRESS):
    for line in open(PROGRESS).read().splitlines():
        if line.startswith("BEGIN "):
            began.add(line[6:])
        elif line.startswith("END "):
            done.add(line[4:])
skip = began - done
if skip:
    log(f"skipping calls that crashed earlier: {sorted(skip)}")

def guarded(key, fn):
    """Run fn() with crash bookkeeping; returns (ran, value)."""
    if key in skip:
        return False, None
    with open(PROGRESS, "a") as f:
        f.write(f"BEGIN {key}\n")
    v = fn()
    with open(PROGRESS, "a") as f:
        f.write(f"END {key}\n")
    return True, v

GETTER = re.compile(r"(all|definition|action|identifier|parameter|categor|registry|descriptor|library|catalog)", re.I)
DENY = re.compile(r"(delete|remove|reset|clear|save|write|sync|upload|purge|terminate|exit|kill|dealloc|release|retain|autorelease|init|new$|copy|mutableCopy)", re.I)

def getters(cls, meta):
    names, c = set(), (objGetClass(cls) if meta else cls)
    while c and S(className(c)) not in ("NSObject", "NSProxy"):
        n = c_uint(0)
        arr = copyMethods(c, ctypes.byref(n))
        for i in range(n.value):
            nm = S(selName(methodSel(arr[i])))
            rt = methodRet(arr[i])
            is_obj = bool(rt) and ctypes.string_at(rt).startswith(b"@")
            if rt:
                libc.free(rt)
            if ":" not in nm and is_obj and GETTER.search(nm) and not DENY.search(nm):
                names.add(nm)
        if arr:
            libc.free(arr)
        c = superclass(c)
    return sorted(names)

REG_OUT = f"{out_dir}/registry-dump.txt"

def emit(text):
    with open(REG_OUT, "a") as f:
        f.write(text)

def items_of(obj):
    """(key, value) pairs for NSDictionary, (index, value) for NSArray, else []."""
    if not obj:
        return []
    if responds(obj, "allKeys") and responds(obj, "objectForKey:"):
        keys = msg(obj, "allKeys")
        return [(desc(k), msg(obj, "objectForKey:", k)) for k in _arr(keys)]
    if responds(obj, "objectAtIndex:") and responds(obj, "count"):
        return list(enumerate(_arr(obj)))
    return []

def _arr(a):
    n = _sendul(a, sel("count"))
    return [_sendu(a, sel("objectAtIndex:"), i) for i in range(n)]

def call_and_dump(target, label, name):
    ran, val = guarded(f"{label}|{name}", lambda: msg(target, name))
    if not ran:
        return None
    text = desc(val)
    emit(f"// ===== {label} {name} -> {S(className(objGetClass(val))) if val else 'nil'} ({len(text)} chars)\n{text[:30_000_000]}\n\n")
    for key, item in items_of(val)[:5000]:
        if not item:
            continue
        for s in ("definition", "actionDefinition", "serializedParameters", "parameters"):
            if responds(item, s):
                ran2, v2 = guarded(f"{label}|{name}|item.{s}", lambda: msg(item, s))
                if ran2:
                    ident = desc(msg(item, "identifier")) if responds(item, "identifier") else str(key)
                    emit(f"--- {label}.{name}[{key}] ident={ident} .{s}\n{desc(v2)[:200000]}\n")
    return val

CANDIDATES = [
    ("WFActionRegistry", ["sharedRegistry", "sharedInstance", "defaultRegistry", "shared"]),
    ("WFActionManager", ["sharedManager", "sharedInstance", "shared"]),
    ("WFWorkflowActionRegistry", ["sharedRegistry", "sharedInstance", "shared"]),
    ("WFActionDefinitionStore", ["sharedStore", "sharedInstance", "shared"]),
]
for cname, sels in CANDIDATES:
    cls = getClass(cname.encode())
    if not cls:
        log(f"stage 2: {cname} absent")
        continue
    log(f"stage 2: {cname} present")
    for g in getters(cls, meta=True):
        call_and_dump(cls, f"+{cname}", g)
    for s in sels:
        if not respondsCls(objGetClass(cls), sel(s)):
            continue
        ran, inst = guarded(f"+{cname}|{s}", lambda: msg(cls, s))
        if not ran or not inst:
            continue
        log(f"stage 2: instance via +{cname} {s}: {S(className(objGetClass(inst)))}")
        for g in getters(objGetClass(inst), meta=False):
            call_and_dump(inst, cname, g)
        break

# stage 3: ask for specific actions by identifier (selector names guessed from the class dump; each is guarded)
WANTED = ["is.workflow.actions.conditional", "is.workflow.actions.choosefrommenu",
          "is.workflow.actions.repeat.count", "is.workflow.actions.repeat.each", "is.workflow.actions.gettext"]
reg_cls = getClass(b"WFActionRegistry")
if reg_cls:
    ran, reg = guarded("stage3|sharedRegistry", lambda: msg(reg_cls, "sharedRegistry"))
    if ran and reg:
        for ident in WANTED:
            for s in ("actionForIdentifier:", "actionWithIdentifier:", "definitionForIdentifier:",
                      "actionDefinitionForIdentifier:", "createActionWithIdentifier:"):
                if not responds(reg, s):
                    continue
                ran2, a = guarded(f"stage3|{s}|{ident}", lambda: _sendp(reg, sel(s), nsstr(ident)))
                if ran2 and a:
                    emit(f"// ===== stage3 {s} {ident} -> {S(className(objGetClass(a)))}\n{desc(a)}\n")
                    for p in ("definition", "parameters", "parameterDefinitions", "serializedParameters", "metadata"):
                        if responds(a, p):
                            ran3, v = guarded(f"stage3|{s}|{ident}|{p}", lambda: msg(a, p))
                            if ran3:
                                emit(f"--- {ident}.{p}\n{desc(v)[:500000]}\n")
log("probe finished")
