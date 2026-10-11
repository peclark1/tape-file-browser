import unittest
from as400_menus import menu_references,MenuExplorer
from as400_5250 import Guided5250
from test_type_capabilities import obj,inventory,Image

class MenuTests(unittest.TestCase):
    def test_variants_truncation_and_invalid_names(self):
        b=bytearray(512);b[256]=0xd7;b[0x130:0x144]=('PROGRAM   '+'QSYS      ').encode('cp037')
        self.assertEqual(('Program','02/01',0x130,'PROGRAM','QSYS'),menu_references(b)[1][0])
        b[256]=0xe4;self.assertEqual((),menu_references(b)[1])
        b[256]=0xd7
        for data in [b[:256],b[:0x140]]:
            with self.assertRaises(ValueError):menu_references(data)
        b[0x130]=0
        with self.assertRaises(ValueError):menu_references(b)

    def test_file_message_candidates_and_back(self):
        menu=obj('MENU',(0x19,0x16));f=obj('DISPLAY',(0x19,1),20);msg=obj('MESSAGES',(0x0e,3),30)
        duplicate=obj('MESSAGES',(0x0e,3),40,'OTHER');decoy=obj('MESSAGES',(2,1),50)
        b=bytearray(1024);b[256]=0xc6
        b[0x130:0x158]=('DISPLAY   '+'QGPL      '+'MESSAGES  '+'*LIBL     ').encode('cp037')
        inv=inventory([menu,f,msg,duplicate,decoy]);ex=MenuExplorer(Image([(menu,b)]),inv)
        rows=ex.rows(menu);self.assertEqual([f,msg,duplicate],[r['object'] for r in rows if r.get('object')])
        model=Guided5250(inv,capability_loader=lambda o,sample=None:ex.rows(o),message_loader=lambda **kw:[])
        model.run_command('DSPMNU MENU(MENU)');model.selected=4;model.open_row(4)
        self.assertEqual('MESSAGES',model.file);model.back();self.assertEqual(4,model.selected)
