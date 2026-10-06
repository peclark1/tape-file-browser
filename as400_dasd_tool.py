#!/usr/bin/env python3

"""Command-line DASD structure explorer for CISC AS/400 disk images."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from as400_dasd import (
    HEADER_SIZE,
    KNOWN_B10_SHADOW_LOG_VADDR,
    PAGE_SIZE,
    SECTOR_SIZE,
    DASDImage,
    Region,
    ebcdic_preview,
    format_hex,
)


def _open(path: str) -> DASDImage:
    return DASDImage(str(Path(path).expanduser()))


def _pct(part: int, whole: int) -> str:
    return "0.0%" if not whole else f"{100.0 * part / whole:.1f}%"


def _format_address(value: int | None) -> str:
    if value is None:
        return "-"
    return f"0x{value:012X}"


def _region_line(region: Region) -> str:
    lbas = f"{region.start_lba:,}-{region.end_lba:,}"
    if region.address_start is None:
        virtual = "-"
    else:
        virtual = (
            f"{_format_address(region.address_start)}-"
            f"{_format_address(region.address_end)}"
        )
    return (
        f"{lbas:<23} {region.sector_count:>10,}  "
        f"{virtual:<33} {region.kind}"
    )


def cmd_info(args):
    for index, path in enumerate(args.images):
        image = _open(path)
        if index:
            print()
        print(os.path.basename(image.path))
        print(f"  Path:          {image.path}")
        print(f"  Image bytes:   {image.size:,}")
        print(f"  Sector size:   {SECTOR_SIZE} bytes")
        print(f"  Header:        {HEADER_SIZE} bytes")
        print(f"  CISC page:     {PAGE_SIZE} bytes")
        print(f"  Sector count:  {image.sector_count:,}")
    return 0


def _scan(path, args):
    image = _open(path)
    result = image.scan(limit=args.limit, min_run=args.min_run)
    return image, result


def _map_lines_from_scan(image, result, args):
    lines = []
    lines.append(f"Disk: {os.path.basename(image.path)}")
    lines.append(f"  sectors:          {image.sector_count:,}")
    if result.scanned_sectors != image.sector_count:
        lines.append(f"  sectors scanned:  {result.scanned_sectors:,} (limited)")
    lines.append(
        f"  zero headers:     {result.zero_headers:,} "
        f"({_pct(result.zero_headers, result.scanned_sectors)})"
    )
    lines.append(
        f"  FF headers:       {result.ff_headers:,} "
        f"({_pct(result.ff_headers, result.scanned_sectors)})"
    )
    lines.append(
        f"  other headers:    {result.other_headers:,} "
        f"({_pct(result.other_headers, result.scanned_sectors)})"
    )
    lines.append(
        f"  zero payloads:    {result.zero_payloads:,} "
        f"({_pct(result.zero_payloads, result.scanned_sectors)})"
    )
    lines.append("")

    best = result.best_layout
    lines.append("  Address-header hypothesis")
    if best is None:
        lines.append("    No usable candidate could be scored.")
    else:
        lines.append(f"    layout:          {best.layout.name}")
        lines.append(
            f"    sequential:      {best.matches:,}/{best.comparisons:,} "
            f"adjacent comparisons ({best.ratio:.1%})"
        )
        lines.append(
            f"    confidence:      {best.confidence} "
            "(heuristic, not yet a decoded IBM field)"
        )
        lines.append(f"    address runs:    {len(result.sequential_regions):,}")
        lines.append(
            f"    sectors in runs: {result.sectors_in_sequential_regions:,} "
            f"({_pct(result.sectors_in_sequential_regions, result.scanned_sectors)})"
        )

        anchor = image.find_virtual(
            KNOWN_B10_SHADOW_LOG_VADDR,
            best.layout,
            limit=args.limit,
        )
        lines.append("")
        lines.append("  Known B10 validation anchor")
        if anchor:
            shown = ", ".join(f"LBA {lba:,}" for lba in anchor[:8])
            if len(anchor) > 8:
                shown += f", ... ({len(anchor):,} matches)"
            lines.append(
                f"    virtual 0x{KNOWN_B10_SHADOW_LOG_VADDR:012X}: {shown}"
            )
        else:
            lines.append(
                f"    virtual 0x{KNOWN_B10_SHADOW_LOG_VADDR:012X}: "
                "not found under this hypothesis"
            )

    lines.append("")
    lines.append("  Longest sequential physical/address runs")
    runs = sorted(
        result.sequential_regions,
        key=lambda region: region.sector_count,
        reverse=True,
    )[: args.top]
    if not runs:
        lines.append("    (none meeting the minimum run length)")
    else:
        lines.append(
            "    LBA range                 sectors  virtual range"
            "                     classification"
        )
        for region in runs:
            lines.append("    " + _region_line(region))

    return lines


def _disk_set_lines(scans):
    if len(scans) < 2:
        return []

    lines = [
        "Disk-set overview",
        "-----------------",
        f"Images:          {len(scans)}",
        f"Total sectors:   {sum(result.scanned_sectors for _, result in scans):,}",
    ]

    layout_keys = []
    for _, result in scans:
        best = result.best_layout
        if best is not None:
            layout_keys.append(
                (
                    best.layout.offset,
                    best.layout.width,
                    best.layout.byteorder,
                    best.layout.stride,
                )
            )
    if layout_keys and len(set(layout_keys)) == 1 and len(layout_keys) == len(scans):
        best = scans[0][1].best_layout
        lines.append(f"Header model:    AGREES across all images: {best.layout.name}")
    else:
        lines.append("Header model:    does not yet agree across all images")

    lines.extend(["", "Inferred virtual coverage from sequential runs"])
    for image, result in scans:
        runs = result.sequential_regions
        if not runs:
            lines.append(f"  {os.path.basename(image.path):<24} (no qualifying runs)")
            continue
        lo = min(
            region.address_start
            for region in runs
            if region.address_start is not None
        )
        hi = max(
            region.address_end for region in runs if region.address_end is not None
        )
        lines.append(
            f"  {os.path.basename(image.path):<24} "
            f"{_format_address(lo)} - {_format_address(hi)} "
            f"({len(runs):,} runs)"
        )
    return lines


def cmd_map(args):
    print("AS/400 CISC DASD structure map")
    print("==============================")
    print(
        "Interpretive fields below are explicitly marked as hypotheses until validated"
    )
    print("against a real B10 image and IBM header bit definitions.")
    print()

    scans = [_scan(path, args) for path in args.images]
    set_lines = _disk_set_lines(scans)
    if set_lines:
        print("\n".join(set_lines))
        print()

    for index, (image, result) in enumerate(scans):
        if index:
            print()
        print("\n".join(_map_lines_from_scan(image, result, args)))
    return 0


def cmd_regions(args):
    image, result = _scan(args.image, args)
    best = result.best_layout
    print(f"Disk: {image.path}")
    if best:
        print(
            f"Address hypothesis: {best.layout.name} "
            f"({best.confidence}, {best.ratio:.1%})"
        )
    else:
        print("Address hypothesis: none")
    print()
    print(
        "LBA range                 sectors  virtual range"
        "                     classification"
    )

    regions = result.regions
    if args.only_runs:
        regions = [region for region in regions if region.kind == "address-run"]
    if args.max_regions is not None:
        regions = regions[: args.max_regions]

    for region in regions:
        print(_region_line(region))
    return 0


def cmd_sector(args):
    image = _open(args.image)
    sector = image.read_sector(args.lba)
    print(f"Image:   {image.path}")
    print(f"LBA:     {sector.lba:,}")
    print(f"Offset:  {sector.offset:,} (0x{sector.offset:X})")
    print(f"Header:  {sector.header.hex(' ').upper()}")
    print()
    print("Candidate six-byte address interpretations (unvalidated):")
    seen = set()
    for layout in image.candidate_layouts():
        key = (layout.offset, layout.byteorder)
        if key in seen:
            continue
        seen.add(key)
        value = layout.decode(sector.header)
        print(
            f"  header[{layout.offset}:{layout.offset + 6}] "
            f"{layout.byteorder:<6} -> {_format_address(value)}"
        )
    print()
    print("Payload EBCDIC preview:")
    print(ebcdic_preview(sector.data, limit=args.preview))
    print()
    print("Payload hex:")
    print(format_hex(sector.data[: args.hex_bytes]))
    return 0


def cmd_scan(args):
    sections = [
        "AS/400 CISC DASD scan report",
        "============================",
        "",
    ]
    scans = [_scan(path, args) for path in args.images]
    set_lines = _disk_set_lines(scans)
    if set_lines:
        sections.extend(set_lines)
        sections.append("")

    for index, (image, result) in enumerate(scans):
        if index:
            sections.append("")
        sections.extend(_map_lines_from_scan(image, result, args))
        sections.append("")
        sections.append("  Region map")
        sections.append(
            "    LBA range                 sectors  virtual range"
            "                     classification"
        )
        for region in result.regions[: args.max_regions]:
            sections.append("    " + _region_line(region))
        if len(result.regions) > args.max_regions:
            sections.append(
                f"    ... {len(result.regions) - args.max_regions:,} "
                "additional regions omitted"
            )

    report = "\n".join(sections) + "\n"
    if args.report:
        Path(args.report).expanduser().write_text(report, encoding="utf-8")
        print(f"Wrote {args.report}")
    else:
        print(report, end="")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="as400-dasd",
        description=(
            "Read-only structure explorer for raw 520-byte CISC AS/400 DASD images"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    info = sub.add_parser("info", help="show image geometry without a full scan")
    info.add_argument("images", nargs="+")
    info.set_defaults(func=cmd_info)

    def add_scan_options(p):
        p.add_argument(
            "--limit",
            type=int,
            help="scan only the first N sectors (development/testing)",
        )
        p.add_argument(
            "--min-run",
            type=int,
            default=4,
            help="minimum consecutive sectors for an address run (default: 4)",
        )

    map_p = sub.add_parser(
        "map", help="summarize physical and inferred address structure"
    )
    map_p.add_argument("images", nargs="+")
    add_scan_options(map_p)
    map_p.add_argument(
        "--top", type=int, default=12, help="show N longest address runs"
    )
    map_p.set_defaults(func=cmd_map)

    regions = sub.add_parser("regions", help="show physical LBA regions")
    regions.add_argument("image")
    add_scan_options(regions)
    regions.add_argument(
        "--only-runs",
        action="store_true",
        help="show only sequential address runs",
    )
    regions.add_argument("--max-regions", type=int, default=None)
    regions.set_defaults(func=cmd_regions)

    sector = sub.add_parser("sector", help="inspect one raw 520-byte sector")
    sector.add_argument("image")
    sector.add_argument("lba", type=int)
    sector.add_argument(
        "--preview", type=int, default=128, help="EBCDIC preview bytes"
    )
    sector.add_argument(
        "--hex-bytes", type=int, default=256, help="payload bytes to hex dump"
    )
    sector.set_defaults(func=cmd_sector)

    scan = sub.add_parser("scan", help="produce a detailed structure report")
    scan.add_argument("images", nargs="+")
    add_scan_options(scan)
    scan.add_argument("--top", type=int, default=12)
    scan.add_argument("--max-regions", type=int, default=250)
    scan.add_argument("--report", help="write report to a text file")
    scan.set_defaults(func=cmd_scan)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError) as exc:
        print(f"as400-dasd: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
