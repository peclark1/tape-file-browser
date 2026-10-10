#!/usr/bin/env python3
"""Read-only physical-primary candidate census for four CISC OS/400 MI types.

This deliberately does NOT count *active* objects. Overwritten, deleted,
unreferenced, duplicate, and otherwise stale physical segment primaries may
survive in an archival disk image. Never use counts as a system inventory.

Input: raw .hda (520-byte physical sectors) or ZIP containing one .hda.
Output: aggregates only; no recovered object names or content are exported.

The four recognized segment group variants are empirically observed in
Mark V2R3 and Pete B10 images, not generic IBM MI specifications.
"""
import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
import json
from pathlib import Path
import re
import sys
import zipfile

SECTOR_SIZE = 520
KNOWN = {
    "0201": ("*PGM", {0x80, 0x81, 0x89}),
    "1905": ("*CMD", {0x89}),
    "0E03": ("*MSGF", {0x90}),
    "1916": ("*MENU", {0x80, 0x81}),
}


def primary_candidate(page):
    """Return (MI code, decoded name, segment tag) or None.

    Uses only a single 512-byte payload from a 520-byte physical sector.
    False negatives are possible; the conservative filter is deliberate.
    """
    if len(page) != 512 or page[0] != 0x01:
        return None
    if page[0x20:0x22] != b"\x80\x00":
        return None
    code = page[0x22:0x24].hex().upper()
    if code not in KNOWN or page[1] not in KNOWN[code][1]:
        return None
    # A primary EPA name occupies 30 EBCDIC bytes, right-padded.
    name = page[0x24:0x42].decode("cp037", errors="replace").rstrip(" ")
    if not 1 <= len(name) <= 30 or not re.fullmatch(r"[A-Z0-9#$@_]+", name):
        return None
    if not page[2:4] or int.from_bytes(page[2:4], "big") == 0:
        return None
    return code, name, page[1]


@contextmanager
def open_hda(path):
    path = Path(path)
    if path.suffix.lower() != ".zip":
        with path.open("rb") as stream:
            yield stream
    else:
        with zipfile.ZipFile(path) as archive:
            files = [entry for entry in archive.infolist()
                     if not entry.is_dir() and entry.filename.lower().endswith(".hda")]
            if len(files) != 1:
                raise ValueError("ZIP must contain exactly one .hda image")
            with archive.open(files[0]) as stream:
                yield stream


def census(stream, *, chunk_sectors=4096):
    counts = Counter()
    names = defaultdict(set)
    variants = defaultdict(Counter)
    sectors = 0
    tail = b""
    while True:
        chunk = stream.read(SECTOR_SIZE * chunk_sectors)
        if not chunk:
            break
        data = tail + chunk
        end = (len(data) // SECTOR_SIZE) * SECTOR_SIZE
        for pos in range(0, end, SECTOR_SIZE):
            sector = data[pos:pos + SECTOR_SIZE]
            entry = primary_candidate(sector[8:])
            if entry is None:
                continue
            code, name, variant = entry
            counts[code] += 1
            names[code].add(name)
            variants[code][f"{variant:02X}"] += 1
        sectors += end // SECTOR_SIZE
        tail = data[end:]
    if tail:
        raise ValueError("Input image is not a complete 520-byte-sector image")
    return {
        "input_sectors": sectors,
        "method": "conservative physical primary page signatures; not an active-object census",
        "results": {
            code: {
                "type": KNOWN[code][0],
                "primary_candidates": counts[code],
                "distinct_primary_names": len(names[code]),
                "segment_group_variants": dict(sorted(variants[code].items())),
            }
            for code in KNOWN
        },
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("image", type=Path, help="Read-only .hda or single-HDA ZIP")
    p.add_argument("--output", type=Path,
                   help="Write JSON aggregate report (no recovered names)")
    args = p.parse_args(argv)
    with open_hda(args.image) as stream:
        report = census(stream)
    report["image_filename"] = args.image.name
    body = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(body, encoding="utf-8")
        print("Census saved; no recovered object names or disk contents included.")
    else:
        sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
