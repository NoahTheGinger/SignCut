# 🔨 SignCut

**Write iOS Shortcuts as code. Sign them in the cloud. Install them with a tap. No Mac required.**

This repo is a pipeline for authoring iOS Shortcuts with an LLM instead of the
drag-and-drop editor, solving the two problems that make that hard:

1. **LLMs hallucinate action identifiers.** Shortcuts are plist files full of
   undocumented identifiers like `is.workflow.actions.gettext`. Community docs
   are years stale. This repo extracts the **ground truth** — Apple's own
   `WFActions.plist` action database — from a live macOS runner.
2. **Apple requires shortcuts to be signed** (since iOS 13) before the app
   will import them. Signing requires macOS. We borrow one from GitHub
   Actions for a few seconds per run.

## How it works

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ extract-actions │ →   │  LLM writes      │ →   │ sign-shortcuts  │
│ (ground-truth   │     │  XML plist using │     │ (lint + sign +  │
│  action DB)     │     │  that reference  │     │  publish)       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

## The two workflows

### 1. `extract-actions.yml` — the documentation miner
Manually triggered. Runs on a macOS runner, finds Apple's `WFActions.plist`
inside `/System/Library/PrivateFrameworks` (WorkflowKit), and produces:

- `WFActions.json` — the full action database, every identifier + parameter schema
- `actions-condensed.json` — slimmed version sized for LLM context injection
- `os-version.txt` — which macOS this truth came from

**Re-run whenever GitHub bumps its macOS runner image** to stay current.

### 2. `sign-shortcuts.yml` — the signer
Fires automatically when a `.plist` lands in `shortcuts/`. It:

1. Lints every plist (`plutil -lint`)
2. Signs each one (`shortcuts sign --mode anyone`)
3. Uploads artifacts **and** publishes to the rolling `latest-signed` release

## Usage loop (works entirely from a phone)

1. Grab (a relevant slice of) `actions-condensed.json`
2. Prompt an LLM: *"Using these action schemas, write an XML plist shortcut
   that does X"*
3. Commit the plist to `shortcuts/` — push triggers signing
4. On iPhone: open this repo's **Releases** page in Safari → tap the
   `.shortcut` file → Shortcuts import screen opens → done

## ⚠️ Things Future Me should remember

- **`plutil -lint` only checks plist syntax**, not whether action identifiers
  exist. A hallucinated action will sign fine and silently break on import.
  Always generate against the extracted action database — that's the entire
  point of workflow 1.
- **Newer actions may be missing from `WFActions.plist`.** Apple has been
  migrating system actions (and all third-party actions) to the App Intents
  framework. For those: build a one-action shortcut by hand, export it, and
  read the identifier out of the plist (round-trip trick).
- **`shortcuts sign` on headless CI is the fragile link.** If signing breaks
  after a runner image update, try pinning `runs-on` to a specific macOS
  version instead of `macos-latest`.
- **Plan B exists:** [Cherri](https://cherrilang.org) is an open-source
  language that compiles to signed shortcuts with real compile-time action
  validation. If plist generation gets too error-prone, switch to having the
  LLM write Cherri instead.

## Why not just use the Shortcuts editor?

Because describing a 40-action shortcut in a sentence and getting a signed,
installable file back is cooler than dragging 40 blocks around a screen.
