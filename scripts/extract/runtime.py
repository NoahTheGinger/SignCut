#!/usr/bin/python3
"""Introspect Apple's own Shortcuts engine (WorkflowKit / ActionKit) on macOS.

Run it with Apple's /usr/bin/python3 - ActionKit asserts that its host process is an Apple platform
binary, so a self-compiled helper or a Homebrew/pyenv Python cannot load it.

    /usr/bin/python3 runtime.py extract FRAMEWORK_LIST OUT_DIR
    /usr/bin/python3 runtime.py lint    FRAMEWORK_LIST OUT_DIR SHORTCUTS_DIR

extract  Dumps what the ToolKit database does not contain: the classic action definitions (including the
         control-flow actions If / Choose from Menu / Repeat), every parameter's UI/serialization class,
         a class dump of the WorkflowKit stack, and a few round-trip probes of the control-flow actions.
lint     Feeds each .plist/.shortcut/.wflow through Apple's real import path: runs Apple's migrations,
         round-trips every action through the live action registry, and runs the import validator.

Native crashes (ObjC exceptions, Swift traps) cannot be caught from Python. Every risky call is logged to
progress.log first; the driver re-runs this script and skips any call that never finished.
"""
import base64
import ctypes
import faulthandler
import json
import os
import re
import signal
import sys
import traceback
from ctypes import CFUNCTYPE, POINTER, c_bool, c_char_p, c_uint, c_ulong, c_void_p

MODE, list_path, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
target_dir = sys.argv[4] if len(sys.argv) > 4 else None
os.makedirs(out_dir, exist_ok=True)
LOG, PROGRESS = f"{out_dir}/probe.log", f"{out_dir}/progress.log"

_fh = open(f"{out_dir}/fault.log", "a")
faulthandler.enable(file=_fh, all_threads=True)
faulthandler.register(signal.SIGTRAP, file=_fh, all_threads=True, chain=True)  # Swift traps arrive as SIGTRAP

libc = ctypes.CDLL("/usr/lib/libc.dylib")
libc.free.argtypes = [c_void_p]
objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
ctypes.CDLL("/System/Library/Frameworks/Foundation.framework/Foundation")


# ------------------------------------------------------------------ ObjC runtime bindings
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


def trace(what):
    """Persist the last thing touched so a native crash can be attributed."""
    with open(f"{out_dir}/trace.log", "w") as f:
        f.write(what)


def raw(restype, *argtypes):
    return CFUNCTYPE(restype, *argtypes)(("objc_msgSend", objc))


_send0 = raw(c_void_p, c_void_p, c_void_p)
_sendp = raw(c_void_p, c_void_p, c_void_p, c_void_p)
_sendpp = raw(c_void_p, c_void_p, c_void_p, c_void_p, c_void_p)
_sendu = raw(c_void_p, c_void_p, c_void_p, c_ulong)
_sendstr = raw(c_char_p, c_void_p, c_void_p)
_sendul = raw(c_ulong, c_void_p, c_void_p)
_sendbool = raw(c_void_p, c_void_p, c_void_p, c_bool)
_sendll = raw(c_void_p, c_void_p, c_void_p, ctypes.c_longlong)
_senddbl = raw(c_void_p, c_void_p, c_void_p, ctypes.c_double)
_retll = raw(ctypes.c_longlong, c_void_p, c_void_p)
_retdbl = raw(ctypes.c_double, c_void_p, c_void_p)
_isKind = raw(c_bool, c_void_p, c_void_p, c_void_p)
_validplist = raw(c_bool, c_void_p, c_void_p, c_void_p, c_ulong)
_plistdata = raw(c_void_p, c_void_p, c_void_p, c_void_p, c_ulong, c_ulong, c_void_p)
_init3 = raw(c_void_p, c_void_p, c_void_p, c_void_p, c_void_p, c_bool)
_init4 = raw(c_void_p, c_void_p, c_void_p, c_void_p, c_void_p, c_void_p, POINTER(c_void_p))
_bool_err = raw(c_bool, c_void_p, c_void_p, c_void_p, POINTER(c_void_p))
_rec_err = raw(c_void_p, c_void_p, c_void_p, POINTER(c_void_p))


def sel(name):
    return selReg(name.encode())


def responds(obj, name):
    return bool(obj) and respondsCls(objGetClass(obj), sel(name))


def msg(obj, name, arg=None):
    return _send0(obj, sel(name)) if arg is None else _sendp(obj, sel(name), arg)


def nsstr(s):
    return _sendp(getClass(b"NSString"), sel("stringWithUTF8String:"),
                  ctypes.cast(ctypes.c_char_p(s.encode()), c_void_p))


def desc(obj):
    if not obj:
        return "nil"
    d = msg(obj, "description")
    return S(_sendstr(d, sel("UTF8String"))) if d else "?"


def _arr(a):
    return [_sendu(a, sel("objectAtIndex:"), i) for i in range(_sendul(a, sel("count")))]


def items_of(obj):
    """(key, value) pairs for an NSDictionary, (index, value) for an NSArray, else []."""
    if not obj:
        return []
    if responds(obj, "allKeys") and responds(obj, "objectForKey:"):
        out = []
        for k in _arr(msg(obj, "allKeys")):
            trace(f"objectForKey: {desc(k)}")
            out.append((desc(k), msg(obj, "objectForKey:", k)))
        return out
    if responds(obj, "objectAtIndex:") and responds(obj, "count"):
        return list(enumerate(_arr(obj)))
    return []


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


# ------------------------------------------------------------------ Python <-> Foundation
def ns(v):
    """Python -> Foundation object."""
    if isinstance(v, bool):
        return _sendbool(getClass(b"NSNumber"), sel("numberWithBool:"), v)
    if isinstance(v, int):
        return _sendll(getClass(b"NSNumber"), sel("numberWithLongLong:"), v)
    if isinstance(v, float):
        return _senddbl(getClass(b"NSNumber"), sel("numberWithDouble:"), v)
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
    raise TypeError(f"cannot marshal {type(v).__name__}")


SUMMARY_IVARS = {
    "WFActionParameterSummary": ["_title", "_singleFormatString", "_possibleValues"],
    "WFActionParameterSummaryValue": ["_key", "_summaryString", "_requiredValues", "_requiredVisibleParameterKeys"],
}
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
        if n == 0:
            return {"__data_b64__": "", "length": 0}
        return {"__data_b64__": base64.b64encode(ctypes.string_at(msg(o, "bytes"), min(n, 100000))).decode(), "length": n}
    if is_kind(o, "NSDate"):
        return {"__date__": desc(o)}
    if is_kind(o, "NSDictionary"):
        trace(f"dict {cn}")
        return {str(k): to_py(v, depth + 1) for k, v in items_of(o)}
    if is_kind(o, "NSArray") or is_kind(o, "NSSet"):
        return [to_py(x, depth + 1) for x in _arr(o if is_kind(o, "NSArray") else msg(o, "allObjects"))]
    trace(cn)
    if has_ivar(o, "_definition"):  # WFActionDefinition / WFParameterDefinition / ... wrap an NSDictionary
        return to_py(_sendp(o, sel("valueForKey:"), nsstr("_definition")), depth + 1)
    if cn in SUMMARY_IVARS:  # read ivars directly; -description can trap on these
        return {iv.lstrip("_"): to_py(_sendp(o, sel("valueForKey:"), nsstr(iv)), depth + 1) for iv in SUMMARY_IVARS[cn]}
    if "Localiz" in cn:
        text = desc(o)
        m = LOC.search(text)
        return {"__localized__": m.group(1) if m else text[:300]}
    return {"__object__": cn}


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


def unwrap(obj):
    """Block -> its result; *Definition wrapper -> its backing dictionary."""
    for _ in range(3):
        if not obj:
            return obj
        cn = S(className(objGetClass(obj)))
        if "Block" in cn:
            invoke = ctypes.cast(obj + 16, POINTER(c_void_p))[0]  # Block_literal_1.invoke
            obj = CFUNCTYPE(c_void_p, c_void_p)(invoke)(obj)
        elif cn.endswith("Definition") and responds(obj, "valueForKey:"):
            obj = _sendp(obj, sel("valueForKey:"), nsstr("_definition"))
        else:
            break
    return obj


# ------------------------------------------------------------------ crash bookkeeping
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
    try:
        log(f"last thing touched before the previous crash: {open(f'{out_dir}/trace.log').read()}")
    except OSError:
        pass


def guarded(key, fn):
    """Run fn() with crash bookkeeping; returns (ran, value). ran is False if it crashed on an earlier attempt."""
    if key in skip:
        return False, None
    with open(PROGRESS, "a") as f:
        f.write(f"BEGIN {key}\n")
    v = fn()
    with open(PROGRESS, "a") as f:
        f.write(f"END {key}\n")
    return True, v


def safe_name(k):
    return re.sub(r"[^A-Za-z0-9._-]", "_", k)[:150]


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


# ------------------------------------------------------------------ load the frameworks
for p in open(list_path).read().split():
    try:
        ctypes.CDLL(p, mode=ctypes.RTLD_GLOBAL)  # binaries live in the dyld shared cache, so no os.path.exists check
    except OSError as e:
        log(f"dlopen FAIL {p}: {e}")

reg_cls = getClass(b"WFActionRegistry")
ran, reg = guarded("sharedRegistry", lambda: msg(reg_cls, "sharedRegistry")) if reg_cls else (False, None)
wff = getClass(b"WFWorkflowFile")
NSDictionary = getClass(b"NSDictionary")


def migrated_file(ns_dict, name, migrate):
    return _init3(msg(wff, "alloc"), sel("initWithDictionary:name:performMigration:"), ns_dict, nsstr(name), migrate)


# ------------------------------------------------------------------ extract
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
    return "\n".join(lines + methods(objGetClass(cls), "+") + methods(cls, "-") + ["@end", ""])


def class_dump():
    path = f"{out_dir}/workflowkit-class-dump.txt"
    if os.path.exists(path):
        return
    n = c_uint(0)
    allc = copyClassList(ctypes.byref(n))
    by_image = {}
    for i in range(n.value):
        img = classImage(allc[i])
        if img and any(f in S(img) for f in ("Workflow", "ToolKit", "ActionKit", "Shortcut", "LinkMetadata", "LinkServices", "AppIntents")):
            by_image.setdefault(S(img), []).append(allc[i])
    total = 0
    with open(path, "w") as f:
        for img in sorted(by_image):
            f.write(f"// ===== IMAGE {img} ({len(by_image[img])} classes)\n")
            for c in sorted(by_image[img], key=lambda c: S(className(c))):
                f.write(dump_class(c) + "\n")
                total += 1
    log(f"class dump: {total} classes")


def definitions():
    adr = getClass(b"WFActionDefinitionRegistry")
    if not adr:
        log("WFActionDefinitionRegistry absent")
        return
    guarded("rediscover", lambda: msg(adr, "rediscoverDefinitionsIfNeeded"))
    ran, regd = guarded("registeredDefinitions", lambda: msg(adr, "registeredDefinitions"))
    merged = {}
    for key, val in (items_of(regd) if ran and regd else []):
        try:
            ran2, py = guarded(f"def|{key}", lambda: to_py(unwrap(val)))
            if not ran2:
                merged[str(key)] = {"__error__": "native crash while converting this definition"}
            elif py:
                merged[str(key)] = py
        except Exception:
            log(f"definition error on {key}: {traceback.format_exc(limit=2)}")
    with open(f"{out_dir}/action-definitions.json", "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=1, sort_keys=True, default=str)
    log(f"definitions: {len(merged)} written")


GID = "11111111-2222-3333-4444-555555555555"
PROBES = {  # what Apple's registry writes back for control flow
    "conditional-open-legacy": ("is.workflow.actions.conditional", {
        "GroupingIdentifier": GID, "WFControlFlowMode": 0, "WFCondition": "Has Any Value",
        "WFInput": {"Type": "Variable", "Variable": {"Value": {"Type": "Variable", "VariableName": "X"},
                                                      "WFSerializationType": "WFTextTokenAttachment"}}}),
    "conditional-otherwise": ("is.workflow.actions.conditional", {"GroupingIdentifier": GID, "WFControlFlowMode": 1}),
    "conditional-end": ("is.workflow.actions.conditional", {"GroupingIdentifier": GID, "WFControlFlowMode": 2}),
    "menu-open": ("is.workflow.actions.choosefrommenu", {"GroupingIdentifier": GID, "WFControlFlowMode": 0,
                                                          "WFMenuPrompt": "Pick", "WFMenuItems": ["A", "B"]}),
    "menu-item": ("is.workflow.actions.choosefrommenu", {"GroupingIdentifier": GID, "WFControlFlowMode": 1,
                                                          "WFMenuItemTitle": "A"}),
    "repeat-count-open": ("is.workflow.actions.repeat.count", {"GroupingIdentifier": GID, "WFControlFlowMode": 0, "WFRepeatCount": 3}),
    "repeat-each-open": ("is.workflow.actions.repeat.each", {"GroupingIdentifier": GID, "WFControlFlowMode": 0}),
}


def control_flow_probes():
    if not reg:
        return
    with open(f"{out_dir}/control-flow-probes.xml", "w", encoding="utf-8") as out:
        for name, (ident, params) in PROBES.items():
            try:
                ran, act = guarded(f"probe|{name}", lambda: _sendpp(
                    reg, sel("createActionWithIdentifier:serializedParameters:"), nsstr(ident), ns(params)))
                if not ran or not act:
                    out.write(f"<!-- probe {name}: not created -->\n")
                    continue
                ran, rep = guarded(f"proberep|{name}", lambda: msg(act, "serializedRepresentation"))
                out.write(f"<!-- probe {name} -> {S(className(objGetClass(act)))}\n     input: {params} -->\n")
                out.write((plist_text(rep) if ran else "skipped") + "\n")
            except Exception:
                log(f"probe error {name}: {traceback.format_exc(limit=2)}")


def meta():
    info = {}
    b = _sendp(getClass(b"NSBundle"), sel("bundleWithPath:"),
               nsstr("/System/Library/PrivateFrameworks/WorkflowKit.framework"))
    for k in ("CFBundleShortVersionString", "CFBundleVersion"):
        v = _sendp(b, sel("objectForInfoDictionaryKey:"), nsstr(k)) if b else None
        info["WorkflowKit." + k] = to_py(v)
    minimal = {"WFWorkflowActions": [], "WFWorkflowClientVersion": "900", "WFWorkflowMinimumClientVersion": 900,
               "WFWorkflowMinimumClientVersionString": "900",
               "WFWorkflowIcon": {"WFWorkflowIconStartColor": -12365313, "WFWorkflowIconGlyphNumber": 61704},
               "WFWorkflowImportQuestions": [], "WFWorkflowTypes": []}
    ran, f = guarded("meta|client", lambda: migrated_file(ns(minimal), "meta", True))
    if ran and f:
        info["current_client_version"] = (to_py(msg(f, "rootObject")) or {}).get("WFWorkflowClientVersion")
    with open(f"{out_dir}/meta.json", "w") as fh:
        json.dump(info, fh, indent=1, sort_keys=True)


# ------------------------------------------------------------------ lint
def lint(directory):
    summary = []
    for fn in sorted(os.listdir(directory)):
        if not fn.endswith((".plist", ".wflow", ".shortcut")):
            continue
        path = os.path.join(directory, fn)
        name = os.path.splitext(fn)[0]
        rep = {"file": fn, "errors": [], "warnings": [], "notes": []}
        try:
            load = lambda: _sendp(NSDictionary, sel("dictionaryWithContentsOfFile:"), nsstr(path))
            orig = to_py(load())
            if not orig:
                rep["errors"].append("not a readable property list")
                summary.append(rep)
                continue
            rep["client_version"] = orig.get("WFWorkflowClientVersion")
            # 1. Apple's migrations (these rewrite legacy-dialect shortcuts, e.g. client version 900, into the modern form)
            ran, f = guarded(f"mig|{name}", lambda: migrated_file(load(), name, True))
            migrated = to_py(msg(f, "rootObject")) if ran and f else None
            if migrated:
                with open(f"{out_dir}/{name}.migrated.xml", "w", encoding="utf-8") as fh:
                    fh.write(plist_text(msg(f, "rootObject")))
                rep["notes"].append(
                    f"migration: client version {orig.get('WFWorkflowClientVersion')} -> {migrated.get('WFWorkflowClientVersion')}; "
                    f"{len(orig.get('WFWorkflowActions', []))} -> {len(migrated.get('WFWorkflowActions', []))} actions")
            else:
                rep["errors"].append("Apple's importer could not load this file")
                summary.append(rep)
                continue
            # 2. round-trip every (migrated) action through the live registry; dropped keys mean Apple ignores them
            for i, a in enumerate(migrated.get("WFWorkflowActions", [])):
                ident, params = a.get("WFWorkflowActionIdentifier"), a.get("WFWorkflowActionParameters", {})
                try:
                    ran, obj = guarded(f"rt|{name}|{i}", lambda: _sendpp(
                        reg, sel("createActionWithIdentifier:serializedParameters:"), nsstr(ident), ns(params)))
                    if not ran:
                        rep["errors"].append(f"action #{i} {ident}: crashed Apple's loader on an earlier attempt")
                    elif not obj:
                        rep["errors"].append(f"action #{i} {ident}: the registry does not know this identifier")
                    else:
                        ran, ser = guarded(f"rtrep|{name}|{i}", lambda: msg(obj, "serializedRepresentation"))
                        out = (to_py(ser) or {}).get("WFWorkflowActionParameters", {}) if ran else {}
                        for finding in diff_params(params, out):
                            if finding.startswith("dropped"):
                                rep["warnings"].append(f"action #{i} {ident}: Apple's loader {finding}")
                except TypeError as e:
                    rep["warnings"].append(f"action #{i} {ident}: {e}")
            # 3. Apple's import validator
            ran, f2 = guarded(f"val|{name}", lambda: migrated_file(load(), name, True))
            if ran and f2:
                e1 = c_void_p()
                ran, rec = guarded(f"rec|{name}", lambda: _rec_err(f2, sel("recordRepresentationWithError:"), ctypes.byref(e1)))
                if ran and rec:
                    e2 = c_void_p()
                    ran, wf = guarded(f"wf|{name}", lambda: _init4(
                        msg(getClass(b"WFWorkflow"), "alloc"), sel("initWithRecord:reference:storageProvider:error:"),
                        rec, None, None, ctypes.byref(e2)))
                    if ran and wf:
                        e3 = c_void_p()
                        ran, ok = guarded(f"valid|{name}", lambda: _bool_err(
                            getClass(b"WFShortcutValidator"), sel("validateForImportWorkflow:error:"), wf, ctypes.byref(e3)))
                        if not ran:
                            rep["errors"].append("import validator crashed on an earlier attempt")
                        elif not ok:
                            rep["errors"].append("import validator rejected the shortcut: " + (desc(e3.value) if e3.value else "no detail"))
                        else:
                            rep["notes"].append("import validator: OK")
                    else:
                        rep["warnings"].append("could not build a WFWorkflow to validate: " + (desc(e2.value) if e2.value else "unknown"))
        except Exception:
            rep["errors"].append("lint exception: " + traceback.format_exc(limit=3))
        summary.append(rep)
        log(f"linted {fn}: {len(rep['errors'])} errors, {len(rep['warnings'])} warnings")
    with open(f"{out_dir}/lint-summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, default=str)


if MODE == "extract":
    class_dump()
    definitions()
    control_flow_probes()
    meta()
elif MODE == "lint":
    lint(target_dir)
log("probe finished")
sys.stdout.flush()
os._exit(0)
