#!/usr/bin/env python3
"""Read-only whole-image BNDDIR / SRVPGM saved-reference audit.

Uses production virtual extent recovery, not raw adjacent physical sectors.
Prints aggregate counts and source SHA256 only, no binding names, module
content, program payloads, private data or original record bytes.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from as400_dasd import DASDImage
from as400_5250 import Guided5250
from as400_binding_directories import BindingDirectoryExplorer
from tools.validate_command_exploration import digest


def _select(model, obj, command):
    model.run_command(command)
    if model.screen == "type_objects":
        index=next((i for i,row in enumerate(model.rows())
                    if row.get("object") is obj), None)
        if index is None:
            raise ValueError("Selected recovered primary missing from command object list")
        model.selected=index
        model.open_row(index)
    if model.screen != "capabilities":
        raise ValueError("Expected selected type-specific capability screen")


def validate(path):
    before=digest(path)
    image=DASDImage(path)
    scan=image.scan()
    segments=image.recover_segments(scan)
    inventory=image.recover_objects(scan,segments)
    svc=BindingDirectoryExplorer(image,inventory)
    model=Guided5250(inventory,binding_loader=svc.rows,
                     capability_loader=lambda obj,sample=None:svc.rows(obj))
    counts=Counter()
    first_directory=None
    first_target=None
    for obj in inventory.objects:
        if obj.type_code!="19/37":
            continue
        counts["recovered binding-directory primaries"]+=1
        try:
            entries=svc.entries(obj)
        except (OSError,ValueError):
            counts["unsupported or truncated BNDDIR primaries"]+=1
            continue
        counts["supported 48-byte entry arrays"]+=1
        counts["saved binding directory records"]+=len(entries)
        for entry in entries:
            counts[f"raw target type {entry.target_type}"]+=1
            matches=svc._matches(entry)
            counts["candidate independently recovered primaries"]+=len(matches)
            counts["entry candidates with no recovered primary"]+=(not bool(matches))
            counts["entry candidates with duplicate recovered primaries"]+=(len(matches)>1)
            counts["saved unresolved *LIBL records"]+=(entry.library_token=="*LIBL")
            if matches and first_target is None:
                first_target=matches[0]
        if entries and first_directory is None:
            first_directory=obj
    if first_directory is not None:
        _select(model,first_directory,"DSPBNDDIR BNDDIR(*ALL/*)")
        index=next((i for i,row in enumerate(model.rows())
                    if row.get("kind")=="binding_entry_action" and
                    row.get("request",{}).get("entry") is not None),None)
        if index is None:
            raise ValueError("BNDDIR entry detail link is missing")
        model.selected=index
        model.open_row(index)
        if model.rows()[0]["name"]!="Saved binding-directory entry":
            raise ValueError("Saved BNDDIR record did not open")
        model.back()
        if model.selected!=index:
            raise ValueError("Saved BNDDIR record Back selection lost")
        counts["directory-entry/Back walkthroughs"]+=1
    for obj in inventory.objects:
        if obj.type_code=="02/03":
            counts["recovered service-program primaries"]+=1
    if first_target is not None and first_target.type_code=="02/03":
        _select(model,first_target,"DSPSRVPGM SRVPGM(*ALL/*)")
        if model.rows()[0]["name"]!="Saved service-program binding references":
            raise ValueError("Reverse service program reference view did not open")
        action=next((i for i,row in enumerate(model.rows())
                     if row.get("kind")=="binding_entry_action"),None)
        if action is None:
            raise ValueError("Corroborated service program lacks reverse source entry")
        model.selected=action
        model.open_row(action)
        if model.rows()[0]["name"]!="Saved binding-directory entry":
            raise ValueError("Reverse BNDDIR entry navigation failed")
        model.back()
        if model.selected!=action:
            raise ValueError("Reverse SRVPGM-to-binding Back selection lost")
        counts["service-program reverse-entry/Back walkthroughs"]+=1
    after=digest(path)
    if before!=after:
        raise ValueError("Original archival HDA SHA256 changed")
    return {"image_bytes":Path(path).stat().st_size,
            "sha256":after,"unchanged":True,
            "counts":dict(sorted(counts.items()))}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image",type=Path)
    print(json.dumps(validate(parser.parse_args().image),indent=2))
