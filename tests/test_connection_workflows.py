import unittest
from types import SimpleNamespace as NS
from as400_connections import ConnectionExplorer
from as400_5250 import Guided5250,_draw,run_curses
from test_type_capabilities import obj,inventory,Image
from test_command_exploration import Screen
from unittest.mock import patch
import curses

class ConnectionTests(unittest.TestCase):
    def test_full_address_reverse_duplicates_and_decoys(self):
        dev=obj('DEV',(0x10,1));ctl=obj('CTL',(0x12,1),20);line=obj('LINE',(0x11,1),30)
        duplicate=obj('OTHER',(0x12,1),40);duplicate.object_address=ctl.object_address
        profile=obj('SECRET',(8,1),50)
        d=bytearray(1024);d[0x128:0x130]=ctl.object_address.to_bytes()
        c=bytearray(1024);c[0x200:0x208]=line.object_address.to_bytes()
        im=Image([(dev,d),(ctl,c),(duplicate,bytes(1024)),(line,bytes(1024))])
        inv=inventory([dev,ctl,line,duplicate,profile]);ex=ConnectionExplorer(im,inv)
        rows=ex.rows(dev);self.assertEqual([ctl,duplicate],[r['object'] for r in rows if r.get('object')])
        rows=ex.rows(ctl);self.assertEqual([dev,line],[r['object'] for r in rows if r.get('object')])
        self.assertNotIn(50,im.reads)
        model=Guided5250(inv,capability_loader=lambda o,sample=None:ex.rows(o))
        model.run_command('DSPDEVD DEVD(DEV)');model.selected=1;model.open_row(1)
        self.assertEqual('CTL',model.file);model.back();self.assertEqual(1,model.selected)
        model.run_command('DSPLIND LIND(LINE)');self.assertEqual('LINE',model.file)
        for dims in [(24,80),(16,64)]:_draw(Screen(*dims),model)
        # No matching address survives a one-bit corruption; common EPA is excluded.
        d[0x12f]^=1;d[0x80:0x88]=ctl.object_address.to_bytes()
        ex=ConnectionExplorer(Image([(dev,d),(ctl,c),(duplicate,bytes(1024)),(line,bytes(1024))]),inv)
        self.assertFalse(any(r.get('object') for r in ex.rows(dev)))
        with self.assertRaises(ValueError):ex.rows(profile)
