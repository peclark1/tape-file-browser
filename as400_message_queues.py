"""Compound MSGQ definition-reference evidence, not delivered-message decoding."""
import re
from dataclasses import dataclass
from as400_capabilities import read_prefix,section,object_row
from as400_menus import qualified_name
from as400_messages import decode_message_index

MAX_BYTES=1024*1024
MAX_REFERENCES=4096


@dataclass(frozen=True)
class MessageReference:
    offset:int
    file:str
    library:str
    identifier:str


def message_references(data):
    """Observed 09 + two padded names + 06 + seven-byte ID compound pattern.

    Searching a compound pattern does not establish queue-entry boundaries,
    active state, chronology, sender, severity or substitution values.
    """
    result=[]
    for at in range(0x100,min(len(data),MAX_BYTES)-28):
        if data[at]!=9 or data[at+21]!=6:continue
        try:file,library=qualified_name(data,at+1)
        except ValueError:continue
        identifier=data[at+22:at+29].decode('cp037')
        if re.fullmatch(r'[A-Z][A-Z0-9]{2}[0-9A-F]{4}',identifier):
            result.append(MessageReference(at,file,library,identifier))
            if len(result)>=MAX_REFERENCES:break
    return tuple(result)


def action(name,obj,start=0,reference=None):
    return dict(kind='queue_action',name=name,type='Reference',note='',request=dict(obj=obj,start=start,reference=reference))


class MessageQueueExplorer:
    def __init__(self,image,inventory):
        self.image,self.inventory=image,inventory;self._definitions={};self._references={}

    def rows(self,obj,start=0,reference=None):
        if obj.type_code!='19/02':raise ValueError('Not a message queue')
        if reference is not None:return self.reference_rows(obj,reference)
        if not isinstance(start,int) or start<0:raise ValueError('Invalid reference window')
        key=obj.segment.start_lba
        if key not in self._references:
            data=read_prefix(self.image,obj.segment,MAX_BYTES)
            self._references[key]=(message_references(data),len(data))
        refs,size=self._references[key]
        rows=[section('Reference evidence',[f'MSGQ {obj.name}; primary LBA {key}',
              f'Compound definition references found: {len(refs)}; primary bytes sampled: {size}',
              'Offsets order these byte occurrences; they do NOT establish message chronology or active queue entries.',
              'Delivered text, substitutions, sender, time and severity remain undecoded.',
              'Select a reference to check its ID in candidate recovered message files.',
              f'Scan bound {MAX_BYTES} bytes / {MAX_REFERENCES} references; missing virtual extents stop the scan.'])]
        if start:rows.append(action('Previous',obj,max(0,start-50)))
        if start+50<len(refs):rows.append(action('Next',obj,start+50))
        for ref in refs[start:start+50]:
            row=action(ref.identifier,obj,reference=ref);row['note']=f'{ref.library}/{ref.file}; +0x{ref.offset:X}';rows.append(row)
        if not refs:rows.append(section('No supported references',['No supported compound pattern in the sampled bytes; not proof that the saved queue was empty.']))
        return rows

    def reference_rows(self,obj,ref):
        rows=[section('Stored reference',[f'MSGQ {obj.name}; LBA {obj.segment.start_lba}; +0x{ref.offset:X}',
              f'Message-file/name candidate: {ref.library}/{ref.file}; message ID: {ref.identifier}',
              'Pattern is empirical reference evidence, not a decoded delivered-message record.'])]
        candidates=[o for o in self.inventory.objects if o.type_code=='0E/03' and o.name==ref.file and
                    (o.library_name==ref.library or o.library_name is None or ref.library in ('*LIBL','*CURLIB'))]
        for target in candidates:
            key=target.segment.start_lba
            try:
                if key not in self._definitions:
                    entries,warnings=decode_message_index(read_prefix(self.image,target.segment,8*1024*1024),target.segment.virtual_address)
                    self._definitions[key]=({e.identifier for e in entries},warnings)
                ids,warnings=self._definitions[key]
                if ref.identifier not in ids:
                    rows.append(section('ID not recovered',[f'Candidate MSGF LBA {key} has no recovered {ref.identifier}.',*warnings]));continue
                row=object_row(target,'ID exists in recovered index; file association is name-based')
                row['message_pattern']=ref.identifier;rows.append(row)
            except (OSError,ValueError) as exc:rows.append(section('Definition unavailable',[f'MSGF LBA {key}: {exc}']))
        if not candidates:rows.append(section('Message file missing',['No matching MSGF primary recovered; stored reference remains visible.']))
        return rows
