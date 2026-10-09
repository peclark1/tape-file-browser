#!/usr/bin/env python3

"""Command-line DASD structure explorer for CISC AS/400 disk images."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
import re
import sys
from pathlib import Path

from as400_dasd import (
    ASDEEntryEvidence,
    CONTEXT_MACHINE_INDEX_PAGE_SIZE,
    CONTEXT_MACHINE_INDEX_ROOT_OFFSET,
    EPA_MIN_SIZE,
    HEADER_SIZE,
    KNOWN_B10_SHADOW_LOG_VADDR,
    PAGE_SIZE,
    QAOSSS14AnchorRecord,
    QAOSSS14_V2_RECORD_LENGTH,
    SECTOR_SIZE,
    SEGMENT_HEADER_SIZE,
    ContextIndexEntry,
    DASDImage,
    DENT_V2_DELETED,
    DENT_V2_LIVE,
    Extent,
    InternalAddress,
    MachineIndexPageHeader,
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
        segments = image.recover_segments(result)
        inventory = image.recover_objects(result, segments)
        lines = _analysis_lines(image, result, top=args.top)
        lines.extend(_second_pass_lines(segments, inventory))
        print("\n".join(lines))
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



_STORAGE_SYMBOLS = ("#SMSMVT", "#SMSMVTN", "#SMSMVTI", "#SMACDIR", "#SMMSIT", "#SMDR2")


def _scan_storage_symbol_literals(
    image,
    symbols,
    *,
    start_lba=0,
    sectors=None,
    limit=50,
    substring=False,
):
    """Count payload CP037 hits; default matches a padded eight-byte name.

    This prevents a seven-character query such as #SMSMVT from accidentally
    counting the different eight-character name #SMSMVTN. No symbol match
    alone establishes a VMC module, loaded SMVT or directory root.
    """

    if start_lba < 0 or start_lba >= image.sector_count:
        raise ValueError("start LBA is outside the image")
    if sectors is not None and sectors < 1:
        raise ValueError("--sectors must be positive")
    if limit < 0:
        raise ValueError("--limit must be non-negative")

    patterns = {}
    for symbol in dict.fromkeys(symbols):
        max_length = PAGE_SIZE if substring else 8
        if not symbol or len(symbol) > max_length:
            raise ValueError(
                f"symbols must be 1..{max_length} characters "
                f"({'substring' if substring else 'eight-byte name'} mode)"
            )
        try:
            encoded = (symbol if substring else symbol.ljust(8)).encode("cp037")
            patterns[symbol] = encoded
        except UnicodeEncodeError as exc:
            raise ValueError(f"symbol cannot be EBCDIC CP037 encoded: {symbol}") from exc
    if not patterns:
        raise ValueError("no search symbols supplied")

    end_lba = image.sector_count
    if sectors is not None:
        end_lba = min(end_lba, start_lba + sectors)

    totals = {symbol: 0 for symbol in patterns}
    hits = []
    with open(image.path, "rb") as handle:
        handle.seek(start_lba * SECTOR_SIZE)
        for lba in range(start_lba, end_lba):
            raw = handle.read(SECTOR_SIZE)
            if len(raw) != SECTOR_SIZE:
                raise ValueError(f"short sector read at LBA {lba}")
            payload = raw[HEADER_SIZE:]
            for symbol, pattern in patterns.items():
                start = 0
                while True:
                    offset = payload.find(pattern, start)
                    if offset < 0:
                        break
                    totals[symbol] += 1
                    if not limit or len(hits) < limit:
                        preceding = payload[offset - 4:offset] if offset >= 4 else b""
                        hits.append((symbol, lba, offset, raw[:HEADER_SIZE], preceding))
                    start = offset + 1
    return totals, tuple(hits), end_lba


def cmd_storage_labels(args):
    """Report literal storage-management symbol evidence in 512-byte payloads."""

    image = _open(args.image)
    symbols = args.symbols or _STORAGE_SYMBOLS
    totals, hits, end_lba = _scan_storage_symbol_literals(
        image,
        symbols,
        start_lba=args.start_lba,
        sectors=args.sectors,
        limit=args.limit,
        substring=args.substring,
    )

    print(f"Image:       {image.path}")
    print(f"Sector span: {args.start_lba:,}..{end_lba - 1:,} (physical LBAs)")
    mode = ("substring" if args.substring else "space-padded eight-byte name")
    print(f"Encoding:    literal EBCDIC CP037 {mode}, 512-byte payloads only")
    print("Occurrences:")
    for symbol, total in totals.items():
        print(f"  {symbol}: {total:,}")
    print()
    print("First matches:")
    for symbol, lba, offset, header, preceding in hits:
        prefix_text = preceding.hex(' ').upper() if preceding else "(start of payload)"
        print(
            f"  {symbol:<12} LBA {lba:>9,} payload +0x{offset:03X} "
            f"preceding4 {prefix_text}  header {header.hex(' ').upper()}"
        )
    if args.limit and sum(totals.values()) > len(hits):
        print(f"  ... {sum(totals.values()) - len(hits):,} additional hits not listed")
    if not hits:
        print("  none")
    print()
    print(
        "These are literal text occurrences, NOT proven SMVT or storage-"
        "directory locations. No ASDE mappings are inferred."
    )
    return 0



def _resolve_extent_relative_address(image, extent_start_lba, address):
    """Resolve a candidate six-byte VA using an explicitly chosen extent.

    The caller, not a symbolic name match, must identify the extent start.
    The sector header independently supplies its base VA and extent order.
    No resident directory or module semantics are inferred.
    """

    start = image.read_sector(extent_start_lba)
    header = start.header
    if header.is_zero or header.is_ff:
        raise ValueError("chosen extent has a zero/FF storage header")
    if not header.page_aligned:
        raise ValueError("chosen extent header is not 512-byte aligned")
    pages = header.extent_pages
    if pages > image.sector_count - extent_start_lba:
        raise ValueError("extent described by header crosses image end")
    base = header.virtual_address
    if address < base or address >= base + pages * PAGE_SIZE:
        raise ValueError(
            f"candidate VA 0x{address:012X} is outside chosen extent "
            f"0x{base:012X}..0x{base + pages * PAGE_SIZE - 1:012X}"
        )
    page_index, offset = divmod(address - base, PAGE_SIZE)
    return extent_start_lba + page_index, offset


def cmd_virtual_xref(args):
    """Check an explicit six-byte candidate virtual pointer against an extent."""

    image = _open(args.image)
    start = image.read_sector(args.extent_start_lba)
    pages = start.header.extent_pages
    if not (
        args.extent_start_lba
        <= args.source_lba
        < args.extent_start_lba + pages
    ):
        raise ValueError("source sector is not in the selected extent")
    if args.offset < 0 or args.offset + 6 > PAGE_SIZE:
        raise ValueError("six-byte candidate must fit inside source payload")

    source = image.read_sector(args.source_lba)
    pointer_raw = source.data[args.offset:args.offset + 6]
    candidate_va = int.from_bytes(pointer_raw, "big")
    target_lba, target_offset = _resolve_extent_relative_address(
        image, args.extent_start_lba, candidate_va
    )
    target = image.read_sector(target_lba)
    source_va = (
        start.header.virtual_address
        + (args.source_lba - args.extent_start_lba) * PAGE_SIZE
    )

    print(f"Image:              {image.path}")
    print(f"Chosen extent LBA:  {args.extent_start_lba:,}")
    print(f"Header base VA:     0x{start.header.virtual_address:012X}")
    print(f"Header extent size: {pages:,} 512-byte pages")
    print(
        f"Source:             LBA {args.source_lba:,}, "
        f"derived page VA 0x{source_va:012X}, payload +0x{args.offset:03X}"
    )
    print(f"Candidate raw:      {pointer_raw.hex(' ').upper()}")
    print(f"Candidate VA:       0x{candidate_va:012X}")
    print(f"Resolved target:    LBA {target_lba:,}, payload +0x{target_offset:03X}")
    print(f"Target header:      {target.header.raw.hex(' ').upper()}")
    print(
        "Target bytes:       "
        + target.data[target_offset:target_offset + args.preview].hex(" ").upper()
    )
    print(
        "This validates only an extent-relative address match. "
        "The candidate pointer field, module semantics, SMVT and "
        "storage-directory location remain unverified."
    )
    return 0



def _scan_extent_virtual_references(
    image,
    extent_start_lba,
    *,
    first_source_lba=None,
    sectors=None,
    alignment=2,
    example_limit=12,
):
    """Count candidate in-extent six-byte VAs at aligned payload offsets.

    This is a structural correlation probe, *not* a pointer or ASDE decoder:
    any matching six-byte number is counted, including potentially coincidental
    bit patterns. Physical extent start is always caller-selected.
    """
    if alignment not in (2, 4, 8):
        raise ValueError("alignment must be 2, 4, or 8")
    if example_limit < 0:
        raise ValueError("example limit must be non-negative")
    if sectors is not None and sectors < 1:
        raise ValueError("sectors must be positive")
    header = image.read_sector(extent_start_lba).header
    if header.is_zero or header.is_ff:
        raise ValueError("chosen extent has a zero/FF storage header")
    if not header.page_aligned:
        raise ValueError("extent header virtual address is not page-aligned")
    pages = header.extent_pages
    if pages > image.sector_count - extent_start_lba:
        raise ValueError("selected extent extends beyond the image")
    first_source_lba = (
        extent_start_lba if first_source_lba is None else first_source_lba
    )
    stop_lba = extent_start_lba + pages
    if not (extent_start_lba <= first_source_lba < stop_lba):
        raise ValueError("source-start LBA lies outside chosen extent")
    if sectors is not None:
        stop_lba = min(stop_lba, first_source_lba + sectors)

    virtual_start = header.virtual_address
    virtual_end = virtual_start + pages * PAGE_SIZE
    source_offsets = Counter()
    pattern_counts = Counter()
    target_distances = Counter()
    target_record_prefix_counts = Counter()
    candidate_record_names = Counter()
    examples = []
    total_matches = 0
    with open(image.path, "rb") as handle, open(image.path, "rb") as target_handle:
        handle.seek(first_source_lba * SECTOR_SIZE)
        for lba in range(first_source_lba, stop_lba):
            raw = handle.read(SECTOR_SIZE)
            if len(raw) != SECTOR_SIZE:
                raise ValueError(f"short sector read at LBA {lba}")
            payload = raw[HEADER_SIZE:]
            for offset in range(0, PAGE_SIZE - 5, alignment):
                value = int.from_bytes(payload[offset:offset + 6], "big")
                if not (virtual_start <= value < virtual_end):
                    continue
                target_index, target_offset = divmod(
                    value - virtual_start, PAGE_SIZE
                )
                target_lba = extent_start_lba + target_index
                delta = target_lba - lba
                total_matches += 1
                source_offsets[offset] += 1
                pattern_key = (offset, delta, target_offset)
                pattern_counts[pattern_key] += 1
                target_distances[delta] += 1
                # A separately read physical target provides stronger *shape*
                # evidence than range matching. 02 00 00 00 7B is an observed
                # module-name record prefix, not a validated directory header.
                if target_offset <= PAGE_SIZE - 5:
                    target_handle.seek(
                        target_lba * SECTOR_SIZE + HEADER_SIZE + target_offset
                    )
                    read_length = min(12, PAGE_SIZE - target_offset)
                    target_prefix = target_handle.read(read_length)
                    if len(target_prefix) != read_length:
                        raise ValueError(f"short target read at LBA {target_lba}")
                    if target_prefix[:5] == bytes((2, 0, 0, 0, 0x7B)):
                        target_record_prefix_counts[pattern_key] += 1
                        if len(target_prefix) == 12:
                            name = target_prefix[4:12].decode(
                                "cp037", errors="replace"
                            )
                            if all(ch.isprintable() for ch in name):
                                candidate_record_names[name] += 1
                if len(examples) < example_limit:
                    examples.append((lba, offset, target_lba, target_offset))

    return {
        "extent_start_lba": extent_start_lba,
        "extent_pages": pages,
        "virtual_start": virtual_start,
        "first_source_lba": first_source_lba,
        "stop_lba": stop_lba,
        "total_matches": total_matches,
        "source_offsets": source_offsets,
        "patterns": pattern_counts,
        "target_record_prefix_counts": target_record_prefix_counts,
        "candidate_record_names": candidate_record_names,
        "distances": target_distances,
        "examples": tuple(examples),
    }


def cmd_virtual_xref_map(args):
    """Print bounded candidate VA correlations for one caller-selected extent."""

    if args.top < 0 or args.names < 0:
        raise ValueError("--top and --names must be non-negative")
    image = _open(args.image)
    result = _scan_extent_virtual_references(
        image,
        args.extent_start_lba,
        first_source_lba=args.source_start_lba,
        sectors=args.sectors,
        alignment=args.alignment,
        example_limit=args.examples,
    )
    print(f"Image:           {image.path}")
    print(f"Extent start:    physical LBA {result['extent_start_lba']:,}")
    print(f"Extent pages:    {result['extent_pages']:,}")
    print(f"Extent base VA:  0x{result['virtual_start']:012X}")
    print(
        f"Source scan:     LBA {result['first_source_lba']:,}"
        f"..{result['stop_lba'] - 1:,}, alignment {args.alignment}"
    )
    print(f"Candidate values within extent: {result['total_matches']:,}")
    print(
        "Top (source payload offset, target page delta, target offset): "
        "count; of which targets begin with raw 02 00 00 00 7B"
    )
    for (offset, delta, target_offset), count in result["patterns"].most_common(
        args.top
    ):
        key = (offset, delta, target_offset)
        markers = result["target_record_prefix_counts"][key]
        print(
            f"  +0x{offset:03X} -> page {delta:+d}, +0x{target_offset:03X}"
            f"    {count:,} occurrences; {markers:,} target prefix matches"
        )
    print("Top printable CP037 eight-byte names following target record markers:")
    for name, count in result["candidate_record_names"].most_common(args.names):
        print(f"  {name!r}: {count:,} target references")
    print("First candidates:")
    for src_lba, src_offset, target_lba, target_offset in result["examples"]:
        print(
            f"  LBA {src_lba:,} +0x{src_offset:03X}"
            f" -> LBA {target_lba:,} +0x{target_offset:03X}"
        )
    print(
        "Matches are numerical six-byte VA candidates, not verified pointer"
        " fields; no SMVT, index-root, or ASDE semantics are inferred."
    )
    return 0


def cmd_asde_probe(args):
    """Inspect an explicit raw ASDE candidate; never discover by guessing."""

    image = _open(args.image)
    if args.offset < 0 or args.offset >= PAGE_SIZE:
        raise ValueError(
            f"ASDE payload offset must be within 0..{PAGE_SIZE - 1}"
        )
    if args.length <= 0 or args.offset + args.length > PAGE_SIZE:
        raise ValueError(
            "ASDE candidate must fit entirely within one 512-byte payload; "
            "a cross-page candidate is not yet supported"
        )

    sector = image.read_sector(args.lba)
    raw = sector.data[args.offset:args.offset + args.length]
    candidate = ASDEEntryEvidence(raw)

    print(f"Image:   {image.path}")
    print(f"LBA:     {args.lba:,} (physical image LBA)")
    print(f"Offset:  payload +0x{args.offset:X}")
    print(f"Length:  {len(candidate.raw)} bytes")
    print(f"Raw:     {candidate.raw.hex(' ').upper()}")
    print()
    print(
        "Tentative System/38 chapter-7 ASDE length partition "
        "(NOT a validated directory entry):"
    )
    print(f"  first six bytes: {candidate.prefix_raw.hex(' ').upper()}")
    print(f"  following 5-byte groups: {candidate.extent_count}")
    for index, piece in enumerate(candidate.descriptors_raw, 1):
        print(f"  raw descriptor {index}: {piece.hex(' ').upper()}")
    print()
    print(
        "No prefix fields, extent address/size, unit, or index location "
        "have been decoded. IBM's chapter-8 entry lengths differ from "
        "chapter 7 (possibly a scan/OCR artifact); use only with independently located directory evidence."
    )
    return 0


def _recover_all(image):
    scan = image.scan()
    segments = image.recover_segments(scan)
    inventory = image.recover_objects(scan, segments)
    return scan, segments, inventory


def _second_pass_lines(segments, inventory):
    primary_keys = {
        (
            segment.header.owner.extender,
            segment.virtual_address,
        )
        for segment in segments.primary_segments
    }
    resolved_secondary = sum(
        1
        for segment in segments.secondary_segments
        if segment.owner_key in primary_keys
    )
    return [
        "",
        "  Second recovery pass / object discovery",
        (
            f"    recovered segments:     "
            f"{len(segments.segments):,}"
        ),
        (
            f"    primary segments:       "
            f"{len(segments.primary_segments):,}"
        ),
        (
            f"    secondary segments:     "
            f"{len(segments.secondary_segments):,}"
        ),
        (
            f"    secondary owner links:  "
            f"{resolved_secondary:,}/"
            f"{len(segments.secondary_segments):,} resolved on this image"
        ),
        (
            f"    unrecovered candidates: "
            f"{len(segments.unrecovered_candidates):,}"
        ),
        f"    EPA objects:            {len(inventory.objects):,}",
        f"    permanent contexts:     {len(inventory.libraries):,}",
        (
            f"    objects assigned to a known context: "
            f"{len(inventory.assigned_objects):,}"
        ),
    ]


def _parse_type_filter(value):
    if value is None:
        return None
    cleaned = value.upper().replace("0X", "").replace("/", "").replace(":", "")
    if len(cleaned) == 2:
        return int(cleaned, 16), None
    if len(cleaned) == 4:
        return int(cleaned[:2], 16), int(cleaned[2:], 16)
    raise ValueError(
        "type must be two hex digits (for example 19) or type/subtype "
        "(for example 19/01)"
    )


def _object_matches(obj, args):
    if getattr(args, "library", None):
        if (obj.library_name or "").upper() != args.library.upper():
            return False
    if getattr(args, "name", None):
        if args.name.upper() not in obj.name.upper():
            return False
    type_filter = _parse_type_filter(getattr(args, "type", None))
    if type_filter is not None:
        obj_type, obj_subtype = type_filter
        if obj.object_type != obj_type:
            return False
        if obj_subtype is not None and obj.object_subtype != obj_subtype:
            return False
    return True


def _object_line(obj):
    library = obj.library_name or "-"
    hint = obj.external_type_hint or "-"
    return (
        f"{library:<12} {obj.type_code:<5} {hint:<8} "
        f"{obj.name:<30.30} "
        f"{obj.segment.virtual_address:012X} "
        f"{obj.segment.start_lba:>9,} "
        f"{obj.segment.pages:>6,}"
    )


def cmd_segments(args):
    image = _open(args.image)
    scan = image.scan()
    recovered = image.recover_segments(scan)

    segments = recovered.segments
    if args.primary_only:
        segments = recovered.primary_segments
    if args.type is not None:
        wanted = int(args.type.replace("0x", ""), 16)
        segments = [
            segment
            for segment in segments
            if segment.header.segment_type == wanted
        ]

    segments = sorted(
        segments,
        key=lambda segment: (
            segment.virtual_address,
            segment.start_lba,
        ),
    )

    print(f"Disk: {image.path}")
    print(f"Permanent extent candidates: {len(scan.permanent_candidates):,}")
    print(f"Recovered segment groups:    {len(recovered.segments):,}")
    print(f"Primary segment groups:      {len(recovered.primary_segments):,}")
    print(f"Secondary segment groups:    {len(recovered.secondary_segments):,}")
    print(f"Unrecovered candidates:      {len(recovered.unrecovered_candidates):,}")
    print()
    print(
        "Virtual addr   LBA        pages  extents  type  "
        "owner                    role"
    )

    if args.limit:
        segments = segments[: args.limit]
    for segment in segments:
        role = "primary" if segment.is_primary else "secondary"
        print(
            f"{segment.virtual_address:012X} "
            f"{segment.start_lba:>9,} "
            f"{segment.pages:>6,} "
            f"{len(segment.extents):>7,} "
            f"{segment.header.segment_type:04X}  "
            f"{str(segment.header.owner):<24} "
            f"{role}"
        )
    return 0


def cmd_libraries(args):
    image = _open(args.image)
    _, segments, inventory = _recover_all(image)
    counts = {}
    for obj in inventory.assigned_objects:
        if obj.library_name is not None:
            counts[obj.library_name] = counts.get(obj.library_name, 0) + 1

    libraries = inventory.libraries
    if args.name:
        wanted = args.name.upper()
        libraries = [
            library
            for library in libraries
            if wanted in library.name.upper()
        ]

    print(f"Disk: {image.path}")
    print(
        f"Recovered {len(inventory.libraries):,} permanent contexts "
        f"from {len(segments.segments):,} segment groups."
    )
    print()
    print("Library       objects  virtual addr   LBA        pages")
    for library in libraries:
        print(
            f"{library.name:<12} "
            f"{counts.get(library.name, 0):>7,}  "
            f"{library.segment.virtual_address:012X} "
            f"{library.segment.start_lba:>9,} "
            f"{library.segment.pages:>6,}"
        )
    return 0


def _print_objects(image, inventory, args):
    objects = [
        obj for obj in inventory.objects if _object_matches(obj, args)
    ]
    objects.sort(
        key=lambda obj: (
            obj.library_name or "",
            obj.object_type,
            obj.object_subtype,
            obj.name,
            obj.segment.virtual_address,
        )
    )

    total = len(objects)
    shown = objects if not args.limit else objects[: args.limit]

    print(f"Disk: {image.path}")
    print(f"Matching objects: {total:,}")
    print()
    print(
        "Library      MI    Hint     Name                           "
        "Virtual addr   LBA        pages"
    )
    for obj in shown:
        print(_object_line(obj))
    if len(shown) < total:
        print(f"... {total - len(shown):,} additional matching objects omitted")
    return 0


def cmd_objects(args):
    image = _open(args.image)
    _, segments, inventory = _recover_all(image)
    return _print_objects(image, inventory, args)


def cmd_ls(args):
    image = _open(args.image)
    _, _, inventory = _recover_all(image)
    # Reuse the objects formatter with the positional library name.
    args.library = args.library_name
    return _print_objects(image, inventory, args)




def cmd_files(args):
    image = _open(args.image)
    _, _, inventory = _recover_all(image)

    wildcard = args.library_name == "*"
    library_filter = None if wildcard else args.library_name
    members = inventory.members(library=library_filter)

    # Key by (library, file) in wildcard mode so same-named files in different
    # libraries do not collapse together. Unresolved contexts remain visible as
    # <orphan>, which is important on incomplete multi-disk captures.
    member_counts = {}
    for member in members:
        library = member.library_name or "<orphan>"
        key = (
            library.upper() if wildcard else args.library_name.upper(),
            member.member_file_name.upper(),
        )
        member_counts[key] = member_counts.get(key, 0) + 1

    file_objects = {}
    objects = (
        inventory.objects
        if wildcard
        else inventory.in_library(args.library_name)
    )
    for obj in objects:
        if obj.object_type != 0x19 or obj.object_subtype != 0x01:
            continue
        if not wildcard and (obj.library_name or "").upper() != args.library_name.upper():
            continue
        library = obj.library_name or "<orphan>"
        key = (
            library.upper() if wildcard else args.library_name.upper(),
            obj.name.upper(),
        )
        file_objects.setdefault(key, obj)

    keys = sorted(set(file_objects) | set(member_counts))
    if args.name:
        wanted = args.name.upper()
        keys = [key for key in keys if wanted in key[1]]

    total = len(keys)
    shown = keys if not args.limit else keys[: args.limit]

    print(f"Disk: {image.path}")
    if wildcard:
        print(
            f"Recovered/inferred files across all contexts: {total:,}"
        )
        print()
        print(
            "Library      File        Members  Object       "
            "Virtual addr   LBA        pages"
        )
    else:
        print(
            f"Recovered/inferred files in {args.library_name.upper()}: "
            f"{total:,}"
        )
        print()
        print("File        Members  Object       Virtual addr   LBA        pages")

    for key in shown:
        library, name = key
        obj = file_objects.get(key)
        member_count = member_counts.get(key, 0)
        if wildcard:
            prefix = f"{library:<12.12} {name:<10.10} "
        else:
            prefix = f"{name:<10.10} "

        if obj is None:
            print(
                prefix
                + f"{member_count:>7,}  "
                + f"{'member-only':<12} {'-':<14} {'-':>9} {'-':>6}"
            )
        else:
            print(
                prefix
                + f"{member_count:>7,}  "
                + f"{'recovered':<12} "
                + f"{obj.segment.virtual_address:012X} "
                + f"{obj.segment.start_lba:>9,} "
                + f"{obj.segment.pages:>6,}"
            )

    if len(shown) < total:
        print(f"... {total - len(shown):,} additional files omitted")
    return 0


def _find_member_cursor(inventory, library_name, file_name, member_name):
    library_filter = None if library_name == "*" else library_name
    matches = [
        obj
        for obj in inventory.members(
            library=library_filter,
            file_name=file_name,
        )
        if obj.member_name.upper() == member_name.upper()
    ]
    if not matches:
        raise ValueError(
            f"member not recovered: "
            f"{library_name.upper()}/{file_name.upper()}"
            f"({member_name.upper()})"
        )
    return matches[0], matches



def _recover_member_storage(
    image,
    library_name,
    file_name,
    member_name,
):
    scan, segments, inventory = _recover_all(image)
    member, matches = _find_member_cursor(
        inventory,
        library_name,
        file_name,
        member_name,
    )
    storage = image.resolve_member_storage(
        member,
        inventory,
        segments,
    )
    return member, matches, storage, inventory


def _resolve_format_fields(
    image,
    inventory,
    library_name,
    file_name,
    *,
    record_length=None,
    format_name=None,
):
    """Resolve one or more MI 19/51 format objects for a recovered *FILE."""

    if format_name:
        formats = [
            obj
            for obj in inventory.objects
            if (
                obj.object_type == 0x19
                and obj.object_subtype == 0x51
                and obj.name.upper() == format_name.upper()
            )
        ]
    else:
        file_objects = [
            obj
            for obj in inventory.in_library(library_name)
            if (
                obj.object_type == 0x19
                and obj.object_subtype == 0x01
                and obj.name.upper() == file_name.upper()
            )
        ]
        formats = []
        for file_obj in file_objects:
            formats.extend(image.resolve_file_formats(file_obj, inventory))

    decoded = []
    seen = set()
    for format_obj in formats:
        key = (
            format_obj.segment.header.owner.extender,
            format_obj.segment.virtual_address,
        )
        if key in seen:
            continue
        seen.add(key)
        fields = image.read_format_fields(
            format_obj,
            record_length=record_length,
        )
        if fields:
            decoded.append((format_obj, fields))

    if record_length is not None and len(decoded) > 1:
        # Physical files normally have one applicable format. Prefer the one
        # whose described fields cover the greatest portion of the member's
        # fixed record without exceeding it.
        decoded.sort(
            key=lambda item: (
                max(
                    (
                        field.offset + field.storage_length
                        for field in item[1]
                    ),
                    default=0,
                ),
                len(item[1]),
            ),
            reverse=True,
        )

    return decoded


def _qddsi_key_field_labels(spec, format_fields):
    """Match ordinary DKYT rows to recovered 19/51 fields conservatively.

    A friendly name is returned only when record offset and storage length
    identify exactly one format field. DKYT rows whose length-or-fork value
    does not behave like a direct field length remain unnamed.
    """

    labels = []
    for key_field in spec.fields:
        offset = key_field.record_offset_hint
        matches = [
            field
            for field in format_fields
            if (
                offset is not None
                and field.offset == offset
                and field.storage_length == key_field.length_or_fork
            )
        ]
        labels.append(matches[0].name if len(matches) == 1 else "")
    return tuple(labels)


def cmd_fields(args):
    image = _open(args.image)
    _, _, inventory = _recover_all(image)
    decoded = _resolve_format_fields(
        image,
        inventory,
        args.library_name,
        args.file_name,
        format_name=args.format_name,
    )
    if not decoded:
        raise ValueError(
            f"no recovered format/field descriptions for "
            f"{args.library_name.upper()}/{args.file_name.upper()}"
        )

    print(f"Disk: {image.path}")
    print(
        f"File: {args.library_name.upper()}/{args.file_name.upper()}"
    )
    for index, (format_obj, fields) in enumerate(decoded):
        if index:
            print()
        print(
            f"Format: {format_obj.name}  MI {format_obj.type_code}  "
            f"VA {format_obj.segment.virtual_address:012X}  "
            f"{len(fields):,} fields"
        )
        print(
            "Offset  Length  Type       Digits  Dec  Field"
        )
        for field in fields:
            print(
                f"{field.offset:>6,}  "
                f"{field.storage_length:>6,}  "
                f"{field.type_name:<10} "
                f"{field.digits:>6,}  "
                f"{field.decimal_positions:>3,}  "
                f"{field.name}"
            )
    return 0


def cmd_records(args):
    image = _open(args.image)
    member, matches, storage, inventory = _recover_member_storage(
        image,
        args.library_name,
        args.file_name,
        args.member_name,
    )
    record_set = image.read_data_space_records(storage)
    if record_set is None:
        raise ValueError(
            f"data-space records were not recovered for "
            f"{args.library_name.upper()}/{args.file_name.upper()}"
            f"({args.member_name.upper()})"
        )

    layout = record_set.layout
    decoded_formats = []
    if args.decoded:
        decoded_formats = _resolve_format_fields(
            image,
            inventory,
            args.library_name,
            args.file_name,
            record_length=layout.record_length,
            format_name=args.format_name,
        )
        if not decoded_formats:
            raise ValueError(
                f"no recovered record format for decoded display of "
                f"{args.library_name.upper()}/{args.file_name.upper()}"
            )

    print(f"Disk:          {image.path}")
    print(
        f"Member:        {(member.library_name or args.library_name)}/"
        f"{member.member_file_name}({member.member_name})"
    )
    print(f"Entry count:   {layout.entry_count:,} user records")
    print(f"Force count:   {layout.force_count:,}")
    print(f"Record length: {layout.record_length:,} bytes")
    print(f"Entry length:  {layout.entry_length:,} bytes")
    print(
        f"Recovered:     {len(record_set.records):,}/"
        f"{layout.expected_entries_with_default:,} entries "
        f"({'complete' if record_set.complete else 'partial'})"
    )
    print(
        f"Data segments: {record_set.data_segment_count:,}  "
        f"logical stream {record_set.raw_stream_bytes:,} bytes"
    )
    if len(matches) > 1:
        print(
            f"Note:          {len(matches):,} matching cursors were "
            "recovered; showing the first by virtual address."
        )
    if not layout.standard_fixed_layout:
        print(
            f"Note:          {layout.per_entry_overhead:,} bytes of "
            "per-entry status/overhead precede or follow record data; "
            "only the first record-length bytes after status are shown."
        )

    records = (
        record_set.records
        if args.include_default
        else record_set.user_records
    )
    total = len(records)
    shown = records if not args.limit else records[: args.limit]

    print()
    if args.decoded:
        format_obj, fields = decoded_formats[0]
        print(
            f"Decoded format: {format_obj.name} "
            f"({len(fields):,} fields)"
        )
        print()
        for record in shown:
            values = []
            for field in fields:
                value = field.decode_value(record.data)
                if args.preview and len(value) > args.preview:
                    value = value[: args.preview] + "..."
                values.append(f"{field.name}={value}")
            print(
                f"RRN {record.rrn:>8,}  status 0x{record.status:02X}  "
                + " | ".join(values)
            )
    else:
        print("RRN       Status  EBCDIC preview")
        for record in shown:
            preview = record.ebcdic_preview
            if args.preview and len(preview) > args.preview:
                preview = preview[: args.preview] + "..."
            print(
                f"{record.rrn:>8,}  0x{record.status:02X}    {preview}"
            )
            if args.hex_bytes:
                amount = min(args.hex_bytes, len(record.data))
                print(
                    "          hex: "
                    + record.data[:amount].hex(" ").upper()
                    + (" ..." if amount < len(record.data) else "")
                )

    if len(shown) < total:
        print(f"... {total - len(shown):,} additional records omitted")
    return 0


def cmd_record(args):
    image = _open(args.image)
    member, matches, storage, inventory = _recover_member_storage(
        image,
        args.library_name,
        args.file_name,
        args.member_name,
    )
    record_set = image.read_data_space_records(storage)
    if record_set is None:
        raise ValueError(
            f"data-space records were not recovered for "
            f"{args.library_name.upper()}/{args.file_name.upper()}"
            f"({args.member_name.upper()})"
        )

    wanted = [
        record
        for record in record_set.records
        if record.rrn == args.rrn
    ]
    if not wanted:
        raise ValueError(
            f"RRN {args.rrn} is outside recovered range "
            f"0..{len(record_set.records) - 1}"
        )
    record = wanted[0]

    print(f"Disk:    {image.path}")
    print(
        f"Member:  {(member.library_name or args.library_name)}/"
        f"{member.member_file_name}({member.member_name})"
    )
    print(f"RRN:     {record.rrn:,}")
    print(f"Status:  0x{record.status:02X}")
    print(f"Length:  {len(record.data):,} bytes")
    if record.extra_raw:
        print(
            f"Extra:   {len(record.extra_raw):,} per-entry bytes: "
            f"{record.extra_raw.hex(' ').upper()}"
        )
    print()
    print("EBCDIC:")
    print(record.ebcdic_preview)
    print()
    print("Hex:")
    print(format_hex(record.data))

    if args.decoded:
        decoded_formats = _resolve_format_fields(
            image,
            inventory,
            args.library_name,
            args.file_name,
            record_length=record_set.layout.record_length,
            format_name=args.format_name,
        )
        if not decoded_formats:
            raise ValueError(
                f"no recovered record format for decoded display of "
                f"{args.library_name.upper()}/{args.file_name.upper()}"
            )
        format_obj, fields = decoded_formats[0]
        print()
        print(f"Decoded fields ({format_obj.name}):")
        for field in fields:
            print(
                f"  {field.name:<10} "
                f"[{field.type_name:<10} "
                f"off {field.offset:>4} len {field.storage_length:>4}] "
                f"{field.decode_value(record.data)}"
            )
    return 0


def cmd_source(args):
    image = _open(args.image)
    scan, segments, inventory = _recover_all(image)
    member, matches = _find_member_cursor(
        inventory,
        args.library_name,
        args.file_name,
        args.member_name,
    )
    storage = image.resolve_member_storage(
        member,
        inventory,
        segments,
    )
    content = image.read_source_member(storage)
    if content is None:
        raise ValueError(
            f"standard source records were not recovered for "
            f"{args.library_name.upper()}/{args.file_name.upper()}"
            f"({args.member_name.upper()}); the member may be a non-source "
            "file or its QDDS data segment may be incomplete"
        )

    info = image.read_member_info(member)

    if not args.text_only:
        print(f"Disk:        {image.path}")
        print(
            f"Member:      {(member.library_name or args.library_name)}/"
            f"{member.member_file_name}({member.member_name})"
        )
        if info is not None:
            print(f"Source type: {info.member_type or '-'}")
            print(f"Changed:     {info.source_change or '-'}")
            print(f"Created:     {info.created or '-'}")
            print(f"Text:        {info.text or '-'}")
        print(
            f"Records:     {content.line_count:,} source lines from "
            f"{content.data_segment_count:,} recovered data segment(s)"
        )
        if len(matches) > 1:
            print(
                f"Note:        {len(matches):,} matching cursors were "
                "recovered; showing the first by virtual address."
            )
        print()
        print("Seq      Date    Source")

    records = content.records
    if args.limit:
        records = records[: args.limit]

    for record in records:
        if args.text_only:
            print(record.text)
        else:
            print(
                f"{record.sequence_display:<8} "
                f"{record.source_date:<6} "
                f"{record.text}"
            )

    if args.limit and len(content.records) > len(records) and not args.text_only:
        print(
            f"... {len(content.records) - len(records):,} "
            "additional source lines omitted"
        )
    return 0


def cmd_cat(args):
    args.text_only = True
    args.limit = 0
    return cmd_source(args)


_DLO_FILENAME_HINT_RE = re.compile(
    r"^[A-Za-z0-9!#$%&'()@^_{}~+-]{1,64}"
    r"\.[A-Za-z0-9!#$%&'()@^_{}~+-]{1,16}$"
)


def _dlo_filename_hint(strings):
    """Return a conservative PC-style filename hint from printable metadata."""

    for value in strings:
        candidate = value.strip()
        if _DLO_FILENAME_HINT_RE.fullmatch(candidate):
            return candidate
    return ""


def _dlo_preview_strings(data, internal_name="", limit=3):
    """Return short printable EBCDIC runs useful while decoding DLO metadata.

    This deliberately does not claim that a printable run is the authoritative
    QDLS name or path. IBM documents QUSRSYS QAOSS* as the search-index files
    that track DLOs, making them a promising independent source for that
    mapping; these strings are forensic hints only.
    """

    strings = _tui_ebcdic_strings(data, min_length=4)
    result = []
    internal = internal_name.upper()
    for value in strings:
        if internal and value.upper() == internal:
            continue
        if len(value) > 120:
            value = value[:117] + "..."
        result.append(value)
        if limit and len(result) >= limit:
            break
    return result


_DLO_RUNTIME_INDEX_FILES = (
    "QAOSSS10",
    "QAOSSS11",
    "QAOSSS12",
    "QAOSSS13",
    "QAOSSS14",
    "QAOSSS15",
    "QAOSSS17",
    "QAOSSS18",
)

_DLO_MODEL_FILES = {
    "QADSPDOC": ("DSPFLR document-list model", "DOCDTL"),
    "QADSPFLR": ("DSPFLR folder-list model", "FLRDTL"),
    "QAOSIQDL": ("QRYDOCLIB output model", "OSQDL"),
    "QAOSIRTV": ("RTVDOC output model", "OSRTVD"),
}


def _dlo_model_files(inventory):
    """Return recovered QSYS model files useful for DLO reverse engineering."""

    result = []
    for obj in inventory.in_library("QSYS"):
        if (
            obj.object_type == 0x19
            and obj.object_subtype == 0x01
            and obj.name.upper() in _DLO_MODEL_FILES
        ):
            result.append(obj)
    return sorted(result, key=lambda obj: obj.name)


def _find_byte_occurrences(data, needle):
    """Return every byte offset of needle in data, including overlaps."""

    if not needle:
        return []
    offsets = []
    start = 0
    while True:
        offset = data.find(needle, start)
        if offset < 0:
            break
        offsets.append(offset)
        start = offset + 1
    return offsets



def _load_qaosss14_anchor_records(image, inventory, segments):
    """Return the best recovered V2R3 QAOSSS14 anchor-record set.

    The file/member relationship may still be partially unresolved, so search
    member cursors by file name globally and prefer the candidate with the most
    successfully decoded 193-byte records.
    """

    candidates = []
    for member in inventory.members(file_name="QAOSSS14"):
        try:
            storage = image.resolve_member_storage(
                member,
                inventory,
                segments,
            )
            record_set = image.read_data_space_records(storage)
        except Exception:
            record_set = None
        if (
            record_set is None
            or record_set.layout.record_length
            != QAOSSS14_V2_RECORD_LENGTH
        ):
            continue

        decoded = []
        for record in record_set.user_records:
            try:
                decoded.append(
                    QAOSSS14AnchorRecord.from_data_space_record(record)
                )
            except ValueError:
                continue
        if decoded:
            candidates.append(
                (
                    len(decoded),
                    member,
                    record_set,
                    tuple(decoded),
                )
            )

    if not candidates:
        return None, None, ()
    candidates.sort(
        key=lambda item: (
            item[0],
            item[1].segment.virtual_address,
        ),
        reverse=True,
    )
    _count, member, record_set, decoded = candidates[0]
    return member, record_set, decoded


def _qaosss14_key_index(records):
    """Index live observed QAOSSS14 identifiers used in recovered QDOC objects."""

    index = {}
    zero = b"\x00" * 8
    for record in records:
        # Deleted 0xC0 QAOSSS14 entries are not present in the ordinary QDDSI
        # access path on the real V2R3 image. Do not let stale deleted anchors
        # compete with live records when correlating recovered QDOC objects.
        if getattr(record, "is_deleted_hint", False):
            continue
        # Most PC Support records use the same value in the leading record
        # key and WOSEFILD. Other records (including the BULLET examples) do
        # not, and both values occur in their corresponding QDOC object.
        for key in (record.leading_key, record.record_key):
            if key == zero:
                continue
            bucket = index.setdefault(key, [])
            if record not in bucket:
                bucket.append(record)
    return index


def _qaosss14_link_index(records):
    """Index live leading 8-byte record keys used by observed parent links."""

    index = {}
    zero = b"\x00" * 8
    for record in records:
        if getattr(record, "is_deleted_hint", False):
            continue
        key = record.leading_key
        if key == zero:
            continue
        index.setdefault(key, []).append(record)
    return index


def _match_qdoc_anchor_record(image, obj, records, key_index=None):
    """Match a recovered QDOC object to one QAOSSS14 record by binary keys.

    Direct V2R3-image evidence shows both the leading eight-byte QAOSSS14
    record key and the WOSEFILD value in corresponding QDOC objects. They are
    identical for many PC Support records but differ for other DLOs such as
    BULLET1.RFT. WOSEPLDN is also present in the matched examples. Score these
    literal byte relationships without assigning meanings to the IBM names.
    """

    if obj is None or not records:
        return None, "QAOSSS14 anchor records are not recovered"

    try:
        data = image.read_segment_bytes(obj.segment)
    except Exception as exc:
        return None, f"could not read QDOC object: {exc}"

    key_index = key_index or _qaosss14_key_index(records)
    candidates = {}
    for offset in range(0, max(0, len(data) - 7)):
        key = data[offset : offset + 8]
        for record in key_index.get(key, ()):
            candidates[record.rrn] = record

    if not candidates:
        return None, "no QAOSSS14 binary anchor key found in QDOC object"

    zero = b"\x00" * 8
    scored = []
    for record in candidates.values():
        score = 0
        if record.leading_key != zero and record.leading_key in data:
            score += 4
        if record.record_key != zero and record.record_key in data:
            score += 3
        if (
            record.parent_key != zero
            and record.parent_key in data
        ):
            score += 1
        if (
            record.secondary_key_raw != zero
            and record.secondary_key_raw in data
        ):
            score += 1
        scored.append((score, record))

    best_score = max(score for score, _record in scored)
    best = [
        record
        for score, record in scored
        if score == best_score
    ]
    if len(best) != 1:
        return None, (
            f"{len(best)} QAOSSS14 anchor candidates tie at "
            f"binary-evidence score {best_score}"
        )
    return best[0], ""


def _qaosss14_path(record, records, link_index=None):
    """Reconstruct the observed QAOSSS14 anchor hierarchy.

    On the real V2R3 image, a child's WOSEPLDN value matches the parent's
    leading eight-byte QAOSSS14 record key. It is *not* universally the
    parent's WOSEFILD value. Components use WOSEFDOC (falling back to
    WOSEDOCN); these are anchor-record names and are not assumed to be the
    user-facing folder name unless independently corroborated.
    """

    if record is None:
        return "", False

    link_index = link_index or _qaosss14_link_index(records)
    zero = b"\x00" * 8
    components = []
    current = record
    seen = set()
    complete = False

    while current is not None and current.rrn not in seen:
        seen.add(current.rrn)
        component = current.short_name or current.long_name
        if component:
            components.append(component)

        parent_key = current.parent_key
        if parent_key == zero:
            complete = True
            break

        parents = link_index.get(parent_key, ())
        if len(parents) != 1:
            break
        current = parents[0]

    components.reverse()
    if not components:
        return "", complete
    return "/".join(components), complete


def _qaosss14_object_info(
    image,
    obj,
    records,
    *,
    key_index=None,
    link_index=None,
):
    record, error = _match_qdoc_anchor_record(
        image,
        obj,
        records,
        key_index=key_index,
    )
    if record is None:
        return {
            "record": None,
            "anchor_path": "",
            "path_complete": False,
            "error": error,
        }
    anchor_path, complete = _qaosss14_path(
        record,
        records,
        link_index=link_index,
    )
    return {
        "record": record,
        "anchor_path": anchor_path,
        # Compatibility while callers transition from the earlier QDLS-path
        # wording. This value is the QAOSSS14 anchor hierarchy, not
        # automatically a user-facing QDLS path.
        "path": anchor_path,
        "path_complete": complete,
        "error": "",
    }

def cmd_dlos(args):
    image = _open(args.image)
    _, _, inventory = _recover_all(image)

    wanted_subtype = None
    if args.object_class == "doc":
        wanted_subtype = 0x0E
    elif args.object_class == "flr":
        wanted_subtype = 0x12

    dlos = [
        obj
        for obj in inventory.in_library("QDOC")
        if obj.object_type == 0x19
        and obj.object_subtype in (0x0E, 0x12)
        and (
            wanted_subtype is None
            or obj.object_subtype == wanted_subtype
        )
    ]
    dlos.sort(
        key=lambda obj: (
            obj.object_subtype,
            obj.name,
            obj.segment.virtual_address,
        )
    )

    total = len(dlos)
    shown = dlos if not args.limit else dlos[: args.limit]

    # IBM's MI type table identifies 06/C1 as *DOCBSS (Document byte string
    # space). On the real V2R3 image, binary-looking FMPV documents have a
    # companion named SYSOBJNAM + "F". Treat that name relationship as an
    # observed association, not yet as a proven byte-export layout.
    docbss_by_name = {}
    for candidate in inventory.objects:
        if (
            candidate.object_type == 0x06
            and candidate.object_subtype == 0xC1
        ):
            docbss_by_name.setdefault(candidate.name.upper(), []).append(
                candidate
            )

    print(f"Disk: {image.path}")
    print(f"Recovered QDOC DLO objects: {total:,}")
    print(
        "Note: SYSOBJNAM is the internal QDOC object name. Printable strings "
        "below are forensic hints, not yet reconstructed QDLS paths."
    )
    print()
    print(
        "Class  SYSOBJNAM   DOCBSS  Virtual addr   "
        "LBA        pages  printable metadata hints"
    )

    for obj in shown:
        label = "*DOC" if obj.object_subtype == 0x0E else "*FLR"
        hints = []
        if args.strings:
            try:
                data = image.read_segment_bytes(obj.segment)
                hints = _dlo_preview_strings(
                    data,
                    internal_name=obj.name,
                    limit=args.strings,
                )
            except Exception:
                hints = []
        preview = " | ".join(hints) if hints else "-"
        docbss_name = (obj.name.upper() + "F") if len(obj.name) == 10 else ""
        docbss_matches = docbss_by_name.get(docbss_name, [])
        docbss_status = "yes" if docbss_matches else "-"
        print(
            f"{label:<6} {obj.name:<10.10} {docbss_status:^6} "
            f"{obj.segment.virtual_address:012X} "
            f"{obj.segment.start_lba:>9,} "
            f"{obj.segment.pages:>6,}  "
            f"{preview}"
        )

    if len(shown) < total:
        print(f"... {total - len(shown):,} additional DLO objects omitted")

    companion_count = sum(
        1
        for obj in dlos
        if len(obj.name) == 10
        and docbss_by_name.get(obj.name.upper() + "F")
    )
    print()
    print(
        f"Observed SYSOBJNAM+'F' *DOCBSS companions: "
        f"{companion_count:,} of {len(dlos):,} recovered DLOs."
    )
    print(
        "IBM documents MI 06/C1 as *DOCBSS (Document byte string space). "
        "The name pairing is observed on this image; payload boundaries and "
        "safe export still require validation."
    )

    qao_prefix = "QAO" if args.all_qao else "QAOSS"
    qao_files = [
        obj
        for obj in inventory.in_library("QUSRSYS")
        if obj.object_type == 0x19
        and obj.object_subtype == 0x01
        and obj.name.upper().startswith(qao_prefix)
    ]
    exact_runtime = {
        obj.name.upper(): obj
        for obj in qao_files
        if obj.name.upper() in _DLO_RUNTIME_INDEX_FILES
    }
    print()
    print(
        "Document/folder search-index names explicitly documented by "
        "later IBM recovery guides (validate on this CISC image):"
    )
    exact_recovered_anywhere = {}
    for name in _DLO_RUNTIME_INDEX_FILES:
        object_matches = [
            obj
            for obj in inventory.objects
            if (
                obj.object_type == 0x19
                and obj.object_subtype == 0x01
                and obj.name.upper() == name
            )
        ]
        member_matches = inventory.members(file_name=name)
        exact_recovered_anywhere[name] = (
            object_matches,
            member_matches,
        )

        obj = exact_runtime.get(name)
        if obj is not None:
            print(
                f"  {name:<10} QUSRSYS *FILE recovered  "
                f"VA {obj.segment.virtual_address:012X}  "
                f"LBA {obj.segment.start_lba:,}  "
                f"{obj.segment.pages:,} pages"
            )
            continue

        if object_matches:
            candidate = object_matches[0]
            library = candidate.library_name or "<unresolved-context>"
            print(
                f"  {name:<10} *FILE object recovered in {library}  "
                f"VA {candidate.segment.virtual_address:012X}  "
                f"LBA {candidate.segment.start_lba:,}"
            )
            continue

        if member_matches:
            libraries = sorted(
                {
                    member.library_name or "<unresolved-context>"
                    for member in member_matches
                }
            )
            print(
                f"  {name:<10} member-only evidence: "
                f"{len(member_matches):,} cursor(s), context "
                + ", ".join(libraries)
            )
            continue

        print(f"  {name:<10} not recovered by current object/member pass")

    other_qao = [
        obj
        for obj in qao_files
        if obj.name.upper() not in _DLO_RUNTIME_INDEX_FILES
    ]
    if other_qao:
        label = "QAO*" if args.all_qao else "QAOSS*"
        print()
        print(
            f"Other recovered QUSRSYS {label} support files "
            f"({len(other_qao):,}):"
        )
        for obj in other_qao:
            print(
                f"  {obj.name:<10} "
                f"VA {obj.segment.virtual_address:012X}  "
                f"LBA {obj.segment.start_lba:,}  "
                f"{obj.segment.pages:,} pages"
            )

    if not exact_runtime:
        print()
        if any(
            objects or members
            for objects, members in exact_recovered_anywhere.values()
        ):
            print(
                "No exact search index is assigned to QUSRSYS yet, but "
                "the lines above show object/member evidence outside the "
                "resolved QUSRSYS context. That is useful recovery evidence."
            )
        else:
            print(
                "None of the eight IBM-documented QAOSSS10-15/17/18 search "
                "indexes is currently visible to the object/member pass. "
                "This does not prove they were absent from the original "
                "system; their directory or storage relationships may still "
                "be unresolved."
            )

    model_files = _dlo_model_files(inventory)
    print()
    if model_files:
        print(
            "Recovered QSYS DLO command model files "
            "(definitions/templates, not the QUSRSYS runtime indexes):"
        )
        for obj in model_files:
            description, expected_format = _DLO_MODEL_FILES[obj.name.upper()]
            decoded = _resolve_format_fields(
                image,
                inventory,
                "QSYS",
                obj.name,
            )
            formats = ", ".join(
                format_obj.name for format_obj, _fields in decoded
            ) or expected_format
            print(
                f"  {obj.name:<10} {formats:<10} {description}"
            )
            if args.model_fields:
                for format_obj, fields in decoded:
                    print(
                        f"    format {format_obj.name}: "
                        + ", ".join(field.name for field in fields)
                    )
                if not decoded:
                    print("    format fields not yet resolved")
    else:
        print("No recovered QSYS DLO command model files were found.")

    print()
    print(
        "DLO name forms documented by IBM: SYSOBJNAM is the 10-character "
        "internal QDOC name; the user-assigned document/folder name is up to "
        "12 characters; DOCID is a 24-character library-assigned name. "
        "RTVDLONAM can also return a folder path up to 63 characters."
    )

    return 0


def cmd_dlo_export(args):
    """Export a conservatively validated *DOCBSS workstation byte stream."""

    image = _open(args.image)
    _, segments, inventory = _recover_all(image)

    sysobjnam = args.sysobjnam.upper()
    if len(sysobjnam) != 10:
        raise ValueError("SYSOBJNAM must be exactly 10 characters")

    docs = [
        obj
        for obj in inventory.in_library("QDOC")
        if (
            obj.object_type == 0x19
            and obj.object_subtype == 0x0E
            and obj.name.upper() == sysobjnam
        )
    ]
    if not docs:
        raise ValueError(
            f"QDOC *DOC object not recovered: {sysobjnam}"
        )

    companion_name = sysobjnam + "F"
    companions = sorted(
        [
            obj
            for obj in inventory.objects
            if (
                obj.object_type == 0x06
                and obj.object_subtype == 0xC1
                and obj.name.upper() == companion_name
            )
        ],
        key=lambda obj: (
            obj.segment.virtual_address,
            obj.segment.start_lba,
        ),
    )
    if not companions:
        raise ValueError(
            f"no recovered IBM *DOCBSS companion named {companion_name}"
        )
    if len(companions) > 1:
        raise ValueError(
            f"multiple *DOCBSS companions named {companion_name}; "
            "refusing ambiguous export"
        )

    companion = companions[0]
    info, payload = image.read_document_byte_string(
        companion,
        segments,
    )

    output = Path(args.output).expanduser()
    image_path = Path(args.image).expanduser().resolve()
    try:
        output_resolved = output.resolve()
    except OSError:
        output_resolved = output.absolute()
    if output_resolved == image_path:
        raise ValueError("output path must not be the DASD image")

    if output.exists() and not args.force:
        raise ValueError(
            f"output already exists: {output}; use --force to replace it"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)

    prefix = payload[:16]
    ascii_prefix = "".join(
        chr(byte) if 32 <= byte < 127 else "."
        for byte in prefix
    )
    print(f"Disk:       {image.path}")
    print(f"QDOC:       {sysobjnam} (*DOC)")
    print(
        f"DOCBSS:     {companion.name}  "
        f"VA {companion.segment.virtual_address:012X}  "
        f"LBA {companion.segment.start_lba:,}"
    )
    print(f"Bytes:      {len(payload):,}")
    print(f"Allocated:  {info.allocated_length:,}")
    extended = (
        info.payload_length
        > companion.segment.pages * PAGE_SIZE - info.payload_offset
    )
    if extended:
        print(
            "Validation: duplicate length fields agree; payload continues "
            "through contiguous owner-matched 0F90 segment storage"
        )
    else:
        print(
            "Validation: duplicate length fields agree; declared payload fits "
            "inside the recovered primary segment"
        )
    print(f"Prefix:     {prefix.hex(' ').upper()}  {ascii_prefix}")
    print(f"Output:     {output}")
    return 0


def _dlo_schema_marker_evidence(window, marker_offset, format_name):
    """Extract exact 8-byte IBM identifier relationships around a format marker.

    The V2R3 image contains dense metadata blocks where an 8-character field
    identifier is immediately followed by WOSFMTxx, then a small separator and
    one or more concatenated 8-character QAOSS/WOS identifiers. This helper
    preserves those literal names without assigning meanings to the binary
    descriptor bytes around them.
    """

    marker = format_name.encode("cp037")
    if window[marker_offset : marker_offset + len(marker)] != marker:
        return None

    field = ""
    for back in (8, 16, 24):
        start = marker_offset - back
        if start < 0:
            continue
        token = window[start : start + 8]
        if len(token) != 8:
            continue
        text = token.decode("cp037", errors="replace")
        if re.fullmatch(r"WOS[A-Z0-9]{5}", text):
            field = text
            break
    if not field or field == format_name:
        return None

    tail_start = marker_offset + len(marker)
    first = None
    for delta in range(0, 8):
        pos = tail_start + delta
        token = window[pos : pos + 8]
        if len(token) != 8:
            break
        text = token.decode("cp037", errors="replace")
        if re.fullmatch(r"QAOSS[A-Z0-9]{3}", text):
            first = pos
            break
    if first is None:
        return None

    related = []
    pos = first
    while pos + 8 <= len(window):
        text = window[pos : pos + 8].decode(
            "cp037",
            errors="replace",
        )
        if not re.fullmatch(r"[A-Z][A-Z0-9]{7}", text):
            break
        if text.startswith(("QAOSS", "WOS")):
            related.append(text)
            pos += 8
            continue
        break

    if not related:
        return None
    return field, tuple(related)


def _dlo_schema_descriptor_layout(window, marker_offset, format_name):
    """Return field/related identifiers plus observed 1-based offset/length."""

    evidence = _dlo_schema_marker_evidence(
        window,
        marker_offset,
        format_name,
    )
    if evidence is None:
        return None
    field, related = evidence

    marker = format_name.encode("cp037")
    tail_start = marker_offset + len(marker)
    first = None
    for delta in range(0, 8):
        pos = tail_start + delta
        token = window[pos : pos + 8]
        if len(token) != 8:
            break
        text = token.decode("cp037", errors="replace")
        if re.fullmatch(r"QAOSS[A-Z0-9]{3}", text):
            first = pos
            break
    if first is None:
        return None

    pos = first
    while pos + 8 <= len(window):
        text = window[pos : pos + 8].decode(
            "cp037",
            errors="replace",
        )
        if (
            re.fullmatch(r"[A-Z][A-Z0-9]{7}", text)
            and text.startswith(("QAOSS", "WOS"))
        ):
            pos += 8
            continue
        break

    if pos + 4 > len(window):
        return None
    offset_one = int.from_bytes(window[pos : pos + 2], "big")
    length = int.from_bytes(window[pos + 2 : pos + 4], "big")
    if offset_one <= 0 or length <= 0:
        return None
    return field, related, offset_one, length


def _iter_file_pattern_windows(
    path,
    needle,
    *,
    before=32,
    after=128,
    chunk_size=4 * 1024 * 1024,
):
    """Yield exact raw-file windows around pattern hits without loading it."""

    overlap = max(0, len(needle) - 1)
    with (
        open(path, "rb") as scan_handle,
        open(path, "rb") as window_handle,
    ):
        base = 0
        carry = b""
        while True:
            chunk = scan_handle.read(chunk_size)
            if not chunk:
                break
            data = carry + chunk
            data_base = base - len(carry)
            pos = 0
            while True:
                hit = data.find(needle, pos)
                if hit < 0:
                    break
                absolute = data_base + hit
                # A hit beginning in carry is new only when it crosses the
                # current chunk boundary; otherwise the previous pass emitted
                # it already.
                if absolute >= base or absolute + len(needle) > base:
                    start = max(0, absolute - before)
                    window_handle.seek(start)
                    window = window_handle.read(
                        before + len(needle) + after
                    )
                    yield absolute, window, absolute - start
                pos = hit + 1
            carry = data[-overlap:] if overlap else b""
            base += len(chunk)


def cmd_dlo_schema(args):
    """Report literal WOSFMT/QAOSS schema associations from the raw image."""

    image = _open(args.image)
    format_name = args.format_name.upper()
    if not re.fullmatch(r"WOSFMT[0-9A-Z]{2}", format_name):
        raise ValueError(
            "format name must use the WOSFMTxx form, for example WOSFMT14"
        )

    needle = format_name.encode("cp037")
    counts = {}
    first_offsets = {}
    layouts = {}
    for absolute, window, marker_offset in _iter_file_pattern_windows(
        image.path,
        needle,
    ):
        evidence = _dlo_schema_descriptor_layout(
            window,
            marker_offset,
            format_name,
        )
        if evidence is None:
            continue
        field, related, offset_one, length = evidence
        if args.family:
            family = args.family.upper()
            if not related or related[0] != family:
                continue
        key = (field, related)
        counts[key] = counts.get(key, 0) + 1
        first_offsets.setdefault(key, absolute)
        layout_counts = layouts.setdefault(key, {})
        layout_key = (offset_one, length)
        layout_counts[layout_key] = layout_counts.get(layout_key, 0) + 1

    rows = sorted(
        counts,
        key=lambda item: (
            item[1][0] if item[1] else "",
            item[0],
            item[1],
        ),
    )

    print(f"Disk:       {image.path}")
    print(f"Format:     {format_name}")
    if args.family:
        print(f"Family:     {args.family.upper()}")
    print(f"Evidence:   {sum(counts.values()):,} marker association(s)")
    print()
    print(
        "Field      Off  Len  Primary     Related identifiers          "
        "Count  First raw offset"
    )
    for field, related in rows:
        key = (field, related)
        primary = related[0] if related else "-"
        extras = " ".join(related[1:]) or "-"
        layout_counts = layouts.get(key, {})
        if layout_counts:
            (offset_one, field_length), layout_count = max(
                layout_counts.items(),
                key=lambda item: item[1],
            )
            marker = "" if layout_count == counts[key] else "?"
            offset_text = f"{offset_one}{marker}"
            length_text = f"{field_length}{marker}"
        else:
            offset_text = "-"
            length_text = "-"
        print(
            f"{field:<10} {offset_text:>4} {length_text:>4} "
            f"{primary:<11} {extras:<30.30} "
            f"{counts[key]:>5,}  "
            f"0x{first_offsets[key]:09X}"
        )

    if not rows:
        print("No matching raw schema associations were found.")
    else:
        print()
        print(
            "These are literal identifier relationships recovered from IBM "
            "metadata near the format marker. Off/Len are the repeated "
            "big-endian descriptor values immediately following the related "
            "identifiers; on QAOSSS14 they reproduce the 193-byte record "
            "layout as 1-based field offsets and lengths. A '?' marks mixed "
            "evidence. The command does not expand unknown abbreviations."
        )
    return 0


def cmd_dlo_xref(args):
    """Find byte-level references to one or more QDOC SYSOBJNAM values."""

    image = _open(args.image)
    _, _, inventory = _recover_all(image)

    targets = [value.upper() for value in args.sysobjnam]
    invalid = [target for target in targets if len(target) != 10]
    if invalid:
        raise ValueError(
            "each SYSOBJNAM must be exactly 10 characters; invalid: "
            + ", ".join(invalid)
        )

    needles = []
    for target in targets:
        needles.append((target, "EBCDIC", target.encode("cp037")))
        if args.ascii:
            needles.append((target, "ASCII", target.encode("ascii")))

    objects = inventory.objects
    if args.library:
        wanted = args.library.upper()
        objects = [
            obj
            for obj in objects
            if (obj.library_name or "<orphan>").upper() == wanted
        ]

    matches = []
    errors = 0
    for obj in objects:
        try:
            data = image.read_segment_bytes(obj.segment)
        except Exception:
            errors += 1
            continue

        for target, encoding, needle in needles:
            if not args.include_self and obj.name.upper() == target:
                continue
            for offset in _find_byte_occurrences(data, needle):
                matches.append((target, obj, offset, encoding, data))
                if args.limit and len(matches) >= args.limit:
                    break
            if args.limit and len(matches) >= args.limit:
                break
        if args.limit and len(matches) >= args.limit:
            break

    print(f"Disk:       {image.path}")
    print(f"SYSOBJNAM:  {', '.join(targets)}")
    scope = args.library.upper() if args.library else "all recovered objects"
    print(f"Scope:      {scope}")
    print(f"Matches:    {len(matches):,}")
    if errors:
        print(f"Read errors: {errors:,} object segment(s)")
    print()
    print(
        "Target      Library      MI    Hint     Object                         "
        "Virtual addr   Offset    Encoding"
    )

    for target, obj, offset, encoding, data in matches:
        library = obj.library_name or "<orphan>"
        print(
            f"{target:<10} "
            f"{library:<12.12} {obj.type_code:<5} "
            f"{(obj.external_type_hint or '-'): <8.8} "
            f"{obj.name:<30.30} "
            f"{obj.segment.virtual_address:012X} "
            f"0x{offset:06X} {encoding}"
        )
        if args.context:
            start = max(0, offset - args.context)
            end = min(
                len(data),
                offset + 10 + args.context,
            )
            window = data[start:end]
            print(
                f"  context 0x{start:06X}-0x{end:06X}: "
                f"{ebcdic_preview(window, limit=len(window))}"
            )
            if args.hex_context:
                print(
                    "  hex: "
                    + window.hex(" ").upper()
                )

    if not matches:
        print(
            "No references were found. Try --include-self to verify the "
            "objects' own headers, --ascii for PC-side payload strings, or "
            "omit --library to broaden the scan."
        )
    return 0

def _scan_ebcdic_sysobjnam(data, encoded_targets):
    """Return (offset, SYSOBJNAM) matches for known 10-byte EBCDIC names."""

    hits = []
    if len(data) < 10 or not encoded_targets:
        return hits
    for offset in range(0, len(data) - 9):
        name = encoded_targets.get(data[offset : offset + 10])
        if name is not None:
            hits.append((offset, name))
    return hits


def cmd_dlo_paths(args):
    """Map recovered QDOC documents to QAOSSS14 names and folder paths."""

    image = _open(args.image)
    _, segments, inventory = _recover_all(image)
    member, record_set, records = _load_qaosss14_anchor_records(
        image,
        inventory,
        segments,
    )

    print(f"Disk:       {image.path}")
    if not records:
        print(
            "No recoverable 193-byte QAOSSS14 anchor-record member was "
            "found."
        )
        return 0

    print(
        f"QAOSSS14:   {member.library_name or '<unresolved-context>'}/"
        f"{member.member_file_name}({member.member_name})"
    )
    print(
        f"Records:    {len(records):,} decoded; "
        f"QDDS record length {record_set.layout.record_length:,}"
    )

    wanted = {
        value.upper()
        for value in (args.sysobjnam or [])
    }
    docs = [
        obj
        for obj in inventory.in_library("QDOC")
        if (
            obj.object_type == 0x19
            and obj.object_subtype == 0x0E
            and len(obj.name) == 10
            and (not wanted or obj.name.upper() in wanted)
        )
    ]
    docs.sort(key=lambda obj: (obj.name, obj.segment.virtual_address))

    key_index = _qaosss14_key_index(records)
    link_index = _qaosss14_link_index(records)
    rows = []
    unmatched = 0
    for obj in docs:
        info = _qaosss14_object_info(
            image,
            obj,
            records,
            key_index=key_index,
            link_index=link_index,
        )
        record = info["record"]
        if record is None:
            unmatched += 1
            if args.show_unmatched:
                rows.append(
                    (
                        obj,
                        None,
                        "",
                        "",
                        False,
                        info["error"],
                    )
                )
            continue
        rows.append(
            (
                obj,
                record,
                record.short_name,
                info["path"],
                info["path_complete"],
                "",
            )
        )

    total_rows = len(rows)
    shown = rows if not args.limit else rows[: args.limit]

    print(f"QDOC docs:  {len(docs):,} considered")
    print(f"Mapped:     {sum(1 for row in rows if row[1] is not None):,}")
    print(f"Unmatched:  {unmatched:,}")
    print()
    print(
        "SYSOBJNAM   RRN      QAOSSS14 short name  "
        "QAOSSS14 anchor hierarchy"
    )
    for obj, record, short_name, path, complete, error in shown:
        if record is None:
            print(
                f"{obj.name:<10} {'-':>8}  {'-':<20} "
                f"<unmatched: {error}>"
            )
            continue
        display_path = path or "-"
        if display_path != "-" and not complete:
            display_path += "  [partial anchor hierarchy]"
        print(
            f"{obj.name:<10} {record.rrn:>8,}  "
            f"{(short_name or '-'):20.20} {display_path}"
        )

    if len(shown) < total_rows:
        print(f"... {total_rows - len(shown):,} additional rows omitted")

    print()
    print(
        "Correlation method: observed QAOSSS14 leading-key and WOSEFILD "
        "bytes are matched against recovered QDOC object data; WOSEPLDN is "
        "followed to another record's leading key only when unique. The "
        "result is an anchor hierarchy, not automatically a user-facing "
        "QDLS folder path. IBM field identifiers remain unexpanded."
    )
    return 0


def cmd_dlo_index_scan(args):
    """Correlate QDOC SYSOBJNAM values against recovered QAOSS member data."""

    image = _open(args.image)
    _, segments, inventory = _recover_all(image)

    qdoc_objects = [
        obj
        for obj in inventory.in_library("QDOC")
        if obj.object_type == 0x19
        and obj.object_subtype in (0x0E, 0x12)
        and len(obj.name) == 10
    ]
    encoded_targets = {
        obj.name.upper().encode("cp037"): obj.name.upper()
        for obj in qdoc_objects
    }

    if args.file_name:
        index_names = [args.file_name.upper()]
    elif args.all_indexes:
        index_names = list(_DLO_RUNTIME_INDEX_FILES)
    else:
        index_names = ["QAOSSS14"]

    print(f"Disk:       {image.path}")
    print(f"QDOC names: {len(encoded_targets):,}")
    print("Indexes:    " + ", ".join(index_names))
    print(
        "Method: exact 10-byte EBCDIC SYSOBJNAM correlation against recovered "
        "QAOSS member records; no field layout is assumed."
    )
    print()

    rows = []
    scanned_members = 0
    unreadable_members = 0

    for index_name in index_names:
        members = inventory.members(file_name=index_name)
        if not members:
            continue

        for member in members:
            scanned_members += 1
            try:
                storage = image.resolve_member_storage(
                    member,
                    inventory,
                    segments,
                )
                record_set = image.read_data_space_records(storage)
            except Exception:
                record_set = None

            if record_set is None:
                unreadable_members += 1
                continue

            for record in record_set.records:
                for offset, target in _scan_ebcdic_sysobjnam(
                    record.data,
                    encoded_targets,
                ):
                    start = max(0, offset - args.context)
                    end = min(
                        len(record.data),
                        offset + 10 + args.context,
                    )
                    rows.append(
                        (
                            index_name,
                            member,
                            record,
                            offset,
                            target,
                            record.data[start:end],
                            start,
                        )
                    )
                    if args.limit and len(rows) >= args.limit:
                        break
                if args.limit and len(rows) >= args.limit:
                    break
            if args.limit and len(rows) >= args.limit:
                break
        if args.limit and len(rows) >= args.limit:
            break

    print(f"Recovered matching member cursors: {scanned_members:,}")
    if unreadable_members:
        print(
            f"Members without recoverable fixed-record QDDS data: "
            f"{unreadable_members:,}"
        )
    print(f"SYSOBJNAM correlations: {len(rows):,}")
    print()

    if rows:
        print(
            "Index      Context      Member      RRN       Status  Off    "
            "SYSOBJNAM   EBCDIC context"
        )
        for (
            index_name,
            member,
            record,
            offset,
            target,
            window,
            start,
        ) in rows:
            library = member.library_name or "<orphan>"
            context = ebcdic_preview(window, limit=len(window))
            print(
                f"{index_name:<10} "
                f"{library:<12.12} "
                f"{member.member_name:<10.10} "
                f"{record.rrn:>8,}  "
                f"0x{record.status:02X}   "
                f"0x{offset:04X} "
                f"{target:<10} "
                f"{context}"
            )
            if args.hex_context:
                print(
                    f"  data context 0x{start:04X}: "
                    + window.hex(" ").upper()
                )
    else:
        print(
            "No QDOC SYSOBJNAM values were found in the recovered record data "
            "for the selected QAOSS member(s). This can mean the index/member "
            "storage is not yet recovered, the record format is not an ordinary "
            "fixed QDDS layout, or this release stores the reference elsewhere."
        )

    if "QAOSSS14" in index_names:
        print()
        print(
            "IBM documents QAOSSS14 as containing an anchor record that stores "
            "the DLO system object name. On the V2R3 image, the useful "
            "correlation is an 8-byte WOSEFILD key embedded in the QDOC "
            "object rather than a plain EBCDIC SYSOBJNAM. Use dlo-paths for "
            "that decoded correlation; this command remains the literal-name "
            "probe."
        )

    return 0


def _qaosss14_unresolved_parent_records(records, *, include_deleted=False):
    """Return live records whose nonzero parent lacks one unique live match.

    V2R3 DENT 0xC0 records are independently validated as deleted and are
    absent from the ordinary QAOSSS14 access path. They are retained in the raw
    recovered record set for forensics but are not live hierarchy gaps unless
    include_deleted is explicitly requested.
    """

    link_index = _qaosss14_link_index(records)
    zero = b"\x00" * 8
    result = []
    for record in records:
        if (
            not include_deleted
            and getattr(record, "is_deleted_hint", False)
        ):
            continue
        parent = record.parent_key
        if parent == zero:
            continue
        matches = link_index.get(parent, [])
        if len(matches) != 1:
            result.append((record, tuple(matches)))
    return tuple(result)


def _segment_containing_lba(segments, lba):
    """Return the recovered segment whose physical extent contains one LBA."""

    for segment in segments.segments:
        for extent in segment.extents:
            if extent.start_lba <= lba <= extent.end_lba:
                return segment
    return None


def cmd_dlo_parent_gaps(args):
    """Investigate QAOSSS14 parent keys that do not resolve uniquely."""

    image = _open(args.image)
    _, segments, inventory = _recover_all(image)
    member, record_set, records = _load_qaosss14_anchor_records(
        image,
        inventory,
        segments,
    )
    if member is None or record_set is None or not records:
        raise ValueError(
            "no recoverable 193-byte QAOSSS14 anchor-record set found"
        )

    gaps = _qaosss14_unresolved_parent_records(records)
    deleted_with_parent = tuple(
        record
        for record in records
        if (
            getattr(record, "is_deleted_hint", False)
            and record.parent_key != b"\x00" * 8
        )
    )
    print(f"Disk:       {image.path}")
    print(
        f"QAOSSS14:  {member.library_name or '<unresolved>'}/"
        f"{member.member_file_name}({member.member_name})"
    )
    print(f"Records:    {len(records):,}")
    print(f"Live parent gaps: {len(gaps):,}")
    print(f"Deleted records with parent keys: {len(deleted_with_parent):,}")
    if deleted_with_parent:
        print(
            "  "
            + ", ".join(
                f"RRN {record.rrn:,} ({record.short_name or '-'})"
                for record in deleted_with_parent[:12]
            )
        )
    print()

    object_by_owner = {}
    for obj in inventory.objects:
        key = (
            obj.segment.header.owner.extender,
            obj.segment.virtual_address,
        )
        object_by_owner.setdefault(key, obj)

    for record, matches in gaps:
        print(
            f"RRN {record.rrn:,}  short={record.short_name or '-'}  "
            f"long={record.long_name or '-'}"
        )
        print(
            f"  parent key: {record.parent_key.hex().upper()}  "
            f"leading-key matches: {len(matches)}"
        )

        if not args.raw_scan:
            continue

        occurrences = []
        for absolute, window, marker_offset in _iter_file_pattern_windows(
            image.path,
            record.parent_key,
            before=args.context,
            after=args.context,
        ):
            lba = absolute // SECTOR_SIZE
            sector_offset = absolute % SECTOR_SIZE
            segment = _segment_containing_lba(segments, lba)
            owner = None
            if segment is not None:
                owner = object_by_owner.get(segment.owner_key)
            occurrences.append(
                (
                    absolute,
                    lba,
                    sector_offset,
                    segment,
                    owner,
                    window,
                    marker_offset,
                )
            )
            if args.limit and len(occurrences) >= args.limit:
                break

        print(f"  raw-image occurrences: {len(occurrences):,}")
        for (
            absolute,
            lba,
            sector_offset,
            segment,
            owner,
            window,
            marker_offset,
        ) in occurrences:
            if owner is not None:
                owner_text = (
                    f"{owner.library_name or '<orphan>'}/{owner.name} "
                    f"{owner.external_type_hint or owner.type_code}"
                )
            elif segment is not None:
                owner_text = (
                    f"recovered segment type "
                    f"{segment.header.segment_type:04X} "
                    f"owner {segment.header.owner}"
                )
            else:
                owner_text = "outside recovered segment map"

            print(
                f"    raw 0x{absolute:09X}  "
                f"LBA {lba:,}+0x{sector_offset:03X}  {owner_text}"
            )
            if args.hex_context:
                print(
                    "      "
                    + window.hex(" ").upper()
                    + f"  [key at window +0x{marker_offset:X}]"
                )
        print()

    if not gaps:
        print(
            "Every live nonzero QAOSSS14 parent key resolves uniquely through "
            "another live record's leading key."
        )
        if deleted_with_parent:
            print(
                "Deleted DENT 0xC0 records are retained as forensic evidence "
                "but are not reported as live hierarchy gaps."
            )
    elif not args.raw_scan:
        print(
            "Use --raw-scan to locate each unresolved 8-byte parent key "
            "elsewhere in the DASD image and classify recovered containers."
        )

    return 0




_MACHINE_INDEX_USED_PAGE_FIELDS = (
    "root node of the page",
    "page type",
    "number of free bytes",
    "offset to the first free byte on the page",
    "backpointer information",
    "current tree",
)

_MACHINE_INDEX_FREE_PAGE_FIELDS = (
    "unused",
    "page type",
    "number of free pages in free chain",
    "pointer to next free page",
)


def _machine_index_page_structure_lines():
    """Summarize documented and independently validated page-header facts."""

    lines = [
        "Release-2 machine-index logical-page structure:",
        "  IBM-documented in-use order: "
        + " | ".join(_MACHINE_INDEX_USED_PAGE_FIELDS),
        "  IBM-documented free-page order: "
        + " | ".join(_MACHINE_INDEX_FREE_PAGE_FIELDS),
        (
            "  Context pages validated on both real images: root node +0x00..02; "
            "page type +0x03; free-byte value +0x04..05; "
            "first-free low address +0x06..07."
        ),
        (
            "  Recovered permanent contexts use 1,024-byte logical pages: "
            "trunk type 0xCC at +0x800; child type 0x55."
        ),
        (
            "  Child type-0x55 pages carry six raw backpointer bytes at "
            "+0x08..0x0D; tree storage begins at +0x0E. "
            "The three two-byte backpointer words remain only partly decoded."
        ),
        (
            "  Trunk type-0xCC tree storage can begin at +0x08. "
            "The exact semantics of non-tail free space and the middle "
            "backpointer word remain unresolved."
        ),
    ]
    return lines

def _find_pattern_offsets(data, pattern, *, limit=8):
    """Return bounded non-overlapping byte-pattern offsets."""

    if not pattern:
        return []
    offsets = []
    start = 0
    while start <= len(data) - len(pattern):
        offset = data.find(pattern, start)
        if offset < 0:
            break
        offsets.append(offset)
        if limit and len(offsets) >= limit:
            break
        start = offset + max(1, len(pattern))
    return offsets


def _object_owned_segments(segment_result, obj):
    """Return every recovered segment group owned by one object/context."""

    key = obj.segment.owner_key
    return sorted(
        [
            segment
            for segment in segment_result.segments
            if segment.owner_key == key
        ],
        key=lambda segment: (
            segment.virtual_address,
            segment.start_lba,
        ),
    )


def _find_pattern_segment_locations(segment_blobs, pattern, *, limit=8):
    """Search a pattern across multiple owned segment groups.

    Locations are returned as (segment, offset) pairs so offsets remain
    meaningful even when an object spans multiple segment groups.
    """

    if not pattern:
        return []

    locations = []
    for segment, data in segment_blobs:
        remaining = 0 if not limit else max(0, limit - len(locations))
        if limit and remaining == 0:
            break
        for offset in _find_pattern_offsets(
            data,
            pattern,
            limit=remaining,
        ):
            locations.append((segment, offset))
            if limit and len(locations) >= limit:
                return locations
    return locations


def _longest_pattern_suffix_locations(
    segment_blobs,
    pattern,
    *,
    min_length=5,
    limit=8,
):
    """Find the longest contiguous suffix of a pattern present in segments.

    Machine-index common text removes leading key bytes from terminal text.
    A long suffix of T+S+NL+N is therefore useful terminal-text evidence
    without assuming that the complete key remains contiguous.
    """

    if not pattern:
        return 0, []
    minimum = max(1, min(min_length, len(pattern)))
    for length in range(len(pattern), minimum - 1, -1):
        locations = _find_pattern_segment_locations(
            segment_blobs,
            pattern[-length:],
            limit=limit,
        )
        if locations:
            return length, locations
    return 0, []



def _key_tail_location_map(rows):
    """Group key-tail evidence by exact recovered segment location."""

    locations = {}
    for (
        obj,
        _entry,
        _full_key_hits,
        key_tail_length,
        key_tail_hits,
        _base_address_hits,
        _physical_epa_hits,
        _expanded_base_hits,
    ) in rows:
        for segment, offset in key_tail_hits:
            key = (segment.virtual_address, offset)
            item = locations.setdefault(
                key,
                {
                    "segment": segment,
                    "offset": offset,
                    "max_tail": 0,
                    "objects": [],
                },
            )
            item["max_tail"] = max(item["max_tail"], key_tail_length)
            item["objects"].append(obj)
    return locations


def _key_tail_storage_page_summary(location_map):
    """Summarize distinct tail locations by 512-byte recovered storage page."""

    pages = {}
    for item in location_map.values():
        segment = item["segment"]
        offset = item["offset"]
        page_index = offset // PAGE_SIZE
        key = (segment.virtual_address, page_index)
        page = pages.setdefault(
            key,
            {
                "segment": segment,
                "page_index": page_index,
                "locations": set(),
                "objects": set(),
                "max_tail": 0,
            },
        )
        page["locations"].add(offset)
        for obj in item["objects"]:
            page["objects"].add(
                (
                    obj.object_type,
                    obj.object_subtype,
                    obj.name,
                    obj.segment.virtual_address,
                )
            )
        page["max_tail"] = max(page["max_tail"], item["max_tail"])
    return sorted(
        pages.values(),
        key=lambda page: (
            -len(page["locations"]),
            -len(page["objects"]),
            page["segment"].virtual_address,
            page["page_index"],
        ),
    )


def _machine_index_text_reference_score(
    segment_blobs,
    location_map,
    page_size,
    *,
    page_origin=0,
):
    """Score plausible text-element references to known key-tail bytes.

    IBM documents each release-2 machine-index element as three bytes. Because
    the page-header/trunk origin is not decoded yet, the raw scorer examines
    every byte start, but it also groups references by element-offset modulo 3.
    A genuine element stream should show substantially better phase coherence
    than accidental three-byte values in arbitrary data.
    """

    data_by_va = {
        segment.virtual_address: data
        for segment, data in segment_blobs
    }
    exact_by_phase = [set(), set(), set()]
    covered_by_phase = [set(), set(), set()]

    for key, item in location_map.items():
        segment = item["segment"]
        data = data_by_va.get(segment.virtual_address)
        if data is None or page_size > len(data):
            continue

        offset = item["offset"]
        if offset < page_origin:
            continue
        page_base = (
            page_origin
            + ((offset - page_origin) // page_size) * page_size
        )
        if page_base + page_size > len(data):
            continue
        page = data[page_base : page_base + page_size]
        relative = offset - page_base
        required = item["max_tail"]

        for element_offset in range(0, max(0, len(page) - 2)):
            value = int.from_bytes(
                page[element_offset : element_offset + 3],
                "big",
            )
            if value & 0x800000:
                continue
            text_length = (value >> 16) & 0x7F
            displacement = value & 0xFFFF
            if not text_length or displacement >= len(page):
                continue
            text_end = displacement + text_length
            if text_end > len(page):
                continue

            phase = element_offset % 3
            if displacement == relative and text_length >= required:
                exact_by_phase[phase].add(key)
                covered_by_phase[phase].add(key)
            elif (
                displacement <= relative
                and text_end >= relative + required
            ):
                covered_by_phase[phase].add(key)

    exact_locations = set().union(*exact_by_phase)
    covered_locations = set().union(*covered_by_phase)

    exact_counts = tuple(len(items) for items in exact_by_phase)
    covered_counts = tuple(len(items) for items in covered_by_phase)
    best_exact_phase = max(range(3), key=lambda phase: exact_counts[phase])
    best_covered_phase = max(
        range(3),
        key=lambda phase: covered_counts[phase],
    )

    return {
        "exact": len(exact_locations),
        "covered": len(covered_locations),
        "exact_by_phase": exact_counts,
        "covered_by_phase": covered_counts,
        "best_exact_phase": best_exact_phase,
        "best_exact": exact_counts[best_exact_phase],
        "best_covered_phase": best_covered_phase,
        "best_covered": covered_counts[best_covered_phase],
    }


def _machine_index_page_size_scores(segment_blobs, location_map):
    """Score documented text-element references for candidate logical sizes."""

    scores = []
    for page_size in (
        512,
        1024,
        2048,
        4096,
        8192,
        16384,
        32768,
    ):
        score = _machine_index_text_reference_score(
            segment_blobs,
            location_map,
            page_size,
        )
        scores.append((page_size, score))
    return scores



_CONTEXT_INDEX_MIN_OFFSET = SEGMENT_HEADER_SIZE + EPA_MIN_SIZE


def _primary_location_map(location_map, primary_segment):
    """Keep key-tail evidence from the primary context segment only."""

    return {
        key: item
        for key, item in location_map.items()
        if item["segment"].virtual_address
        == primary_segment.virtual_address
    }


def _machine_index_origin_rank(score):
    """Rank an origin using suffix evidence before exact-start coincidence."""

    return (
        score["best_covered"],
        score["covered"],
        score["best_exact"],
        score["exact"],
    )


def _machine_index_origin_scan(
    primary_blob,
    location_map,
    page_size,
    *,
    step=8,
    max_origin=PAGE_SIZE - 1,
):
    """Score candidate first-page origins after the documented object headers.

    The exact context-index start is unknown. The documentation says the first
    context segment contains YYSGHDR, EPA header, then the machine index, so
    candidates before the minimum known header footprint (0x78) are excluded.
    The scan is deliberately limited to the first 512-byte storage page.
    """

    segment, data = primary_blob
    if step < 1:
        raise ValueError("origin scan step must be positive")
    if not location_map:
        return []

    start = _CONTEXT_INDEX_MIN_OFFSET
    stop = min(max_origin, PAGE_SIZE - 1, len(data) - 1)
    scores = []
    for origin in range(start, stop + 1, step):
        # Require at least one complete logical page after the candidate origin.
        if origin + page_size > len(data):
            continue
        score = _machine_index_text_reference_score(
            [(segment, data)],
            location_map,
            page_size,
            page_origin=origin,
        )
        # We are locating only the longest known *suffix* of each logical key.
        # A real text element may therefore begin before that suffix. Prefer
        # phase-coherent coverage over exact-start coincidences.
        rank = _machine_index_origin_rank(score)
        scores.append((rank, origin, score))

    scores.sort(
        key=lambda item: (
            -item[0][0],
            -item[0][1],
            -item[0][2],
            -item[0][3],
            item[1],
        )
    )
    return scores


def _machine_index_origin_scan_summary(
    primary_blob,
    location_map,
    *,
    step=8,
):
    """Return top origin candidates for the three smallest IBM page sizes."""

    rows = []
    for page_size in (512, 1024, 2048, 4096):
        candidates = _machine_index_origin_scan(
            primary_blob,
            location_map,
            page_size,
            step=step,
        )
        rows.append((page_size, candidates[:3]))
    return rows


def cmd_context_xref(args):
    """Correlate EPA-known members with documented context-entry byte forms."""

    image = _open(args.image)
    _, segment_result, inventory = _recover_all(image)

    libraries = [
        library
        for library in inventory.libraries
        if library.name.upper() == args.library_name.upper()
    ]
    if not libraries:
        available = ", ".join(
            library.name for library in inventory.libraries[:12]
        )
        suffix = (
            f" Recovered contexts include: {available}."
            if available
            else " No permanent contexts were recovered."
        )
        raise ValueError(
            f"library/context not recovered: {args.library_name.upper()}."
            f"{suffix} Run 'as400-dasd libraries {args.image}' for the "
            "complete list."
        )
    context = libraries[0]
    objects = inventory.in_library(context.name)
    owned_segments = _object_owned_segments(segment_result, context)
    segment_blobs = [
        (segment, image.read_segment_bytes(segment))
        for segment in owned_segments
    ]

    rows = []
    full_key_hits_total = 0
    key_tail_hits_total = 0
    base_address_hits_total = 0
    physical_epa_hits_total = 0
    expanded_base_hits_total = 0

    for obj in objects:
        entry = ContextIndexEntry.from_object(obj)
        full_key_hits = _find_pattern_segment_locations(
            segment_blobs,
            entry.key_prefix,
            limit=args.max_hits,
        )
        key_tail_length, key_tail_hits = _longest_pattern_suffix_locations(
            segment_blobs,
            entry.key_prefix,
            min_length=args.min_key_tail,
            limit=args.max_hits,
        )

        base_address_pattern = obj.object_address.to_bytes()
        physical_epa_pattern = obj.physical_epa_byte_address.to_bytes()
        base_address_hits = _find_pattern_segment_locations(
            segment_blobs,
            base_address_pattern,
            limit=args.max_hits,
        )
        physical_epa_hits = _find_pattern_segment_locations(
            segment_blobs,
            physical_epa_pattern,
            limit=args.max_hits,
        )
        expanded_base_hits = _find_pattern_segment_locations(
            segment_blobs,
            entry.raw,
            limit=args.max_hits,
        )

        if full_key_hits:
            full_key_hits_total += 1
        if key_tail_hits:
            key_tail_hits_total += 1
        if base_address_hits:
            base_address_hits_total += 1
        if physical_epa_hits:
            physical_epa_hits_total += 1
        if expanded_base_hits:
            expanded_base_hits_total += 1

        if (
            key_tail_hits
            or base_address_hits
            or physical_epa_hits
            or args.include_misses
        ):
            rows.append(
                (
                    obj,
                    entry,
                    full_key_hits,
                    key_tail_length,
                    key_tail_hits,
                    base_address_hits,
                    physical_epa_hits,
                    expanded_base_hits,
                )
            )

    print(f"Disk:       {image.path}")
    print(f"Context:    {context.name}")
    print(
        f"Primary:    VA {context.segment.virtual_address:012X}  "
        f"LBA {context.segment.start_lba:,}  "
        f"{context.segment.pages:,} pages"
    )
    print(
        f"Owned segment groups: {len(owned_segments):,}  "
        f"({sum(segment.pages for segment in owned_segments):,} pages total)"
    )
    print(f"EPA-assigned objects: {len(objects):,}")
    print()
    print(
        "Documented logical context-entry form: "
        "T S NL N @  (type, subtype, name length, name, 8-byte object address)"
    )
    print(
        "This diagnostic does not assume the logical entry is contiguous on "
        "disk; machine-index common-text compression may split its leading "
        "bytes from terminal text."
    )
    print()
    print(
        f"Objects with complete T+S+NL+N key bytes contiguous: "
        f"{full_key_hits_total:,}/{len(objects):,}"
    )
    print(
        f"Objects with a >= {args.min_key_tail}-byte documented key suffix: "
        f"{key_tail_hits_total:,}/{len(objects):,}"
    )
    print(
        f"Objects whose base/object address occurs: "
        f"{base_address_hits_total:,}/{len(objects):,}"
    )
    print(
        f"Objects whose literal base+0x20 EPA byte address occurs: "
        f"{physical_epa_hits_total:,}/{len(objects):,}"
    )
    print(
        f"Objects with complete key+base-address candidate contiguous: "
        f"{expanded_base_hits_total:,}/{len(objects):,}"
    )
    print()

    if not rows:
        print("No key-tail or candidate-address evidence was found.")
        return 0

    print(
        "Type   Object                         keytail  base@  +20@  full  "
        "first key-tail location"
    )
    shown = 0
    for (
        obj,
        entry,
        full_key_hits,
        key_tail_length,
        key_tail_hits,
        base_address_hits,
        physical_epa_hits,
        expanded_base_hits,
    ) in rows:
        if args.limit and shown >= args.limit:
            break
        if key_tail_hits:
            first_segment, first_offset = key_tail_hits[0]
            first = (
                f"{first_segment.virtual_address:012X}+0x{first_offset:X}"
            )
        else:
            first = "-"
        print(
            f"{entry.type_code:<7}"
            f"{obj.name[:30]:<31}"
            f"{key_tail_length:>7}  "
            f"{len(base_address_hits):>5}  "
            f"{len(physical_epa_hits):>4}  "
            f"{len(expanded_base_hits):>4}  "
            f"{first}"
        )
        shown += 1

    if args.limit and len(rows) > shown:
        print(f"... {len(rows) - shown:,} additional row(s)")

    location_map = _key_tail_location_map(rows)
    if location_map:
        ambiguous = sum(
            1
            for item in location_map.values()
            if len(item["objects"]) > 1
        )
        print()
        print(
            f"Distinct key-tail byte locations: {len(location_map):,}  "
            f"shared by multiple candidate objects: {ambiguous:,}"
        )

        page_summary = _key_tail_storage_page_summary(location_map)
        print("Top 512-byte storage-page clusters:")
        print(
            "  Segment VA    page  page VA       locations  objects  max tail"
        )
        for page in page_summary[: args.page_summary]:
            segment = page["segment"]
            page_index = page["page_index"]
            page_va = segment.virtual_address + page_index * PAGE_SIZE
            print(
                f"  {segment.virtual_address:012X}  "
                f"{page_index:>4}  "
                f"{page_va:012X}  "
                f"{len(page['locations']):>9}  "
                f"{len(page['objects']):>7}  "
                f"{page['max_tail']:>8}"
            )
        if len(page_summary) > args.page_summary:
            print(
                f"  ... {len(page_summary) - args.page_summary:,} "
                "additional storage page(s)"
            )

        print()
        print(
            "Plausible text-element references to these key tails by "
            "candidate logical page size:"
        )
        print(
            "  page size   exact  best exact phase   covers  "
            "best cover phase"
        )
        for page_size, score in _machine_index_page_size_scores(
            segment_blobs,
            location_map,
        ):
            if score["exact"] or score["covered"]:
                print(
                    f"  {page_size:>8,}  "
                    f"{score['exact']:>6,}  "
                    f"{score['best_exact']:>6,}@{score['best_exact_phase']}  "
                    f"{score['covered']:>7,}  "
                    f"{score['best_covered']:>6,}@"
                    f"{score['best_covered_phase']}"
                )
        print(
            "  Phase is element offset modulo 3 within the candidate logical "
            "page. Every byte alignment is still tested; phase concentration "
            "is evidence, not a decoded page origin."
        )

        primary_blob = next(
            (
                item
                for item in segment_blobs
                if item[0].virtual_address
                == context.segment.virtual_address
            ),
            None,
        )
        primary_locations = _primary_location_map(
            location_map,
            context.segment,
        )
        if primary_blob is not None and primary_locations:
            print()
            print(
                "Primary-segment logical-page origin scan "
                f"(0x{_CONTEXT_INDEX_MIN_OFFSET:X}-0x1FF, "
                f"step {args.origin_step}):"
            )
            print(
                "  page size  origin   exact  best exact phase   "
                "covers  best cover phase"
            )
            for page_size, candidates in _machine_index_origin_scan_summary(
                primary_blob,
                primary_locations,
                step=args.origin_step,
            ):
                if not candidates:
                    print(
                        f"  {page_size:>8,}  "
                        "no full page fits after the minimum object headers"
                    )
                    continue
                for index, (_rank, origin, score) in enumerate(candidates):
                    prefix = f"  {page_size:>8,}" if index == 0 else " " * 10
                    print(
                        f"{prefix}  0x{origin:03X}  "
                        f"{score['exact']:>6,}  "
                        f"{score['best_exact']:>6,}@"
                        f"{score['best_exact_phase']}  "
                        f"{score['covered']:>7,}  "
                        f"{score['best_covered']:>6,}@"
                        f"{score['best_covered_phase']}"
                    )
            print(
                "  Origin candidates are forensic scores only. The scan starts "
                "after the minimum known YYSGHDR+EPA footprint and assumes the "
                "first logical page begins within the first 512-byte storage page."
            )

    print()
    print(
        "Interpretation: IBM documents T+S+NL+N as the identifying portion of "
        "the context entry and machine-index common text can remove leading "
        "bytes from terminal text. Long key tails are therefore more useful "
        "for locating terminal text than a raw full-entry search. The manual "
        "calls @ the EPA-header address, but current evidence does not justify "
        "a literal +0x20 interpretation; base@ and +20@ are shown separately."
    )
    if len(owned_segments) > 1:
        print(
            "All recovered segment groups owned by this context were searched; "
            "reported offsets are relative to the individual segment VA shown."
        )
    return 0


def cmd_context_page(args):
    image = _open(args.image)
    _, segments, inventory = _recover_all(image)

    libraries = [
        library
        for library in inventory.libraries
        if library.name.upper() == args.library_name.upper()
    ]
    if not libraries:
        raise ValueError(
            f"library/context not recovered: {args.library_name.upper()}"
        )
    context = libraries[0]

    page_start = args.origin + args.page * args.page_size
    context_data = image.read_segment_bytes(context.segment)
    page_header = None
    if page_start + 8 <= len(context_data):
        try:
            page_header = MachineIndexPageHeader.from_bytes(
                context_data,
                offset=page_start,
            )
        except ValueError:
            page_header = None

    probes = image.probe_machine_index_page(
        context,
        args.page,
        element_offset=args.offset,
        count=args.count,
        page_size=args.page_size,
        page_origin=args.origin,
    )

    print(f"Disk:       {image.path}")
    print(f"Context:    {context.name}")
    print(
        f"Segment:    VA {context.segment.virtual_address:012X}  "
        f"LBA {context.segment.start_lba:,}  "
        f"{context.segment.pages:,} pages"
    )
    print(
        f"Logical page {args.page}  size {args.page_size:,}  "
        f"origin 0x{args.origin:X}  element offset 0x{args.offset:X}"
    )
    if page_header is not None:
        first_free = page_header.first_free_offset()
        tail_free = page_header.tail_free_bytes(page_size=args.page_size)
        internal_free = page_header.non_tail_free_bytes_hint(
            page_size=args.page_size,
        )
        print(
            f"Page header: type 0x{page_header.page_type:02X}  "
            f"free {page_header.free_bytes:,}  "
            f"first-free 0x{first_free:X}"
        )
        if tail_free is not None:
            internal_text = (
                "unknown"
                if internal_free is None
                else f"{internal_free:,}"
            )
            print(
                f"             tail-free {tail_free:,}  "
                f"non-tail-free {internal_text}"
            )
        if page_header.backpointer_words is not None:
            words = page_header.backpointer_words
            print(
                "Backpointer: raw "
                f"{page_header.backpointer_raw.hex().upper()}  "
                f"words {words[0]:04X} {words[1]:04X} {words[2]:04X}"
            )
            v2_pair = page_header.shared_high16_node_pair_hint
            if v2_pair is not None:
                print(
                    "             V2R3 state~ "
                    f"(0x{v2_pair[0]:X}, 0x{v2_pair[1]:X})"
                )
            older_va = page_header.rotated_virtual_address_hint
            if older_va is not None:
                print(
                    "             older-B10 VA~ "
                    f"0x{older_va:012X}"
                )
        if page_header.current_tree_offset_hint is not None:
            print(
                "Tree start:  observed storage boundary "
                f"0x{page_header.current_tree_offset_hint:X}"
            )
    else:
        print("Page header: not recognized as an in-use machine-index page")
    print()
    print(
        "Offset  Raw     Kind          Details"
    )
    for probe in probes:
        element = probe.element
        if element.kind == "text":
            details = (
                f"length={element.text_length} "
                f"text_off=0x{element.text_displacement:04X}"
            )
        elif element.kind == "node":
            details = (
                f"dir={element.direction} "
                f"bit={element.bit_to_test} "
                f"common={'yes' if element.common_text_present else 'no'} "
                f"xor_disp=0x{element.xor_displacement:05X}"
            )
        else:
            details = (
                f"segment_index={element.segment_table_index} "
                f"page_offset=0x{element.page_offset:04X}"
            )
        print(
            f"0x{probe.offset:04X}  "
            f"{element.raw.hex().upper()}  "
            f"{element.kind:<13} {details}"
        )

    print()
    print(
        "Note: element decoding follows IBM's published release-2 "
        "three-byte machine-index format."
    )
    print(
        "For ordinary permanent contexts, +0x800 trunk placement and the "
        "1,024-byte page size are independently validated across both images; "
        "explicit options remain available for forensic probing."
    )
    print()
    for line in _machine_index_page_structure_lines():
        print(line)
    return 0


def cmd_members(args):
    image = _open(args.image)
    _, _, inventory = _recover_all(image)
    library_filter = None if args.library_name == "*" else args.library_name
    members = inventory.members(
        library=library_filter,
        file_name=args.file_name,
    )

    total = len(members)
    shown = members if not args.limit else members[: args.limit]

    print(f"Disk: {image.path}")
    if args.file_name:
        print(
            f"Recovered members in "
            f"{args.library_name.upper()}/{args.file_name.upper()}: "
            f"{total:,}"
        )
    else:
        print(
            f"Recovered member cursors in "
            f"{args.library_name.upper()}: {total:,}"
        )
    print()
    print(
        "Library      File       Member      Type       "
        "Source changed       Virtual addr   LBA"
    )
    for obj in shown:
        info = image.read_member_info(obj)
        member_type = info.member_type if info is not None else ""
        changed = info.source_change if info is not None else ""
        print(
            f"{(obj.library_name or '-'):<12} "
            f"{obj.member_file_name:<10.10} "
            f"{obj.member_name:<10.10} "
            f"{member_type:<10.10} "
            f"{changed:<20.20} "
            f"{obj.segment.virtual_address:012X} "
            f"{obj.segment.start_lba:>9,}"
        )
        if args.long and info is not None:
            print(
                f"  created: {info.created or '-'}"
                f"  text: {info.text or '-'}"
            )
    if len(shown) < total:
        print(
            f"... {total - len(shown):,} "
            "additional matching members omitted"
        )
    return 0


def cmd_member(args):
    image = _open(args.image)
    scan, segments, inventory = _recover_all(image)

    candidates = [
        obj
        for obj in inventory.members(
            library=args.library_name,
            file_name=args.file_name,
        )
        if obj.member_name.upper() == args.member_name.upper()
    ]
    if not candidates:
        raise ValueError(
            f"member not recovered: "
            f"{args.library_name.upper()}/"
            f"{args.file_name.upper()}("
            f"{args.member_name.upper()})"
        )

    member = candidates[0]
    info = image.read_member_info(member)
    storage = image.resolve_member_storage(
        member,
        inventory,
        segments,
    )

    print(f"Disk:        {image.path}")
    print(
        f"Member:      {(member.library_name or args.library_name)}/"
        f"{member.member_file_name}({member.member_name})"
    )
    print(f"Cursor MI:   {member.type_code} {member.external_type_hint}")
    print(
        f"Cursor:      VA {member.segment.virtual_address:012X}  "
        f"LBA {member.segment.start_lba:,}  "
        f"{member.segment.pages:,} pages"
    )

    if len(candidates) > 1:
        print(
            f"Note:        {len(candidates):,} matching cursor objects "
            "were recovered; showing the first by virtual address."
        )

    if info is not None:
        print(f"Source type: {info.member_type or '-'}")
        print(f"Changed:     {info.source_change or '-'}")
        print(f"Created:     {info.created or '-'}")
        print(f"Text:        {info.text or '-'}")
        print(
            f"Member hdr:  associated +0x"
            f"{info.associated_space_offset:X}, "
            f"header +0x{info.member_header_offset:X}"
        )

    print()
    print("Member storage")
    index_format_fields = ()
    if member.library_name:
        try:
            index_formats = _resolve_format_fields(
                image,
                inventory,
                member.library_name,
                member.member_file_name,
            )
            if index_formats:
                index_format_fields = index_formats[0][1]
        except Exception:
            index_format_fields = ()
    if storage.data_space is None:
        if storage.data_space_address is None:
            print("  QDDS data space: no direct pointer / not recovered")
        else:
            print(
                "  QDDS data space: primary not recovered; "
                f"cursor points to {storage.data_space_address}"
            )
    else:
        qdds = storage.data_space
        print(
            f"  QDDS data space: VA {qdds.segment.virtual_address:012X}  "
            f"LBA {qdds.segment.start_lba:,}  "
            f"primary {qdds.segment.pages:,} pages"
        )

    if storage.data_segments:
        print(
            f"  Owned segments:  {len(storage.data_segments):,}  "
            f"{storage.data_pages:,} pages / "
            f"{storage.data_bytes:,} bytes"
        )
        for segment in storage.data_segments:
            role = "primary" if segment.is_primary else "secondary"
            print(
                f"    {segment.virtual_address:012X}  "
                f"LBA {segment.start_lba:>9,}  "
                f"{segment.pages:>6,} pages  "
                f"type {segment.header.segment_type:04X}  "
                f"{role}"
            )

    if storage.data_index is None:
        if storage.data_index_address is None:
            print("  QDDSI index:     no direct pointer / not present")
        else:
            print(
                "  QDDSI index:     primary not recovered; "
                f"cursor points to {storage.data_index_address}"
            )
    else:
        index = storage.data_index
        print(
            f"  QDDSI index:     VA {index.segment.virtual_address:012X}  "
            f"LBA {index.segment.start_lba:,}  "
            f"{index.segment.pages:,} pages"
        )
        index_layout = image.read_data_space_index_layout(storage)
        if index_layout is not None:
            print(
                f"  QDDSI DKEY rows: {index_layout.dkey_count:,}  "
                f"table VA {index_layout.dkey_address:012X}"
            )
            for number, spec in enumerate(index_layout.keys):
                print(
                    f"    DKEY {number}: data space {spec.data_space}  "
                    f"keys {spec.key_count:,}  fields {spec.key_field_count:,}  "
                    f"user/machine key {spec.user_key_length}/"
                    f"{spec.machine_key_length} bytes"
                )
                field_labels = _qddsi_key_field_labels(
                    spec,
                    index_format_fields,
                )
                for field_number, field in enumerate(spec.fields, 1):
                    location = (
                        f"record +{field.record_offset_hint}"
                        if field.record_offset_hint is not None
                        else "record location unknown"
                    )
                    label = field_labels[field_number - 1]
                    friendly = f" {label}" if label else ""
                    print(
                        f"      key field {field_number}{friendly}: "
                        f"len/fork {field.length_or_fork}  {location}  "
                        f"seq 0x{field.sequence_attributes:02X}  "
                        f"attr 0x{field.field_attributes:02X}"
                    )

            traversal = image.read_data_space_index_traversal(storage)
            if traversal is not None:
                state = "complete" if traversal.complete else "partial"
                page_note = (
                    f"  page {traversal.page_size:,} bytes"
                    if traversal.page_size is not None
                    else ""
                )
                partial_note = (
                    f"  partial keys {traversal.partial_key_count:,}"
                    if traversal.partial_key_count
                    else ""
                )
                print(
                    f"  QDDSI keyed entries: {traversal.entry_count:,}/"
                    f"{traversal.expected_entries:,}  {state}{page_note}  "
                    f"pages {traversal.page_count:,}{partial_note}"
                )
                for entry in traversal.entries[:32]:
                    key_bytes = entry.display_key_bytes
                    preview = ebcdic_preview(
                        key_bytes,
                        limit=len(key_bytes),
                    )
                    ordinal = (
                        f"RRN~{entry.ordinal_hint:,}"
                        if entry.ordinal_hint is not None
                        else f"dbref {entry.database_reference.hex().upper()}"
                    )
                    key_label = "key" if entry.key_complete else "tree-key evidence"
                    partial = "" if entry.key_complete else "  (partial key)"
                    print(
                        f"      DKEY {entry.dkey_index}  "
                        f"{key_label} {key_bytes.hex().upper()}  "
                        f"[{preview}]  {ordinal}{partial}"
                    )
                if traversal.entry_count > 32:
                    print(
                        f"      ... {traversal.entry_count - 32:,} more key(s)"
                    )
                if traversal.page_pointers:
                    unresolved = traversal.unresolved_page_pointers
                    print(
                        f"      page pointers: {len(traversal.page_pointers):,}  "
                        f"unresolved {len(unresolved):,}"
                    )
                    for pointer in unresolved[:8]:
                        print(
                            f"        element 0x{pointer.element_offset:04X}: "
                            f"STI {pointer.segment_table_index}  "
                            f"page 0x{pointer.page_offset:04X}"
                        )
                for warning in traversal.warnings:
                    print(f"      warning: {warning}")

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
        segments = image.recover_segments(result)
        inventory = image.recover_objects(result, segments)
        sections.extend(_analysis_lines(image, result, top=args.top))
        sections.extend(_second_pass_lines(segments, inventory))
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



DASD_IMAGE_SUFFIXES = {
    ".hda",
    ".img",
    ".dsk",
    ".raw",
    ".bin",
}


def _tui_clip(text, width):
    if width <= 0:
        return ""
    text = str(text)
    if len(text) <= width:
        return text
    if width == 1:
        return "…"
    return text[: width - 1] + "…"


def _tui_safe_addstr(screen, y, x, text, attr=0):
    height, width = screen.getmaxyx()
    if y < 0 or y >= height or x < 0 or x >= width:
        return
    available = width - x
    if available <= 0:
        return
    try:
        screen.addstr(y, x, _tui_clip(text, available), attr)
    except Exception:
        # Some curses implementations reject a write to the final cell.
        pass


def _tui_list_start(count, selected, visible):
    if count <= 0 or visible <= 0:
        return 0
    selected = max(0, min(selected, count - 1))
    start = max(0, selected - visible // 2)
    return min(start, max(0, count - visible))


def _tui_draw_list(
    screen,
    title,
    items,
    selected,
    x,
    y,
    width,
    height,
    focused,
):
    import curses

    heading_attr = curses.A_BOLD | (
        curses.A_REVERSE if focused else 0
    )
    _tui_safe_addstr(
        screen,
        y,
        x,
        title.ljust(max(0, width - 1)),
        heading_attr,
    )

    visible = max(0, height - 1)
    if visible <= 0:
        return 0

    if not items:
        _tui_safe_addstr(
            screen,
            y + 1,
            x,
            "(empty)",
            curses.A_DIM,
        )
        return 0

    selected = max(0, min(selected, len(items) - 1))
    start = _tui_list_start(len(items), selected, visible)
    for row, item_index in enumerate(
        range(start, min(len(items), start + visible))
    ):
        prefix = "> " if item_index == selected else "  "
        attr = curses.A_REVERSE if item_index == selected else 0
        _tui_safe_addstr(
            screen,
            y + 1 + row,
            x,
            prefix + items[item_index]["label"],
            attr,
        )
    return start


def _tui_inspector_selection_key(state):
    """Stable key for the hierarchy item currently owning the inspector."""

    target = _tui_viewer_target(state)
    if target == "right":
        item = _tui_selected(state, "right")
        if item is None:
            return ("right", None)
        if item["kind"] in ("member", "object"):
            obj = item["object"]
            owner = getattr(getattr(obj.segment, "header", None), "owner", None)
            extender = getattr(owner, "extender", None)
            return (
                "right",
                item["kind"],
                extender,
                obj.segment.virtual_address,
            )
        if item["kind"] == "context-entry":
            entry = item["entry"]
            if entry.object_address is None:
                address_key = (-1, -1)
            else:
                address_key = getattr(
                    entry.object_address,
                    "key",
                    (
                        getattr(entry.object_address, "extender", -1),
                        entry.object_address.address,
                    ),
                )
            return (
                "right",
                "context-entry",
                entry.library_name,
                address_key,
                entry.terminal_element_offset,
            )
        return ("right", item.get("kind"), item.get("label"))

    if target == "mid":
        item = _tui_selected(state, "mid")
        if item is None:
            return ("mid", None)
        return (
            "mid",
            item.get("kind"),
            item.get("library"),
            item.get("name"),
            item.get("type"),
            item.get("subtype"),
        )

    item = _tui_selected(state, "left")
    if item is None:
        return ("left", None)
    return (
        "left",
        item.get("kind"),
        item.get("library"),
        item.get("label"),
    )


def _tui_inspector_availability(state):
    """Return meaningful-data availability for each inspector view."""

    key = _tui_inspector_selection_key(state)
    cache = state.setdefault("inspector_availability_cache", {})
    if key in cache:
        return cache[key]

    available = {name: False for name in _TUI_INSPECTOR_TABS}
    available["Summary"] = True
    target = _tui_viewer_target(state)

    if target == "right":
        item = _tui_selected(state, "right")
        if item is not None:
            if item["kind"] == "member":
                # One decode gives us a conservative capability map that
                # mirrors what the Data/Keys views can actually display.
                try:
                    detail = _tui_member_lines(state, item)
                except Exception:
                    detail = []
                available["Data"] = any(
                    line.strip().startswith(("Source records:", "Database records"))
                    for line in detail
                )
                available["Keys"] = any(
                    line.strip() == "Recovered keyed access path"
                    for line in detail
                )
                available["Storage"] = any(
                    line.strip() == "Recovered storage"
                    for line in detail
                )
                available["Evidence"] = True
                available["Raw"] = True
            elif item["kind"] == "object":
                obj = item["object"]
                try:
                    detail = _tui_object_lines(state, obj)
                except Exception:
                    detail = []
                available["Data"] = any(
                    line.strip().startswith(("QDLS anchor metadata", "DLO export:"))
                    for line in detail
                )
                available["Storage"] = True
                available["Evidence"] = True
                available["Raw"] = True
            elif item["kind"] == "context-entry":
                entry = item["entry"]
                available["Storage"] = bool(entry.owned_segment_count)
                available["Evidence"] = True
                available["Raw"] = True

    elif target == "mid":
        item = _tui_selected(state, "mid")
        if item is not None and item["kind"] == "file":
            file_obj = item.get("object")
            available["Storage"] = bool(file_obj is not None or item.get("members"))
            available["Evidence"] = True
            available["Raw"] = file_obj is not None

    elif target == "left":
        item = _tui_selected(state, "left")
        if item is not None and item["kind"] == "library":
            available["Evidence"] = True
            available["Storage"] = item.get("object") is not None
            available["Raw"] = item.get("object") is not None
            try:
                available["Keys"] = (
                    _tui_context_traversal(state, item["library"]) is not None
                )
            except Exception:
                available["Keys"] = False

    cache[key] = available
    return available


def _tui_preferred_inspector_tab(state):
    """Choose the most useful view for the current logical selection."""

    available = _tui_inspector_availability(state)
    target = _tui_viewer_target(state)
    if target == "right":
        item = _tui_selected(state, "right")
        if item is not None:
            if item["kind"] == "member" and available["Data"]:
                return "Data"
            if item["kind"] == "context-entry" and available["Evidence"]:
                return "Evidence"
            if item["kind"] == "object" and available["Data"]:
                return "Data"

    for name in ("Summary", "Data", "Evidence", "Storage", "Keys", "Raw"):
        if available.get(name):
            return name
    return "Summary"


def _tui_apply_default_inspector(state):
    """Apply a context-sensitive default after the logical selection changes."""

    preferred = _tui_preferred_inspector_tab(state)
    state["inspector_tab"] = _TUI_INSPECTOR_TABS.index(preferred)
    state["viewer_scroll"] = 0
    return preferred


def _tui_draw_inspector_tabs(screen, y, width, state, focused):
    """Draw compact inspector tabs and return the rendered text width."""

    import curses

    x = 0
    active = _tui_inspector_tab(state)
    availability = _tui_inspector_availability(state)
    for index, name in enumerate(_TUI_INSPECTOR_TABS):
        label = f" {index + 1}:{name} "
        if name == active:
            # Selection stays unmistakable even while keyboard focus remains
            # in one of the navigation panes.
            attr = curses.A_BOLD | curses.A_REVERSE
        elif availability.get(name, False):
            attr = curses.A_NORMAL
        else:
            attr = curses.A_DIM
        if focused and name == active:
            attr |= curses.A_UNDERLINE
        if x + len(label) >= width:
            break
        _tui_safe_addstr(screen, y, x, label, attr)
        x += len(label) + 1
    return x


def _tui_picker_entries(directory):
    directory = Path(directory).resolve()
    directories = []
    files = []

    try:
        entries = list(directory.iterdir())
    except OSError:
        return []

    for entry in entries:
        try:
            if entry.is_dir():
                if not entry.name.startswith("."):
                    directories.append(entry)
            elif (
                entry.is_file()
                and entry.suffix.lower() in DASD_IMAGE_SUFFIXES
            ):
                files.append(entry)
        except OSError:
            continue

    directories.sort(key=lambda item: item.name.lower())
    files.sort(key=lambda item: item.name.lower())

    result = []
    if directory.parent != directory:
        result.append((directory.parent, True))
    result.extend((entry, True) for entry in directories)
    result.extend((entry, False) for entry in files)
    return result


def _tui_help_lines():
    """Built-in DASD browser guide; kept concise enough for terminal use."""

    return [
        "USING THE AS/400 DASD BROWSER",
        "",
        "Screen layout",
        "  Breadcrumb       Current image > library > file/type > member/object.",
        "  Library / view   Choose an AS/400 library or an aggregate recovery view.",
        "  File / type      Choose a file or MI object type within that scope.",
        "  Member / object  Choose the concrete member, object, or [dir] identity.",
        "  Inspector        Summary / Data / Keys / Storage / Evidence / Raw.",
        "",
        "Inspector views",
        "  Summary   Human-facing identity, role, and high-value recovery status.",
        "  Data      Source lines, database records, or decoded document metadata.",
        "  Keys      QDDSI keyed access paths or a library context machine index.",
        "  Storage   QDDS/QDDSI relationships and recovered segment groups.",
        "  Evidence  Why the browser assigned an identity/library; disagreements.",
        "  Raw       Bounded hex/EBCDIC forensic bytes; never interpreted as source.",
        "  A dim view has no meaningful data for the current selection. It remains",
        "  selectable so the browser can explicitly explain the absence.",
        "",
        "Recovery terminology",
        "  recovered primary/object",
        "    The object's primary on-disk structure and identity were recovered.",
        "    This does NOT guarantee every secondary/owned byte of the original",
        "    object survives on the imaged disk.",
        "  [dir]  Directory-only identity. The library context proves the object",
        "    existed and preserves useful name/type/address evidence, but its",
        "    primary object is not recovered on this image.",
        "  [ctx]  The recovered primary's library assignment comes from the",
        "    context index because the EPA back-pointer direction was unavailable.",
        "  !      Independent EPA and context-index membership evidence disagrees.",
        "  member-only",
        "    A member cursor survived even though its owning *FILE primary did not.",
        "",
        "AS/400 storage/database terms",
        "  context / library",
        "    A permanent context is the MI namespace underlying an AS/400 library.",
        "    Its machine index maps named objects to internal addresses.",
        "  member cursor",
        "    The 0D/50 object representing a database/source file member and its",
        "    links to backing storage such as QDDS and QDDSI.",
        "  QDDS",
        "    Data Space backing member records/source data when independently",
        "    recoverable.",
        "  QDDSI",
        "    Data Space Index describing keyed access paths into QDDS records.",
        "  DENT",
        "    Data Space Entry Status byte. 0x80 and 0xC0 have validated live/deleted",
        "    behavior on the real V2R3 corpus; other bit meanings remain cautious.",
        "  keyed order",
        "    Record order reconstructed from QDDSI. Keys can occasionally be partial",
        "    when the physical index stores compressed/indirect key material.",
        "  arrival / RRN order",
        "    Independent physical/logical record-number order from the QDDS stream.",
        "",
        "Navigation",
        "  Tab / Left / Right       change pane",
        "  Up / Down                move selection or scroll inspector/help",
        "  PgUp / PgDn, Home / End  page or jump through the focused view",
        "  Enter                    drill to the next pane / inspector",
        "  [ / ]                    previous / next inspector view",
        "  1..6                     Summary / Data / Keys / Storage / Evidence / Raw",
        "  /                        search object/member/file names",
        "  e                        export a validated QDOC/*DOCBSS workstation file",
        "  o                        open another DASD image",
        "  r                        rescan the current image",
        "  ? or h                   this help",
        "  q or Esc                 quit",
        "",
        "All DASD browsing is read-only. Export writes a separate output file and",
        "never modifies the source disk image.",
    ]


def _tui_help(stdscr):
    """Scrollable modal help/terminology page."""

    import curses

    lines = _tui_help_lines()
    scroll = 0
    while True:
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        _tui_safe_addstr(
            stdscr,
            0,
            0,
            " AS/400 DASD Browser Help ",
            curses.A_BOLD | curses.A_REVERSE,
        )
        visible = max(1, height - 3)
        max_scroll = max(0, len(lines) - visible)
        scroll = max(0, min(scroll, max_scroll))

        for row, line in enumerate(lines[scroll : scroll + visible]):
            attr = 0
            if line and not line.startswith(" ") and line.isalpha():
                attr = curses.A_BOLD
            _tui_safe_addstr(stdscr, 1 + row, 0, line, attr)

        _tui_safe_addstr(
            stdscr,
            height - 1,
            0,
            (
                "Up/Down PgUp/PgDn Home/End scroll   "
                "Enter/?/h/q/Esc close help"
            ),
            curses.A_REVERSE,
        )
        stdscr.refresh()
        key = stdscr.getch()

        if key in (
            27,
            10,
            13,
            curses.KEY_ENTER,
            ord("?"),
            ord("h"),
            ord("H"),
            ord("q"),
            ord("Q"),
        ):
            return
        if key == curses.KEY_UP:
            scroll = max(0, scroll - 1)
        elif key == curses.KEY_DOWN:
            scroll = min(max_scroll, scroll + 1)
        elif key == curses.KEY_PPAGE:
            scroll = max(0, scroll - max(1, visible - 2))
        elif key == curses.KEY_NPAGE:
            scroll = min(max_scroll, scroll + max(1, visible - 2))
        elif key == curses.KEY_HOME:
            scroll = 0
        elif key == curses.KEY_END:
            scroll = max_scroll


def _tui_file_picker(stdscr, start_dir):
    """Single-file curses picker for raw DASD images."""
    import curses

    directory = Path(start_dir).expanduser()
    if not directory.is_dir():
        directory = Path.cwd()
    directory = directory.resolve()
    selected = 0
    status = ""

    while True:
        entries = _tui_picker_entries(directory)
        if entries:
            selected = max(0, min(selected, len(entries) - 1))
        else:
            selected = 0

        stdscr.erase()
        height, width = stdscr.getmaxyx()
        _tui_safe_addstr(
            stdscr,
            0,
            0,
            " Open AS/400 DASD image ",
            curses.A_BOLD | curses.A_REVERSE,
        )
        _tui_safe_addstr(
            stdscr,
            1,
            0,
            f"Directory: {directory}",
            curses.A_BOLD,
        )

        list_y = 3
        visible = max(1, height - 7)
        start = _tui_list_start(
            len(entries),
            selected,
            visible,
        )

        if not entries:
            _tui_safe_addstr(
                stdscr,
                list_y,
                2,
                "(no .hda/.img/.dsk/.raw/.bin images or subdirectories)",
            )
        else:
            for row, idx in enumerate(
                range(
                    start,
                    min(len(entries), start + visible),
                )
            ):
                path, is_dir = entries[idx]
                is_parent = (
                    is_dir
                    and path == directory.parent
                    and path != directory
                )
                if is_parent:
                    label = "<DIR> ../"
                elif is_dir:
                    label = f"<DIR> {path.name}/"
                else:
                    label = path.name
                attr = (
                    curses.A_REVERSE
                    if idx == selected
                    else 0
                )
                _tui_safe_addstr(
                    stdscr,
                    list_y + row,
                    0,
                    label,
                    attr,
                )

        _tui_safe_addstr(
            stdscr,
            height - 3,
            0,
            status,
            curses.A_DIM,
        )
        _tui_safe_addstr(
            stdscr,
            height - 2,
            0,
            "Enter: open  Backspace: parent",
        )
        _tui_safe_addstr(
            stdscr,
            height - 1,
            0,
            "↑/↓ PgUp/PgDn Home/End: navigate   Esc/q: cancel",
            curses.A_REVERSE,
        )
        stdscr.refresh()

        key = stdscr.getch()

        if key in (27, ord("q"), ord("Q")):
            return None
        if key in (curses.KEY_BACKSPACE, 127, 8):
            parent = directory.parent
            if parent != directory:
                directory = parent
                selected = 0
                status = ""
            continue
        if key == curses.KEY_UP:
            selected = max(0, selected - 1)
            continue
        if key == curses.KEY_DOWN:
            selected = min(
                max(0, len(entries) - 1),
                selected + 1,
            )
            continue
        if key == curses.KEY_PPAGE:
            selected = max(0, selected - visible)
            continue
        if key == curses.KEY_NPAGE:
            selected = min(
                max(0, len(entries) - 1),
                selected + visible,
            )
            continue
        if key == curses.KEY_HOME:
            selected = 0
            continue
        if key == curses.KEY_END:
            selected = max(0, len(entries) - 1)
            continue

        if not entries:
            continue

        path, is_dir = entries[selected]
        if key in (10, 13, curses.KEY_ENTER):
            if is_dir:
                directory = path.resolve()
                selected = 0
                status = ""
                continue
            return str(path.resolve())


def _tui_loading_screen(stdscr, path, stage):
    import curses

    stdscr.erase()
    height, width = stdscr.getmaxyx()
    title = " AS/400 CISC DASD Browser "
    _tui_safe_addstr(
        stdscr,
        0,
        0,
        title,
        curses.A_BOLD | curses.A_REVERSE,
    )
    _tui_safe_addstr(
        stdscr,
        2,
        2,
        f"Image: {path}",
        curses.A_BOLD,
    )
    _tui_safe_addstr(stdscr, 4, 2, stage)
    _tui_safe_addstr(
        stdscr,
        6,
        2,
        "Read-only: the disk image will not be modified.",
        curses.A_DIM,
    )
    stdscr.refresh()


def _tui_build_state(stdscr, path):
    path = os.path.realpath(
        os.path.abspath(os.path.expanduser(str(path)))
    )

    _tui_loading_screen(
        stdscr,
        path,
        "Opening image and validating 520-byte geometry…",
    )
    image = _open(path)

    _tui_loading_screen(
        stdscr,
        path,
        "Pass 1/3: scanning storage headers and reconstructing extents…",
    )
    scan = image.scan()

    _tui_loading_screen(
        stdscr,
        path,
        "Pass 2/3: reconstructing permanent segment groups…",
    )
    segments = image.recover_segments(scan)

    _tui_loading_screen(
        stdscr,
        path,
        "Pass 3/3: recovering EPA objects, libraries, files, and members…",
    )
    inventory = image.recover_objects(scan, segments)

    state = {
        "image": image,
        "scan": scan,
        "segments": segments,
        "inventory": inventory,
        "left_index": 0,
        "mid_index": 0,
        "right_index": 0,
        "focus": 0,
        "viewer_scroll": 0,
        "inspector_tab": 0,
        "inspector_availability_cache": {},
        "viewer_cache": {},
        "left_items": [],
        "mid_items": [],
        "right_items": [],
        "status": "",
    }
    _tui_build_left_items(state)
    _tui_rebuild_from_left(state)
    return state


def _tui_build_left_items(state):
    inventory = state["inventory"]
    library_counts = {}
    for obj in inventory.objects:
        if obj.library_name:
            library_counts[obj.library_name.upper()] = (
                library_counts.get(obj.library_name.upper(), 0) + 1
            )

    items = [
        {
            "kind": "objects-view",
            "label": f"<ALL OBJECTS>  {len(inventory.objects):,}",
        },
        {
            "kind": "orphans-view",
            "label": "<ORPHANS / MEMBER-ONLY>",
        },
    ]

    for library in inventory.libraries:
        count = library_counts.get(library.name.upper(), 0)
        items.append(
            {
                "kind": "library",
                "label": f"{library.name}  {count:,}",
                "library": library.name,
                "object": library,
            }
        )
    state["left_items"] = items


def _tui_file_items(state, library_name):
    inventory = state["inventory"]
    orphan_mode = library_name is None

    if orphan_mode:
        members = [
            obj
            for obj in inventory.members()
            if obj.library_name is None
        ]
        file_objects = [
            obj
            for obj in inventory.objects
            if (
                obj.library_name is None
                and obj.object_type == 0x19
                and obj.object_subtype == 0x01
            )
        ]
    else:
        members = inventory.members(library=library_name)
        file_objects = [
            obj
            for obj in inventory.in_library(library_name)
            if (
                obj.object_type == 0x19
                and obj.object_subtype == 0x01
            )
        ]

    member_map = {}
    for member in members:
        member_map.setdefault(
            member.member_file_name.upper(),
            [],
        ).append(member)

    object_map = {}
    for obj in file_objects:
        object_map.setdefault(obj.name.upper(), obj)

    names = sorted(set(member_map) | set(object_map))
    result = []
    for name in names:
        file_obj = object_map.get(name)
        file_members = sorted(
            member_map.get(name, []),
            key=lambda obj: (
                obj.member_name,
                obj.segment.virtual_address,
            ),
        )
        marker = "" if file_obj is not None else "  [member-only]"
        result.append(
            {
                "kind": "file",
                "name": name,
                "library": library_name,
                "object": file_obj,
                "members": file_members,
                "label": (
                    f"{name:<10}  "
                    f"{len(file_members):>4}"
                    f"{marker}"
                ),
            }
        )
    return result


def _tui_library_items(state, library_name):
    """Files plus object-type groups for one recovered library.

    Directory-only context terminals are grouped beside recovered objects by
    MI type/subtype instead of being hidden in a separate catch-all bucket.
    This lets an incomplete disk present the namespace the AS/400 knew while
    still marking entries whose primary object is not recovered.
    """

    inventory = state["inventory"]
    result = _tui_file_items(state, library_name)

    groups = {}
    for obj in inventory.in_library(library_name):
        # Files and members already have the normal file/member navigation.
        if (
            (obj.object_type == 0x19 and obj.object_subtype == 0x01)
            or obj.is_member_cursor
        ):
            continue
        key = (obj.object_type, obj.object_subtype)
        groups.setdefault(key, {"objects": [], "entries": []})["objects"].append(
            obj
        )

    for entry in inventory.unresolved_context_entries(library_name):
        key = (entry.object_type, entry.object_subtype)
        groups.setdefault(key, {"objects": [], "entries": []})["entries"].append(
            entry
        )

    for key in sorted(groups):
        objects = sorted(
            groups[key]["objects"],
            key=lambda obj: (
                obj.name,
                obj.segment.virtual_address,
            ),
        )
        entries = sorted(
            groups[key]["entries"],
            key=lambda entry: (
                entry.display_name_hint or "",
                (
                    entry.object_address.address
                    if entry.object_address is not None
                    else 0
                ),
            ),
        )
        sample = objects[0] if objects else None
        hint = sample.external_type_hint if sample is not None else ""
        suffix = f" {hint}" if hint else ""
        count_text = f"{len(objects):,}"
        if entries:
            count_text += f" + {len(entries):,} dir"
        result.append(
            {
                "kind": "library-object-type",
                "library": library_name,
                "type": key[0],
                "subtype": key[1],
                "objects": objects,
                "entries": entries,
                "label": (
                    f"{key[0]:02X}/{key[1]:02X}"
                    f"{suffix:<10}  {count_text}"
                ),
            }
        )

    return result


def _tui_object_type_items(state):
    """Group recovered and directory-only objects by MI type/subtype."""

    inventory = state["inventory"]
    groups = {}
    for obj in inventory.objects:
        key = (obj.object_type, obj.object_subtype)
        groups.setdefault(key, {"objects": [], "entries": []})["objects"].append(
            obj
        )
    for entry in inventory.unresolved_context_entries():
        key = (entry.object_type, entry.object_subtype)
        groups.setdefault(key, {"objects": [], "entries": []})["entries"].append(
            entry
        )

    result = []
    for key in sorted(groups):
        objects = sorted(
            groups[key]["objects"],
            key=lambda obj: (
                obj.library_name or "",
                obj.name,
                obj.segment.virtual_address,
            ),
        )
        entries = sorted(
            groups[key]["entries"],
            key=lambda entry: (
                entry.library_name,
                entry.display_name_hint or "",
                (
                    entry.object_address.address
                    if entry.object_address is not None
                    else 0
                ),
            ),
        )
        sample = objects[0] if objects else None
        hint = sample.external_type_hint if sample is not None else ""
        suffix = f" {hint}" if hint else ""
        count_text = f"{len(objects):,}"
        if entries:
            count_text += f" + {len(entries):,} dir"
        result.append(
            {
                "kind": "object-type",
                "type": key[0],
                "subtype": key[1],
                "objects": objects,
                "entries": entries,
                "label": (
                    f"{key[0]:02X}/{key[1]:02X}"
                    f"{suffix:<10}  {count_text}"
                ),
            }
        )
    return result


def _tui_rebuild_from_left(state):
    left_items = state["left_items"]
    if not left_items:
        state["mid_items"] = []
        state["right_items"] = []
        return

    state["left_index"] = max(
        0,
        min(state["left_index"], len(left_items) - 1),
    )
    selected = left_items[state["left_index"]]

    if selected["kind"] == "library":
        state["mid_items"] = _tui_library_items(
            state,
            selected["library"],
        )
    elif selected["kind"] == "orphans-view":
        state["mid_items"] = _tui_file_items(
            state,
            None,
        )
    else:
        state["mid_items"] = _tui_object_type_items(state)

    state["mid_index"] = 0
    state["right_index"] = 0
    state["viewer_scroll"] = 0
    _tui_rebuild_from_mid(state)


def _tui_object_display_identity(obj):
    """Human-facing logical identity used for navigation/sorting."""

    if getattr(obj, "is_member_cursor", False):
        file_name = getattr(obj, "member_file_name", "") or "<file?>"
        member_name = getattr(obj, "member_name", "") or obj.name
        return f"{file_name}({member_name})"
    return obj.name


def _tui_group_right_items(selected):
    """Build one identity-first mixed recovered/directory object list."""

    result = []
    for obj in selected.get("objects", ()):
        library = obj.library_name or "<orphan>"
        hint = obj.external_type_hint or obj.type_code
        epa_library = getattr(obj, "epa_library_name", None)
        context_libraries = tuple(
            getattr(obj, "context_library_names", ()) or ()
        )
        marker = ""
        if (
            epa_library
            and context_libraries
            and epa_library not in context_libraries
        ):
            marker = "  !"
        elif epa_library is None and len(context_libraries) == 1:
            marker = "  [ctx]"
        identity = _tui_object_display_identity(obj)
        result.append(
            {
                "kind": "object",
                "object": obj,
                "label": f"{library}/{identity}  {hint}{marker}",
                "_sort": (
                    library.upper(),
                    identity.upper(),
                    0,
                    obj.segment.virtual_address,
                ),
            }
        )

    for entry in selected.get("entries", ()):
        library = (
            getattr(entry, "library_name", None)
            or selected.get("library")
            or "<unknown>"
        )
        name = entry.display_name_hint or "<name undecoded>"
        surviving = " +seg" if entry.owned_segment_count else ""
        result.append(
            {
                "kind": "context-entry",
                "entry": entry,
                "label": f"{library}/{name}  {entry.type_code}  [dir]{surviving}",
                "_sort": (
                    library.upper(),
                    name.upper(),
                    1,
                    (
                        entry.object_address.address
                        if entry.object_address is not None
                        else 0
                    ),
                ),
            }
        )

    result.sort(key=lambda item: item["_sort"])
    for item in result:
        item.pop("_sort", None)
    return result


def _tui_rebuild_from_mid(state):
    mid_items = state["mid_items"]
    if not mid_items:
        state["right_items"] = []
        return

    state["mid_index"] = max(
        0,
        min(state["mid_index"], len(mid_items) - 1),
    )
    selected = mid_items[state["mid_index"]]

    if selected["kind"] == "file":
        result = []
        for member in selected["members"]:
            info = state["image"].read_member_info(member)
            source_type = (
                info.member_type if info is not None else ""
            )
            suffix = f"  {source_type}" if source_type else ""
            epa_library = getattr(member, "epa_library_name", None)
            context_libraries = tuple(
                getattr(member, "context_library_names", ()) or ()
            )
            marker = ""
            if (
                epa_library
                and context_libraries
                and epa_library not in context_libraries
            ):
                marker = "  !"
            elif epa_library is None and len(context_libraries) == 1:
                marker = "  [ctx]"
            result.append(
                {
                    "kind": "member",
                    "object": member,
                    "file": selected,
                    "source_type": source_type,
                    "label": f"{member.member_name}{suffix}{marker}",
                }
            )
        state["right_items"] = result
    elif selected["kind"] == "context-directory":
        result = []
        for entry in selected["entries"]:
            name = entry.display_name_hint or "<name undecoded>"
            surviving = (
                f"  owned-segments={entry.owned_segment_count}"
                if entry.owned_segment_count
                else ""
            )
            result.append(
                {
                    "kind": "context-entry",
                    "entry": entry,
                    "label": (
                        f"{name}  {entry.type_code}{surviving}"
                    ),
                }
            )
        state["right_items"] = result
    elif selected["kind"] == "search-group":
        state["right_items"] = list(selected.get("search_items", ()))
    else:
        state["right_items"] = _tui_group_right_items(selected)

    state["right_index"] = 0
    state["viewer_scroll"] = 0


def _tui_selected(state, key):
    items = state[key + "_items"]
    index = state[key + "_index"]
    if not items:
        return None
    index = max(0, min(index, len(items) - 1))
    return items[index]


def _dlo_export_pair(inventory, obj):
    """Return a unique (QDOC *DOC, *DOCBSS) pair for a selected object.

    Selection may be either the QDOC document or its observed same-base
    SYSOBJNAM+"F" IBM *DOCBSS companion. The name relationship is an
    observed V2R3 convention; byte extraction is separately validated by
    DASDImage.read_document_byte_string().
    """

    if obj is None:
        return None, None, "no object selected"

    doc = None
    companion = None

    if (
        obj.object_type == 0x19
        and obj.object_subtype == 0x0E
        and (obj.library_name or "").upper() == "QDOC"
    ):
        doc = obj
        companion_name = obj.name.upper() + "F"
        companions = [
            candidate
            for candidate in inventory.objects
            if (
                candidate.object_type == 0x06
                and candidate.object_subtype == 0xC1
                and candidate.name.upper() == companion_name
            )
        ]
        if not companions:
            return doc, None, (
                f"no recovered *DOCBSS companion named {companion_name}"
            )
        if len(companions) != 1:
            return doc, None, (
                f"{len(companions)} *DOCBSS companions named "
                f"{companion_name}; export is ambiguous"
            )
        companion = companions[0]
        return doc, companion, ""

    if obj.object_type == 0x06 and obj.object_subtype == 0xC1:
        name = obj.name.upper()
        if not name.endswith("F") or len(name) < 2:
            return None, obj, (
                "selected *DOCBSS does not use the observed SYSOBJNAM+'F' "
                "name form"
            )
        sysobjnam = name[:-1]
        docs = [
            candidate
            for candidate in inventory.objects
            if (
                candidate.object_type == 0x19
                and candidate.object_subtype == 0x0E
                and (candidate.library_name or "").upper() == "QDOC"
                and candidate.name.upper() == sysobjnam
            )
        ]
        if not docs:
            return None, obj, (
                f"no recovered QDOC *DOC named {sysobjnam}"
            )
        if len(docs) != 1:
            return None, obj, (
                f"{len(docs)} QDOC *DOC objects named {sysobjnam}; "
                "export is ambiguous"
            )
        return docs[0], obj, ""

    return None, None, (
        "export applies to a QDOC *DOC or its IBM *DOCBSS companion"
    )


def _tui_dlo_export_selection(state):
    right = _tui_selected(state, "right")
    if right is None or right.get("kind") != "object":
        return None, None, "select a QDOC document or *DOCBSS object first"
    return _dlo_export_pair(
        state["inventory"],
        right["object"],
    )


def _tui_prompt_text(stdscr, prompt, default=""):
    import curses

    height, width = stdscr.getmaxyx()
    suffix = f" [{default}]" if default else ""
    label = prompt + suffix + ": "

    curses.echo()
    try:
        curses.curs_set(1)
    except curses.error:
        pass
    try:
        _tui_safe_addstr(
            stdscr,
            height - 1,
            0,
            " " * max(0, width - 1),
        )
        shown = label[-max(1, width - 2):]
        _tui_safe_addstr(
            stdscr,
            height - 1,
            0,
            shown,
            curses.A_REVERSE,
        )
        stdscr.refresh()
        start_x = min(len(shown), max(0, width - 2))
        raw = stdscr.getstr(
            height - 1,
            start_x,
            max(1, width - start_x - 1),
        )
    finally:
        curses.noecho()
        try:
            curses.curs_set(0)
        except curses.error:
            pass

    value = raw.decode(errors="replace").strip()
    return value or default


def _tui_confirm(stdscr, prompt):
    import curses

    height, width = stdscr.getmaxyx()
    label = prompt + " [y/N] "
    _tui_safe_addstr(
        stdscr,
        height - 1,
        0,
        " " * max(0, width - 1),
    )
    _tui_safe_addstr(
        stdscr,
        height - 1,
        0,
        label,
        curses.A_REVERSE,
    )
    stdscr.refresh()
    key = stdscr.getch()
    return key in (ord("y"), ord("Y"))


def _tui_export_selected_dlo(stdscr, state, current_dir):
    doc, companion, error = _tui_dlo_export_selection(state)
    if error:
        state["status"] = "Export unavailable: " + error
        return

    try:
        info, payload = state["image"].read_document_byte_string(
            companion,
            state["segments"],
        )
    except (OSError, ValueError) as exc:
        state["status"] = f"Export validation failed: {exc}"
        return

    default_name = f"{doc.name}.bin"

    # Prefer the QAOSSS14 12-byte short-name field when the selected QDOC
    # object has a unique binary-key correlation. Fall back to the older
    # printable-metadata hint if anchor reconstruction is unavailable.
    anchor_info = _tui_dlo_anchor_info(state, doc)
    anchor_name = ""
    if anchor_info and anchor_info.get("record") is not None:
        anchor_name = anchor_info["record"].short_name
    if anchor_name and _DLO_FILENAME_HINT_RE.fullmatch(anchor_name):
        default_name = anchor_name
    else:
        try:
            doc_data = state["image"].read_segment_bytes(doc.segment)
            filename_hint = _dlo_filename_hint(
                _dlo_preview_strings(
                    doc_data,
                    internal_name=doc.name,
                    limit=20,
                )
            )
        except (OSError, ValueError):
            filename_hint = ""
        if filename_hint:
            default_name = filename_hint

    entered = _tui_prompt_text(
        stdscr,
        "Export workstation bytes to",
        default_name,
    )
    if not entered:
        state["status"] = "Export cancelled"
        return

    output = Path(entered).expanduser()
    if not output.is_absolute():
        output = Path(current_dir) / output
    output = output.resolve()

    image_path = Path(state["image"].path).resolve()
    if output == image_path:
        state["status"] = "Export refused: output path is the DASD image"
        return

    if output.exists():
        if not _tui_confirm(
            stdscr,
            f"Replace {output.name}?",
        ):
            state["status"] = "Export cancelled; existing file left unchanged"
            return

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(payload)
    except OSError as exc:
        state["status"] = f"Export failed: {exc}"
        return

    state["status"] = (
        f"Exported {len(payload):,} bytes from {doc.name}/"
        f"{companion.name} to {output}"
    )


_TUI_OBJECT_TYPE_CONTEXT = {
    (0x02, 0x01): (
        "compiled MI program object; segment/raw browsing is available, "
        "while program-template, instruction-stream, and ODT decoding remain "
        "future work"
    ),
    (0x04, 0x01): (
        "OS/400 *LIB directory for a set of objects; object identity includes "
        "type as well as name. At the MI level this is a permanent context "
        "namespace whose first segment group contains an EPA header and a "
        "machine index of named object addressability."
    ),
    (0x06, 0xC1): (
        "IBM *DOCBSS Document byte string space used by Document Library "
        "Services; a same-named QDOC document may reference its workstation "
        "byte content through this internal object"
    ),
    (0x08, 0x01): (
        "OS/400 user profile object containing security identity and "
        "sign-on/environment attributes; a profile can reference an "
        "associated message queue"
    ),
    (0x0B, 0x90): "internal QDDS data space backing a member record stream",
    (0x0C, 0x90): "internal QDDS index associated with member storage",
    (0x0D, 0x50): "member cursor linking a file/member name to its storage",
    (0x0E, 0x90): (
        "IBM *QDIDX independent index; a library/context uses one to locate "
        "entries in its associated *OIRS object-information repository"
    ),
    (0x19, 0x01): "file object whose members may contain source or database records",
    (0x19, 0x02): (
        "OS/400 message queue object used to receive messages for users, "
        "workstations, programs, or system functions"
    ),
    (0x19, 0x0E): (
        "QDLS document-library document; the QDOC object name is internal "
        "and the user-facing document name may differ"
    ),
    (0x19, 0x12): "QDLS document-library folder stored through QDOC",
    (0x19, 0x51): "record-format metadata associated with a *FILE object",
    (0x19, 0x52): (
        "IBM *OIRS Object Information Repository space associated with a "
        "library/context; stores object-description information for external "
        "objects in that context"
    ),
}


def _tui_object_type_context(object_type, object_subtype):
    return _TUI_OBJECT_TYPE_CONTEXT.get((object_type, object_subtype), "")


# Library descriptions live in an editable JSON catalog rather than in the
# browser code. The repository ships a base catalog; installed copies use the
# XDG data directory, while an optional XDG config file and environment
# override can add or replace entries without modifying the installed file.
_TUI_LIBRARY_CATALOG_CACHE = None


def _tui_library_catalog_paths():
    paths = []

    data_home = os.environ.get("XDG_DATA_HOME")
    if data_home:
        data_dir = Path(data_home)
    else:
        data_dir = Path.home() / ".local" / "share"
    paths.append(
        data_dir / "tape-file-browser" / "as400_libraries.json"
    )

    # When running directly from a source checkout, keep the catalog beside
    # this script so a git checkout is immediately self-contained.
    paths.append(Path(__file__).resolve().with_name("as400_libraries.json"))

    config_home = os.environ.get("XDG_CONFIG_HOME")
    if config_home:
        config_dir = Path(config_home)
    else:
        config_dir = Path.home() / ".config"
    paths.append(
        config_dir / "tape-file-browser" / "as400_libraries.json"
    )

    override = os.environ.get("AS400_DASD_LIBRARY_CONFIG")
    if override:
        paths.append(Path(override).expanduser())

    # Preserve priority while avoiding duplicate reads when source/data paths
    # happen to resolve to the same file.
    result = []
    seen = set()
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def _load_library_catalog(paths=None):
    catalog = {}
    for path in paths or _tui_library_catalog_paths():
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError, TypeError):
            continue

        entries = (
            payload.get("libraries", payload)
            if isinstance(payload, dict)
            else {}
        )
        if not isinstance(entries, dict):
            continue

        for raw_name, raw_entry in entries.items():
            name = str(raw_name).upper()
            if isinstance(raw_entry, str):
                entry = {"description": raw_entry}
            elif isinstance(raw_entry, dict):
                entry = dict(raw_entry)
            else:
                continue

            # Merge fields rather than replacing the whole entry so a user
            # override can change only description/category/status while
            # retaining the remaining base-catalog metadata.
            merged = dict(catalog.get(name, {}))
            merged.update(entry)

            description = merged.get("description")
            if not isinstance(description, str) or not description.strip():
                continue
            merged["description"] = description.strip()

            for key in ("category", "status"):
                value = merged.get(key)
                if isinstance(value, str):
                    merged[key] = value.strip()

            catalog[name] = merged

    return catalog


def _get_library_catalog():
    global _TUI_LIBRARY_CATALOG_CACHE
    if _TUI_LIBRARY_CATALOG_CACHE is None:
        _TUI_LIBRARY_CATALOG_CACHE = _load_library_catalog()
    return _TUI_LIBRARY_CATALOG_CACHE


def _tui_library_context(library_name):
    name = (library_name or "").upper()
    if not name:
        return ""

    entry = _get_library_catalog().get(name)
    if entry is not None:
        description = entry["description"]
        category = entry.get("category")
        status = entry.get("status")

        labels = []
        if isinstance(category, str) and category.strip():
            labels.append(category.strip())
        if (
            isinstance(status, str)
            and status.strip()
            and status.strip() != "documented"
        ):
            labels.append(status.strip())

        if labels:
            return f"[{' · '.join(labels)}] {description}"
        return description

    return (
        f"{name} — AS/400 *LIB object context; purpose is not yet in the "
        "library-description catalog. Source code, when present, lives in "
        "source physical *FILE members rather than in a distinct library type."
    )

def _tui_context_traversal(state, library_name):
    """Cache the recovered machine-index traversal for one library context."""

    name = (library_name or "").upper()
    cache = state.setdefault("context_traversal_cache", {})
    if name in cache:
        return cache[name]

    context = next(
        (
            obj
            for obj in state["inventory"].libraries
            if obj.name.upper() == name
        ),
        None,
    )
    if context is None:
        cache[name] = None
        return None

    try:
        traversal = state["image"].read_context_machine_index(context)
    except Exception:
        traversal = None
    cache[name] = traversal
    return traversal


def _tui_qaosss14_cache(state):
    cache = state.setdefault("qaosss14_cache", {})
    if "records" not in cache:
        member, record_set, records = _load_qaosss14_anchor_records(
            state["image"],
            state["inventory"],
            state["segments"],
        )
        cache["member"] = member
        cache["record_set"] = record_set
        cache["records"] = records
        cache["key_index"] = _qaosss14_key_index(records)
        cache["link_index"] = _qaosss14_link_index(records)
        cache["objects"] = {}
    return cache


def _tui_dlo_anchor_info(state, obj):
    if obj is None:
        return None

    doc = obj
    if obj.object_type == 0x06 and obj.object_subtype == 0xC1:
        matched_doc, _companion, error = _dlo_export_pair(
            state["inventory"],
            obj,
        )
        if error or matched_doc is None:
            return None
        doc = matched_doc

    if not (
        doc.object_type == 0x19
        and doc.object_subtype == 0x0E
        and (doc.library_name or "").upper() == "QDOC"
    ):
        return None

    cache = _tui_qaosss14_cache(state)
    object_cache = cache["objects"]
    key = doc.segment.virtual_address
    if key not in object_cache:
        info = _qaosss14_object_info(
            state["image"],
            doc,
            cache["records"],
            key_index=cache["key_index"],
            link_index=cache["link_index"],
        )
        info["doc"] = doc
        info["member"] = cache["member"]
        object_cache[key] = info
    return object_cache[key]


_TUI_INSPECTOR_TABS = (
    "Summary",
    "Data",
    "Keys",
    "Storage",
    "Evidence",
    "Raw",
)


def _tui_breadcrumb(state):
    """Return the current image/navigation path in human-facing terms."""

    image = state.get("image")
    image_name = (
        os.path.basename(image.path)
        if image is not None and getattr(image, "path", None)
        else "<image>"
    )
    parts = [image_name]

    left = _tui_selected(state, "left")
    mid = _tui_selected(state, "mid")
    right = _tui_selected(state, "right")

    if left is not None:
        if left["kind"] == "library":
            parts.append(left["library"])
        elif left["kind"] == "orphans-view":
            parts.append("ORPHANS")
        elif left["kind"] == "objects-view":
            parts.append("ALL OBJECTS")
        elif left["kind"] == "search-view":
            parts.append("SEARCH")

    if mid is not None:
        if mid["kind"] == "file":
            parts.append(mid["name"])
        elif mid["kind"] in ("library-object-type", "object-type"):
            parts.append(
                f"{mid.get('type', 0):02X}/{mid.get('subtype', 0):02X}"
            )
        elif mid["kind"] == "search-group":
            parts.append("RESULTS")

    if right is not None:
        if right["kind"] == "member":
            parts.append(right["object"].member_name)
        elif right["kind"] == "object":
            parts.append(right["object"].name)
        elif right["kind"] == "context-entry":
            entry = right["entry"]
            parts.append(
                entry.display_name_hint
                or (
                    str(entry.object_address)
                    if entry.object_address is not None
                    else "<directory entry>"
                )
            )

    return " > ".join(parts)


def _tui_inspector_tab(state):
    index = int(state.get("inspector_tab", 0))
    index = max(0, min(index, len(_TUI_INSPECTOR_TABS) - 1))
    return _TUI_INSPECTOR_TABS[index]


def _tui_cycle_inspector_tab(state, delta):
    index = int(state.get("inspector_tab", 0))
    state["inspector_tab"] = (
        index + delta
    ) % len(_TUI_INSPECTOR_TABS)
    state["viewer_scroll"] = 0
    return _tui_inspector_tab(state)


def _tui_context_lines(state):
    """Return one contextual explanation for each navigation pane.

    A selection in a deeper pane must not hide the meaning of its parent
    library or file/object-type selection. Keeping the three explanations
    separate also mirrors the three-pane object hierarchy shown above.
    """

    left = _tui_selected(state, "left")
    mid = _tui_selected(state, "mid")
    right = _tui_selected(state, "right")

    if left is None:
        left_line = "Library/view: no selection"
    elif left["kind"] == "library":
        left_line = (
            f"Library/view: {left['library']} — "
            + _tui_library_context(left["library"])
        )
    elif left["kind"] == "orphans-view":
        left_line = (
            "Library/view: <ORPHANS / MEMBER-ONLY> — object primaries or "
            "member cursors whose library/context is unavailable on this image."
        )
    elif left["kind"] == "search-view":
        left_line = (
            f"Library/view: {left['label']} — global identity search "
            "across libraries, object classes, and directory-only entries."
        )
    else:
        left_line = (
            "Library/view: <ALL OBJECTS> — AS/400 object identities "
            "grouped by MI type/subtype, including [dir] entries."
        )

    if mid is None:
        mid_line = "File/type: no selection"
    elif mid["kind"] == "file":
        source_types = sorted(
            {
                item.get("source_type")
                for item in state["right_items"]
                if item.get("source_type")
            }
        )
        source_suffix = ""
        if source_types:
            shown = ", ".join(source_types[:4])
            if len(source_types) > 4:
                shown += ", …"
            source_suffix = f"; source type(s): {shown}"
        file_context = _tui_file_context(
            mid.get("library"),
            mid["name"],
        )
        if file_context:
            mid_line = (
                f"File/type: *FILE {mid['name']} — {file_context}"
            )
        else:
            mid_line = (
                f"File/type: *FILE {mid['name']} — "
                f"{len(mid['members']):,} member cursor(s)"
                f"{source_suffix}; members are separate *MEM cursors."
            )
    elif mid["kind"] == "context-directory":
        mid_line = (
            "File/type: directory-only context references — "
            f"{len(mid['entries']):,} entry/entries whose object primary "
            "is not recovered on this image."
        )
    elif mid["kind"] == "search-group":
        mid_line = (
            "File/type: search results — "
            f"{len(mid.get('search_items', ())):,} object/directory "
            "identity match(es)."
        )
    else:
        meaning = _tui_object_type_context(
            mid.get("type", 0),
            mid.get("subtype", 0),
        )
        if mid.get("objects"):
            hint = mid["objects"][0].external_type_hint
        else:
            hint = ""
        type_label = hint or (
            f"{mid.get('type', 0):02X}/{mid.get('subtype', 0):02X}"
        )
        if meaning:
            mid_line = f"File/type: {type_label} — {meaning}."
        else:
            mid_line = (
                f"File/type: {type_label} — MI object group."
            )

    if right is None:
        right_line = "Member/object: no selection"
    elif right["kind"] == "member":
        member = right["object"]
        source_type = right.get("source_type") or ""
        source_suffix = (
            f"; source type {source_type}"
            if source_type
            else ""
        )
        right_line = (
            f"Member/object: *MEM "
            f"{member.member_file_name}({member.member_name})"
            f"{source_suffix}; member data is backed by QDDS/QDDSI."
        )
    elif right["kind"] == "context-entry":
        entry = right["entry"]
        name = entry.display_name_hint or "<name undecoded>"
        right_line = (
            f"Member/object: {name}  {entry.type_code} — context-directory "
            "reference; object primary not recovered on this image."
        )
    else:
        obj = right["object"]
        meaning = _tui_object_type_context(
            obj.object_type,
            obj.object_subtype,
        )
        type_label = obj.external_type_hint or obj.type_code
        dlo_info = _tui_dlo_anchor_info(state, obj)
        if dlo_info and dlo_info.get("record") is not None:
            record = dlo_info["record"]
            path = (
                dlo_info.get("anchor_path")
                or record.short_name
            )
            path_note = (
                path
                if dlo_info.get("path_complete")
                else f"{path} (partial)"
            )
            right_line = (
                f"Member/object: {obj.name}  {type_label} — "
                f"QAOSSS14 RRN {record.rrn:,}; anchor hierarchy "
                f"{path_note}."
            )
        elif meaning:
            right_line = (
                f"Member/object: {obj.name}  {type_label} — {meaning}."
            )
        else:
            right_line = (
                f"Member/object: {obj.name}  {type_label} — primary object "
                "is present on this image."
            )

    return left_line, mid_line, right_line


def _tui_context_line(state):
    """Compatibility helper returning the deepest available pane context."""

    return next(
        (
            line
            for line in reversed(_tui_context_lines(state))
            if not line.endswith("no selection")
        ),
        "Member/object: no selection",
    )

def _tui_ebcdic_strings(data, min_length=4):
    """Return printable CP037 runs separated by binary/control data."""

    decoded = data.decode("cp037", errors="replace")
    runs = re.findall(r"[ -~]{" + str(min_length) + r",}", decoded)

    result = []
    previous = None
    for run in runs:
        text = run.strip()
        if not text:
            continue
        if text == previous:
            continue
        result.append(text)
        previous = text
    return result


_TUI_FILE_CONTEXT = {
    ("QGPL", "QAAPFILE"): (
        "IBM AFP Utilities symbol-set symbol-definitions logical file. "
        "A logical file is a database view/access path rather than independent "
        "record storage, so member cursors may legitimately have no QDDS "
        "record stream of their own."
    ),
    ("QGPL", "QAAPFILE$"): (
        "IBM AFP Utilities small symbol-set symbol definitions."
    ),
    ("QGPL", "QAAPFILE#"): (
        "IBM AFP Utilities medium symbol-set symbol definitions."
    ),
    ("QGPL", "QAAPFILE@"): (
        "IBM AFP Utilities large symbol-set symbol definitions."
    ),
}


def _tui_file_context(library_name, file_name):
    key = ((library_name or "").upper(), (file_name or "").upper())
    return _TUI_FILE_CONTEXT.get(key, "")


def _tui_segment_prefix(image, segment, limit=1024):
    """Read a small virtual-order prefix without materializing a large object."""

    if limit <= 0:
        return b""
    result = bytearray()
    for extent in segment.extents:
        for page_index in range(extent.pages):
            if len(result) >= limit:
                return bytes(result[:limit])
            sector = image.read_sector(extent.start_lba + page_index)
            result.extend(sector.data)
    return bytes(result[:limit])


def _tui_hex_lines(data, *, base_offset=0):
    """Format bytes as offset + hex + EBCDIC for AS/400 forensic browsing."""

    lines = []
    for offset in range(0, len(data), 16):
        chunk = data[offset : offset + 16]
        hex_text = " ".join(f"{byte:02X}" for byte in chunk)
        ebcdic = chunk.decode("cp037", errors="replace")
        ebcdic_text = "".join(
            character if character.isprintable() else "."
            for character in ebcdic
        )
        lines.append(
            f"{base_offset + offset:08X}  "
            f"{hex_text:<47}  "
            f"E:{ebcdic_text}"
        )
    return lines


def _tui_owned_segments(state, obj):
    return _object_owned_segments(state["segments"], obj)



def _tui_same_name_objects(
    inventory,
    obj,
    object_type,
    object_subtype,
):
    """Find exact same-name objects of another MI class.

    This is deliberately only a correlation helper. A matching name is useful
    evidence, but does not prove an internal object relationship until the
    relevant pointer/attribute is decoded.
    """

    wanted = obj.name.upper()
    return sorted(
        [
            candidate
            for candidate in inventory.objects
            if candidate is not obj
            and candidate.name.upper() == wanted
            and candidate.object_type == object_type
            and candidate.object_subtype == object_subtype
        ],
        key=lambda candidate: (
            candidate.library_name or "",
            candidate.segment.virtual_address,
        ),
    )



def _tui_msgq_profile_link(inventory, obj):
    """Resolve the observed EPA+0x38 address on a recovered *MSGQ.

    The real B10 JHUDGINS 19/02 object contains an eight-byte internal address
    at EPA+0x38 which exactly matches the owning-object address of the recovered
    JHUDGINS 08/01 *USRPRF. The field's formal IBM name/meaning is not yet
    documented here, so callers must present this as observed correlation rather
    than a decoded architectural attribute.
    """

    if (obj.object_type, obj.object_subtype) != (0x19, 0x02):
        return None, []
    if len(obj.epa.raw) < 0x40:
        return None, []

    pointer = InternalAddress.from_bytes(obj.epa.raw[0x38:0x40])
    if pointer.is_null:
        return pointer, []

    matches = sorted(
        [
            candidate
            for candidate in inventory.objects
            if (candidate.object_type, candidate.object_subtype) == (0x08, 0x01)
            and candidate.segment.header.owner.key == pointer.key
        ],
        key=lambda candidate: (
            candidate.library_name or "",
            candidate.name,
            candidate.segment.virtual_address,
        ),
    )
    return pointer, matches

def _tui_profile_queue_lines(state, obj):
    """Semantic-first view for *USRPRF and *MSGQ objects."""

    pair = (obj.object_type, obj.object_subtype)
    if pair == (0x08, 0x01):
        title = "User profile semantic view"
        counterpart_type = (0x19, 0x02)
        counterpart_label = "*MSGQ"
        explanation = (
            "  This is the recovered user-profile object. Security/profile "
            "fields are not named until their CISC layout is independently "
            "corroborated."
        )
    else:
        title = "Message queue semantic view"
        counterpart_type = (0x08, 0x01)
        counterpart_label = "*USRPRF"
        explanation = (
            "  This is the recovered message-queue object. Queue entries are "
            "not yet decoded as individual OS/400 messages."
        )

    counterparts = _tui_same_name_objects(
        state["inventory"],
        obj,
        counterpart_type[0],
        counterpart_type[1],
    )

    lines = ["", title, explanation]

    direct_pointer = None
    direct_profiles = []
    if pair == (0x19, 0x02):
        direct_pointer, direct_profiles = _tui_msgq_profile_link(
            state["inventory"],
            obj,
        )
        if direct_pointer is not None:
            lines.append(
                f"  Observed EPA+0x38 internal address: {direct_pointer}"
            )
            if direct_profiles:
                lines.append("  Address-resolved *USRPRF target:")
                for candidate in direct_profiles[:8]:
                    context = candidate.library_name or "<unresolved context>"
                    lines.append(
                        f"    {context}/{candidate.name}  "
                        f"VA {candidate.segment.virtual_address:012X}"
                    )
                lines.append(
                    "  Evidence note: the real B10 JHUDGINS sample resolves "
                    "this address exactly to its same-name *USRPRF owner "
                    "address. The formal meaning/name of EPA+0x38 remains "
                    "undecoded."
                )
            elif not direct_pointer.is_null:
                lines.append(
                    "  Address-resolved *USRPRF target: not recovered on "
                    "this image."
                )

    if counterparts:
        same_as_direct = (
            direct_profiles
            and {id(candidate) for candidate in counterparts}
            == {id(candidate) for candidate in direct_profiles}
        )
        if not same_as_direct:
            lines.append(f"  Same-name {counterpart_label} correlation:")
            for candidate in counterparts[:8]:
                context = candidate.library_name or "<unresolved context>"
                lines.append(
                    f"    {context}/{candidate.name}  "
                    f"VA {candidate.segment.virtual_address:012X}"
                )
            if len(counterparts) > 8:
                lines.append(
                    f"    ... {len(counterparts) - 8:,} additional match(es)"
                )
        lines.append(
            "  Relationship note: OS/400's default MSGQ(*USRPRF) convention "
            "uses a same-name user-profile message queue. Name correlation "
            "alone is not treated as a decoded linkage field."
        )
    else:
        lines.append(
            f"  Same-name {counterpart_label}: not recovered on this image."
        )

    owned = _tui_owned_segments(state, obj)
    lines.append(f"  Recovered owned segments: {len(owned):,}")
    for segment in owned[:16]:
        role = "primary" if segment.is_primary else "secondary"
        lines.append(
            f"    type {segment.header.segment_type:04X}  "
            f"VA {segment.virtual_address:012X}  "
            f"LBA {segment.start_lba:>9,}  "
            f"{segment.pages:>6,} pages  {role}"
        )
    if len(owned) > 16:
        lines.append(
            f"    ... {len(owned) - 16:,} additional owned segments"
        )

    seen = set()
    hints = []
    for segment in owned[:8]:
        try:
            prefix = _tui_segment_prefix(
                state["image"],
                segment,
                limit=1024,
            )
        except Exception:
            continue
        for value in _tui_ebcdic_strings(prefix, min_length=5):
            value = value.strip()
            if not value or value in seen:
                continue
            seen.add(value)
            hints.append((segment, value[:160]))
            if len(hints) >= 24:
                break
        if len(hints) >= 24:
            break

    if hints:
        lines.extend(
            [
                "",
                "  Bounded EBCDIC text hints from owned segments",
                (
                    "  (forensic strings only; not decoded profile fields or "
                    "message entries)"
                ),
            ]
        )
        for segment, value in hints:
            lines.append(
                f"    {segment.header.segment_type:04X}/"
                f"{segment.virtual_address:012X}: {value}"
            )

    try:
        primary_prefix = _tui_segment_prefix(
            state["image"],
            obj.segment,
            limit=256,
        )
    except Exception as exc:
        primary_prefix = b""
        lines.extend(["", f"  Raw preview error: {exc}"])

    if primary_prefix:
        lines.extend(
            [
                "",
                "  Raw primary-segment prefix (first 256 bytes)",
                "  Offset    Hex                                              EBCDIC",
            ]
        )
        lines.extend(
            "  " + line
            for line in _tui_hex_lines(primary_prefix)
        )

    return lines


def _tui_file_format_evidence(state, file_obj):
    """Explain the literal FCB evidence used for 19/51 format association."""

    try:
        references = state["image"].file_format_references(
            file_obj,
            state["inventory"],
        )
    except Exception as exc:
        return [
            "FCB record-format evidence",
            "",
            f"Unable to inspect the *FILE primary: {exc}",
        ]

    lines = ["FCB record-format evidence"]
    if not references:
        lines.extend(
            [
                "  No exact recovered 19/51 format-name occurrence was found",
                "  in the *FILE primary.",
            ]
        )
        return lines

    for reference in references:
        name_offsets = ", ".join(
            f"0x{offset:X}" for offset in reference.name_offsets[:8]
        )
        if len(reference.name_offsets) > 8:
            name_offsets += (
                f", ... ({len(reference.name_offsets):,} occurrences)"
            )

        if reference.address_offsets:
            address_offsets = ", ".join(
                f"0x{offset:X}" for offset in reference.address_offsets[:8]
            )
            if len(reference.address_offsets) > 8:
                address_offsets += (
                    f", ... ({len(reference.address_offsets):,} occurrences)"
                )
            address_text = f"internal address @ {address_offsets}"
        else:
            address_text = "internal address not found"

        lines.append(
            f"  {reference.format_object.name}: "
            f"name @ {name_offsets}; {address_text}"
        )

    lines.extend(
        [
            "",
            (
                "  These are literal byte matches in the recovered *FILE FCB. "
                "They support format association without assigning undocumented "
                "FCB field names; an internal-address match is independent "
                "corroboration when present."
            ),
        ]
    )
    return lines


def _tui_file_storage_evidence(state, file_item, *, formats=None):
    """Summarize recovered *FILE storage without guessing file semantics."""

    image = state["image"]
    inventory = state["inventory"]
    segments = state["segments"]
    members = file_item["members"]
    file_obj = file_item["object"]

    if formats is None:
        formats = []
        if file_obj is not None:
            try:
                formats = image.resolve_file_formats(
                    file_obj,
                    inventory,
                )
            except Exception:
                formats = []

    source_types = set()
    qdds_count = 0
    qddsi_count = 0
    unresolved_count = 0

    for member in members:
        try:
            info = image.read_member_info(member)
        except Exception:
            info = None
        if info is not None and info.member_type:
            source_types.add(info.member_type)

        try:
            storage = image.resolve_member_storage(
                member,
                inventory,
                segments,
            )
        except Exception:
            unresolved_count += 1
            continue

        if storage.data_space is not None:
            qdds_count += 1
        else:
            unresolved_count += 1
        if storage.data_index is not None:
            qddsi_count += 1

    documented_context = _tui_file_context(
        file_item["library"],
        file_item["name"],
    )
    documented_logical = (
        bool(documented_context)
        and "logical file" in documented_context.lower()
    )

    if documented_logical:
        interpretation = (
            "Documented logical/access-path file; independent member QDDS "
            "record storage is not required."
        )
    elif source_types and qdds_count:
        interpretation = (
            "Source physical-file evidence: source-member metadata and "
            "recovered QDDS record storage are both present."
        )
    elif formats and qdds_count:
        interpretation = (
            "Formatted database file with recovered member record storage. "
            "This evidence alone does not distinguish every physical/logical "
            "file variant."
        )
    elif qdds_count:
        interpretation = (
            "Recovered member QDDS record storage is present, but no record "
            "format object was resolved."
        )
    elif members:
        interpretation = (
            "No independent member QDDS record stream was recovered. This can "
            "reflect logical/access-path behavior or an incomplete capture."
        )
    else:
        interpretation = "No recovered members are available to classify."

    lines = [
        "Storage evidence",
        f"  Recovered members:        {len(members):,}",
        f"  QDDS data space(s):       {qdds_count:,}/{len(members):,}",
        f"  QDDSI index object(s):    {qddsi_count:,}/{len(members):,}",
        f"  Resolved format object(s): {len(formats):,}",
    ]
    if formats:
        lines.append(
            "  Format name(s):           "
            + ", ".join(format_obj.name for format_obj in formats[:12])
        )
    if source_types:
        lines.append(
            "  Source member type(s):    "
            + ", ".join(sorted(source_types))
        )
    if unresolved_count:
        lines.append(
            f"  Unresolved member storage: {unresolved_count:,}"
        )
    lines.append(f"  Interpretation: {interpretation}")
    return lines

def _data_space_status_note(status):
    """Describe only documented semantics plus independently validated V2R3 forms."""

    if status == DENT_V2_LIVE:
        return (
            "0x80 (observed V2R3 live/valid entry form; ordinary access "
            "paths include these entries)"
        )
    if status == DENT_V2_DELETED:
        return (
            "0xC0 (observed V2R3 deleted entry form; 0x40 is independently "
            "validated as the deleted-state indicator in these files)"
        )
    return (
        f"0x{status:02X} (raw Data Space Entry Status/DENT byte; IBM also "
        "documents other status such as cross-segment state, whose bit "
        "assignment is not yet decoded here)"
    )


def _tui_context_directory_entry_lines(state, entry):
    """Explain a context-index reference whose object primary is not recovered."""

    name = entry.display_name_hint or "<name undecoded>"
    lines = [
        f"Directory entry: {entry.library_name}/{name}",
        f"MI type:         {entry.type_code}",
        "Recovery state:  object primary not recovered on this image",
        f"Context:         {entry.context_address}",
    ]
    if entry.object_address is not None:
        lines.append(f"Object address~: {entry.object_address}")
    else:
        lines.append("Object address~: unavailable")

    if entry.name_raw_hint is not None:
        if entry.is_member_cursor:
            lines.extend(
                [
                    f"File hint:       {entry.member_file_name_hint}",
                    f"Member hint:     {entry.member_name_hint}",
                ]
            )
        else:
            lines.append(f"Name hint:       {entry.name_hint}")
        lines.append(
            "Name evidence:   observed compact context-key blank-run decoding; "
            "not the published expanded T+S+NL+N+@ byte layout."
        )
    else:
        lines.append(
            "Name evidence:   compact/special key form is not decoded; raw "
            "terminal bytes are preserved below."
        )

    owned = []
    if entry.object_address is not None:
        owned = sorted(
            [
                segment
                for segment in state["segments"].segments
                if segment.owner_key == entry.object_address.key
            ],
            key=lambda segment: (
                segment.virtual_address,
                segment.start_lba,
            ),
        )
    lines.append(f"Surviving owned segments: {len(owned):,}")
    for segment in owned[:24]:
        role = "primary" if segment.is_primary else "secondary"
        lines.append(
            f"  type {segment.header.segment_type:04X}  "
            f"VA {segment.virtual_address:012X}  "
            f"LBA {segment.start_lba:>9,}  "
            f"{segment.pages:>6,} pages  {role}"
        )
    if len(owned) > 24:
        lines.append(
            f"  ... {len(owned) - 24:,} additional owned segments"
        )

    lines.extend(
        [
            "",
            (
                "Forensic note: this entry survives in the library/context "
                "machine index even though the referenced EPA primary does not. "
                "On a partial multi-disk image this can preserve object name, "
                "type, and addressability after the primary was lost."
            ),
            "",
            "Raw context terminal:",
            "  " + entry.raw.hex(" ").upper(),
        ]
    )
    return lines


def _tui_object_lines(state, obj):
    meaning = _tui_object_type_context(
        obj.object_type,
        obj.object_subtype,
    )
    lines = [
        f"Object:       {(obj.library_name or '<orphan>')}/{obj.name}",
        f"MI type:      {obj.type_code}"
        + (
            f"  {obj.external_type_hint}"
            if obj.external_type_hint
            else ""
        ),
    ]
    if meaning:
        lines.append(f"Object role:   {meaning}")
    lines.extend(
        [
        (
            f"Virtual addr: {obj.segment.virtual_address:012X}"
        ),
        f"Physical LBA: {obj.segment.start_lba:,}",
        f"Pages:        {obj.segment.pages:,}",
        (
            f"Segment type: {obj.segment.header.segment_type:04X}"
        ),
        f"Owner:        {obj.segment.header.owner}",
        f"EPA context:  {obj.epa.context}",
        ]
    )

    epa_library = getattr(obj, "epa_library_name", None)
    context_libraries = tuple(
        getattr(obj, "context_library_names", ()) or ()
    )
    if epa_library is None and not hasattr(obj, "epa_library_name"):
        epa_library = obj.library_name

    lines.append("")
    lines.append("Library membership evidence")
    lines.append(
        "  EPA back-pointer: "
        + (epa_library or "<not resolved>")
    )
    lines.append(
        "  Context index:    "
        + (
            ", ".join(context_libraries)
            if context_libraries
            else "<not resolved>"
        )
    )
    if (
        epa_library is not None
        and context_libraries == (epa_library,)
    ):
        lines.append("  Resolution:       both directions agree")
    elif epa_library is None and len(context_libraries) == 1:
        lines.append(
            "  Resolution:       context-index-only membership"
        )
    elif epa_library is not None and not context_libraries:
        lines.append(
            "  Resolution:       EPA-only membership; no recovered context "
            "terminal matched"
        )
    elif (
        epa_library is not None
        and context_libraries
        and epa_library not in context_libraries
    ):
        lines.append(
            "  Resolution:       CONFLICT — EPA and context index disagree"
        )
    elif len(context_libraries) > 1:
        lines.append(
            "  Resolution:       ambiguous — multiple context indexes refer "
            "to this object"
        )
    else:
        lines.append("  Resolution:       membership unresolved")

    if obj.object_type == 0x02 and obj.object_subtype == 0x01:
        owned = _tui_owned_segments(state, obj)
        lines.extend(
            [
                "",
                "Program object browse",
                (
                    "  *PGM is a compiled MI program object. The current "
                    "browser has not decoded its program template/instruction "
                    "stream yet, so the views below are forensic."
                ),
                f"  Recovered owned segments: {len(owned):,}",
            ]
        )
        for segment in owned[:32]:
            role = "primary" if segment.is_primary else "secondary"
            lines.append(
                f"    type {segment.header.segment_type:04X}  "
                f"VA {segment.virtual_address:012X}  "
                f"LBA {segment.start_lba:>9,}  "
                f"{segment.pages:>6,} pages  {role}"
            )
        if len(owned) > 32:
            lines.append(
                f"    ... {len(owned) - 32:,} additional owned segments"
            )

        try:
            prefix = _tui_segment_prefix(
                state["image"],
                obj.segment,
                limit=2048,
            )
        except Exception as exc:
            prefix = b""
            lines.append(f"  Raw preview error: {exc}")

        if prefix:
            strings = _tui_ebcdic_strings(prefix, min_length=5)
            if strings:
                lines.extend(["", "  Printable EBCDIC strings (prefix)"])
                for value in strings[:24]:
                    lines.append(f"    {value[:120]}")
            lines.extend(
                [
                    "",
                    "  Raw primary-segment prefix (first 512 bytes)",
                    "  Offset    Hex                                              EBCDIC",
                ]
            )
            lines.extend(
                "  " + line
                for line in _tui_hex_lines(prefix[:512])
            )


    if (obj.object_type, obj.object_subtype) in {
        (0x08, 0x01),
        (0x19, 0x02),
    }:
        lines.extend(_tui_profile_queue_lines(state, obj))

    dlo_anchor_info = _tui_dlo_anchor_info(state, obj)
    if dlo_anchor_info and dlo_anchor_info.get("record") is not None:
        anchor_record = dlo_anchor_info["record"]
        lines.extend(
            [
                "",
                "QDLS anchor metadata",
                f"  QAOSSS14 RRN: {anchor_record.rrn:,}",
                (
                    f"  Short name:    "
                    f"{anchor_record.short_name or '-'}"
                ),
                (
                    f"  Long name:     "
                    f"{anchor_record.long_name or '-'}"
                ),
                (
                    f"  Owner text:    "
                    f"{anchor_record.owner_text or '-'}"
                ),
            ]
        )
        path = dlo_anchor_info.get("anchor_path") or ""
        if path:
            label = (
                "Anchor hierarchy"
                if dlo_anchor_info.get("path_complete")
                else "Partial anchor hierarchy"
            )
            lines.append(f"  {label}: {path}")
        lines.extend(
            [
                (
                    "  Leading key:   "
                    + anchor_record.leading_key.hex().upper()
                ),
                (
                    "  WOSEFILD:      "
                    + anchor_record.record_key.hex().upper()
                ),
                (
                    "  WOSEPLDN:      "
                    + anchor_record.parent_key.hex().upper()
                ),
                (
                    "  Link method:   QDOC binary keys correlate the anchor; "
                    "WOSEPLDN follows a unique leading-record key."
                ),
            ]
        )

    if (
        (
            obj.object_type == 0x19
            and obj.object_subtype == 0x0E
            and (obj.library_name or "").upper() == "QDOC"
        )
        or (
            obj.object_type == 0x06
            and obj.object_subtype == 0xC1
        )
    ):
        doc, companion, export_error = _dlo_export_pair(
            state["inventory"],
            obj,
        )
        lines.append("")
        if companion is not None and not export_error:
            try:
                info, _payload = state["image"].read_document_byte_string(
                    companion,
                    state["segments"],
                )
                lines.extend(
                    [
                        "DLO export:    available (press e)",
                        f"QDOC document: {doc.name}",
                        f"DOCBSS:        {companion.name}",
                        f"Payload bytes: {info.payload_length:,}",
                        (
                            f"Storage:       "
                            + (
                                "extended 0F90 continuation"
                                if (
                                    info.payload_length
                                    > companion.segment.pages * PAGE_SIZE
                                    - info.payload_offset
                                )
                                else "primary DOCBSS segment"
                            )
                        ),
                        (
                            f"Allocation:    "
                            f"{info.allocated_length:,} bytes"
                        ),
                    ]
                )
                try:
                    doc_data = state["image"].read_segment_bytes(
                        doc.segment
                    )
                    filename_hint = _dlo_filename_hint(
                        _dlo_preview_strings(
                            doc_data,
                            internal_name=doc.name,
                            limit=20,
                        )
                    )
                except (OSError, ValueError):
                    filename_hint = ""
                if filename_hint:
                    lines.append(
                        "Filename hint:  "
                        f"{filename_hint} "
                        "(QDOC metadata; not yet QAOSS-verified)"
                    )
            except (OSError, ValueError) as exc:
                lines.append(
                    f"DLO export:    validation failed: {exc}"
                )
        else:
            lines.append(f"DLO export:    unavailable: {export_error}")

    if obj.object_type == 0x19 and obj.object_subtype == 0x51:
        try:
            fields = state["image"].read_format_fields(obj)
        except Exception as exc:
            fields = ()
            lines.extend(["", f"Format decode error: {exc}"])
        if fields:
            lines.extend(
                [
                    "",
                    f"Record format fields ({len(fields):,})",
                    "Off   Len   Type        Digits Dec  Field",
                ]
            )
            for field in fields:
                lines.append(
                    f"{field.offset:>4}  "
                    f"{field.storage_length:>4}  "
                    f"{field.type_name:<10} "
                    f"{field.digits:>6} "
                    f"{field.decimal_positions:>3}  "
                    f"{field.name}"
                )

    if obj.object_type == 0x19 and obj.object_subtype == 0x01:
        members = state["inventory"].members(
            library=obj.library_name,
            file_name=obj.name,
        )
        lines.extend(
            [
                "",
                f"Recovered members: {len(members):,}",
            ]
        )
        try:
            formats = state["image"].resolve_file_formats(
                obj,
                state["inventory"],
            )
        except Exception:
            formats = []
        if formats:
            lines.append(
                "Formats: "
                + ", ".join(format_obj.name for format_obj in formats)
            )

    if (
        obj.library_name == "QDOC"
        and (obj.object_type, obj.object_subtype)
        in {(0x19, 0x0E), (0x19, 0x12)}
    ):
        try:
            data = state["image"].read_segment_bytes(obj.segment)
            strings = _tui_ebcdic_strings(data)
        except Exception as exc:
            strings = []
            lines.extend(["", f"DLO preview error: {exc}"])

        if strings:
            label = (
                "Document"
                if obj.object_subtype == 0x0E
                else "Folder"
            )
            lines.extend(
                [
                    "",
                    f"{label} library object preview",
                    (
                        "The QDOC name above is the internal system object "
                        "name; DLO/user-facing names may appear below."
                    ),
                    "",
                ]
            )
            lines.extend(strings[:300])
            if len(strings) > 300:
                lines.append(
                    f"... {len(strings) - 300:,} additional strings omitted"
                )

    specialized = (
        (obj.object_type, obj.object_subtype)
        in {
            (0x02, 0x01),
            (0x06, 0xC1),
            (0x08, 0x01),
            (0x19, 0x01),
            (0x19, 0x02),
            (0x19, 0x0E),
            (0x19, 0x12),
            (0x19, 0x51),
        }
    )
    if not specialized:
        try:
            prefix = _tui_segment_prefix(
                state["image"],
                obj.segment,
                limit=256,
            )
        except Exception as exc:
            prefix = b""
            lines.extend(["", f"Raw object preview error: {exc}"])
        if prefix:
            lines.extend(
                [
                    "",
                    "Forensic raw object prefix (first 256 bytes)",
                    "Offset    Hex                                              EBCDIC",
                ]
            )
            lines.extend(_tui_hex_lines(prefix))

    return lines


def _tui_file_lines(state, file_item):
    library = file_item["library"] or "<orphan>"
    file_obj = file_item["object"]
    members = file_item["members"]

    lines = [
        f"File:    {library}/{file_item['name']}",
        f"Members: {len(members):,}",
        (
            "Primary *FILE: present"
            if file_obj is not None
            else "Primary *FILE: absent; member cursor(s) survive"
        ),
    ]

    file_context = _tui_file_context(
        file_item["library"],
        file_item["name"],
    )
    if file_context:
        lines.extend(["", "File role", "  " + file_context])

    formats = []
    if file_obj is not None:
        lines.extend(
            [
                f"MI type: {file_obj.type_code}  {file_obj.external_type_hint}",
                (
                    f"VA:      "
                    f"{file_obj.segment.virtual_address:012X}"
                ),
                f"LBA:     {file_obj.segment.start_lba:,}",
            ]
        )
        try:
            formats = state["image"].resolve_file_formats(
                file_obj,
                state["inventory"],
            )
        except Exception:
            formats = []
        if formats:
            label = "Format:" if len(formats) == 1 else "Formats:"
            lines.append(
                f"{label:<8}"
                + ", ".join(format_obj.name for format_obj in formats)
            )

    lines.extend(
        [
            "",
            *_tui_file_storage_evidence(
                state,
                file_item,
                formats=formats,
            ),
        ]
    )

    if members:
        lines.extend(["", "Members"])
        for member in members[:200]:
            info = state["image"].read_member_info(member)
            type_text = (
                info.member_type if info is not None else ""
            )
            lines.append(
                f"  {member.member_name:<10} {type_text:<10} "
                f"VA {member.segment.virtual_address:012X}"
            )
        if len(members) > 200:
            lines.append(
                f"  ... {len(members) - 200:,} additional members"
            )
    return lines


def _tui_member_lines(state, member_item):
    image = state["image"]
    inventory = state["inventory"]
    segments = state["segments"]
    member = member_item["object"]
    file_item = member_item["file"]
    library = member.library_name or "<orphan>"

    lines = [
        (
            f"Member:       {library}/"
            f"{member.member_file_name}({member.member_name})"
        ),
        f"Cursor MI:    {member.type_code}",
        (
            f"Virtual addr: {member.segment.virtual_address:012X}"
        ),
        f"Physical LBA: {member.segment.start_lba:,}",
    ]

    info = image.read_member_info(member)
    if info is not None:
        lines.extend(
            [
                f"Source type:  {info.member_type or '-'}",
                f"Changed:      {info.source_change or '-'}",
                f"Created:      {info.created or '-'}",
                f"Text:         {info.text or '-'}",
            ]
        )

    try:
        storage = image.resolve_member_storage(
            member,
            inventory,
            segments,
        )
    except Exception as exc:
        lines.extend(["", f"Storage resolution error: {exc}"])
        return lines

    lines.extend(
        [
            "",
            "Recovered storage",
            (
                "  QDDS:  "
                + (
                    f"VA {storage.data_space.segment.virtual_address:012X}"
                    if storage.data_space is not None
                    else (
                        f"{storage.data_space_address} (primary not recovered)"
                        if storage.data_space_address is not None
                        else "not recovered"
                    )
                )
            ),
            (
                "  QDDSI: "
                + (
                    f"VA {storage.data_index.segment.virtual_address:012X}"
                    if storage.data_index is not None
                    else (
                        f"{storage.data_index_address} (primary not recovered)"
                        if storage.data_index_address is not None
                        else "not recovered"
                    )
                )
            ),
            (
                f"  Data segments: {len(storage.data_segments):,} "
                f"({storage.data_bytes:,} bytes)"
            ),
        ]
    )

    index_layout = None
    traversal = None
    index_format_fields = ()
    if storage.data_index is not None:
        try:
            index_layout = image.read_data_space_index_layout(storage)
            traversal = image.read_data_space_index_traversal(storage)
        except Exception as exc:
            lines.extend(["", f"Access-path decode error: {exc}"])
        if member.library_name:
            try:
                index_formats = _resolve_format_fields(
                    image,
                    inventory,
                    member.library_name,
                    member.member_file_name,
                )
                if index_formats:
                    index_format_fields = index_formats[0][1]
            except Exception:
                index_format_fields = ()

    if index_layout is not None:
        lines.extend(["", "Recovered keyed access path"])
        for number, spec in enumerate(index_layout.keys):
            lines.append(
                f"  DKEY {number}: {spec.key_count:,} key(s), "
                f"{spec.key_field_count:,} field(s), "
                f"user/machine {spec.user_key_length}/"
                f"{spec.machine_key_length} bytes"
            )
            labels = _qddsi_key_field_labels(spec, index_format_fields)
            for field_number, field in enumerate(spec.fields, 1):
                label = labels[field_number - 1]
                name = label or f"field {field_number}"
                location = (
                    f"record +{field.record_offset_hint}"
                    if field.record_offset_hint is not None
                    else "record location unknown"
                )
                lines.append(
                    f"    {field_number}. {name}: len/fork "
                    f"{field.length_or_fork}, {location}"
                )
        if traversal is not None:
            state_text = "complete" if traversal.complete else "partial"
            key_state = (
                f", {traversal.partial_key_count:,} partial key(s)"
                if traversal.partial_key_count
                else ""
            )
            lines.append(
                f"  Traversal: {traversal.entry_count:,}/"
                f"{traversal.expected_entries:,} entries ({state_text}), "
                f"{traversal.page_count:,} page(s){key_state}"
            )
            if traversal.page_pointers:
                lines.append(
                    f"  Page pointers: {len(traversal.page_pointers):,}; "
                    f"unresolved {len(traversal.unresolved_page_pointers):,}"
                )
            if traversal.entries:
                lines.extend(["", "Key preview (first 20)"])
                for entry in traversal.entries[:20]:
                    key_bytes = entry.display_key_bytes
                    key_hex = key_bytes.hex().upper()
                    key_text = ebcdic_preview(
                        key_bytes,
                        limit=len(key_bytes),
                    )
                    rrn = (
                        f"RRN~{entry.ordinal_hint:,}"
                        if entry.ordinal_hint is not None
                        else entry.database_reference.hex().upper()
                    )
                    key_label = "key" if entry.key_complete else "tree evidence"
                    partial = "" if entry.key_complete else " (partial key)"
                    lines.append(
                        f"  DKEY {entry.dkey_index}  {key_label} "
                        f"{key_hex}  [{key_text}] -> {rrn}{partial}"
                    )
                if traversal.entry_count > 20:
                    lines.append(
                        f"  ... {traversal.entry_count - 20:,} more key(s)"
                    )
            for warning in traversal.warnings:
                lines.append(f"  Warning: {warning}")

    try:
        source = image.read_source_member(storage)
    except Exception as exc:
        source = None
        lines.extend(["", f"Source decode error: {exc}"])

    if source is not None:
        lines.extend(
            [
                "",
                (
                    f"Source records: {source.line_count:,} "
                    f"from {source.data_segment_count:,} data segment(s)"
                ),
                "",
                "Seq      Date    Source",
            ]
        )
        for record in source.records:
            lines.append(
                f"{record.sequence_display:<8} "
                f"{record.source_date:<6} "
                f"{record.text}"
            )
        return lines

    try:
        record_set = image.read_data_space_records(storage)
    except Exception as exc:
        record_set = None
        lines.extend(["", f"Record decode error: {exc}"])

    if record_set is None:
        file_context = _tui_file_context(
            member.library_name,
            member.member_file_name,
        )
        lines.extend([""])
        if file_context and "logical file" in file_context.lower():
            lines.extend(
                [
                    "No independent QDDS record stream for this member.",
                    (
                        "This is consistent with the documented logical-file "
                        "role: a logical file describes a view/access path "
                        "rather than owning a separate copy of database rows."
                    ),
                    "",
                    "File context:",
                    "  " + file_context,
                ]
            )
        else:
            lines.extend(
                [
                    "No recoverable source or fixed-length QDDS records.",
                    (
                        "The member cursor is recovered, but its data space "
                        "is absent, incomplete, or uses a layout the current "
                        "decoder does not yet recognize."
                    ),
                ]
            )
        return lines

    layout = record_set.layout
    lines.extend(
        [
            "",
            "Database records",
            (
                "  DENT byte:    IBM documents per-entry valid/deleted/"
                "cross-segment state. Real V2R3 access paths independently "
                "validate 0x80 as the ordinary live form and 0xC0 as deleted; "
                "other bit forms remain raw."
            ),
            f"  User entries:  {layout.entry_count:,}",
            f"  Record length: {layout.record_length:,}",
            f"  Entry length:  {layout.entry_length:,}",
            (
                f"  Recovered:     {len(record_set.records):,}/"
                f"{layout.expected_entries_with_default:,} "
                f"({'complete' if record_set.complete else 'partial'})"
            ),
        ]
    )

    decoded_formats = []
    if member.library_name:
        try:
            decoded_formats = _resolve_format_fields(
                image,
                inventory,
                member.library_name,
                member.member_file_name,
                record_length=layout.record_length,
            )
        except Exception:
            decoded_formats = []

    records = record_set.user_records
    if decoded_formats:
        format_obj, fields = decoded_formats[0]
        lines.extend(
            [
                f"  Format:        {format_obj.name}",
                f"  Fields:        {len(fields):,}",
                "",
                "Field layout",
                "  Off   Len  Type       Field",
            ]
        )
        for field in fields:
            lines.append(
                f"  {field.offset:>4}  "
                f"{field.storage_length:>4}  "
                f"{field.type_name:<10} {field.name}"
            )
        if traversal is not None and traversal.entries:
            by_rrn = {record.rrn: record for record in records}
            current_dkeys = set()
            if index_layout is not None and storage.data_space_address is not None:
                current_dkeys = {
                    index
                    for index, spec in enumerate(index_layout.keys)
                    if spec.data_space == storage.data_space_address
                }

            member_entries = [
                entry
                for entry in traversal.entries
                if (
                    entry.ordinal_hint is not None
                    and (
                        not current_dkeys
                        or entry.dkey_index in current_dkeys
                    )
                )
            ]
            keyed_rows = [
                (entry, by_rrn.get(entry.ordinal_hint))
                for entry in member_entries
            ]
            resolved_rows = [
                (entry, record)
                for entry, record in keyed_rows
                if record is not None
            ]
            lines.extend(
                [
                    "",
                    (
                        "Keyed-order records (first 50; original RRN view "
                        "is retained below)"
                    ),
                ]
            )
            for entry, record in resolved_rows[:50]:
                key_bytes = entry.display_key_bytes
                key_hex = key_bytes.hex().upper()
                key_label = "Key" if entry.key_complete else "Tree-key evidence"
                partial = "" if entry.key_complete else " (partial key)"
                lines.append(
                    f"DKEY {entry.dkey_index}  "
                    f"{key_label} {key_hex} -> RRN {record.rrn:,}{partial}"
                )
                for field in fields:
                    value = field.decode_value(record.data)
                    if value:
                        lines.append(f"  {field.name:<10} {value}")
                lines.append("")
            if len(resolved_rows) < len(member_entries):
                lines.append(
                    f"  {len(member_entries) - len(resolved_rows):,} "
                    "index entry/entries for this QDDS do not currently "
                    "resolve to a recovered RRN."
                )
            if traversal.entry_count > len(member_entries):
                lines.append(
                    f"  {traversal.entry_count - len(member_entries):,} "
                    "additional index entry/entries refer to other DKEY "
                    "data spaces in this access path."
                )
            if len(resolved_rows) > 50:
                lines.append(
                    f"... {len(resolved_rows) - 50:,} additional keyed "
                    "records omitted from this preview."
                )

        lines.extend(["", "Arrival/RRN-order decoded records (first 50)"])
        for record in records[:50]:
            lines.append(
                f"RRN {record.rrn:,}  DENT "
                f"{_data_space_status_note(record.status)}"
            )
            shown_fields = 0
            for field in fields:
                value = field.decode_value(record.data)
                if value:
                    lines.append(
                        f"  {field.name:<10} {value}"
                    )
                    shown_fields += 1
            if not shown_fields:
                preview = record.ebcdic_preview
                if len(preview) > 96:
                    preview = preview[:93] + "..."
                lines.append(
                    "  Decoded fields are blank; raw EBCDIC: "
                    + (preview or "<blank>")
                )
                amount = min(48, len(record.data))
                lines.append(
                    "  Raw hex: "
                    + record.data[:amount].hex(" ").upper()
                    + (" ..." if amount < len(record.data) else "")
                )
            lines.append("")
        if len(records) > 50:
            lines.append(
                f"... {len(records) - 50:,} additional records; "
                "use as400-dasd records for the full listing."
            )
    else:
        lines.extend(
            [
                "",
                "Arrival/RRN-order raw record preview (first 100)",
            ]
        )
        for record in records[:100]:
            lines.append(
                f"RRN {record.rrn:>8,}  "
                f"DENT 0x{record.status:02X}  "
                f"{record.ebcdic_preview}"
            )
        if len(records) > 100:
            lines.append(
                f"... {len(records) - 100:,} additional records; "
                "use as400-dasd records for the full listing."
            )

    return lines


def _tui_viewer_target(state):
    """Return the navigation level whose details should fill the lower pane.

    The focused navigation pane owns the detail view. This keeps a child that
    was auto-selected for navigation from hiding its parent library/file
    details. When the content pane itself has focus, retain the traditional
    deepest-selection behavior.
    """

    focus = state.get("focus", 3)
    if focus == 0:
        return "left"
    if focus == 1:
        return "mid"
    if focus == 2:
        return "right"

    if _tui_selected(state, "right") is not None:
        return "right"
    if _tui_selected(state, "mid") is not None:
        return "mid"
    return "left"


def _tui_full_detail_lines(state):
    right = _tui_selected(state, "right")
    mid = _tui_selected(state, "mid")
    left = _tui_selected(state, "left")
    target = _tui_viewer_target(state)

    if target == "right" and right is not None:
        if right["kind"] == "member":
            key = (
                "member",
                right["object"].segment.virtual_address,
            )
            if key not in state["viewer_cache"]:
                state["viewer_cache"][key] = _tui_member_lines(
                    state,
                    right,
                )
            return state["viewer_cache"][key]
        if right["kind"] == "object":
            key = (
                "object",
                right["object"].segment.virtual_address,
            )
            if key not in state["viewer_cache"]:
                state["viewer_cache"][key] = _tui_object_lines(
                    state,
                    right["object"],
                )
            return state["viewer_cache"][key]
        if right["kind"] == "context-entry":
            entry = right["entry"]
            address_key = (
                entry.object_address.key
                if entry.object_address is not None
                else (0, 0)
            )
            key = (
                "context-entry",
                entry.library_name,
                address_key,
                entry.terminal_element_offset,
            )
            if key not in state["viewer_cache"]:
                state["viewer_cache"][key] = (
                    _tui_context_directory_entry_lines(
                        state,
                        entry,
                    )
                )
            return state["viewer_cache"][key]

    if (
        target in ("right", "mid")
        and mid is not None
    ):
        if mid["kind"] == "file":
            key = (
                "file",
                mid["library"],
                mid["name"],
            )
            if key not in state["viewer_cache"]:
                state["viewer_cache"][key] = _tui_file_lines(
                    state,
                    mid,
                )
            return state["viewer_cache"][key]

        if mid["kind"] == "context-directory":
            surviving = sum(
                1
                for entry in mid["entries"]
                if entry.owned_segment_count
            )
            return [
                "Directory-only context references",
                "",
                f"Entries without recovered primaries: {len(mid['entries']):,}",
                f"Entries with surviving owned segments: {surviving:,}",
                "",
                (
                    "These names/type/address references were reconstructed "
                    "from the library's own machine index. Select an entry "
                    "to inspect the surviving forensic evidence."
                ),
            ]

        if mid["kind"] == "search-group":
            directory_count = sum(
                1
                for item in mid.get("search_items", ())
                if item.get("kind") == "context-entry"
            )
            object_count = (
                len(mid.get("search_items", ())) - directory_count
            )
            return [
                "Search results",
                "",
                f"Recovered objects: {object_count:,}",
                f"Directory-only references: {directory_count:,}",
                "",
                "Select a result in the right pane.",
            ]

        directory_count = len(mid.get("entries", ()))
        return [
            f"Object type: {mid['type']:02X}/{mid['subtype']:02X}",
            f"Recovered objects:       {len(mid['objects']):,}",
            f"Directory-only entries:  {directory_count:,}",
            "",
            "Select an object/directory entry in the right pane to inspect it.",
        ]

    if left is not None:
        if left["kind"] == "library":
            objects = state["inventory"].in_library(
                left["library"]
            )
            files = [
                obj
                for obj in objects
                if (
                    obj.object_type == 0x19
                    and obj.object_subtype == 0x01
                )
            ]
            members = state["inventory"].members(
                library=left["library"]
            )
            directory_entries = (
                state["inventory"].context_entries_for_library(
                    left["library"]
                )
            )
            directory_only = (
                state["inventory"].unresolved_context_entries(
                    left["library"]
                )
            )
            resolved_directory = (
                len(directory_entries) - len(directory_only)
            )
            both = sum(
                1
                for obj in objects
                if (
                    getattr(obj, "epa_library_name", None)
                    == left["library"]
                    and left["library"]
                    in getattr(obj, "context_library_names", ())
                )
            )
            context_only = sum(
                1
                for obj in objects
                if (
                    getattr(obj, "epa_library_name", None) is None
                    and left["library"]
                    in getattr(obj, "context_library_names", ())
                )
            )
            epa_only = sum(
                1
                for obj in objects
                if (
                    getattr(obj, "epa_library_name", None)
                    == left["library"]
                    and left["library"]
                    not in getattr(obj, "context_library_names", ())
                )
            )
            conflicts = sum(
                1
                for obj in objects
                if (
                    getattr(obj, "epa_library_name", None)
                    and getattr(obj, "context_library_names", ())
                    and getattr(obj, "epa_library_name", None)
                    not in getattr(obj, "context_library_names", ())
                )
            )
            warning_count = len(
                state["inventory"].context_warnings.get(
                    left["library"],
                    (),
                )
            )
            traversal = _tui_context_traversal(
                state,
                left["library"],
            )
            index_lines = []
            if traversal is not None:
                status = "complete" if traversal.complete else "partial"
                page_types = sorted(
                    {header.page_type for header in traversal.page_headers}
                )
                type_text = ",".join(f"{value:02X}" for value in page_types)
                index_lines = [
                    (
                        f"Machine-index traversal: {status}; "
                        f"{traversal.page_count:,} page(s), "
                        f"{len(traversal.page_pointers):,} page pointer(s)"
                    ),
                    (
                        "  page layout: 1,024 bytes, root +0x800"
                        + (
                            f", observed types {type_text}"
                            if type_text
                            else ""
                        )
                    ),
                ]
                if traversal.unresolved_page_pointers:
                    index_lines.append(
                        "  unresolved page pointers: "
                        f"{len(traversal.unresolved_page_pointers):,}"
                    )

            return [
                f"Library: {left['library']}",
                "Role:    " + _tui_library_context(left["library"]),
                f"Object primaries present: {len(objects):,}",
                f"*FILE primaries present:   {len(files):,}",
                f"Member cursors present:    {len(members):,}",
                f"Context-index entries: {len(directory_entries):,}",
                f"  resolved to primaries: {resolved_directory:,}",
                f"  directory-only:         {len(directory_only):,}",
                f"Membership cross-check:  both={both:,}  "
                f"EPA-only={epa_only:,}  context-only={context_only:,}  "
                f"conflicts={conflicts:,}",
                f"Context traversal warnings: {warning_count:,}",
                *index_lines,
                "",
                (
                    "MI context: a library is a context namespace whose "
                    "machine index stores addressability to named system objects."
                ),
                (
                    "Membership evidence now uses both independent directions: "
                    "object EPA -> context and context machine index -> object."
                ),
                "",
                (
                    "Select a file or MI object type in the middle pane; "
                    "directory-only identities appear inline and are marked [dir]."
                ),
            ]

        if left["kind"] == "orphans-view":
            orphans = [
                obj
                for obj in state["inventory"].objects
                if obj.library_name is None
            ]
            members = [
                obj
                for obj in state["inventory"].members()
                if obj.library_name is None
            ]
            directory_only = (
                state["inventory"].unresolved_context_entries()
            )
            return [
                "Orphans / member-only recovery",
                "",
                (
                    "These objects or member cursors survived without "
                    "a recovered library context on this disk."
                ),
                f"Orphaned objects: {len(orphans):,}",
                f"Orphaned members: {len(members):,}",
                (
                    "Directory-only identities (shown under their context "
                    f"libraries): {len(directory_only):,}"
                ),
                "",
                "This view is especially useful on an incomplete multi-disk system.",
            ]

        directory_only = state["inventory"].unresolved_context_entries()
        return [
            "All object identities",
            "",
            f"Object primaries present:    {len(state['inventory'].objects):,}",
            f"Directory-only identities:  {len(directory_only):,}",
            "",
            (
                "Select an MI object type in the middle pane; directory-only "
                "entries are grouped beside primary-backed objects and marked [dir]."
            ),
        ]

    return ["No selection."]


def _tui_section(lines, start_prefixes, stop_prefixes=()):
    """Extract one named section from legacy detail lines."""

    start = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if any(stripped.startswith(prefix) for prefix in start_prefixes):
            start = index
            break
    if start is None:
        return []

    end = len(lines)
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if any(stripped.startswith(prefix) for prefix in stop_prefixes):
            end = index
            break
    return lines[start:end]


def _tui_object_evidence_lines(obj):
    epa_library = getattr(obj, "epa_library_name", None)
    context_libraries = tuple(
        getattr(obj, "context_library_names", ()) or ()
    )
    if epa_library is None and not hasattr(obj, "epa_library_name"):
        epa_library = obj.library_name

    lines = [
        "Library membership evidence",
        f"  EPA back-pointer: {epa_library or '<not resolved>'}",
        (
            "  Context index:    "
            + (
                ", ".join(context_libraries)
                if context_libraries
                else "<not resolved>"
            )
        ),
    ]
    if epa_library is not None and context_libraries == (epa_library,):
        lines.append("  Resolution:       both directions agree")
    elif epa_library is None and len(context_libraries) == 1:
        lines.append("  Resolution:       context-index-only membership")
    elif epa_library is not None and not context_libraries:
        lines.append(
            "  Resolution:       EPA-only membership; no recovered context terminal matched"
        )
    elif (
        epa_library is not None
        and context_libraries
        and epa_library not in context_libraries
    ):
        lines.append("  Resolution:       CONFLICT — EPA and context index disagree")
    elif len(context_libraries) > 1:
        lines.append(
            "  Resolution:       ambiguous — multiple context indexes refer to this object"
        )
    else:
        lines.append("  Resolution:       membership unresolved")
    return lines


def _tui_object_storage_lines(state, obj):
    owned = _tui_owned_segments(state, obj)
    lines = [
        f"Object storage: {(obj.library_name or '<orphan>')}/{obj.name}",
        (
            f"Primary: type {obj.segment.header.segment_type:04X}  "
            f"VA {obj.segment.virtual_address:012X}  "
            f"LBA {obj.segment.start_lba:,}  {obj.segment.pages:,} page(s)"
        ),
        f"Owner:   {obj.segment.header.owner}",
        f"Owned segment groups: {len(owned):,}",
        "",
    ]
    for segment in owned[:64]:
        role = "primary" if segment.is_primary else "secondary"
        lines.append(
            f"  {segment.header.segment_type:04X}  "
            f"VA {segment.virtual_address:012X}  "
            f"LBA {segment.start_lba:>9,}  "
            f"{segment.pages:>6,} pages  {role}"
        )
    if len(owned) > 64:
        lines.append(f"... {len(owned) - 64:,} additional segment group(s)")
    return lines


def _tui_raw_object_lines(state, obj):
    try:
        prefix = _tui_segment_prefix(state["image"], obj.segment, limit=1024)
    except Exception as exc:
        return ["Raw view unavailable:", str(exc)]
    return [
        (
            f"Raw primary-segment prefix: {(obj.library_name or '<orphan>')}/"
            f"{obj.name}"
        ),
        "Offset    Hex                                              EBCDIC",
        *_tui_hex_lines(prefix),
    ]


def _tui_member_summary_lines(state, item):
    member = item["object"]
    full = _tui_member_lines(state, item)
    lines = []
    for line in full:
        if line == "Recovered storage":
            break
        lines.append(line)

    storage = _tui_section(
        full,
        ("Recovered storage",),
        ("Recovered keyed access path", "Source records:", "Database records"),
    )
    if storage:
        lines.extend(["", *storage])

    traversal_line = next(
        (line for line in full if line.strip().startswith("Traversal:")),
        None,
    )
    source_line = next(
        (line for line in full if line.strip().startswith("Source records:")),
        None,
    )
    database_index = next(
        (
            index
            for index, line in enumerate(full)
            if line.strip() == "Database records"
        ),
        None,
    )
    if traversal_line:
        lines.extend(["", "Access path", traversal_line])
    if source_line:
        lines.extend(["", source_line])
    elif database_index is not None:
        summary = ["", "Database records"]
        for line in full[database_index + 1 : database_index + 8]:
            if line.strip().startswith(("Keyed-order", "Arrival/RRN-order")):
                break
            summary.append(line)
        lines.extend(summary)
    return lines


def _tui_member_data_lines(state, item):
    full = _tui_member_lines(state, item)
    source = _tui_section(full, ("Source records:",))
    if source:
        return source

    database = _tui_section(full, ("Database records",))
    if not database:
        return [
            "Data",
            "",
            "No recoverable source or fixed-length database records for this member.",
        ]

    result = []
    skipping_keyed = False
    for line in database:
        stripped = line.strip()
        if stripped.startswith("Keyed-order records"):
            skipping_keyed = True
            continue
        if skipping_keyed and stripped.startswith("Arrival/RRN-order"):
            skipping_keyed = False
        if not skipping_keyed:
            result.append(line)
    return result


def _tui_member_key_lines(state, item):
    full = _tui_member_lines(state, item)
    access = _tui_section(
        full,
        ("Recovered keyed access path",),
        ("Source records:", "Database records"),
    )
    keyed = _tui_section(
        full,
        ("Keyed-order records",),
        ("Arrival/RRN-order",),
    )
    if not access and not keyed:
        return [
            "Keys / access path",
            "",
            "No decoded QDDSI keyed access path is available for this member.",
        ]
    lines = list(access)
    if keyed:
        lines.extend(["", *keyed])
    return lines


def _tui_member_storage_lines(state, item):
    full = _tui_member_lines(state, item)
    storage = _tui_section(
        full,
        ("Recovered storage",),
        ("Recovered keyed access path", "Source records:", "Database records"),
    )
    return storage or [
        "Storage",
        "",
        "No recoverable member storage relationship is available.",
    ]


def _tui_summary_lines(state):
    target = _tui_viewer_target(state)
    right = _tui_selected(state, "right")
    mid = _tui_selected(state, "mid")

    if target == "right" and right is not None:
        if right["kind"] == "member":
            return _tui_member_summary_lines(state, right)
        if right["kind"] == "context-entry":
            entry = right["entry"]
            name = entry.display_name_hint or "<name undecoded>"
            return [
                f"Directory object: {entry.library_name}/{name}",
                f"MI type:          {entry.type_code}",
                "Recovery:         primary object not recovered",
                (
                    f"Object address~: {entry.object_address}"
                    if entry.object_address is not None
                    else "Object address~: unavailable"
                ),
                f"Owned segments:   {entry.owned_segment_count:,}",
                "",
                "The library context preserves this object's name/type/addressability.",
            ]
        if right["kind"] == "object":
            obj = right["object"]
            meaning = _tui_object_type_context(
                obj.object_type,
                obj.object_subtype,
            )
            lines = [
                f"Object:   {(obj.library_name or '<orphan>')}/{obj.name}",
                (
                    f"Type:     {obj.external_type_hint or obj.type_code}"
                    + (
                        f"  ({obj.type_code})"
                        if obj.external_type_hint
                        else ""
                    )
                ),
            ]
            if meaning:
                lines.append(f"Role:     {meaning}")
            lines.extend(
                [
                    f"Primary:  present, {obj.segment.pages:,} page(s)",
                    *_tui_object_evidence_lines(obj)[1:],
                ]
            )
            dlo = _tui_dlo_anchor_info(state, obj)
            if dlo and dlo.get("record") is not None:
                record = dlo["record"]
                lines.extend(
                    [
                        "",
                        "QDLS",
                        f"  Short name: {record.short_name or '-'}",
                        f"  Anchor path: {dlo.get('anchor_path') or '-'}",
                    ]
                )
            return lines

    return _tui_full_detail_lines(state)


def _tui_data_lines(state):
    target = _tui_viewer_target(state)
    right = _tui_selected(state, "right")
    if target == "right" and right is not None:
        if right["kind"] == "member":
            return _tui_member_data_lines(state, right)
        if right["kind"] == "context-entry":
            return [
                "Data",
                "",
                "The object primary is not recovered, so no object payload can be decoded.",
            ]
        if right["kind"] == "object":
            obj = right["object"]
            if (
                (obj.object_type, obj.object_subtype) in {
                    (0x19, 0x0E),
                    (0x06, 0xC1),
                }
            ):
                full = _tui_object_lines(state, obj)
                section = _tui_section(
                    full,
                    ("QDLS anchor metadata",),
                )
                if section:
                    return section
            return [
                "Data",
                "",
                "No dedicated decoded data view is available for this object type.",
                "Use Summary, Storage, Evidence, or Raw for the recovered object.",
            ]
    return _tui_full_detail_lines(state)


def _tui_key_lines(state):
    target = _tui_viewer_target(state)
    right = _tui_selected(state, "right")
    left = _tui_selected(state, "left")

    if target == "right" and right is not None and right["kind"] == "member":
        return _tui_member_key_lines(state, right)

    if target == "left" and left is not None and left["kind"] == "library":
        traversal = _tui_context_traversal(state, left["library"])
        if traversal is None:
            return [
                "Context machine index",
                "",
                "No traversable recovered context index is available.",
            ]
        page_types = sorted(
            {header.page_type for header in traversal.page_headers}
        )
        return [
            f"Context machine index: {left['library']}",
            (
                f"Traversal: {'complete' if traversal.complete else 'partial'}; "
                f"{traversal.entry_count:,} terminal(s)"
            ),
            f"Pages:     {traversal.page_count:,}",
            f"Pointers:  {len(traversal.page_pointers):,}",
            (
                "Types:     "
                + ", ".join(f"0x{value:02X}" for value in page_types)
            ),
            (
                f"Unresolved pointers: "
                f"{len(traversal.unresolved_page_pointers):,}"
            ),
        ]

    return [
        "Keys / index",
        "",
        "No keyed/index view applies to the current selection.",
    ]


def _tui_storage_lines(state):
    target = _tui_viewer_target(state)
    right = _tui_selected(state, "right")
    left = _tui_selected(state, "left")

    if target == "right" and right is not None:
        if right["kind"] == "member":
            return _tui_member_storage_lines(state, right)
        if right["kind"] == "object":
            return _tui_object_storage_lines(state, right["object"])
        if right["kind"] == "context-entry":
            return _tui_context_directory_entry_lines(state, right["entry"])

    if target == "mid":
        mid = _tui_selected(state, "mid")
        if mid is not None and mid["kind"] == "file":
            formats = []
            file_obj = mid.get("object")
            if file_obj is not None:
                try:
                    formats = state["image"].resolve_file_formats(
                        file_obj,
                        state["inventory"],
                    )
                except Exception:
                    formats = []
            return [
                f"File storage: {(mid.get('library') or '<orphan>')}/{mid['name']}",
                "",
                *_tui_file_storage_evidence(
                    state,
                    mid,
                    formats=formats,
                ),
            ]

    if target == "left" and left is not None and left["kind"] == "library":
        obj = left.get("object")
        if obj is not None:
            return _tui_object_storage_lines(state, obj)

    return [
        "Storage",
        "",
        "Select an object/member/file with storage evidence to inspect it.",
    ]


def _tui_evidence_lines(state):
    target = _tui_viewer_target(state)
    right = _tui_selected(state, "right")
    if target == "right" and right is not None:
        if right["kind"] == "context-entry":
            return _tui_context_directory_entry_lines(state, right["entry"])
        if right["kind"] in ("member", "object"):
            return _tui_object_evidence_lines(right["object"])

    if target == "mid":
        mid = _tui_selected(state, "mid")
        if mid is not None and mid["kind"] == "file":
            file_obj = mid.get("object")
            if file_obj is not None:
                lines = _tui_object_evidence_lines(file_obj)
                lines.extend(
                    [
                        "",
                        *_tui_file_format_evidence(state, file_obj),
                    ]
                )
                return lines
            return [
                f"File evidence: {(mid.get('library') or '<orphan>')}/{mid['name']}",
                "",
                "Primary *FILE object is absent on this image.",
                f"Surviving member cursors: {len(mid.get('members', ())):,}",
                (
                    "The file identity is reconstructed from surviving member "
                    "cursor names rather than a present *FILE primary."
                ),
            ]

    return _tui_full_detail_lines(state)


def _tui_raw_lines(state):
    target = _tui_viewer_target(state)
    right = _tui_selected(state, "right")
    left = _tui_selected(state, "left")

    if target == "right" and right is not None:
        if right["kind"] in ("member", "object"):
            return _tui_raw_object_lines(state, right["object"])
        if right["kind"] == "context-entry":
            entry = right["entry"]
            return [
                "Raw context-directory terminal",
                "",
                entry.raw.hex(" ").upper(),
            ]

    if target == "mid":
        mid = _tui_selected(state, "mid")
        if mid is not None and mid["kind"] == "file":
            obj = mid.get("object")
            if obj is not None:
                return _tui_raw_object_lines(state, obj)

    if target == "left" and left is not None and left["kind"] == "library":
        obj = left.get("object")
        if obj is not None:
            return _tui_raw_object_lines(state, obj)

    return [
        "Raw",
        "",
        "Select an object/member/file primary to inspect raw bytes.",
    ]


def _tui_viewer_lines(state):
    """Return the active inspector-tab view for the current selection."""

    tab = _tui_inspector_tab(state)
    availability = _tui_inspector_availability(state)
    if tab != "Summary" and not availability.get(tab, False):
        return [
            tab,
            "",
            (
                "No meaningful data for this view is available for the "
                "current selection."
            ),
            (
                "The tab remains selectable so the absence is explicit rather "
                "than silently hidden."
            ),
        ]
    if tab == "Summary":
        return _tui_summary_lines(state)
    if tab == "Data":
        return _tui_data_lines(state)
    if tab == "Keys":
        return _tui_key_lines(state)
    if tab == "Storage":
        return _tui_storage_lines(state)
    if tab == "Evidence":
        return _tui_evidence_lines(state)
    return _tui_raw_lines(state)


def _tui_prompt_search(stdscr, state):
    import curses

    height, width = stdscr.getmaxyx()
    prompt = "Search object/member/file name: "
    curses.echo()
    try:
        curses.curs_set(1)
    except curses.error:
        pass
    try:
        _tui_safe_addstr(
            stdscr,
            height - 1,
            0,
            " " * max(0, width - 1),
        )
        _tui_safe_addstr(
            stdscr,
            height - 1,
            0,
            prompt,
            curses.A_REVERSE,
        )
        stdscr.refresh()
        raw = stdscr.getstr(
            height - 1,
            min(len(prompt), max(0, width - 2)),
            max(1, width - len(prompt) - 2),
        )
    finally:
        curses.noecho()
        try:
            curses.curs_set(0)
        except curses.error:
            pass

    query = raw.decode(errors="replace").strip()
    if not query:
        return

    wanted = query.upper()
    object_matches = []
    for obj in state["inventory"].objects:
        haystack = " ".join(
            [
                obj.library_name or "",
                obj.name,
                obj.member_file_name,
                obj.member_name,
                obj.external_type_hint,
                obj.type_code,
            ]
        ).upper()
        if wanted in haystack:
            object_matches.append(obj)

    object_matches.sort(
        key=lambda obj: (
            obj.library_name or "",
            obj.name,
            obj.segment.virtual_address,
        )
    )

    directory_matches = []
    for entry in state["inventory"].unresolved_context_entries():
        address = (
            str(entry.object_address)
            if entry.object_address is not None
            else ""
        )
        haystack = " ".join(
            [
                entry.library_name,
                entry.display_name_hint,
                entry.type_code,
                address,
            ]
        ).upper()
        if wanted in haystack:
            directory_matches.append(entry)

    directory_matches.sort(
        key=lambda entry: (
            entry.library_name,
            entry.display_name_hint,
            entry.type_code,
            (
                entry.object_address.address
                if entry.object_address is not None
                else 0
            ),
        )
    )

    search_items = _tui_group_right_items(
        {
            "objects": object_matches,
            "entries": directory_matches,
        }
    )

    state["left_items"].insert(
        0,
        {
            "kind": "search-view",
            "label": f"<SEARCH {query}>  {len(search_items):,}",
            "objects": object_matches,
            "entries": directory_matches,
        },
    )
    state["left_index"] = 0
    state["mid_items"] = [
        {
            "kind": "search-group",
            "label": f"Results  {len(search_items):,}",
            "objects": object_matches,
            "entries": directory_matches,
            "search_items": search_items,
            "type": 0,
            "subtype": 0,
        }
    ]
    state["mid_index"] = 0
    state["right_items"] = search_items
    state["right_index"] = 0
    state["focus"] = 2
    state["viewer_scroll"] = 0
    state["viewer_cache"] = {}
    state["inspector_availability_cache"] = {}
    _tui_apply_default_inspector(state)
    state["status"] = (
        f"Search '{query}': {len(object_matches):,} recovered object(s), "
        f"{len(directory_matches):,} directory-only reference(s)"
    )

def _tui_rebuild_search_safe_from_left(state):
    selected = _tui_selected(state, "left")
    if selected and selected["kind"] == "search-view":
        objects = selected.get("objects", [])
        entries = selected.get("entries", [])
        search_items = _tui_group_right_items(
            {
                "objects": objects,
                "entries": entries,
            }
        )
        state["mid_items"] = [
            {
                "kind": "search-group",
                "label": f"Results  {len(search_items):,}",
                "objects": objects,
                "entries": entries,
                "search_items": search_items,
                "type": 0,
                "subtype": 0,
            }
        ]
        state["right_items"] = search_items
        state["mid_index"] = 0
        state["right_index"] = 0
        state["viewer_scroll"] = 0
        return
    _tui_rebuild_from_left(state)


def _tui_browse(stdscr, initial_path=None):
    import curses

    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.keypad(True)

    state = None
    current_dir = Path.cwd()

    if initial_path:
        try:
            state = _tui_build_state(stdscr, initial_path)
            current_dir = Path(initial_path).expanduser().resolve().parent
        except (OSError, ValueError) as exc:
            _tui_safe_addstr(
                stdscr,
                8,
                2,
                f"Could not open image: {exc}",
                curses.A_BOLD,
            )
            _tui_safe_addstr(
                stdscr,
                10,
                2,
                "Press any key to choose another image.",
            )
            stdscr.refresh()
            stdscr.getch()

    while state is None:
        picked = _tui_file_picker(stdscr, current_dir)
        if picked is None:
            return
        try:
            state = _tui_build_state(stdscr, picked)
            current_dir = Path(picked).parent
        except (OSError, ValueError) as exc:
            stdscr.erase()
            _tui_safe_addstr(
                stdscr,
                1,
                1,
                f"Could not open {picked}",
                curses.A_BOLD,
            )
            _tui_safe_addstr(stdscr, 3, 1, str(exc))
            _tui_safe_addstr(
                stdscr,
                5,
                1,
                "Press any key to return to the file picker.",
            )
            stdscr.refresh()
            stdscr.getch()

    while True:
        stdscr.erase()
        height, width = stdscr.getmaxyx()

        if height < 20 or width < 72:
            _tui_safe_addstr(
                stdscr,
                0,
                0,
                "AS/400 DASD Browser",
                curses.A_BOLD,
            )
            _tui_safe_addstr(
                stdscr,
                2,
                0,
                "Terminal is too small; resize to at least 72x20.",
            )
            stdscr.refresh()
            key = stdscr.getch()
            if key in (27, ord("q"), ord("Q")):
                return
            continue

        title = (
            " AS/400 CISC DASD Browser — "
            f"{os.path.basename(state['image'].path)} "
        )
        _tui_safe_addstr(
            stdscr,
            0,
            0,
            title,
            curses.A_BOLD | curses.A_REVERSE,
        )

        breadcrumb = _tui_breadcrumb(state)
        _tui_safe_addstr(
            stdscr,
            1,
            0,
            breadcrumb,
            curses.A_BOLD,
        )

        nav_y = 3
        nav_height = max(7, min(18, height // 2 - 1))
        separator_y = nav_y + nav_height
        viewer_y = separator_y + 1
        # The redesign replaces three always-on explanatory rows with a
        # breadcrumb and a purpose-specific inspector, leaving more room for
        # actual object data.
        viewer_height = max(2, height - viewer_y - 3)

        left_w = max(20, width // 4)
        mid_w = max(25, width // 3)
        if left_w + mid_w > width - 25:
            mid_w = max(20, width - left_w - 25)
        right_x = left_w + mid_w + 2
        right_w = max(1, width - right_x)

        for y in range(nav_y, separator_y):
            _tui_safe_addstr(
                stdscr,
                y,
                left_w,
                "│",
                curses.A_DIM,
            )
            _tui_safe_addstr(
                stdscr,
                y,
                left_w + mid_w + 1,
                "│",
                curses.A_DIM,
            )
        for x in range(width):
            _tui_safe_addstr(
                stdscr,
                separator_y,
                x,
                "─",
                curses.A_DIM,
            )

        left_labels = state["left_items"]
        mid_labels = state["mid_items"]
        right_labels = state["right_items"]

        left_title = "Library / view"
        left = _tui_selected(state, "left")
        if left and left["kind"] in (
            "library",
            "orphans-view",
        ):
            mid_title = "File / object type"
        elif left and left["kind"] == "search-view":
            mid_title = "Search results"
        else:
            mid_title = "MI object type"

        mid = _tui_selected(state, "mid")
        if mid and mid["kind"] == "file":
            right_title = "Member / object"
        else:
            right_title = "Object / directory entry"

        _tui_draw_list(
            stdscr,
            left_title,
            left_labels,
            state["left_index"],
            0,
            nav_y,
            left_w,
            nav_height,
            state["focus"] == 0,
        )
        _tui_draw_list(
            stdscr,
            mid_title,
            mid_labels,
            state["mid_index"],
            left_w + 1,
            nav_y,
            mid_w,
            nav_height,
            state["focus"] == 1,
        )
        _tui_draw_list(
            stdscr,
            right_title,
            right_labels,
            state["right_index"],
            right_x,
            nav_y,
            right_w,
            nav_height,
            state["focus"] == 2,
        )

        _tui_draw_inspector_tabs(
            stdscr,
            viewer_y,
            width,
            state,
            state["focus"] == 3,
        )

        try:
            viewer_lines = _tui_viewer_lines(state)
        except Exception as exc:
            viewer_lines = [
                "Could not build content view:",
                str(exc),
            ]

        visible_viewer = max(0, viewer_height - 1)
        max_scroll = max(0, len(viewer_lines) - visible_viewer)
        state["viewer_scroll"] = max(
            0,
            min(state["viewer_scroll"], max_scroll),
        )
        start = state["viewer_scroll"]
        for row, line in enumerate(
            viewer_lines[start : start + visible_viewer]
        ):
            _tui_safe_addstr(
                stdscr,
                viewer_y + 1 + row,
                0,
                line,
            )

        scan = state["scan"]
        status = (
            state["status"]
            or (
                f"{state['image'].sector_count:,} sectors • "
                f"{len(state['segments'].segments):,} segments • "
                f"{len(state['inventory'].objects):,} object primaries • "
                f"{len(state['inventory'].libraries):,} libraries • "
                f"RR0 LBA {scan.origin.lba if scan.origin else 'unknown'}"
            )
        )
        _tui_safe_addstr(
            stdscr,
            height - 2,
            0,
            status,
            curses.A_DIM,
        )

        right = _tui_selected(state, "right")
        export_action = ""
        if right is not None and right.get("kind") == "object":
            obj = right["object"]
            if (
                (obj.object_type, obj.object_subtype) in {
                    (0x19, 0x0E),
                    (0x06, 0xC1),
                }
            ):
                export_action = "  e export"

        _tui_safe_addstr(
            stdscr,
            height - 1,
            0,
            (
                "Tab/←→ pane  ↑/↓ PgUp/PgDn navigate/scroll  "
                "[/] view  1-6 view  / search  ? help"
                f"{export_action}  o open  r rescan  q quit"
            ),
            curses.A_REVERSE,
        )
        stdscr.refresh()

        key = stdscr.getch()
        state["status"] = ""

        if key in (27, ord("q"), ord("Q")):
            return

        if key in (ord("?"), ord("h"), ord("H")):
            _tui_help(stdscr)
            continue

        if key == ord("["):
            name = _tui_cycle_inspector_tab(state, -1)
            state["status"] = f"Inspector: {name}"
            continue
        if key == ord("]"):
            name = _tui_cycle_inspector_tab(state, 1)
            state["status"] = f"Inspector: {name}"
            continue
        if ord("1") <= key <= ord("6"):
            state["inspector_tab"] = key - ord("1")
            state["viewer_scroll"] = 0
            state["status"] = f"Inspector: {_tui_inspector_tab(state)}"
            continue

        if key in (ord("e"), ord("E")):
            _tui_export_selected_dlo(
                stdscr,
                state,
                current_dir,
            )
            continue

        if key in (ord("o"), ord("O")):
            picked = _tui_file_picker(stdscr, current_dir)
            if picked:
                try:
                    state = _tui_build_state(stdscr, picked)
                    current_dir = Path(picked).parent
                except (OSError, ValueError) as exc:
                    state["status"] = f"Open failed: {exc}"
            continue

        if key in (ord("r"), ord("R")):
            path = state["image"].path
            try:
                state = _tui_build_state(stdscr, path)
            except (OSError, ValueError) as exc:
                state["status"] = f"Rescan failed: {exc}"
            continue

        if key == ord("/"):
            _tui_prompt_search(stdscr, state)
            continue

        if key in (9, curses.KEY_RIGHT):
            state["focus"] = min(3, state["focus"] + 1)
            continue
        if key == curses.KEY_LEFT:
            state["focus"] = max(0, state["focus"] - 1)
            continue

        if key in (10, 13, curses.KEY_ENTER):
            if state["focus"] < 3:
                state["focus"] += 1
            continue

        if state["focus"] == 3:
            page = max(1, visible_viewer - 2)
            if key == curses.KEY_UP:
                state["viewer_scroll"] = max(
                    0,
                    state["viewer_scroll"] - 1,
                )
            elif key == curses.KEY_DOWN:
                state["viewer_scroll"] = min(
                    max_scroll,
                    state["viewer_scroll"] + 1,
                )
            elif key == curses.KEY_PPAGE:
                state["viewer_scroll"] = max(
                    0,
                    state["viewer_scroll"] - page,
                )
            elif key == curses.KEY_NPAGE:
                state["viewer_scroll"] = min(
                    max_scroll,
                    state["viewer_scroll"] + page,
                )
            elif key == curses.KEY_HOME:
                state["viewer_scroll"] = 0
            elif key == curses.KEY_END:
                state["viewer_scroll"] = max_scroll
            continue

        pane_key = (
            "left"
            if state["focus"] == 0
            else "mid"
            if state["focus"] == 1
            else "right"
        )
        items = state[pane_key + "_items"]
        index_key = pane_key + "_index"
        index = state[index_key]
        visible = max(1, nav_height - 1)

        new_index = index
        if key == curses.KEY_UP:
            new_index = max(0, index - 1)
        elif key == curses.KEY_DOWN:
            new_index = min(
                max(0, len(items) - 1),
                index + 1,
            )
        elif key == curses.KEY_PPAGE:
            new_index = max(0, index - visible)
        elif key == curses.KEY_NPAGE:
            new_index = min(
                max(0, len(items) - 1),
                index + visible,
            )
        elif key == curses.KEY_HOME:
            new_index = 0
        elif key == curses.KEY_END:
            new_index = max(0, len(items) - 1)
        else:
            continue

        if new_index != index:
            state[index_key] = new_index
            state["viewer_scroll"] = 0
            if pane_key == "left":
                _tui_rebuild_search_safe_from_left(state)
            elif pane_key == "mid":
                _tui_rebuild_from_mid(state)
            _tui_apply_default_inspector(state)


def cmd_browse(args):
    try:
        import curses
    except ImportError:
        raise ValueError(
            "the curses module is not available in this Python installation"
        )

    initial = args.image
    curses.wrapper(
        lambda stdscr: _tui_browse(stdscr, initial)
    )
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="as400-dasd",
        description=(
            "Read-only structure explorer for raw 520-byte CISC AS/400 DASD images"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    browse = sub.add_parser(
        "browse",
        help="interactive curses browser for libraries, files, members, objects, and contents",
    )
    browse.add_argument(
        "image",
        nargs="?",
        help="raw 520-byte DASD image; omit to use the file picker",
    )
    browse.set_defaults(func=cmd_browse)

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

    asde = sub.add_parser(
        "asde-probe",
        help="inspect explicitly selected raw ASDE-shaped bytes (not a detector)",
    )
    asde.add_argument("image", help="raw 520-byte DASD image")
    asde.add_argument("lba", type=int, help="physical image LBA")
    asde.add_argument("offset", type=int, help="offset in the 512-byte sector payload")
    asde.add_argument(
        "length",
        type=int,
        choices=(11, 16, 21, 26),
        help="candidate entry length from System/38 chapter 7",
    )
    asde.set_defaults(func=cmd_asde_probe)

    labels = sub.add_parser(
        "storage-labels",
        help="scan raw EBCDIC storage-management symbol hints (not a locator)",
    )
    labels.add_argument("image", help="raw 520-byte DASD image")
    labels.add_argument(
        "--symbol",
        action="append",
        dest="symbols",
        help="literal EBCDIC symbol to search (repeat to search several)",
    )
    labels.add_argument("--start-lba", type=int, default=0)
    labels.add_argument(
        "--sectors",
        type=int,
        help="number of physical sectors to scan (default: through EOF)",
    )
    labels.add_argument(
        "--substring",
        action="store_true",
        help=(
            "use the old literal substring search instead of matching "
            "complete space-padded eight-byte names; may include other names"
        ),
    )
    labels.add_argument(
        "--limit",
        type=int,
        default=50,
        help="maximum occurrence rows to show; 0 lists all",
    )
    labels.set_defaults(func=cmd_storage_labels)

    xref = sub.add_parser(
        "virtual-xref",
        help="resolve a selected six-byte candidate pointer within an explicit extent",
    )
    xref.add_argument("image")
    xref.add_argument("extent_start_lba", type=int)
    xref.add_argument("source_lba", type=int)
    xref.add_argument("offset", type=int, help="six-byte value's payload offset")
    xref.add_argument(
        "--preview",
        type=int,
        default=16,
        choices=range(1, 65),
        metavar="{1..64}",
        help="target payload bytes to print (1..64; default 16)",
    )
    xref.set_defaults(func=cmd_virtual_xref)

    xref_map = sub.add_parser(
        "virtual-xref-map",
        help="summarize six-byte address candidates in a selected extent",
    )
    xref_map.add_argument("image")
    xref_map.add_argument("extent_start_lba", type=int)
    xref_map.add_argument("--source-start-lba", type=int)
    xref_map.add_argument("--sectors", type=int)
    xref_map.add_argument("--alignment", type=int, choices=(2, 4, 8), default=2)
    xref_map.add_argument("--top", type=int, default=12)
    xref_map.add_argument("--names", type=int, default=10)
    xref_map.add_argument("--examples", type=int, default=12)
    xref_map.set_defaults(func=cmd_virtual_xref_map)

    segments = sub.add_parser(
        "segments",
        help="perform the second recovery pass and list segment groups",
    )
    segments.add_argument("image")
    segments.add_argument(
        "--primary-only",
        action="store_true",
        help="show only base/primary object segments",
    )
    segments.add_argument(
        "--type",
        help="filter 16-bit segment type as hex, for example 0190",
    )
    segments.add_argument(
        "--limit",
        type=int,
        default=100,
        help="maximum rows to print; use 0 for all (default: 100)",
    )
    segments.set_defaults(func=cmd_segments)

    libraries = sub.add_parser(
        "libraries",
        help="list recovered permanent contexts/libraries",
    )
    libraries.add_argument("image")
    libraries.add_argument("--name", help="substring filter")
    libraries.set_defaults(func=cmd_libraries)

    objects = sub.add_parser(
        "objects",
        help="list recovered EPA objects",
    )
    objects.add_argument("image")
    objects.add_argument("--library", help="restrict to a recovered library")
    objects.add_argument("--name", help="object-name substring")
    objects.add_argument(
        "--type",
        help="MI type or type/subtype in hex, for example 19 or 19/01",
    )
    objects.add_argument(
        "--limit",
        type=int,
        default=200,
        help="maximum rows to print; use 0 for all (default: 200)",
    )
    objects.set_defaults(func=cmd_objects)

    ls_parser = sub.add_parser(
        "ls",
        help="list recovered objects in one library",
    )
    ls_parser.add_argument("image")
    ls_parser.add_argument("library_name")
    ls_parser.add_argument("--name", help="object-name substring")
    ls_parser.add_argument(
        "--type",
        help="MI type or type/subtype in hex, for example 19/01",
    )
    ls_parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="maximum rows to print; use 0 for all (default: 200)",
    )
    ls_parser.set_defaults(func=cmd_ls)

    files = sub.add_parser(
        "files",
        help="list recovered *FILE objects in one library",
    )
    files.add_argument("image")
    files.add_argument(
        "library_name",
        help="library name, or * to include all known and orphaned contexts",
    )
    files.add_argument("--name", help="file-name substring")
    files.add_argument(
        "--limit",
        type=int,
        default=200,
        help="maximum rows to print; use 0 for all (default: 200)",
    )
    files.set_defaults(func=cmd_files)

    fields = sub.add_parser(
        "fields",
        help="list decoded field descriptions for a recovered *FILE format",
    )
    fields.add_argument("image")
    fields.add_argument("library_name")
    fields.add_argument("file_name")
    fields.add_argument(
        "--format",
        dest="format_name",
        help="explicit MI 19/51 format name when automatic FCB matching is ambiguous",
    )
    fields.set_defaults(func=cmd_fields)

    dlos = sub.add_parser(
        "dlos",
        help=(
            "list recovered QDOC document/folder objects and QUSRSYS "
            "DLO-index candidates"
        ),
    )
    dlos.add_argument("image")
    dlos.add_argument(
        "--class",
        dest="object_class",
        choices=("doc", "flr"),
        help="restrict output to documents or folders",
    )
    dlos.add_argument(
        "--strings",
        type=int,
        default=3,
        help=(
            "print up to this many EBCDIC metadata hints per DLO; "
            "use 0 to suppress them (default: 3)"
        ),
    )
    dlos.add_argument(
        "--all-qao",
        action="store_true",
        help="list all recovered QUSRSYS QAO* files, not only QAOSS*",
    )
    dlos.add_argument(
        "--model-fields",
        action="store_true",
        help=(
            "show decoded MI 19/51 field names for recovered QSYS DLO "
            "command model files"
        ),
    )
    dlos.add_argument(
        "--limit",
        type=int,
        default=200,
        help="maximum DLO rows to print; use 0 for all (default: 200)",
    )
    dlos.set_defaults(func=cmd_dlos)

    dlo_export = sub.add_parser(
        "dlo-export",
        help=(
            "export a validated workstation byte stream from a recovered "
            "QDOC document's IBM *DOCBSS companion"
        ),
    )
    dlo_export.add_argument("image")
    dlo_export.add_argument(
        "sysobjnam",
        help="10-character internal QDOC document SYSOBJNAM",
    )
    dlo_export.add_argument(
        "output",
        help="destination file for the recovered workstation bytes",
    )
    dlo_export.add_argument(
        "--force",
        action="store_true",
        help="replace an existing output file",
    )
    dlo_export.set_defaults(func=cmd_dlo_export)

    dlo_schema = sub.add_parser(
        "dlo-schema",
        help=(
            "report raw WOSFMT/QAOSS identifier associations useful for "
            "QDLS search-index reverse engineering"
        ),
    )
    dlo_schema.add_argument("image")
    dlo_schema.add_argument(
        "--format",
        dest="format_name",
        default="WOSFMT14",
        help="8-character WOSFMTxx marker (default: WOSFMT14)",
    )
    dlo_schema.add_argument(
        "--family",
        help=(
            "restrict to one primary QAOSS identifier, for example "
            "QAOSSS14 or QAOSSY14"
        ),
    )
    dlo_schema.set_defaults(func=cmd_dlo_schema)

    dlo_xref = sub.add_parser(
        "dlo-xref",
        help=(
            "find byte-level references to a 10-character QDOC SYSOBJNAM "
            "across recovered objects"
        ),
    )
    dlo_xref.add_argument("image")
    dlo_xref.add_argument(
        "sysobjnam",
        nargs="+",
        help=(
            "one or more 10-character QDOC internal system object names; "
            "multiple names are scanned in one recovery pass"
        ),
    )
    dlo_xref.add_argument(
        "--library",
        help=(
            "restrict scan to one recovered library; use <orphan> for "
            "unassigned objects"
        ),
    )
    dlo_xref.add_argument(
        "--ascii",
        action="store_true",
        help="also search for an ASCII copy of the name",
    )
    dlo_xref.add_argument(
        "--include-self",
        action="store_true",
        help="include the QDOC object itself in results",
    )
    dlo_xref.add_argument(
        "--context",
        type=int,
        default=32,
        help="bytes of context before/after each match (default: 32)",
    )
    dlo_xref.add_argument(
        "--hex-context",
        action="store_true",
        help="also print the context bytes in hexadecimal",
    )
    dlo_xref.add_argument(
        "--limit",
        type=int,
        default=200,
        help="maximum matches to report; use 0 for all (default: 200)",
    )
    dlo_xref.set_defaults(func=cmd_dlo_xref)

    dlo_paths = sub.add_parser(
        "dlo-paths",
        help=(
            "map QDOC internal document names to QAOSSS14 short names "
            "and reconstructed QDLS folder paths"
        ),
    )
    dlo_paths.add_argument("image")
    dlo_paths.add_argument(
        "sysobjnam",
        nargs="*",
        help=(
            "optional QDOC SYSOBJNAM values; omit to scan all recovered "
            "QDOC documents"
        ),
    )
    dlo_paths.add_argument(
        "--show-unmatched",
        action="store_true",
        help="include QDOC documents that cannot be uniquely correlated",
    )
    dlo_paths.add_argument(
        "--limit",
        type=int,
        default=200,
        help="maximum rows to print; use 0 for all (default: 200)",
    )
    dlo_paths.set_defaults(func=cmd_dlo_paths)

    dlo_parent_gaps = sub.add_parser(
        "dlo-parent-gaps",
        help=(
            "inspect QAOSSS14 records whose parent key does not resolve "
            "uniquely through another anchor record"
        ),
    )
    dlo_parent_gaps.add_argument("image")
    dlo_parent_gaps.add_argument(
        "--raw-scan",
        action="store_true",
        help=(
            "search the raw DASD image for each unresolved 8-byte parent "
            "key and classify recovered containing segments"
        ),
    )
    dlo_parent_gaps.add_argument(
        "--context",
        type=int,
        default=24,
        help="raw bytes before/after each parent-key hit (default: 24)",
    )
    dlo_parent_gaps.add_argument(
        "--hex-context",
        action="store_true",
        help="print hexadecimal context for raw parent-key hits",
    )
    dlo_parent_gaps.add_argument(
        "--limit",
        type=int,
        default=50,
        help="maximum raw hits per unresolved key; use 0 for all (default: 50)",
    )
    dlo_parent_gaps.set_defaults(func=cmd_dlo_parent_gaps)

    dlo_index_scan = sub.add_parser(
        "dlo-index-scan",
        help=(
            "correlate recovered QDOC SYSOBJNAM values against QAOSS "
            "member records"
        ),
    )
    dlo_index_scan.add_argument("image")
    dlo_index_scan.add_argument(
        "--file",
        dest="file_name",
        help=(
            "scan one QAOSS file/member name; default is QAOSSS14, the "
            "IBM-documented anchor-record index"
        ),
    )
    dlo_index_scan.add_argument(
        "--all-indexes",
        action="store_true",
        help=(
            "scan QAOSSS10-15, QAOSSS17, and QAOSSS18 instead of only "
            "QAOSSS14"
        ),
    )
    dlo_index_scan.add_argument(
        "--context",
        type=int,
        default=24,
        help="record bytes before/after each match (default: 24)",
    )
    dlo_index_scan.add_argument(
        "--hex-context",
        action="store_true",
        help="also print matching record context in hexadecimal",
    )
    dlo_index_scan.add_argument(
        "--limit",
        type=int,
        default=500,
        help="maximum correlations to report; use 0 for all (default: 500)",
    )
    dlo_index_scan.set_defaults(func=cmd_dlo_index_scan)

    context_xref = sub.add_parser(
        "context-xref",
        help=(
            "correlate EPA-known library members with documented context "
            "machine-index entry byte patterns"
        ),
    )
    context_xref.add_argument("image")
    context_xref.add_argument("library_name")
    context_xref.add_argument(
        "--limit",
        type=int,
        default=200,
        help="maximum matching rows to print; use 0 for all (default: 200)",
    )
    context_xref.add_argument(
        "--max-hits",
        type=int,
        default=8,
        help="maximum offsets retained per pattern; use 0 for all (default: 8)",
    )
    context_xref.add_argument(
        "--min-key-tail",
        type=int,
        default=5,
        help=(
            "minimum contiguous suffix of T+S+NL+N to count as terminal-text "
            "evidence (default: 5)"
        ),
    )
    context_xref.add_argument(
        "--page-summary",
        type=int,
        default=12,
        help=(
            "maximum 512-byte storage-page clusters to print "
            "(default: 12)"
        ),
    )
    context_xref.add_argument(
        "--origin-step",
        type=int,
        default=8,
        help=(
            "byte step for the primary-segment page-origin scan "
            "(default: 8; use 1 for an exhaustive first-page scan)"
        ),
    )
    context_xref.add_argument(
        "--include-misses",
        action="store_true",
        help="also list EPA-assigned objects with no address occurrence",
    )
    context_xref.set_defaults(func=cmd_context_xref)

    context_page = sub.add_parser(
        "context-page",
        help="decode raw three-byte machine-index elements in a library context",
    )
    context_page.add_argument("image")
    context_page.add_argument("library_name")
    context_page.add_argument(
        "page",
        type=int,
        help="logical page number within the recovered context segment",
    )
    context_page.add_argument(
        "--page-size",
        type=int,
        default=CONTEXT_MACHINE_INDEX_PAGE_SIZE,
        help=(
            "logical index-page size; multiple of 512 "
            f"(default: {CONTEXT_MACHINE_INDEX_PAGE_SIZE})"
        ),
    )
    context_page.add_argument(
        "--origin",
        type=lambda value: int(value, 0),
        default=CONTEXT_MACHINE_INDEX_ROOT_OFFSET,
        help=(
            "byte offset of logical page 0 within the recovered context "
            f"segment (default: 0x{CONTEXT_MACHINE_INDEX_ROOT_OFFSET:X})"
        ),
    )
    context_page.add_argument(
        "--offset",
        type=lambda value: int(value, 0),
        default=0,
        help=(
            "first element-stream byte offset within the logical page; any "
            "modulo-3 phase is allowed (default: 0)"
        ),
    )
    context_page.add_argument(
        "--count",
        type=int,
        default=32,
        help="number of three-byte elements to decode (default: 32)",
    )
    context_page.set_defaults(func=cmd_context_page)

    members = sub.add_parser(
        "members",
        help="list recovered database-file member cursors",
    )
    members.add_argument("image")
    members.add_argument(
        "library_name",
        help="library name, or * to search recovered orphan/member cursors",
    )
    members.add_argument(
        "file_name",
        nargs="?",
        help="optional database file name",
    )
    members.add_argument(
        "--limit",
        type=int,
        default=200,
        help="maximum rows to print; use 0 for all (default: 200)",
    )
    members.add_argument(
        "--long",
        action="store_true",
        help="also show member creation timestamp and descriptive text",
    )
    members.set_defaults(func=cmd_members)

    member = sub.add_parser(
        "member",
        help="show one member cursor and its recovered QDDS/QDDSI storage",
    )
    member.add_argument("image")
    member.add_argument(
        "library_name",
        help="library name, or * to search recovered orphan/member cursors",
    )
    member.add_argument("file_name")
    member.add_argument("member_name")
    member.set_defaults(func=cmd_member)

    records = sub.add_parser(
        "records",
        help="list raw ordinal records from any recovered QDDS member",
    )
    records.add_argument("image")
    records.add_argument(
        "library_name",
        help="library name, or * to search recovered orphan/member cursors",
    )
    records.add_argument("file_name")
    records.add_argument("member_name")
    records.add_argument(
        "--include-default",
        action="store_true",
        help="include ordinal-zero default entry",
    )
    records.add_argument(
        "--preview",
        type=int,
        default=96,
        help="maximum EBCDIC preview characters per row (default: 96)",
    )
    records.add_argument(
        "--hex-bytes",
        type=int,
        default=0,
        help="also print the first N bytes of each record in hex",
    )
    records.add_argument(
        "--limit",
        type=int,
        default=50,
        help="maximum records to print; use 0 for all (default: 50)",
    )
    records.add_argument(
        "--decoded",
        action="store_true",
        help="decode each record through the recovered MI 19/51 format",
    )
    records.add_argument(
        "--format",
        dest="format_name",
        help="explicit format name for --decoded",
    )
    records.set_defaults(func=cmd_records)

    record = sub.add_parser(
        "record",
        help="show one recovered raw record by relative record number",
    )
    record.add_argument("image")
    record.add_argument(
        "library_name",
        help="library name, or * to search recovered orphan/member cursors",
    )
    record.add_argument("file_name")
    record.add_argument("member_name")
    record.add_argument(
        "rrn",
        type=int,
        help="relative record number; 0 selects the default entry",
    )
    record.add_argument(
        "--decoded",
        action="store_true",
        help="decode record fields through the recovered MI 19/51 format",
    )
    record.add_argument(
        "--format",
        dest="format_name",
        help="explicit format name for --decoded",
    )
    record.set_defaults(func=cmd_record)

    source = sub.add_parser(
        "source",
        help="show recovered standard source records from one member",
    )
    source.add_argument("image")
    source.add_argument(
        "library_name",
        help="library name, or * to search recovered orphan/member cursors",
    )
    source.add_argument("file_name")
    source.add_argument("member_name")
    source.add_argument(
        "--text-only",
        action="store_true",
        help="print only the 80-byte source text field",
    )
    source.add_argument(
        "--limit",
        type=int,
        default=0,
        help="maximum source lines to print; 0 means all",
    )
    source.set_defaults(func=cmd_source)

    cat = sub.add_parser(
        "cat",
        help="print source text only for one recovered source member",
    )
    cat.add_argument("image")
    cat.add_argument(
        "library_name",
        help="library name, or * to search recovered orphan/member cursors",
    )
    cat.add_argument("file_name")
    cat.add_argument("member_name")
    cat.set_defaults(func=cmd_cat)

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
