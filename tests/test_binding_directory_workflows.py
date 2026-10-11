"""Synthetic CISC BNDDIR 48-byte records and read-only SRVPGM links."""
import unittest
from types import SimpleNamespace as NS

from as400_5250 import Guided5250, parse_command
from as400_binding_directories import (
    ENTRY_AT, STRIDE, BindingDirectoryExplorer, decode_binding_entries)
from test_type_capabilities import Image, inventory, obj


def record(name, library="*LIBL", target="02/03", tail=None):
    first=name.ljust(10).encode("cp037")
    second=library.ljust(10).encode("cp037")
    typ=bytes.fromhex(target.replace("/",""))
    opaque=bytes(26) if tail is None else tail
    assert len(first)==len(second)==10 and len(opaque)==26
    return first+second+typ+opaque


def binding_fixture(entries, *, pages=8):
    data=bytearray(pages*512)
    data[0x100:0x104]=bytes.fromhex("00010000")
    data[0x104:0x108]=len(entries).to_bytes(4,"big")
    data[0x112:0x114]=STRIDE.to_bytes(2,"big")
    data[0x116:0x118]=(len(entries)*STRIDE).to_bytes(2,"big")
    for i,entry in enumerate(entries):
        at=ENTRY_AT+STRIDE*i
        data[at:at+STRIDE]=entry
    return data


class BindingDirectoryTests(unittest.TestCase):
    def make(self, *, names=None, duplicates=False):
        if names is None:
            names=[("QLEAWI","*LIBL","02/03"),
                   ("QLESSNSY","*LIBL","02/03"),
                   ("QC2ABS","*LIBL","03/01")]
        directory=obj("QILE",(0x19,0x37),10,"QSYS")
        blob=binding_fixture([record(*item) for item in names])
        directory.segment.virtual_address=0x100000
        directory.segment.extents=(NS(start_lba=10,
                                     virtual_address=0x100000,
                                     pages=len(blob)//512),)
        a=obj("QLEAWI",(0x02,0x03),100,"QSYS")
        b=obj("QLESSNSY",(0x02,0x03),101,"QSYS")
        c=obj("QLEAWI",(0x02,0x01),102,"QSYS")
        objects=[directory,a,b,c]
        if duplicates:
            objects.append(obj("QLEAWI",(0x02,0x03),103,None))
        inv=inventory(objects)
        image=Image([(directory,blob)])
        service=BindingDirectoryExplorer(image,inv)
        model=Guided5250(inv,binding_loader=service.rows,
                         capability_loader=lambda o,sample=None: service.rows(o))
        return directory,a,b,c,inv,image,service,model

    def test_empirical_header_count_stride_and_exact_fields(self):
        entries=[record("QSNAPI","*LIBL","02/03"),
                 record("QC2ABS","*LIBL","03/01",
                        tail=bytes(range(26)))]
        for count in (0,1,2,52):
            arr=[entries[i%2] for i in range(count)]
            blob=binding_fixture(arr)
            found=decode_binding_entries(blob,type_code="19/37")
            self.assertEqual(count,len(found))
            if count:
                self.assertEqual(ENTRY_AT,found[0].offset)
                self.assertEqual(48,len(found[0].raw))
                self.assertEqual("*LIBL",found[0].library_token)
                self.assertEqual(count,found[-1].ordinal)
        found=decode_binding_entries(binding_fixture(entries),type_code="19/37")
        self.assertEqual("QSNAPI",found[0].name)
        self.assertEqual("02/03",found[0].target_type)
        self.assertEqual("*SRVPGM",found[0].target_type_name)
        self.assertEqual("03/01",found[1].target_type)
        self.assertEqual("*MODULE",found[1].target_type_name)
        self.assertEqual(bytes(range(26)),found[1].raw[22:])

    def test_supported_name_type_links_not_other_types_or_resolved_libl(self):
        d,a,b,c,inv,image,svc,model=self.make()
        entries=svc.entries(d)
        rows=svc.rows(d,entry=entries[0])
        self.assertEqual("Saved binding-directory entry",rows[0]["name"])
        self.assertIn("*LIBL",rows[0]["lines"][2])
        self.assertIn("48",rows[0]["lines"][1])
        self.assertEqual([a],[r["object"] for r in rows if r.get("object")])
        self.assertNotIn(c,[r["object"] for r in rows if r.get("object")])
        unknown=svc.rows(d,entry=entries[2])
        self.assertEqual("No recovered target candidate",unknown[-1]["name"])
        self.assertFalse([r for r in unknown if r.get("object")])
        # A concrete saved library name restricts *candidate* matching.
        d,a,b,c,inv,image,svc,model=self.make(names=[("QLEAWI","QGPL","02/03")])
        self.assertEqual("No recovered target candidate",svc.rows(d,entry=svc.entries(d)[0])[-1]["name"])
        self.assertEqual("Saved service-program binding references",svc.rows(a)[0]["name"])
        self.assertEqual(0,len([r for r in svc.rows(a) if r["kind"]=="binding_entry_action"]))

    def test_paged_directory_and_bidirectional_service_program_selection(self):
        d,a,b,c,inv,image,svc,model=self.make(duplicates=True)
        self.assertEqual(("DSPBNDDIR",{"BNDDIR":"QILE","NAME":"QLE*"}),
                         parse_command("DSPBNDDIR BNDDIR(QILE) NAME(QLE*)"))
        model.run_command("DSPBNDDIR BNDDIR(QILE) NAME(QLE*)")
        self.assertEqual("Saved binding-directory entries",model.rows()[0]["name"])
        self.assertEqual(["Entry 1 QLEAWI","Entry 2 QLESSNSY"],
                         [r["name"] for r in model.rows()[1:]])
        model.selected=1;model.open_row(1)
        self.assertEqual("Saved binding-directory entry",model.rows()[0]["name"])
        refs=[(i,r["object"]) for i,r in enumerate(model.rows()) if r.get("object")]
        self.assertEqual([inv.objects[4],a],[target for _,target in refs])
        i=refs[1][0];model.selected=i;model.open_row(i)
        self.assertEqual("Saved service-program binding references",model.rows()[0]["name"])
        item=next(j for j,r in enumerate(model.rows()) if r["kind"]=="binding_entry_action")
        model.selected=item;model.open_row(item)
        self.assertEqual("Saved binding-directory entry",model.rows()[0]["name"])
        model.back();self.assertEqual(item,model.selected)
        model.back();self.assertEqual(i,model.selected)
        model.back();self.assertEqual(1,model.selected)
        model.run_command("DSPSRVPGM SRVPGM(QLESSNSY)")
        self.assertEqual("Saved service-program binding references",model.rows()[0]["name"])
        self.assertEqual(1,len([r for r in model.rows() if r["kind"]=="binding_entry_action"]))

    def test_malformed_headers_lengths_names_and_opaque_unknown_type(self):
        original=binding_fixture([record("QSNAPI")])
        for length in (0,0x107,ENTRY_AT,ENTRY_AT+47):
            with self.assertRaises(ValueError):
                decode_binding_entries(original[:length],type_code="19/37")
        for off,raw in ((0x100,b"\xff"),(0x104,(513).to_bytes(4,"big")),
                        (0x112,(40).to_bytes(2,"big")),
                        (0x116,(49).to_bytes(2,"big")),
                        (ENTRY_AT+10,b"\x00"),
                        (ENTRY_AT,b"\x00")):
            bad=bytearray(original);bad[off:off+len(raw)]=raw
            with self.assertRaises(ValueError):
                decode_binding_entries(bad,type_code="19/37")
        unknown=binding_fixture([record("NAME","*LIBL","19/ED")])
        found=decode_binding_entries(unknown,type_code="19/37")
        self.assertIsNone(found[0].target_type_name)
        with self.assertRaises(ValueError):
            decode_binding_entries(original,type_code="02/03")

    def test_missing_virtual_extent_and_unrelated_entry_origin(self):
        d,a,b,c,inv,image,svc,model=self.make()
        d.segment.extents=(NS(start_lba=10,virtual_address=0x100000,pages=1),
                           NS(start_lba=11,virtual_address=0x100400,pages=7))
        fresh=BindingDirectoryExplorer(image,inv)
        with self.assertRaises(ValueError):
            fresh.rows(d)
        with self.assertRaises(ValueError):
            svc.rows(a,entry=svc.entries(d)[0])
        d,a,b,c,inv,image,svc,model=self.make()
        for bad in ({"start":-1},{"start":"0"},{"name":"QLE!"}):
            with self.assertRaises(ValueError):
                svc.rows(d,**bad)

    def test_52_record_paging_and_filter_preserves_exact_ordinals(self):
        names=[(f"QC2{i:04d}","*LIBL","03/01") for i in range(52)]
        d,a,b,c,inv,image,svc,model=self.make(names=names)
        model.run_command("DSPBNDDIR BNDDIR(QILE)")
        self.assertEqual(50,len([r for r in model.rows() if r["name"].startswith("Entry ")]))
        next_row=next(i for i,r in enumerate(model.rows()) if r["name"]=="Next")
        model.selected=next_row;model.open_row(next_row)
        self.assertEqual(["Entry 51 QC20050","Entry 52 QC20051"],
                         [r["name"] for r in model.rows() if r["name"].startswith("Entry ")])
        model.back()
        self.assertEqual(next_row,model.selected)


if __name__=="__main__":
    unittest.main()
