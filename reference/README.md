# The SignCut action references

Everything here is **generated from a real macOS by the `Extract Shortcuts Reference` workflow** (one run, one commit), except `control-flow-and-serialization.md`, which is hand-written from evidence the run produces.

| File | What it is | Use it for |
|---|---|---|
| `actions-condensed.json` | Every tool in Apple's **ToolKit** registry (classic actions, Siri intents, App Intents): names, descriptions, parameter keys and types, enum cases, outputs, deprecations. | Finding actions and exact parameter keys. |
| `action-definitions.json` | Apple's **WorkflowKit classic action definitions**. Adds the control-flow actions ToolKit does not list (`conditional`, `choosefrommenu`, `repeat.*`) and each parameter's serialization `Class`, defaults and items. | Serialization, control flow, platform availability. |
| `control-flow-and-serialization.md` | Evidence-tagged guide to the plist layouts (menus, If, Repeat, variables) and the client-version rule. | Writing any non-trivial shortcut. |
| `gallery-examples/*.xml` | Apple's own shipped example shortcuts. | Copying real layouts. |
| `control-flow-probes.xml` | What Apple's live registry writes back when fed control-flow parameters. | Evidence for the guide. |
| `action-catalog.md` | Browsable rendering of the two JSON files (`scripts/build_catalog.py`). | Reading and searching. |
| `workflowkit-class-dump.txt.gz` | Objective-C class dump of the WorkflowKit stack (classes, methods, ivars). | Digging when something is missing. |
| `toolkit-raw.db` | The original ToolKit SQLite database. | Fields the JSON omits. |
| `os-version.txt`, `workflowkit-meta.json` | macOS build, Xcode, WorkflowKit version and the **current Shortcuts client version**. | Provenance and freshness. |

## How it is produced

`Extract Shortcuts Reference` runs on a `macos-26` GitHub runner (manually, and monthly on a schedule):

1. launches Shortcuts so that it builds its ToolKit database, then condenses it (`scripts/build_reference.py`);
2. runs `scripts/extract/runtime.py` under Apple's platform-binary `/usr/bin/python3` (ActionKit refuses to load in any other host) to read WorkflowKit's own action-definition registry and class metadata at runtime. The framework binaries live inside the dyld shared cache, so reading them at runtime is the only practical way;
3. copies Apple's Gallery shortcuts, renders the catalog, lints `shortcuts/`, and commits the changes.

Native crashes in Apple's code cannot be caught from Python, so `run_runtime.sh` retries and the script skips the call that crashed (logged in the artifact's `progress.log`).

## What this reference does and does not prove

- **Action discovery and parameter keys** are authoritative for the macOS build in `os-version.txt`.
- **Serialization** of control flow, variables and the legacy-dialect migration is verified on that build and tagged G/R/M/V in `control-flow-and-serialization.md`. Other parameter value shapes are described by `Parameters[].Class` but not individually verified.
- **It is a macOS snapshot.** iPhone availability can differ. The `Lint Shortcuts` workflow checks a concrete shortcut against Apple's importer, but it cannot prove iOS runtime behavior.
