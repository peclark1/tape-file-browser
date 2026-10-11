"""Bounded first-page CISC 0A/01 *DTAQ saved pair evidence, not queue contents.

Three Mark V2R3 QNMACDQ physical primaries corroborate nine 16-byte
0x6C00-tagged entries at +0x170..+0x1FF. First and second six-byte
address-shaped fields have the same high three bytes in each entry and
a strict common low-byte progression. No pointer/queue semantics inferred.
"""
from dataclasses import dataclass
from as400_capabilities import object_row, read_prefix, section

SLOT_BASE=0x170
SLOT_COUNT=9
SLOT_SIZE=16
CONTROL=bytes.fromhex("500000000010000000100000")


@dataclass(frozen=True)
class QueuePair:
    ordinal: int
    offset: int
    first: bytes
    second: bytes
    raw: bytes


@dataclass(frozen=True)
class QueueFirstPage:
    variant: int
    pairs: tuple[QueuePair, ...]


def decode_dtaq_first_page(data, *, type_code):
    if type_code!="0A/01":
        raise ValueError("Not a saved CISC 0A/01 DTAQ primary")
    if len(data)<0x200:
        raise ValueError("DTAQ first logical page is incomplete")
    if data[0x100] not in (0x40,0x50) or data[0x101]!=0:
        raise ValueError("Unsupported DTAQ raw +0x100 control variant")
    if data[0x140:0x14C]!=CONTROL:
        raise ValueError("Unsupported DTAQ +0x140 saved control pattern")
    slots=[]
    for i in range(SLOT_COUNT):
        offset=SLOT_BASE+i*SLOT_SIZE
        raw=bytes(data[offset:offset+SLOT_SIZE])
        first,second=raw[2:8],raw[8:14]
        if (raw[:2]!=b"\x6c\x00" or raw[-2:]!=b"\x00\x00"
                or first[:3]!=second[:3] or not any(first) or not any(second)
                or int.from_bytes(first[3:],"big")!=0x160+i*0x10
                or int.from_bytes(second[3:],"big")!=0x7B0-i*0x60):
            raise ValueError(f"Unrecognized DTAQ first-page pair at +0x{offset:X}")
        slots.append(QueuePair(i+1,offset,first,second,raw))
    return QueueFirstPage(data[0x100],tuple(slots))


def action(obj, pair):
    return dict(kind="dtaq_pair_action",name=f"Pair {pair.ordinal} (+0x{pair.offset:X})",
                type="Saved raw bytes",note=pair.raw.hex(" ").upper(),
                request=dict(obj=obj,slot=pair.ordinal))


class SavedDataQueueExplorer:
    def __init__(self,image,inventory):
        self.image=image
        self.objects=tuple(o for o in inventory.objects if o.type_code=="0A/01")
        self._cache={}

    def header(self,obj):
        if obj.type_code!="0A/01":
            raise ValueError("Not a saved DTAQ primary")
        key=(obj.segment.start_lba,obj.segment.virtual_address)
        if key not in self._cache:
            self._cache[key]=decode_dtaq_first_page(
                read_prefix(self.image,obj.segment,0x200),type_code=obj.type_code)
        return self._cache[key]

    def rows(self,obj,slot=None):
        if slot is not None and (not isinstance(slot,int) or not 1<=slot<=SLOT_COUNT):
            raise ValueError("SLOT must be 1..9")
        head=self.header(obj)
        origin=f"DTAQ {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}"
        if slot is not None:
            p=head.pairs[slot-1]
            return [section(f"Saved DTAQ first-page pair {slot}",[
                origin,f"Saved slot {slot}/9; primary +0x{p.offset:X}..+0x{p.offset+15:X}",
                f"Exact 16 bytes: {p.raw.hex(' ').upper()}",
                f"First six-byte candidate: {p.first.hex(' ').upper()}",
                f"Second six-byte candidate: {p.second.hex(' ').upper()}",
                f"Shared high-three bytes: {p.first[:3].hex(' ').upper()}",
                "Address-shaped bytes are not proven dereferenceable pointers.",
                "No live queue entries/messages, chronology, depth or capacity are decoded."])]
        candidates=[];withheld=0
        for other in self.objects:
            if other is obj:
                continue
            try:
                other_head=self.header(other)
            except (ValueError,OSError):
                withheld+=1
                continue
            if other.name.upper()!=obj.name.upper():
                continue
            matches=sum((a.first[3:],a.second[3:])==(b.first[3:],b.second[3:])
                        for a,b in zip(head.pairs,other_head.pairs))
            candidates.append((matches,other,other_head))
        candidates.sort(key=lambda c:(-c[0],c[1].library_name or "",c[1].segment.start_lba))
        rows=[section("Saved DTAQ first-page raw pairs",[
            origin,f"Observed raw +0x100 control first byte 0x{head.variant:02X}.",
            "Nine corroborated 16-byte raw pairs +0x170..+0x1FF, ending at the first page.",
            "Each pair preserves two six-byte address-shaped strings, not validated addresses.",
            f"Supported same-name historical origins: {len(candidates)}; withheld: {withheld}.",
            "No virtual second-page structure, queue messages or queue count reconstructed.",
            "Inspect a pair or a same-name saved primary and Back."])]
        rows.extend(action(obj,p) for p in head.pairs)
        rows.append(section("Same-name historical candidates",[
            "These are independent recovered primaries with byte-matching EPA names.",
            "Relative byte-pattern comparison does not prove queue history or identity."]))
        rows.extend(object_row(o,f"{matches}/9 relative low-three-byte pairs equal;"
                               f" raw control 0x{other.variant:02X}; link unverified")
                    for matches,o,other in candidates[:50])
        if len(candidates)>50:
            rows.append(section("Additional origins",[f"{len(candidates)-50} further same-name sources withheld."]))
        return rows
