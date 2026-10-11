#!/usr/bin/env python3
"""Opt-in aggregate-only workflow validation against an original read-only HDA."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from as400_dasd import DASDImage
from as400_capabilities import (CapabilityExplorer, decode_translation_table,
                               decode_character_data_area, read_prefix, type_rows)
from as400_5250 import Guided5250
from tools.validate_command_exploration import digest


def walkthroughs(image, inv, segments=None):
    """Real selection/back paths without exporting names or payload content."""
    service=CapabilityExplorer(image,inv,segments)
    model=Guided5250(inv,capability_loader=service.rows)
    checked=[]
    model.run_command('WRKTYP TYPE(*TBL)');model.open_row(0)
    if model.screen!='type_objects' or not model.rows():raise ValueError('Type drill-down failed')
    model.open_row(0);model.open_row(1)
    if model.screen!='details':raise ValueError('Table byte drill-down failed')
    model.back();model.back();model.back();checked.append('type/table/byte/back')
    for obj in inv.objects:
        if obj.type_code!='19/01':continue
        rows=service.file_rows(obj)
        candidates=[(i,r) for i,r in enumerate(rows) if r.get('object') and len(service.format_rows(r['object']))>1]
        if not candidates:continue
        model.explore_object(obj);i,_=candidates[0];model.selected=i;model.open_row(i)
        model.open_row(1)
        if model.screen!='details' or not any('Record offset:' in x for x in model.detail):
            raise ValueError('File/field path failed')
        model.back();model.back()
        if model.selected!=i:raise ValueError('File selection lost')
        checked.append('file/format/field/back');break
    for obj in inv.objects:
        if not obj.is_member_cursor:continue
        rows=service.member_rows(obj)
        i=next((i for i,r in enumerate(rows) if r.get('object')),None)
        if i is None:continue
        model.explore_object(obj);model.selected=i;model.open_row(i)
        if model.screen!='capabilities' or not any(r.get('object') is obj for r in model.rows()):
            raise ValueError('Member/storage reverse path failed')
        model.back()
        if model.selected!=i:raise ValueError('Member selection lost')
        checked.append('member/storage/reverse/back');break
    if len(checked)!=3:raise ValueError('Insufficient original workflow coverage')
    return checked


def validate(path):
    before=digest(path)
    image=DASDImage(path);scan=image.scan();segments=image.recover_segments(scan)
    inv=image.recover_objects(scan,segments);service=CapabilityExplorer(image,inv,segments)
    model=Guided5250(inv,capability_loader=service.rows)
    counts=Counter();errors=Counter();types=Counter(o.type_code for o in inv.objects)
    fixtures={}
    supported={'19/01','19/51','0D/50','0B/90','0C/90','19/06','19/0A','19/0E','06/C1'}
    first={}
    for obj in inv.objects:
        code=obj.type_code
        if code not in supported:continue
        counts[code+' primaries']+=1
        try:
            rows=service.rows(obj)
        except (OSError,ValueError) as exc:
            # No object names, raw bytes or exception messages in exported results.
            errors[code+' '+type(exc).__name__]+=1
            continue
        first.setdefault(code,obj)
        counts[code+' opened']+=1
        counts[code+' navigable rows']+=len(rows)
        if code=='19/51':counts['format fields']+=len(rows)-1
        if code=='19/01':counts['file format candidate links']+=sum('object'in r for r in rows)
        if code=='0D/50':counts['exact member storage links']+=sum('object'in r for r in rows)
        if code=='19/0A':
            value=decode_character_data_area(read_prefix(image,obj.segment,2259),type_pair=(0x19,10))
            counts['character data-area bytes']+=len(value)
        if code=='19/06' and obj.name in ('QASCII','QEBCDIC','QSYSTRNTBL'):
            fixtures[obj.name]=decode_translation_table(read_prefix(image,obj.segment,512),type_pair=(0x19,6))
    for code,obj in first.items():
        if not model.explore_object(obj):raise ValueError('Workflow failed for '+code)
        if model.rows():
            i=next((i for i,r in enumerate(model.rows()) if r['kind']=='capability_section'),None)
            if i is not None:
                model.selected=i;model.open_row(i);model.back()
                if model.selected!=i:raise ValueError('Back failed for '+code)
        model.back()
    if 'QASCII' not in fixtures or 'QSYSTRNTBL' not in fixtures:raise ValueError('Reference tables missing')
    sample='ABC abc 012'
    if sample.encode('cp037').translate(fixtures['QASCII'])!=sample.encode('ascii'):
        raise ValueError('QASCII reference conversion differs')
    if sample.encode('cp037').translate(fixtures['QSYSTRNTBL'])!=sample.upper().encode('cp037'):
        raise ValueError('QSYSTRNTBL reference conversion differs')
    if 'QEBCDIC' in fixtures:
        if bytes(range(256)).translate(fixtures['QASCII']).translate(fixtures['QEBCDIC'])!=bytes(range(256)):
            raise ValueError('Reference table inverse differs')
    if sum(int(r['note'].split()[0]) for r in type_rows(inv)) != len(inv.objects):
        raise ValueError('Catalog counts do not cover recovered objects')
    paths=walkthroughs(image,inv,segments)
    after=digest(path)
    if before!=after:raise ValueError('Original image digest changed')
    return {'image_bytes':Path(path).stat().st_size,'sha256':after,'unchanged':True,
            'recovered_type_count':len(types),'workflow_counts':dict(sorted(counts.items())),
            'withheld':dict(sorted(errors.items())),'reference_checks':sorted(fixtures),'original_ui_paths':paths}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('image')
    args=parser.parse_args();print(json.dumps(validate(args.image),indent=2))
