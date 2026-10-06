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
    Extent,
    ebcdic_preview,
    format_hex,
)


def _open(path: str) -> DASDImage:
    return DASDImage(str(Path(path).expanduser()))


def _pct(part: int, whole: int) -> str:
    return "0.0%" if not whole else f"{100.0 * part / whole:.1f}%"


def _addr(value: int | None) -> str:
    return "-" if value is None else f"0x{value:012X}"


def _extent_line(extent: Extent) -> str:
    lbas = f"{extent.start_lba:,}-{extent.end_lba:,}"
    virtual = "-"
    if extent.virtual_address is not None:
        virtual = f"{_addr(extent.virtual_address)}-{_addr(extent.virtual_end)}"
    return f"{lbas:<23} {extent.pages:>8,}  {virtual:<33} {extent.kind}"


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


def _analysis_lines(image, result, *, top=12):
    lines = [
        f"Disk: {os.path.basename(image.path)}",
        f"  sectors:             {result.sector_count:,}",
        f"  zero headers:        {result.zero_headers:,} ({_pct(result.zero_headers, result.sector_count)})",
        f"  FF headers:          {result.ff_headers:,} ({_pct(result.ff_headers, result.sector_count)})",
        f"  other headers:       {result.other_headers:,} ({_pct(result.other_headers, result.sector_count)})",
    ]
    if result.zero_payloads is not None:
        lines.append(
            f"  zero payloads:       {result.zero_payloads:,} ({_pct(result.zero_payloads, result.sector_count)})"
        )
    lines.append(f"  reserved byte != 0:  {result.reserved_nonzero_headers:,}")
    lines.append("")
    lines.append("  Storage-management structure")

    if result.origin is None:
        lines.append("    managed origin:       not detected")
        return lines

    origin = result.origin
    lines.extend(
        [
            f"    reserved prefix:      LBA 0-{origin.lba - 1:,} ({origin.lba:,} sectors)",
            f"    managed origin:       LBA {origin.lba:,} ({origin.confidence})",
            f"    delimiter header:     {origin.header.hex(' ').upper()}",
            f"    delimiter extent:     {origin.extent_pages:,} pages",
            f"    delimiter repeats:    {origin.repeats:,}",
            f"    free extents:         {len(result.free_extents):,} / {result.free_pages:,} pages",
            f"    allocated candidates: {len(result.allocated_extents):,} / {result.allocated_pages:,} pages",
            f"    unresolved regions:   {len(result.gaps):,} / {result.unresolved_pages:,} pages",
            f"    recognized coverage:  {result.recognized_pages:,}/{result.managed_sectors:,} ({result.recognized_ratio:.1%})",
        ]
    )

    lines.extend(["", "  Allocated extent-size distribution"])
    hist = result.extent_size_histogram
    if hist:
        for pages in sorted(hist):
            lines.append(f"    {pages:>6,} pages : {hist[pages]:>8,} extents")
    else:
        lines.append("    (none)")

    lines.extend(["", "  B10 load-source validation anchor"])
    resolved = result.resolve_virtual(KNOWN_B10_SHADOW_LOG_VADDR)
    if resolved is None:
        lines.append(
            f"    {_addr(KNOWN_B10_SHADOW_LOG_VADDR)}: not present in reconstructed extents"
        )
    else:
        offset_pages = (
            KNOWN_B10_SHADOW_LOG_VADDR - resolved.virtual_address
        ) // PAGE_SIZE
        lines.append(
            f"    {_addr(KNOWN_B10_SHADOW_LOG_VADDR)}: LBA {resolved.start_lba + offset_pages:,} "
            f"inside {resolved.pages:,}-page extent"
        )

    lines.extend(["", "  Largest candidate virtual chains"])
    chains = sorted(
        result.virtual_chains, key=lambda chain: chain.pages, reverse=True
    )[:top]
    for chain in chains:
        lines.append(
            f"    {_addr(chain.virtual_address)}-{_addr(chain.virtual_end)}  "
            f"{chain.pages:>7,} pages  {len(chain.extents):>3} extents"
        )
    if not chains:
        lines.append("    (none)")

    lines.extend(["", "  Largest physical allocated extents"])
    for extent in sorted(
        result.allocated_extents, key=lambda item: item.pages, reverse=True
    )[:top]:
        lines.append("    " + _extent_line(extent))
    return lines


def cmd_map(args):
    print("AS/400 CISC DASD structure map")
    print("==============================")
    print(
        "Extent/address decoding is evidence-backed by the real B10 image; "
        "unknown flag bits remain unlabeled."
    )
    print()

    for index, path in enumerate(args.images):
        if index:
            print()
        image = _open(path)
        result = image.scan()
        print("\n".join(_analysis_lines(image, result, top=args.top)))
    return 0


def cmd_regions(args):
    image = _open(args.image)
    result = image.scan()
    if result.origin is None:
        print("No storage-management origin detected.")
        return 1

    entries = [*result.free_extents, *result.allocated_extents]
    entries.sort(key=lambda extent: extent.start_lba)

    print(f"Disk: {image.path}")
    print(f"Managed origin: LBA {result.origin.lba:,} ({result.origin.confidence})")
    print()
    print(
        "LBA range                 pages  virtual range"
        "                     classification"
    )

    combined = [(extent.start_lba, "extent", extent) for extent in entries]
    if not args.no_gaps:
        combined += [(gap.start_lba, "gap", gap) for gap in result.gaps]
    combined.sort(key=lambda item: item[0])
    if args.max_regions is not None:
        combined = combined[: args.max_regions]

    for _, kind, item in combined:
        if kind == "extent":
            print(_extent_line(item))
        else:
            lbas = f"{item.start_lba:,}-{item.end_lba:,}"
            print(
                f"{lbas:<23} {item.sector_count:>8,}  "
                f"{'-':<33} unresolved"
            )
    return 0


def cmd_sector(args):
    image = _open(args.image)
    sector = image.read_sector(args.lba)
    header = sector.header

    print(f"Image:   {image.path}")
    print(f"LBA:     {sector.lba:,}")
    print(f"Offset:  {sector.offset:,} (0x{sector.offset:X})")
    print(f"Header:  {header.raw.hex(' ').upper()}")
    print()
    print("Decoded storage header:")
    print(f"  zero header:              {header.is_zero}")
    print(f"  virtual page number:      0x{header.virtual_page_number:010X}")
    print(f"  virtual byte address:     {_addr(header.virtual_address)}")
    print(
        f"  page-word low flag:       {header.page_word_low_flag} "
        "(semantics TBD)"
    )
    print(f"  extent order:             {header.extent_order}")
    print(f"  extent size:              {header.extent_pages:,} pages")
    print(
        f"  extent high flag bits:    0x{header.extent_flag_bits:02X} "
        "(semantics TBD)"
    )
    print(f"  reserved byte:            0x{header.reserved_byte:02X}")
    print(f"  pointer/control byte:     0x{header.pointer_control:02X}")
    print(f"  pointer field C (low 5):  {header.pointer_field_c}")
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
    for index, path in enumerate(args.images):
        if index:
            sections.append("")
        image = _open(path)
        result = image.scan()
        sections.extend(_analysis_lines(image, result, top=args.top))
        sections.extend(["", "  Physical region map"])

        combined = [
            (extent.start_lba, "extent", extent)
            for extent in result.free_extents + result.allocated_extents
        ]
        combined += [(gap.start_lba, "gap", gap) for gap in result.gaps]
        combined.sort(key=lambda item: item[0])

        for _, kind, item in combined[: args.max_regions]:
            if kind == "extent":
                sections.append("    " + _extent_line(item))
            else:
                lbas = f"{item.start_lba:,}-{item.end_lba:,}"
                sections.append(
                    f"    {lbas:<23} {item.sector_count:>8,}  "
                    f"{'-':<33} unresolved"
                )

        if len(combined) > args.max_regions:
            sections.append(
                f"    ... {len(combined) - args.max_regions:,} "
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

    map_p = sub.add_parser(
        "map", help="reconstruct high-level storage/extent structure"
    )
    map_p.add_argument("images", nargs="+")
    map_p.add_argument("--top", type=int, default=12)
    map_p.set_defaults(func=cmd_map)

    regions = sub.add_parser(
        "regions", help="show physical extent/gap regions"
    )
    regions.add_argument("image")
    regions.add_argument("--no-gaps", action="store_true")
    regions.add_argument("--max-regions", type=int, default=None)
    regions.set_defaults(func=cmd_regions)

    sector = sub.add_parser("sector", help="inspect one raw 520-byte sector")
    sector.add_argument("image")
    sector.add_argument("lba", type=int)
    sector.add_argument("--preview", type=int, default=128)
    sector.add_argument("--hex-bytes", type=int, default=256)
    sector.set_defaults(func=cmd_sector)

    scan = sub.add_parser("scan", help="produce a detailed structure report")
    scan.add_argument("images", nargs="+")
    scan.add_argument("--top", type=int, default=12)
    scan.add_argument("--max-regions", type=int, default=500)
    scan.add_argument("--report")
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
