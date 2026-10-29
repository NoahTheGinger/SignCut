#!/usr/bin/env python3
"""Convert an XML Shortcut plist to an unsigned binary .shortcut file.

Standard library only. Checks the expected Shortcut envelope and, by default,
validates action identifiers against SignCut's bundled ToolKit reference.
Does not sign, guarantee importability, or validate complex parameter encoding.
"""
from __future__ import annotations

import argparse
import json
import plistlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REFERENCE = REPO_ROOT / "reference" / "actions-condensed.json"
REQUIRED_KEYS = (
    "WFWorkflowActions",
    "WFWorkflowClientVersion",
    "WFWorkflowMinimumClientVersion",
    "WFWorkflowMinimumClientVersionString",
    "WFWorkflowIcon",
    "WFWorkflowImportQuestions",
)


def validate(shortcut: object, reference: dict | None) -> tuple[int, set[str]]:
    """Perform basic structural and identifier checks (not full Shortcuts validation)."""
    if not isinstance(shortcut, dict):
        raise ValueError("Plist root must be a dictionary.")
    missing = [key for key in REQUIRED_KEYS if key not in shortcut]
    if missing:
        raise ValueError("Missing required top-level keys: " + ", ".join(missing))
    if not isinstance(shortcut["WFWorkflowClientVersion"], str):
        raise ValueError("WFWorkflowClientVersion must be a string.")
    if type(shortcut["WFWorkflowMinimumClientVersion"]) is not int:
        raise ValueError("WFWorkflowMinimumClientVersion must be an integer.")
    if not isinstance(shortcut["WFWorkflowMinimumClientVersionString"], str):
        raise ValueError("WFWorkflowMinimumClientVersionString must be a string.")
    if not isinstance(shortcut["WFWorkflowImportQuestions"], list):
        raise ValueError("WFWorkflowImportQuestions must be an array.")
    if "WFWorkflowTypes" in shortcut and not isinstance(shortcut["WFWorkflowTypes"], list):
        raise ValueError("WFWorkflowTypes must be an array when provided.")

    icon = shortcut["WFWorkflowIcon"]
    if not isinstance(icon, dict):
        raise ValueError("WFWorkflowIcon must be a dictionary.")
    for key in ("WFWorkflowIconStartColor", "WFWorkflowIconGlyphNumber"):
        if type(icon.get(key)) is not int:
            raise ValueError(f"WFWorkflowIcon.{key} must be an integer.")

    actions = shortcut["WFWorkflowActions"]
    if not isinstance(actions, list) or not actions:
        raise ValueError("WFWorkflowActions must be a nonempty array.")

    unusual_types: set[str] = set()
    for index, action in enumerate(actions, 1):
        if not isinstance(action, dict):
            raise ValueError(f"Action #{index} must be a dictionary.")
        identifier = action.get("WFWorkflowActionIdentifier")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError(f"Action #{index} needs a nonempty WFWorkflowActionIdentifier.")
        params = action.get("WFWorkflowActionParameters", {})
        if not isinstance(params, dict):
            raise ValueError(f"Action #{index} WFWorkflowActionParameters must be a dictionary.")
        if reference is not None:
            entry = reference.get(identifier)
            if entry is None:
                raise ValueError(f"Unknown action identifier in action #{index}: {identifier}")
            action_type = entry.get("type")
            if action_type in ("appIntent", "siriIntent"):
                unusual_types.add(f"{identifier} ({action_type})")
    return len(actions), unusual_types


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plist", type=Path, help="Input XML plist (or an existing binary plist).")
    parser.add_argument("-o", "--output", type=Path, help="Output path (default: <name>.unsigned.shortcut next to input).")
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE,
                        help="Reference JSON for action-ID checks (default: bundled SignCut reference).")
    parser.add_argument("--no-reference-check", action="store_true",
                        help="Skip action-ID validation against the reference JSON.")
    args = parser.parse_args()

    try:
        with args.plist.open("rb") as handle:
            shortcut = plistlib.load(handle)
        reference = None
        if not args.no_reference_check:
            with args.reference.open("r", encoding="utf-8") as handle:
                reference = json.load(handle)
            if not isinstance(reference, dict):
                raise ValueError("The reference JSON must contain a top-level object.")
        count, unusual_types = validate(shortcut, reference)
        destination = args.output or args.plist.with_name(args.plist.stem + ".unsigned.shortcut")
        if destination.resolve() == args.plist.resolve():
            raise ValueError("Output path must differ from input path.")
        data = plistlib.dumps(shortcut, fmt=plistlib.FMT_BINARY, sort_keys=False)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    except (OSError, ValueError, TypeError, plistlib.InvalidFileException, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Created: {destination} ({len(data):,} bytes; {count} actions)")
    if unusual_types:
        print("Warning: the following Siri/App Intents may need specialized plist serialization:", file=sys.stderr)
        for identifier in sorted(unusual_types):
            print("  - " + identifier, file=sys.stderr)
    print("Unsigned binary plist only — sign separately before importing on iOS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
