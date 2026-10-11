#!/usr/bin/env python3
"""Opt-in original-image validation. Read only; print aggregates and IBM specimens.

Never writes images or recovered content. Not part of CI; original HDA files
must remain outside the repository. Hash before/after to check immutability.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from as400_dasd import DASDImage
from as400_dasd_tool import _tui_command_definition
from as400_5250 import Guided5250


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def validate(path, specimens):
    before = digest(path)
    image = DASDImage(path)
    scan = image.scan()
    segments = image.recover_segments(scan)
    inventory = image.recover_objects(scan, segments)
    state = {"image": image}
    model = Guided5250(inventory, command_definition_loader=lambda obj: _tui_command_definition(state, obj))
    counts = Counter()
    for obj in inventory.objects:
        if (obj.object_type, obj.object_subtype) != (0x19, 5):
            continue
        view = _tui_command_definition(state, obj)
        counts["recovered_commands"] += 1
        counts["library_assigned"] += bool(obj.library_name)
        counts["complete_keyword_sequences"] += bool(view.recovery.parameters)
    expected = ({
        "QIWS/CPYTOPCD": "FROMFILE TOFLR FROMMBR TODOC REPLACE TRNTBL TRNFMT RCDFMT TRNIGC",
        "QSYS/ADDPFM": "FILE MBR EXPDATE SHARE TEXT SRCTYPE",
        "QSYS/DSPCMD": "CMD OUTPUT",
        "QSYS/CRTCMD": "CMD PGM SRCFILE SRCMBR REXSRCFILE REXSRCMBR REXCMDENV REXEXITPGM VLDCKR MODE TYPE ALLOW ALWOBS ALWLMTUSR MAXPOS PMTFILE MSGF HLPPNLGRP HLPID HLPSCHIDX CURLIB PRDLIB PMTOVRPGM AUT REPLACE TEXT NATIVE",
    } if specimens == "marks" else {})
    checked = []
    for qualified, words in expected.items():
        rows = model.command_rows(qualified)
        if len(rows) != 1:
            raise ValueError(f"{qualified}: expected one context-assigned primary; found {len(rows)}")
        obj = rows[0]["object"]
        view = _tui_command_definition(state, obj)
        if words and [p.keyword for p in view.recovery.parameters] != words.split():
            raise ValueError(f"{qualified}: keyword sequence mismatch")
        if not view.recovery.parameters:
            raise ValueError(f"{qualified}: no complete sequence")
        model.run_command(f"DSPCMD CMD({qualified})")
        assert model.screen == "command_definition"
        for index, row in enumerate(model.rows()):
            if row["type"].startswith("#"):
                model.selected = index
                model.open_row(index)
                assert model.screen == "command_info"
                assert any(row["name"] in line for line in model.detail)
                model.back()
                assert model.selected == index
        model.back()
        checked.append({"command": qualified, "lba": obj.segment.start_lba,
                        "keywords": len(view.recovery.parameters)})
    if specimens == "petes":
        # Unassigned primary: validates stored keywords, NOT a library/semantic link.
        rows = model.command_rows("*ORPHAN/ADDPFM")
        obj = next((r["object"] for r in rows if r["object"].segment.start_lba == 587516), None)
        if obj is None:
            raise ValueError("Pete ADDPFM reference primary not recovered")
        view = _tui_command_definition(state, obj)
        if [p.keyword for p in view.recovery.parameters] != "FILE MBR EXPDATE SHARE TEXT".split():
            raise ValueError("Pete ADDPFM stored keyword sequence mismatch")
        model.run_command("WRKCMD CMD(*ORPHAN/ADDPFM)")
        index = next(i for i, row in enumerate(model.rows()) if row["object"] is obj)
        model.open_row(index)
        assert model.screen == "command_definition" and model.library == "<unassigned>"
        model.back()
        checked.append({"command": "<unassigned>/ADDPFM", "lba": 587516,
                        "keywords": 5, "scope": "stored fields, library context unknown"})
    model.run_command("WRKCMD CMD(*ORPHAN/*)")
    counts["unassigned_search_rows"] = len(model.rows())
    after = digest(path)
    if after != before:
        raise ValueError("Image digest changed during validation")
    return {"specimens": specimens, "bytes": image.size, "sha256": after,
            "immutable": True, "counts": dict(counts), "workflow_checks": checked}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--specimens", choices=("marks", "petes"), required=True)
    args = parser.parse_args()
    print(json.dumps(validate(args.image, args.specimens), indent=2))


if __name__ == "__main__":
    main()
