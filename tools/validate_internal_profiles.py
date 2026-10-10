#!/usr/bin/env python3
"""Read-only INTPRF/USRPRF name-correlation census; aggregate results only."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from as400_dasd import DASDImage
from as400_5250 import Guided5250
from as400_internal_profiles import InternalProfileExplorer
from tools.validate_command_exploration import digest


def validate(path):
    before = digest(path)
    image = DASDImage(path)
    scan = image.scan()
    segments = image.recover_segments(scan)
    inventory = image.recover_objects(scan,segments)
    ex = InternalProfileExplorer(inventory)
    counts = Counter()
    profiles = [o for o in inventory.objects if o.type_code == "0E/C4"]
    users = [o for o in inventory.objects if o.type_code == "08/01"]
    counts["recovered internal primaries"] = len(profiles)
    counts["recovered user primaries"] = len(users)
    counts["unique internal names"] = len(set(o.name.upper() for o in profiles))
    model = Guided5250(inventory, capability_loader=lambda o,sample=None: ex.rows(o))
    for obj in profiles:
        rows = ex.rows(obj)
        linked = [r for r in rows if r.get("object") is not None]
        counts["name-candidate links"] += len(linked)
        counts["no-match internal primaries"] += (not bool(linked))
        counts["multiple-matches internal primaries"] += len(linked) > 1
        if linked and not counts["identity walkthroughs"]:
            model.run_command("DSPINTPRF INTPRF(*ALL/*)")
            # Navigate by the exact recovered primary's object identity, never
            # assume a globally unique name.
            model.explore_object(obj)
            selected=next(i for i,r in enumerate(model.rows()) if r.get("object") is not None)
            model.selected=selected
            model.open_row(selected)
            if model.screen != "config_info":
                raise ValueError("Profile identity link did not open safe view")
            model.back()
            if model.selected != selected:
                raise ValueError("Back did not preserve internal-profile selection")
            counts["identity walkthroughs"] += 1
    after = digest(path)
    if before != after:
        raise ValueError("Archival HDA SHA256 changed")
    return {"image_bytes":Path(path).stat().st_size,
            "sha256":after,"unchanged":True,"counts":dict(sorted(counts.items()))}


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("image")
    a=p.parse_args()
    print(json.dumps(validate(a.image),indent=2))
