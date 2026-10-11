"""Invented saved WSCST TRANSFORM fixtures for bounded forward/reverse links."""
import unittest
from types import SimpleNamespace as NS

from as400_wscst import (
    WorkstationTransformExplorer, decode_wscst_transform,
    NAME_BYTES)
from as400_5250 import Guided5250, parse_command
from test_type_capabilities import Image, inventory, obj


def fixture(name=None, *, where=0x1024, declared=0x1400):
    size=((0x100+declared+511)//512)*512
    data=bytearray(size)
    data[0x100:0x104]=bytes.fromhex("00000034")
    data[0x104:0x108]=declared.to_bytes(4,"big")
    data[0x108:0x10A]=bytes.fromhex("0002")
    data[0x10A:0x114]="TRANSFORM ".encode("cp037")
    data[0x114:0x118]=bytes.fromhex("00000034")
    data[0x118:0x11C]=(declared-52).to_bytes(4,"big")
    data[0x134:0x138]=bytes.fromhex("00000036")
    data[0x138:0x13C]=(declared-52).to_bytes(4,"big")
    data[0x13C:0x144]="TRANSFRM".encode("cp037")
    if name:
        assert where in (0x824,0x1024) and len(name)<=10
        data[where:where+NAME_BYTES]=name.ljust(NAME_BYTES).encode("cp037")
    return data


class WSCSTTests(unittest.TestCase):
    def setup(self, *, alias=False):
        source=obj("QWPPAN2180",(0x19,0x38),10,"QSYS")
        target=obj("QWPIBM4208",(0x19,0x38),50,"QSYS")
        unknown=obj("QWPOKI810",(0x19,0x38),90,None)
        others=[source,target,unknown]
        if alias:
            dup=obj("QWPIBM4208",(0x19,0x38),120,None)
            others.append(dup)
        else:
            dup=None
        payloads=[fixture("QWPIBM4208"),fixture(),fixture("QNOTHERE",where=0x824)]
        if dup:payloads.append(fixture(declared=0x600))
        for item,data in zip(others,payloads):
            item.segment.virtual_address=0x100000
            item.segment.pages=len(data)//512
            item.segment.extents=(NS(start_lba=item.segment.start_lba,
                                     virtual_address=0x100000,
                                     pages=item.segment.pages),)
        img=Image(list(zip(others,payloads)))
        inv=inventory(others)
        ex=WorkstationTransformExplorer(img,inv)
        model=Guided5250(inv,capability_loader=lambda o,sample=None:ex.rows(o))
        return source,target,unknown,dup,img,ex,model

    def test_independent_echo_lengths_and_record_markers(self):
        h=decode_wscst_transform(fixture("QWPIBM4208"),type_code="19/38")
        self.assertEqual(0x1400,h.length)
        self.assertEqual([0x1024],[r.offset for r in h.references])
        self.assertEqual("QWPIBM4208",h.references[0].name)
        self.assertEqual(30,len(h.references[0].raw))
        shorter=decode_wscst_transform(fixture("QNOTHERE",where=0x824,declared=0x900),
                                       type_code="19/38")
        self.assertEqual([0x824],[r.offset for r in shorter.references])
        no_slot=decode_wscst_transform(fixture(declared=0x200),type_code="19/38")
        self.assertEqual((),no_slot.references)

    def test_forward_same_name_origin_and_reverse_links_with_back(self):
        source,target,unknown,dup,img,ex,model=self.setup()
        self.assertEqual(("DSPWSCST",{"WSCST":"QWPPAN2180"}),
                         parse_command("DSPWSCST WSCST(QWPPAN2180)"))
        model.run_command("DSPWSCST WSCST(QWPPAN2180)")
        self.assertEqual("Saved WSCST TRANSFORM descriptor",model.rows()[0]["name"])
        self.assertEqual([target],[r["object"] for r in model.rows() if r.get("object")])
        link=next(i for i,r in enumerate(model.rows()) if r.get("object") is target)
        model.selected=link;model.open_row(link)
        self.assertEqual("Saved WSCST TRANSFORM descriptor",model.rows()[0]["name"])
        self.assertEqual([source],[r["object"] for r in model.rows() if r.get("object")])
        self.assertIn("its exact name in one supported slot: 1",model.rows()[1]["lines"][0])
        model.back();self.assertEqual(link,model.selected)
        model.run_command("DSPWSCST WSCST(QWPIBM4208)")
        self.assertEqual("Saved WSCST TRANSFORM descriptor",model.rows()[0]["name"])
        self.assertIn("TRANSFRM",model.rows()[0]["lines"][3])

    def test_duplicate_target_names_are_not_called_parent_pointers(self):
        src,target,unknown,dup,img,ex,model=self.setup(alias=True)
        rows=ex.rows(src)
        targets=[r["object"] for r in rows if r.get("object")]
        self.assertEqual([dup,target],targets)
        self.assertTrue(all("role" in r["note"] or "name" in r["note"]
                            for r in rows if r.get("object")))
        self.assertEqual([src],[r["object"] for r in ex.rows(target)
                                if r.get("object")])
        self.assertEqual([src],[r["object"] for r in ex.rows(dup)
                                if r.get("object")])

    def test_malformed_control_and_unpadded_name_fail_closed(self):
        for at,value in ((0x103,0),(0x109,0),(0x10A,0),(0x117,0),
                         (0x11A,0),(0x137,0),(0x13C,0)):
            bad=fixture()
            bad[at]=value
            with self.assertRaises(ValueError):
                decode_wscst_transform(bad,type_code="19/38")
        with self.assertRaises(ValueError):
            decode_wscst_transform(fixture()[:0x800],type_code="19/38")
        with self.assertRaises(ValueError):
            decode_wscst_transform(fixture(),type_code="19/0C")
        data=fixture("QWPIBM4208")
        data[0x1024+12]=0x00
        h=decode_wscst_transform(data,type_code="19/38")
        self.assertEqual([],list(h.references))

    def test_virtual_gap_withheld_and_reverse_index_not_inferred_missing(self):
        src,target,unknown,dup,img,ex,model=self.setup()
        src.segment.extents=(NS(start_lba=10,virtual_address=0x100000,pages=2),
                             NS(start_lba=12,virtual_address=0x100600,pages=9))
        fresh=WorkstationTransformExplorer(img,inventory([src,target,unknown]))
        with self.assertRaises(ValueError):fresh.rows(src)
        links=fresh.rows(target)
        self.assertEqual("Other saved transforms naming this WSCST",links[-1]["name"])
        self.assertIn("Withheld/unsupported WSCST primary sources: 1",
                      links[-1]["lines"][1])
        before=len(img.reads)
        fresh.rows(target)
        self.assertEqual(before,len(img.reads))


if __name__=="__main__":
    unittest.main()
