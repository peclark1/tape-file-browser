"""Empirical MSGF index/record navigation; compressed message text stays opaque."""
import fnmatch
import re
from dataclasses import dataclass
from as400_dasd import decode_context_machine_index
from as400_capabilities import read_prefix, section
from as400_records import read_range

MAX_PRIMARY = 8 * 1024 * 1024
WINDOW = 50


@dataclass(frozen=True)
class MessageEntry:
    identifier: str
    raw: bytes
    terminal_offset: int

    @property
    def offsets(self):
        return tuple(int.from_bytes(self.raw[i:i+4], 'big') for i in (9,13,21))


def decode_message_index(data, virtual_address):
    if len(data) < 0x42e or data[0x100:0x106] != bytes.fromhex('6000002c0007'):
        raise ValueError('Unsupported or truncated MSGF control header')
    count = int.from_bytes(data[0x106:0x10a], 'big')
    if count == 0:
        return (), ('Stored count is zero; no message index traversed.',)
    root = int.from_bytes(data[0x420:0x426], 'big') - virtual_address
    page_size = int.from_bytes(data[0x42a:0x42e], 'big')
    traversal = decode_context_machine_index(data,root_offset=root,page_size=page_size,strict_pages=True)
    entries=[]; warnings=list(traversal.warnings)
    for item in traversal.entries:
        identifier=item.raw[:7].decode('cp037')
        if len(item.raw)!=44 or not re.fullmatch(r'[A-Z][A-Z0-9]{2}[0-9A-F]{4}',identifier):
            warnings.append(f'Unsupported terminal at +0x{item.terminal_element_offset:X}; withheld')
            continue
        entries.append(MessageEntry(identifier,item.raw,item.terminal_element_offset))
    if len(entries)!=count:
        warnings.append(f'Stored count {count}; recovered supported entries {len(entries)}. Listing is incomplete.')
    return tuple(entries), tuple(dict.fromkeys(warnings))


def decode_message_record(data, identifier, role):
    """Validate redundant ID, inclusive length and empirically correlated tag.

    01/02 carry literal first/second text; 81/82 contain compressed bytes.
    10 is an ancillary record, not interpreted as a message description.
    """
    tags={'first':(1,0x81),'second':(2,0x82),'ancillary':(0x10,)}
    if role not in tags or len(data)<16:
        raise ValueError('Unsupported or short message record')
    size=int.from_bytes(data[:4],'big')
    if size!=len(data) or not 16<=size<=65536:
        raise ValueError('Message record length mismatch or outside bound')
    if data[5:12]!=identifier.encode('cp037') or data[4] not in tags[role]:
        raise ValueError('Message record ID/tag does not match selected index entry')
    payload=data[16:]
    if role!='ancillary' and int.from_bytes(data[14:16],'big')!=len(payload):
        raise ValueError('Message payload length mismatch')
    literal=role!='ancillary' and data[4] in (1,2)
    return data[4],payload,literal


def action(name,obj,start=0,pattern='*',entry=None):
    return dict(kind='message_action',name=name,type='Message',note='',
                request=dict(obj=obj,start=start,pattern=pattern,entry=entry))


class MessageExplorer:
    def __init__(self,image,inventory,segments,alert_explorer=None):
        self.image,self.inventory,self.segments=image,inventory,segments
        self.alert_explorer=alert_explorer
        self._cache={}
        self._storage={}
        for segment in segments.segments:
            if segment.header.segment_type==0x0280:
                self._storage.setdefault(segment.owner_key,[]).append(segment)

    def rows(self,obj,start=0,pattern='*',entry=None):
        if obj.type_code!='0E/03':raise ValueError('Not a message-file primary')
        if entry is not None:return self.record_rows(obj,entry)
        if not isinstance(start,int) or start<0:raise ValueError('Invalid message window')
        if pattern=='*ALL':pattern='*'
        key=obj.segment.start_lba
        if key not in self._cache:
            self._cache[key]=decode_message_index(read_prefix(self.image,obj.segment,MAX_PRIMARY),obj.segment.virtual_address)
        entries,warnings=self._cache[key]
        matches=[e for e in entries if fnmatch.fnmatchcase(e.identifier,pattern)]
        rows=[section('Summary',[f'MSGF: {obj.library_name or "<unassigned>"}/{obj.name}; LBA {key}',
              f'Recovered IDs: {len(entries)}; matching {pattern}: {len(matches)}',
              'Empirical 44-byte terminals, active root pointer and stored page size.',
              'Text records require exact owner, offset, repeated ID, length and role tag.',
              'Compressed payloads remain opaque; substitutions are not expanded.',*warnings])]
        if start:rows.append(action('Previous',obj,max(0,start-WINDOW),pattern))
        if start+WINDOW<len(matches):rows.append(action('Next',obj,start+WINDOW,pattern))
        for e in matches[start:start+WINDOW]:
            r=action(e.identifier,obj,entry=e);r['note']=f'Index +0x{e.terminal_offset:X}; select record evidence';rows.append(r)
        return rows

    def alert_reference_rows(self,obj,entry):
        if self.alert_explorer is None:
            return []
        try:
            return self.alert_explorer.alert_rows_for_message_id(obj,entry.identifier)
        except (ValueError,OSError) as exc:
            return [section("Saved alert evidence unavailable", [
                f"Could not cross-check same-name alert-table keys: {exc}",
                "No alert relationship is inferred from missing or unreadable records."])]

    def record_rows(self,obj,entry):
        rows=[section('Index evidence',[f'{obj.name}/{entry.identifier}; primary LBA {obj.segment.start_lba}',
             f'Terminal element +0x{entry.terminal_offset:X}',
             'Raw 44-byte terminal: '+entry.raw.hex(' ').upper(),
             'First/second/ancillary offsets: '+', '.join(f'0x{x:X}' for x in entry.offsets),
             'Severity and remaining terminal fields have not been decoded.'])]
        candidates=self._storage.get(obj.segment.owner_key,[])
        if len(candidates)!=1:
            rows.append(section('Text unavailable',[f'Exact-owner 0280 segments: {len(candidates)}; no implicit substitute.',
                        'IDs remain navigable. Older-release storage/continuations require further evidence.']))
            rows.extend(self.alert_reference_rows(obj,entry))
            return rows
        segment=candidates[0]
        for role,offset in zip(('first','second','ancillary'),entry.offsets):
            if not offset:continue
            try:
                at=32+offset
                head=read_range(self.image,segment,at,16)
                size=int.from_bytes(head[:4],'big')
                if not 16<=size<=65536:raise ValueError('Record length outside 16..65536 bound')
                raw=read_range(self.image,segment,at,size)
                tag,payload,literal=decode_message_record(raw,entry.identifier,role)
                lines=[f'{entry.identifier}: {role}; storage LBA {segment.start_lba}; offset +0x{at:X}',
                       f'ID/length/tag corroborated; tag {tag:02X}; payload {len(payload)} bytes.']
                if literal:
                    lines+=['Literal CP037 text; CCSID not decoded, substitution markers remain stored:',
                            ''.join(c if c.isprintable() else f'\\x{ord(c):02x}' for c in payload.decode('cp037'))]
                else:lines+=['Compressed/ancillary bytes; text semantics are NOT decoded.']
                lines+=['Payload hex (first 256 bytes): '+payload[:256].hex(' ').upper()]
                rows.append(section(role.title(),lines,'Literal text' if literal else 'Opaque payload'))
            except (OSError,ValueError) as exc:rows.append(section(role.title()+' unavailable',[str(exc)]))
        rows.extend(self.alert_reference_rows(obj,entry))
        return rows
