"""QDIDX -> OIRS identity corroboration; no arbitrary repository payload display."""
import fnmatch
import re
from dataclasses import dataclass
from as400_dasd import decode_context_machine_index
from as400_capabilities import read_prefix,section,object_row
from as400_records import read_range
from as400_object_types import lookup


@dataclass(frozen=True)
class DirectoryEntry:
    raw: bytes
    terminal_offset: int

    @property
    def name(self):return self.raw[2:12].decode('cp037').rstrip(' ')
    @property
    def code(self):return self.raw[:2].hex().upper()
    @property
    def ordinal(self):return int.from_bytes(self.raw[16:20],'big')


def decode_directory_index(data,virtual_address):
    if len(data)<0x42e or data[0x100:0x106]!=bytes.fromhex('60000018000c'):
        raise ValueError('Unsupported or truncated QDIDX header')
    root=int.from_bytes(data[0x420:0x426],'big')-virtual_address
    count=int.from_bytes(data[0x426:0x42a],'big')
    if count==0:return (),('Stored active count is zero; no tree traversed.',)
    t=decode_context_machine_index(data,root_offset=root,page_size=int.from_bytes(data[0x42a:0x42e],'big'),strict_pages=True)
    entries=[];warnings=list(t.warnings)
    for e in t.entries:
        if len(e.raw)!=24 or not re.fullmatch(r'[A-Z#$@][A-Z0-9_#$@.]{0,9}',e.raw[2:12].decode('cp037').rstrip(' ')):
            warnings.append(f'Unsupported directory terminal +0x{e.terminal_element_offset:X}; withheld');continue
        entries.append(DirectoryEntry(e.raw,e.terminal_element_offset))
    if len(entries)!=count:warnings.append(f'Active-count scalar {count}; supported recovered entries {len(entries)}.')
    return tuple(entries),tuple(dict.fromkeys(warnings))


def action(name,obj,start=0,entry=None):
    return dict(kind='directory_action',name=name,type='Directory',note='',request=dict(obj=obj,start=start,entry=entry))


class DirectoryExplorer:
    def __init__(self,image,inventory):
        self.image,self.inventory=image,inventory;self._cache={}
        self._repos={};self._indexes={};self._primaries={}
        for obj in inventory.objects:
            if obj.type_code=='19/52':self._repos.setdefault(obj.name,[]).append(obj)
            if obj.type_code=='0E/90':self._indexes.setdefault(obj.name,[]).append(obj)
            self._primaries.setdefault((f'{obj.object_type:02X}{obj.object_subtype:02X}',obj.name,obj.library_name),[]).append(obj)

    def rows(self,obj,start=0,entry=None):
        if obj.type_code=='19/52':
            rows=[section('Repository evidence',[f'OIRS {obj.name}; LBA {obj.segment.start_lba}',
                  'Select a same-name QDIDX candidate. Each slot is checked independently against its index type/name.',
                  'The shared name alone does not prove repository ownership. No arbitrary record payload is displayed.'])]
            rows.extend(object_row(o,'same-name QDIDX candidate; per-entry identity corroboration required')
                        for o in self._indexes.get(obj.name,()))
            if len(rows)==1:rows.append(section('No index',['No same-name QDIDX was recovered; repository records are not guessed.']))
            return rows
        if obj.type_code!='0E/90':raise ValueError('Not a directory index or repository')
        if entry is not None:return self.entry_rows(obj,entry)
        if not isinstance(start,int) or start<0:raise ValueError('Invalid directory window')
        key=obj.segment.start_lba
        if key not in self._cache:self._cache[key]=decode_directory_index(read_prefix(self.image,obj.segment,8*1024*1024),obj.segment.virtual_address)
        entries,warnings=self._cache[key]
        rows=[section('Directory summary',[f'QDIDX {obj.name}; LBA {key}; entries {len(entries)}',
               '24-byte index entries carry a 12-byte type/name key and empirical repository-slot ordinal.',
               'Select an entry to cross-check its identity in candidate OIRS repositories.',
               'Recovered directory evidence does not certify active objects or recover missing payloads.',*warnings])]
        if start:rows.append(action('Previous',obj,max(0,start-50)))
        if start+50<len(entries):rows.append(action('Next',obj,start+50))
        for e in entries[start:start+50]:
            row=action(e.name,obj,entry=e);info=lookup(e.code)
            row['type']=info.name if info else e.code
            row['note']=f'OIRS ordinal {e.ordinal}; terminal +0x{e.terminal_offset:X}'
            rows.append(row)
        return rows

    def entry_rows(self,obj,entry):
        rows=[section('Index identity',[f'QDIDX {obj.name}; LBA {obj.segment.start_lba}',
              f'Type {entry.code}; name {entry.name}; candidate ordinal {entry.ordinal}',
              'Only type/name and cross-check results are shown; repository attributes remain undecoded.'])]
        candidates=self._repos.get(obj.name,())
        for repo in candidates:
            try:
                if entry.ordinal<1:raise ValueError('Non-positive slot ordinal')
                header=read_range(self.image,repo.segment,entry.ordinal*512,16)
                matches=header[4:16]==entry.raw[:12]
                lines=[f'OIRS LBA {repo.segment.start_lba}; slot +0x{entry.ordinal*512:X}',
                       'Type/name exactly corroborated.' if matches else 'TYPE/NAME MISMATCH; do not use this slot as the selected object.',
                       'The 512-byte slot relationship is empirical; other attributes are not decoded.']
                rows.append(section('Repository match' if matches else 'Repository mismatch',lines))
            except (OSError,ValueError) as exc:rows.append(section('Repository unavailable',[str(exc)]))
        if not candidates:rows.append(section('Repository missing',['No same-name OIRS primary was recovered. Index identity survives independently.']))
        matches=self._primaries.get((entry.code,entry.name,obj.name),())
        rows.append(section('Primary candidates',[f'{len(matches)} recovered primaries match type/name and library name {obj.name}.',
                    'Library name is a scope candidate, not an object pointer. All duplicates are retained.']))
        rows.extend(object_row(o,'directory type/name/library-name candidate') for o in matches)
        return rows
