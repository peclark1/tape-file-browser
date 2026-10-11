"""Synthetic nine-slot DTAQ first-page evidence and navigation tests."""
import unittest
from types import SimpleNamespace as NS
from as400_dtaq import SavedDataQueueExplorer,decode_dtaq_first_page
from as400_5250 import Guided5250,parse_command
from test_type_capabilities import Image,inventory,obj


def fixture(flag=0x40,high=0x2e08):
    data=bytearray(1024)
    data[0x100]=flag
    data[0x140:0x14C]=bytes.fromhex("500000000010000000100000")
    for i in range(9):
        at=0x170+i*16
        prefix=high.to_bytes(3,"big")
        data[at:at+16]=(b"\x6c\x00"+prefix+(0x160+i*16).to_bytes(3,"big")
                         +prefix+(0x7B0-i*96).to_bytes(3,"big")+bytes(2))
    return data


class DTAQTests(unittest.TestCase):
    def setup(self):
        a=obj("QNMACDQ",(0x0a,1),10,"QSYS")
        b=obj("QNMACDQ",(0x0a,1),20,None)
        c=obj("QNMACDQ",(0x0a,1),30,"QSYS")
        inv=inventory([a,b,c])
        exp=SavedDataQueueExplorer(Image([(a,fixture()),(b,fixture(0x50,0x2dd6)),
                                           (c,fixture(0x50,0x25a1))]),inv)
        model=Guided5250(inv,capability_loader=lambda o,sample=None:exp.rows(o),
                         dtaq_loader=exp.rows)
        return a,b,c,exp,model

    def test_bounds_and_supported_variants(self):
        a=decode_dtaq_first_page(fixture(),type_code="0A/01")
        b=decode_dtaq_first_page(fixture(0x50,0x2dd6),type_code="0A/01")
        self.assertEqual(9,len(a.pairs))
        self.assertEqual(0x170,a.pairs[0].offset)
        self.assertEqual(0x1F0,a.pairs[-1].offset)
        self.assertEqual(0x50,b.variant)
        for at in (0x100,0x140,0x170,0x172,0x17E,0x1FE):
            bad=fixture()
            bad[at]=0xFF
            with self.assertRaises(ValueError):
                decode_dtaq_first_page(bad,type_code="0A/01")
        for n in (0,511):
            with self.assertRaises(ValueError):
                decode_dtaq_first_page(fixture()[:n],type_code="0A/01")
        with self.assertRaises(ValueError):
            decode_dtaq_first_page(fixture(),type_code="19/02")

    def test_saved_pairs_and_history_navigation_back(self):
        a,b,c,ex,model=self.setup()
        self.assertEqual(("DSPDTAQ",{"DTAQ":"QNMACDQ","SLOT":"9"}),
                         parse_command("DSPDTAQ DTAQ(QNMACDQ) SLOT(9)"))
        self.assertTrue(model.run_command("DSPDTAQ DTAQ(*ALL/QNMACDQ)"))
        self.assertEqual("type_objects",model.screen)
        index=next(i for i,r in enumerate(model.rows()) if r.get("object") is a)
        model.selected=index;model.open_row(index)
        self.assertEqual("Saved DTAQ first-page raw pairs",model.rows()[0]["name"])
        self.assertEqual([b,c],[r["object"] for r in model.rows() if r.get("object")])
        i=next(i for i,r in enumerate(model.rows()) if r["name"].startswith("Pair 9"))
        model.selected=i;model.open_row(i)
        self.assertEqual("Saved DTAQ first-page pair 9",model.rows()[0]["name"])
        self.assertIn("+0x1F0",model.rows()[0]["lines"][1])
        model.back();self.assertEqual(i,model.selected)
        self.assertTrue(model.run_command("DSPDTAQ DTAQ(*ALL/QNMACDQ) SLOT(9)"))
        j=next(i for i,r in enumerate(model.rows()) if r.get("object") is b)
        model.selected=j;model.open_row(j)
        self.assertEqual("Saved DTAQ first-page pair 9",model.rows()[0]["name"])

    def test_invalid_slot_and_gaps_withheld(self):
        a,b,c,ex,model=self.setup()
        for pos in (0,10,-1):
            with self.assertRaises(ValueError):ex.rows(a,slot=pos)
        for cmd in ("DSPDTAQ DTAQ(QNMACDQ) SLOT(0)",
                    "DSPDTAQ DTAQ(QNMACDQ) SLOT(10)",
                    "DSPDTAQ DTAQ(QNMACDQ) SLOT(x)"):
            self.assertFalse(model.run_command(cmd))
        b.segment.extents=()
        fresh=SavedDataQueueExplorer(ex.image,inventory([a,b,c]))
        rows=fresh.rows(a)
        self.assertIn("withheld: 1",rows[0]["lines"][4])
        self.assertNotIn(b,[r["object"] for r in rows if r.get("object")])


if __name__=="__main__":
    unittest.main()
