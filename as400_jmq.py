"""Saved Mark V2R3 18/A0 JMQ 16-byte entry-window explorer.

Empirical, read-only: +0x100 80000000, a two-byte count at +0x800,
14 zero control bytes, then count nonzero 16-byte entries from +0x810.
No runtime queue state, message text, slot field interpretation, or
chronological semantics are established. Older Pete B10 has no sampled
JMQ primary signature, so it is *not* claimed to share this layout.
"""
from dataclasses import dataclass
from as400_capabilities import read_prefix, section

HEADER_AT = 0x800
ENTRY_AT = 0x810
ENTRY_BYTES = 16
MAX_ENTRY_COUNT = 256
PRIMARY_CAP = 8192


@dataclass(frozen=True)
class SavedJMQSlot:
    ordinal: int
    offset: int
    raw: bytes


def read_jmq_slots(data, *, type_code):
    if type_code!="18/A0":
        raise ValueError("Not a saved job-message queue")
    if len(data)<ENTRY_AT or data[0x100:0x104]!=bytes.fromhex("80000000"):
        raise ValueError("Truncated or unsupported JMQ primary control prefix")
    if data[HEADER_AT+2:ENTRY_AT]!=bytes(14):
        raise ValueError("Unsupported JMQ header tail; count not trusted")
    count=int.from_bytes(data[HEADER_AT:HEADER_AT+2],"big")
    if count>MAX_ENTRY_COUNT or ENTRY_AT+count*ENTRY_BYTES>PRIMARY_CAP:
        raise ValueError("Unverified or excessive JMQ saved slot count")
    end=ENTRY_AT+count*ENTRY_BYTES
    if end>len(data):
        raise ValueError("Truncated JMQ saved entry window/virtual extent gap")
    slots=[]
    for i in range(count):
        pos=ENTRY_AT+i*ENTRY_BYTES
        raw=bytes(data[pos:pos+ENTRY_BYTES])
        if len(raw)!=ENTRY_BYTES or not any(raw):
            raise ValueError(f"JMQ slot {i+1} is absent/zero inside declared window")
        slots.append(SavedJMQSlot(i+1,pos,raw))
    warnings=[]
    if end+ENTRY_BYTES<=len(data) and any(data[end:end+ENTRY_BYTES]):
        warnings.append("A nonzero slot follows the saved declared count; no extra entry assumed")
    return tuple(slots),count,tuple(warnings)


def action(name,obj,**kwargs):
    return dict(kind="jmq_action",name=name,type="Saved JMQ entry",
                note="",request=dict(obj=obj,**kwargs))


class JobMessageQueueExplorer:
    def __init__(self,image):
        self.image=image
        self._cache={}

    def entries(self,obj):
        if obj.type_code!="18/A0":
            raise ValueError("Not a job message queue")
        key=(obj.segment.start_lba,obj.segment.virtual_address)
        if key not in self._cache:
            header=read_prefix(self.image,obj.segment,ENTRY_AT)
            if len(header)<ENTRY_AT:
                raise ValueError("JMQ header not recovered across virtual extents")
            if header[0x100:0x104]!=bytes.fromhex("80000000") or header[HEADER_AT+2:ENTRY_AT]!=bytes(14):
                raise ValueError("Unrecognized saved JMQ control variant")
            count=int.from_bytes(header[HEADER_AT:HEADER_AT+2],"big")
            if count>MAX_ENTRY_COUNT:
                raise ValueError("JMQ declared count above audited safety bound")
            need=min(PRIMARY_CAP,ENTRY_AT+(count+1)*ENTRY_BYTES)
            data=read_prefix(self.image,obj.segment,need)
            self._cache[key]=read_jmq_slots(data,type_code=obj.type_code)
        return self._cache[key]

    def rows(self,obj,start=0,entry=None):
        if not isinstance(start,int) or start<0:
            raise ValueError("Invalid JMQ saved-entry window")
        entries,count,warnings=self.entries(obj)
        if entry is not None:
            if entry not in entries:raise ValueError("Slot does not belong to chosen JMQ primary")
            return [section("Saved JMQ slot",[
                f"QJOBMSGQ {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
                f"Declared slot ordinal {entry.ordinal}; primary +0x{entry.offset:X}; {len(entry.raw)} bytes",
                "Raw bytes: "+entry.raw.hex(" ").upper(),
                "First 8 bytes (CP037 lens): "+repr(entry.raw[:8].decode("cp037")),
                "Last 8 bytes (CP037 lens): "+repr(entry.raw[8:].decode("cp037")),
                "Two eight-byte halves are for byte navigation only; no pointer or timestamp role is proven.",
                "Saved slot is not a certified live message, sending job, queue position or text.",
                *warnings])]
        rows=[section("Saved job-message queue slots",[
            f"Recovered JMQ {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
            f"Observed u16 header count at +0x800: {count}; complete nonzero 16-byte slots: {len(entries)}",
            "Empirically supported Mark V2R3 layout; older B10 remains unverified.",
            "Saved ordinal is not a message timestamp or historical job chronology.",
            "These are opaque slot bytes; content/body and ownership remain unproven.",
            *warnings])]
        if start:
            rows.append(action("Previous",obj,start=max(0,start-50)))
        if start+50<len(entries):
            rows.append(action("Next",obj,start=start+50))
        for slot in entries[start:start+50]:
            row=action(f"Slot {slot.ordinal}",obj,entry=slot)
            row["note"]=f"Primary +0x{slot.offset:X}; 16 raw bytes; {slot.raw[:4].hex().upper()}"
            rows.append(row)
        return rows
