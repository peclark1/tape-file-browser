import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
from as400_indexes import IndexExplorer
from as400_dasd import DataSpaceIndexEntry,InternalAddress
from as400_5250 import Guided5250
from test_type_capabilities import obj,inventory,Image
from test_as400_dasd import make_qddsi_root_fixture


class IndexTests(unittest.TestCase):
    def make(self):
        data,layout=make_qddsi_root_fixture('970008CC07E4101C 0D100E600000 5CD7E4C2D3C9C340404000000001',key_count=1,user_key_length=10,machine_key_length=14)
        data=bytearray(data);data[0x13a:0x140]=(0x1000000a00).to_bytes(6,'big');data[0xa20:0xa26]=(0x1000001000).to_bytes(6,'big')
        o=obj('INDEX',(0x0c,0x90));o.segment.virtual_address=0x1000000000
        o.segment.extents=(NS(start_lba=10,pages=len(data)//512,virtual_address=o.segment.virtual_address),)
        inv=inventory([o]);ex=IndexExplorer(Image([(o,data)]),inv,NS(segments=[]))
        return o,inv,ex,layout

    def test_key_select_back_and_no_implicit_name_link(self):
        o,inv,ex,layout=self.make();rows=ex.rows(o)
        self.assertEqual('Key 1',rows[-1]['name'])
        model=Guided5250(inv,index_loader=ex.rows)
        model.show_evidence(dict(obj=o),ex.rows);model.selected=1;model.open_row(1)
        self.assertEqual('No cursor',model.rows()[-1]['name']);model.back();self.assertEqual(1,model.selected)
        self.assertIn('complete',model.rows()[1]['note'])

    def test_partial_key_remains_partial_and_dual_pointer_gate(self):
        o,inv,ex,layout=self.make()
        member=obj('CURSOR',(0x0d,0x50));member.member_name='MEM'
        ex._members={(o.object_address.key,layout.keys[0].data_space.key):[member]}
        e=DataSpaceIndexEntry(b'',b'',bytes.fromhex('00000007'),0x1010,0,False,b'\xc1\x3f\xff')
        rows=ex.entry_rows(o,e)
        self.assertTrue(any('PARTIAL' in line for line in rows[0]['lines']))
        self.assertEqual(7,rows[1]['request']['start'])
        ex._members={(o.object_address.key,('wrong',)):[member]}
        self.assertFalse(any(r['kind']=='record_action' for r in ex.entry_rows(o,e)))
        e=DataSpaceIndexEntry(b'',b'',bytes.fromhex('01000007'),0x1010,0,False,b'')
        self.assertTrue(any(r['name']=='Record link withheld' for r in ex.entry_rows(o,e)))

    def test_windows_preserve_tree_order(self):
        o,inv,ex,layout=self.make();ex.rows(o);_,result=ex._cache[o.segment.start_lba]
        from dataclasses import replace
        entries=tuple(replace(result.entries[0],database_reference=i.to_bytes(4,'big')) for i in range(70,0,-1))
        ex._cache[o.segment.start_lba]=(layout,replace(result,entries=entries))
        rows=ex.rows(o);self.assertEqual(50,sum(r['name'].startswith('Key ') for r in rows))
        self.assertIn('RRN hint 70',rows[2]['note'])
        nxt=next(r for r in rows if r['name']=='Next');rows=ex.rows(**nxt['request'])
        self.assertEqual(20,sum(r['name'].startswith('Key ') for r in rows))
        self.assertIn('RRN hint 20',rows[2]['note'])
        with self.assertRaises(ValueError):ex.rows(o,start=-1)
