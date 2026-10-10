import unittest
from types import SimpleNamespace as NS
from as400_messages import decode_message_index,decode_message_record,MessageExplorer
from as400_5250 import Guided5250,run_curses
from test_type_capabilities import obj,inventory,Image
from test_command_exploration import Screen
from unittest.mock import patch


def fixture(page_size=1024,root=0x800):
    data=bytearray(root+page_size)
    data[0x100:0x106]=bytes.fromhex('6000002c0007')
    data[0x106:0x10a]=(1).to_bytes(4,'big')
    data[0x420:0x426]=(0x100000+root).to_bytes(6,'big')
    data[0x42a:0x42e]=page_size.to_bytes(4,'big')
    entry=bytearray(44);entry[:7]='TST0001'.encode('cp037');entry[9:13]=(64).to_bytes(4,'big')
    end=root+14+44
    data[root:root+8]=bytes.fromhex('970008cc')+(page_size-58).to_bytes(2,'big')+end.to_bytes(2,'big')
    data[root+8:root+14]=bytes([43])+ (root+14).to_bytes(2,'big')+bytes.fromhex('600000')
    data[root+14:end]=entry
    return data


def record(tag=1):
    payload='Synthetic message &1.'.encode('cp037')
    return (16+len(payload)).to_bytes(4,'big')+bytes([tag])+'TST0001'.encode('cp037')+b'\0\0'+len(payload).to_bytes(2,'big')+payload


class MessageTests(unittest.TestCase):
    def test_root_relocation_page_sizes_and_count(self):
        for size,root in [(1024,0x800),(2048,0x1000),(2048,0x1800)]:
            entries,warnings=decode_message_index(fixture(size,root),0x100000)
            self.assertEqual(['TST0001'],[e.identifier for e in entries]);self.assertFalse(warnings)
        data=fixture();data[0x109]=2
        self.assertTrue(decode_message_index(data,0x100000)[1])
        for cut in [0,256,0x42d]:
            with self.assertRaises(ValueError):decode_message_index(data[:cut],0x100000)
        data[0x42a:0x42e]=(4096).to_bytes(4,'big')
        with self.assertRaises(ValueError):decode_message_index(data,0x100000)

    def test_record_id_role_length_and_compression(self):
        self.assertTrue(decode_message_record(record(),'TST0001','first')[2])
        self.assertFalse(decode_message_record(record(0x81),'TST0001','first')[2])
        for data,identifier,role in [(record(),'TST0002','first'),(record(),'TST0001','second'),(record()[:-1],'TST0001','first'),(b'','TST0001','first')]:
            with self.assertRaises(ValueError):decode_message_record(data,identifier,role)
        data=bytearray(record());data[15]+=1
        with self.assertRaises(ValueError):decode_message_record(data,'TST0001','first')

    def test_command_select_back_missing_storage_and_keyboard(self):
        o=obj('TESTMSG',(0x0e,3));o.segment.virtual_address=0x100000
        data=fixture();o.segment.pages=len(data)//512;o.segment.extents=(NS(start_lba=10,virtual_address=0x100000,pages=o.segment.pages),);o.segment.owner_key=('owner',)
        inv=inventory([o]);service=MessageExplorer(Image([(o,data)]),inv,NS(segments=[]))
        model=Guided5250(inv,message_loader=service.rows)
        model.run_command('DSPMSGD MSGF(TESTMSG) MSGID(TST*)')
        self.assertEqual(['Summary','TST0001'],[r['name'] for r in model.rows()])
        model.selected=1;model.open_row(1)
        self.assertEqual('Text unavailable',model.rows()[-1]['name'])
        model.back();self.assertEqual(1,model.selected)
        model.run_command('DSPMSGD MSGF(TESTMSG) MSGID(NO*)');self.assertEqual(1,len(model.rows()))
        model.run_command('WRKOBJ OBJ(*ALL/TESTMSG) OBJTYPE(*MSGF)');model.open_row(0)
        self.assertEqual('TST0001',model.rows()[1]['name'])

    def test_duplicate_storage_and_pointer_mismatch_are_withheld(self):
        o=obj('TESTMSG',(0x0e,3));o.segment.owner_key='owner'
        data=fixture();entry=decode_message_index(data,0x100000)[0][0]
        seg=NS(owner_key='owner',header=NS(segment_type=0x280),start_lba=40,virtual_address=0x200000,pages=1,extents=(NS(start_lba=40,virtual_address=0x200000,pages=1),))
        im=Image([]);b=bytearray(512);r=record();b[96:96+len(r)]=r;im.pages[40]=b
        ex=MessageExplorer(im,inventory([o]),NS(segments=[seg]))
        self.assertEqual('Literal text',ex.record_rows(o,entry)[1]['note'])
        im.pages[40][101]=0
        self.assertIn('unavailable',ex.record_rows(o,entry)[1]['name'])
        ex=MessageExplorer(im,inventory([o]),NS(segments=[seg,seg]))
        self.assertEqual('Text unavailable',ex.record_rows(o,entry)[1]['name'])

    def test_curses_enter_back_and_small_terminal(self):
        import curses
        from as400_5250 import _draw
        o=obj('TESTMSG',(0x0e,3));o.segment.virtual_address=0x100000;o.segment.owner_key='owner'
        d=fixture();o.segment.extents=(NS(start_lba=10,virtual_address=0x100000,pages=len(d)//512),)
        inv=inventory([o]);ex=MessageExplorer(Image([(o,d)]),inv,NS(segments=[]))
        for height,width in [(24,80),(16,64)]:
            model=Guided5250(inv,message_loader=ex.rows);model.run_command('DSPMSGD MSGF(TESTMSG)');model.selected=1
            screen=Screen(height,width,keys=[10,10,curses.KEY_F12,curses.KEY_F12,curses.KEY_F3])
            with patch('curses.curs_set',return_value=None):run_curses(screen,model)
            self.assertEqual(1,model.selected);self.assertEqual('TST0001',model.rows()[1]['name'])

    def test_in_use_page_boundary_and_wrong_identifier(self):
        d=fixture();d[0x806:0x808]=(0x810).to_bytes(2,'big')
        entries,warnings=decode_message_index(d,0x100000)
        self.assertFalse(entries);self.assertTrue(warnings)
        d=fixture();d[0x80e]=0
        entries,warnings=decode_message_index(d,0x100000)
        self.assertFalse(entries);self.assertTrue(warnings)
