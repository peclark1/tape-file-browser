"""Synthetic SBSD/CLS exact ten-byte name-evidence navigation and safety tests."""
import unittest
from types import SimpleNamespace as NS

from as400_5250 import Guided5250, parse_command
from as400_capabilities import section
from as400_subsystems import SubsystemExplorer
from test_type_capabilities import obj, inventory, Image


def fixture(sbsd):
    data = bytearray(3072)
    data[0x327:0x331] = sbsd.name.ljust(10).encode("cp037")
    data[0x500:0x50A] = "QBATCH".ljust(10).encode("cp037")
    data[0x600:0x60A] = "QWORK".ljust(10).encode("cp037")
    data[0x640:0x64A] = "QCMD".ljust(10).encode("cp037")
    sbsd.segment.virtual_address=0x100000
    sbsd.segment.extents=(NS(start_lba=10,virtual_address=0x100000,pages=6),)
    return data


class SubsystemTests(unittest.TestCase):
    def make(self):
        s=obj("QFNC",(0x19,0x09),10,"QSYS")
        q=obj("QBATCH",(0x0e,0x01),20,"QSYS")
        c=obj("QWORK",(0x19,0x04),30,"QSYS")
        p=obj("QCMD",(0x02,0x01),40,"QSYS")
        decoy=obj("QBATCH",(0x19,0x08),50,"QSYS")
        data=fixture(s)
        inv=inventory([s,q,c,p,decoy])
        ex=SubsystemExplorer(Image([(s,data)]),inv)
        return s,q,c,p,inv,ex

    def test_supported_exact_names_and_explicit_self_exclusion(self):
        s,q,c,p,_,ex=self.make()
        candidates,self_echo,truncated,bytes_read=ex._evidence(s)
        self.assertEqual(3,len(candidates))
        self.assertEqual([(0x500,q),(0x600,c),(0x640,p)],list(candidates))
        self.assertEqual(1,self_echo)
        self.assertFalse(truncated)
        self.assertEqual(3072,bytes_read)
        self.assertNotIn("QFNC",[o.name for _,o in candidates])
        for row in ex.rows(s)[1:]:
            self.assertIn("name evidence only",row["note"])
        bad=obj("NOPE",(0x0e,0xc4))
        with self.assertRaises(ValueError):ex.rows(bad)

    def test_sbsd_to_cls_and_reverse_with_back(self):
        s,q,c,p,inv,ex=self.make()
        self.assertIn(("DSPSBSD",{"SBSD":"QFNC"}),[parse_command("DSPSBSD SBSD(QFNC)")])
        model=Guided5250(inv,subsystem_loader=ex.rows,
                         capability_loader=lambda o,sample=None:
                         ex.rows(o) if o.type_code in ("19/09","19/04")
                         else [section("Other safe identity",[o.name])])
        model.run_command("DSPSBSD SBSD(QFNC)")
        self.assertEqual("capabilities",model.screen)
        i=next(i for i,r in enumerate(model.rows()) if r.get("object") is c)
        model.selected=i;model.open_row(i)
        self.assertEqual("Class reference candidates",model.rows()[0]["name"])
        self.assertEqual(s,model.rows()[1]["object"])
        model.selected=1;model.open_row(1)
        self.assertEqual("Subsystem name candidates",model.rows()[0]["name"])
        model.back();model.back()
        self.assertEqual(i,model.selected)
        model.run_command("DSPCLS CLS(QWORK)")
        self.assertEqual("Class reference candidates",model.rows()[0]["name"])
        self.assertEqual(s,model.rows()[1]["object"])

    def test_missing_and_ambiguous_candidates_and_invalid_page(self):
        s,q,c,p,inv,ex=self.make()
        unrelated=obj("QNONE",(0x19,0x04),70,"QSYS")
        unmatched=SubsystemExplorer(Image([(s,fixture(s))]),inventory([s,unrelated]))
        rows=unmatched.rows(s)
        self.assertEqual("No cross-name evidence",rows[-1]["name"])
        self.assertIn("not proof",rows[-1]["lines"][1])
        clsrows=unmatched.rows(unrelated)
        self.assertEqual("No cross-name evidence",clsrows[-1]["name"])
        for start in (-1,):
            with self.assertRaises(ValueError):ex.rows(s,start=start)
        # A duplicate class origin must retain a separate candidate, never
        # silently select the first same-name class primary.
        dup=obj("QWORK",(0x19,0x04),75,None)
        ex2=SubsystemExplorer(Image([(s,fixture(s))]),inventory([s,c,dup]))
        links=[r for r in ex2.rows(s) if r.get("object") is not None]
        self.assertEqual(2,len(links))
        self.assertTrue(any(r["object"] is c for r in links))
        self.assertTrue(any(r["object"] is dup for r in links))


if __name__=="__main__":
    unittest.main()
