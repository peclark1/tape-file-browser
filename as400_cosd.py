"""Evidence-scoped CISC 14/01 *COSD saved eight-profile-slot browser.

Five Mark V2R3 and three Pete B10 physical first primaries preserve:
 raw +0x100 00000001 (Mark) or 000000DF (Pete);
 EBCDIC padded exact EPA-name echo +0x130..+0x137, saved name size +0x138,
 8 saved 48-byte slots beginning at +0x150 with invariant first two bytes.
 The three overlapping names #BATCH/#BATCHSC/#INTER have identical 416-byte
 +0x130..+0x2CF spans on independent originals. The slot fields and numeric
 meanings are *not decoded* beyond exact bytes and empirically confirmed size.
"""
from dataclasses import dataclass
from as400_capabilities import object_row, read_prefix, section

TYPE = "14/01"
START = 0x150
STRIDE = 48
COUNT = 8
END = START + STRIDE * COUNT
PREFIXES = ("1E05", "3C0A", "5A14", "7828",
            "963C", "B450", "D278", "F0A0")
VARIANTS = (1, 0xDF)
FLAGS = (bytes(4), bytes.fromhex("01000000"), bytes.fromhex("02000000"))
MAX_PEERS = 50


@dataclass(frozen=True)
class Profile:
    variant: int
    saved_name: str
    flag: bytes
    slots: tuple[bytes, ...]

    @property
    def entire(self):
        return b"".join(self.slots)


def decode_cosd(data, *, type_code, primary_name):
    if type_code != TYPE:
        raise ValueError("Not a saved CISC COSD primary")
    if len(data) < END:
        raise ValueError("COSD primary is truncated before eight 48-byte slots")
    variant = int.from_bytes(data[0x100:0x104], "big")
    if variant not in VARIANTS or any(data[0x104:0x130]):
        raise ValueError("Unsupported COSD saved release-specific control region")
    name_raw = bytes(data[0x130:0x138])
    try:
        name = name_raw.decode("cp037").rstrip(" ")
    except UnicodeError:
        raise ValueError("Malformed saved COSD name echo") from None
    if not name.startswith("#") or len(name) > 8 or name != primary_name.upper():
        raise ValueError("Saved COSD name echo differs from independent EPA identity")
    if name.ljust(8).encode("cp037") != name_raw:
        raise ValueError("COSD name padding is not supported")
    declared_name_length = int.from_bytes(data[0x138:0x13A], "big")
    saved_count = int.from_bytes(data[0x13A:0x13C], "big")
    flag = bytes(data[0x13C:0x140])
    if declared_name_length != len(name) or saved_count != COUNT or flag not in FLAGS:
        raise ValueError("Unsupported COSD saved header/slot count/flag")
    slots=[]
    for i in range(COUNT):
        at=START+i*STRIDE
        pair=bytes(data[at:at+STRIDE])
        if pair[:2].hex().upper() != PREFIXES[i]:
            raise ValueError(f"Unrecognized COSD 48-byte slot {i+1} header at +0x{at:X}")
        slots.append(pair)
    return Profile(variant,name,flag,tuple(slots))


def action(label,obj,**kwargs):
    return dict(kind="cosd_action",name=label,type="Saved COSD profile",
                note="",request=dict(obj=obj,**kwargs))


class SavedCOSDExplorer:
    def __init__(self,image,inventory):
        self.image=image
        self.objects=tuple(o for o in inventory.objects if o.type_code==TYPE)
        self._cache={}

    def profile(self,obj):
        if obj.type_code!=TYPE:
            raise ValueError("Not a saved COSD primary")
        key=(obj.segment.start_lba,obj.segment.virtual_address)
        if key not in self._cache:
            self._cache[key]=decode_cosd(
                read_prefix(self.image,obj.segment,END),
                type_code=obj.type_code,primary_name=obj.name)
        return self._cache[key]

    def _origin(self,obj):
        return f"COSD {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}"

    def rows(self,obj,slot=None,peer=None):
        if slot is not None and (not isinstance(slot,int) or not 1<=slot<=COUNT):
            raise ValueError("SLOT must be a saved position 1..8")
        p=self.profile(obj)
        if peer is not None:
            q=self.profile(peer)
            slot_mismatches=[sum(a!=b for a,b in zip(s,t))
                             for s,t in zip(p.slots,q.slots)]
            differs=sum(slot_mismatches)
            if slot is not None:
                a,b=p.slots[slot-1],q.slots[slot-1]
                at=START+(slot-1)*STRIDE
                changed=[i for i in range(STRIDE) if a[i]!=b[i]]
                rows=[section(f"Saved COSD slot {slot} exact comparison",[
                    self._origin(obj),
                    f"Compared with {self._origin(peer)}",
                    f"Primary +0x{at:03X}..+0x{at+STRIDE-1:03X}; {len(changed)} of 48 raw bytes differ",
                    "No saved slot bytes have proven class-of-service meanings."])]
                for start in range(0,STRIDE,16):
                    rows.append(section(f"Relative +0x{start:02X}..+0x{start+15:02X}",[
                        "Original: "+a[start:start+16].hex(" ").upper(),
                        "Compared: "+b[start:start+16].hex(" ").upper()]))
                rows.append(section("Exact differing offsets",[
                    ", ".join(f"+0x{at+i:03X}" for i in changed) if changed else
                    "Identical original saved 48-byte slots."]))
                return rows
            rows=[section("Saved COSD profile byte comparison",[
                self._origin(obj),f"Compared with {self._origin(peer)}",
                f"Exact saved slot-byte differences: {differs}/384 across {sum(x>0 for x in slot_mismatches)}/8 slots.",
                f"Source raw +0x100 variant: 0x{p.variant:08X}; compared: 0x{q.variant:08X}.",
                f"Saved flag bytes at +0x13C: {p.flag.hex(' ').upper()} / {q.flag.hex(' ').upper()}.",
                "The 48-byte slot records are compared exactly, not interpreted as routing policy.",
                "Select a slot to compare every original byte; Back restores original selection."])]
            for i,m in enumerate(slot_mismatches):
                row=action(f"Compare slot {i+1} (+0x{START+i*STRIDE:X})",obj,slot=i+1,peer=peer)
                row["note"]=f"{m}/48 original bytes differ"
                rows.append(row)
            return rows
        if slot is not None:
            raw=p.slots[slot-1]
            at=START+(slot-1)*STRIDE
            rows=[section(f"Saved COSD slot {slot} (of 8)",[
                self._origin(obj),
                f"Exact original primary offset +0x{at:03X}..+0x{at+STRIDE-1:03X}.",
                f"First two bytes: {raw[:2].hex(' ').upper()} (observed slot-position marker).",
                "Slot's remaining bytes are unidentified saved configuration values.",
                "No IBM-defined routing interpretation or edits are implied."])]
            for offset in range(0,STRIDE,16):
                rows.append(section(f"Original bytes +0x{at+offset:03X}..+0x{at+offset+15:03X}",[
                    raw[offset:offset+16].hex(" ").upper()]))
            return rows
        peers=[];withheld=0
        for other in self.objects:
            if other is obj:continue
            try: candidate=self.profile(other)
            except (OSError,ValueError):
                withheld+=1
                continue
            changes=sum(a!=b for a,b in zip(p.entire,candidate.entire))
            changed_slots=sum(a!=b for a,b in zip(p.slots,candidate.slots))
            peers.append((changes,changed_slots,other))
        peers.sort(key=lambda x:(x[0],x[1],x[2].library_name or "",x[2].name,x[2].segment.start_lba))
        rows=[section("Saved COSD profile and eight saved slots",[
            self._origin(obj),f"Saved +0x130 eight-byte name echo: {p.saved_name}; verified against EPA identity.",
            f"Raw +0x100 release-specific value: 0x{p.variant:08X}; saved +0x13C flag bytes: {p.flag.hex(' ').upper()}.",
            "Exactly eight 48-byte records at +0x150..+0x2CF across a recovered virtual-page boundary.",
            f"Supported other COSD origins: {len(peers)}; unreadable/unknown variants withheld: {withheld}.",
            "Each selectable slot contains exact original bytes, not decoded communications policy.",
            "Choose a peer comparison to see byte/slot differences and inspect every compared byte."])]
        for i,raw in enumerate(p.slots):
            row=action(f"Saved slot {i+1} (+0x{START+i*STRIDE:X})",obj,slot=i+1)
            row["note"]=f"{raw[:2].hex(' ').upper()}... 48 raw bytes"
            rows.append(row)
        rows.append(section("Compare with other saved COSD objects",[
            "Differences are exact original slot bytes; first-page variant/header fields are reported separately.",
            "Select Compare to drill into exact offsets, or select a peer origin to browse that profile."]))
        for diff,affected,other in peers[:MAX_PEERS]:
            row=action(f"Compare {other.name} @ LBA {other.segment.start_lba}",obj,peer=other)
            row["note"]=f"{diff}/384 raw bytes; {affected}/8 unequal slots"
            rows.append(row)
            rows.append(object_row(other,f"Open original COSD primary; {diff}/384 unequal saved slot bytes"))
        if len(peers)>MAX_PEERS:
            rows.append(section("Further profiles",[
                f"{len(peers)-MAX_PEERS} additional peers not listed; use DSPCOSD COSD(library/name)."]))
        return rows
