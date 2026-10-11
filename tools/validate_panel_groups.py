#!/usr/bin/env python3
"""Read-only compiled CISC PNLGRP identity scan with aggregate-only output."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from as400_dasd import DASDImage
from as400_5250 import Guided5250
from as400_panel_groups import PanelGroupExplorer, WINDOW_BYTES
from tools.validate_command_exploration import digest


def validate(path):
    before=digest(path)
    image=DASDImage(path)
    scan=image.scan()
    segments=image.recover_segments(scan)
    inventory=image.recover_objects(scan,segments)
    explorer=PanelGroupExplorer(image,inventory)
    model=Guided5250(inventory,panel_group_loader=explorer.rows)
    counts=Counter()
    walked=set()
    for obj in inventory.objects:
        if obj.type_code!="19/15":
            continue
        counts["recovered panel-group primaries"]+=1
        for start in (0,WINDOW_BYTES):
            if start>=obj.segment.pages*512:
                continue
            try:
                symbols,header,readsize,capacity=explorer.symbols(obj,start)
            except (OSError,ValueError):
                counts["unsupported or unrecovered windows"]+=1
                continue
            counts["validated virtual scan windows"]+=1
            counts["name-shaped tagged symbols"]+=len(symbols)
            counts["windows with candidates"]+=bool(symbols)
            counts[f"header variant {header}"]+=1 if start==0 else 0
            if symbols and (start//WINDOW_BYTES) not in walked:
                model.show_evidence(dict(obj=obj,at=start),explorer.rows)
                row=next((i for i,r in enumerate(model.rows())
                          if r.get("request",{}).get("symbol") is not None),None)
                if row is not None:
                    model.selected=row;model.open_row(row)
                    if model.rows()[0]["name"]!="Tagged compiled name":
                        raise ValueError("PNLGRP symbol detail did not open")
                    model.back()
                    if model.selected!=row:
                        raise ValueError("PNLGRP Back lost selected symbol")
                    counts["symbol detail/Back walkthroughs"]+=1
                    walked.add(start//WINDOW_BYTES)
    after=digest(path)
    if before!=after:
        raise ValueError("Original archive changed")
    return {"image_bytes":Path(path).stat().st_size,"sha256":after,
            "unchanged":True,"counts":dict(sorted(counts.items()))}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    print(json.dumps(validate(parser.parse_args().image),indent=2))
