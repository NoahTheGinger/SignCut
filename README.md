# 🔨 SignCut — Apple Shortcuts reference kit

**Give an LLM a rich reference of Apple Shortcuts actions, have it create a complete XML plist, turn that plist into an unsigned `.shortcut` file locally, and sign the result separately.**

This stripped-down edition is intentionally **not a GitHub Actions pipeline, signing service, or Shortcut repository**. The original reference data is preserved; builds happen wherever your LLM or Python environment can create a file.

## Contents

```text
SignCut/
├── README.md
├── reference/
│   ├── README.md
│   ├── actions-condensed.json    # 1,791 machine-readable actions
│   ├── action-catalog.md        # all actions in readable Markdown
│   ├── toolkit-raw.db           # original Apple ToolKit SQLite data
│   └── os-version.txt           # macOS 26.4 / build 25E246
├── prompts/
│   └── generate-shortcut.md    # LLM instructions + request template
└── scripts/
    └── plist_to_shortcut.py    # standard-library plist converter
```

## Fastest way to use it with an LLM

1. Give your LLM **`prompts/generate-shortcut.md`** and **`reference/actions-condensed.json`** (or the whole repository if its environment supports reading files). You can also supply `reference/action-catalog.md` for browsing and `reference/toolkit-raw.db` if advanced investigation is needed.
2. Replace `[DESCRIBE YOUR SHORTCUT HERE]` in the prompt with the Shortcut behavior you want.
3. Ask the LLM to create an XML plist named, for example, `my-shortcut.plist` **and an actual downloadable `.unsigned.shortcut` file**, not merely a code block. It should validate the structure and action IDs against the reference; import-time behavior cannot be guaranteed from the registry alone.
4. If the LLM cannot produce a binary attachment, save the XML plist and convert it yourself:

   **Windows (PowerShell):**
   ```powershell
   py scripts/plist_to_shortcut.py my-shortcut.plist
   ```

   **macOS/Linux/iSH (if Python is installed):**
   ```bash
   python3 scripts/plist_to_shortcut.py my-shortcut.plist
   ```

   The default output is `my-shortcut.unsigned.shortcut`, next to the input. Override with `-o output.unsigned.shortcut`.
5. Upload **the `.unsigned.shortcut` file** to [Shortcuty Signer](https://sign.shortcuty.app/), download its **signed** `.shortcut` output, and import it into Apple Shortcuts on your iPhone. Shortcuty is a third-party remote signing service: it receives the complete file, so **don't upload secrets or private data**.

## Requirements

- **Python 3.9+**, using only built-in `plistlib`, `json`, and other standard-library modules. No macOS, Xcode, GitHub Actions or signing certificate is required to *create the unsigned file*.
- A compatible signing solution is still required before iOS import.
- For Windows, use `py` (or `python`, depending on your installation). On iSH, install Python first if needed (`apk add python3`).

## Converter options

```bash
python3 scripts/plist_to_shortcut.py --help
python3 scripts/plist_to_shortcut.py my-shortcut.plist -o ready.unsigned.shortcut
python3 scripts/plist_to_shortcut.py my-shortcut.plist --no-reference-check
```

The script validates plist syntax, the expected Shortcut envelope, and action identifiers against the included reference by default. It does **not** certify parameter serialization, iPhone compatibility, runtime behavior, or signature validity. `--no-reference-check` turns off only the identifier lookup (for example, if you deliberately work with newer actions than this snapshot).

## What the Apple action reference covers

The snapshot contains **1,791 tool records**: **382 classic actions**, **87 Siri intents**, and **1,322 App Intents**. IDs, names, descriptions, parameters, enum cases, outputs and deprecation data are provided wherever available. This is an extracted **macOS Shortcuts runtime registry**, rather than a complete, public authoring API or a guarantee that every action works on your iPhone.

For complex Shortcuts (conditionals, loops, magic variables, App Intents), working examples exported by the Shortcuts app can be more important than the action reference: the database does not describe all plist serialization details. Avoid guessing opaque parameter payloads and warn about unverified encodings.

## Privacy and maintenance

Never hardcode API tokens, private messages, contacts, secrets or other sensitive values in a file that will be uploaded to a signing service. Have the Shortcut ask for runtime inputs or load secrets locally after import where possible. Your generated plist and unsigned output can remain local until you choose where to sign them.

**No extract/build/sign workflows are retained.** This kit preserves the original reference snapshot, the instructions for LLM generation, and one local conversion script. To update the database for a future OS release, supply a newer extracted reference manually.
