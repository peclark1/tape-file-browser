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
    if extent.virtual_address is None:
        virtual = "-"
    else:
        virtual = f"{_addr(extent.virtual_address)}-{_addr(extent.virtual_end)}"
    return (
        f"{lbas:<23} {extent.pages:>8,}  "
        f"{virtual:<33} {extent.kind}"
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


def _analysis_lines(image, result, *, top=12):
    lines = [
        f"Disk: {os.path.basename(image.path)}",
        f"  sectors:             {result.sector_count:,}",
        (
            f"  zero headers:        {result.zero_headers:,} "
            f"({_pct(result.zero_headers, result.sector_count)})"
        ),
        (
            f"  FF headers:          {result.ff_headers:,} "
            f"({_pct(result.ff_headers, result.sector_count)})"
        ),
        (
            f"  other headers:       {result.other_headers:,} "
            f"({_pct(result.other_headers, result.sector_count)})"
        ),
    ]
    if result.zero_payloads is not None:
        lines.append(
            f"  zero payloads:       {result.zero_payloads:,} "
            f"({_pct(result.zero_payloads, result.sector_count)})"
        )
    lines.append(f"  reserved byte != 0:  {result.reserved_nonzero_headers:,}")
    lines.append("")
    lines.append("  Directory-recovery structure")

    if result.origin is None:
        lines.append("    relative record zero: not detected")
        lines.append(
            "    The preassigned large-free-space delimiter was not found."
        )
        return lines

    origin = result.origin
    lines.extend(
        [
            (
                f"    reserved prefix:      LBA 0-{origin.lba - 1:,} "
                f"({origin.lba:,} sectors)"
            ),
            (
                f"    relative record zero: LBA {origin.lba:,} "
                f"({origin.confidence})"
            ),
            (
                f"    delimiter header:     "
                f"{origin.delimiter_header.hex(' ').upper()}"
            ),
            f"    delimiter size:       {origin.extent_pages:,} pages",
            (
                f"    delimiter locations:  "
                f"{len(origin.delimiter_occurrences):,}"
            ),
            (
                f"    supporting large extents: "
                f"{origin.supporting_large_extents:,}"
            ),
            (
                f"    explicit large-free:   "
                f"{len(result.free_delimiter_extents):,} extents / "
                f"{result.explicit_free_pages:,} pages"
            ),
            (
                f"    permanent candidates:  "
                f"{len(result.permanent_candidates):,} extents / "
                f"{result.permanent_candidate_pages:,} pages"
            ),
            (
                f"    reclaimable regions:   "
                f"{len(result.reclaimable_regions):,} / "
                f"{result.reclaimable_pages:,} pages"
            ),
            (
                f"    structured coverage:   "
                f"{result.structured_pages:,}/{result.managed_sectors:,} "
                f"({result.structured_ratio:.1%})"
            ),
        ]
    )

    lines.extend(
        [
            "",
            (
                "  'Reclaimable' follows IBM directory-recovery terminology: "
                "zeroed,"
            ),
            (
                "  temporary, stale, or permanent headers on the wrong "
                "power-of-two"
            ),
            (
                "  boundary are returned to free space during recovery. It is "
                "not a claim"
            ),
            "  that every such sector was unused before recovery.",
        ]
    )

    lines.extend(["", "  Permanent-candidate extent-size distribution"])
    hist = result.extent_size_histogram
    if hist:
        for pages in sorted(hist):
            lines.append(
                f"    {pages:>6,} pages : {hist[pages]:>8,} extents"
            )
    else:
        lines.append("    (none)")

    lines.extend(["", "  Load-source validation anchor"])
    resolved = result.resolve_virtual(KNOWN_B10_SHADOW_LOG_VADDR)
    if resolved is None:
        lines.append(
            f"    {_addr(KNOWN_B10_SHADOW_LOG_VADDR)}: "
            "not present in reconstructed permanent candidates"
        )
    else:
        offset_pages = (
            KNOWN_B10_SHADOW_LOG_VADDR - resolved.virtual_address
        ) // PAGE_SIZE
        anchor_lba = resolved.start_lba + offset_pages
        lines.append(
            f"    {_addr(KNOWN_B10_SHADOW_LOG_VADDR)}: "
            f"LBA {anchor_lba:,} inside {resolved.pages:,}-page extent"
        )
        if isinstance(image, DASDImage):
            first_64k = image.count_nonzero_payloads(anchor_lba, 128)
            next_64k = image.count_nonzero_payloads(anchor_lba + 128, 128)
            lines.append(
                f"    first 64 KiB:        {first_64k}/128 pages contain data"
            )
            if resolved.pages >= 256:
                lines.append(
                    f"    following 64 KiB:    {next_64k}/128 pages contain data"
                )

    lines.extend(["", "  Largest candidate virtual chains"])
    chains = sorted(
        result.virtual_chains,
        key=lambda chain: chain.pages,
        reverse=True,
    )[:top]
    if not chains:
        lines.append("    (none)")
    else:
        for chain in chains:
            lines.append(
                f"    {_addr(chain.virtual_address)}-"
                f"{_addr(chain.virtual_end)}  "
                f"{chain.pages:>7,} pages  "
                f"{len(chain.extents):>3} extents"
            )

    lines.extend(["", "  Largest physical permanent candidates"])
    extents = sorted(
        result.permanent_candidates,
        key=lambda item: item.pages,
        reverse=True,
    )[:top]
    if not extents:
        lines.append("    (none)")
    else:
        for extent in extents:
            lines.append("    " + _extent_line(extent))
    return lines


def cmd_map(args):
    print("AS/400 CISC DASD structure map")
    print("==============================")
    print(
        "The map follows IBM's documented directory-recovery rules. "
        "Unknown indicator bits remain unlabeled."
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

    entries = [
        (extent.start_lba, "extent", extent)
        for extent in (
            result.free_delimiter_extents + result.permanent_candidates
        )
    ]
    if not args.no_reclaimable:
        entries += [
            (region.start_lba, "reclaimable", region)
            for region in result.reclaimable_regions
        ]
    entries.sort(key=lambda item: item[0])

    print(f"Disk: {image.path}")
    print(
        f"Relative record zero: LBA {result.origin.lba:,} "
        f"({result.origin.confidence})"
    )
    print()
    print(
        "LBA range                 pages  virtual range"
        "                     classification"
    )

    if args.max_regions is not None:
        entries = entries[: args.max_regions]

    for _, kind, item in entries:
        if kind == "extent":
            print(_extent_line(item))
        else:
            lbas = f"{item.start_lba:,}-{item.end_lba:,}"
            print(
                f"{lbas:<23} {item.sector_count:>8,}  "
                f"{'-':<33} reclaimable-by-recovery"
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
    print(
        f"  virtual-page prefix:      "
        f"0x{header.virtual_page_prefix:010X}"
    )
    print(f"  virtual byte address:     {_addr(header.virtual_address)}")
    print(f"  512-byte page aligned:    {header.page_aligned}")
    print(f"  indicators byte:          0x{header.raw[5]:02X}")
    print(f"  extent order:             {header.extent_order}")
    print(f"  extent size:              {header.extent_pages:,} pages")
    print(
        f"  other indicator bits:     0x{header.indicator_flags:02X} "
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
        sections.extend(["", "  Physical recovery map"])

        combined = [
            (extent.start_lba, "extent", extent)
            for extent in (
                result.free_delimiter_extents + result.permanent_candidates
            )
        ]
        combined += [
            (region.start_lba, "reclaimable", region)
            for region in result.reclaimable_regions
        ]
        combined.sort(key=lambda item: item[0])

        for _, kind, item in combined[: args.max_regions]:
            if kind == "extent":
                sections.append("    " + _extent_line(item))
            else:
                lbas = f"{item.start_lba:,}-{item.end_lba:,}"
                sections.append(
                    f"    {lbas:<23} {item.sector_count:>8,}  "
                    f"{'-':<33} reclaimable-by-recovery"
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
        "map", help="reconstruct high-level storage/recovery structure"
    )
    map_p.add_argument("images", nargs="+")
    map_p.add_argument("--top", type=int, default=12)
    map_p.set_defaults(func=cmd_map)

    regions = sub.add_parser(
        "regions", help="show physical extent/reclaimable regions"
    )
    regions.add_argument("image")
    regions.add_argument(
        "--no-reclaimable",
        action="store_true",
        help="show only explicit free and permanent candidate extents",
    )
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
