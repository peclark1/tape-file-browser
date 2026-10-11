"""Read-only CISC V2R3 19/37 binding-directory saved 48-byte entries.

On five independently examined Mark V2R3 *BNDDIR primaries:
 +0x100 00 01 00 00; +0x104 u32 count;
 +0x112 u16 0x0030; +0x116 u16 count*48;
 +0x130 begins count fixed 48-byte entries.
Each entry has two ten-byte CP037 right-padded names at +0/+10 and a
two-byte target MI type at +20. All observed library tokens are *LIBL.
The remaining 26 bytes have NOT been assigned field semantics.
Pete B10 contains no corroborated 19/37 primary; that release is NOT
claimed supported. Name/type matching is candidate identity, not a
linker dependency, search-list resolution or an actual bound procedure.
"""
from dataclasses import dataclass
import fnmatch
import re

from as400_capabilities import read_prefix, section, object_row

HEADER = bytes.fromhex("00010000")
COUNT_AT = 0x104
STRIDE_AT = 0x112
SIZE_AT = 0x116
ENTRY_AT = 0x130
STRIDE = 48
MAX_ENTRIES = 512
PAGE_ENTRIES = 50
MAX_READ = ENTRY_AT + MAX_ENTRIES * STRIDE
TYPE_NAMES = {"02/03": "*SRVPGM", "03/01": "*MODULE"}
VALID_NAME = re.compile(r"[A-Z#$@][A-Z0-9_#$@]{0,9}")
LIB_TOKEN = re.compile(r"(?:[A-Z#$@][A-Z0-9_#$@]{0,9}|\*[A-Z0-9#$@]{1,9})")
FILTER_NAME = re.compile(r"[A-Z0-9_#$@*?]{1,32}")


def _name(raw, *, token=False):
    if len(raw) != 10:
        raise ValueError("Saved binding directory name is truncated")
    text = raw.decode("cp037", errors="replace").rstrip(" ")
    pattern = LIB_TOKEN if token else VALID_NAME
    if not pattern.fullmatch(text) or text.ljust(10).encode("cp037") != raw:
        raise ValueError("Unsupported saved binding-directory name padding")
    return text


@dataclass(frozen=True)
class BindingEntry:
    ordinal: int
    offset: int
    name: str
    library_token: str
    target_type: str
    raw: bytes

    @property
    def target_type_name(self):
        return TYPE_NAMES.get(self.target_type)


def decode_binding_entries(data, *, type_code):
    """Fail closed on invalid count/stride/size; preserve unknown target types."""
    if type_code != "19/37":
        raise ValueError("Not a saved binding directory")
    if len(data) < ENTRY_AT or data[0x100:0x104] != HEADER:
        raise ValueError("Unsupported or truncated CISC binding-directory control")
    count = int.from_bytes(data[COUNT_AT:COUNT_AT+4], "big")
    stride = int.from_bytes(data[STRIDE_AT:STRIDE_AT+2], "big")
    saved_size = int.from_bytes(data[SIZE_AT:SIZE_AT+2], "big")
    if count > MAX_ENTRIES or stride != STRIDE or saved_size != count * STRIDE:
        raise ValueError("Unsupported BNDDIR saved count, record stride or byte length")
    end = ENTRY_AT + saved_size
    if end > len(data):
        raise ValueError("Truncated BNDDIR saved entry array or virtual extent gap")
    records = []
    for i in range(count):
        at = ENTRY_AT + STRIDE*i
        raw = bytes(data[at:at+STRIDE])
        records.append(BindingEntry(
            ordinal=i+1, offset=at,
            name=_name(raw[:10]),
            library_token=_name(raw[10:20], token=True),
            target_type=f"{raw[20]:02X}/{raw[21]:02X}",
            raw=raw))
    return tuple(records)


def action(label, obj, **kwargs):
    return dict(kind="binding_entry_action", name=label,
                type="Saved binding entry", note="",
                request=dict(obj=obj, **kwargs))


class BindingDirectoryExplorer:
    def __init__(self, image, inventory):
        self.image = image
        self._directories = tuple(o for o in inventory.objects
                                  if o.type_code == "19/37")
        self._candidates = {}
        for target in inventory.objects:
            if target.type_code not in TYPE_NAMES:
                continue
            self._candidates.setdefault(
                (target.type_code, target.name.upper()), []).append(target)
        for targets in self._candidates.values():
            targets.sort(key=lambda o:(o.library_name or "",
                                       o.segment.start_lba))
        self._cache = {}
        self._reverse = None
        self._withheld_directories = 0

    def entries(self, obj):
        if obj.type_code != "19/37":
            raise ValueError("Not a saved binding-directory primary")
        origin = (obj.segment.start_lba, obj.segment.virtual_address)
        if origin not in self._cache:
            raw = read_prefix(self.image, obj.segment, MAX_READ)
            self._cache[origin] = decode_binding_entries(
                raw, type_code=obj.type_code)
        return self._cache[origin]

    def _matches(self, entry):
        if entry.target_type not in TYPE_NAMES:
            return ()
        # Even if stored token is *LIBL, do not assume a particular
        # system library-list state or resolved target library.
        candidates = self._candidates.get((entry.target_type,
                                           entry.name), ())
        if entry.library_token == "*LIBL":
            return candidates
        # A non-LIBL explicit saved library token can be compared by
        # exact name; this still does not establish a binary pointer.
        return tuple(c for c in candidates if
                     (c.library_name or "").upper() == entry.library_token)

    def _reverse_index(self):
        if self._reverse is None:
            links = {}
            missing = 0
            for directory in self._directories:
                try:
                    entries = self.entries(directory)
                except (OSError, ValueError):
                    missing += 1
                    continue
                for entry in entries:
                    for target in self._matches(entry):
                        identity = (target.segment.start_lba,
                                    target.segment.virtual_address)
                        links.setdefault(identity, []).append((directory, entry))
            for refs in links.values():
                refs.sort(key=lambda r:(r[0].name, r[0].library_name or "",
                                        r[0].segment.start_lba,
                                        r[1].ordinal))
            self._reverse, self._withheld_directories = links, missing
        return self._reverse

    def rows(self, obj, start=0, name="*", entry=None):
        if obj.type_code == "02/03":
            if entry is not None:
                raise ValueError("A service program does not own a binding-directory entry")
            origin = (obj.segment.start_lba, obj.segment.virtual_address)
            matches = self._reverse_index().get(origin, ())
            rows = [section("Saved service-program binding references", [
                f"SRVPGM {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
                f"Binding-directory records with corroborated name/type candidates: {len(matches)}",
                f"Unrecoverable BNDDIR primaries withheld: {self._withheld_directories}",
                "*LIBL is a saved library search token, not a resolved historical library.",
                "Entries are candidate identity matches, NOT verified actual linker bindings, exports or activation.",
                "Select the exact saved directory entry for original record bytes."])]
            for directory, binding in matches:
                a = action(f"Entry {binding.ordinal} in {directory.name}",
                           directory, entry=binding)
                a["note"] = (
                    f"BNDDIR primary LBA {directory.segment.start_lba}; "
                    f"record +0x{binding.offset:X}; {binding.library_token} "
                    "name/type candidate")
                rows.append(a)
            if not matches:
                rows.append(section("No recovered saved directory entry", [
                    "No supported BNDDIR name/type record matched this exact recovered service program.",
                    "This does not prove the program had no historical bindings."]))
            return rows

        if obj.type_code != "19/37":
            raise ValueError("Expected *BNDDIR or *SRVPGM")
        if not isinstance(start, int) or start < 0:
            raise ValueError("Invalid saved entry page")
        if not isinstance(name, str) or not FILTER_NAME.fullmatch(name):
            raise ValueError("NAME must be a simple uppercase binding-name glob")
        entries = self.entries(obj)
        if entry is not None:
            if entry not in entries:
                raise ValueError("Saved binding record is not from the selected primary")
            targets = self._matches(entry)
            rows = [section("Saved binding-directory entry", [
                f"BNDDIR {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
                f"Entry ordinal {entry.ordinal}; exact primary +0x{entry.offset:X}; {len(entry.raw)} bytes",
                f"Candidate name: {entry.name}; saved library search token: {entry.library_token}",
                f"Two-byte target MI type: {entry.target_type} ({entry.target_type_name or 'unknown'})",
                "Original 48 bytes: " + entry.raw.hex(" ").upper(),
                "Opaque 26-byte tail: " + entry.raw[22:].hex(" ").upper(),
                f"Recovered primaries with supported name/type and allowed library candidate: {len(targets)}",
                "*LIBL does NOT certify which library or version a historical binder selected.",
                "No linker import/export, procedure call or runtime dependency is decoded."])]
            rows.extend(object_row(t,
                "Saved 48-byte BNDDIR entry name/type candidate only; choose source LBA")
                        for t in targets)
            if not targets:
                rows.append(section("No recovered target candidate", [
                    "No independently recovered target primary matches supported name/type resolution.",
                    "Missing modules/secondary libraries cannot be inferred absent historically."]))
            return rows

        filtered = [(i,e) for i,e in enumerate(entries)
                    if fnmatch.fnmatchcase(e.name,name)]
        rows = [section("Saved binding-directory entries", [
            f"BNDDIR {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
            f"Validated 48-byte saved records: {len(entries)}; matching NAME({name}): {len(filtered)}",
            "Each record has two padded ten-byte name slots and a two-byte raw target MI type.",
            "Only independently recovered target primaries can be navigated; *LIBL is unresolved.",
            "Record order does not establish loader precedence or actual resolved bindings.",
            "Supported 19/37 structure is Mark V2R3 evidence; Pete B10 remains unverified."])]
        if start:
            rows.append(action("Previous",obj,start=max(0,start-PAGE_ENTRIES),name=name))
        if start+PAGE_ENTRIES < len(filtered):
            rows.append(action("Next",obj,start=start+PAGE_ENTRIES,name=name))
        for i,e in filtered[start:start+PAGE_ENTRIES]:
            a = action(f"Entry {e.ordinal} {e.name}",obj,entry=e)
            a["note"] = (f"record +0x{e.offset:X}; {e.library_token}, "
                         f"target {e.target_type_name or e.target_type}")
            rows.append(a)
        return rows
