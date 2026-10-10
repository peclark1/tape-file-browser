#!/usr/bin/env python3
"""Opt-in original-image checks; emit aggregate counts only, never recovered text."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from as400_reference_codes import ReferenceCodeExplorer
from as400_libraries import LibraryExplorer
from as400_programs import ProgramExplorer
from as400_cmd import command_exploration
from as400_jobs import JobExplorer
from as400_message_queues import MessageQueueExplorer
from as400_dasd import DASDImage
from as400_messages import MessageExplorer,decode_message_index
from as400_indexes import IndexExplorer
from as400_connections import ConnectionExplorer
from as400_menus import MenuExplorer,menu_references
from as400_directory import DirectoryExplorer,decode_directory_index
from as400_capabilities import CapabilityExplorer,read_prefix
from as400_records import RecordExplorer,RecordReader,read_range
from as400_5250 import Guided5250
from tools.validate_command_exploration import digest


def validate(path, inventory=None, segments=None):
    before=digest(path);image=DASDImage(path)
    if inventory is None or segments is None:
        scan=image.scan();segments=image.recover_segments(scan);inventory=image.recover_objects(scan,segments)
    messages=MessageExplorer(image,inventory,segments);indexes=IndexExplorer(image,inventory,segments)
    references=ReferenceCodeExplorer(image,inventory,segments)
    libraries=LibraryExplorer(inventory)
    programs=ProgramExplorer(image,inventory)
    jobs=JobExplorer(image,inventory);queues=MessageQueueExplorer(image,inventory)
    connections=ConnectionExplorer(image,inventory);menus=MenuExplorer(image,inventory)
    directories=DirectoryExplorer(image,inventory);records=RecordExplorer(image,inventory,segments)
    capabilities=CapabilityExplorer(image,inventory,segments)
    def capability(obj,sample=None):
        if obj.type_code=='02/01':return programs.rows(obj)
        if obj.type_code in ('19/03','0E/01'):return jobs.rows(obj)
        if obj.type_code=='19/16':return menus.rows(obj)
        if obj.type_code in ('10/01','12/01','11/01'):return connections.rows(obj)
        return capabilities.rows(obj,sample)
    model=Guided5250(inventory,reference_loader=references.rows,library_loader=libraries.rows,message_loader=messages.rows,index_loader=indexes.rows,
                    command_definition_loader=lambda o:command_exploration(o,read_prefix(image,o.segment,8192)),
                    directory_loader=directories.rows,queue_loader=queues.rows,record_loader=records.rows,capability_loader=capability)
    counts=Counter();paths=set()
    for obj in inventory.objects:
        if obj.type_code=='0E/08':
            entries,warnings=references.entries(obj)
            counts['RCT indexes']+=1;counts['RCT entries']+=len(entries);counts['RCT warnings']+=len(warnings)
            storage=references._storage.get(obj.segment.owner_key,())
            if len(storage)!=1:counts['RCT indexes without unique storage']+=1
            else:
                for entry in entries:
                    record=references.record(obj,entry)
                    counts['RCT corroborated records']+=1
                    counts['RCT record variant '+entry.key[:1].hex().upper()]+=1
            if entries and counts['RCT record walkthroughs']<3:
                model.show_evidence(dict(obj=obj),references.rows)
                selected=next(i for i,r in enumerate(model.rows()) if r.get("request",{}).get("entry") is not None)
                model.selected=selected;model.open_row(selected)
                expected='Corroborated record' if len(storage)==1 else 'Unavailable'
                if model.rows()[0]['name']!=expected:raise ValueError('RCT record/diagnostic not opened')
                model.back()
                if model.selected!=selected:raise ValueError('RCT selection lost')
                counts['RCT record walkthroughs']+=1;paths.add('RCT key/record or missing storage/back')
        elif obj.type_code=='04/01':
            rows=libraries.rows(obj);counts['library contexts opened']+=1
            entries=libraries._entries.get(obj.object_address.key,())
            for entry in entries:counts['library references '+libraries.status(entry)]+=1
            if entries and counts['library recovery walkthroughs']<3:
                model.show_evidence(dict(obj=obj),libraries.rows)
                i=next(i for i,r in enumerate(model.rows()) if r.get('request',{}).get('entry') is not None)
                model.selected=i;model.open_row(i)
                expected=len(libraries.candidates(rows[i]['request']['entry']))
                if sum('object' in r for r in model.rows())!=expected:raise ValueError('Library candidates lost')
                model.back()
                if model.selected!=i:raise ValueError('Library selection lost')
                counts['library recovery walkthroughs']+=1;paths.add('library reference/all candidates/back')
        elif obj.type_code=='02/01':
            rows=programs.rows(obj);refs=[(i,r) for i,r in enumerate(rows) if r.get('object')]
            counts['program primaries']+=1;counts['programs with name references']+=bool(refs);counts['program name-reference links']+=len(refs)
            commands=[(i,r) for i,r in refs if r['object'].type_code=='19/05']
            if commands and counts['program definition walkthroughs']<3:
                model.explore_object(obj);i,_=commands[0];model.selected=i;model.open_row(i)
                if model.screen!='command_definition':raise ValueError('Program command definition not opened')
                model.back()
                if model.selected!=i:raise ValueError('Program selection lost')
                counts['program definition walkthroughs']+=1;paths.add('program name reference/command definition/back')
        elif obj.type_code in ('19/03','0E/01'):
            rows=jobs.rows(obj);counts[obj.type_code+' job workflow opened']+=1
            for row in rows:
                if row.get('object'):
                    counts['job links to '+row['object'].type_code]+=1
                    if 'unassigned' in row['note']:counts['job unassigned candidates']+=1
            links=[(i,r) for i,r in enumerate(rows) if r.get('object') and r['object'].type_code=='0E/01']
            if obj.type_code=='19/03' and links:
                model.explore_object(obj);i,_=links[0];model.selected=i;model.open_row(i)
                if not any(r.get('object') is obj for r in model.rows()):raise ValueError('Reverse JOBD link missing')
                model.back()
                if model.selected!=i:raise ValueError('JOBD selection lost')
                counts['job forward/reverse/back walkthroughs']+=1;paths.add('job description/queue/reverse/back')
        elif obj.type_code=='19/02':
            queues.rows(obj);refs,_=queues._references[obj.segment.start_lba]
            counts['message queues']+=1;counts['queue definition references']+=len(refs)
            for ref in refs:
                rows=queues.reference_rows(obj,ref);matches=[(i,r) for i,r in enumerate(rows) if r.get('object')]
                counts['queue references with ID confirmed']+=bool(matches)
                counts['queue references without ID confirmed']+=not matches
                if matches and counts['queue definition walkthroughs']<3:
                    model.show_evidence(dict(obj=obj,reference=ref),queues.rows);i,_=matches[0];model.selected=i;model.open_row(i)
                    if not any(r['name']==ref.identifier for r in model.rows()):raise ValueError('Queue ID not followed')
                    model.back()
                    if model.selected!=i:raise ValueError('Queue selection lost')
                    counts['queue definition walkthroughs']+=1;paths.add('queue reference/message definition/back')
        elif obj.type_code=='0E/03':
            entries,warnings=decode_message_index(read_prefix(image,obj.segment,8*1024*1024),obj.segment.virtual_address)
            counts['message files']+=1;counts['message IDs']+=len(entries)
            counts['message warnings']+=len(warnings)
            for entry in entries:
                rows=messages.record_rows(obj,entry)
                for row in rows:
                    if row['name'] in ('First','Second','Ancillary'):
                        counts['validated message '+row['name'].lower()]+=1
                        if row['note']=='Literal text':counts['literal message '+row['name'].lower()]+=1
                    elif 'unavailable' in row['name'].lower():counts['message '+row['name']]+=1
            if entries and 'message ID/record/back' not in paths:
                model.show_evidence(dict(obj=obj),messages.rows)
                i=next(i for i,r in enumerate(model.rows()) if r.get('request',{}).get('entry') is not None)
                model.selected=i;model.open_row(i);model.open_row(0)
                if model.screen!='details':raise ValueError('Message evidence path failed')
                model.back();model.back()
                if model.selected!=i:raise ValueError('Message selection lost')
                paths.add('message ID/record/back')
        elif obj.type_code=='0C/90':
            indexes.rows(obj);layout,t=indexes._cache[obj.segment.start_lba]
            counts['QDDSI opened']+=1;counts['index terminals']+=len(t.entries);counts['partial keys']+=t.partial_key_count
            counts['complete index traversals']+=t.complete
            # Distinct real indexes with exact two-pointer record links.
            for entry in t.entries[:3]:
                if counts['index record walkthroughs']>=3:break
                rows=indexes.entry_rows(obj,entry)
                links=[r for r in rows if r['kind']=='record_action']
                if not links:continue
                try:rr=records.rows(**links[0]['request'])
                except ValueError:counts['record links with missing storage']+=1;continue
                if not any(r['kind']=='record_entry' and r['record'].ordinal==entry.ordinal_hint for r in rr):
                    counts['record links outside recovered range']+=1;continue
                model.show_evidence(dict(obj=obj,entry=entry),indexes.rows)
                i=next(i for i,r in enumerate(model.rows()) if r['kind']=='record_action')
                model.selected=i;model.open_row(i)
                j=next(i for i,r in enumerate(model.rows()) if r['kind']=='record_entry')
                model.open_row(j);model.open_row(0)
                if model.screen!='details':raise ValueError('Key/record path failed')
                model.back();model.back();model.back()
                if model.selected!=i:raise ValueError('Key selection lost')
                counts['index record walkthroughs']+=1;paths.add('key/record/raw/back');break
        elif obj.type_code in ('10/01','12/01','11/01'):
            rows=connections.rows(obj);counts['configuration primaries']+=1
            if any(r.get('object') for r in rows) and 'configuration relationship/back' not in paths:
                model.explore_object(obj);i=next(i for i,r in enumerate(model.rows()) if r.get('object'))
                model.selected=i;model.open_row(i);model.back()
                if model.selected!=i:raise ValueError('Configuration selection lost')
                paths.add('configuration relationship/back')
        elif obj.type_code=='19/16':
            variant,refs=menu_references(read_prefix(image,obj.segment,512));rows=menus.rows(obj)
            counts['menu variant '+f'{variant:02X}']+=1;counts['menu target candidates']+=sum(bool(r.get('object')) for r in rows)
            if refs and 'menu target/back' not in paths:
                model.explore_object(obj)
                candidates=[i for i,r in enumerate(model.rows()) if r.get('object')]
                if candidates:
                    i=candidates[0];model.selected=i;model.open_row(i);model.back()
                    if model.selected!=i:raise ValueError('Menu selection lost')
                    paths.add('menu target/back')
        elif obj.type_code=='0E/90':
            entries,warnings=decode_directory_index(read_prefix(image,obj.segment,8*1024*1024),obj.segment.virtual_address)
            counts['directory indexes']+=1;counts['directory entries']+=len(entries);counts['directory warnings']+=len(warnings)
            for entry in entries:
                rows=directories.entry_rows(obj,entry)
                for row in rows:
                    if row['name'].startswith('Repository '):counts[row['name']]+=1
            if entries and 'directory identity/repository/back' not in paths:
                model.show_evidence(dict(obj=obj),directories.rows)
                i=next(i for i,r in enumerate(model.rows()) if r.get('request',{}).get('entry') is not None)
                model.selected=i;model.open_row(i);model.open_row(1);model.back();model.back()
                if model.selected!=i:raise ValueError('Directory selection lost')
                paths.add('directory identity/repository/back')
    if connections._links is not None:
        counts['configuration address occurrences']=len(connections._links)
        for source,target,at in connections._links:counts[f'configuration {source.type_code}->{target.type_code} +{at:X}']+=1
    after=digest(path)
    if after!=before:raise ValueError('Image hash changed')
    return dict(image_bytes=Path(path).stat().st_size,sha256=after,unchanged=True,
                counts=dict(sorted(counts.items())),paths=sorted(paths))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('image');args=parser.parse_args()
    print(json.dumps(validate(args.image),indent=2))
