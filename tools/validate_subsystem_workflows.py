#!/usr/bin/env python3
"""Reproduce archival SBSD/CLS name-occurrence checks without disclosing names.

All image access is read-only, output is aggregate counts and hash only.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from as400_dasd import DASDImage
from as400_subsystems import SubsystemExplorer
from as400_5250 import Guided5250
from tools.validate_command_exploration import digest


def validate(path):
    before=digest(path)
    img=DASDImage(path)
    scan=img.scan()
    segments=img.recover_segments(scan)
    inv=img.recover_objects(scan,segments)
    service=SubsystemExplorer(img,inv)
    model=Guided5250(inv,subsystem_loader=service.rows,
                     capability_loader=lambda o,sample=None:service.rows(o))
    counts=Counter()
    sampled=False
    for obj in inv.objects:
        if obj.type_code!="19/09":
            continue
        counts["SBSD recovered primaries"]+=1
        try:
            found,self_echo,truncated,read_size=service._evidence(obj)
        except (ValueError,OSError):
            counts["SBSD withheld primaries"]+=1
            continue
        counts["SBSD padded-name candidate target occurrences"]+=len(found)
        counts["SBSD self-name occurrence offsets"]+=self_echo
        counts["SBSD scans truncated by candidate count"]+=int(truncated)
        for offset,target in found:
            counts["SBSD candidate target "+target.type_code]+=1
        if found and not sampled:
            model.explore_object(obj)
            i=next(i for i,r in enumerate(model.rows()) if r.get("object") is not None)
            model.selected=i;model.open_row(i)
            model.back()
            if model.selected!=i: raise ValueError("SBSD Back lost source selection")
            sampled=True;counts["SBSD candidate navigation checks"]+=1
    for obj in inv.objects:
        if obj.type_code!="19/04":continue
        counts["CLS recovered primaries"]+=1
        rows=service.rows(obj)
        links=[r for r in rows if r.get("object") is not None]
        counts["CLS reverse candidate links"]+=len(links)
    after=digest(path)
    if after!=before:raise ValueError("Original image hash changed")
    return dict(image_bytes=Path(path).stat().st_size,sha256=after,unchanged=True,
                counts=dict(sorted(counts.items())))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("image")
    a=p.parse_args()
    print(json.dumps(validate(a.image),indent=2))
