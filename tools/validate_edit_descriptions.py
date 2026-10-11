#!/usr/bin/env python3
"""Original-image EDTD edit-mask and peer-navigation audit (aggregate only)."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from as400_dasd import DASDImage
from as400_5250 import Guided5250
from as400_edit_descriptions import EditDescriptionExplorer
from tools.validate_command_exploration import digest


def validate(path):
    before=digest(path)
    image=DASDImage(path)
    scan=image.scan();segments=image.recover_segments(scan)
    inventory=image.recover_objects(scan,segments)
    explorer=EditDescriptionExplorer(image,inventory)
    model=Guided5250(inventory,capability_loader=lambda obj,sample=None:explorer.rows(obj))
    counts=Counter()
    walked=False
    for obj in inventory.objects:
        if obj.type_code!="19/08":
            continue
        counts["recovered edit descriptions"]+=1
        try:
            view=explorer.evidence(obj)
        except (OSError,ValueError):
            counts["unsupported variants"]+=1
            continue
        counts["bounded candidate patterns"]+=1
        counts["candidate separator bytes"]+=sum(b in (0x6B,0x60)
                                                  for b in view.template)
        counts["saved sign token length "+str(len(view.sign))]+=1
        counts["Y/N flag "+view.flag.hex().upper()]+=1
        if walked:
            continue
        model.explore_object(obj)
        if model.rows()[0]["name"]!="Saved edit pattern evidence":
            raise ValueError("EDTD candidate pattern viewer not reachable")
        i=next((i for i,row in enumerate(model.rows())
                if row.get("object") is not None),None)
        if i is not None:
            model.selected=i
            model.open_row(i)
            if model.rows()[0]["name"]!="Saved edit pattern evidence":
                raise ValueError("Peer EDTD pattern navigation failed")
            model.back()
            if model.selected!=i:
                raise ValueError("EDTD Back lost comparison selection")
            counts["compare/Back walkthroughs"]+=1
            walked=True
    after=digest(path)
    if before!=after:
        raise ValueError("Original archival image digest changed")
    return {"image_bytes":Path(path).stat().st_size,"sha256":after,
            "unchanged":True,"counts":dict(sorted(counts.items()))}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("image")
    print(json.dumps(validate(p.parse_args().image),indent=2))
