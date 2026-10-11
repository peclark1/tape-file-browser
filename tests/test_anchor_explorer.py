"""Synthetic anchor graph: ambiguity/cycles never silently resolved."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
from as400_dasd import QAOSSS14AnchorRecord
from as400_anchors import AnchorGraph,AnchorExplorer
from as400_5250 import Guided5250,_draw
from test_type_capabilities import obj,Image,inventory
from test_command_exploration import Screen


def anchor(ordinal,key,parent=bytes(8),name='NODE',fieldkey=None,status=128):
    b=bytearray(193);b[:8]=key;b[16:24]=key if fieldkey is None else fieldkey
    b[131:139]=parent;b[111:131]=name.ljust(20).encode('cp037')
    return QAOSSS14AnchorRecord(ordinal,status,bytes(b))


class AnchorTests(unittest.TestCase):
    def test_twenty_byte_name_and_parent_uses_leading_not_record_key(self):
        a=anchor(1,b'ROOTKEY1',name='LONG-FOLDER-NAME-123',fieldkey=b'OTHERKEY')
        b=anchor(2,b'CHILD001',b'ROOTKEY1','CHILD')
        graph=AnchorGraph([a,b])
        self.assertEqual('LONG-FOLDER-NAME-123',a.short_name)
        self.assertEqual([a],graph.parents(b));self.assertEqual(('root reached',[a.short_name,'CHILD']),graph.path_state(b))
        self.assertEqual({1:[2]},graph.match(b'xxOTHERKEYxx'))

    def test_duplicate_missing_and_cycle_are_explicit(self):
        a=anchor(1,b'ROOTKEY1');duplicate=anchor(2,b'ROOTKEY1');child=anchor(3,b'CHILD001',b'ROOTKEY1')
        self.assertEqual('ambiguous parent',AnchorGraph([a,duplicate,child]).path_state(child)[0])
        self.assertEqual('missing parent',AnchorGraph([child]).path_state(child)[0])
        a=anchor(1,b'ROOTKEY1',b'CHILD001');self.assertEqual('cycle',AnchorGraph([a,child]).path_state(child)[0])
        with self.assertRaises(ValueError):AnchorGraph([a,a])
        self.assertEqual({},AnchorGraph([anchor(1,bytes(8))]).match(bytes(100)))

    def test_folder_source_anchor_children_and_back(self):
        source=obj('QAOSSS14.ONE',(0x0D,0x50));source.is_member_cursor=True;source.member_file_name='QAOSSS14'
        folder=obj('FOLDER',(0x19,0x12),20,'QDOC')
        inv=inventory([source,folder]);data=bytearray(1024);data[300:308]=b'ROOTKEY1'
        im=Image([(folder,data)]);service=AnchorExplorer(im,inv,None)
        parent=anchor(1,b'ROOTKEY1',name='ROOT');child=anchor(2,b'CHILD001',b'ROOTKEY1','CHILD',status=192)
        service._graphs[source.segment.start_lba]=AnchorGraph([parent,child])
        model=Guided5250(inv,capability_loader=lambda o,sample=None:service.object_rows(o),anchor_loader=service.rows)
        model.run_command('WRKFLR FLR(QDOC/FOLDER)');model.open_row(1)
        self.assertEqual('ROOT',model.rows()[1]['name']);model.selected=1;model.open_row(1)
        i=next(i for i,r in enumerate(model.rows()) if r['name']=='CHILD');model.selected=i;model.open_row(i)
        self.assertTrue(any(r['name']=='Parent: ROOT' for r in model.rows()))
        with patch('curses.has_colors',return_value=False):
            for h,w in ((24,80),(16,64)):_draw(Screen(h,w),model)
        model.back();self.assertEqual(i,model.selected)
        roots=service.rows(source,roots=True)
        self.assertEqual(['ROOT'],[r['name'] for r in roots if r['kind']=='anchor_action'])
        self.assertTrue(any(r['request'].get('roots') for r in service.object_rows(folder) if r['kind']=='anchor_action'))


    def test_missing_source_and_schema_fail_without_guessing(self):
        folder=obj('FOLDER',(0x19,0x12));service=AnchorExplorer(Image([]),inventory([folder]),None)
        self.assertEqual('Unavailable',service.object_rows(folder)[1]['name'])
        source=obj('QAOSSS14.ONE',(0x0D,0x50));source.is_member_cursor=True;source.member_file_name='QAOSSS14'
        service=AnchorExplorer(Image([]),inventory([source]),None)
        with self.assertRaisesRegex(ValueError,'all 15'):service.graph(source)
