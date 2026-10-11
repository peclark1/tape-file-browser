#!/usr/bin/env python3
"""Read-only original-image QLDA validation (aggregate counts, no values)."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from as400_dasd import DASDImage
from as400_5250 import Guided5250
from as400_local_data import LocalDataExplorer
from tools.validate_command_exploration import digest


def validate(path):
    before=digest(path)
    image=DASDImage(path)
    scan=image.scan();segments=image.recover_segments(scan)
    inventory=image.recover_objects(scan,segments)
    explorer=LocalDataExplorer(image)
    model=Guided5250(inventory,lda_loader=explorer.rows)
    counts=Counter()
    for obj in inventory.objects:
        if obj.type_code!="19/CE":
            continue
        counts["recovered LDA primaries"]+=1
        try:
            value=explorer.data(obj)
        except (OSError,ValueError):
            counts["unsupported or truncated LDA primaries"]+=1
            continue
        counts["fully bounded 1024-byte values"]+=1
        counts["blank-only values"]+=(value==bytes([0x40])*1024)
        counts["values containing nonblank bytes"]+=(value!=bytes([0x40])*1024)
        if not counts["page/Back walkthroughs"]:
            model.show_evidence(dict(obj=obj),explorer.rows)
            next_idx=next(i for i,r in enumerate(model.rows()) if r["name"]=="Next 128")
            model.selected=next_idx;model.open_row(next_idx)
            if "129..256" not in model.rows()[0]["lines"][3]:
                raise ValueError("LDA next page did not preserve value positions")
            model.back()
            if model.selected!=next_idx:
                raise ValueError("LDA Back selection lost")
            counts["page/Back walkthroughs"]+=1
    after=digest(path)
    if before!=after:
        raise ValueError("Original archival image SHA-256 changed")
    return {"image_bytes":Path(path).stat().st_size,
            "sha256":after,"unchanged":True,
            "counts":dict(sorted(counts.items()))}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("image")
    print(json.dumps(validate(p.parse_args().image),indent=2))
