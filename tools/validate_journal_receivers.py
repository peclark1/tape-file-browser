#!/usr/bin/env python3
"""Read-only full recovered-object JRN <-> JRNRCV address-link audit.

Outputs aggregate counts and original SHA256 only. Does not dump names,
journal entries, receiver content or raw pointers. Original HDAs remain
read-only; image scan and virtual extent reconstruction are shared.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from as400_dasd import DASDImage
from as400_5250 import Guided5250
from as400_journals import JournalReceiverExplorer
from tools.validate_command_exploration import digest


def validate(path):
    before=digest(path)
    image=DASDImage(path)
    scan=image.scan()
    segments=image.recover_segments(scan)
    inventory=image.recover_objects(scan,segments)
    ex=JournalReceiverExplorer(image,inventory)
    model=Guided5250(inventory,capability_loader=lambda obj,sample=None:ex.rows(obj))
    counts=Counter()
    seen_source=False
    seen_receiver=False
    seen_direct_parent=False
    for obj in inventory.objects:
        if obj.type_code!="09/01":
            continue
        counts["recovered journal primaries"]+=1
        try:
            pointers=ex.addresses(obj)
        except (OSError,ValueError):
            counts["unsupported/fragmented journal primaries"]+=1
            continue
        counts["supported two-slot journal layouts"]+=1
        for slot in pointers:
            counts[f"journal slot 0x{slot.offset:X}"]+=1
            if slot.address.is_null:
                counts["saved null address slots"]+=1
                continue
            targets=ex._receivers_by_address.get(slot.address.key,())
            counts["nonzero saved full addresses"]+=1
            counts["full address matches to recovered receiver primaries"]+=len(targets)
            counts["saved addresses without recovered target"]+=(len(targets)==0)
            counts["ambiguous multi-origin saved address slots"]+=(len(targets)>1)
        if not seen_source and any(
                ex._receivers_by_address.get(p.address.key)
                for p in pointers if not p.address.is_null):
            model.run_command("DSPJRN JRN(*ALL/*)")
            if model.screen!="type_objects":
                raise ValueError("JRN selection screen did not open")
            i=next(i for i,row in enumerate(model.rows()) if row.get("object") is obj)
            model.selected=i;model.open_row(i)
            if model.rows()[0]["name"]!="Saved journal receiver addresses":
                raise ValueError("Journal address view missing")
            link=next((j for j,row in enumerate(model.rows())
                       if row.get("object") is not None),None)
            if link is not None:
                model.selected=link;model.open_row(link)
                if model.rows()[0]["name"]!="Saved journal receiver identity":
                    raise ValueError("Exact receiver navigation did not open")
                model.back()
                if model.selected!=link:
                    raise ValueError("Receiver link Back changed selection")
                counts["journal-to-receiver/Back walkthroughs"]+=1
            seen_source=True
    for receiver in inventory.objects:
        if receiver.type_code!="07/01":
            continue
        counts["recovered receiver primaries"]+=1
        rows=ex.rows(receiver)
        try:
            saved_parent=ex.receiver_parent_address(receiver)
        except (OSError,ValueError):
            counts["unsupported receiver-owned journal pointers"]+=1
        else:
            counts["supported receiver-owned pointer fields"]+=1
            counts["saved null parent addresses"]+=saved_parent.is_null
            if not saved_parent.is_null:
                count=len(ex._journals_by_address.get(saved_parent.key,()))
                counts["exact receiver-to-journal owner key matches"]+=count
                counts["receiver pointers with no journal primary"]+=(count==0)
                counts["ambiguous direct receiver parent candidates"]+=(count>1)
                if count and not seen_direct_parent:
                    model.show_evidence(dict(obj=receiver),ex.rows)
                    evidence=next((i for i,row in enumerate(model.rows())
                                  if row.get("name")=="Receiver-saved journal pointer"),None)
                    if evidence is None:
                        raise ValueError("Receiver-owned +0x108 pointer evidence missing")
                    counts["receiver direct-parent evidence walkthroughs"]+=1
                    seen_direct_parent=True
        links=[(i,row) for i,row in enumerate(rows) if row.get("object") is not None]
        counts["reverse saved-address references"]+=len(links)
        counts["receivers with saved journal links"]+=bool(links)
        if not seen_receiver and links:
            model.run_command("DSPJRNRCV JRNRCV(*ALL/*)")
            if model.screen!="type_objects":
                raise ValueError("JRNRCV selection screen did not open")
            i=next(i for i,row in enumerate(model.rows()) if row.get("object") is receiver)
            model.selected=i;model.open_row(i)
            if model.rows()[0]["name"]!="Saved journal receiver identity":
                raise ValueError("Receiver reverse view missing")
            link=next(j for j,row in enumerate(model.rows())
                      if row.get("object") is not None)
            model.selected=link;model.open_row(link)
            if model.rows()[0]["name"]!="Saved journal receiver addresses":
                raise ValueError("Receiver-to-journal navigation failed")
            model.back()
            if model.selected!=link:
                raise ValueError("Receiver reverse-link Back selection changed")
            counts["receiver-to-journal/Back walkthroughs"]+=1
            seen_receiver=True
    counts["unsupported journal primaries excluded from reverse index"]=ex._withheld
    counts["receiver records withheld from parent reverse index"]=ex._receiver_direct_withheld
    after=digest(path)
    if before!=after:
        raise ValueError("Original archived HDA SHA256 changed")
    return {"image_bytes":Path(path).stat().st_size,
            "sha256":after, "unchanged":True,
            "counts":dict(sorted(counts.items()))}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    print(json.dumps(validate(parser.parse_args().image),indent=2))
