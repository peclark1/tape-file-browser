#!/usr/bin/env python3
"""Validate saved Mark CISC JMQ slots with complete recovery, read-only.

No original message payloads, key bytes or object names are output.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from as400_dasd import DASDImage
from as400_5250 import Guided5250
from as400_jmq import JobMessageQueueExplorer
from tools.validate_command_exploration import digest


def validate(path):
    before=digest(path);image=DASDImage(path)
    scan=image.scan();seg=image.recover_segments(scan);inv=image.recover_objects(scan,seg)
    exp=JobMessageQueueExplorer(image)
    model=Guided5250(inv,jmq_loader=exp.rows)
    counts=Counter();visited=False
    for obj in inv.objects:
        if obj.type_code!="18/A0":continue
        counts["recovered JMQ primaries"]+=1
        try:slots,n,warnings=exp.entries(obj)
        except (OSError,ValueError):
            counts["unsupported or noncontiguous primaries"]+=1;continue
        counts["validated saved count headers"]+=1
        counts["complete saved 16-byte slots"]+=len(slots)
        counts["extra/nonzero tail warnings"]+=len(warnings)
        counts["empty saved slot arrays"]+=(n==0)
        if slots and not visited:
            model.show_evidence(dict(obj=obj),exp.rows)
            selected=next(i for i,row in enumerate(model.rows())
                          if row.get("request",{}).get("entry") is not None)
            model.selected=selected;model.open_row(selected)
            if model.rows()[0]["name"]!="Saved JMQ slot":
                raise ValueError("Failed JMQ saved-slot detail navigation")
            model.back()
            if model.selected!=selected:
                raise ValueError("Lost JMQ Back selection")
            counts["saved-slot/Back walkthroughs"]+=1;visited=True
    after=digest(path)
    if before!=after:raise ValueError("Archival image digest changed")
    return {"image_bytes":Path(path).stat().st_size,
            "sha256":after,"unchanged":True,
            "counts":dict(sorted(counts.items()))}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("image")
    print(json.dumps(validate(p.parse_args().image),indent=2))
