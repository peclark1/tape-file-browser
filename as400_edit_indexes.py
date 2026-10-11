"""Saved CISC V2R3 0E/D0 *EDTIDX 22-byte key/catalog browser.

Four original Mark CISC EDTIDX primaries share +0x100..105 control
20 00 00 16 00 12 and the release-2 machine-index root at +0x420,
page size +0x42A=2048. Probed terminals are 22 bytes:
  +0..1 opaque 2-byte prefix, +2..13 CP037 12-byte name-shaped
  token, +14..21 unknown 8-byte tail.
No historic edit action, record-pointer ownership, user identity
or live index semantics inferred. Older Pete B10 has no primary
EDTIDX signature candidate under this heuristic.
"""
from dataclasses import dataclass
import fnmatch
import re

from as400_capabilities import read_prefix, section
from as400_dasd import decode_context_machine_index

HEADER = bytes.fromhex("200000160012")
MAX_PRIMARY = 8 * 1024 * 1024
KEY_LENGTH = 22
PAGE_ENTRIES = 50
NAME = re.compile(r"[A-Z0-9_#$@*?]{1,12}")
NAME_FILTER = re.compile(r"[A-Z0-9_#$@*?]{1,24}")


@dataclass(frozen=True)
class EditIndexKey:
    raw: bytes
    terminal_offset: int

    @property
    def leading_word(self):
        return int.from_bytes(self.raw[:2],"big")

    @property
    def name_candidate(self):
        if len(self.raw)!=KEY_LENGTH:
            return None
        raw=self.raw[2:14]
        text=raw.decode("cp037",errors="replace").rstrip(" ")
        if not NAME.fullmatch(text) or raw!=text.ljust(12).encode("cp037"):
            return None
        return text


def decode_edit_index(data, virtual_address):
    if len(data)<0x42E or data[0x100:0x106]!=HEADER:
        raise ValueError("Unsupported CISC EDTIDX control header")
    root=int.from_bytes(data[0x420:0x426],"big")-virtual_address
    size=int.from_bytes(data[0x42A:0x42E],"big")
    if size!=2048 or root<0 or root+size>len(data):
        raise ValueError("EDTIDX root or Mark V2R3 2048-byte page is unavailable")
    scalar=int.from_bytes(data[0x106:0x10A],"big")
    tree=decode_context_machine_index(
        data,root_offset=root,page_size=size,strict_pages=True)
    warnings=list(tree.warnings)
    if not tree.complete:
        warnings.append("Incomplete saved index traversal; no missing keys invented")
    result=[]
    for entry in tree.entries:
        if len(entry.raw)!=KEY_LENGTH:
            warnings.append(
                f"EDTIDX key of length {len(entry.raw)} at +0x{entry.terminal_element_offset:X} withheld")
            continue
        result.append(EditIndexKey(bytes(entry.raw),entry.terminal_element_offset))
    return tuple(result),tuple(dict.fromkeys(warnings)),scalar


def action(label,obj,**kwargs):
    return dict(kind="edit_index_action",name=label,
                type="Saved edit-index key",note="",request=dict(obj=obj,**kwargs))


class EditIndexExplorer:
    def __init__(self,image):
        self.image=image
        self._cache={}

    def entries(self,obj):
        if obj.type_code!="0E/D0":
            raise ValueError("Not a recovered edit-index primary")
        origin=(obj.segment.start_lba,obj.segment.virtual_address)
        if origin not in self._cache:
            self._cache[origin]=decode_edit_index(
                read_prefix(self.image,obj.segment,MAX_PRIMARY),
                obj.segment.virtual_address)
        return self._cache[origin]

    def rows(self,obj,start=0,name="*",keyhex="",entry=None):
        if not isinstance(start,int) or start<0:
            raise ValueError("Invalid EDTIDX key-window start")
        if not isinstance(name,str) or not NAME_FILTER.fullmatch(name):
            raise ValueError("NAME must be an uppercase index-token glob")
        try:
            prefix=bytes.fromhex(keyhex)
        except ValueError:
            raise ValueError("KEYHEX must be complete hexadecimal bytes") from None
        if len(prefix)>KEY_LENGTH:
            raise ValueError("KEYHEX exceeds 22-byte saved key")
        keys,warnings,scalar=self.entries(obj)
        if entry is not None:
            if entry not in keys:
                raise ValueError("Saved key does not belong to selected EDTIDX origin")
            return [section("Saved edit-index key",[
                f"EDTIDX {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
                f"Terminal element +0x{entry.terminal_offset:X}; exactly 22 reconstructed bytes",
                f"Uninterpreted leading 2-byte word: 0x{entry.leading_word:04X}",
                f"12-byte name-shaped candidate: {entry.name_candidate or '<opaque>'}",
                f"Original saved raw bytes: {entry.raw.hex(' ').upper()}",
                f"Eight opaque trailing bytes: {entry.raw[14:].hex(' ').upper()}",
                "Leading word is not a verified category or search mode; tail is not a proven pointer.",
                "No historic edit entry, action or CISC object target is decoded.",
                *warnings])]
        candidates=[(i,k) for i,k in enumerate(keys)
                    if k.raw.startswith(prefix) and (
                    name=="*" or (k.name_candidate is not None
                                  and fnmatch.fnmatchcase(k.name_candidate,name)))]
        names=sum(k.name_candidate is not None for k in keys)
        rows=[section("Saved edit-index token catalog",[
            f"EDTIDX {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
            f"Supported complete 22-byte saved keys: {len(keys)}; 12-byte name-shaped tokens: {names}",
            f"NAME({name}) and raw KEYHEX matches: {len(candidates)}",
            f"Uninterpreted 4-byte control scalar +0x106: {scalar}; not a proven entry count",
            "The saved two-byte prefix and eight-byte tail are opaque; select a key for exact evidence.",
            "Mark V2R3 2048-byte release-2 pages; Pete B10 format unverified.",
            *warnings])]
        if start:
            rows.append(action("Previous",obj,start=max(0,start-PAGE_ENTRIES),
                               name=name,keyhex=keyhex))
        if start+PAGE_ENTRIES<len(candidates):
            rows.append(action("Next",obj,start=start+PAGE_ENTRIES,
                               name=name,keyhex=keyhex))
        for i,key in candidates[start:start+PAGE_ENTRIES]:
            text=key.name_candidate or f"Opaque key {i+1}"
            row=action(text,obj,entry=key)
            row["note"]=(f"terminal +0x{key.terminal_offset:X}; "
                         f"prefix {key.leading_word:04X}; key 22 bytes")
            rows.append(row)
        if not candidates:
            rows.append(section("No matching saved token",[
                "No recovered supported key matched this exact saved-byte/name filter.",
                "Unreadable pages and other release variants remain possible."]))
        return rows
