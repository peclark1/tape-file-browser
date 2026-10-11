#!/usr/bin/env python3
"""Validate saved OUTQ/JOBQ key workflows against original CISC HDA files.

Read-only. Prints aggregated counts only, never key bytes, object names,
spooled content or user records. No image modifications.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from as400_dasd import DASDImage
from as400_5250 import Guided5250
from as400_outq import OutputQueueExplorer
from tools.validate_command_exploration import digest


def validate(path):
    before = digest(path)
    image = DASDImage(path)
    scan = image.scan()
    segments = image.recover_segments(scan)
    inventory = image.recover_objects(scan, segments)
    explorer = OutputQueueExplorer(image)
    model = Guided5250(inventory, outq_loader=explorer.rows)
    counts = Counter()
    visited = set()
    for obj in inventory.objects:
        if obj.type_code not in ("0E/01", "0E/02"):
            continue
        kind = "JOBQ" if obj.type_code == "0E/01" else "OUTQ"
        counts[kind + " primaries"] += 1
        try:
            entries, warnings = explorer.entries(obj)
        except (ValueError, OSError):
            counts[kind + " withheld primaries"] += 1
            continue
        counts[kind + " terminal keys"] += len(entries)
        counts[kind + " control-like"] += sum(e.control_like for e in entries)
        counts[kind + " non-control"] += sum(not e.control_like for e in entries)
        counts[kind + " candidate form tokens"] += sum(
            e.form_candidate is not None for e in entries) if kind == "OUTQ" else 0
        counts[kind + " warning instances"] += len(warnings)
        # Test actual navigator models, even if every saved key looks control-like.
        model.show_evidence(dict(obj=obj), explorer.rows)
        if model.rows()[0]["name"] != "Saved " + kind + " index":
            raise ValueError("Queue summary did not open")
        candidates = [i for i, row in enumerate(model.rows())
                      if row.get("request", {}).get("entry") is not None]
        if candidates and kind not in visited:
            selected = candidates[0]
            model.selected = selected
            model.open_row(selected)
            if model.rows()[0]["name"] != "Saved " + kind + " key":
                raise ValueError("Queue key detail did not open")
            model.back()
            if model.selected != selected:
                raise ValueError("Queue Back lost its selected key")
            visited.add(kind)
            counts[kind + " key walkthroughs"] += 1
        model.back()
    after = digest(path)
    if before != after:
        raise ValueError("Original HDA hash changed")
    return {
        "image_bytes": Path(path).stat().st_size,
        "sha256": after,
        "unchanged": True,
        "counts": dict(sorted(counts.items())),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    args = parser.parse_args()
    print(json.dumps(validate(args.image), indent=2))
