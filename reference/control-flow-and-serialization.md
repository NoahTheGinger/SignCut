# Control flow and serialization — verified against Apple's own code

`actions-condensed.json` (from the ToolKit database) lists **tools**. Menus, If and Repeat are not tools; they are
language constructs implemented in WorkflowKit, so they are described by `action-definitions.json` (WorkflowKit's
classic action definitions) and by the facts on this page. Everything here was checked on a real macOS runner
(see `os-version.txt`, `workflowkit-meta.json`) by one of:

- **G** — Apple's own shipped example shortcuts, `gallery-examples/*.xml` (WorkflowKit `Gallery.bundle`);
- **R** — round-tripping the parameters through Apple's live action registry (`control-flow-probes.xml`);
- **M** — running Apple's import migrations on a sample (`Lint Shortcuts` workflow, `*.migrated.xml`);
- **V** — Apple's import validator (`WFShortcutValidator`).

Anything not tagged is not verified. `Lint Shortcuts` re-runs R, M and V on every shortcut in `shortcuts/`.

## 1. Choose the dialect first: `WFWorkflowClientVersion`

| Client version in the file | What Apple's importer does | Use it for |
|---|---|---|
| **`"900"` (legacy dialect)** | Runs its migrations (M): action outputs are chained implicitly, so *Get Variable* actions are folded into direct references, `UUID`/`WFInput` links are added, the legacy If condition is converted, and the file is re-stamped with the current client version (`workflowkit-meta.json`, `4711` on macOS 26.6.2). Validator passes (V). | **Generated shortcuts.** Write simple chained actions and let the device upgrade the file. |
| A modern version (`4018.0.4`, `9999` in Apple's gallery) | **No migrations.** Every reference must already be explicit. Legacy keys are ignored: a legacy If loads as an *empty* `WFConditions` block (R). | Only for files that were exported by the Shortcuts app. |

Measured on the clipboard example: at `"900"` the importer turned 71 actions into 57 (14 *Get Variable* actions
folded away) and validated it; the same file at `"4018.0.4"` was left untouched and its If was dropped by the loader.
`WFWorkflowMinimumClientVersion` stays `900`.

## 2. Envelope

```xml
<key>WFWorkflowActions</key>                      <array>…</array>
<key>WFWorkflowClientVersion</key>                <string>900</string>       <!-- see §1 -->
<key>WFWorkflowMinimumClientVersion</key>         <integer>900</integer>
<key>WFWorkflowMinimumClientVersionString</key>   <string>900</string>
<key>WFWorkflowIcon</key>
<dict>
  <key>WFWorkflowIconStartColor</key>             <integer>-12365313</integer>  <!-- SIGNED 32-bit (G: -2873601) -->
  <key>WFWorkflowIconGlyphNumber</key>            <integer>61704</integer>      <!-- G -->
</dict>
<key>WFWorkflowImportQuestions</key>              <array/>
<key>WFWorkflowTypes</key>                        <array/>
```

Apple's gallery files also carry `WFWorkflowInputContentItemClasses`, `WFWorkflowOutputContentItemClasses`,
`WFWorkflowHasShortcutInputVariables`, `WFWorkflowHasOutputFallback` and `WFQuickActionSurfaces`; none are required.
Colors are signed 32-bit integers (`4282601983` written unsigned is `-12365313`).

## 3. Action shape

```xml
<dict>
  <key>WFWorkflowActionIdentifier</key><string>is.workflow.actions.gettext</string>
  <key>WFWorkflowActionParameters</key>
  <dict> <key>UUID</key><string>…</string> <key>WFTextActionText</key><string>hi</string> </dict>
</dict>
```

- `UUID` lives **inside** `WFWorkflowActionParameters` and names the action's output (G).
- Parameter keys and enum values: `actions-condensed.json`. The way a value is encoded is the parameter's
  **serialization class** in `action-definitions.json` (`Parameters[].Class`, e.g. `WFTextInputParameter`,
  `WFEnumerationParameter`, `WFSwitchParameter`, `WFNumberFieldParameter`, `WFVariablePickerParameter`). Plain values
  (strings, booleans, numbers, enum strings) are stored as-is (R, G).

## 4. Variables and magic variables (G)

Whole-value reference (a parameter that is entirely one variable):

```xml
<key>WFInput</key>
<dict>
  <key>Value</key><dict>
    <key>Type</key><string>ActionOutput</string>
    <key>OutputUUID</key><string>UUID-OF-PRODUCING-ACTION</string>
    <key>OutputName</key><string>Response</string>
  </dict>
  <key>WFSerializationType</key><string>WFTextTokenAttachment</string>
</dict>
```

- Named variable: `Type` = `Variable`, `VariableName` = `Input` (no `OutputUUID`).
- The loop variable inside *Repeat with Each* is `{Type: Variable, VariableName: "Repeat Item"}` (G). *Ask Each Time* is `{Type: Ask}` (G). The names `Repeat Index`, `Menu Result` and `If Result` exist in WorkflowKit; the importer wrote `Menu Result` as an `ActionOutput` name (M).
- Text that contains variables (a string with one or more embedded variables):

```xml
<key>WFNotificationActionBody</key>
<dict>
  <key>Value</key><dict>
    <key>string</key><string>Total: ￼</string>             <!-- U+FFFC marks each variable -->
    <key>attachmentsByRange</key><dict>
      <key>{7, 1}</key><dict><key>Type</key><string>Variable</string><key>VariableName</key><string>Total</string></dict>
    </dict>
  </dict>
  <key>WFSerializationType</key><string>WFTextTokenString</string>
</dict>
```

  The key is `{index, 1}`, the UTF-16 index of the `U+FFFC` character.
- Implicit chaining (an action with no input parameter takes the previous action's output) is legacy-dialect only (§1).

## 5. Choose from Menu (G, R, M, V)

One begin, one `WFControlFlowMode 1` entry per item, one end; every entry shares `GroupingIdentifier`; actions that
belong to an item sit between its entry and the next.

```xml
<!-- begin -->  is.workflow.actions.choosefrommenu  { GroupingIdentifier: G, WFControlFlowMode: 0,
                   WFMenuPrompt: "Pick one", WFMenuItems: ["File", "URL"] }
<!-- item  -->  is.workflow.actions.choosefrommenu  { GroupingIdentifier: G, WFControlFlowMode: 1, WFMenuItemTitle: "File" }
   …actions for "File"…
<!-- item  -->  is.workflow.actions.choosefrommenu  { GroupingIdentifier: G, WFControlFlowMode: 1, WFMenuItemTitle: "URL" }
   …actions for "URL"…
<!-- end   -->  is.workflow.actions.choosefrommenu  { GroupingIdentifier: G, WFControlFlowMode: 2, UUID: … }
```

Apple's examples keep `WFMenuItems` identical to the `WFMenuItemTitle` entries, in order (G). The construct's output is called `Menu Result`.

## 6. Repeat (G, R)

```xml
is.workflow.actions.repeat.count { GroupingIdentifier: G, WFControlFlowMode: 0, WFRepeatCount: 2 }   … is.workflow.actions.repeat.count { …, WFControlFlowMode: 2, UUID }
is.workflow.actions.repeat.each  { GroupingIdentifier: G, WFControlFlowMode: 0, WFInput: <variable reference, §4> } … { …, WFControlFlowMode: 2, UUID }
```

Inside *Repeat with Each* the current item is the variable `Repeat Item` (G); `Repeat Index` is the counter.

## 7. If / Otherwise / End If (R, M, V — partly verified)

Legacy dialect (client version `"900"`):

```xml
is.workflow.actions.conditional { GroupingIdentifier: G, WFControlFlowMode: 0,
    WFCondition: "Has Any Value",
    WFInput: { Type: "Variable", Variable: { Value: { Type: "Variable", VariableName: "Result" },
                                             WFSerializationType: "WFTextTokenAttachment" } } }
   …then…
is.workflow.actions.conditional { GroupingIdentifier: G, WFControlFlowMode: 1 }          <!-- Otherwise (optional) -->
   …else…
is.workflow.actions.conditional { GroupingIdentifier: G, WFControlFlowMode: 2, UUID: … } <!-- End If -->
```

- Note that `WFInput` of an If is a **`{Type, Variable: {Value, WFSerializationType}}`** wrapper, unlike other actions (§4).
- **Verified:** `"Has Any Value"` is migrated to `WFCondition: 99` with `WFConditionalLegacyComparisonBehavior: true`, the importer
  copies the input onto the Otherwise/End entries, and the validator accepts it (M, V).
- **Not verified:** the other legacy condition strings (`Is`, `Contains`, `Equals`, …) and `WFConditionalActionString`/number operands. Add
  a sample to `shortcuts/` and read the `Lint Shortcuts` report before relying on them.
- Modern files store conditions as `WFConditions` (`WFSerializationType: WFContentPredicateTableTemplate`). The registry always writes
  this key back (R); its template contents were not reverse-engineered here.
- Output of the construct is `If Result`.

## 8. Limits of this reference

- Source is macOS WorkflowKit. `DisabledOnPlatforms` and `RemoteExecuteOnPlatforms` in `action-definitions.json` say which actions are
  Mac-only; an action present here may still be unavailable on an iPhone.
- App-Intents actions (`type: appIntent` in `actions-condensed.json`) are serialized differently from the classic actions on this page and are
  not covered; prefer classic actions.
- Signing cannot be done in CI (`shortcuts sign` needs an iCloud sign-in), so signing stays a separate step.
