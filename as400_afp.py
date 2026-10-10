"""Embedded AFP framing and FOCA coded-font references; no rendering/execution.

Object wrapper offsets are empirical CISC evidence. AFP/FOCA field layouts:
afpcinc.org/wp-content/uploads/2016/08/MODCA-Reference-Mixed-Object-Document-Content-Architecture-Reference.pdf
afpcinc.org/wp-content/uploads/2016/08/FOCA-Reference-Font-Object-Content-Architecture-Reference.pdf
"""
from dataclasses import dataclass
from collections import defaultdict
from as400_capabilities import read_prefix, section, object_row

TYPES = ('19/26', '19/28', '19/36')
MAX_BYTES = 8*1024*1024
NAMES = {
    'D3A88A': 'Begin coded font', 'D3A98A': 'End coded font',
    'D3A887': 'Begin code page', 'D3A987': 'End code page',
    'D3A889': 'Begin font character set', 'D3A989': 'End font character set',
    'D3A78A': 'Coded font control', 'D38C8A': 'Coded font index',
    'D3EEEE': 'No operation',
    'D3A8CD': 'Begin form map', 'D3A9CD': 'End form map',
    'D3A8CC': 'Begin medium map', 'D3A9CC': 'End medium map',
}


@dataclass(frozen=True)
class AFPField:
    offset: int
    code: str
    flags: int
    sequence_bytes: bytes
    payload: bytes


def decode_resource(data):
    if len(data) < 512:
        raise ValueError('Truncated AFP resource wrapper')
    end = 256 + int.from_bytes(data[256:260], 'big')
    if not 521 <= end <= MAX_BYTES:
        raise ValueError('Unsupported AFP resource bound')
    if end > len(data):
        raise ValueError('Declared AFP bytes cross missing virtual storage')
    fields = []; at = 512
    while at < end:
        if at+9 > end or data[at] != 0x5a:
            raise ValueError(f'Invalid/truncated AFP introducer at +0x{at:X}')
        length = int.from_bytes(data[at+1:at+3], 'big')
        if not 8 <= length <= 32767 or at+1+length > end:
            raise ValueError(f'Invalid AFP field length at +0x{at:X}')
        fields.append(AFPField(at, data[at+3:at+6].hex().upper(), data[at+6],
                               bytes(data[at+7:at+9]), bytes(data[at+9:at+1+length])))
        at += length+1
    return tuple(fields)


def field_pairs(fields):
    """Match nested begin/end category codes, without asserting name validity."""
    stack = []; pairs = {}; warnings = []
    for i, field in enumerate(fields):
        if not field.code.startswith('D3'):
            continue
        if field.code[2:4] == 'A8':
            stack.append(i)
        elif field.code[2:4] == 'A9':
            if stack and fields[stack[-1]].code[4:] == field.code[4:]:
                start = stack.pop(); pairs[start] = i; pairs[i] = start
            else:
                warnings.append(f'Unmatched end-category at +0x{field.offset:X}')
    warnings.extend(f'Unclosed begin-category at +0x{fields[i].offset:X}' for i in stack)
    return pairs, tuple(warnings)


def coded_font_references(fields):
    refs = []; warnings = []; control = False; active = False
    for i, field in enumerate(fields):
        if field.code == 'D3A88A':
            active = True; control = False
        elif field.code == 'D3A98A':
            active = False; control = False
        elif field.code == 'D3A78A':
            control = active and field.flags == 0 and field.payload == b'\x19\x01'
        elif field.code == 'D38C8A':
            if not active or not control or field.flags or len(field.payload)%25 or not field.payload:
                warnings.append(f'CFI +0x{field.offset:X}: unsupported control/flags/group length; references withheld')
                continue
            for at in range(0,len(field.payload),25):
                group = field.payload[at:at+25]
                if group[20:24] != bytes(4) or group[24] not in (0, *range(0x41,0xff)):
                    warnings.append(f'CFI +0x{field.offset:X} group {at//25}: unsupported reserved/section bytes')
                    continue
                for role, offset, begin in (('Character set',0,'D3A889'), ('Code page',8,'D3A887')):
                    raw = group[offset:offset+8]
                    if raw[:2] == b'\xff\xff' or raw == b'\x40'*8:
                        warnings.append(f'CFI +0x{field.offset:X}: invalid {role} name');continue
                    refs.append(dict(field=i, role=role, name=raw.decode('cp500').rstrip(' '),
                                     begin=begin, section=group[24],
                                     vertical=int.from_bytes(group[16:18],'big'),
                                     horizontal=int.from_bytes(group[18:20],'big')))
    return tuple(refs), tuple(warnings)


def action(name,obj,**request):
    return dict(kind='afp_action',name=name,type='AFP',note='',request=dict(obj=obj,**request))


class AFPExplorer:
    def __init__(self,image,inventory):
        self.image=image;self._cache={};self._fonts=defaultdict(list)
        for obj in inventory.objects:
            if obj.type_code=='19/26':self._fonts[obj.name].append(obj)

    def fields(self,obj):
        if obj.type_code not in TYPES:raise ValueError('Unsupported AFP resource type')
        key=obj.segment.start_lba
        if key not in self._cache:self._cache[key]=decode_resource(read_prefix(self.image,obj.segment,MAX_BYTES))
        return self._cache[key]

    def rows(self,obj,start=0,field=None,byte_start=0):
        if not isinstance(start,int) or start<0 or not isinstance(byte_start,int) or byte_start<0:
            raise ValueError('Invalid AFP window')
        fields=self.fields(obj);pairs,pair_warnings=field_pairs(fields);refs,ref_warnings=coded_font_references(fields)
        if field is None:
            rows=[section('AFP resource',[f'{obj.name}; {obj.type_code}; primary LBA {obj.segment.start_lba}; fields {len(fields)}',
                'Empirical CISC wrapper: stream +0x200 through +0x100 + u32(+0x100).',
                'AFP field boundaries are validated. Select fields, follow matching category boundaries or inspect coded-font dependencies.',
                'No glyph/page rendering, printer execution, full AFP conformance or complete resource resolution is claimed.',
                *pair_warnings,*ref_warnings])]
            if start:rows.append(action('Previous',obj,start=max(0,start-50)))
            if start+50<len(fields):rows.append(action('Next',obj,start=start+50))
            for i in range(start,min(start+50,len(fields))):
                f=fields[i];row=action(f'{i+1}: {NAMES.get(f.code,f.code)}',obj,field=i)
                row['note']=f'{f.code}; +0x{f.offset:X}; {len(f.payload)} payload bytes';rows.append(row)
            return rows
        if not isinstance(field,int) or not 0<=field<len(fields):raise ValueError('Invalid AFP field selection')
        f=fields[field]
        rows=[section('Structured field',[f'{NAMES.get(f.code,f.code)}; code {f.code}; primary +0x{f.offset:X}',
             f'Flags {f.flags:02X}; trailing introducer bytes {f.sequence_bytes.hex().upper()}; payload {len(f.payload)} bytes',
             'Nonzero flags retain extension/segmentation/padding bytes as opaque; semantic decoding is withheld.',
             'Begin/end links pair category codes; they do not certify resource-name matching or full conformance.',
             *ref_warnings])]
        if field in pairs:rows.append(action('Matching boundary',obj,field=pairs[field]))
        for ref in refs:
            if ref['field']!=field:continue
            rows.append(section(ref['role'],[f"Name {ref['name']}; section {ref['section']:02X}",
                f"Vertical size {ref['vertical']}; horizontal scale {ref['horizontal']} (raw values in 20ths of a point).",
                'Name matching is library-independent; every recovered candidate is retained, with its first AFP field checked.']))
            candidates=self._fonts.get(ref['name'],())
            if not candidates:rows.append(section('Resource missing',['No recovered font-resource primary matches this stored name.']))
            for candidate in candidates:
                try:
                    target=self.fields(candidate)
                    if not target or target[0].code!=ref['begin']:
                        rows.append(section('Resource kind mismatch',[f'Candidate LBA {candidate.segment.start_lba} has a different initial AFP field.']));continue
                    rows.append(object_row(candidate,ref['role']+' name match; AFP begin-kind corroborated; runtime library order unknown'))
                except (OSError,ValueError) as exc:rows.append(section('Resource unavailable',[f'Candidate LBA {candidate.segment.start_lba}: {exc}']))
        if byte_start:rows.append(action('Previous bytes',obj,field=field,byte_start=max(0,byte_start-256)))
        if byte_start+256<len(f.payload):rows.append(action('Next bytes',obj,field=field,byte_start=byte_start+256))
        for at in range(byte_start,min(byte_start+256,len(f.payload)),32):
            chunk=f.payload[at:at+32];rows.append(section(f'Payload +{at:04X}',[chunk.hex(' ').upper(),repr(chunk.decode('cp500')),'CP500 display lens; arbitrary payload is not treated as text.']))
        return rows
