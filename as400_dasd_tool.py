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
    _, _, inventory = _recover_all(image)
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

    members = inventory.members(library=args.library_name)
    member_counts = {}
    for member in members:
        name = member.member_file_name.upper()
        member_counts[name] = member_counts.get(name, 0) + 1

    file_objects = {}
    for obj in inventory.in_library(args.library_name):
        if obj.object_type == 0x19 and obj.object_subtype == 0x01:
            file_objects.setdefault(obj.name.upper(), obj)

    # On an incomplete multi-disk system, a *FILE primary object can live on
    # the missing disk while one or more member cursors survive here. Include
    # those member-derived file names so the forensic file list remains useful.
    names = sorted(set(file_objects) | set(member_counts))
    if args.name:
        wanted = args.name.upper()
        names = [name for name in names if wanted in name]

    total = len(names)
    shown = names if not args.limit else names[: args.limit]

    print(f"Disk: {image.path}")
    print(
        f"Recovered/inferred files in {args.library_name.upper()}: "
        f"{total:,}"
    )
    print()
    print("File        Members  Object       Virtual addr   LBA        pages")
    for name in shown:
        obj = file_objects.get(name)
        if obj is None:
            print(
                f"{name:<10.10} "
                f"{member_counts.get(name, 0):>7,}  "
                f"{'member-only':<12} {'-':<14} {'-':>9} {'-':>6}"
            )
        else:
            print(
                f"{obj.name:<10.10} "
                f"{member_counts.get(name, 0):>7,}  "
                f"{'recovered':<12} "
                f"{obj.segment.virtual_address:012X} "
                f"{obj.segment.start_lba:>9,} "
                f"{obj.segment.pages:>6,}"
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

    probes = image.probe_machine_index_page(
        context,
        args.page,
        element_offset=args.offset,
        count=args.count,
        page_size=args.page_size,
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
        f"element offset 0x{args.offset:X}"
    )
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
        "The context's page-header/trunk location is still under "
        "reverse engineering, so page/offset selection is explicit."
    )
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
    if storage.data_space is None:
        print("  QDDS data space: not recovered")
    else:
        qdds = storage.data_space
        print(
            f"  QDDS data space: VA {qdds.segment.virtual_address:012X}  "
            f"LBA {qdds.segment.start_lba:,}  "
            f"primary {qdds.segment.pages:,} pages"
        )
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
        print("  QDDSI index:     not recovered / not present")
    else:
        index = storage.data_index
        print(
            f"  QDDSI index:     VA {index.segment.virtual_address:012X}  "
            f"LBA {index.segment.start_lba:,}  "
            f"{index.segment.pages:,} pages"
        )

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
    files.add_argument("library_name")
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
        default=512,
        help="logical index-page size; multiple of 512 (default: 512)",
    )
    context_page.add_argument(
        "--offset",
        type=lambda value: int(value, 0),
        default=0,
        help="3-byte-aligned element offset within the logical page",
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
