# 🔨 SignCut

**Write iOS Shortcuts as code. Validate them against Apple's own action
database. Build unsigned `.shortcut` files in GitHub Actions. Sign them later
with a trusted signer.**

SignCut is a personal pipeline for vibe-coding Apple Shortcuts with an LLM
instead of building them manually in the Shortcuts editor.

The project solves the hardest part first: giving the LLM a current,
machine-readable reference of the Shortcuts action universe so it stops
inventing fake `WFWorkflowActionIdentifier` values.

## What this repo does

SignCut has three jobs:

1. **Extract Apple's action database**
   - Runs on a macOS GitHub Actions runner.
   - Opens the Shortcuts runtime enough to populate Apple's ToolKit database.
   - Reads the live ToolKit SQLite database from:
     `~/Library/Shortcuts/ToolKit/Tools-active`
   - Builds `actions-condensed.json`, a compact LLM-friendly reference.

2. **Guide LLM shortcut generation**
   - The prompt template in `prompts/generate-shortcut.md` explains how an LLM
     should use `reference/actions-condensed.json`.
   - Generated shortcuts are written as XML plist files in `shortcuts/`.

3. **Validate and build unsigned shortcut files**
   - The build workflow lints plist syntax.
   - Checks required Shortcut top-level keys.
   - Validates every `WFWorkflowActionIdentifier` against
     `reference/actions-condensed.json`.
   - Converts XML plist files into binary `.unsigned.shortcut` files.
   - Uploads those unsigned files as GitHub Actions artifacts.

## What this repo does *not* currently do

It does **not** fully sign shortcuts on GitHub-hosted macOS runners.

Apple's `shortcuts sign` command exists on macOS, but in practice the GitHub
hosted runner fails with:

```text
Error: In order to do this, you must be signed into iCloud.
```

So SignCut currently stops at producing valid unsigned `.shortcut` files.

Final signing must happen through one of these trusted paths:

* a personal Mac signed into iCloud,
* a self-hosted GitHub runner on a Mac signed into iCloud,
* a private shortcut-signing server backed by your own Mac,
* or a third-party signing service such as HubSign, only for non-sensitive
  shortcuts.

## Repo layout

```text
SignCut/
├── .github/workflows/
│   ├── Extract Shortcuts Action Database.yaml
│   └── Sign Shortcuts.yaml
├── prompts/
│   └── generate-shortcut.md
├── reference/
│   └── actions-condensed.json
├── scripts/
│   └── build_reference.py
└── shortcuts/
    └── example.plist
```

## Core files

### `reference/actions-condensed.json`

This is the precious artifact.

It is generated from Apple's current Shortcuts ToolKit database and contains
the available actions, identifiers, parameter keys, parameter labels, enum
values, output types, and deprecation info.

Top-level keys are action identifiers such as:

```text
is.workflow.actions.gettext
is.workflow.actions.showresult
is.workflow.actions.notification
```

These exact strings are what generated plist files must use in
`WFWorkflowActionIdentifier`.

### `prompts/generate-shortcut.md`

This is the reusable LLM prompt template.

Use it whenever asking an LLM to generate a new Shortcut plist. Give the LLM:

1. the prompt template,
2. the specific shortcut idea,
3. `reference/actions-condensed.json`.

The LLM should use the JSON as ground truth and refuse to invent identifiers
or parameter keys that are not present.

### `shortcuts/*.plist`

These are XML plist source files for generated shortcuts.

Each plist should be a complete Shortcut source file with:

* `WFWorkflowActions`
* `WFWorkflowClientVersion`
* `WFWorkflowMinimumClientVersion`
* `WFWorkflowMinimumClientVersionString`
* `WFWorkflowIcon`
* `WFWorkflowImportQuestions`
* optionally `WFWorkflowTypes`

The build workflow converts each `.plist` into a binary
`.unsigned.shortcut` artifact.

## Workflows

### `Extract Shortcuts Action Database`

Manual workflow.

It runs on macOS 26 and extracts the live Shortcuts ToolKit database. It then
uses `scripts/build_reference.py` to produce:

```text
out/actions-condensed.json
out/toolkit-raw.db
out/os-version.txt
```

After running this workflow, download the artifact and commit the generated
file to:

```text
reference/actions-condensed.json
```

Re-run this after macOS / iOS / Shortcuts updates to refresh the action
database.

### `Build Unsigned Shortcuts`

Triggered by changes to:

```text
shortcuts/*.plist
reference/actions-condensed.json
.github/workflows/Sign Shortcuts.yaml
```

It performs:

1. plist syntax linting,
2. required Shortcut top-level key checks,
3. action identifier validation against `reference/actions-condensed.json`,
4. XML plist → binary `.unsigned.shortcut` conversion,
5. artifact upload.

The output artifact is named:

```text
unsigned-shortcuts
```

Inside it, files look like:

```text
test1.unsigned.shortcut
```

## Using SignCut

### 1. Generate or refresh the action reference

Run:

```text
Actions → Extract Shortcuts Action Database → Run workflow
```

Download the artifact and copy:

```text
actions-condensed.json
```

into:

```text
reference/actions-condensed.json
```

Commit it.

### 2. Ask an LLM to write a shortcut

Open:

```text
prompts/generate-shortcut.md
```

Give the LLM:

* the prompt template,
* your shortcut idea,
* `reference/actions-condensed.json`.

Ask it to produce one complete XML plist.

### 3. Save the plist

Save the generated plist under:

```text
shortcuts/<shortcut-name>.plist
```

Commit and push.

### 4. Build the unsigned shortcut

GitHub Actions will run automatically.

Download the `unsigned-shortcuts` artifact from the workflow run.

### 5. Sign the shortcut

The artifact is not yet importable on iOS because modern Shortcuts requires
signed shortcut files.

You have several signing options.

#### Option A: Sign on your own Mac

On a Mac signed into iCloud:

```bash
shortcuts sign --mode anyone \
  --input "test1.unsigned.shortcut" \
  --output "test1.shortcut"
```

Then send `test1.shortcut` to your iPhone and open it.

#### Option B: Use HubSign

HubSign is RoutineHub's shortcut signing service. Cherri uses HubSign as a
fallback signing path when it cannot sign locally on macOS.

Use this only for shortcuts that contain no sensitive data.

Do not send shortcuts containing:

* API keys,
* webhook URLs,
* personal contacts,
* message contents,
* home addresses,
* calendar details,
* private notes,
* health data,
* authentication tokens,
* anything you would not want a third party to see.

Also remember: HubSign availability, account requirements, or subscription
requirements may change, so check RoutineHub before relying on it.

#### Option C: Self-host a signing backend

A private signing server or self-hosted GitHub runner can work if it is backed
by a Mac that is signed into iCloud.

This is the likely long-term automation path for personal/private shortcuts.

## Important lessons learned

### `WFActions.plist` is no longer the source of truth

Older Shortcuts reverse-engineering notes refer to:

```text
/System/Library/PrivateFrameworks/WorkflowKit.framework/Resources/WFActions.plist
```

On current macOS runners, that file is gone.

The useful action data now lives in the Shortcuts ToolKit SQLite database:

```text
~/Library/Shortcuts/ToolKit/Tools-active
```

### ToolKit contains both old and new action worlds

`actions-condensed.json` includes entries with:

```json
"type": "action"
```

and:

```json
"type": "appIntent"
```

For now, prefer `"type": "action"` entries when generating plist shortcuts.

Classic `"action"` entries map more directly to
`WFWorkflowActionIdentifier` plist serialization.

`"appIntent"` entries are documented in the ToolKit database, but their exact
plist serialization may require more round-trip research.

### `plutil -lint` is not enough

`plutil -lint` only checks whether the file is a syntactically valid plist.

A file can pass `plutil` and still fail as a Shortcut.

That is why the build workflow also checks required Shortcut keys and validates
action identifiers against `reference/actions-condensed.json`.

### Do not hardcode secrets in generated shortcuts

Even private repos can leak through accidents, old commits, collaborators,
forks, compromised tokens, or future public release plans.

Avoid committing shortcuts containing secrets or personal data.

If this project ever becomes public, create a fresh clean-room public repo
rather than trying to scrub private commit history.

## Future ideas

* Add stricter parameter-key validation.
* Add a workflow that diffs old vs. new `actions-condensed.json`.
* Add a local/private signer path.
* Add example shortcuts known to build and sign cleanly.
* Add decompilation / round-trip tests from hand-built shortcuts.
* Research plist serialization for `appIntent` actions.
* Add a searchable mini-doc site generated from `actions-condensed.json`.

## Why this exists

Because writing:

```text
"Make me a shortcut that does X"
```

and getting a valid Shortcut file back is cooler than dragging 40 blocks around
on a phone screen.
