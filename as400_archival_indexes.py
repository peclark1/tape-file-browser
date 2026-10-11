"""Bounded, read-only CISC SCHIDX and MSRVI release-2 index-key browser.

No scheduler, service-record, job status, owner pointer or record-content
semantics are implied. Reconstructed keys remain opaque bytes. Page roots
and 1024/2048 page sizes were observed on both independent original images.
"""
from dataclasses import dataclass

from as400_dasd import decode_context_machine_index
from as400_capabilities import read_prefix, section

MAX_PRIMARY_BYTES = 8 * 1024 * 1024
MAX_KEY_SIZE = 256
TYPES = {
    "0E/07": ("SCHIDX", 0xE0, 0x2E),
    "0E/91": ("MSRVI", 0x20, 0x16),
    "0E/D0": ("EDTIDX", 0x20, 0x12),
    "0E/C8": ("SRMIDX", None, None),
}


@dataclass(frozen=True)
class OpaqueIndexEntry:
    raw: bytes
    terminal_offset: int


def decode_archival_index(data, virtual_address, type_code):
    if type_code not in TYPES:
        raise ValueError("Not a supported archival index type")
    kind, leading, last = TYPES[type_code]
    if len(data) < 0x42E:
        raise ValueError("Truncated primary before saved index control fields")
    header = data[0x100:0x106]
    if type_code == "0E/D0":
        if header != bytes.fromhex("200000160012"):
            raise ValueError("Unsupported EDTIDX saved header variant")
    elif type_code == "0E/C8":
        if header not in (bytes.fromhex("200000160006"),
                          bytes.fromhex("20000016000C"),
                          bytes.fromhex("60000032001B")):
            raise ValueError("Unsupported SRMIDX saved header variant")
    elif (header[0:3] != bytes([leading,0,0]) or
          header[4:6] != bytes([0,last])):
        raise ValueError(f"Unsupported {kind} index header; field variant withheld")
    # +0x103 remains an unknown control/layout byte. The observed header
    # scalar at +0x106 has not been proven to be a universal live entry count.
    scalar = int.from_bytes(data[0x106:0x10A], "big")
    root = int.from_bytes(data[0x420:0x426], "big") - virtual_address
    size = int.from_bytes(data[0x42A:0x42E], "big")
    if size not in (1024,2048) or root < 0 or root+size > len(data):
        raise ValueError("Saved index root or release-specific page size is unavailable")
    result = decode_context_machine_index(
        data, root_offset=root, page_size=size, strict_pages=True)
    warnings = list(result.warnings)
    entries = []
    for entry in result.entries:
        if not 1 <= len(entry.raw) <= MAX_KEY_SIZE:
            warnings.append(f"{kind} terminal length {len(entry.raw)} unsupported; withheld")
            continue
        entries.append(OpaqueIndexEntry(bytes(entry.raw),entry.terminal_element_offset))
    if not result.complete:
        warnings.append("Index traversal incomplete; no missing keys synthesized")
    if scalar != len(entries):
        warnings.append(f"Saved +0x106 scalar {scalar} differs from {len(entries)} recovered supported keys; meaning unresolved")
    return tuple(entries), tuple(dict.fromkeys(warnings)), scalar, size


def action(name, obj, **kwargs):
    return dict(kind="archival_index_action", name=name, type="Opaque index evidence",
                note="", request=dict(obj=obj, **kwargs))


class ArchivalIndexExplorer:
    def __init__(self,image):
        self.image=image
        self._cache={}

    def entries(self,obj):
        if obj.type_code not in TYPES:
            raise ValueError("Unsupported saved archival index type")
        key=(obj.segment.start_lba,obj.segment.virtual_address,obj.type_code)
        if key not in self._cache:
            self._cache[key]=decode_archival_index(
                read_prefix(self.image,obj.segment,MAX_PRIMARY_BYTES),
                obj.segment.virtual_address,obj.type_code)
        return self._cache[key]

    def rows(self,obj,start=0,keyhex="",entry=None):
        if not isinstance(start,int) or start<0:raise ValueError("Invalid index page window")
        try:prefix=bytes.fromhex(keyhex)
        except ValueError:raise ValueError("KEYHEX must be complete hexadecimal bytes") from None
        if len(prefix)>MAX_KEY_SIZE:raise ValueError("KEYHEX exceeds maximum key length")
        keys,warnings,scalar,size=self.entries(obj)
        kind=TYPES[obj.type_code][0]
        if entry is not None:
            if entry not in keys:
                raise ValueError("Key is not part of this recovered index")
            rows=[section("Opaque index key",[
                f"{kind} {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
                f"Tree terminal +0x{entry.terminal_offset:X}; reconstructed key length {len(entry.raw)} bytes",
                "Bytes are reconstructed using release-2 front-end/common-text traversal.",
                "Hex and CP037 views are display lenses, not decoded field semantics.",
                "No chronological order, record pointer, scheduler action or service meaning inferred.",
                *warnings])]
            for pos in range(0,len(entry.raw),16):
                part=entry.raw[pos:pos+16]
                rows.append(section(f"+0x{pos:X}",[
                    part.hex(" ").upper(), repr(part.decode("cp037",errors="replace"))]))
            return rows
        candidates=[(i,e) for i,e in enumerate(keys) if e.raw.startswith(prefix)]
        rows=[section("Saved machine-index keys",[
            f"{kind} {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
            f"Recovered supported keys {len(keys)}; prefix matches {len(candidates)}; page size {size}",
            f"Uninterpreted four-byte header scalar +0x106: {scalar}",
            "Tree order only; no action, record type, job status or service function interpreted.",
            *warnings])]
        if start:rows.append(action("Previous",obj,start=max(0,start-50),keyhex=keyhex))
        if start+50<len(candidates):
            rows.append(action("Next",obj,start=start+50,keyhex=keyhex))
        for i,e in candidates[start:start+50]:
            r=action(f"Key {i+1}",obj,entry=e)
            r["note"]=(f"{len(e.raw)} bytes; element +0x{e.terminal_offset:X}; "
                       f"hex prefix {e.raw[:8].hex().upper()}")
            rows.append(r)
        return rows
