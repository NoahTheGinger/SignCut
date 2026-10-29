# SignCut — generate an unsigned Apple Shortcut

## Your role

Create an Apple Shortcut from the user's request. Use the attached **SignCut runtime reference** to discover real action identifiers and parameters. Your deliverable, if you can create files, is **one actual downloadable `NAME.unsigned.shortcut` binary file**; include the corresponding **`NAME.plist` XML source** when useful for editing. **Do not sign the file.** It will be signed separately, such as with Shortcuty.

## References (inspect these before designing the shortcut)

1. `reference/actions-condensed.json` — primary machine-readable mapping from identifier to `type`, `name`, `description`, `parameters[]` (including exact keys, available types and enum cases), `outputs`, and deprecation information.
2. `reference/action-catalog.md` — complete readable rendering of the same 1,791 entries; use for discovery, not instead of exact identifier verification.
3. `reference/toolkit-raw.db` — optional original ToolKit SQLite data for metadata not preserved by the condensed JSON.
4. `reference/README.md` and `reference/os-version.txt` — scope, provenance, and limitations.

The snapshot was extracted from Shortcuts ToolKit on macOS 26.4. It may include actions unavailable on the target iPhone, and it is **not** a complete specification of the `.shortcut` file format. Do not present the reference as proof that a particular action can be serialized or will run correctly.

## Method

1. **Understand the request:** list desired actions, their order, inputs, outputs and any expected system prompts or limitations. If essential behavior is impossible, report the limitation rather than silently substituting.
2. **Discover actions:** search the reference by `name` and `description`. Confirm every selected action identifier appears **verbatim as a JSON key**. Prefer known-working classic `type: "action"` entries when equivalent; evaluate `siriIntent` and `appIntent` entries when necessary, but treat their plist encoding as potentially different. Do **not** assume every top-level reference key can simply be dropped into `WFWorkflowActionIdentifier` unchanged for App Intents.
3. **Choose parameters:** use exact documented `parameters[].key` names for action settings, and documented `enumValues[].value` where applicable. Metadata may omit defaults or serialization rules. Control metadata (`UUID`, `GroupingIdentifier`, `WFControlFlowMode`) and attachment structures are separate from action-settings metadata; base their placement on known-working Shortcut exports, not speculation.
4. **Construct a complete XML plist** containing at least:
   - `WFWorkflowActions` — array of action dictionaries, each with `WFWorkflowActionIdentifier` and usually `WFWorkflowActionParameters` dictionary;
   - `WFWorkflowClientVersion` — string;
   - `WFWorkflowMinimumClientVersion` — integer;
   - `WFWorkflowMinimumClientVersionString` — string;
   - `WFWorkflowIcon` — dictionary with integer `WFWorkflowIconStartColor` and `WFWorkflowIconGlyphNumber`;
   - `WFWorkflowImportQuestions` — array;
   - `WFWorkflowTypes` — array (if required by your target format).

   For version and icon metadata, prefer values from a known-working export from the target iOS release. If you lack one, clearly label copied example values as unverified. Use proper XML escaping or Python's `plistlib` to generate XML rather than assembling raw XML unsafely.
5. **Variables and control flow:** prefer straightforward chaining when sufficient. Where action output references, rich text attachments, typed values, conditional blocks, repeats or menus are required, verify their binary/XML plist structure from a known working export. Do not guess UUID/attachment/control-flow field layouts solely from ToolKit action metadata.
6. **Check:** parse the XML with `plistlib`; check required envelope fields, action parameter dictionaries, and action identifiers against `reference/actions-condensed.json`. Optionally run the included converter, which performs those basic checks. Clearly identify any serialization assumptions and device-dependent actions. Passing basic checks is **not** proof the Shortcut imports or runs correctly.
7. **Convert:** use the built-in Python `plistlib` via the included converter (no Mac required):

   ```bash
   python3 scripts/plist_to_shortcut.py NAME.plist
   ```

   This creates `NAME.unsigned.shortcut` in **binary plist** format. If using Python directly, the essential operation is:

   ```python
   import plistlib
   from pathlib import Path
   source = Path("NAME.plist")
   shortcut = plistlib.loads(source.read_bytes())
   Path("NAME.unsigned.shortcut").write_bytes(
       plistlib.dumps(shortcut, fmt=plistlib.FMT_BINARY, sort_keys=False)
   )
   ```

8. **Deliver:** provide clickable/downloadable generated file attachments if tools support them, with the unsigned `.shortcut` as the main deliverable, and optionally the source XML plist. If file creation is unavailable, output the *complete* XML plist in one `xml` fenced code block and explicitly say you could not generate a downloadable binary. Never pretend a textual code block is an attached `.shortcut`.
9. **Signing and privacy:** instruct the user to upload the `.unsigned.shortcut` to [Shortcuty Signer](https://sign.shortcuty.app/) and import the signed result. It is a remote signing service that receives the file; do **not** embed credentials or sensitive personal data in uploads. The signing step does not validate logic or guarantee import success.

## Response format

- A short summary of the Shortcut's exact behavior (and any confirmations required by iOS).
- A link to the **actual unsigned binary file**, when generated; optionally a link to the XML plist source.
- Any action compatibility / serialization uncertainties, especially for App Intents or Siri Intents.
- A one-sentence note explaining how to sign it.

## The Shortcut I want

[DESCRIBE YOUR SHORTCUT HERE]
