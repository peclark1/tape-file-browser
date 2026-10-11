"""Synthetic CISC EDTD punctuation/sign mask browsing; no archival values."""
import unittest
from types import SimpleNamespace as NS

from as400_edit_descriptions import (
    EditDescriptionExplorer, decode_edit_mask, TEMPLATE_AT, SIGN_LENGTH_AT,
    SIGN_AT, FLAG_AT)
from as400_5250 import Guided5250, parse_command
from test_type_capabilities import obj, inventory, Image


def fixture(digit="8", *, punctuation=",",sign="-",flag="Y",zeros=1):
    data=bytearray(512)
    data[0x100:0x101]=digit.encode("cp037")
    text="   "+punctuation+"   "+punctuation+"   "+punctuation+"   "+punctuation+" "+("0"*zeros)
    text=text.ljust(30)
    assert len(text)==30
    data[TEMPLATE_AT:TEMPLATE_AT+30]=text.encode("cp037")
    data[SIGN_LENGTH_AT]=len(sign)
    data[SIGN_AT:SIGN_AT+len(sign)]=sign.encode("cp037")
    data[FLAG_AT:FLAG_AT+1]=flag.encode("cp037")
    return data


class EditDescriptionTests(unittest.TestCase):
    def setup(self):
        eight=obj("QEDIT8",(0x19,0x08),10,"QSYS")
        six=obj("QEDIT6",(0x19,0x08),20,"QSYS")
        five=obj("QEDIT5",(0x19,0x08),30,None)
        eight.segment.extents=(NS(start_lba=10,virtual_address=eight.segment.virtual_address,pages=1),)
        six.segment.extents=(NS(start_lba=20,virtual_address=six.segment.virtual_address,pages=1),)
        five.segment.extents=(NS(start_lba=30,virtual_address=five.segment.virtual_address,pages=1),)
        inv=inventory([eight,six,five])
        im=Image([(eight,fixture("8")),(six,fixture("6",flag="N")),
                  (five,fixture("5",sign="CR",flag="N"))])
        ex=EditDescriptionExplorer(im,inv)
        model=Guided5250(inv,capability_loader=lambda o,sample=None:ex.rows(o))
        return eight,six,five,im,ex,model

    def test_bounded_observed_header_pattern_sign_and_flag(self):
        for digit,sign,flag in (("5","CR","N"),("6","-","N"),
                                ("8","-","Y"),("9","","Y")):
            src=fixture(digit,sign=sign,flag=flag)
            parsed=decode_edit_mask(src,type_code="19/08",name="QEDIT"+digit)
            self.assertEqual(digit,parsed.digit)
            self.assertEqual(sign,parsed.sign.decode("cp037"))
            self.assertEqual(flag,parsed.flag.decode("cp037"))
            self.assertEqual(30,len(parsed.template))
            self.assertEqual(",",parsed.template.decode("cp037")[3])
        with self.assertRaises(ValueError):
            decode_edit_mask(fixture(),type_code="19/09")

    def test_strict_corruption_rejection_and_virtual_gap(self):
        data=fixture()
        for cut in (0,255,457):
            with self.assertRaises(ValueError):
                decode_edit_mask(data[:cut],type_code="19/08")
        for at,invalid in ((0x100,0),(0x124,0),(SIGN_LENGTH_AT,9),(FLAG_AT,0)):
            d=bytearray(data);d[at]=invalid
            with self.assertRaises(ValueError):
                decode_edit_mask(d,type_code="19/08")
        with self.assertRaises(ValueError):
            decode_edit_mask(fixture("7"),type_code="19/08",name="QEDIT8")
        eight,six,five,im,ex,model=self.setup()
        eight.segment.extents=(NS(start_lba=10,virtual_address=eight.segment.virtual_address+512,pages=1),)
        ex2=EditDescriptionExplorer(im,inventory([eight,six,five]))
        with self.assertRaises(ValueError):
            ex2.rows(eight)

    def test_command_comparison_and_back_preserve_exact_origin(self):
        eight,six,five,im,ex,model=self.setup()
        self.assertEqual(("DSPEDTD",{"EDTD":"QEDIT8"}),
                         parse_command("DSPEDTD EDTD(QEDIT8)"))
        model.run_command("DSPEDTD EDTD(QEDIT8)")
        self.assertEqual("Saved edit pattern evidence",model.rows()[0]["name"])
        self.assertIn("30-byte pattern",model.rows()[0]["lines"][2])
        self.assertEqual("Pattern 1-10",model.rows()[1]["name"])
        self.assertEqual("Other saved edit descriptions",model.rows()[5]["name"])
        index=next(i for i,row in enumerate(model.rows())
                   if row.get("object") is five)
        model.selected=index;model.open_row(index)
        self.assertIn("QEDIT5",model.rows()[0]["lines"][0])
        self.assertIn("'CR'",model.rows()[0]["lines"][4])
        model.back()
        self.assertEqual(index,model.selected)
        self.assertEqual(2,len([r for r in model.rows() if r.get("object")]))
        self.assertIn(10,im.reads)
        self.assertIn(30,im.reads)

    def test_unsupported_status_and_identity_selection(self):
        eight,six,five,im,ex,model=self.setup()
        for data in (fixture("8",flag="X"),fixture("8",sign="\x00")):
            with self.assertRaises(ValueError):
                decode_edit_mask(data,type_code="19/08")
        model.run_command("DSPEDTD EDTD(*ALL/QEDIT*)")
        self.assertEqual("type_objects",model.screen)
        self.assertEqual(3,len(model.rows()))


if __name__=="__main__":
    unittest.main()
