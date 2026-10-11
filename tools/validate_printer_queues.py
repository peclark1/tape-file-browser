#!/usr/bin/env python3
"""Read-only whole-image PRTQ key and SPLCB token-candidate acceptance.

Run only against extracted original HDA. Prints aggregate counts only; never
saved SP tokens, object names, printer contents, job details or raw keys.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from as400_dasd import DASDImage
from as400_5250 import Guided5250
from as400_printer_queues import PrinterQueueExplorer
from as400_spool_controls import SpoolControlExplorer
from tools.validate_command_exploration import digest


def validate(path):
    before=digest(path)
    image=DASDImage(path)
    scan=image.scan();segments=image.recover_segments(scan)
    inventory=image.recover_objects(scan,segments)
    exp=PrinterQueueExplorer(image,inventory)
    spool=SpoolControlExplorer(image,inventory,printer_queue_explorer=exp)
    model=Guided5250(inventory,
                      printer_queue_loader=exp.rows,
                      capability_loader=lambda obj,sample=None:
                       spool.rows(obj) if obj.type_code=="19/C2"
                       else exp.rows(obj) if obj.type_code=="0E/C7"
                       else [])
    count=Counter()
    walked=False
    for obj in inventory.objects:
        if obj.type_code!="0E/C7":
            continue
        count["recovered PRTQ primaries"]+=1
        try:
            entries,warnings,page_size=exp.entries(obj)
        except (ValueError,OSError):
            count["withheld or unsupported roots"]+=1
            continue
        count["validated saved key roots"]+=1
        count[f"page size {page_size}"]+=1
        count["saved terminal keys"]+=len(entries)
        count["index warnings"]+=len(warnings)
        token_entries=[e for e in entries if e.token_candidate]
        count["SP-shaped key candidates"]+=len(token_entries)
        for entry in token_entries:
            matches=exp._spool_token_index().get(entry.token_candidate,())
            count["matching SPLCB primary candidates"]+=len(matches)
            count["ambiguous token candidates"]+=(len(matches)>1)
            count["unmatched SP-shaped candidates"]+=(len(matches)==0)
        if entries and not walked:
            model.show_evidence(dict(obj=obj),exp.rows)
            i=next(i for i,row in enumerate(model.rows())
                   if row.get("request",{}).get("entry") is not None)
            model.selected=i;model.open_row(i)
            if model.rows()[0]["name"]!="Saved printer-queue key":
                raise ValueError("PRTQ exact-key detail not opened")
            candidate=next((j for j,row in enumerate(model.rows())
                            if row.get("object") is not None),None)
            if candidate is not None:
                model.selected=candidate;model.open_row(candidate)
                if model.rows()[0]["name"]!="Saved spool-control evidence":
                    raise ValueError("PRTQ SPLCB candidate navigation failed")
                model.back()
                if model.selected!=candidate:
                    raise ValueError("PRTQ linked spool Back lost selection")
                count["token-candidate/Back walkthroughs"]+=1
            model.back()
            if model.selected!=i:
                raise ValueError("PRTQ key/Back lost selection")
            count["PRTQ key/Back walkthroughs"]+=1
            walked=True
    after=digest(path)
    if before!=after:
        raise ValueError("Original archival HDA digest changed")
    return {"image_bytes":Path(path).stat().st_size,
            "sha256":after,"unchanged":True,
            "counts":dict(sorted(count.items()))}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    args=parser.parse_args()
    print(json.dumps(validate(args.image),indent=2))
