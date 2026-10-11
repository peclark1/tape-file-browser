"""Read-only CISC product load/definition descriptor identity and text evidence.

Mark V2R3: 40 physical 19/1D *PRDLOD candidates share +0x100 0x14A,
a 24-byte saved text token +0x104, +0x15C EBCDIC '00010200',
and an exact 10-byte padded self-name +0x164 (40/40 observed).
Two Mark *PRDDFN identities have exact same-name *PRDLOD candidates.
Pete B10: four 19/1B *PRDDFN first primaries have +0x100 0x1F0
and 64 strict printable EBCDIC bytes +0x104..+0x143.
Those are observed save layouts, NOT certified product identity fields,
release levels, installation status or binary ownership pointers.
"""
from dataclasses import dataclass

from as400_capabilities import object_row, read_prefix, section

LOD_BYTES = 0x24A
DFN_BYTES = 0x2F0
DFN_TEXT_END = 0x144
MAX_LINKS = 50
LOD_SELECTOR = 0x14A
DFN_SELECTOR = 0x1F0
LOD_CONTROL = "00010200".encode("cp037")
BLANK = 0x40


def _printable(data):
    decoded = data.decode("cp037", errors="replace")
    return all(32 <= ord(c) <= 126 for c in decoded)


@dataclass(frozen=True)
class SavedProductLoad:
    token: bytes
    saved_self_name: str


@dataclass(frozen=True)
class SavedProductDefinition:
    raw_length: int
    first_text: str | None
    second_text: str | None

    @property
    def readable(self):
        return self.first_text is not None


def decode_prdlod(prefix, *, type_code, primary_name):
    if type_code != "19/1D":
        raise ValueError("Not a CISC PRDLOD primary")
    if len(prefix) < LOD_BYTES:
        raise ValueError("Incomplete saved PRDLOD descriptor/virtual extent")
    if int.from_bytes(prefix[0x100:0x104], "big") != LOD_SELECTOR:
        raise ValueError("Unsupported saved PRDLOD descriptor length at +0x100")
    if prefix[0x15C:0x164] != LOD_CONTROL:
        raise ValueError("Unsupported saved PRDLOD +0x15C control bytes")
    if len(primary_name) > 10 or not primary_name:
        raise ValueError("Invalid saved PRDLOD primary name")
    name_bytes = primary_name.upper().ljust(10).encode("cp037")
    if prefix[0x164:0x16E] != name_bytes:
        raise ValueError("PRDLOD saved +0x164 self-name does not match its recovered EPA identity")
    token = bytes(prefix[0x104:0x11C])
    if not _printable(token):
        raise ValueError("Unprintable saved PRDLOD +0x104 text token")
    return SavedProductLoad(token, primary_name.upper())


def decode_prddfn(prefix, *, type_code):
    if type_code != "19/1B":
        raise ValueError("Not a CISC PRDDFN primary")
    if len(prefix) < DFN_TEXT_END:
        raise ValueError("Truncated saved PRDDFN first-page identity region")
    declared = int.from_bytes(prefix[0x100:0x104], "big")
    if declared == DFN_SELECTOR:
        if len(prefix) < DFN_BYTES:
            raise ValueError("Supported older PRDDFN variant is missing declared virtual bytes")
        first, second = bytes(prefix[0x104:0x138]), bytes(prefix[0x138:0x144])
        if not _printable(first) or not _printable(second):
            raise ValueError("Unsupported PRDDFN nonprintable text in older saved variant")
        return SavedProductDefinition(declared, first.decode("cp037").rstrip(),
                                      second.decode("cp037").rstrip())
    return SavedProductDefinition(declared, None, None)


class SavedProductExplorer:
    def __init__(self, image, inventory):
        self.image = image
        self.loads = tuple(o for o in inventory.objects if o.type_code == "19/1D")
        self.definitions = tuple(o for o in inventory.objects if o.type_code == "19/1B")
        self._cache = {}

    def record(self, obj):
        if obj.type_code not in ("19/1D", "19/1B"):
            raise ValueError("Not a saved CISC product load or product definition")
        key = (obj.type_code, obj.segment.start_lba, obj.segment.virtual_address)
        if key not in self._cache:
            limit = LOD_BYTES if obj.type_code == "19/1D" else DFN_BYTES
            prefix = read_prefix(self.image, obj.segment, limit)
            self._cache[key] = (decode_prdlod(prefix, type_code=obj.type_code,
                                             primary_name=obj.name) if obj.type_code == "19/1D"
                                else decode_prddfn(prefix, type_code=obj.type_code))
        return self._cache[key]

    def rows(self, obj):
        info = self.record(obj)
        identity = (f"{obj.type_code} {obj.library_name or '<unassigned>'}/{obj.name}; "
                    f"recovered primary LBA {obj.segment.start_lba}")
        if obj.type_code == "19/1D":
            rows = [section("Saved product-load descriptor", [
                identity, "Supported saved length 0x014A at primary +0x100.",
                "Exact padded ten-byte EPA self-name repeated at +0x164; 0x15C saved control is 00010200 (EBCDIC).",
                f"Saved literal token +0x104..+0x11B: {info.token.decode('cp037')}",
                f"Exact 24 source bytes: {info.token.hex(' ').upper()}",
                "Token is not a decoded PTF/release/version number or installed-product status.",
                "No install/remove/execute capability. This view is archival evidence only."])]
            supported = []
            withheld = 0
            for candidate in self.loads:
                if candidate is obj:
                    continue
                try:
                    other = self.record(candidate)
                except (OSError, ValueError):
                    withheld += 1
                    continue
                if other.token == info.token:
                    supported.append(candidate)
            rows.append(section("Other loads with identical saved tokens", [
                f"Strict byte equality across +0x104..+0x11B: {len(supported)} recovered peer origins.",
                f"Other recovered load primaries withheld: {withheld}.",
                "An equal token is not proof of release/installed-program equivalence."]))
            rows.extend(object_row(item,"Exact saved 24-byte token equality; semantic relationship unverified")
                        for item in supported[:MAX_LINKS])
            if len(supported) > MAX_LINKS:
                rows.append(section("Additional equal tokens", [
                    f"{len(supported)-MAX_LINKS} further matches not shown; filter DSPPRDLOD PRDLOD(library/name)."]))
            other_kind = self.definitions
            label = "*PRDDFN"
        else:
            rows = [section("Saved product-definition descriptor", [
                identity,
                f"Raw +0x100 saved descriptor length: 0x{info.raw_length:08X}; "
                f"{'supported B10 text form' if info.readable else 'variant text semantics withheld'}.",
                "The +0x100 length field is observed raw; its role and full extent semantics remain unproven.",
                ("Literal EBCDIC +0x104..+0x137: " + info.first_text) if info.readable else
                "No readable text extraction for this alternate layout.",
                ("Literal EBCDIC +0x138..+0x143: " + info.second_text) if info.readable else
                "Do not interpret Mark V2R3 blank bytes as missing product names.",
                "Displayed text is not certified vendor, license, product ID, release or entitlement.",
                "No product installation or command execution."])]
            other_kind = self.loads
            label = "*PRDLOD"
        matches = sorted((candidate for candidate in other_kind if candidate.name.upper() == obj.name.upper()),
                         key=lambda item: (item.library_name or "",item.segment.start_lba))
        rows.append(section(f"Same-name saved {label} candidates", [
            f"Exact EPA name match across historical product object types: {len(matches)} recovered origins.",
            "Saved byte/name equality only: no independently proven binary ownership, prerequisite or load chain.",
            "Duplicates, absent matches and unassigned library contexts are preserved."]))
        rows.extend(object_row(item,f"Exact same-name {label} primary; link role unverified")
                    for item in matches[:MAX_LINKS])
        if len(matches)>MAX_LINKS:
            rows.append(section("Further same-name objects", [
                f"{len(matches)-MAX_LINKS} origins not shown; filter product by qualified name."]))
        return rows
