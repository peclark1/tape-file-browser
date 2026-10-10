"""QDDSI keyed navigation with explicit partial keys and candidate RRN links."""
from as400_dasd import DataSpaceIndexLayout,decode_data_space_index_root,MemberStoragePointers
from as400_capabilities import read_prefix,section
from as400_records import action as record_action

WINDOW=50
MAX_INDEX_BYTES=8*1024*1024


def action(name,obj,start=0,entry=None):
    return dict(kind='index_action',name=name,type='Index',note='',
                request=dict(obj=obj,start=start,entry=entry))


class IndexExplorer:
    def __init__(self,image,inventory,segments):
        self.image,self.inventory,self.segments=image,inventory,segments
        self._cache={};self._members=None

    def referencing_members(self,obj,data_space_key):
        if self._members is None:
            self._members={}
            for member in self.inventory.objects:
                if not member.is_member_cursor:continue
                try:pointers=MemberStoragePointers.from_cursor_segment(read_prefix(self.image,member.segment,0x308))
                except (OSError,ValueError):continue
                if pointers.data_index is not None and pointers.data_space is not None:
                    self._members.setdefault((pointers.data_index.key,pointers.data_space.key),[]).append(member)
        return self._members.get((obj.object_address.key,data_space_key),())

    def rows(self,obj,start=0,entry=None):
        if obj.type_code!='0C/90':raise ValueError('Index navigation requires QDDSI')
        if entry is not None:return self.entry_rows(obj,entry)
        if not isinstance(start,int) or start<0:raise ValueError('Invalid index window')
        key=obj.segment.start_lba
        if key not in self._cache:
            data=read_prefix(self.image,obj.segment,MAX_INDEX_BYTES)
            layout=DataSpaceIndexLayout.from_primary_segment(data,virtual_address=obj.segment.virtual_address)
            self._cache[key]=(layout,decode_data_space_index_root(data,layout,virtual_address=obj.segment.virtual_address))
        layout,result=self._cache[key]
        rows=[section('Traversal',[f'QDDSI {obj.name}; LBA {key}',
              f'Recovered terminals: {len(result.entries)}; expected: {result.expected_entries}',
              f'Complete keys: {result.complete_key_count}; partial keys: {result.partial_key_count}',
              f'Pages: {result.page_count}; traversal complete: {result.complete}',
              'Order is recovered tree traversal order, not a new text sort.',
              'RRNs are hints; missing initial record groups and multi-data-space mapping remain limitations.',
              *result.warnings])]
        if start:rows.append(action('Previous',obj,max(0,start-WINDOW)))
        if start+WINDOW<len(result.entries):rows.append(action('Next',obj,start+WINDOW))
        for i,e in enumerate(result.entries[start:start+WINDOW],start):
            row=action(f'Key {i+1}',obj,entry=e)
            row['note']=f'DKEY {e.dkey_index}; RRN hint {e.ordinal_hint}; '+('complete' if e.key_complete else 'PARTIAL')+'; '+e.display_key_bytes[:24].hex().upper()
            rows.append(row)
        return rows

    def entry_rows(self,obj,entry):
        rows=[section('Key evidence',[f'QDDSI {obj.name}; LBA {obj.segment.start_lba}',
              f'Terminal +0x{entry.terminal_element_offset:X}; DKEY {entry.dkey_index}',
              f'Database reference: {entry.database_reference.hex().upper()}; ordinal hint: {entry.ordinal_hint}',
              'Complete user key' if entry.key_complete else 'PARTIAL tree evidence; omitted bytes are unknown',
              entry.display_key_bytes.hex(' ').upper(),
              'CP037 lens: '+repr(entry.display_key_bytes.decode('cp037')),
              'Candidate record links below use exact cursor->QDDSI pointers, never same-name fallback.',
              'Both cursor pointers must match the selected QDDSI and DKEY data space; missing-group origin remains unproven.'])]
        data=read_prefix(self.image,obj.segment,MAX_INDEX_BYTES)
        layout=DataSpaceIndexLayout.from_primary_segment(data,virtual_address=obj.segment.virtual_address)
        if not 0<=entry.dkey_index<len(layout.keys):raise ValueError("DKEY outside layout")
        members=self.referencing_members(obj,layout.keys[entry.dkey_index].data_space.key)
        if entry.ordinal_hint is not None and entry.ordinal_hint>0:
            for member in members:
                row=record_action('Candidate '+member.member_name,member,start=entry.ordinal_hint,
                                  note=f'Raw window starts at RRN hint {entry.ordinal_hint}; cursor LBA {member.segment.start_lba}')
                rows.append(row)
        else:
            rows.append(section('Record link withheld',['No supported positive ordinal; record link withheld.']))
        if not members:rows.append(section('No cursor',['No member matches both this QDDSI and the selected DKEY data-space address.']))
        return rows
