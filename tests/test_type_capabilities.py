"""Synthetic workflows and corruption cases; no original-image bytes."""
import curses
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from as400_capabilities import (CapabilityExplorer, decode_translation_table,
                               hex_sample, read_prefix, select_objects, type_rows)
from as400_5250 import Guided5250, _draw, run_curses
from as400_dasd import InternalAddress
from test_as400_5250 import FakeInventory, object_record
from test_command_exploration import Screen


def obj(name, pair, lba=10, library="QGPL"):
    o = object_record(name, library, type_code=pair)
    o.segment = NS(start_lba=lba, virtual_address=lba*512,
                   extents=(NS(start_lba=lba, virtual_address=lba*512, pages=2),))
    o.epa = NS(name_raw=name.ljust(30).encode('cp037'))
    o.object_address = InternalAddress.from_bytes((lba*512).to_bytes(8, 'big'))
    return o


class Image:
    def __init__(self, objects):
        self.pages = {}
        self.reads = []
        for o, data in objects:
            for i in range(0, len(data), 512):
                self.pages[o.segment.start_lba + i//512] = data[i:i+512]

    def read_sector(self, lba):
        self.reads.append(lba)
        if lba not in self.pages:
            raise ValueError('Missing test sector')
        return NS(data=self.pages[lba])


def inventory(objects):
    inv = FakeInventory()
    inv.objects = objects
    inv.libraries = []
    inv.context_entries = []
    return inv


def field_bytes():
    b = bytearray(1024)
    at = 0x130
    b[at] = 0x44
    b[at+1:at+21] = ('LABEL'.ljust(10)*2).encode('cp037')
    b[at+21:at+34] = bytes.fromhex('00 04 03 00 02 00 02 00 08 00 00 00 00')
    return b


class TypeCapabilitiesTests(unittest.TestCase):
    def test_complete_catalog_unknown_codes_orphans_and_duplicate_names(self):
        a = obj('SAME', (0x19,6)); b = obj('SAME',(0x19,6),20, None)
        c = obj('MYSTERY',(0x19,0xED),30)
        inv = inventory([a,b,c]); rows = type_rows(inv)
        self.assertEqual(269,len(rows))
        self.assertEqual(['1906'],[r['code'] for r in type_rows(inv,'*TBL')])
        self.assertEqual(rows,type_rows(inv,'*ALL'))
        self.assertIn('2 primaries; 1 unassigned',next(r['note'] for r in rows if r['code']=='1906'))
        self.assertEqual([b],[r['object'] for r in select_objects(inv,'*ORPHAN/*','*TBL')])
        self.assertEqual(2,len(select_objects(inv,'SAME','19/06')))
        self.assertEqual([c],[r['object'] for r in select_objects(inv,object_type='19ED')])
        for pattern, kind in (('A/B/C','*TBL'),('QGPL/','*TBL'),('*','*FAKE')):
            with self.assertRaises(ValueError): select_objects(inv,pattern,kind)

    def test_translation_map_bounds_type_guard_and_noninvertible_maps(self):
        data = bytes(256) + bytes(reversed(range(256)))
        table = decode_translation_table(data,type_pair=(0x19,6))
        self.assertEqual(bytes([255,254,0]),bytes([0,1,255]).translate(table))
        self.assertEqual(bytes(256),decode_translation_table(bytes(512),type_pair=(0x19,6)))
        for size in (0,255,256,511):
            with self.assertRaises(ValueError): decode_translation_table(data[:size],type_pair=(0x19,6))
        with self.assertRaises(ValueError): decode_translation_table(data,type_pair=(8,1))
        self.assertEqual(b'\xc1\xc2',hex_sample('C1 C2'))
        for value in ('', '1','GG','0x12','00'*65):
            with self.assertRaises(ValueError): hex_sample(value)

    def test_virtual_extent_gaps_and_read_cap(self):
        segment = NS(virtual_address=0x1000, extents=(
            NS(start_lba=5,pages=1,virtual_address=0x1000),
            NS(start_lba=90,pages=1,virtual_address=0x1200)))
        im = Image([]);im.pages={5:b'A'*512,90:b'B'*512}
        self.assertEqual(b'A'*512+b'B'*10,read_prefix(im,segment,522))
        im.reads=[]
        self.assertEqual(512,len(read_prefix(im,segment,512)));self.assertEqual([5],im.reads)
        segment.extents[1].virtual_address=0x1400
        self.assertEqual(b'A'*512,read_prefix(im,segment,1024))
        im.pages[5]=b'A'
        with self.assertRaises(ValueError):read_prefix(im,segment,512)

    def test_table_navigation_sample_duplicates_back_and_rendering(self):
        a=obj('SAME',(0x19,6));b=obj('SAME',(0x19,6),20,None)
        data=bytes(256)+bytes(reversed(range(256)))+bytes(512)
        inv=inventory([a,b]);service=CapabilityExplorer(Image([(a,data),(b,data)]),inv)
        model=Guided5250(inv,capability_loader=service.rows)
        self.assertTrue(model.run_command('DSPTBL TBL(SAME) HEX(0001FF)'))
        self.assertEqual('type_objects',model.screen)
        model.selected=1;model.open_row(1)
        self.assertEqual('capabilities',model.screen)
        model.open_row(1);self.assertIn('Output hex: FF FE 00',model.detail)
        model.back();model.selected=3;model.open_row(3);self.assertIn('0x01',model.detail[0]);model.back()
        self.assertEqual(3,model.selected)
        with patch('curses.has_colors',return_value=False):
            for h,w in ((24,80),(16,64)):_draw(Screen(h,w),model)
        model.back();self.assertEqual(1,model.selected)
        self.assertFalse(model.run_command('DSPTBL HEX(00F)'))

    def test_file_format_evidence_duplicate_formats_and_field_drilldown(self):
        file=obj('SOURCE',(0x19,1));fmt=obj('FORMATA',(0x19,0x51),20)
        duplicate=obj('FORMATA',(0x19,0x51),30,None)
        fcb=bytearray(1024);fcb[300:310]=fmt.epa.name_raw[:10];fcb[350:358]=fmt.object_address.to_bytes()
        inv=inventory([file,fmt,duplicate]);service=CapabilityExplorer(Image([(file,fcb),(fmt,field_bytes()),(duplicate,field_bytes())]),inv)
        model=Guided5250(inv,capability_loader=service.rows)
        self.assertTrue(model.run_command('DSPFD FILE(QGPL/SOURCE)'))
        self.assertEqual(3,len(model.rows()))
        self.assertIn('address +0x15E',model.rows()[1]['note'])
        self.assertIn('name only',model.rows()[2]['note'])
        model.selected=1;model.open_row(1);self.assertEqual('LABEL',model.rows()[1]['name'])
        model.open_row(1);self.assertIn('Record offset: 2; storage bytes: 8',model.detail)
        model.back();model.back();self.assertEqual(1,model.selected)

    def test_cursor_direct_address_not_name_and_reverse_navigation(self):
        member=obj('DATA.ONE',(0x0D,0x50));member.is_member_cursor=True
        member.member_file_name='DATA';member.member_name='ONE'
        data=obj('DIFFERENT',(0x0B,0x90),20,None)
        impostor=obj('DATA.ONE',(0x0B,0x90),30)
        cursor=bytearray(1024);cursor[0x300:0x308]=data.object_address.to_bytes()
        body=bytearray(1024);body[0x13C:0x140]=(11).to_bytes(4,'big')
        inv=inventory([member,data,impostor]);im=Image([(member,cursor),(data,body),(impostor,body)])
        service=CapabilityExplorer(im,inv)
        model=Guided5250(inv,capability_loader=service.rows,member_loader=lambda lib,file,m:[f'{lib}/{file}/{m.member_name}'])
        model.run_command('WRKOBJ OBJ(*) OBJTYPE(*MEM)');model.open_row(0,'9')
        links=[(i,r) for i,r in enumerate(model.rows()) if r.get('object')]
        self.assertEqual([data],[r['object'] for i,r in links])
        model.open_row(links[0][0]);refs=[(i,r) for i,r in enumerate(model.rows()) if r.get('object')]
        self.assertEqual([member],[r['object'] for i,r in refs])
        model.open_row(refs[0][0]);self.assertEqual(['QGPL/DATA/ONE'],model.detail)
        model.back();self.assertEqual('capabilities',model.screen)

    def test_read_errors_are_visible_and_profiles_are_never_read(self):
        table=obj('BROKEN',(0x19,6));profile=obj('ACCOUNT',(8,1),20)
        inv=inventory([table,profile]);im=Image([]);service=CapabilityExplorer(im,inv)
        self.assertEqual([],service.rows(profile));self.assertEqual([],im.reads)
        model=Guided5250(inv,capability_loader=service.rows)
        model.run_command('DSPTBL TBL(BROKEN)');model.open_row(0)
        self.assertIn('Missing test sector',model.detail)

    def test_keyboard_loop_catalog_to_objects_and_back(self):
        inv=inventory([obj('MAP',(0x19,6))]);model=Guided5250(inv)
        model.run_command('WRKTYP TYPE(*TBL)')
        class Keys(Screen):
            def __init__(self):super().__init__(24,80);self.keys=iter([10,curses.KEY_F12,curses.KEY_F3])
            def getch(self):return next(self.keys)
        with patch('curses.curs_set'),patch('curses.has_colors',return_value=False):run_curses(Keys(),model)
        self.assertEqual('mi_types',model.screen)

class DataAreaTests(unittest.TestCase):
    def fixture(self, value=b'\xc1\x40\x00\xc2'):
        data=bytearray(1024);data[0x100]=4
        data[0x101:0x103]=len(value).to_bytes(2,'big');data[0x103:0x103+len(value)]=value
        return data

    def test_character_value_length_spaces_and_nuls_not_padding(self):
        from as400_capabilities import decode_character_data_area
        data=self.fixture(); original=bytes(data)
        self.assertEqual(b'\xc1\x40\x00\xc2',decode_character_data_area(data,type_pair=(0x19,10)))
        self.assertEqual(original,bytes(data))
        for selector in (3,0x84,0,0xFF):
            data=self.fixture();data[0x100]=selector
            with self.assertRaisesRegex(ValueError,'withheld'):decode_character_data_area(data,type_pair=(0x19,10))

    def test_header_value_bounds_and_type_gate(self):
        from as400_capabilities import decode_character_data_area
        for size in (0,0x100,0x102,0x106):
            with self.assertRaises(ValueError):decode_character_data_area(self.fixture()[:size],type_pair=(0x19,10))
        for length in (0,2001,65535):
            data=self.fixture();data[0x101:0x103]=length.to_bytes(2,'big')
            with self.assertRaises(ValueError):decode_character_data_area(data,type_pair=(0x19,10))
        with self.assertRaises(ValueError):decode_character_data_area(self.fixture(),type_pair=(8,1))

    def test_data_area_navigation_and_unsupported_variant_diagnostic(self):
        area=obj('SETTING',(0x19,10));inv=inventory([area]);data=self.fixture()
        im=Image([(area,data)]);service=CapabilityExplorer(im,inv);model=Guided5250(inv,capability_loader=service.rows)
        self.assertTrue(model.run_command('DSPDTAARA DTAARA(QGPL/SETTING)'))
        self.assertEqual('1-4',model.rows()[1]['name'])
        model.open_row(1);self.assertIn('Hex: C1 40 00 C2',model.detail);model.back()
        data[0x100]=3;im.pages[area.segment.start_lba]=data[:512]
        model.back();model.run_command('DSPDTAARA DTAARA(SETTING)');model.open_row(0)
        self.assertIn('selector 0x03',model.detail[0])

class DocumentWorkflowTests(unittest.TestCase):
    def setup_docs(self, payload=b'hello\x00world', declared=None):
        doc=obj('DOC001',(0x19,14),library='QDOC');bss=obj('DOC001F',(6,0xC1),20,None)
        bss.segment.pages=2;bss.segment.owner_key=(0,10240)
        data=bytearray(1024);n=len(payload) if declared is None else declared
        data[0x106:0x108]=n.to_bytes(2,'big');data[0x112:0x114]=n.to_bytes(2,'big')
        data[0x10A:0x10C]=(1024).to_bytes(2,'big');data[512:512+len(payload)]=payload
        inv=inventory([doc,bss]);im=Image([(bss,data)]);return doc,bss,inv,im,data

    def test_document_companion_to_validated_bytes_and_back(self):
        doc,bss,inv,im,data=self.setup_docs()
        service=CapabilityExplorer(im,inv);model=Guided5250(inv,capability_loader=service.rows)
        model.run_command('WRKOBJ OBJ(QDOC/*) OBJTYPE(*DOC)');model.open_row(0)
        self.assertIn('name only',model.rows()[1]['note']);model.selected=1;model.open_row(1)
        target=next(i for i,r in enumerate(model.rows()) if r['name']=='+0000')
        model.open_row(target);self.assertIn('68 65 6C 6C 6F 00 77 6F 72 6C 64',' '.join(model.detail))
        model.back();model.back();self.assertEqual(1,model.selected)

    def test_duplicate_companions_remain_selectable_and_bad_lengths_fail(self):
        doc,bss,inv,im,data=self.setup_docs();duplicate=obj('DOC001F',(6,0xC1),30,None);inv.objects.append(duplicate)
        service=CapabilityExplorer(im,inv)
        self.assertEqual(2,sum('object'in r for r in service.document_rows(doc)))
        data[0x112:0x114]=(12).to_bytes(2,'big');im.pages[20]=data[:512]
        with self.assertRaisesRegex(ValueError,'disagree'):service.document_rows(bss)

    def test_continuation_requires_exact_owner_type_and_virtual_contiguity(self):
        doc,bss,inv,im,data=self.setup_docs(b'A'*512,declared=520)
        seg=NS(virtual_address=11264,start_lba=90,pages=2,owner_key=bss.segment.owner_key,
               header=NS(segment_type=0x0F90),extents=(NS(virtual_address=11264,start_lba=90,pages=2),))
        im.pages[90]=bytes(512);im.pages[91]=b'B'*8+bytes(504)
        service=CapabilityExplorer(im,inv,NS(segments=[seg]));rows=service.document_rows(bss)
        summary=next(r for r in rows if r['name']=='Byte stream')
        self.assertIn('Declared/recovered bytes: 520/520',summary['lines'])
        for field,value in (('virtual_address',12288),('owner_key',(99,1))):
            old=getattr(seg,field);setattr(seg,field,value)
            with self.assertRaises(ValueError):service.document_rows(bss)
            setattr(seg,field,old)

class CapabilityTrackerTests(unittest.TestCase):
    def test_all_types_accounted_for_without_generic_navigation_promoting_them(self):
        from tools.mi_capability_progress import progress_rows,markdown,ROOT
        rows=progress_rows()
        self.assertEqual(268,len(rows));self.assertEqual(268,len({r['key'] for r in rows}))
        self.assertEqual(242,sum(r['state']=='queued' for r in rows))
        self.assertEqual(26,sum(r['state']=='partial' for r in rows))
        self.assertFalse(any(r['state']=='delivered' for r in rows))
        self.assertEqual(markdown(rows),(ROOT/'docs/MI_CAPABILITY_PROGRESS.md').read_text())

class OrphanIsolationTests(unittest.TestCase):
    def test_orphan_file_does_not_collect_same_named_members_from_other_libraries(self):
        from as400_dasd import ObjectInventory
        orphan_file=obj('SOURCE',(0x19,1),library=None)
        orphan=obj('SOURCE.ONE',(0x0D,0x50),20,None)
        assigned=obj('SOURCE.ONE',(0x0D,0x50),30,'QGPL')
        for item in (orphan,assigned):
            item.is_member_cursor=True;item.member_file_name='SOURCE';item.member_name='ONE'
        inv=ObjectInventory([orphan_file,orphan,assigned],{})
        model=Guided5250(inv,member_loader=lambda lib,file,m:[str(m.segment.start_lba)])
        model.run_command('WRKOBJ OBJ(*ORPHAN/SOURCE) OBJTYPE(*FILE)');model.open_row(0,'12')
        self.assertEqual([orphan],[r['object'] for r in model.rows()])
        model.open_row(0);self.assertEqual(['20'],model.detail)
