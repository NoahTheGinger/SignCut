# The SignCut action references

The files in this folder come from an **Apple Shortcuts ToolKit runtime snapshot**, not from public Apple documentation. The source was collected on **macOS 26.4 (build 25E246)**. It reflects the tools registered in that environment, including third-party integrations; the exact actions available on an iPhone vary with OS version, device and installed apps.

| File | Purpose | How to use |
|---|---|---|
| `actions-condensed.json` | Primary machine-readable catalog of 1,791 action identifiers with available names, descriptions, parameter keys/types, enum cases, output data and deprecations. | **Provide this to an LLM**; search for candidate actions and inspect their properties. |
| `action-catalog.md` | Human-readable rendering of **all 1,791 JSON records**, with parameter descriptions and enum values when present. | Browse/search; useful when an LLM handles Markdown better than large JSON. |
| `toolkit-raw.db` | Original SQLite ToolKit database (`Tools-active`), before the condensation step. | Advanced research into metadata not exposed in the JSON. Requires SQLite tooling. |
| `os-version.txt` | Exact source OS version. | Check reference age and platform compatibility. |

## What this reference does and does not prove

- **Action discovery:** an action *identifier* appears in this extracted ToolKit registry, and the associated metadata describes the action and many of its parameters.
- **Not a complete serialization specification:** ToolKit metadata does not fully specify how to encode every action in a `.shortcut` plist (especially App Intents and Siri Intents, magic variables, nested data and control flow).
- **Not an installability guarantee:** actions from macOS, other devices, or third-party apps may not be usable on a particular iPhone. A plist passing syntax checks or signing successfully may still fail to import or run.
- **Parameter keys:** prefer documented keys and enum values for regular action settings; serialization-specific fields such as UUIDs and control-flow metadata may also be needed. Confirm their format from known-working exports.
- **No automatic updates:** these are the preserved files from the provided repository. To refresh them, you must replace the reference files with data from a newer extraction.

## Find an action quickly

```python
import json
from pathlib import Path

reference = json.loads(Path("reference/actions-condensed.json").read_text(encoding="utf-8"))
for identifier, entry in reference.items():
    description = (entry.get("name", "") + " " + entry.get("description", "")).lower()
    if "airplane" in description:
        print(entry.get("name"), identifier, entry.get("type"))
```

For a quick look at the raw database:

```bash
sqlite3 reference/toolkit-raw.db '.tables'
```

See [`../prompts/generate-shortcut.md`](../prompts/generate-shortcut.md) for the generation workflow.
