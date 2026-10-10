#!/usr/bin/env python3
"""Conservative all-MI physical-primary signature survey of AS/400 CISC HDA.

Reads the complete image read-only. This does NOT resolve the context index,
live objects, stale/duplicate primaries, or completeness of the disk image.

No object names, recovered bytes, or secrets are exported: only aggregates.
Supports a raw 520-byte-sector HDA or ZIP holding exactly one .hda file.
"""
import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
import json
from pathlib import Path
import re
import sys
import zipfile

SECTOR_BYTES = 520
NAME_RE = re.compile(r"^[A-Z0-9#$@_]{1,30}$")


@contextmanager
def open_image(path):
    path = Path(path)
    if path.suffix.lower() != ".zip":
        with path.open("rb") as fp:
            yield fp
    else:
        with zipfile.ZipFile(path) as archive:
            members = [m for m in archive.infolist()
                       if not m.is_dir() and m.filename.lower().endswith(".hda")]
            if len(members) != 1:
                raise ValueError("ZIP must contain exactly one .hda member")
            with archive.open(members[0]) as fp:
                yield fp


def candidate_primary(sector):
    """Return (MI code, EBCDIC name, segment tag), or None.

    Structural constraints are deliberately generic (unlike earlier
    type-specific scans): segment group byte 01, EPA signature 8000 at
    virtual-order logical payload +0x20, nonzero page count, uppercase
    IBM-style 30-byte name at +0x24, and two-byte MI type at +0x22.

    Heuristic, not a published complete on-disk validity test. Some
    legitimate primaries may be missed; coincidences can be included.
    """
    if len(sector) != SECTOR_BYTES:
        return None
    page = sector[8:]
    if page[0] != 1 or page[0x20:0x22] != b"\x80\x00":
        return None
    if page[2:4] == b"\x00\x00":
        return None
    name = page[0x24:0x42].decode("cp037", errors="replace").rstrip(" ")
    if NAME_RE.fullmatch(name) is None:
        return None
    return page[0x22:0x24].hex().upper(), name, f"{page[1]:02X}"


def survey(stream, *, chunk_sectors=8192):
    if chunk_sectors < 1:
        raise ValueError("chunk_sectors must be positive")
    counts = Counter()
    variants = defaultdict(Counter)
    distinct_names = defaultdict(set)
    rejected = Counter()
    sector_count = 0
    tail = b""
    while True:
        buf = tail + stream.read(SECTOR_BYTES * chunk_sectors)
        if not buf:
            break
        complete = len(buf) // SECTOR_BYTES
        view = memoryview(buf)
        for i in range(complete):
            sector = view[i * SECTOR_BYTES:(i + 1) * SECTOR_BYTES]
            page = sector[8:]
            if page[0] != 1 or page[0x20:0x22] != b"\x80\x00":
                continue
            if page[2:4] == b"\x00\x00":
                rejected["zero_declared_pages"] += 1
                continue
            name = bytes(page[0x24:0x42]).decode(
                "cp037", errors="replace").rstrip(" ")
            if NAME_RE.fullmatch(name) is None:
                rejected["invalid_ebcdic_name"] += 1
                continue
            code = bytes(page[0x22:0x24]).hex().upper()
            tag = f"{page[1]:02X}"
            counts[code] += 1
            variants[code][tag] += 1
            distinct_names[code].add(name)
        sector_count += complete
        tail = bytes(view[complete * SECTOR_BYTES:])
        del view
    if tail:
        raise ValueError("Image length is not a multiple of 520 bytes")
    return {
        "sector_size": SECTOR_BYTES,
        "sectors_scanned": sector_count,
        "candidate_primary_pages": sum(counts.values()),
        "distinct_mi_codes_observed": len(counts),
        "near_candidate_rejections": dict(rejected),
        "by_type": {
            code: {
                "physical_primary_candidates": count,
                "distinct_name_strings": len(distinct_names[code]),
                "segment_group_variants": dict(sorted(variants[code].items())),
            }
            for code, count in sorted(counts.items())
        },
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("image", type=Path, help="Raw .hda or single-member .hda ZIP")
    p.add_argument("--output", type=Path, help="JSON path; stdout if omitted")
    args = p.parse_args(argv)
    with open_image(args.image) as stream:
        results = survey(stream)
    # Only basename and aggregate counts are exposed.
    results["image_filename"] = args.image.name
    body = json.dumps(results, indent=2) + "\n"
    if args.output:
        args.output.write_text(body, encoding="utf-8")
    else:
        sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
