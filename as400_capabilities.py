"""Read-only workflows built from bounded CISC evidence, not modern API layouts."""
from collections import Counter
import fnmatch
import re

from as400_object_types import catalog, lookup
from as400_dasd import (DataSpaceLayout, DataSpaceIndexLayout,
                        MemberStoragePointers, decode_format_fields)


def object_row(obj, note=""):
    info = lookup(obj.object_type, obj.object_subtype)
    kind = "member" if obj.is_member_cursor else "file" if obj.type_code == "19/01" else "library" if obj.type_code == "04/01" else "object"
    origin = obj.library_name or "<unassigned>"
    lba = getattr(getattr(obj, "segment", None), "start_lba", "?")
    return dict(kind=kind, name=obj.member_name if obj.is_member_cursor else obj.name,
                type=info.name if info else obj.type_code, object=obj, catalog_info=info,
                note=f"{origin} LBA {lba}" + (f"; {note}" if note else ""))


def select_objects(inventory, pattern="*ALL/*", object_type="*ALL"):
    """Search all primaries; never deduplicate equal names or conceal orphans."""
    parts = pattern.upper().split("/")
    if len(parts) == 1:
        parts.insert(0, "*ALL")
    if len(parts) != 2 or not all(parts):
        raise ValueError("Specify OBJ(library/name), OBJ(name), or OBJ(*ORPHAN/*).")
    lib, name = parts
    wanted = object_type.upper()
    if wanted != "*ALL":
        if re.fullmatch(r"[0-9A-F]{2}/?[0-9A-F]{2}", wanted):
            codes = {wanted.replace("/", "")}
        else:
            codes = {c for c, info in catalog().items() if info.name == wanted}
            if not codes:
                raise ValueError("Unknown OBJTYPE; use a catalog name or raw MI code XX/YY.")
    else:
        codes = None
    rows = []
    for obj in inventory.objects:
        code = f"{obj.object_type:02X}{obj.object_subtype:02X}"
        if codes is not None and code not in codes:
            continue
        origin = (obj.library_name or "").upper()
        if lib == "*ORPHAN":
            if origin:
                continue
        elif lib not in ("*ALL", "*") and not fnmatch.fnmatchcase(origin, lib):
            continue
        if fnmatch.fnmatchcase(obj.name.upper(), "*" if name == "*ALL" else name):
            rows.append(object_row(obj))
    return sorted(rows, key=lambda r: (r["name"], r["type"], r["object"].library_name or "",
                                       getattr(getattr(r["object"], "segment", None), "start_lba", -1)))


def type_rows(inventory, pattern="*"):
    pattern = "*" if pattern.upper() == "*ALL" else pattern
    exact_name = pattern.upper() in {info.name for info in catalog().values()}
    counts = Counter(f"{o.object_type:02X}{o.object_subtype:02X}" for o in inventory.objects)
    orphan = Counter(f"{o.object_type:02X}{o.object_subtype:02X}" for o in inventory.objects if not o.library_name)
    rows = []
    for code in sorted(set(catalog()) | set(counts)):
        info = lookup(code)
        name = info.name if info else code[:2] + "/" + code[2:]
        if exact_name:
            if name != pattern.upper():
                continue
        elif not (fnmatch.fnmatchcase(name, pattern.upper()) or
                  fnmatch.fnmatchcase(code, pattern.upper().replace("/", ""))):
            continue
        rows.append(dict(kind="mi_type", name=name, type=code[:2] + "/" + code[2:],
                         code=code, note=f"{counts[code]} primaries; {orphan[code]} unassigned; " +
                         (info.description if info else "Unidentified raw code")))
    return rows


def read_prefix(image, segment, limit):
    """Read virtual extents in order, stopping at gaps rather than shifting bytes."""
    result = bytearray()
    expected = segment.virtual_address
    for extent in segment.extents:
        if extent.virtual_address != expected:
            break
        for page in range(extent.pages):
            if len(result) >= limit:
                return bytes(result[:limit])
            data = image.read_sector(extent.start_lba + page).data
            if len(data) != 512:
                raise ValueError("Short logical sector in recovered primary")
            result.extend(data)
        expected += extent.pages * 512
    return bytes(result[:limit])


def decode_translation_table(prefix, *, type_pair):
    """Empirical 19/06 single-byte map at +100..+1FF, tested on both images.

    No name/codepage guessing; any of 256 output bytes is legal, including
    repeated or NUL values. Layout/CCSID/type flags beyond the map are unknown.
    """
    if type_pair != (0x19, 0x06):
        raise ValueError("Selected primary is not MI 19/06 *TBL")
    if len(prefix) < 0x200:
        raise ValueError("Incomplete *TBL map: need primary bytes +0x100 through +0x1FF")
    return bytes(prefix[0x100:0x200])


def decode_character_data_area(prefix, *, type_pair):
    """Empirical selector 04: u16 length at +101, value at +103.

    Other selectors need independent numeric/logical validation. No coercion.
    """
    if type_pair != (0x19, 0x0A):
        raise ValueError("Selected primary is not MI 19/0A *DTAARA")
    if len(prefix) < 0x103:
        raise ValueError("Incomplete data-area header")
    selector = prefix[0x100]
    if selector != 0x04:
        raise ValueError(f"Data-area selector 0x{selector:02X} is not decoded; value withheld.")
    length = int.from_bytes(prefix[0x101:0x103], "big")
    if not 1 <= length <= 2000:
        raise ValueError("Character data-area length is outside supported 1..2000 bytes")
    if 0x103 + length > len(prefix):
        raise ValueError(f"Character data area declares {length} bytes but its value is incomplete")
    return bytes(prefix[0x103:0x103 + length])


def hex_sample(value):
    if not re.fullmatch(r"[0-9A-Fa-f\s]+", value) or len(value.split()) > 64:
        raise ValueError("HEX must contain 1–64 bytes as hexadecimal pairs.")
    try:
        data = bytes.fromhex(value)
    except ValueError:
        raise ValueError("HEX must contain complete hexadecimal byte pairs.") from None
    if not 1 <= len(data) <= 64:
        raise ValueError("HEX must contain 1–64 bytes.")
    return data


def section(name, lines, note=""):
    return dict(kind="capability_section", name=name, type="View", note=note, lines=list(lines))


class CapabilityExplorer:
    """Lazy services: no primary reads until an applicable object is opened."""
    def __init__(self, image, inventory, segments=None):
        self.segments = segments
        self.image, self.inventory = image, inventory
        self._reverse = None
        self._reverse_errors = 0

    def rows(self, obj, sample=None):
        pair = (obj.object_type, obj.object_subtype)
        if pair in ((0x19, 0x0E), (0x06, 0xC1)):
            return self.document_rows(obj)
        if pair == (0x19, 0x06):
            return self.table_rows(obj, sample)
        if pair == (0x19, 0x0A):
            return self.data_area_rows(obj)
        if pair == (0x19, 0x01):
            return self.file_rows(obj)
        if pair == (0x19, 0x51):
            return self.format_rows(obj)
        if pair == (0x0D, 0x50):
            return self.member_rows(obj)
        if pair in ((0x0B, 0x90), (0x0C, 0x90)):
            return self.storage_rows(obj)
        return []

    def data_area_rows(self, obj):
        data = decode_character_data_area(read_prefix(self.image, obj.segment, 0x103 + 2000),
                                          type_pair=(obj.object_type, obj.object_subtype))
        rows = [section("Summary", [f"Data area: {obj.library_name or '<unassigned>'}/{obj.name}",
                 f"Primary LBA: {obj.segment.start_lba}; recovered value bytes: {len(data)}",
                 "Empirical selector 04 layout: length +0x101 (u16), value +0x103.",
                 "CP037 is a display lens, not a decoded CCSID. Spaces/NULs are preserved.",
                 "Positions below are one-based within the value; no updates are allowed."])]
        for start in range(0, len(data), 32):
            chunk = data[start:start+32]
            row = section(f"{start+1}-{start+len(chunk)}", [
                f"Value positions {start+1} through {start+len(chunk)} of {len(data)}.",
                f"Primary offset +0x{0x103+start:X}; LBA {obj.segment.start_lba}.",
                f"CP037: {chunk.decode('cp037')!r}", f"Hex: {chunk.hex(' ').upper()}",
                "No numeric/logical or CCSID conversion is inferred."], note=repr(chunk.decode('cp037')))
            row['type'] = "Positions"
            rows.append(row)
        return rows

    def table_rows(self, obj, sample=None):
        table = decode_translation_table(read_prefix(self.image, obj.segment, 512),
                                         type_pair=(obj.object_type, obj.object_subtype))
        counts = Counter(table)
        lines = [f"Table: {obj.library_name or '<unassigned>'}/{obj.name}",
                 f"Primary LBA: {obj.segment.start_lba}",
                 "Empirical single-byte map: output = primary[0x100 + input].",
                 "CCSIDs, table purpose and non-map flags are not decoded.",
                 f"Distinct outputs: {len(counts)}; unchanged inputs: {sum(i == b for i, b in enumerate(table))}",
                 f"Inputs sharing an output: {sum(n for n in counts.values() if n > 1)}",
                 "ASCII/CP037 previews are reference lenses, not declared encodings.",
                 "Use DSPTBL TBL(library/name) HEX(C1C2C3) for an offline sample."]
        rows = [section("Summary", lines)]
        if sample is not None:
            result = sample.translate(table)
            rows.append(section("Sample", ["Offline byte lookup only; image unchanged.",
                         f"Input hex:  {sample.hex(' ').upper()}",
                         f"Output hex: {result.hex(' ').upper()}",
                         f"Output as ASCII: {result.decode('ascii', errors='backslashreplace')!r}",
                         f"Output as CP037: {result.decode('cp037')!r}"]))
        for value, output in enumerate(table):
            sources = [i for i, b in enumerate(table) if b == output]
            rows.append(section(f"{value:02X} -> {output:02X}", [
                f"Input byte 0x{value:02X} maps to output 0x{output:02X}.",
                f"Evidence: primary +0x{0x100 + value:03X}; LBA {obj.segment.start_lba}.",
                f"Input as ASCII: {bytes([value]).decode('ascii', errors='backslashreplace')!r}",
                f"Input as CP037: {bytes([value]).decode('cp037')!r}",
                f"Output as ASCII: {bytes([output]).decode('ascii', errors='backslashreplace')!r}",
                f"Output as CP037: {bytes([output]).decode('cp037')!r}",
                "Inputs producing this output: " + " ".join(f"{i:02X}" for i in sources),
                "No inverse is assumed when multiple inputs share an output."],
                note="unchanged" if value == output else f"{len(sources)} input(s) share output"))
        return rows

    def file_rows(self, obj):
        # Reuse existing exact FCB evidence, but bound the primary read and retain
        # duplicate name matches instead of auto-selecting one format.
        prefix = read_prefix(self.image, obj.segment, 65536)
        rows = [section("Evidence", [
            "Formats below are exact padded-name occurrences in the first 64 KiB of the FCB.",
            "Address occurrences independently corroborate a candidate; they are not decoded FCB fields.",
            "A name match alone is not proof of ownership. Select a candidate to inspect its fields.",
            "12 on the file opens recovered members; 5 opens this schema view."])]
        for fmt in self.inventory.objects:
            if (fmt.object_type, fmt.object_subtype) != (0x19, 0x51):
                continue
            name = fmt.epa.name_raw[:10]
            if len(name) != 10 or not name.strip(b'\x40\x00'):
                continue
            off = prefix.find(name)
            if off < 0:
                continue
            addr = prefix.find(fmt.object_address.to_bytes())
            row = object_row(fmt, f"name +0x{off:X}; " + (f"address +0x{addr:X}" if addr >= 0 else "name only"))
            row["source_file"] = obj
            rows.append(row)
        if len(rows) == 1:
            rows.append(section("Unavailable", ["No recovered format name matched the bounded FCB prefix.",
                                                "Absence of a match does not establish absence of a format."]))
        return rows

    def format_rows(self, obj):
        prefix = read_prefix(self.image, obj.segment, 65536)
        fields = decode_format_fields(prefix)
        rows = [section("Evidence", [f"Format {obj.name}; primary LBA {obj.segment.start_lba}",
                 "Empirical repeated 19/51 field descriptors; first 64 KiB only.",
                 f"Recovered descriptors: {len(fields)}; offsets are relative to a record payload.",
                 "No record length is assumed. This is not proof of a complete schema."])]
        for field in fields:
            row = section(field.name, [f"Field: {field.name}", f"Reference name: {field.reference_name}",
                f"Storage type: {field.type_name} (0x{field.type_code:02X})",
                f"Record offset: {field.offset}; storage bytes: {field.storage_length}",
                f"Digits: {field.digits}; decimal positions: {field.decimal_positions}",
                f"Descriptor marker: 0x{field.marker:02X}; flags: 0x{field.flags:02X}",
                "DBCS and unknown data types remain raw; no inferred CCSID."])
            row.update(type=field.type_name, note=f"offset {field.offset}; {field.storage_length} bytes")
            rows.append(row)
        return rows

    def member_rows(self, obj):
        ptrs = MemberStoragePointers.from_cursor_segment(read_prefix(self.image, obj.segment, 0x308))
        rows = []
        for label, ptr, pair, offset in (("QDDS", ptrs.data_space, (0x0B, 0x90), 0x300),
                                         ("QDDSI", ptrs.data_index, (0x0C, 0x90), 0x128)):
            matches = [o for o in self.inventory.objects if ptr is not None and
                       (o.object_type, o.object_subtype) == pair and o.object_address.key == ptr.key]
            rows.append(section(label, [f"Cursor +0x{offset:X}: " + (ptr.to_bytes().hex().upper() if ptr else "null or unavailable"),
                f"Exact recovered address/type matches: {len(matches)}",
                "All duplicate primaries are retained. No same-name fallback is used in this view.",
                "A missing primary may have surviving secondary storage; member content recovery is separate."]))
            rows.extend(object_row(o, f"direct cursor pointer +0x{offset:X}") for o in matches)
        return rows

    def storage_rows(self, obj):
        prefix = read_prefix(self.image, obj.segment, 65536)
        if obj.object_type == 0x0B:
            layout = DataSpaceLayout.from_primary_segment(prefix)
            rows = [section("Layout", [f"Entry count: {layout.entry_count}; force count: {layout.force_count}",
                f"Entry bytes: {layout.entry_length}; payload bytes: {layout.record_length}",
                "Counts are stored scalars, not proof that all records survive.",
                "Select a referencing member below, then use 5 to view recovered content."])]
        else:
            layout = DataSpaceIndexLayout.from_primary_segment(prefix, virtual_address=obj.segment.virtual_address)
            rows = [section("Keys", [f"Declared key specifications: {layout.dkey_count}",
                     f"Recovered key specifications: {len(layout.keys)}",
                     "Bounded DKEY/DKYT decoding; unknown attributes remain raw."])]
            for i, key in enumerate(layout.keys, 1):
                lines = [f"Stored key count: {key.key_count}",
                         f"User key bytes: {key.user_key_length}; machine key bytes: {key.machine_key_length}",
                         f"Declared fields: {key.key_field_count}; recovered: {len(key.fields)}",
                         "Field locations/ordinals are empirical hints, not universal record offsets."]
                for number, field in enumerate(key.fields, 1):
                    lines.append(f"Field {number}: length/fork {field.length_or_fork}; "
                                 f"location {field.location}; ordinal hint {field.field_ordinal_hint}; "
                                 f"sequence 0x{field.sequence_attributes:02X}")
                rows.append(section(f"Key {i}", lines))
        # Build once per image, using exact addresses, never member names.
        if self._reverse is None:
            self._reverse = {}
            for member in self.inventory.objects:
                if not member.is_member_cursor:
                    continue
                try:
                    ptrs = MemberStoragePointers.from_cursor_segment(read_prefix(self.image, member.segment, 0x308))
                except (ValueError, OSError):
                    self._reverse_errors += 1
                    continue
                for pair, ptr in (((0x0B, 0x90), ptrs.data_space), ((0x0C, 0x90), ptrs.data_index)):
                    if ptr is not None:
                        self._reverse.setdefault((pair, ptr.key), []).append(member)
        matches = self._reverse.get(((obj.object_type, obj.object_subtype), obj.object_address.key), ())
        rows.append(section("References", [f"Exact referencing member cursors: {len(matches)}",
                     f"Unreadable cursor primaries skipped: {self._reverse_errors}",
                     "This is a recovered-pointer index, not proof of active membership."]))
        rows.extend(object_row(member, "exact cursor pointer; 5=content, 9=storage") for member in matches)
        return rows

    def document_rows(self, obj):
        """Navigate observed DOC/DOCBSS name companions without claiming pointers."""
        is_doc = (obj.object_type, obj.object_subtype) == (0x19, 0x0E)
        rows = [section("Relationship", [
            "QDOC DOC name + 'F' is an observed companion-name convention.",
            "It is not a verified ownership pointer. All matching primaries remain selectable.",
            "Byte-string lengths and continuation ownership are validated independently."])]
        if is_doc:
            matches = [o for o in self.inventory.objects if o.type_code == '06/C1' and
                       (obj.library_name or '').upper() == 'QDOC' and o.name.upper() == obj.name.upper() + 'F']
        else:
            matches = [o for o in self.inventory.objects if o.type_code == '19/0E' and
                       (o.library_name or '').upper() == 'QDOC' and obj.name.upper() == o.name.upper() + 'F']
        rows.extend(object_row(o, "companion name only") for o in matches)
        if not matches:
            rows.append(section("No companion", ["No matching primary under the observed QDOC naming convention."]))
        if is_doc:
            return rows
        from as400_dasd import DocumentByteStringInfo, assemble_document_byte_string
        header = read_prefix(self.image, obj.segment, 512)
        info = DocumentByteStringInfo.from_primary_segment(header)
        info.validate_metadata()
        primary = read_prefix(self.image, obj.segment, 512 + info.payload_length)
        if len(primary) < min(obj.segment.pages * 512, 512 + info.payload_length):
            raise ValueError("DOCBSS primary has an incomplete virtual extent range")
        remaining = max(0, info.payload_length - max(0, len(primary) - 512))
        continuations = []
        expected = obj.segment.virtual_address + obj.segment.pages * 512
        candidates = sorted((s for s in getattr(self.segments, 'segments', ())
                             if s.owner_key == obj.segment.owner_key and s.header.segment_type == 0x0F90 and
                             s.virtual_address > obj.segment.virtual_address), key=lambda s: (s.virtual_address,s.start_lba))
        for segment in candidates:
            if not remaining:
                break
            if segment.virtual_address != expected:
                raise ValueError("DOCBSS continuation gap or duplicate virtual range; payload withheld")
            chunk = read_prefix(self.image, segment, remaining + 512)
            if len(chunk) < min(segment.pages * 512, remaining + 512):
                raise ValueError("DOCBSS continuation has an incomplete virtual extent range")
            continuations.append(chunk)
            remaining -= max(0, len(chunk) - 512)
            expected += segment.pages * 512
        data = assemble_document_byte_string(info, primary, tuple(continuations))
        rows.append(section("Byte stream", [f"Declared/recovered bytes: {info.payload_length}/{len(data)}",
            f"Allocation field: {info.allocated_length}; duplicate lengths agree.",
            f"Continuation groups used: {len(continuations)}; primary LBA {obj.segment.start_lba}.",
            "Select a byte range below. Hex is exact; ASCII/CP037 are optional display lenses.",
            "No document format/encoding is inferred and no program or embedded content executes."]))
        for offset in range(0, len(data), 64):
            chunk = data[offset:offset+64]
            rows.append(section(f"+{offset:04X}", [
                f"Byte-stream offsets +0x{offset:X}..+0x{offset+len(chunk)-1:X} (not primary offsets).",
                f"ASCII: {chunk.decode('ascii', errors='backslashreplace')!r}",
                f"CP037: {chunk.decode('cp037')!r}",
                *[f"+{offset+i:04X}: {chunk[i:i+16].hex(' ').upper()}" for i in range(0,len(chunk),16)]],
                note=f"{len(chunk)} recovered bytes"))
        return rows
