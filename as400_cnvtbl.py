"""Read-only CISC 19/FB *CNVTBL saved paired-byte position browser.

Mark V2R3 has 41 physical primary-signature candidates. All 41 show a
big-endian +0x100 two-byte raw variant 0001 or 0002 and a 256-position
sequence of two-byte entries at +0x102 through +0x301. The bytes are
exposed as pairs, without assigning a value width, endian interpretation,
conversion direction, CCSID or character semantics. The full 0x302
primary prefix must be reconstructed in virtual order, without gaps.
Pete B10 has no 19/FB primary-signature candidate in the current image.
"""
from dataclasses import dataclass

from as400_capabilities import object_row, read_prefix, section

ENTRY_COUNT = 256
TABLE_BASE = 0x102
TABLE_END = TABLE_BASE + ENTRY_COUNT * 2
WINDOW = 32
MAX_PEERS = 50
VARIANTS = (1, 2)


@dataclass(frozen=True)
class SavedConversionTable:
    raw_variant: int
    entries: tuple[bytes, ...]


def decode_cnvtbl(data, *, type_code):
    if type_code != "19/FB":
        raise ValueError("Not a saved CISC 19/FB CNVTBL primary")
    if len(data) < TABLE_END:
        raise ValueError("CNVTBL pair table incomplete: requires primary +0x102..+0x301")
    variant = int.from_bytes(data[0x100:TABLE_BASE], "big")
    if variant not in VARIANTS:
        raise ValueError("Unsupported CISC CNVTBL raw +0x100 variant")
    entries = tuple(bytes(data[TABLE_BASE + n * 2:TABLE_BASE + (n + 1) * 2])
                    for n in range(ENTRY_COUNT))
    return SavedConversionTable(variant, entries)


def action(name, obj, **kwargs):
    return dict(kind="conversion_table_action", name=name,
                type="Saved position", note="", request=dict(obj=obj, **kwargs))


class SavedConversionExplorer:
    def __init__(self, image, inventory):
        self.image = image
        self.objects = tuple(obj for obj in inventory.objects if obj.type_code == "19/FB")
        self._cache = {}

    def table(self, obj):
        if obj.type_code != "19/FB":
            raise ValueError("Not a saved CNVTBL primary")
        key = (obj.segment.start_lba, obj.segment.virtual_address)
        if key not in self._cache:
            prefix = read_prefix(self.image, obj.segment, TABLE_END)
            self._cache[key] = decode_cnvtbl(prefix, type_code=obj.type_code)
        return self._cache[key]

    def rows(self, obj, start=0, position=None):
        if not isinstance(start, int) or not 0 <= start < ENTRY_COUNT or start % WINDOW:
            raise ValueError("Saved CNVTBL page must be a zero-based multiple of 32 in 0..224")
        table = self.table(obj)
        identity = (f"CNVTBL {obj.library_name or '<unassigned>'}/{obj.name}; "
                    f"primary LBA {obj.segment.start_lba}")
        if position is not None:
            if not isinstance(position, int) or not 1 <= position <= ENTRY_COUNT:
                raise ValueError("POS must be 1..256")
            pair = table.entries[position - 1]
            offset = TABLE_BASE + (position - 1) * 2
            return [section(f"Saved position {position} (0x{position - 1:02X})", [
                identity, f"First byte-index {position - 1} / 0x{position - 1:02X}; position is one-based.",
                f"Primary +0x{offset:03X} through +0x{offset + 1:03X}",
                f"Exact saved pair: {pair.hex(' ').upper()}",
                f"First byte 0x{pair[0]:02X}; second byte 0x{pair[1]:02X}.",
                f"Raw +0x100 variant: 0x{table.raw_variant:04X}.",
                "Pair-byte meaning, direction, endian interpretation and CCSID are not decoded.",
                "No conversion or program execution is performed."])]
        peers = []
        withheld = 0
        for other in self.objects:
            if other is obj:
                continue
            try:
                candidate = self.table(other)
            except (OSError, ValueError):
                withheld += 1
                continue
            different = sum(a != b for a, b in zip(table.entries, candidate.entries))
            peers.append((different, other, candidate))
        peers.sort(key=lambda t: (t[0], t[1].library_name or "",
                                  t[1].name, t[1].segment.start_lba))
        equal = sum(d == 0 for d, _, _ in peers)
        rows = [section("Saved CNVTBL paired positions", [
            identity,
            f"Raw +0x100 variant 0x{table.raw_variant:04X}; 256 saved two-byte positions.",
            "Saved position n starts at primary +0x102 + 2*(n-1).",
            f"Showing {start + 1}..{min(ENTRY_COUNT, start + WINDOW)} (1-based).",
            f"Other recovered CNVTBL primaries: {len(self.objects) - 1}; "
            f"supported peers: {len(peers)}; withheld: {withheld}.",
            f"Exact 512-byte saved-entry matches: {equal}.",
            "Peer differences are exact pair-byte inequalities, not conversion semantics.",
            "Only raw pairs, positions and equalities are established; no CCSID or direction is inferred."])]
        if start:
            rows.append(action("Previous 32 positions", obj, start=start - WINDOW))
        if start + WINDOW < ENTRY_COUNT:
            rows.append(action("Next 32 positions", obj, start=start + WINDOW))
        for n in range(start, min(ENTRY_COUNT, start + WINDOW)):
            pair = table.entries[n]
            row = action(f"Position {n + 1:3d} (0x{n:02X})", obj, position=n + 1)
            row["note"] = (f"+0x{TABLE_BASE + 2 * n:03X}: {pair.hex(' ').upper()}; "
                           "saved bytes only")
            rows.append(row)
        rows.append(section("Other saved CNVTBL primaries", [
            f"{len(peers)} supported comparands; {equal} exact entry-array matches.",
            f"{withheld} peers withheld because their virtual data or variant is unsupported.",
            "Navigate a candidate origin to inspect its own table and Back to return.",
            "Nearest comparisons listed by number of unequal 2-byte positions; "
            "the raw +0x100 variant is shown separately."]))
        for differences, other, candidate in peers[:MAX_PEERS]:
            row = object_row(other, f"{differences}/256 differing pairs; "
                             f"raw variant 0x{candidate.raw_variant:04X}; "
                             "byte evidence, not codepage equivalence")
            rows.append(row)
        if len(peers) > MAX_PEERS:
            rows.append(section("Additional peers", [
                f"{len(peers) - MAX_PEERS} candidate comparisons not shown; "
                "filter DSPCNVTBL CNVTBL(library/name)."]))
        return rows
