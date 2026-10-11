"""Bounded CISC 19/D7 *EPTAB saved 16-bit word viewer (read-only).

The sole Mark V2R3 and Pete B10 QDMEPTB primaries are identical in
all 1280 bytes after +0x100 when Pete's third page is reconstructed
from its nonadjacent *virtual* address. First eight bytes at +0x100
are 00 10 00 0E 00 0F 06 B0; exactly 512 u16 big-endian words exist
at +0x100..+0x4FF with zero tail at +0x500..+0x5FF.
These are saved word positions, NOT verified translation, editing,
character set or application semantics.
"""
from dataclasses import dataclass

from as400_capabilities import read_prefix, section

START = 0x100
WORD_COUNT = 512
WORD_BYTES = 2
END = START + WORD_COUNT * WORD_BYTES
PAGE_ENTRIES = 50
SUPPORTED_HEADER = bytes.fromhex("0010000E000F06B0")


@dataclass(frozen=True)
class EPTabWord:
    index: int
    offset: int
    value: int

    @property
    def hex(self):
        return f"{self.value:04X}"


def decode_eptab_words(data, *, type_code):
    if type_code!="19/D7":
        raise ValueError("Not a saved EPTAB primary")
    if len(data)<END or data[START:START+len(SUPPORTED_HEADER)]!=SUPPORTED_HEADER:
        raise ValueError("Truncated or unsupported CISC EPTAB control/table prefix")
    return tuple(EPTabWord(i,START+2*i,
                          int.from_bytes(data[START+2*i:START+2*i+2],"big"))
                 for i in range(WORD_COUNT))


def action(name,obj,**kwargs):
    return dict(kind="eptab_word_action",name=name,
                type="Saved 16-bit EPTAB word",note="",
                request=dict(obj=obj,**kwargs))


class EPTabExplorer:
    def __init__(self,image):
        self.image=image
        self._cache={}

    def words(self,obj):
        if obj.type_code!="19/D7":
            raise ValueError("Not a saved EPTAB primary")
        origin=(obj.segment.start_lba,obj.segment.virtual_address)
        if origin not in self._cache:
            data=read_prefix(self.image,obj.segment,END)
            self._cache[origin]=decode_eptab_words(data,type_code=obj.type_code)
        return self._cache[origin]

    def rows(self,obj,start=0,word="",entry=None):
        if not isinstance(start,int) or start<0:
            raise ValueError("Invalid EPTAB saved-word window")
        if word and (not isinstance(word,str) or len(word)!=4 or
                     any(c not in "0123456789ABCDEF" for c in word)):
            raise ValueError("WORD must contain exactly four hexadecimal digits")
        values=self.words(obj)
        if entry is not None:
            if entry not in values:
                raise ValueError("Word is not from selected recovered EPTAB primary")
            count=sum(v.value==entry.value for v in values)
            return [section("Saved EPTAB word",[
                f"EPTAB {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
                f"Exact zero-based word index: {entry.index}; original primary byte offset +0x{entry.offset:X}",
                f"Raw two bytes: {entry.hex[:2]} {entry.hex[2:]}; unsigned big-endian value {entry.value}",
                f"Same saved u16 value occurs in {count} of 512 positions",
                "This is a stored word, not a proven translation table entry, code point, glyph, or runtime flag.",
                "No EPTAB content, code page, or live system state is modified."])]
        selected=[v for v in values if not word or v.hex==word]
        common=sum(v.value==0x0045 for v in values)
        zero=sum(v.value==0 for v in values)
        rows=[section("Saved EPTAB 16-bit words",[
            f"EPTAB {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
            f"Validated 512 consecutive two-byte words at primary +0x100..+0x4FF (end exclusive).",
            f"Exact value 0045: {common}; 0000: {zero}; other values: {512-common-zero}",
            f"Matches WORD({word or '*'}): {len(selected)}; indexed zero-based word positions.",
            "The leading words include an empirically supported control prefix; not all words are data mappings.",
            "Source is a recovered virtual address stream; unknown field roles remain opaque.",
            "Select a position for original bytes/unsigned value; 50 rows per result page."])]
        if start:
            rows.append(action("Previous",obj,start=max(0,start-PAGE_ENTRIES),word=word))
        if start+PAGE_ENTRIES<len(selected):
            rows.append(action("Next",obj,start=start+PAGE_ENTRIES,word=word))
        for value in selected[start:start+PAGE_ENTRIES]:
            a=action(f"Word {value.index:03d}: {value.hex}",obj,entry=value)
            a["note"]=f"Primary +0x{value.offset:X}; unsigned {value.value}; 2 raw bytes"
            rows.append(a)
        if not selected:
            rows.append(section("No matching saved word",[
                "No supported two-byte value exactly matches this hexadecimal filter.",
                "A word's application meaning or charset is not implied by its numeric value."]))
        return rows
