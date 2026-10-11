"""Invented record groups and schemas, including incomplete virtual storage."""
import unittest
from types import SimpleNamespace as NS
from dataclasses import replace
from unittest.mock import patch
from as400_dasd import DataSpaceRecord,FormatField
from as400_records import RecordReader,RecordExplorer,field_value,read_range
from as400_capabilities import CapabilityExplorer
from as400_5250 import Guided5250,_draw
from test_type_capabilities import obj,Image,inventory,field_bytes
from test_command_exploration import Screen


def fixture(count=60):
    member=obj('SOURCE.ONE',(0x0D,0x50));member.is_member_cursor=True
    member.member_file_name='SOURCE';member.member_name='ONE'
    qdds=obj('STORAGE',(0x0B,0x90),20,None);file=obj('SOURCE',(0x19,1),30)
    fmt=obj('FORMATA',(0x19,0x51),40);other=obj('FORMATA',(0x19,0x51),50,None)
    cursor=bytearray(1024);cursor[0x300:0x308]=qdds.object_address.to_bytes()
    header=bytearray(1024);header[0x11A:0x11E]=count.to_bytes(4,'big');header[0x13C:0x140]=(11).to_bytes(4,'big')
    fcb=bytearray(1024);fcb[300:310]=fmt.epa.name_raw[:10]
    stream=bytearray(1024)
    for i in range(min(count+1,90)):
        at=32+i*11;stream[at]=0xC0 if i==2 else 0x01 if i==3 else 0x80
        stream[at+1:at+11]=f'{i:010d}'.encode('cp037')
    group=NS(start_lba=90,virtual_address=0xA000,pages=2,owner_key=qdds.object_address.key,
             header=NS(segment_type=0x03B4),extents=(NS(start_lba=90,virtual_address=0xA000,pages=2),))
    otherbytes=field_bytes();otherbytes[0x130+24:0x130+28]=bytes.fromhex('00 08 00 08')
    im=Image([(member,cursor),(qdds,header),(file,fcb),(fmt,field_bytes()),(other,otherbytes)])
    im.pages[90]=bytes(stream[:512]);im.pages[91]=bytes(stream[512:])
    return im,inventory([member,qdds,file,fmt,other]),NS(segments=[group]),member,fmt,other


class RecordExplorerTests(unittest.TestCase):
    def test_bounded_window_default_deleted_unknown_and_final_page(self):
        im,inv,segs,m,fmt,other=fixture();reader=RecordReader(im,inv,segs,m)
        first=reader.window();self.assertEqual(list(range(50)),[r.ordinal for r in first.records])
        self.assertEqual(0xC0,first.records[2].status);self.assertEqual(1,first.records[3].status)
        im.reads=[];last=reader.window(50)
        self.assertEqual(list(range(50,61)),[r.ordinal for r in last.records]);self.assertEqual([91],im.reads)
        for start in (-1,61,'1'):
            with self.assertRaises(ValueError):reader.window(start)

    def test_gap_does_not_shift_later_data_and_complete_entries_only(self):
        im,inv,segs,m,fmt,other=fixture();group=segs.segments[0]
        group.extents=(NS(start_lba=90,virtual_address=0xA000,pages=1),NS(start_lba=91,virtual_address=0xA400,pages=1))
        w=RecordReader(im,inv,segs,m).window()
        self.assertEqual(43,len(w.records));self.assertIn('Entry 43 withheld',w.warning)
        self.assertEqual(42,w.records[-1].ordinal)
        with self.assertRaises(ValueError):read_range(im,group,500,20)
        group.extents=(NS(start_lba=90,virtual_address=0xA000,pages=1),)
        second=NS(start_lba=100,virtual_address=0xB000,pages=2,owner_key=group.owner_key,header=group.header)
        segs.segments.append(second)
        self.assertIn('Gap/overlap',RecordReader(im,inv,segs,m).warning)

    def test_null_or_duplicate_qdds_and_oversized_record_fail_closed(self):
        im,inv,segs,m,fmt,other=fixture();inv.objects.append(inv.objects[1])
        with self.assertRaisesRegex(ValueError,'2 matching'):RecordReader(im,inv,segs,m)
        inv.objects.pop();header=bytearray(im.pages[20]);header[0x13C:0x140]=(100000).to_bytes(4,'big');im.pages[20]=header
        with self.assertRaisesRegex(ValueError,'64 KiB'):RecordReader(im,inv,segs,m)
        cursor=bytearray(im.pages[11]);cursor[0x100:0x108]=bytes(8);im.pages[11]=cursor
        with self.assertRaisesRegex(ValueError,'No direct'):RecordReader(im,inv,segs,m)

    def test_explicit_duplicate_format_preserved_and_outside_fields_not_dropped(self):
        im,inv,segs,m,fmt,other=fixture();service=RecordExplorer(im,inv,segs)
        model=Guided5250(inv,record_loader=service.rows,capability_loader=CapabilityExplorer(im,inv,segs).rows)
        model.show_records(dict(member=m,mode='choose'))
        choices=[(i,r) for i,r in enumerate(model.rows()) if r.get('request',{}).get('fmt') is not None]
        self.assertEqual(2,len(choices));i,row=choices[-1];model.selected=i;model.open_row(i)
        entry=next(i for i,r in enumerate(model.rows()) if r['name']=='#1');model.selected=entry;model.open_row(entry)
        self.assertIn('schema mismatch',model.rows()[1]['note']);model.open_row(1)
        self.assertIn(f'Format: FORMATA LBA {other.segment.start_lba}',model.detail)
        model.back();model.back();self.assertEqual(entry,model.selected)
        model.back();self.assertEqual(i,model.selected)

    def test_page_filters_and_keyboard_size(self):
        im,inv,segs,m,fmt,other=fixture();service=RecordExplorer(im,inv,segs)
        for status,wanted in [('DELETED',[2]),('UNKNOWN',[3])]:
            rows=service.rows(m,fmt,status=status,mode='records')
            self.assertEqual(wanted,[r['record'].ordinal for r in rows if r['kind']=='record_entry'])
        model=Guided5250(inv,record_loader=service.rows);model.show_records(dict(member=m,fmt=fmt,mode='records'))
        nxt=next(i for i,r in enumerate(model.rows()) if r['name']=='Next');model.selected=nxt;model.open_row(nxt)
        self.assertEqual('#50',next(r['name'] for r in model.rows() if r['kind']=='record_entry'))
        with patch('curses.has_colors',return_value=False):
            for h,w in [(24,80),(16,64)]:_draw(Screen(h,w),model)
        model.back();self.assertEqual(nxt,model.selected)

    def test_dspfd_chosen_format_to_member_records(self):
        im,inv,segs,m,fmt,other=fixture();cap=CapabilityExplorer(im,inv,segs);records=RecordExplorer(im,inv,segs)
        model=Guided5250(inv,record_loader=records.rows,capability_loader=cap.rows)
        model.run_command('DSPFD FILE(QGPL/SOURCE)');model.open_row(1)
        self.assertEqual('Records',model.rows()[1]['name']);model.open_row(1);model.open_row(0)
        model.open_row(0);self.assertIn('Format: FORMATA LBA 40',model.detail)

    def test_numeric_corruption_not_presented_as_decimal_and_unknown_types_raw(self):
        f=FormatField(0,'NUM','NUM',2,3,0,2,2,0)
        self.assertEqual('12',field_value(f,bytes.fromhex('f1f2')))
        self.assertIn('invalid numeric',field_value(f,bytes.fromhex('faf2')))
        packed=replace(f,type_code=3,digits=3)
        self.assertEqual('-123',field_value(packed,bytes.fromhex('123d')))
        self.assertIn('invalid numeric',field_value(packed,bytes.fromhex('1231')))
        self.assertIn('raw type',field_value(replace(f,type_code=6),b'AB'))
        self.assertIn('unsupported binary',field_value(replace(f,type_code=0,storage_length=20),bytes(20)))

class RecordSafetyTests(unittest.TestCase):
    def test_overlapping_groups_and_extents_are_not_silently_chosen(self):
        im,inv,segs,m,fmt,other=fixture();group=segs.segments[0]
        segs.segments.append(group)
        with self.assertRaisesRegex(ValueError,'overlapping data groups'):RecordReader(im,inv,segs,m)
        segs.segments.pop();group.extents=(*group.extents,NS(start_lba=99,virtual_address=0xA000,pages=1))
        with self.assertRaisesRegex(ValueError,'Overlapping'):read_range(im,group,32,11)

    def test_profile_cannot_be_used_as_schema_and_payload_is_not_read(self):
        im,inv,segs,m,fmt,other=fixture();profile=obj('ACCOUNT',(8,1),900)
        service=RecordExplorer(im,inv,segs);im.reads=[]
        with self.assertRaisesRegex(ValueError,'not a record format'):service.rows(m,profile,mode='records')
        self.assertNotIn(900,im.reads)

class RecordKeyboardTests(unittest.TestCase):
    def test_actual_numeric_keys_six_and_nine_reach_their_workflows(self):
        import curses
        from as400_5250 import run_curses
        for key,expected in [('6','Raw bytes'),('9','QDDS')]:
            im,inv,segs,m,fmt,other=fixture();records=RecordExplorer(im,inv,segs);cap=CapabilityExplorer(im,inv,segs)
            model=Guided5250(inv,record_loader=records.rows,capability_loader=cap.rows)
            model._goto('members',library='QGPL',file='SOURCE')
            class Keys(Screen):
                def __init__(self):super().__init__(24,80);self.keys=iter([ord(key),10,curses.KEY_F3])
                def getch(self):return next(self.keys)
            with patch('curses.curs_set'),patch('curses.has_colors',return_value=False):run_curses(Keys(),model)
            self.assertEqual('capabilities',model.screen)
            self.assertIn(expected,[r['name'] for r in model.rows()])
