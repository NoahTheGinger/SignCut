#!/usr/bin/env python3
"""Build actions-condensed.json from a Shortcuts ToolKit database."""
import json, sqlite3, sys
from collections import defaultdict

db = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else "actions-condensed.json"
con = sqlite3.connect(f"file:{db}?immutable=1", uri=True)
con.row_factory = sqlite3.Row

def rows(q, args=()):
    return con.execute(q, args).fetchall()

# --- English localizations (prefer exact 'en', fall back to en_*) ---
def best_en(table, key_cols, val_cols):
    result = {}
    for r in rows(f"SELECT * FROM {table} WHERE locale LIKE 'en%'"):
        k = tuple(r[c] for c in key_cols)
        if k not in result or r["locale"] == "en":
            result[k] = {c: r[c] for c in val_cols}
    return result

tool_loc  = best_en("ToolLocalizations", ["toolId"],
                    ["name", "descriptionSummary", "outputResultName", "deprecationMessage"])
param_loc = best_en("ParameterLocalizations", ["toolId", "key"],
                    ["name", "description", "trueString", "falseString"])
type_name = best_en("TypeDisplayRepresentations", ["typeId"], ["name"])

# --- Enum cases per type ---
enums = defaultdict(list)
for r in rows("SELECT typeId, id, title FROM EnumerationCases WHERE locale LIKE 'en%'"):
    enums[r["typeId"]].append({"value": r["id"], "title": r["title"]})

# --- Parameter -> type(s) ---
ptype = defaultdict(list)
for r in rows("SELECT toolId, key, typeId FROM ToolParameterTypes"):
    ptype[(r["toolId"], r["key"])].append(r["typeId"])

# --- Parameters per tool ---
params = defaultdict(list)
for r in rows("SELECT toolId, key, sortOrder, flags FROM Parameters ORDER BY toolId, sortOrder"):
    k = (r["toolId"], r["key"])
    loc = param_loc.get(k, {})
    entry = {"key": r["key"]}
    if loc.get("name"): entry["label"] = loc["name"]
    if loc.get("description"): entry["description"] = loc["description"]
    if loc.get("trueString") or loc.get("falseString"):
        entry["type"] = "Boolean"
    tids = ptype.get(k, [])
    tnames = [type_name[(t,)]["name"] for t in tids if (t,) in type_name]
    if tnames and "type" not in entry:
        entry["type"] = tnames[0] if len(tnames) == 1 else tnames
    for t in tids:
        if t in enums:
            entry["enumValues"] = enums[t]
            break
    params[r["toolId"]].append(entry)

# --- Outputs per tool ---
outputs = defaultdict(list)
for r in rows("SELECT toolId, typeIdentifier FROM ToolOutputTypes"):
    outputs[r["toolId"]].append(r["typeIdentifier"])

# --- Assemble ---
result = {}
for t in rows("SELECT rowId, id, toolType, deprecationReplacementId FROM Tools"):
    loc = tool_loc.get((t["rowId"],), {})
    entry = {"type": t["toolType"]}
    if loc.get("name"): entry["name"] = loc["name"]
    if loc.get("descriptionSummary"): entry["description"] = loc["descriptionSummary"]
    if params.get(t["rowId"]): entry["parameters"] = params[t["rowId"]]
    if outputs.get(t["rowId"]): entry["outputs"] = outputs[t["rowId"]]
    if loc.get("outputResultName"): entry["outputName"] = loc["outputResultName"]
    if t["deprecationReplacementId"]:
        entry["deprecated"] = True
        entry["replacedBy"] = t["deprecationReplacementId"]
    result[t["id"]] = entry

with open(out, "w") as f:
    json.dump(result, f, indent=1, sort_keys=True)

legacy = sum(1 for v in result.values() if v["type"] == "action")
print(f"{len(result)} tools written ({legacy} classic actions, {len(result)-legacy} app intents)")
