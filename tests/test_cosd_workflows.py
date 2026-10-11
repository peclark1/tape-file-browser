"""Synthetic first/second virtual-page COSD profile navigation and comparisons."""
import unittest
from types import SimpleNamespace as NS
from as400_cosd import (COUNT, END, PREFIXES, START, STRIDE,
                        SavedCOSDExplorer, decode_cosd)
from as400_5250 import Guided5250, parse_command
from test_type_capabilities import Image, inventory, obj


def fixture(name="#BATCH",variant=1,flag=0,changed=None):
    data=bytearray(1024)
    data[0x100:0x104]=variant.to_bytes(4,"big")
    data[0x130:0x138]=name.ljust(8).encode("cp037")
    data[0x138:0x13A]=len(name).to_bytes(2,"big")
    data[0x13A:0x13C]=(8).to_bytes(2,"big")
    data[0x13C:0x140]=(flag*0x1000000).to_bytes(4,"big")
    for i,prefix in enumerate(PREFIXES):
        at=START+STRIDE*i
        data[at:at+2]=bytes.fromhex(prefix)
        data[at+2]=0x44 if "BATCH" in name else 0x38
        data[at+11]=0x20 if "SC" in name else 1
        data[at+32]=0xC0
        data[at+33]=0x71 if "INTER" in name else 0xFF
        data[at+34:at+38]=bytes.fromhex("FFFFFFFF")
        data[at+46]=i*0x20+0x1F
    for pos,value in (changed or {}).items():
        if not 0<=pos<COUNT*STRIDE:
            raise ValueError("Fixture change must be inside COSD saved slots")
        data[START+pos]=value
    return data


class COSDTests(unittest.TestCase):
    def setup(self):
        a=obj("#BATCH",(0x14,1),10,"QSYS")
        b=obj("#BATCH",(0x14,1),20,None)
        c=obj("#INTER",(0x14,1),30,"QSYS")
        d=obj("#BATCHSC",(0x14,1),40,"QSYS")
        inv=inventory([a,b,c,d])
        service=SavedCOSDExplorer(Image([(a,fixture()),(b,fixture(variant=0xDF)),
            (c,fixture("#INTER",flag=2,changed={127:0xAA,250:0xBB})),
            (d,fixture("#BATCHSC",changed={300:0x80}))]),inv)
        model=Guided5250(inv,cosd_loader=service.rows,
                         capability_loader=lambda obj,sample=None:service.rows(obj))
        return a,b,c,d,service,model

    def test_cross_release_exact_profile_and_two_page_offset(self):
        a=decode_cosd(fixture(),type_code="14/01",primary_name="#BATCH")
        b=decode_cosd(fixture(variant=0xDF),type_code="14/01",primary_name="#BATCH")
        self.assertEqual(1,a.variant)
        self.assertEqual(0xDF,b.variant)
        self.assertEqual(a.entire,b.entire)
        self.assertEqual(8,len(a.slots))
        self.assertEqual(384,len(a.entire))
        self.assertEqual(0x150,START)
        self.assertEqual(0x2D0,END)
        self.assertEqual(bytes.fromhex("1E05"),a.slots[0][:2])
        self.assertEqual(bytes.fromhex("F0A0"),a.slots[-1][:2])
        self.assertEqual("02000000",decode_cosd(fixture("#INTER",flag=2),
                          type_code="14/01",primary_name="#INTER").flag.hex())

    def test_strict_header_slot_virtual_gap_guards(self):
        for at in (0x100,0x104,0x130,0x138,0x13A,0x13C,0x150,0x180,0x210,0x2A0):
            bad=fixture()
            bad[at]=0xFF
            with self.assertRaises(ValueError):
                decode_cosd(bad,type_code="14/01",primary_name="#BATCH")
        for size in (0,511,END-1):
            with self.assertRaises(ValueError):
                decode_cosd(fixture()[:size],type_code="14/01",primary_name="#BATCH")
        with self.assertRaises(ValueError):
            decode_cosd(fixture(),type_code="14/02",primary_name="#BATCH")
        with self.assertRaises(ValueError):
            decode_cosd(fixture(),type_code="14/01",primary_name="#INTER")

    def test_command_compare_zero_and_differing_slots_with_back(self):
        a,b,c,d,service,model=self.setup()
        self.assertEqual(("DSPCOSD",{"COSD":"#INTER","SLOT":"8"}),
                         parse_command("DSPCOSD COSD(#INTER) SLOT(8)"))
        self.assertTrue(model.run_command("DSPCOSD COSD(*ALL/#*)"))
        self.assertEqual("type_objects",model.screen)
        row=next(i for i,x in enumerate(model.rows()) if x.get("object") is a)
        model.selected=row;model.open_row(row)
        self.assertEqual("Saved COSD profile and eight saved slots",model.rows()[0]["name"])
        # Duplicate historical same-name profile has identical body even with distinct +0x100.
        comp=next(i for i,r in enumerate(model.rows()) if r["name"].startswith("Compare #BATCH @"))
        model.selected=comp;model.open_row(comp)
        self.assertIn("0/384",model.rows()[0]["lines"][2])
        first=next(i for i,x in enumerate(model.rows()) if x["name"].startswith("Compare slot 1"))
        model.selected=first;model.open_row(first)
        self.assertIn("0 of 48 raw bytes differ",model.rows()[0]["lines"][2])
        model.back();self.assertEqual(first,model.selected)
        model.back();self.assertEqual(comp,model.selected)
        changed=next(i for i,x in enumerate(model.rows()) if x["name"].startswith("Compare #INTER"))
        model.selected=changed;model.open_row(changed)
        self.assertIn("differ",model.rows()[0]["lines"][2])
        self.assertTrue(any("/48" in x.get("note","") and "0/48" not in x.get("note","") for x in model.rows()))
        model.back();self.assertEqual(changed,model.selected)
        self.assertTrue(model.run_command("DSPCOSD COSD(QSYS/#INTER) SLOT(8)"))
        self.assertEqual("Saved COSD slot 8 (of 8)",model.rows()[0]["name"])
        self.assertIn("+0x2A0",model.rows()[0]["lines"][1])

    def test_unsupported_slot_peer_and_virtual_gap(self):
        a,b,c,d,ex,model=self.setup()
        for slot in (0,9,-1):
            with self.assertRaises(ValueError):ex.rows(a,slot=slot)
        for command in ("DSPCOSD COSD(#INTER) SLOT(0)","DSPCOSD COSD(#INTER) SLOT(9)",
                        "DSPCOSD COSD(#INTER) SLOT(ZZ)"):
            self.assertFalse(model.run_command(command))
        b.segment.extents=(NS(start_lba=20,virtual_address=b.segment.virtual_address,pages=1),
                           NS(start_lba=21,virtual_address=b.segment.virtual_address+1024,pages=1))
        fresh=SavedCOSDExplorer(ex.image,inventory([a,b,c,d]))
        view=fresh.rows(a)
        self.assertIn("withheld: 1",view[0]["lines"][4])
        self.assertNotIn(b,[row["object"] for row in view if row.get("object")])
        with self.assertRaises(ValueError):
            fresh.rows(b)


if __name__=="__main__":
    unittest.main()
