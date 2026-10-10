#!/usr/bin/env python3
"""Read-only original-image record/folder workflow checks; aggregate output only."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from as400_dasd import DASDImage
from as400_records import RecordReader,RecordExplorer,StorageCatalog
from as400_capabilities import CapabilityExplorer,read_prefix
from as400_anchors import AnchorExplorer
from as400_5250 import Guided5250
from tools.validate_command_exploration import digest


def validate_recovered(image,inventory,segments):
    counts=Counter();errors=Counter();examples=[]
    catalog=StorageCatalog(inventory,segments)
    for member in inventory.objects:
        if not member.is_member_cursor:continue
        counts['member cursors']+=1
        try:
            reader=RecordReader(image,inventory,segments,member,catalog);window=reader.window()
            counts['direct readers opened']+=1;counts['first-window entries']+=len(window.records)
            counts['first-window deleted hints']+=sum(r.status==0xC0 and r.ordinal>0 for r in window.records)
            counts['first-window unknown statuses']+=sum(r.status not in (0x80,0xC0) and r.ordinal>0 for r in window.records)
            counts['readers with warnings']+=bool(window.warning)
            if len(examples)<3 and window.records and reader.layout.entry_count>1:examples.append((member,reader,window))
            if reader.readable_entries>50:
                start=((reader.readable_entries-1)//50)*50;last=reader.window(start)
                counts['last-window entries']+=len(last.records);counts['last-window warnings']+=bool(last.warning)
        except (OSError,ValueError) as exc:
            errors[str(exc) if isinstance(exc,ValueError) else 'I/O error']+=1
    if not examples:raise ValueError('No original member record workflow could be tested')
    cap=CapabilityExplorer(image,inventory,segments);records=RecordExplorer(image,inventory,segments)
    for member,reader,window in examples:
        # Compare the bounded first window with the preexisting whole-stream decoder.
        storage=image.resolve_member_storage(member,inventory,segments)
        old=image.read_data_space_records(storage)
        if old is None or tuple(old.records[:len(window.records)])!=window.records:
            raise ValueError('Bounded record window differs from legacy whole-stream decoding')
        model=Guided5250(inventory,record_loader=records.rows,capability_loader=cap.rows)
        model.show_records(dict(member=member,mode='choose'));model.open_row(1)
        i=next(i for i,r in enumerate(model.rows()) if r['kind']=='record_entry')
        model.selected=i;model.open_row(i);model.open_row(0);model.back();model.back()
        if model.selected!=i:raise ValueError('Record Back did not preserve selection')
        counts['original record walkthroughs']+=1
    # Actual explicitly selected format flows, retaining its exact LBA.
    for member,reader,window in examples:
        choices=records.choices(member)
        selected=next((r for r in choices if r.get('request',{}).get('fmt') is not None),None)
        if selected is None:continue
        fmt=selected['request']['fmt'];model=Guided5250(inventory,record_loader=records.rows)
        model.show_records(selected['request'])
        row=next((r for r in model.rows() if r['kind']=='record_entry'),None)
        if row is None or not any(f'LBA {fmt.segment.start_lba}' in line for line in row['origin']):
            raise ValueError('Explicit original format identity lost')
        counts['explicit format walkthroughs']+=1
    anchors=AnchorExplorer(image,inventory,segments)
    counts['anchor source cursors']=len(anchors.sources)
    folders=[o for o in inventory.objects if o.type_code=='19/12'];counts['folder primaries']=len(folders)
    if anchors.sources:
        for source in anchors.sources:
            graph=anchors.graph(source);counts['anchor records']+=len(graph.records)
            roots=anchors.rows(source,roots=True)
            root_rows=[r for r in roots if r['kind']=='anchor_action']
            assert all(graph.records[r['request']['ordinal']].parent_key==bytes(8) for r in root_rows)
            counts['anchor roots browsed']+=len(root_rows)
            counts['anchor parent edges']+=sum(len(graph.parents(r)) for r in graph.records.values())
            states=Counter(graph.path_state(r)[0] for r in graph.records.values())
            for key,n in states.items():counts['anchor paths: '+key]+=n
            for folder in folders:
                matches=graph.match(read_prefix(image,folder.segment,65536))
                counts['folders with candidate anchors']+=bool(matches)
                counts['folder anchor candidates']+=len(matches)
            selected=next((o for o in folders if graph.match(read_prefix(image,o.segment,65536))),None)
            if selected:
                model=Guided5250(inventory,capability_loader=lambda o,sample=None:anchors.object_rows(o),anchor_loader=anchors.rows)
                model.explore_object(selected);model.open_row(1);model.selected=1;model.open_row(1);model.open_row(0)
                if model.screen!='details':raise ValueError('Folder anchor drill-down failed')
                model.back();model.back()
                if model.selected!=1:raise ValueError('Anchor Back failed')
                counts['original folder walkthroughs']+=1
    elif folders:
        if anchors.object_rows(folders[0])[-1]['name']!='Unavailable':raise ValueError('Missing anchor source not reported')
        counts['missing anchor source diagnostic verified']+=1
    return {'counts':dict(sorted(counts.items())),'unsupported_readers':dict(errors)}


def validate(path):
    before=digest(path);image=DASDImage(path);scan=image.scan();segments=image.recover_segments(scan)
    inventory=image.recover_objects(scan,segments);result=validate_recovered(image,inventory,segments)
    after=digest(path)
    if before!=after:raise ValueError('Original digest changed')
    return {'image_bytes':Path(path).stat().st_size,'sha256':after,'unchanged':True,**result}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('image');args=p.parse_args()
    print(json.dumps(validate(args.image),indent=2))
