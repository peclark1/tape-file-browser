#!/usr/bin/env python3
"""Read-only reproducible CISC SCHIDX/MSRVI index workflow audit.

Reports aggregate recovery counts and UI navigation only. No archival data,
private key values or record content is emitted or committed.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from as400_dasd import DASDImage
from as400_5250 import Guided5250
from as400_archival_indexes import ArchivalIndexExplorer, TYPES
from tools.validate_command_exploration import digest


def validate(path):
    before = digest(path)
    image = DASDImage(path)
    scan = image.scan()
    segments = image.recover_segments(scan)
    inventory = image.recover_objects(scan, segments)
    explorer = ArchivalIndexExplorer(image)
    model = Guided5250(inventory, archival_index_loader=explorer.rows)
    counts = Counter()
    walked = set()
    for obj in inventory.objects:
        if obj.type_code not in TYPES:
            continue
        kind = TYPES[obj.type_code][0]
        counts[kind + " primaries"] += 1
        try:
            keys, warnings, scalar, page_size = explorer.entries(obj)
        except (OSError, ValueError):
            counts[kind + " withheld primaries"] += 1
            continue
        counts[kind + " keys"] += len(keys)
        counts[kind + " warning instances"] += len(warnings)
        counts[kind + f" page size {page_size}"] += 1
        counts[kind + " scalar discrepancies"] += (scalar != len(keys))
        if kind in walked or not keys:
            continue
        model.show_evidence(dict(obj=obj), explorer.rows)
        idx = next((i for i, row in enumerate(model.rows()) if
                    row.get("request", {}).get("entry") is not None), None)
        if idx is None:
            continue
        model.selected = idx
        model.open_row(idx)
        if model.rows()[0]["name"] != "Opaque index key":
            raise ValueError("Index key detail navigation failed")
        model.back()
        if model.selected != idx:
            raise ValueError("Back lost the index selection")
        counts[kind + " UI walkthroughs"] += 1
        walked.add(kind)
        model.back()
    after = digest(path)
    if before != after:
        raise ValueError("Original archival image SHA-256 changed")
    return {"image_bytes": Path(path).stat().st_size, "sha256": after,
            "unchanged": True, "counts": dict(sorted(counts.items()))}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    args = parser.parse_args()
    print(json.dumps(validate(args.image), indent=2))
