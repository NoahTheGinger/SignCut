// Runtime probe of Apple's Shortcuts frameworks (WorkflowKit & friends) on macOS.
//
//   swiftc -O scripts/probe/probe.swift -o probe
//   ./probe DLOPEN_LIST OUT_DIR
//
// Stage 1: dlopen every framework in the list and dump every class from those images
//          (class-dump style: superclass, protocols, ivars, properties, methods).
// Stage 2: instantiate likely registry singletons and call zero-argument getters whose
//          names suggest "all actions / definitions", dumping whatever they return.
//
// Stage 2 can hit ObjC exceptions or crashes. Every call is logged to progress.log before it
// runs, and the driver script re-runs the probe, skipping any call that never finished.
import Foundation
import ObjectiveC

let argv = CommandLine.arguments
guard argv.count >= 3 else { print("usage: probe DLOPEN_LIST OUT_DIR"); exit(2) }
let listPath = argv[1]
let outDir = argv[2]
let fm = FileManager.default
try? fm.createDirectory(atPath: outDir, withIntermediateDirectories: true)

func append(_ path: String, _ s: String) {
    if !fm.fileExists(atPath: path) { fm.createFile(atPath: path, contents: nil) }
    if let h = FileHandle(forWritingAtPath: path) {
        h.seekToEndOfFile()
        h.write(s.data(using: .utf8)!)
        h.synchronizeFile()
        h.closeFile()
    }
}
let logPath = outDir + "/probe.log"
let progressPath = outDir + "/progress.log"
func note(_ s: String) {
    append(logPath, s + "\n")
    FileHandle.standardError.write((s + "\n").data(using: .utf8)!)
}

// ---------------------------------------------------------------- stage 1
let imageFilter = ["Workflow", "ToolKit", "ActionKit", "Shortcut", "LinkMetadata", "LinkServices", "AppIntents"]
let paths = ((try? String(contentsOfFile: listPath, encoding: .utf8)) ?? "")
    .split(separator: "\n").map(String.init)
for p in paths {
    if dlopen(p, RTLD_NOW) == nil {
        note("dlopen FAIL \(p): \(String(cString: dlerror()))")
    } else {
        note("dlopen ok   \(p)")
    }
}

func cstr(_ p: UnsafePointer<CChar>?) -> String { p.map { String(cString: $0) } ?? "?" }

func methodLines(_ cls: AnyClass, prefix: String) -> [String] {
    var n: UInt32 = 0
    guard let ms = class_copyMethodList(cls, &n) else { return [] }
    defer { free(ms) }
    return (0..<Int(n)).map { i in
        let m = ms[i]
        return "  \(prefix) \(sel_getName(method_getName(m))) \(cstr(method_getTypeEncoding(m)))"
    }
}

func dumpClass(_ cls: AnyClass) -> String {
    var out = "@interface \(NSStringFromClass(cls))"
    if let sup = class_getSuperclass(cls) { out += " : \(NSStringFromClass(sup))" }
    var pc: UInt32 = 0
    if let pl = class_copyProtocolList(cls, &pc) {
        out += " <" + (0..<Int(pc)).map { cstr(protocol_getName(pl[$0])) }.joined(separator: ", ") + ">"
    }
    out += "\n"
    var ic: UInt32 = 0
    if let il = class_copyIvarList(cls, &ic) {
        for i in 0..<Int(ic) { out += "  ivar \(cstr(ivar_getName(il[i]))) \(cstr(ivar_getTypeEncoding(il[i])))\n" }
        free(il)
    }
    var pcnt: UInt32 = 0
    if let pl = class_copyPropertyList(cls, &pcnt) {
        for i in 0..<Int(pcnt) {
            out += "  prop \(cstr(property_getName(pl[i]))) \(cstr(property_getAttributes(pl[i])))\n"
        }
        free(pl)
    }
    if let meta = object_getClass(cls) { out += methodLines(meta, prefix: "+").joined(separator: "\n") + "\n" }
    out += methodLines(cls, prefix: "-").joined(separator: "\n") + "\n@end\n\n"
    return out
}

var classCount: UInt32 = 0
var matched = 0
if let all = objc_copyClassList(&classCount) {
    let path = outDir + "/classes.txt"
    try? fm.removeItem(atPath: path)
    var byImage: [String: [AnyClass]] = [:]
    for i in 0..<Int(classCount) {
        let c: AnyClass = all[i]
        guard let img = class_getImageName(c) else { continue }
        let image = String(cString: img)
        if imageFilter.contains(where: { image.contains($0) }) { byImage[image, default: []].append(c) }
    }
    for image in byImage.keys.sorted() {
        append(path, "// ===== IMAGE \(image)  (\(byImage[image]!.count) classes)\n")
        for c in byImage[image]!.sorted(by: { NSStringFromClass($0) < NSStringFromClass($1) }) {
            append(path, dumpClass(c)); matched += 1
        }
    }
    free(UnsafeMutableRawPointer(all))
}
note("stage 1: \(matched) classes dumped from \(classCount) total")

// ---------------------------------------------------------------- stage 2
var done = Set<String>(), began = Set<String>()
if let prog = try? String(contentsOfFile: progressPath, encoding: .utf8) {
    for line in prog.split(separator: "\n") {
        if line.hasPrefix("BEGIN ") { began.insert(String(line.dropFirst(6))) }
        if line.hasPrefix("END ") { done.insert(String(line.dropFirst(4))) }
    }
}
let skip = began.subtracting(done)
if !skip.isEmpty { note("skipping calls that crashed previously: \(skip.sorted())") }

let getterPattern = try! NSRegularExpression(
    pattern: "(all|definition|action|identifier|parameter|categor|registry|descriptor|library|catalog)",
    options: [.caseInsensitive])
let denyPattern = try! NSRegularExpression(
    pattern: "(delete|remove|reset|clear|save|write|sync|upload|purge|terminate|exit|kill|dealloc|release|retain|autorelease|init|new$|copy|mutableCopy)",
    options: [.caseInsensitive])

func returnsObject(_ m: Method) -> Bool {
    let t = method_copyReturnType(m); defer { free(t) }
    return String(cString: t).hasPrefix("@")
}

func zeroArgObjectGetters(_ cls: AnyClass, meta: Bool) -> [String] {
    var names: [String] = []
    var c: AnyClass? = meta ? object_getClass(cls) : cls
    while let k = c, NSStringFromClass(k) != "NSObject", NSStringFromClass(k) != "NSProxy" {
        var n: UInt32 = 0
        if let ms = class_copyMethodList(k, &n) {
            for i in 0..<Int(n) {
                let name = String(cString: sel_getName(method_getName(ms[i])))
                let r = NSRange(name.startIndex..., in: name)
                if !name.contains(":") && returnsObject(ms[i])
                    && getterPattern.firstMatch(in: name, range: r) != nil
                    && denyPattern.firstMatch(in: name, range: r) == nil { names.append(name) }
            }
            free(ms)
        }
        c = class_getSuperclass(k)
    }
    return Array(Set(names)).sorted()
}

func describeValue(_ v: AnyObject?) -> String {
    guard let v = v else { return "nil" }
    return String(describing: v)
}

func tryCall(_ target: AnyObject, label: String, selName: String, outFile: String) -> AnyObject? {
    let key = "\(label)|\(selName)"
    if skip.contains(key) { return nil }
    append(progressPath, "BEGIN \(key)\n")
    let sel = Selector(selName)
    guard (target as AnyObject).responds(to: sel) else { append(progressPath, "END \(key)\n"); return nil }
    let result = (target as AnyObject).perform(sel)?.takeUnretainedValue()
    append(progressPath, "END \(key)\n")
    let text = describeValue(result)
    append(outFile, "// ===== \(label) \(selName)  -> \(result.map { String(describing: type(of: $0)) } ?? "nil")  (\(text.count) chars)\n")
    append(outFile, String(text.prefix(40_000_000)) + "\n\n")
    return result
}

/// If the call returned a collection of objects that expose `definition`, dump identifier -> definition.
func dumpDefinitions(_ result: AnyObject?, label: String, outFile: String) {
    var items: [AnyObject] = []
    if let a = result as? NSArray { items = a.compactMap { $0 as AnyObject } }
    else if let d = result as? NSDictionary { items = d.allValues.compactMap { $0 as AnyObject } }
    guard !items.isEmpty else { return }
    for sel in ["definition", "actionDefinition", "metadata", "serializedParameters"] {
        guard items[0].responds(to: Selector(sel)) else { continue }
        var text = "// ===== \(label) per-item `\(sel)` (\(items.count) items)\n"
        for item in items {
            let key = "\(label)|item.\(sel)"
            if skip.contains(key) { text += "// skipped (crashed earlier)\n"; break }
            append(progressPath, "BEGIN \(key)\n")
            let ident = item.responds(to: Selector("identifier")) ? describeValue(item.perform(Selector("identifier"))?.takeUnretainedValue()) : "?"
            let val = item.perform(Selector(sel))?.takeUnretainedValue()
            append(progressPath, "END \(key)\n")
            text += "--- \(ident)\n\(describeValue(val))\n"
        }
        append(outFile, text + "\n")
    }
}

// Candidate singletons. Names come from Apple's long-standing WorkflowKit class naming; unknown ones are logged and ignored.
let candidates: [(cls: String, sels: [String])] = [
    ("WFActionRegistry", ["sharedRegistry", "sharedInstance", "defaultRegistry", "shared"]),
    ("WFActionManager", ["sharedManager", "sharedInstance", "shared"]),
    ("WFWorkflowActionRegistry", ["sharedRegistry", "sharedInstance", "shared"]),
    ("WFActionDefinitionStore", ["sharedStore", "sharedInstance", "shared"]),
    ("WFParameterDefinitionRegistry", ["sharedRegistry", "sharedInstance", "shared"]),
    ("WFDatabase", ["defaultDatabase", "sharedDatabase", "shared"]),
]
let regOut = outDir + "/registry-dump.txt"
for (clsName, sels) in candidates {
    guard let cls = NSClassFromString(clsName) else { note("stage 2: class \(clsName) not present"); continue }
    note("stage 2: class \(clsName) present")
    // class-level getters first
    for g in zeroArgObjectGetters(cls, meta: true) {
        let r = tryCall(cls, label: "+\(clsName)", selName: g, outFile: regOut)
        dumpDefinitions(r, label: "+\(clsName).\(g)", outFile: regOut)
    }
    for s in sels {
        guard (cls as AnyObject).responds(to: Selector(s)) else { continue }
        guard let inst = tryCall(cls, label: "+\(clsName)", selName: s, outFile: regOut) else { continue }
        note("stage 2: got instance via +\(clsName) \(s): \(type(of: inst))")
        for g in zeroArgObjectGetters(type(of: inst), meta: false) {
            let r = tryCall(inst, label: "\(clsName)", selName: g, outFile: regOut)
            dumpDefinitions(r, label: "\(clsName).\(g)", outFile: regOut)
        }
        break
    }
}
note("probe finished")
