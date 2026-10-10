import unittest
from types import SimpleNamespace as NS
from as400_reference_codes import ReferenceCodeEntry, decode_reference_index, validate_reference_record, ReferenceCodeExplorer
from as400_5250 import Guided5250
from test_message_workflows import fixture
from test_type_capabilities import obj, inventory, Image


def index_fixture():
    data = fixture()
    data[0x100:0x106] = bytes.fromhex('6000000c0008')
    data[0x808] = 11
    data[0x80e:0x81a] = bytes.fromhex('e21234000000000000000040')
    return data


class ReferenceCodeTests(unittest.TestCase):
    def test_index_bounds_count_and_corruption(self):
        data = index_fixture()
        entries,warnings = decode_reference_index(data,0x100000)
        self.assertFalse(warnings);self.assertEqual(64,entries[0].offset)
        for cut in (0,256,0x42d):
            with self.assertRaises(ValueError):decode_reference_index(data[:cut],0x100000)
        data[0x109] = 2
        self.assertTrue(decode_reference_index(data,0x100000)[1])
        data[0x806:0x808] = (0x810).to_bytes(2,'big')
        entries,warnings = decode_reference_index(data,0x100000)
        self.assertFalse(entries);self.assertTrue(warnings)
        data[0x42a:0x42e] = (4096).to_bytes(4,'big')
        with self.assertRaises(ValueError):decode_reference_index(data,0x100000)

    def test_four_repeated_key_layouts_length_and_mismatch(self):
        for key,identity in [('c4c1c2c3c4000000','c1c2c3c4'),('c6c1c2c340000000','c1c2c340'),('e212340000000000','1234'),('d701f1f2f3f40000','d7f1f2f3f401')]:
            e=ReferenceCodeEntry(bytes.fromhex(key),0,0)
            record=(16).to_bytes(2,'big')+bytes.fromhex(identity)+bytes(14-len(bytes.fromhex(identity)))
            self.assertEqual(record,validate_reference_record(e,record))
            for bad in (record[:-1],record[:2]+b'\xff'+record[3:],b''):
                with self.assertRaises(ValueError):validate_reference_record(e,bad)
        e=ReferenceCodeEntry(b'\0'*8,0,0)
        with self.assertRaises(ValueError):validate_reference_record(e,b'\0\x08'+bytes(6))

    def test_command_record_window_back_and_ambiguous_storage(self):
        o=obj('RCT',(0x0e,8));o.segment.virtual_address=0x100000;o.segment.owner_key='owner'
        data=index_fixture();o.segment.extents=(NS(start_lba=10,virtual_address=0x100000,pages=len(data)//512),)
        storage=NS(owner_key='owner',header=NS(segment_type=0x280),start_lba=40,virtual_address=0x200000,pages=1,extents=(NS(start_lba=40,virtual_address=0x200000,pages=1),))
        image=Image([(o,data)]);record=(300).to_bytes(2,'big')+bytes.fromhex('1234')+bytes(296)
        image.pages[40]=bytes(96)+record+bytes(116)
        inv=inventory([o]);ex=ReferenceCodeExplorer(image,inv,NS(segments=[storage]))
        model=Guided5250(inv,reference_loader=ex.rows)
        model.run_command('DSPRCT RCT(RCT) KEYHEX(E2)');self.assertEqual(2,len(model.rows()))
        model.selected=1;model.open_row(1);self.assertEqual('Corroborated record',model.rows()[0]['name'])
        model.open_row(1);self.assertIn('256..300',model.rows()[0]['lines'][-1]);model.back();model.back();self.assertEqual(1,model.selected)
        model.run_command('DSPRCT RCT(RCT) KEYHEX(FF)');self.assertEqual(1,len(model.rows()))
        for storage_list in ([],[storage,storage]):
            ex=ReferenceCodeExplorer(image,inv,NS(segments=storage_list))
            with self.assertRaises(ValueError):ex.record(o,decode_reference_index(data,0x100000)[0][0])
        for kwargs in ({'start':-1},{'keyhex':'Z'},{'keyhex':'00'*9}):
            with self.assertRaises(ValueError):ex.rows(o,**kwargs)
