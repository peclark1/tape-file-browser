"""Read-only CISC 19/38 WSCST saved TRANSFORM and name-candidate browser.

On 66 Mark V2R3 WSCST physical-primary candidates a strict common
+0x100 outer descriptor has a 0x34-byte wrapper, class 0002,
EBCDIC "TRANSFORM ", repeated 0x34 and data length less 52;
a +0x134 inner descriptor has 0x36, repeated data length and
"TRANSFRM" text. 30-byte padded EBCDIC name-shaped fields at
+0x824/+0x1024 sometimes equal independently recovered WSCST
identities. These are byte/name candidate relations ONLY, not
certified inheritance links, printer models or executed transforms.
Pete B10 has no matching WSCST physical primary signatures yet.
"""
from dataclasses import dataclass
import re

from as400_capabilities import object_row, read_prefix, section

MAX_READ = 65536
NAME_BYTES = 30
FIELD_OFFSETS = (0x824,0x1024)
PREFIX = bytes.fromhex("00000034")
MODE = b"\x00\x02"
TRANSFORM = "TRANSFORM ".encode("cp037")
INNER = "TRANSFRM".encode("cp037")
NAME = re.compile(r"[A-Z@#$][A-Z0-9_@#$]{0,9}")


@dataclass(frozen=True)
class SavedTransformName:
    offset: int
    name: str
    raw: bytes


@dataclass(frozen=True)
class SavedTransformHeader:
    length: int
    references: tuple[SavedTransformName, ...]


def decode_wscst_transform(data, *, type_code):
    if type_code!="19/38":
        raise ValueError("Not a saved WSCST primary")
    if len(data)<0x144:
        raise ValueError("Truncated WSCST outer/nested transform descriptors")
    declared=int.from_bytes(data[0x104:0x108],"big")
    length2=int.from_bytes(data[0x118:0x11C],"big")
    length3=int.from_bytes(data[0x138:0x13C],"big")
    end=0x100+declared
    if (data[0x100:0x104]!=PREFIX or data[0x108:0x10A]!=MODE or
            data[0x10A:0x114]!=TRANSFORM or data[0x114:0x118]!=PREFIX or
            data[0x134:0x138]!=bytes.fromhex("00000036") or
            data[0x13C:0x144]!=INNER or
            declared<0x50 or declared>MAX_READ-0x100 or
            length2!=declared-52 or length3!=length2 or end>len(data)):
        raise ValueError("Unsupported compiled WSCST TRANSFORM variant, length or virtual gap")
    found=[]
    for offset in FIELD_OFFSETS:
        if offset+NAME_BYTES>end:
            continue
        raw=bytes(data[offset:offset+NAME_BYTES])
        name=raw.decode("cp037",errors="replace").rstrip(" ")
        if NAME.fullmatch(name) and name.ljust(NAME_BYTES).encode("cp037")==raw:
            found.append(SavedTransformName(offset,name,raw))
    return SavedTransformHeader(declared,tuple(found))


class WorkstationTransformExplorer:
    def __init__(self,image,inventory):
        self.image=image
        self._objects=tuple(o for o in inventory.objects if o.type_code=="19/38")
        self._by_name={}
        for o in self._objects:
            self._by_name.setdefault(o.name.upper(),[]).append(o)
        for values in self._by_name.values():
            values.sort(key=lambda o:(o.library_name or "",o.segment.start_lba))
        self._cache={}
        self._incoming=None
        self._withheld=0

    def header(self,obj):
        if obj.type_code!="19/38":
            raise ValueError("Not a WSCST primary")
        key=(obj.segment.start_lba,obj.segment.virtual_address)
        if key not in self._cache:
            data=read_prefix(self.image,obj.segment,
                             min(MAX_READ,obj.segment.pages*512))
            self._cache[key]=decode_wscst_transform(data,type_code=obj.type_code)
        return self._cache[key]

    def _reverse_index(self):
        if self._incoming is None:
            index={}
            missing=0
            for source in self._objects:
                try:
                    hdr=self.header(source)
                except (OSError,ValueError):
                    missing+=1
                    continue
                for ref in hdr.references:
                    index.setdefault(ref.name,[]).append((source,ref.offset))
            for group in index.values():
                group.sort(key=lambda p:(p[0].library_name or "",p[0].name,
                                         p[0].segment.start_lba,p[1]))
            self._incoming=index
            self._withheld=missing
        return self._incoming

    def rows(self,obj):
        hdr=self.header(obj)
        rows=[section("Saved WSCST TRANSFORM descriptor",[
            f"WSCST {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
            f"Outer wrapper length 0x34; class 0002; EBCDIC TRANSFORM at primary +0x10A.",
            f"Declared transform bytes {hdr.length} at primary +0x104; echoed length less 52 twice.",
            "Inner record prefix 0x36 at +0x134; EBCDIC TRANSFRM at +0x13C.",
            f"Strict padded name-shaped fields at +0x824/+0x1024: {len(hdr.references)}",
            "These are archived compiled transform/name fields, not certified printer controls, device settings or inheritance.",
            "No transform sequences are executed or sent to a printer."])]
        for ref in hdr.references:
            targets=self._by_name.get(ref.name,())
            rows.append(section(f"Saved candidate at +0x{ref.offset:X}",[
                f"Strict 30-byte EBCDIC padded identifier: {ref.name}",
                f"Original raw bytes: {ref.raw.hex(' ').upper()}",
                f"Recovered same-name WSCST primaries: {len(targets)}",
                "Same-name origin is a candidate correlation ONLY; no validated binary pointer or inheritance."]))
            rows.extend(object_row(target,
                f"Saved transform name at primary +0x{ref.offset:X}; role unproven")
                        for target in targets)
        sources=self._reverse_index().get(obj.name.upper(),())
        rows.append(section("Other saved transforms naming this WSCST",[
            f"Recovered WSCST primaries containing its exact name in one supported slot: {len(sources)}",
            f"Withheld/unsupported WSCST primary sources: {self._withheld}",
            "Reverse links use exact name bytes and original offsets; not proof of active reuse."]))
        rows.extend(object_row(source,
            f"Saved +0x{offset:X} name candidate matches this WSCST; inspect original source")
                    for source,offset in sources[:50])
        if len(sources)>50:
            rows.append(section("More name occurrences",[
                f"{len(sources)-50} additional candidate origins not expanded in this view.",
                "Filter with DSPWSCST WSCST(library/name) to inspect a specific source."]))
        return rows
