import unittest
from types import SimpleNamespace as NS
from as400_directory import decode_directory_index,DirectoryExplorer
from as400_5250 import Guided5250
from test_message_workflows import fixture
from test_type_capabilities import obj,inventory,Image

class DirectoryTests(unittest.TestCase):
    def make(self):
        d=fixture();d[0x100:0x106]=bytes.fromhex('60000018000c');d[0x426:0x42a]=(1).to_bytes(4,'big')
        raw=b'\x19\x01'+'FILE'.ljust(10).encode('cp037')+(1).to_bytes(4,'big')+(2).to_bytes(4,'big')+bytes(4)
        d[0x808]=23;d[0x80e:0x826]=raw
        return d

    def test_slot_corroboration_missing_primary_and_mismatch(self):
        index=obj('LIB',(0x0e,0x90));repo=obj('LIB',(0x19,0x52),30)
        d=self.make();index.segment.virtual_address=0x100000
        index.segment.extents=(NS(start_lba=10,virtual_address=0x100000,pages=len(d)//512),)
        r=bytearray(1536);r[1028:1040]=b'\x19\x01'+'FILE'.ljust(10).encode('cp037')
        repo.segment.pages=3;repo.segment.extents=(NS(start_lba=30,virtual_address=repo.segment.virtual_address,pages=3),)
        inv=inventory([index,repo]);im=Image([(index,d),(repo,r)]);ex=DirectoryExplorer(im,inv)
        entries,warnings=decode_directory_index(d,0x100000);self.assertFalse(warnings)
        self.assertEqual(2,entries[0].ordinal)
        rows=ex.entry_rows(index,entries[0]);self.assertEqual('Repository match',rows[1]['name']);self.assertIn('0 recovered',rows[-1]['lines'][0])
        im.pages[32]=bytes(512);self.assertEqual('Repository mismatch',ex.entry_rows(index,entries[0])[1]['name'])
        model=Guided5250(inv,directory_loader=ex.rows)
        model.run_command('WRKOBJ OBJ(*ALL/LIB) OBJTYPE(*OIRS)');model.open_row(0);model.selected=1;model.open_row(1)
        self.assertEqual('FILE',model.rows()[1]['name']);model.back();self.assertEqual(1,model.selected)
        with self.assertRaises(ValueError):decode_directory_index(d[:0x400],0x100000)
        bad=bytearray(d);bad[0x810]=0
        self.assertEqual((),decode_directory_index(bad,0x100000)[0])
