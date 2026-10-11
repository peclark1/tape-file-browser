"""Synthetic bounded QLDA position windows; original-image bytes never committed."""
import unittest
from types import SimpleNamespace as NS

from as400_local_data import (
    LocalDataExplorer, decode_local_data, LOCAL_DATA_START,
    LOCAL_DATA_END, READ_LIMIT)
from as400_5250 import Guided5250, parse_command
from test_type_capabilities import obj, inventory, Image


def fixture(content=None):
    data=bytearray(4*512)
    data[0x100:0x104]=bytes.fromhex("D3F0055F")
    data[0x15D:0x160]=bytes.fromhex("040400")
    value = b"\x40"*1024 if content is None else content
    assert len(value)==1024
    data[LOCAL_DATA_START:LOCAL_DATA_END]=value
    data[LOCAL_DATA_END]=1
    return data


class LocalDataTests(unittest.TestCase):
    def setup(self, data=None):
        o=obj("QLDA",(0x19,0xCE))
        o.segment.virtual_address=0x100000
        d=fixture() if data is None else data
        o.segment.extents=(NS(start_lba=10,virtual_address=0x100000,
                              pages=len(d)//512),)
        inv=inventory([o]); im=Image([(o,d)]); ex=LocalDataExplorer(im)
        model=Guided5250(inv,lda_loader=ex.rows,
                          capability_loader=lambda item,sample=None:ex.rows(item))
        return o,im,ex,model

    def test_corroborated_layout_bounds_and_full_length(self):
        value=b"\x40"*1000+bytes(range(24))
        data=fixture(value)
        self.assertEqual(value,decode_local_data(data,type_code="19/CE"))
        self.assertEqual(1024,len(decode_local_data(data,type_code="19/CE")))
        for cut in (0,0x100,0x15F,0x560):
            with self.assertRaises(ValueError):decode_local_data(data[:cut],type_code="19/CE")
        for off,bad in ((0x100,0),(0x15D,0),(0x560,0)):
            modified=bytearray(data); modified[off]=bad
            with self.assertRaises(ValueError):decode_local_data(modified,type_code="19/CE")
        with self.assertRaises(ValueError):decode_local_data(data,type_code="19/0A")

    def test_multiple_origins_and_1024_positions_navigation(self):
        value=b"\x40"*992 + b"X"*32
        o,im,ex,model=self.setup(fixture(value))
        self.assertEqual(("DSPLDA",{"LDA":"QLDA"}),parse_command("DSPLDA LDA(QLDA)"))
        model.run_command("DSPLDA LDA(QLDA)")
        self.assertEqual("capabilities",model.screen)
        self.assertEqual("Local data-area bytes",model.rows()[0]["name"])
        self.assertIn("32",model.rows()[0]["lines"][2])
        for _ in range(7):
            i=next(i for i,r in enumerate(model.rows()) if r["name"]=="Next 128")
            model.selected=i; model.open_row(i)
        self.assertIn("897..1024",model.rows()[0]["lines"][3])
        self.assertEqual("993-1024",model.rows()[-1]["name"])
        self.assertIn("58 58",model.rows()[-1]["lines"][1])
        model.back()
        self.assertIn("769..896",model.rows()[0]["lines"][3])
        self.assertEqual(2,model.selected)
        self.assertEqual([10,11,12],im.reads)

    def test_missing_virtual_extent_and_invalid_start_fail_closed(self):
        o,im,ex,_=self.setup()
        o.segment.extents=(NS(start_lba=10,virtual_address=0x100000,pages=2),
                           NS(start_lba=12,virtual_address=0x100600,pages=2))
        with self.assertRaisesRegex(ValueError,"gap/truncation"):
            ex.rows(o)
        o,im,ex,_=self.setup()
        for start in (-1,1,1000,1024,"0",None):
            with self.assertRaises(ValueError):ex.rows(o,start=start)
        other=obj("USER",(0x08,1))
        with self.assertRaises(ValueError):ex.rows(other)
        self.assertEqual([],im.reads)

    def test_readonly_list_duplicate_origin_selection(self):
        one,im,ex,model=self.setup()
        duplicate=obj("QLDA",(0x19,0xCE),40,None)
        model.inventory.objects.append(duplicate)
        model.run_command("DSPLDA LDA(QLDA)")
        self.assertEqual("type_objects",model.screen)
        self.assertEqual(2,len(model.rows()))
        self.assertNotEqual(model.rows()[0]["note"],model.rows()[1]["note"])


if __name__=="__main__":
    unittest.main()
