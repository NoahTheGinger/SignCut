## Context

Attached is `actions-condensed.json`: a machine-generated reference of every
action available in the Apple Shortcuts runtime, extracted directly from the
ToolKit database (`Tools-active`) of macOS 26 — the same action registry the
Shortcuts app itself uses. It is ground truth and it is current. Structure:

- Each **top-level key** is an action identifier (e.g.
  `is.workflow.actions.gettext`). This exact string is what goes in a
  shortcut file's `WFWorkflowActionIdentifier` field.
- `type`: `"action"` = classic WorkflowKit action; `"appIntent"` = App
  Intents-based action.
- `name` / `description`: human-readable, for finding the right action.
- `parameters[]`: each parameter's exact `key` (the plist parameter key),
  plus `label`, `type`, and — where present — `enumValues` listing the only
  valid values for that parameter.
- `outputs` / `outputName`: what the action emits, for chaining.
- `deprecated` / `replacedBy`: avoid these; use the replacement.

## Your task

Write a complete Apple Shortcut as an **XML property list** (the `.plist`
source of a `.shortcut` file). It will be signed by Apple's `shortcuts sign`
tool on macOS and imported on iOS 26 — so it must be strictly valid.

## Hard rules

1. **Identifiers:** Every `WFWorkflowActionIdentifier` you write MUST appear
   verbatim as a top-level key in `actions-condensed.json`. Never invent,
   guess, or "remember" an identifier. If no suitable action exists in the
   JSON, stop and tell me instead of improvising.
2. **Prefer `"type": "action"` entries.** Only use `"appIntent"` entries if
   no classic action can do the job, and flag it prominently if you do.
3. **Parameter keys** must come from that action's `parameters[].key` list,
   exactly. For parameters with `enumValues`, use one of the listed `value`
   strings verbatim.
4. **Output format:** one complete XML plist — XML declaration, plist
   DOCTYPE, single root `<dict>` — in a single code block with no commentary
   inside it. Top-level keys: `WFWorkflowActions` (the action array),
   `WFWorkflowClientVersion` (string), `WFWorkflowMinimumClientVersion`
   (integer) and `WFWorkflowMinimumClientVersionString`, `WFWorkflowIcon`
   (dict with `WFWorkflowIconStartColor` and `WFWorkflowIconGlyphNumber`,
   both integers), and `WFWorkflowImportQuestions` (empty array).
5. **Variable passing:** prefer implicit input chaining (each action
   receives the previous action's output) where possible. Where an earlier
   result must be referenced explicitly, give the producing action a `UUID`
   parameter (uppercase UUIDv4) and reference it downstream as a magic
   variable (attachment dict with `Type: ActionOutput` and `OutputUUID`).
   Use each UUID exactly once as a producer.
6. **Control flow:** `if`/`repeat`/`menu` actions require paired begin/end
   entries sharing a `GroupingIdentifier` UUID, with `WFControlFlowMode`
   0 (begin), 1 (middle, e.g. else), 2 (end). Every begin must have its end.
7. If any part of my request is impossible or ambiguous given the available
   actions, say so before writing the plist — do not silently substitute.

## The shortcut I want

[YOUR IDEA HERE — describe behavior, inputs, outputs, and any UI you want,
e.g. "Ask me for a number of minutes, start a timer for that long, then
show a confirmation."]
