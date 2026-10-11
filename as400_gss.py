"""Read-only CISC 19/0C GSS saved symbol-record navigator.

Observed independently in Pete B10 and Mark V2R3 004A/4009 variant:
+0x100 word 0014; +0x102 stored byte length, +0x112 length minus four;
+0x116..+0x11B 0183004A4009; +0x120..+0x123 200000F9.
Exactly 176 big-endian 16-bit saved offset slots begin at +0x124.
Nonzero offsets start no earlier than 0x160 and address C1-prefixed
byte sequences relative to +0x124. Between successive different
offsets the sequences normally end in FF00. Final-sequence termination
is *not* corroborated and is labeled an open tail.

Slot order, tags and binary content are not proved Unicode glyphs,
printable font identities, drawing instructions, screen characters or
application semantics. Unsupported GSS control variants fail closed.
"""
from dataclasses import dataclass

from as400_capabilities import read_prefix, section

TABLE_BASE = 0x124
SLOT_COUNT = 176
TABLE_BYTES = SLOT_COUNT * 2
TABLE_END = TABLE_BASE + TABLE_BYTES
MAX_PRIMARY_READ = 65536
MAX_SYMBOL_RECORD = 2048
WINDOW = 50
HEADER = bytes.fromhex("0183004A4009")
MODE = bytes.fromhex("200000F9")


@dataclass(frozen=True)
class SavedSymbolSlot:
    ordinal: int
    offset: int
    raw: bytes
    status: str
    alias: bool


def decode_gss_symbol_slots(data, *, type_code):
    if type_code != "19/0C":
        raise ValueError("Not a CISC saved GSS primary")
    if len(data) < TABLE_END or data[0x100:0x102] != bytes.fromhex("0014"):
        raise ValueError("Unsupported or truncated CISC GSS header")
    length = int.from_bytes(data[0x102:0x106], "big")
    repeated = int.from_bytes(data[0x112:0x116], "big")
    end = 0x100 + length
    if (length <= TABLE_END-0x100 or length > MAX_PRIMARY_READ-0x100 or
            end > len(data) or repeated != length-4 or
            data[0x116:0x11C] != HEADER or
            data[0x120:0x124] != MODE):
        raise ValueError("Unsupported GSS saved record table, length or variant")
    values = [
        int.from_bytes(data[TABLE_BASE+i*2:TABLE_BASE+i*2+2], "big")
        for i in range(SLOT_COUNT)
    ]
    offsets = sorted(set(x for x in values if x))
    if not offsets or offsets[0] < TABLE_BYTES:
        raise ValueError("No bounded GSS record offsets in supported table")
    if any(TABLE_BASE+offset >= end for offset in offsets):
        raise ValueError("GSS saved record offset is outside declared byte length")
    by_offset = {}
    warnings = []
    for i, offset in enumerate(offsets):
        start = TABLE_BASE + offset
        stop = TABLE_BASE+offsets[i+1] if i+1 < len(offsets) else end
        length = stop-start
        if not 2 <= length <= MAX_SYMBOL_RECORD:
            warnings.append(f"Candidate record +0x{start:X} withheld: length {length} unsupported")
            continue
        raw = bytes(data[start:stop])
        if raw[:1] != b"\xc1":
            warnings.append(f"Candidate record +0x{start:X} withheld: leading tag is not C1")
            continue
        if i+1 < len(offsets) and not raw.endswith(b"\xff\x00"):
            warnings.append(f"Candidate record +0x{start:X} withheld: missing FF00 boundary")
            continue
        status = "delimited" if raw.endswith(b"\xff\x00") else "open-tail"
        by_offset[offset] = (start, raw, status)
    slots = []
    seen = set()
    for ordinal, offset in enumerate(values, 1):
        if offset not in by_offset:
            continue
        start, raw, status = by_offset[offset]
        slots.append(SavedSymbolSlot(ordinal, start, raw, status, offset in seen))
        seen.add(offset)
    return tuple(slots), tuple(warnings), len(values)-sum(bool(v) for v in values)


def action(name, obj, **kwargs):
    return dict(kind="gss_symbol_action", name=name,
                type="Saved symbol record", note="", request=dict(obj=obj, **kwargs))


class SavedSymbolExplorer:
    def __init__(self, image):
        self.image = image
        self._cache = {}

    def slots(self, obj):
        if obj.type_code != "19/0C":
            raise ValueError("Not a GSS primary")
        key = (obj.segment.start_lba, obj.segment.virtual_address)
        if key not in self._cache:
            capacity = min(MAX_PRIMARY_READ, obj.segment.pages*512)
            primary = read_prefix(self.image, obj.segment, capacity)
            self._cache[key] = decode_gss_symbol_slots(
                primary, type_code=obj.type_code)
        return self._cache[key]

    def rows(self, obj, start=0, slot=None):
        if not isinstance(start, int) or start < 0:
            raise ValueError("Invalid GSS symbol-record page")
        entries, warnings, empty = self.slots(obj)
        if slot is not None:
            if not isinstance(slot, int) or not 1 <= slot <= SLOT_COUNT:
                raise ValueError("SLOT must be 1..176")
            selected = next((s for s in entries if s.ordinal == slot), None)
            if selected is None:
                return [section("Saved slot unavailable", [
                    f"GSS {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
                    f"Saved table slot {slot} is empty or unsupported, not a decoded record.",
                    "No record bytes inferred from unrelated storage.", *warnings])]
            rows = [section("Saved GSS byte record", [
                f"GSS {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
                f"Saved table slot {selected.ordinal} of {SLOT_COUNT}; primary +0x{selected.offset:X}",
                f"Reconstructed sequence length {len(selected.raw)} bytes; boundary {selected.status}",
                f"Leading byte C1; duplicate-slot alias: {'yes' if selected.alias else 'no'}",
                "Binary bytes are not a verified character, vector drawing, glyph, code point or executable instruction.",
                "Final sequence may be open-tailed; FF00 is supported only between successive offsets.",
                *warnings])]
            for n in range(0,len(selected.raw),32):
                chunk=selected.raw[n:n+32]
                rows.append(section(f"Record bytes {n+1}-{n+len(chunk)}", [
                    f"Primary +0x{selected.offset+n:X}",
                    chunk.hex(" ").upper()]))
            return rows
        rows = [section("Saved GSS symbol slots", [
            f"GSS {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
            f"176 saved pointer slots; {len(entries)} bounded record-slot views; {empty} zero/unused slots",
            f"Duplicate offset aliases: {sum(entry.alias for entry in entries)}",
            "Strict supported 004A/4009 variant; offsets relative to +0x124, raw records begin C1.",
            "Only reconstructed record boundaries and raw bytes are shown; no graphics/font semantics proven.",
            f"Withheld record warnings: {len(warnings)}",
            *warnings[:8]] )]
        if start:
            rows.append(action("Previous 50", obj, start=max(0,start-WINDOW)))
        if start+WINDOW<len(entries):
            rows.append(action("Next 50",obj,start=start+WINDOW))
        for s in entries[start:start+WINDOW]:
            row=action(f"Saved slot {s.ordinal}",obj,slot=s.ordinal)
            row["note"]=(f"primary +0x{s.offset:X}; {len(s.raw)} bytes; "
                         f"{s.status}{'; alias' if s.alias else ''}")
            rows.append(row)
        return rows
