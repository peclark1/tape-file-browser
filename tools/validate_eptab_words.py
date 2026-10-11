#!/usr/bin/env python3
"""Read-only recovered-image EPTAB 512-u16 word and hash comparison audit.

Run on each separately extracted original HDA. One normal DASD scan and
inventory per file, SHA256 before/after, aggregate-only counts and SHA256
of the bounded 1024-byte word region. No word values or object names
are output, and source bytes are never modified.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from as400_dasd import DASDImage
from as400_5250 import Guided5250
from as400_eptab import EPTabExplorer
from tools.validate_command_exploration import digest


def validate(path):
    before=digest(path)
    image=DASDImage(path)
    scan=image.scan()
    segments=image.recover_segments(scan)
    inventory=image.recover_objects(scan,segments)
    service=EPTabExplorer(image)
    model=Guided5250(inventory,eptab_loader=service.rows)
    counts=Counter();streams=[]
    walked=False
    for obj in inventory.objects:
        if obj.type_code!="19/D7":
            continue
        counts["recovered EPTAB primaries"]+=1
        try:
            words=service.words(obj)
        except (OSError,ValueError):
            counts["unrecoverable or unsupported EPTAB primaries"]+=1
            continue
        counts["bounded 512-word regions"]+=1
        counts["saved word slots"]+=len(words)
        counts["word 0045 occurrences"]+=sum(w.value==0x45 for w in words)
        counts["word 0000 occurrences"]+=sum(w.value==0 for w in words)
        counts["other saved word values"]+=sum(w.value not in (0,0x45) for w in words)
        word_bytes=b"".join(word.value.to_bytes(2,"big") for word in words)
        streams.append(sha256(word_bytes).hexdigest())
        if not walked:
            model.run_command("DSPEPTAB EPTAB(*ALL/*) WORD(0045)")
            if model.screen=="type_objects":
                idx=next(i for i,row in enumerate(model.rows())
                         if row.get("object") is obj)
                model.selected=idx
                model.open_row(idx)
            if model.screen!="capabilities" or model.rows()[0]["name"]!="Saved EPTAB 16-bit words":
                raise ValueError("EPTAB 16-bit word search screen did not open")
            detail=next((i for i,row in enumerate(model.rows())
                        if row.get("kind")=="eptab_word_action" and
                        row.get("request",{}).get("entry") is not None),None)
            if detail is not None:
                model.selected=detail
                model.open_row(detail)
                if model.rows()[0]["name"]!="Saved EPTAB word":
                    raise ValueError("Selected saved-word detail did not open")
                model.back()
                if model.selected!=detail:
                    raise ValueError("EPTAB Back lost word selection")
                counts["selected word/Back walkthroughs"]+=1
            walked=True
    after=digest(path)
    if before!=after:
        raise ValueError("Original archived HDA SHA256 changed")
    return {"image_bytes":Path(path).stat().st_size,"sha256":after,
            "unchanged":True,
            "word_region_sha256":sorted(streams),
            "counts":dict(sorted(counts.items()))}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("image",type=Path)
    print(json.dumps(validate(p.parse_args().image),indent=2))
