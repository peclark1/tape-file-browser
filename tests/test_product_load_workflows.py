"""Invented PRDLOD product-code / PRDDFN identity correlations and TUI Back."""
import unittest
from types import SimpleNamespace as NS

from as400_5250 import Guided5250, parse_command
from as400_product_loads import ProductLoadExplorer, decode_product_load
from test_type_capabilities import Image, obj, inventory


def sample(name="QHI0050", product="5738PC1", release="5001",
           fmt="CV47", other="QIWS"):
    data=bytearray(2*512)
    data[0x100:0x108]=bytes.fromhex("0000014a")+"PLO ".encode("cp037")
    data[0x10C:0x110]=fmt.encode("cp037")
    data[0x111:0x118]=product.encode("cp037")
    data[0x118:0x11C]=release.encode("cp037")
    data[0x164:0x16E]=name.ljust(10).encode("cp037")
    data[0x174:0x17E]=other.ljust(10).encode("cp037") if other else bytes(10)
    return data


class ProductLoadTests(unittest.TestCase):
    def model(self):
        source=obj("QHI0050",(0x19,0x1D),10,"QSYS")
        sibling=obj("QHI0250",(0x19,0x1D),30,"QSYS")
        other=obj("QMG0450",(0x19,0x1D),50,None)
        bad=obj("QBAD0050",(0x19,0x1D),70,None)
        definition=obj("Q5738PC1",(0x19,0x1B),90,"QSYS")
        dup=obj("Q5738PC1",(0x19,0x1B),110,None)
        missing=obj("Q5738SS1",(0x19,0x1B),120,"QSYS")
        objs=[source,sibling,other,bad,definition,dup,missing]
        data={10:sample(),30:sample("QHI0250",other=""),
              50:sample("QMG0450",product="5738SS1",release="2924"),
              70:sample("QBAD0050",fmt="CV48")}
        for o in objs:
            o.segment.virtual_address=0x100000
            o.segment.extents=(NS(start_lba=o.segment.start_lba,
                                  virtual_address=0x100000,pages=2),)
        image=Image([(o,data[o.segment.start_lba]) for o in objs[:4]])
        inv=inventory(objs)
        explorer=ProductLoadExplorer(image,inv)
        model=Guided5250(inv,capability_loader=lambda o,sample=None:explorer.rows(o))
        return source,sibling,other,bad,definition,dup,missing,image,explorer,model

    def test_verified_padded_loader_name_product_code_and_variant(self):
        for product,release in (("5738PC1","5001"),("5738SS1","2924"),
                                ("5738RG1","6050"),("5738999","5001")):
            hdr=decode_product_load(sample(product=product,release=release),
                                    type_code="19/1D",name="QHI0050")
            self.assertEqual(product,hdr.code)
            self.assertEqual(release,hdr.release_token)
            self.assertEqual("QHI0050",hdr.saved_loader_name)
            self.assertEqual("QIWS",hdr.saved_name_candidate)
        with self.assertRaises(ValueError):
            decode_product_load(sample(),type_code="19/1B",name="QHI0050")

    def test_independently_correlated_target_and_duplicate_origins(self):
        src,sibling,other,bad,definition,dup,missing,img,service,model=self.model()
        self.assertEqual(("DSPPRDLOD",{"PRDLOD":"QHI0050"}),
                         parse_command("DSPPRDLOD PRDLOD(QHI0050)"))
        model.run_command("DSPPRDLOD PRDLOD(QHI0050)")
        self.assertEqual("Saved product-load header",model.rows()[0]["name"])
        self.assertIn("5738PC1",model.rows()[0]["lines"][2])
        self.assertEqual([dup,definition,sibling],
                         [r["object"] for r in model.rows() if r.get("object")])
        self.assertEqual("Matching product-definition names",model.rows()[1]["name"])
        i=next(i for i,r in enumerate(model.rows()) if r.get("object") is definition)
        model.selected=i
        model.open_row(i)
        self.assertEqual("Product-definition identity and saved loader candidates",
                         model.rows()[0]["name"])
        loaders=[r["object"] for r in model.rows() if r.get("object")]
        self.assertEqual([src,sibling],loaders)
        j=next(j for j,r in enumerate(model.rows()) if r.get("object") is sibling)
        model.selected=j;model.open_row(j)
        self.assertEqual("Saved product-load header",model.rows()[0]["name"])
        model.back();self.assertEqual(j,model.selected)
        model.back();self.assertEqual(i,model.selected)

    def test_reverse_product_definition_origin_and_absent_loader_cases(self):
        src,sibling,other,bad,definition,dup,missing,img,service,model=self.model()
        self.assertEqual(("DSPPRDDFN",{"PRDDFN":"Q5738PC1"}),
                         parse_command("DSPPRDDFN PRDDFN(Q5738PC1)"))
        model.run_command("DSPPRDDFN PRDDFN(Q5738PC1)")
        self.assertEqual("type_objects",model.screen) # two exact-name primaries
        self.assertEqual(2,len(model.rows()))
        model.selected=1;model.open_row(1)
        self.assertEqual("Product-definition identity and saved loader candidates",
                         model.rows()[0]["name"])
        no=service.rows(missing)
        self.assertEqual([other],[r["object"] for r in no if r.get("object")])
        unrelated=obj("UNRELATED",(0x19,0x1B),400,None)
        self.assertFalse(any(r.get("object") for r in service.rows(unrelated)))

    def test_truncation_corrupt_prefix_code_own_name_and_release_withheld(self):
        source=sample()
        for cut in (0,0x100,0x111,0x17D):
            with self.assertRaises(ValueError):
                decode_product_load(source[:cut],type_code="19/1D",name="QHI0050")
        for at,new in ((0x100,0xFF),(0x104,0),(0x10D,0xFF),
                       (0x111,0xFF),(0x118,0),(0x164,0),
                       (0x169,0)):
            data=sample();data[at]=new
            with self.assertRaises(ValueError):
                decode_product_load(data,type_code="19/1D",name="QHI0050")
        with self.assertRaises(ValueError):
            decode_product_load(sample(),type_code="19/1D",name="QHI0250")
        src,sibling,other,bad,definition,dup,missing,img,service,model=self.model()
        self.assertEqual(1,service._load_index().get("5738SS1").__len__())
        self.assertEqual(1,service._withheld)

    def test_no_virtual_gap_content_substitution_and_cached_correlations(self):
        src,sibling,other,bad,definition,dup,missing,img,service,model=self.model()
        src.segment.extents=(NS(start_lba=10,virtual_address=0x100000,pages=1),
                             NS(start_lba=11,virtual_address=0x100400,pages=1))
        fresh=ProductLoadExplorer(img,inventory([src,sibling,other,bad,definition,dup,missing]))
        with self.assertRaises(ValueError):fresh.rows(src)
        references=fresh.rows(definition)
        self.assertEqual([sibling],[r["object"] for r in references if r.get("object")])
        self.assertIn("with unsupported headers: 2",references[0]["lines"][3])
        count=len(img.reads)
        fresh.rows(definition)
        self.assertEqual(count,len(img.reads))


if __name__=="__main__":
    unittest.main()
