#!/usr/bin/env python3
"""Read-only recovered CISC GSS table and exact symbol-byte navigation audit.

This tests the production recovered *virtual* extents and 5250 selected
origin. The independent physical-signature survey is not equivalent.
No symbol bytes, name/private content, records or fonts are printed.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from as400_dasd import DASDImage
from as400_5250 import Guided5250
from as400_gss import SavedSymbolExplorer
from tools.validate_command_exploration import digest


def validate(path):
    before=digest(path)
    image=DASDImage(path)
    scan=image.scan()
    segments=image.recover_segments(scan)
    inventory=image.recover_objects(scan,segments)
    service=SavedSymbolExplorer(image)
    model=Guided5250(inventory,gss_loader=service.rows)
    stats=Counter()
    walked=False
    for primary in inventory.objects:
        if primary.type_code!="19/0C":
            continue
        stats["recovered GSS primaries"]+=1
        try:
            slots,warnings,empty=service.slots(primary)
        except (OSError,ValueError):
            stats["unrecognized GSS variants or virtual gaps"]+=1
            continue
        stats["supported 176-slot tables"]+=1
        stats["bounded saved record slots"]+=len(slots)
        stats["empty pointer slots"]+=empty
        stats["duplicate offset aliases"]+=sum(s.alias for s in slots)
        stats["FF00-delimited records"]+=sum(s.status=="delimited" for s in slots)
        stats["open-tail final records"]+=sum(s.status=="open-tail" for s in slots)
        stats["withheld record warnings"]+=len(warnings)
        if slots and not walked:
            model.show_evidence(dict(obj=primary),service.rows)
            i=next((i for i,r in enumerate(model.rows()) if
                    r.get("kind")=="gss_symbol_action" and
                    r.get("request",{}).get("slot") is not None),None)
            if i is None:
                raise ValueError("GSS slot action omitted from Guided view")
            model.selected=i
            model.open_row(i)
            if model.rows()[0]["name"]!="Saved GSS byte record":
                raise ValueError("Selected GSS byte record did not open")
            model.back()
            if model.selected!=i:
                raise ValueError("GSS Back changed saved record selection")
            stats["slot/detail/Back walkthroughs"]+=1
            walked=True
    after=digest(path)
    if before!=after:
        raise ValueError("Original archived DASD SHA256 changed")
    return {"image_bytes":Path(path).stat().st_size,
            "sha256":after,"unchanged":True,
            "counts":dict(sorted(stats.items()))}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("image")
    print(json.dumps(validate(p.parse_args().image),indent=2))
