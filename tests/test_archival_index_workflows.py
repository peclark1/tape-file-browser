"""Synthetic bounded SCHIDX/MSRVI machine-index key navigation tests."""
import unittest
from types import SimpleNamespace as NS

from as400_archival_indexes import (ArchivalIndexExplorer,
                                    decode_archival_index)
from as400_5250 import Guided5250,parse_command
from test_type_capabilities import obj,inventory,Image


def index_fixture(kind="0E/07", size=1024, root=0x800, key_len=47):
    data=bytearray(root+size)
    headers={"0E/07":bytes.fromhex("E000004B002E"),
             "0E/91":bytes.fromhex("2000004B0016"),
             "0E/D0":bytes.fromhex("200000160012"),
             "0E/C8":bytes.fromhex("60000032001B")}
    data[0x100:0x106]=headers[kind]
    data[0x106:0x10A]=(1).to_bytes(4,"big")
    data[0x420:0x426]=(0x100000+root).to_bytes(6,"big")
    data[0x42A:0x42E]=size.to_bytes(4,"big")
    key=bytes([0xC1]) + bytes((i%256 for i in range(key_len-1)))
    end=root+14+key_len
    data[root:root+8]=(bytes.fromhex("970008cc") +
        (size-14-key_len).to_bytes(2,"big")+end.to_bytes(2,"big"))
    data[root+8:root+14]=(bytes([key_len-1]) +
        (root+14).to_bytes(2,"big")+bytes.fromhex("600000"))
    data[root+14:end]=key
    return data,key


class ArchivalIndexTests(unittest.TestCase):
    def setup_view(self,kind,key_len=47):
        pair={"0E/07":(0x0E,0x07),"0E/91":(0x0E,0x91),
              "0E/D0":(0x0E,0xD0),"0E/C8":(0x0E,0xC8)}[kind]
        o=obj("TESTIDX",pair)
        o.segment.virtual_address=0x100000
        d,key=index_fixture(kind,key_len=key_len)
        o.segment.extents=(NS(start_lba=10,virtual_address=0x100000,
                              pages=len(d)//512),)
        inv=inventory([o])
        ex=ArchivalIndexExplorer(Image([(o,d)]))
        return o,ex,Guided5250(inv,archival_index_loader=ex.rows),key

    def test_both_release_page_sizes_and_key_lengths(self):
        for kind,length in (("0E/07",47),("0E/91",81),("0E/D0",32),("0E/C8",42)):
            for size,root in ((1024,0x800),(2048,0x1000),(2048,0x1800)):
                d,key=index_fixture(kind,size=size,root=root,key_len=length)
                found,warnings,scalar,page=decode_archival_index(d,0x100000,kind)
                self.assertEqual(1,len(found))
                self.assertEqual(key,found[0].raw)
                self.assertEqual(size,page)
                self.assertEqual(1,scalar)
                self.assertFalse(warnings)

    def test_malformed_page_bounds_and_unverified_count(self):
        d,key=index_fixture()
        for cut in (0,256,0x42D):
            with self.assertRaises(ValueError):
                decode_archival_index(d[:cut],0x100000,"0E/07")
        b=bytearray(d);b[0x100]=0
        with self.assertRaises(ValueError):decode_archival_index(b,0x100000,"0E/07")
        b=bytearray(d);b[0x42A:0x42E]=(4096).to_bytes(4,"big")
        with self.assertRaises(ValueError):decode_archival_index(b,0x100000,"0E/07")
        b=bytearray(d);b[0x420:0x426]=(0x200000).to_bytes(6,"big")
        with self.assertRaises(ValueError):decode_archival_index(b,0x100000,"0E/07")
        b=bytearray(d);b[0x806:0x808]=(0x810).to_bytes(2,"big")
        found,warn,_,_=decode_archival_index(b,0x100000,"0E/07")
        self.assertFalse(found);self.assertTrue(warn)
        b=bytearray(d);b[0x109]=2
        found,warn,scalar,_=decode_archival_index(b,0x100000,"0E/07")
        self.assertEqual(1,len(found));self.assertEqual(2,scalar)
        self.assertTrue(any("differs" in x for x in warn))
        with self.assertRaises(ValueError):decode_archival_index(d,0x100000,"19/05")

    def test_new_saved_variant_headers_and_corrupt_root_gates(self):
        d,key=index_fixture("0E/D0",size=2048,root=0x1000)
        got,warnings,_,size=decode_archival_index(d,0x100000,"0E/D0")
        self.assertEqual([key],[item.raw for item in got])
        self.assertFalse(warnings)
        self.assertEqual(size,2048)
        b=bytearray(d);b[0x103]=0x32
        with self.assertRaises(ValueError):
            decode_archival_index(b,0x100000,"0E/D0")
        for header in ("200000160006","20000016000C","60000032001B"):
            d,key=index_fixture("0E/C8",size=2048,root=0x1000)
            b=bytearray(d);b[0x100:0x106]=bytes.fromhex(header)
            got,warnings,_,size=decode_archival_index(b,0x100000,"0E/C8")
            self.assertEqual([key],[item.raw for item in got])
            self.assertFalse(warnings)
        b[0x100:0x106]=bytes.fromhex("60000032000C")
        with self.assertRaises(ValueError):
            decode_archival_index(b,0x100000,"0E/C8")
        b=bytearray(d);b[0x420:0x426]=bytes(6)
        with self.assertRaises(ValueError):
            decode_archival_index(b,0x100000,"0E/C8")

    def test_guided_hex_navigation_back_and_unresolved_semantics(self):
        for kind,length,command,arg in (("0E/07",47,"DSPSCHIDX","SCHIDX"),
                                        ("0E/91",81,"DSPMSRVI","MSRVI"),
                                        ("0E/D0",32,"DSPEDTIDX","EDTIDX"),
                                        ("0E/C8",42,"DSPSRMIDX","SRMIDX")):
            o,ex,model,key=self.setup_view(kind,length)
            model.run_command(f"{command} {arg}(TESTIDX) KEYHEX(C1)")
            self.assertEqual("Saved machine-index keys",model.rows()[0]["name"])
            self.assertEqual(2,len(model.rows()))
            model.selected=1;model.open_row(1)
            self.assertEqual("Opaque index key",model.rows()[0]["name"])
            self.assertIn("No chronological order",model.rows()[0]["lines"][4])
            self.assertEqual(1+(length+15)//16,len(model.rows()))
            model.back();self.assertEqual(1,model.selected)
            model.run_command(f"{command} {arg}(TESTIDX) KEYHEX(FF)")
            self.assertEqual(1,len(model.rows()))
            for values in ({"start":-1},{"keyhex":"GG"},{"keyhex":"FF"*257}):
                with self.assertRaises(ValueError):ex.rows(o,**values)
            with self.assertRaises(ValueError):
                ex.rows(o,entry=NS(raw=key,terminal_offset=-1))
            self.assertEqual(command,parse_command(f"{command} {arg}(TESTIDX)")[0])


if __name__=="__main__":
    unittest.main()
