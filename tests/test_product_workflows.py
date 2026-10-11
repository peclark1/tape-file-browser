"""Synthetic source-safe CISC PRDLOD/PRDDFN navigation and variant guards."""
import unittest
from types import SimpleNamespace as NS

from as400_products import (LOD_BYTES, DFN_BYTES, SavedProductExplorer,
                            decode_prdlod, decode_prddfn)
from as400_5250 import Guided5250, parse_command
from test_type_capabilities import Image, inventory, obj


def load_fixture(name, token="PLO 0000CV4705738PC15001"):
    assert len(name) <= 10 and len(token)==24
    data = bytearray(1024)
    data[0x100:0x104]=(0x14A).to_bytes(4,"big")
    data[0x104:0x11C]=token.encode("cp037")
    data[0x15C:0x164]="00010200".encode("cp037")
    data[0x164:0x16E]=name.ljust(10).encode("cp037")
    return data


def definition_fixture(*, older=True, broken=False):
    data = bytearray(1024)
    data[0x100:0x104]=(496 if older else 703).to_bytes(4,"big")
    if older:
        data[0x104:0x138]="EXAMPLE COMPUTERS".ljust(52).encode("cp037")
        data[0x138:0x144]="ABC TEST0001".encode("cp037")
    else:
        data[0x104:0x144]=b"\x40"*64
    if broken:data[0x110]=0
    return data


class ProductTests(unittest.TestCase):
    def setup(self):
        load_a=obj("QSZ0050",(0x19,0x1D),10,"QSYS")
        load_b=obj("QSZ0050",(0x19,0x1D),20,None)
        load_c=obj("QPZ0050",(0x19,0x1D),30,"QSYS")
        definition=obj("QSZ0050",(0x19,0x1B),40,"QSYS")
        older=obj("Q5728PC1",(0x19,0x1B),50,"QSYS")
        objects=[load_a,load_b,load_c,definition,older]
        image=Image([(load_a,load_fixture("QSZ0050")),
                     (load_b,load_fixture("QSZ0050")),
                     (load_c,load_fixture("QPZ0050","PLO 0001CV4705738PC15001")),
                     (definition,definition_fixture(older=False)),
                     (older,definition_fixture())])
        inv=inventory(objects)
        exp=SavedProductExplorer(image,inv)
        model=Guided5250(inv,capability_loader=exp.rows)
        return load_a,load_b,load_c,definition,older,exp,model

    def test_mark_load_guard_evidence_and_name_keeping(self):
        raw=load_fixture("QSZ0050")
        item=decode_prdlod(raw,type_code="19/1D",primary_name="QSZ0050")
        self.assertEqual("QSZ0050",item.saved_self_name)
        self.assertEqual(24,len(item.token))
        self.assertEqual("PLO 0000CV4705738PC15001",item.token.decode("cp037"))
        for bad_offset in (0x102,0x15C,0x164):
            corrupt=load_fixture("QSZ0050")
            corrupt[bad_offset]=0
            with self.assertRaises(ValueError):
                decode_prdlod(corrupt,type_code="19/1D",primary_name="QSZ0050")
        for size in (0,0x100,LOD_BYTES-1):
            with self.assertRaises(ValueError):
                decode_prdlod(raw[:size],type_code="19/1D",primary_name="QSZ0050")
        with self.assertRaises(ValueError):
            decode_prdlod(raw,type_code="19/1B",primary_name="QSZ0050")

    def test_b10_text_and_mark_other_length_are_separate(self):
        old=decode_prddfn(definition_fixture(),type_code="19/1B")
        self.assertTrue(old.readable)
        self.assertEqual("EXAMPLE COMPUTERS",old.first_text)
        self.assertEqual("ABC TEST0001",old.second_text)
        new=decode_prddfn(definition_fixture(older=False),type_code="19/1B")
        self.assertFalse(new.readable)
        self.assertEqual(703,new.raw_length)
        for sample in (definition_fixture()[:0x143],
                       definition_fixture()[:DFN_BYTES-1],
                       definition_fixture(broken=True)):
            with self.assertRaises(ValueError):
                decode_prddfn(sample,type_code="19/1B")
        with self.assertRaises(ValueError):
            decode_prddfn(definition_fixture(),type_code="19/1D")

    def test_forward_reverse_duplicate_origins_and_back(self):
        a,b,c,d,old,exp,model=self.setup()
        self.assertEqual(("DSPPRDLOD",{"PRDLOD":"QSZ0050"}),
                         parse_command("DSPPRDLOD PRDLOD(QSZ0050)"))
        self.assertTrue(model.run_command("DSPPRDLOD PRDLOD(*ALL/QSZ0050)"))
        self.assertEqual("type_objects",model.screen)
        item=next(i for i,row in enumerate(model.rows()) if row.get("object") is a)
        model.selected=item;model.open_row(item)
        rows=model.rows()
        self.assertEqual("Saved product-load descriptor",rows[0]["name"])
        self.assertIn("identical saved tokens: 1",rows[1]["lines"][0].lower())
        self.assertIn(b,[row["object"] for row in rows if row.get("object")])
        link=next(i for i,row in enumerate(rows) if row.get("object") is d)
        model.selected=link;model.open_row(link)
        self.assertEqual("Saved product-definition descriptor",model.rows()[0]["name"])
        self.assertEqual([b,a],[row["object"] for row in model.rows() if row.get("object")])
        back=next(i for i,row in enumerate(model.rows()) if row.get("object") is a)
        model.selected=back;model.open_row(back)
        self.assertEqual("Saved product-load descriptor",model.rows()[0]["name"])
        model.back();self.assertEqual(back,model.selected)
        model.back();self.assertEqual(link,model.selected)
        model.back();self.assertEqual(item,model.selected)

    def test_b10_definition_readable_and_invalid_other_type(self):
        a,b,c,d,older,exp,model=self.setup()
        self.assertTrue(model.run_command("DSPPRDDFN PRDDFN(QSYS/Q5728PC1)"))
        self.assertEqual("Saved product-definition descriptor",model.rows()[0]["name"])
        self.assertIn("EXAMPLE COMPUTERS",model.rows()[0]["lines"][3])
        self.assertIn("ABC TEST0001",model.rows()[0]["lines"][4])
        self.assertIn("0 recovered origins",model.rows()[1]["lines"][0])
        for cmd in ("DSPPRDDFN X(123)","DSPPRDLOD O(456)"):
            self.assertFalse(model.run_command(cmd))

    def test_unreadable_saved_load_withheld_but_identity_link_retained(self):
        a,b,c,d,older,exp,model=self.setup()
        b.segment.extents=(NS(start_lba=20,virtual_address=b.segment.virtual_address,pages=1),
                           NS(start_lba=21,virtual_address=b.segment.virtual_address+1024,pages=1))
        fresh=SavedProductExplorer(exp.image,inventory([a,b,c,d,older]))
        rows=fresh.rows(a)
        self.assertIn("withheld: 1",rows[1]["lines"][1].lower())
        # The historical name correlation is independent of the unreadable payload.
        self.assertIn(b,[r["object"] for r in fresh.rows(d) if r.get("object")])
        with self.assertRaises(ValueError):fresh.rows(b)


if __name__=="__main__":
    unittest.main()
