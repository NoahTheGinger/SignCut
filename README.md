# 🔨 SignCut — Apple Shortcuts reference kit

**Give an LLM a reference of Apple Shortcuts actions that was read out of a real macOS, let it write an XML plist, build an unsigned `.shortcut` locally, have Apple's own importer lint it, and sign it separately.**

## What is in the box

```text
SignCut/
├── reference/                         # generated from a real Mac by the Extract workflow
│   ├── actions-condensed.json         # every ToolKit tool: parameters, enums, outputs
│   ├── action-definitions.json        # WorkflowKit classic definitions: control flow + serialization classes
│   ├── control-flow-and-serialization.md   # verified plist layouts: menus, If, Repeat, variables
│   ├── gallery-examples/              # Apple's own shipped shortcuts
│   ├── action-catalog.md  …  see reference/README.md for the full list
├── prompts/generate-shortcut.md       # LLM instructions + request template
├── scripts/
│   ├── plist_to_shortcut.py           # XML plist -> unsigned binary .shortcut (standard library only)
│   ├── build_reference.py, build_catalog.py
│   └── extract/                       # runs on macOS: runtime introspection of WorkflowKit + the linter
├── shortcuts/                         # put your plists here to have Apple's importer lint them
└── .github/workflows/
    ├── Extract Shortcuts Reference.yaml   # refreshes reference/ from macOS (manual + monthly)
    └── Lint Shortcuts.yaml                # lints shortcuts/*.plist with Apple's own importer
```

## Use it with an LLM

1. Give your LLM `prompts/generate-shortcut.md` and the `reference/` folder (at minimum `actions-condensed.json`, `action-definitions.json`, `control-flow-and-serialization.md`). Replace `[DESCRIBE YOUR SHORTCUT HERE]`.
2. Ask for the XML plist **and** an actual `.unsigned.shortcut` file. If it can't produce a binary, convert the plist yourself:

   ```bash
   python3 scripts/plist_to_shortcut.py my-shortcut.plist        # Windows: py scripts/plist_to_shortcut.py …
   ```

   The converter checks the envelope and every action identifier (including the control-flow ones), and warns when the client version would skip Apple's migrations.
3. **Lint it with Apple's own code (recommended).** Commit the plist to `shortcuts/` and push. The `Lint Shortcuts` workflow runs it through the real importer on macOS: Apple's migrations, the live action registry (it reports every parameter Apple would silently drop) and the import validator. It fails the run on errors, and attaches the `.unsigned.shortcut` and the migrated plist as artifacts.
4. Upload the `.unsigned.shortcut` to [Shortcuty Signer](https://sign.shortcuty.app/), download the signed file and import it on your iPhone. Shortcuty is a third-party service that receives the complete file, so never put secrets in it. Signing can't run in CI: `shortcuts sign` needs an iCloud sign-in.

## Keeping the reference current

Run **Actions → Extract Shortcuts Reference → Run workflow** (it also runs monthly). One run refreshes everything in `reference/` from the runner's macOS and commits it. See `reference/README.md` for how, and `reference/os-version.txt` for the version in the repo now.

## Honest limits

- The data comes from **macOS**. Mac-only actions are marked (`DisabledOnPlatforms`), but nothing here proves an action exists or behaves on a given iPhone.
- The ToolKit database alone cannot describe If / Menu / Repeat (they are not tools); `action-definitions.json` and the guide cover them. The If **condition** layout is verified only for "Has Any Value"; other conditions need a lint run.
- App-Intents actions are serialized differently from classic actions and are not covered.
- Apple's native code can crash during extraction; the scripts retry and log what was skipped (`progress.log` in the run artifact).

## Requirements

Python 3.9+ standard library for the converter. The workflows need GitHub-hosted `macos-26` runners (free on public repositories). No certificate or Xcode setup.

## Privacy

Never hardcode tokens, messages, contacts or other secrets in a plist that will be uploaded to a signing service; have the shortcut ask for them at run time.
