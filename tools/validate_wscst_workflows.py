#!/usr/bin/env python3
"""Read-only complete recovered WSCST transform/name candidate audit.

One normal physical scan/virtual recovery, guarded transform metadata,
name correlations, original selection/Back, SHA256 before/after.
Emits counts only: never original printer setup bytes or saved names.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from as400_dasd import DASDImage
from as400_5250 import Guided5250
from as400_wscst import WorkstationTransformExplorer
from tools.validate_command_exploration import digest


def validate(path):
    before=digest(path)
    image=DASDImage(path)
    scan=image.scan();segments=image.recover_segments(scan)
    inv=image.recover_objects(scan,segments)
    exp=WorkstationTransformExplorer(image,inv)
    model=Guided5250(inv,capability_loader=lambda obj,sample=None:exp.rows(obj))
    count=Counter()
    navigated=False
    for item in inv.objects:
        if item.type_code!="19/38":continue
        count["recovered WSCST primaries"]+=1
        try:hdr=exp.header(item)
        except (ValueError,OSError):
            count["unsupported or incomplete TRANSFORM wrappers"]+=1
            continue
        count["validated saved TRANSFORM wrappers"]+=1
        count["supported name-shaped saved fields"]+=len(hdr.references)
        for saved in hdr.references:
            targets=exp._by_name.get(saved.name,())
            count["same-name WSCST target primaries"]+=len(targets)
            count["unmatched saved name candidates"]+=(len(targets)==0)
            count["ambiguous matched name candidates"]+=(len(targets)>1)
        if navigated or not any(exp._by_name.get(r.name) for r in hdr.references):
            continue
        model.explore_object(item)
        i=next((i for i,r in enumerate(model.rows())
                if r.get("object") is not None),None)
        if i is None:raise ValueError("Supported WSCST name link omitted")
        model.selected=i;model.open_row(i)
        if model.rows()[0]["name"]!="Saved WSCST TRANSFORM descriptor":
            raise ValueError("Linked transform primary did not open")
        reverse=next((j for j,r in enumerate(model.rows())
                      if r.get("object") is item),None)
        if reverse is None:
            raise ValueError("Reverse WSCST name candidate missing")
        model.selected=reverse;model.open_row(reverse)
        if model.rows()[0]["name"]!="Saved WSCST TRANSFORM descriptor":
            raise ValueError("Reverse source transform did not open")
        model.back()
        if model.selected!=reverse:
            raise ValueError("Reverse WSCST Back selection lost")
        model.back()
        if model.selected!=i:
            raise ValueError("Forward WSCST Back selection lost")
        count["forward/reverse name/Back walkthroughs"]+=1
        navigated=True
    after=digest(path)
    if before!=after:raise ValueError("Original archived image SHA256 changed")
    return {"image_bytes":Path(path).stat().st_size,"sha256":after,
            "unchanged":True,"counts":dict(sorted(count.items()))}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    print(json.dumps(validate(parser.parse_args().image),indent=2))
