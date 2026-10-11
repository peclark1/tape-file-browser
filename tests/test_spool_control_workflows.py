"""Synthetic saved SPLCB slot/link tests; no real spool records committed."""
import unittest
from types import SimpleNamespace as NS

from as400_spool_controls import (
    SpoolControlExplorer, decode_spool_slots, strict_name)
from as400_5250 import Guided5250, parse_command
from as400_capabilities import section
from test_type_capabilities import obj, inventory, Image


def fixture(name="QCTL", library="QSYS", tag="SP2619"):
    data=bytearray(512)
    data[0x1AE:0x1B8]=(name.ljust(10).encode("cp037")
                           if name is not None else bytes(10))
    data[0x1B8:0x1C2]=(library.ljust(10).encode("cp037")
                           if library is not None else bytes(10))
    data[0x1C5:0x1CB]=tag.encode("cp037")
    return data


class SpoolControlTests(unittest.TestCase):
    def model(self, data=None):
        source=obj("QSPSCB",(0x19,0xC2),10,None)
        source.segment.virtual_address=0x100000
        source.segment.extents=(NS(start_lba=10,virtual_address=0x100000,pages=1),)
        a=obj("QCTL",(0x19,0x09),20,"QSYS")
        b=obj("QCTL",(0x19,0x09),30,"QGPL")
        c=obj("QCTL",(0x19,0x04),40,"QSYS")
        inv=inventory([source,a,b,c]);im=Image([(source,data or fixture())])
        ex=SpoolControlExplorer(im,inv)
        m=Guided5250(inv,capability_loader=lambda o,sample=None:
                     ex.rows(o) if o.type_code=="19/C2"
                     else [section("Target identity",[o.name])])
        return source,a,b,c,im,ex,m

    def test_fixed_width_candidates_strict_padding_and_opaque_token(self):
        self.assertEqual(("QCTL","QSYS","SP2619"),
                         decode_spool_slots(fixture(),type_code="19/C2"))
        self.assertEqual((None,None,None),
                         decode_spool_slots(fixture(None,None,"ABCDEF"),type_code="19/C2"))
        self.assertIsNone(strict_name(b"\x00"*10))
        self.assertIsNone(strict_name(bytes.fromhex("D8C3E3D3")+b"\x00"*6))
        self.assertIsNone(strict_name(b"\x40"*9+b"\xc1"))
        for data in (b"",fixture()[:0x1ca]):
            with self.assertRaises(ValueError):
                decode_spool_slots(data,type_code="19/C2")
        with self.assertRaises(ValueError):
            decode_spool_slots(fixture(),type_code="19/CE")

    def test_exact_qualified_links_duplicates_and_back(self):
        source,a,b,c,im,ex,m=self.model()
        rows=ex.rows(source)
        self.assertEqual("Saved spool-control evidence",rows[0]["name"])
        self.assertEqual([c,a],[r["object"] for r in rows if r.get("object")])
        self.assertNotIn(b,[r["object"] for r in rows if r.get("object")])
        self.assertIn("SP2619",rows[0]["lines"][3])
        self.assertEqual(("DSPSPLCB",{"SPLCB":"QSPSCB"}),
                         parse_command("DSPSPLCB SPLCB(QSPSCB)"))
        m.run_command("DSPSPLCB SPLCB(QSPSCB)")
        i=next(i for i,r in enumerate(m.rows()) if r.get("object") is a)
        m.selected=i;m.open_row(i)
        self.assertEqual("Target identity",m.rows()[0]["name"])
        m.back()
        self.assertEqual(i,m.selected)
        self.assertEqual([10],im.reads)

    def test_missing_and_invalid_slot_displays_no_invented_match(self):
        source,a,b,c,im,ex,m=self.model(fixture(None,None,"SP1000"))
        rows=ex.rows(source)
        self.assertEqual("No qualified-name pair",rows[-1]["name"])
        self.assertFalse(any(r.get("object") for r in rows))
        source,a,b,c,im,ex,m=self.model(fixture("QCTL",None,"SP9999"))
        self.assertEqual("Incomplete name pair",ex.rows(source)[-1]["name"])
        source,a,b,c,im,ex,m=self.model(fixture("NOJOB","QSYS","SP0001"))
        self.assertEqual("No matching primary",ex.rows(source)[-1]["name"])
        with self.assertRaises(ValueError):ex.rows(a)


if __name__=="__main__":
    unittest.main()
