"""Synthetic CISC 19/D7 EPTAB saved u16 word-window and filter tests."""
import unittest
from types import SimpleNamespace as NS

from as400_5250 import Guided5250, parse_command
from as400_eptab import START, END, EPTabExplorer, EPTabWord, decode_eptab_words
from test_type_capabilities import Image, inventory, obj


def eptab_fixture():
    data=bytearray(3*512)
    for i in range(512):
        data[START+i*2:START+i*2+2]=(0x45 if i<384 else 0).to_bytes(2,"big")
    data[START:START+8]=bytes.fromhex("0010000e000f06b0")
    data[START+2*125:START+2*126]=bytes.fromhex("0313")
    data[START+2*250:START+2*251]=bytes.fromhex("0313")
    return data


class EPTabTests(unittest.TestCase):
    def make(self):
        table=obj("QDMEPTB",(0x19,0xD7),10,"QSYS")
        table.segment.virtual_address=0x100000
        raw=eptab_fixture()
        table.segment.extents=(NS(start_lba=10,virtual_address=0x100000,pages=3),)
        inv=inventory([table])
        image=Image([(table,raw)])
        service=EPTabExplorer(image)
        model=Guided5250(inv,eptab_loader=service.rows,
                          capability_loader=lambda o,sample=None:service.rows(o))
        return table,image,service,model

    def test_exact_corroborated_control_words_and_all_512_positions(self):
        words=decode_eptab_words(eptab_fixture(),type_code="19/D7")
        self.assertEqual(512,len(words))
        self.assertEqual([0x0010,0x000e,0x000f,0x06b0],[w.value for w in words[:4]])
        self.assertEqual([0,1,2,511],[words[i].index for i in (0,1,2,511)])
        self.assertEqual(START,words[0].offset)
        self.assertEqual(END-2,words[-1].offset)
        self.assertEqual("0045",words[5].hex)
        self.assertEqual(0x0313,words[125].value)
        self.assertEqual(0,words[-1].value)

    def test_hex_filter_index_origin_and_back(self):
        obj_,image,svc,model=self.make()
        self.assertEqual(("DSPEPTAB",{"EPTAB":"QDMEPTB","WORD":"0313"}),
                         parse_command("DSPEPTAB EPTAB(QDMEPTB) WORD(0313)"))
        model.run_command("DSPEPTAB EPTAB(QDMEPTB) WORD(0313)")
        self.assertEqual("Saved EPTAB 16-bit words",model.rows()[0]["name"])
        self.assertEqual(["Word 125: 0313","Word 250: 0313"],
                         [r["name"] for r in model.rows()[1:]])
        model.selected=2;model.open_row(2)
        self.assertEqual("Saved EPTAB word",model.rows()[0]["name"])
        self.assertIn("index: 250",model.rows()[0]["lines"][1])
        self.assertIn("03 13",model.rows()[0]["lines"][2])
        model.back()
        self.assertEqual(2,model.selected)
        self.assertEqual([10,11,12],image.reads)
        model.run_command("DSPEPTAB EPTAB(QDMEPTB) WORD(FFFF)")
        self.assertEqual("No matching saved word",model.rows()[-1]["name"])

    def test_paged_512_words_retains_selected_window(self):
        obj_,image,svc,model=self.make()
        model.run_command("DSPEPTAB EPTAB(QDMEPTB)")
        self.assertEqual(50,len([r for r in model.rows() if r["name"].startswith("Word ")]))
        for page in range(10):
            next_i=next(i for i,row in enumerate(model.rows()) if row["name"]=="Next")
            model.selected=next_i
            model.open_row(next_i)
        self.assertEqual("Word 500: 0000",model.rows()[2]["name"])
        self.assertEqual("Word 511: 0000",model.rows()[-1]["name"])
        model.back()
        self.assertEqual(next_i,model.selected)
        self.assertEqual("Word 450: 0000",next(r["name"] for r in model.rows() if r["name"].startswith("Word ")))

    def test_malformed_gapped_and_wrong_type_data_fail_closed(self):
        raw=eptab_fixture()
        for cut in (0,0x100,0x300,END-1):
            with self.assertRaises(ValueError):
                decode_eptab_words(raw[:cut],type_code="19/D7")
        altered=bytearray(raw);altered[START]=0xFF
        with self.assertRaises(ValueError):
            decode_eptab_words(altered,type_code="19/D7")
        with self.assertRaises(ValueError):
            decode_eptab_words(raw,type_code="19/37")
        table,image,svc,model=self.make()
        table.segment.extents=(NS(start_lba=10,virtual_address=0x100000,pages=1),
                               NS(start_lba=11,virtual_address=0x100400,pages=2))
        with self.assertRaises(ValueError):
            EPTabExplorer(image).rows(table)
        table,image,svc,model=self.make()
        for bad in ({"start":-1},{"start":"0"},{"word":"F"},{"word":"CABC0"},{"word":"GHJI"},
                    {"entry":EPTabWord(511,END-2,0x45)}):
            with self.assertRaises(ValueError):
                svc.rows(table,**bad)
        with self.assertRaises(ValueError):
            svc.rows(obj("OTHER",(0x19,0x37)))

    def test_complete_u16_window_is_read_only_and_preserves_origin(self):
        table,image,svc,model=self.make()
        rows=svc.rows(table)
        self.assertIn("zero-based",rows[0]["lines"][3])
        before=len(image.reads)
        another=svc.rows(table,word="0045")
        self.assertEqual(before,len(image.reads))
        self.assertTrue(any(r["name"].endswith("0045") for r in another))
        self.assertEqual(bytes.fromhex("0010000e000f06b0"),
                         bytes(eptab_fixture()[START:START+8]))


if __name__=="__main__":
    unittest.main()
