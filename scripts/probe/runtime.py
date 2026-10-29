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

# ---------------------------------------------------------------- stage 4/5: definitions and real serialization
import threading, traceback

_sendpp = raw(c_void_p, c_void_p, c_void_p, c_void_p, c_void_p)
_sendbool = raw(c_void_p, c_void_p, c_void_p, c_bool)
_sendll = raw(c_void_p, c_void_p, c_void_p, ctypes.c_longlong)
_validplist = raw(c_bool, c_void_p, c_void_p, c_void_p, c_ulong)
_plistdata = raw(c_void_p, c_void_p, c_void_p, c_void_p, c_ulong, c_ulong, c_void_p)


def ns(v):
    """Python -> Foundation object."""
    if isinstance(v, bool):
        return _sendbool(getClass(b"NSNumber"), sel("numberWithBool:"), v)
    if isinstance(v, int):
        return _sendll(getClass(b"NSNumber"), sel("numberWithLongLong:"), v)
    if isinstance(v, float):
        return raw(c_void_p, c_void_p, c_void_p, ctypes.c_double)(getClass(b"NSNumber"), sel("numberWithDouble:"), v)
    if isinstance(v, str):
        return nsstr(v)
    if isinstance(v, list):
        arr = msg(getClass(b"NSMutableArray"), "array")
        for x in v:
            _sendp(arr, sel("addObject:"), ns(x))
        return arr
    if isinstance(v, dict):
        d = msg(getClass(b"NSMutableDictionary"), "dictionary")
        for k, x in v.items():
            _sendpp(d, sel("setObject:forKey:"), ns(x), ns(k))
        return d
    raise TypeError(type(v))


def plist_text(obj):
    """XML plist text of obj if it is property-list-clean, else its description."""
    if not obj:
        return "nil"
    cls = getClass(b"NSPropertyListSerialization")
    if _validplist(cls, sel("propertyList:isValidForFormat:"), obj, 100):
        data = _plistdata(cls, sel("dataWithPropertyList:format:options:error:"), obj, 100, 0, None)
        if data:
            return ctypes.string_at(msg(data, "bytes"), _sendul(data, sel("length"))).decode("utf-8", "replace")
    return "<!-- not a clean property list; description follows -->\n" + desc(obj)


def block_call(block):
    invoke = ctypes.cast(block + 16, POINTER(c_void_p))[0]        # Block_literal_1.invoke
    return CFUNCTYPE(c_void_p, c_void_p)(invoke)(block)


def unwrap(obj):
    """Block -> its result; WFActionDefinition -> its backing dictionary."""
    for _ in range(3):
        if not obj:
            return obj
        cn = S(className(objGetClass(obj)))
        if "Block" in cn:
            obj = block_call(obj)
        elif cn.endswith("Definition") and responds(obj, "valueForKey:"):
            obj = _sendp(obj, sel("valueForKey:"), nsstr("_definition"))
        else:
            break
    return obj


def with_timeout(fn, secs, what):
    box = {}
    t = threading.Thread(target=lambda: box.setdefault("v", fn()), daemon=True)
    t.start()
    t.join(secs)
    if t.is_alive():
        log(f"TIMEOUT after {secs}s: {what}")
        return None
    return box.get("v")


def safe_name(k):
    return re.sub(r"[^A-Za-z0-9._-]", "_", k)[:150]


DEFDIR = f"{out_dir}/definitions"
SERDIR = f"{out_dir}/default-serialized"
os.makedirs(DEFDIR, exist_ok=True)
os.makedirs(SERDIR, exist_ok=True)

adr = getClass(b"WFActionDefinitionRegistry")
if adr:
    guarded("s4|rediscover", lambda: msg(adr, "rediscoverDefinitionsIfNeeded"))
    ran, regd = guarded("s4|registeredDefinitions", lambda: msg(adr, "registeredDefinitions"))
    pairs = items_of(regd) if ran else []
    log(f"stage 4: registeredDefinitions has {len(pairs)} entries (class {S(className(objGetClass(regd))) if regd else None})")
    if not pairs:
        # Fall back: the +actionDefinitionFor* methods register themselves when called.
        n = c_uint(0)
        arr = copyMethods(objGetClass(adr), ctypes.byref(n))
        names = [S(selName(methodSel(arr[i]))) for i in range(n.value)]
        names = [x for x in names if x.startswith("actionDefinitionFor")]
        for nm in names:
            guarded(f"s4|call.{nm}", lambda nm=nm: msg(adr, nm))
        ran, regd = guarded("s4|registeredDefinitions2", lambda: msg(adr, "registeredDefinitions"))
        pairs = items_of(regd) if ran else []
        log(f"stage 4 (after calling {len(names)} registrars): {len(pairs)} entries")
    for key, val in pairs:
        try:
            ran, d = guarded(f"s4|dump|{key}", lambda: unwrap(val))
            if ran and d:
                with open(f"{DEFDIR}/{safe_name(str(key))}.xml", "w", encoding="utf-8") as f:
                    f.write(f"<!-- key={key} class={S(className(objGetClass(d)))} -->\n" + plist_text(d))
        except Exception:
            log(f"stage 4 error on {key}: {traceback.format_exc(limit=2)}")
else:
    log("stage 4: WFActionDefinitionRegistry absent")

# stage 5: instantiate through the real registry and read back Apple's own serialization
reg_cls = getClass(b"WFActionRegistry")
ran, reg = guarded("s5|sharedRegistry", lambda: msg(reg_cls, "sharedRegistry")) if reg_cls else (False, None)
if ran and reg:
    with_timeout(lambda: guarded("s5|fill", lambda: msg(reg, "fill")), 120, "registry fill")
    ran, byid = guarded("s5|actionsByIdentifier", lambda: msg(reg, "actionsByIdentifier"))
    log(f"stage 5: actionsByIdentifier count after fill = {_sendul(byid, sel('count')) if byid else None}")
    if byid:
        for key, act in items_of(byid)[:3000]:
            try:
                if responds(act, "serializedRepresentation"):
                    ran, rep = guarded(f"s5|rep|{key}", lambda: msg(act, "serializedRepresentation"))
                    if ran and rep:
                        with open(f"{SERDIR}/{safe_name(str(key))}.xml", "w", encoding="utf-8") as f:
                            f.write(plist_text(rep))
            except Exception:
                log(f"stage 5 error on {key}: {traceback.format_exc(limit=2)}")

    # What does Apple write back for control flow? Feed in the legacy shapes this repo's generator uses.
    GID = "11111111-2222-3333-4444-555555555555"
    probes = {
        "conditional-legacy-hasanyvalue": ("is.workflow.actions.conditional", {
            "GroupingIdentifier": GID, "WFControlFlowMode": 0, "WFCondition": "Has Any Value",
            "WFInput": {"Type": "Variable", "Variable": {"Value": {"Type": "Variable", "VariableName": "Result"},
                                                          "WFSerializationType": "WFTextTokenAttachment"}}}),
        "conditional-legacy-contains": ("is.workflow.actions.conditional", {
            "GroupingIdentifier": GID, "WFControlFlowMode": 0, "WFCondition": "Contains",
            "WFConditionalActionString": "x",
            "WFInput": {"Type": "Variable", "Variable": {"Value": {"Type": "Variable", "VariableName": "A"},
                                                          "WFSerializationType": "WFTextTokenAttachment"}}}),
        "conditional-otherwise": ("is.workflow.actions.conditional", {"GroupingIdentifier": GID, "WFControlFlowMode": 1}),
        "conditional-end": ("is.workflow.actions.conditional", {"GroupingIdentifier": GID, "WFControlFlowMode": 2}),
        "conditional-bare": ("is.workflow.actions.conditional", {}),
        "menu-open": ("is.workflow.actions.choosefrommenu", {"GroupingIdentifier": GID, "WFControlFlowMode": 0,
                                                              "WFMenuPrompt": "Pick", "WFMenuItems": ["A", "B"]}),
        "menu-item": ("is.workflow.actions.choosefrommenu", {"GroupingIdentifier": GID, "WFControlFlowMode": 1,
                                                              "WFMenuItemTitle": "A"}),
        "repeat-count": ("is.workflow.actions.repeat.count", {"GroupingIdentifier": GID, "WFControlFlowMode": 0,
                                                               "WFRepeatCount": 3}),
        "repeat-each-bare": ("is.workflow.actions.repeat.each", {}),
        "replace-regex": ("is.workflow.actions.text.replace", {"WFReplaceTextFind": "a", "WFReplaceTextReplace": "b",
                                                               "WFReplaceTextRegularExpression": True}),
        "matchtext": ("is.workflow.actions.text.match", {"WFMatchTextPattern": "x"}),
        "setvariable": ("is.workflow.actions.setvariable", {"WFVariableName": "V"}),
    }
    for name, (ident, params) in probes.items():
        try:
            ran, act = guarded(f"s5|create|{name}", lambda: _sendpp(
                reg, sel("createActionWithIdentifier:serializedParameters:"), nsstr(ident), ns(params)))
            if not ran or not act:
                emit(f"// ===== probe {name}: create returned nil\n")
                continue
            ran, rep = guarded(f"s5|probe-rep|{name}", lambda: msg(act, "serializedRepresentation"))
            emit(f"// ===== probe {name} -> {S(className(objGetClass(act)))}\n// IN : {params}\n"
                 f"{plist_text(rep) if ran else 'skipped'}\n")
            if responds(act, "parameterDefinitions"):
                ran, pd = guarded(f"s5|probe-pd|{name}", lambda: msg(act, "parameterDefinitions"))
                if ran and pd:
                    emit(f"// ----- {name}.parameterDefinitions\n{desc(pd)[:300000]}\n")
        except Exception:
            log(f"stage 5 probe error {name}: {traceback.format_exc(limit=2)}")



# ---------------------------------------------------------------- stage 6: JSON definitions + Apple-side lint of sample shortcuts
import json, base64

_isKind = raw(c_bool, c_void_p, c_void_p, c_void_p)
_retll = raw(ctypes.c_longlong, c_void_p, c_void_p)
_retdbl = raw(ctypes.c_double, c_void_p, c_void_p)
_init3 = raw(c_void_p, c_void_p, c_void_p, c_void_p, c_void_p, c_bool)
_init4 = raw(c_void_p, c_void_p, c_void_p, c_void_p, c_void_p, c_void_p, POINTER(c_void_p))
_bool_err = raw(c_bool, c_void_p, c_void_p, c_void_p, POINTER(c_void_p))
_rec_err = raw(c_void_p, c_void_p, c_void_p, POINTER(c_void_p))
_NS = {n: getClass(n.encode()) for n in ("NSString", "NSNumber", "NSArray", "NSDictionary", "NSData", "NSDate", "NSNull", "NSSet")}


def is_kind(o, n):
    return bool(_isKind(o, sel("isKindOfClass:"), _NS[n]))


def has_ivar(o, name):
    n = c_uint(0)
    arr = copyIvars(objGetClass(o), ctypes.byref(n))
    found = bool(arr) and any(S(ivarName(arr[i])) == name for i in range(n.value))
    if arr:
        libc.free(arr)
    return found


LOC = re.compile(r'LocalizationValue\(arguments: \[\], key: \\*"([^"\\]*)')


def to_py(o, depth=0):
    """Recursive Foundation -> JSON-able Python. Unwraps WF*Definition objects and localized strings."""
    if not o:
        return None
    if depth > 14:
        return "<max depth>"
    cn = S(className(objGetClass(o)))
    if is_kind(o, "NSString"):
        return S(_sendstr(o, sel("UTF8String")))
    if is_kind(o, "NSNumber"):
        if "Boolean" in cn:
            return bool(_retll(o, sel("longLongValue")))
        if S(_sendstr(o, sel("objCType"))) in ("f", "d"):
            return _retdbl(o, sel("doubleValue"))
        return _retll(o, sel("longLongValue"))
    if is_kind(o, "NSNull"):
        return None
    if is_kind(o, "NSData"):
        n = _sendul(o, sel("length"))
        return {"__data_b64__": base64.b64encode(ctypes.string_at(msg(o, "bytes"), min(n, 100000))).decode(), "length": n}
    if is_kind(o, "NSDate"):
        return {"__date__": desc(o)}
    if is_kind(o, "NSDictionary"):
        return {desc(k): to_py(v, depth + 1) for k, v in items_of(o)}
    if is_kind(o, "NSArray") or is_kind(o, "NSSet"):
        arr = o if is_kind(o, "NSArray") else msg(o, "allObjects")
        return [to_py(x, depth + 1) for x in _arr(arr)]
    if has_ivar(o, "_definition"):
        return to_py(_sendp(o, sel("valueForKey:"), nsstr("_definition")), depth + 1)
    text = desc(o)
    m = LOC.search(text)
    if m or "Localiz" in cn:
        return {"__localized__": m.group(1) if m else text[:300]}
    return {"__object__": cn, "description": text[:1500]}


def diff_params(inp, out, path=""):
    f = []
    if isinstance(inp, dict) and isinstance(out, dict):
        f += [f"dropped {path}{k}" for k in inp if k not in out]
        f += [f"added {path}{k}" for k in out if k not in inp]
        for k in inp:
            if k in out:
                f += diff_params(inp[k], out[k], f"{path}{k}.")
    elif isinstance(inp, list) and isinstance(out, list):
        if len(inp) != len(out):
            f.append(f"list length changed at {path}: {len(inp)} -> {len(out)}")
        else:
            for i, (a, b) in enumerate(zip(inp, out)):
                f += diff_params(a, b, f"{path}[{i}].")
    elif inp != out:
        f.append(f"changed {path}: {inp!r} -> {out!r}")
    return f


JSONDIR = f"{out_dir}/definitions-json"
LINTDIR = f"{out_dir}/lint"
os.makedirs(JSONDIR, exist_ok=True)
os.makedirs(LINTDIR, exist_ok=True)

# 6a. every registered definition as JSON (parameters unwrapped, localized strings resolved)
if adr:
    ran, regd = guarded("s6|registeredDefinitions", lambda: msg(adr, "registeredDefinitions"))
    merged = {}
    for key, val in (items_of(regd) if ran and regd else []):
        try:
            ran2, d = guarded(f"s6|def|{key}", lambda: unwrap(val))
            if ran2 and d:
                py = to_py(d)
                merged[str(key)] = py
                with open(f"{JSONDIR}/{safe_name(str(key))}.json", "w", encoding="utf-8") as f:
                    json.dump(py, f, indent=1, sort_keys=True, default=str)
        except Exception:
            log(f"stage 6a error on {key}: {traceback.format_exc(limit=2)}")
    with open(f"{out_dir}/action-definitions.json", "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=1, sort_keys=True, default=str)
    log(f"stage 6a: {len(merged)} definitions written as JSON")

# 6b. default serialization of every bundled action, via the bundled provider
if reg:
    provs_obj = msg(reg, "actionProvidersForLoading")
    provs = _arr(provs_obj) if provs_obj else []
    bundled = [p for p in provs if S(className(objGetClass(p))) == "WFBundledActionProvider"]
    if bundled:
        ran, acts = guarded("s6|createAll", lambda: with_timeout(lambda: msg(bundled[0], "createAllAvailableActions"), 180, "createAllAvailableActions"))
        defaults = {}
        if ran and acts:
            for i, a in enumerate(_arr(acts)):
                try:
                    ran2, rep = guarded(f"s6|ser|{i}", lambda: msg(a, "serializedRepresentation"))
                    if ran2 and rep:
                        py = to_py(rep)
                        defaults[py.get("WFWorkflowActionIdentifier", f"#{i}")] = py
                except Exception:
                    log(f"stage 6b error #{i}: {traceback.format_exc(limit=2)}")
        with open(f"{out_dir}/default-serialized.json", "w", encoding="utf-8") as f:
            json.dump(defaults, f, indent=1, sort_keys=True, default=str)
        log(f"stage 6b: {len(defaults)} default serialized actions")

# 6c. run sample shortcuts through Apple's own import path and diff every action against the registry round-trip
samples_dir = sys.argv[3] if len(sys.argv) > 3 else None
if samples_dir and os.path.isdir(samples_dir) and reg:
    wff = getClass(b"WFWorkflowFile")
    for fn in sorted(os.listdir(samples_dir)):
        if not fn.endswith((".plist", ".wflow", ".shortcut")):
            continue
        path = os.path.join(samples_dir, fn)
        name = os.path.splitext(fn)[0]
        report = {"file": fn}
        try:
            orig = to_py(_sendp(getClass(b"NSDictionary"), sel("dictionaryWithContentsOfFile:"), nsstr(path)))
            if not orig:
                report["error"] = "could not parse as a property list"
            else:
                report["client_version"] = orig.get("WFWorkflowClientVersion")
                for migrate in (False, True):
                    ran, f = guarded(f"s6|file|{name}|{migrate}", lambda: _init3(
                        msg(wff, "alloc"), sel("initWithDictionary:name:performMigration:"),
                        _sendp(getClass(b"NSDictionary"), sel("dictionaryWithContentsOfFile:"), nsstr(path)),
                        nsstr(name), migrate))
                    if ran and f:
                        root = msg(f, "rootObject")
                        with open(f"{LINTDIR}/{name}.migrate-{str(migrate).lower()}.xml", "w", encoding="utf-8") as fh:
                            fh.write(plist_text(root))
                        report[f"migrate_{str(migrate).lower()}_diff_vs_input"] = diff_params(
                            {k: v for k, v in orig.items() if k != "WFWorkflowActions"},
                            {k: v for k, v in (to_py(root) or {}).items() if k != "WFWorkflowActions"})
                        mig_actions = (to_py(root) or {}).get("WFWorkflowActions", [])
                        report[f"migrate_{str(migrate).lower()}_action_changes"] = [
                            {"index": i, "id": a.get("WFWorkflowActionIdentifier"),
                             "findings": diff_params(o.get("WFWorkflowActionParameters", {}), a.get("WFWorkflowActionParameters", {}))}
                            for i, (o, a) in enumerate(zip(orig.get("WFWorkflowActions", []), mig_actions))
                            if diff_params(o.get("WFWorkflowActionParameters", {}), a.get("WFWorkflowActionParameters", {}))]
                # registry round trip, action by action, against the ORIGINAL (unmigrated) parameters
                rt = []
                for i, a in enumerate(orig.get("WFWorkflowActions", [])):
                    ident = a.get("WFWorkflowActionIdentifier")
                    params = a.get("WFWorkflowActionParameters", {})
                    try:
                        ran, obj = guarded(f"s6|rt|{name}|{i}", lambda: _sendpp(
                            reg, sel("createActionWithIdentifier:serializedParameters:"), nsstr(ident), ns(params)))
                        if not ran:
                            rt.append({"index": i, "id": ident, "findings": ["skipped: crashed on an earlier attempt"]})
                            continue
                        if not obj:
                            rt.append({"index": i, "id": ident, "findings": ["registry returned nil (unknown identifier?)"]})
                            continue
                        ran, rep = guarded(f"s6|rtrep|{name}|{i}", lambda: msg(obj, "serializedRepresentation"))
                        out = (to_py(rep) or {}).get("WFWorkflowActionParameters", {}) if ran else {}
                        fnd = diff_params(params, out)
                        if fnd:
                            rt.append({"index": i, "id": ident, "class": S(className(objGetClass(obj))), "findings": fnd})
                    except TypeError as e:
                        rt.append({"index": i, "id": ident, "findings": [f"python could not marshal parameter: {e}"]})
                report["registry_roundtrip_findings"] = rt
                # Apple's import validator, if we can build a WFWorkflow without a database
                ran, f = guarded(f"s6|file-v|{name}", lambda: _init3(
                    msg(wff, "alloc"), sel("initWithDictionary:name:performMigration:"),
                    _sendp(getClass(b"NSDictionary"), sel("dictionaryWithContentsOfFile:"), nsstr(path)), nsstr(name), True))
                if ran and f:
                    err = c_void_p()
                    ran, rec = guarded(f"s6|rec|{name}", lambda: _rec_err(f, sel("recordRepresentationWithError:"), ctypes.byref(err)))
                    report["record_error"] = desc(err.value) if err.value else None
                    if ran and rec:
                        err2 = c_void_p()
                        ran, wf = guarded(f"s6|wf|{name}", lambda: _init4(
                            msg(getClass(b"WFWorkflow"), "alloc"), sel("initWithRecord:reference:storageProvider:error:"),
                            rec, None, None, ctypes.byref(err2)))
                        report["workflow_error"] = desc(err2.value) if err2.value else None
                        if ran and wf:
                            err3 = c_void_p()
                            ran, ok = guarded(f"s6|validate|{name}", lambda: _bool_err(
                                getClass(b"WFShortcutValidator"), sel("validateForImportWorkflow:error:"), wf, ctypes.byref(err3)))
                            report["validateForImport"] = {"ok": bool(ok) if ran else None,
                                                           "error": desc(err3.value) if err3.value else None}
        except Exception:
            report["exception"] = traceback.format_exc(limit=3)
        with open(f"{LINTDIR}/{name}.report.json", "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1, default=str)
        log(f"stage 6c: linted {fn}")


log("probe finished")
sys.stdout.flush()
os._exit(0)
