#!/usr/bin/env python3
"""Read-only full-image SPLCB name-slot/navigation audit (counts only)."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from as400_dasd import DASDImage
from as400_5250 import Guided5250
from as400_spool_controls import SpoolControlExplorer
from tools.validate_command_exploration import digest


def validate(path):
    before=digest(path)
    image=DASDImage(path)
    scan=image.scan();segments=image.recover_segments(scan)
    inventory=image.recover_objects(scan,segments)
    explorer=SpoolControlExplorer(image,inventory)
    model=Guided5250(inventory,capability_loader=lambda obj,sample=None:explorer.rows(obj))
    counts=Counter()
    walkthrough=False
    for obj in inventory.objects:
        if obj.type_code!="19/C2":
            continue
        counts["recovered spool-control primaries"]+=1
        try:
            rows=explorer.rows(obj)
        except (OSError,ValueError):
            counts["unsupported primary layouts"]+=1
            continue
        counts["bounded primary inspections"]+=1
        names=rows[0]["lines"]
        counts["complete name pairs"]+=("<unresolved>" not in names[1]+names[2])
        counts["SP-shaped saved tokens"]+=("<unresolved>" not in names[3])
        target_rows=[row for row in rows if row.get("object") is not None]
        counts["recovered qualified-name candidates"]+=len(target_rows)
        if target_rows and not walkthrough:
            model.show_evidence(dict(obj=obj),explorer.rows)
            i=next(i for i,r in enumerate(model.rows()) if r.get("object") is not None)
            model.selected=i;model.open_row(i);model.back()
            if model.selected!=i:
                raise ValueError("Spool-control name selection lost on Back")
            walkthrough=True
            counts["candidate-navigation/Back walkthroughs"]+=1
    after=digest(path)
    if before!=after:raise ValueError("Original image SHA-256 changed")
    return {"image_bytes":Path(path).stat().st_size,
            "sha256":after,"unchanged":True,
            "counts":dict(sorted(counts.items()))}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("image")
    print(json.dumps(validate(p.parse_args().image),indent=2))
