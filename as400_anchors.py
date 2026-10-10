"""Evidence-qualified navigation of the recovered V2R3 DLO anchor graph."""
from collections import defaultdict
from as400_dasd import QAOSSS14AnchorRecord,QAOSSS14_V2_FIELD_LAYOUT,decode_format_fields
from as400_capabilities import read_prefix,section,object_row
from as400_records import RecordReader

MAX_ANCHORS=20000


def anchor_action(name,member,ordinal=None,obj=None,note='',roots=False):
    return dict(kind='anchor_action',name=name,type='Anchor',note=note,
                request=dict(member=member,ordinal=ordinal,obj=obj,roots=roots))


class AnchorGraph:
    def __init__(self,records):
        self.records={r.ordinal:r for r in records}
        if len(self.records)!=len(records):raise ValueError('Duplicate anchor ordinals')
        self.leading=defaultdict(list);self.children=defaultdict(list);self.keys=defaultdict(set)
        zero=bytes(8)
        for r in records:
            if r.leading_key!=zero:self.leading[r.leading_key].append(r)
            if r.parent_key!=zero:self.children[r.parent_key].append(r)
            for key in (r.leading_key,r.record_key):
                if key!=zero:self.keys[key].add(r.ordinal)

    def parents(self,record):
        return self.leading.get(record.parent_key,()) if record.parent_key!=bytes(8) else ()

    def path_state(self,record):
        seen=set();current=record;parts=[]
        while current:
            if current.ordinal in seen:return 'cycle',list(reversed(parts))
            seen.add(current.ordinal);parts.append(current.short_name or current.long_name or '<unnamed>')
            if current.parent_key==bytes(8):return 'root reached',list(reversed(parts))
            parents=self.parents(current)
            if not parents:return 'missing parent',list(reversed(parts))
            if len(parents)>1:return 'ambiguous parent',list(reversed(parts))
            current=parents[0]
        return 'unknown',parts

    def match(self,prefix):
        found=defaultdict(list)
        for offset in range(max(0,len(prefix)-7)):
            for ordinal in self.keys.get(prefix[offset:offset+8],()):found[ordinal].append(offset)
        return dict(found)


class AnchorExplorer:
    def __init__(self,image,inventory,segments):
        self.image,self.inventory,self.segments=image,inventory,segments
        self.sources=[m for m in inventory.objects if m.is_member_cursor and m.member_file_name.upper()=='QAOSSS14']
        self._graphs={};self._matches={};self._schema_checked=False

    def graph(self,member):
        key=member.segment.start_lba
        if key in self._graphs:return self._graphs[key]
        if member not in self.sources:raise ValueError('Selected cursor is not an anchor-source candidate')
        if not self._schema_checked:
            corroborated=False
            for fmt in self.inventory.objects:
                if fmt.type_code!='19/51' or fmt.name.upper()!='WOSFMT14':continue
                fields=decode_format_fields(read_prefix(self.image,fmt.segment,65536))
                values={f.name:(f.offset+1,f.storage_length) for f in fields}
                if all(values.get(name)==pair for name,pair in QAOSSS14_V2_FIELD_LAYOUT.items()):
                    corroborated=True;break
            if not corroborated:raise ValueError('No recovered WOSFMT14 corroborates all 15 anchor field ranges')
            self._schema_checked=True
        reader=RecordReader(self.image,self.inventory,self.segments,member)
        if reader.layout.record_length!=193:raise ValueError('Anchor source does not have the observed 193-byte layout')
        if reader.layout.entry_count>MAX_ANCHORS:raise ValueError('Anchor source exceeds the 20,000-entry safety bound')
        records=[]
        for start in range(0,reader.readable_entries,50):
            window=reader.window(start)
            if window.warning:raise ValueError('Incomplete anchor storage: '+window.warning)
            records.extend(QAOSSS14AnchorRecord.from_data_space_record(r) for r in window.records if r.ordinal)
        if len(records)!=reader.layout.entry_count:raise ValueError('Anchor source has missing declared entries')
        graph=AnchorGraph(records);self._graphs[key]=graph;return graph

    def object_rows(self,obj):
        rows=[section('Evidence',[
            'Choose an anchor source, then inspect exact key occurrences for this object.',
            'Matching anchor keys are candidate associations, not decoded ownership pointers.',
            'Parent edges match WOSEPLDN to the parent leading key; anchor paths are not certified QDLS paths.',
            'Deleted/unknown records remain visible; duplicate keys and cycles are not resolved by guessing.'])]
        if not self.sources:
            return rows+[section('Unavailable',['No recovered QAOSSS14 member cursor; this image cannot supply the anchor graph.',
                                               'Folder identity is retained. Another capture containing the anchor member could resolve this.'])]
        rows.extend(anchor_action(f'Source {i}',m,obj=obj,note=f'QAOSSS14 cursor LBA {m.segment.start_lba}')
                    for i,m in enumerate(self.sources,1))
        rows.extend(anchor_action(f'Roots {i}',m,roots=True,note='Browse anchor roots independently of object identity')
                    for i,m in enumerate(self.sources,1))
        return rows

    def rows(self,member,ordinal=None,obj=None,roots=False):
        graph=self.graph(member)
        if ordinal is None:
            if obj is None:matches={n:[] for n,r in graph.records.items() if not roots or r.parent_key==bytes(8)}
            else:matches=graph.match(read_prefix(self.image,obj.segment,65536))
            rows=[section('Matches',[f'Anchor source cursor LBA {member.segment.start_lba}; records: {len(graph.records)}',
                                    f'Candidate anchors: {len(matches)}. No best-score candidate is chosen.',
                                    'Key search is bounded to the first 64 KiB of the selected primary.',
                                    'Folders can contain child keys; occurrences need not identify the folder itself.',
                                    'Roots view follows anchor records without inferring object ownership.'])]
            rows.extend(anchor_action(graph.records[n].short_name or f'#{n}',member,n,
                note=f'ordinal {n}; status {graph.records[n].status:02X}; key offsets '+','.join(f'+{off:X}' for off in offsets[:8]))
                for n,offsets in sorted(matches.items(),key=lambda item:(min(item[1]) if item[1] else -1,item[0])))
            if not matches:rows.append(section('Unavailable',['No nonzero leading/record-key occurrence matched the bounded primary.']))
            return rows
        record=graph.records.get(ordinal)
        if record is None:raise ValueError('Anchor ordinal is not present in this source')
        state,path=graph.path_state(record)
        rows=[section('Anchor',[f'Source cursor LBA {member.segment.start_lba}; ordinal {ordinal}; status {record.status:02X}',
             f'Short name (20-byte field): {record.short_name}',f'Long name: {record.long_name}',
             f'Leading key: {record.leading_key.hex().upper()}',f'WOSEFILD: {record.record_key.hex().upper()}',
             f'WOSEPLDN: {record.parent_key.hex().upper()}',f'Path state: {state}',
             'Anchor path: '+ '/'.join(path),'Anchor names/paths are evidence, not guaranteed user-facing QDLS paths.'])]
        for parent in graph.parents(record):
            rows.append(anchor_action('Parent: '+(parent.short_name or f'#{parent.ordinal}'),member,parent.ordinal,
                                      note=f'exact leading-key match; ordinal {parent.ordinal}; status {parent.status:02X}'))
        for child in graph.children.get(record.leading_key,()):
            rows.append(anchor_action(child.short_name or f'#{child.ordinal}',member,child.ordinal,
                                      note=f'child key match; ordinal {child.ordinal}; status {child.status:02X}'))
        # Key occurrences remain candidates and retain all duplicate primaries.
        source_key=member.segment.start_lba
        if source_key not in self._matches:
            index=defaultdict(list)
            for candidate in self.inventory.objects:
                if candidate.type_code not in ('19/12','19/0E'):continue
                try:found=graph.match(read_prefix(self.image,candidate.segment,65536))
                except (OSError,ValueError):continue
                for n in found:index[n].append(candidate)
            self._matches[source_key]=index
        rows.extend(object_row(o,'anchor key occurrence only') for o in self._matches[source_key].get(ordinal,()))
        return rows
