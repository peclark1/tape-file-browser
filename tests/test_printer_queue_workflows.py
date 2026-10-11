"""Synthetic saved 0E/C7 printer-queue keys and SPLCB token candidate navigation."""
import unittest
from types import SimpleNamespace as NS

from as400_printer_queues import (
    PrinterQueueExplorer, PrinterQueueKey, decode_printer_queue_index)
from as400_5250 import Guided5250, parse_command
from as400_spool_controls import SpoolControlExplorer
from test_type_capabilities import Image, inventory, obj


def index_fixture(*, page_size=1024, root=0x800, key_token="SP0002",
                  prefix="2000001a001a"):
    key = (key_token.ljust(10).encode("cp037")
           + bytes.fromhex("00000500000003707678000000000000"))
    assert len(key) == 26
    data=bytearray(root+page_size)
    data[0x100:0x106]=bytes.fromhex(prefix)
    data[0x420:0x426]=(0x100000+root).to_bytes(6,"big")
    data[0x42A:0x42E]=page_size.to_bytes(4,"big")
    end=root+14+len(key)
    data[root:root+8]=(bytes.fromhex("970008cc") +
          (page_size-14-len(key)).to_bytes(2,"big")
          +end.to_bytes(2,"big"))
    data[root+8:root+14]=(bytes([len(key)-1]) +
                          (root+14).to_bytes(2,"big")
                          +bytes.fromhex("600000"))
    data[root+14:end]=key
    return data,key


def spool_fixture(token):
    data=bytearray(512)
    if token is not None:
        data[0x1C5:0x1CB]=token.encode("cp037")
    return data


class PrinterQueueTests(unittest.TestCase):
    def make(self,*, page_size=1024, root=0x800, token="SP0002",
             spool_tags=("SP0002","SP0002"),prefix="2000001a001a"):
        d,key=index_fixture(page_size=page_size,root=root,
                            key_token=token,prefix=prefix)
        pr=obj("QSPSIDQ",(0x0E,0xC7),10,"QSYS")
        pr.segment.virtual_address=0x100000
        pr.segment.extents=(NS(start_lba=10,virtual_address=0x100000,
                               pages=len(d)//512),)
        spools=[];data=[(pr,d)]
        for i,tag in enumerate(spool_tags):
            target=obj("QSPSCB",(0x19,0xC2),100+i,None)
            target.segment.extents=(NS(start_lba=100+i,
                    virtual_address=target.segment.virtual_address,pages=1),)
            spools.append(target);data.append((target,spool_fixture(tag)))
        inv=inventory([pr]+spools)
        img=Image(data)
        exp=PrinterQueueExplorer(img,inv)
        separate=SpoolControlExplorer(img,inv)
        model=Guided5250(inv,printer_queue_loader=exp.rows,
            capability_loader=lambda o,sample=None:
              exp.rows(o) if o.type_code=="0E/C7" else separate.rows(o))
        return pr,spools,img,exp,model,key

    def test_release_page_sizes_and_expected_prefixes(self):
        for page,root,prefix in (
            (1024,0x800,"2000001a001a"),
            (2048,0x1000,"2000005a001a"),
            (2048,0x1800,"30000050002c"),
        ):
            data,key=index_fixture(page_size=page,root=root,prefix=prefix)
            values,warn,pages=decode_printer_queue_index(data,0x100000)
            self.assertEqual(page,pages)
            self.assertFalse(warn)
            self.assertEqual(1,len(values))
            self.assertEqual(key,values[0].raw)
            self.assertEqual("SP0002",values[0].token_candidate)
            self.assertEqual(root+8,values[0].terminal_offset)  # tree element, not payload offset

    def test_strict_candidate_and_no_claimed_token_identity(self):
        for raw in (
            b"SP0002" + b" " * 4,
            b"SP0002"+b"\x00"*4,
            b"SPAB12"+b" "*4,
            b"SP0002"+b" "*3,
        ):
            entry=PrinterQueueKey(raw,0x80)
            # ASCII text is not an EBCDIC SP token even if legible.
            self.assertIsNone(entry.token_candidate)
        data,key=index_fixture()
        entry=PrinterQueueKey(key[0:6]+b"\x00"*4+key[10:],0x80)
        self.assertIsNone(entry.token_candidate)

    def test_command_spool_token_links_and_back(self):
        pr,spools,img,ex,model,key=self.make()
        self.assertEqual(("DSPPRTQ",{"PRTQ":"QSPSIDQ","TOKEN":"SP0002"}),
                         parse_command("DSPPRTQ PRTQ(QSPSIDQ) TOKEN(SP0002)"))
        model.run_command("DSPPRTQ PRTQ(QSPSIDQ) TOKEN(SP0002)")
        self.assertEqual("Saved printer-queue index",model.rows()[0]["name"])
        self.assertEqual("Key 1",model.rows()[1]["name"])
        model.selected=1;model.open_row(1)
        self.assertEqual("Saved printer-queue key",model.rows()[0]["name"])
        self.assertIn("SP0002",model.rows()[0]["lines"][2])
        links=[(i,r["object"]) for i,r in enumerate(model.rows())
               if r.get("object") is not None]
        self.assertEqual(spools,[target for _,target in links])
        i=links[1][0]
        model.selected=i;model.open_row(i)
        self.assertEqual("Saved spool-control evidence",model.rows()[0]["name"])
        model.back();self.assertEqual(i,model.selected)
        model.back();self.assertEqual(1,model.selected)
        self.assertTrue(img.reads)

    def test_no_match_and_duplicate_origins_retained(self):
        pr,spools,img,ex,model,key=self.make(spool_tags=("SP0001",))
        page=ex.rows(pr)
        self.assertEqual(2,len(page))
        info=ex.rows(pr,entry=ex.entries(pr)[0][0])
        self.assertEqual("No spool-control token match",info[-1]["name"])
        self.assertFalse(any(r.get("object") for r in info))
        self.assertEqual(1,len([r for r in info if r["name"]=="SPLCB token-name candidates"]))

    def test_malformed_controls_and_filters_fail_closed(self):
        data,key=index_fixture()
        for cut in (0,512,0x42D):
            with self.assertRaises(ValueError):
                decode_printer_queue_index(data[:cut],0x100000)
        for offset,contents in ((0x100,b"\x00"),(0x105,b"\x01"),
                                 (0x42A,(4096).to_bytes(4,"big")),
                                 (0x420,(0x200000).to_bytes(6,"big"))):
            bad=bytearray(data);bad[offset:offset+len(contents)]=contents
            with self.assertRaises(ValueError):
                decode_printer_queue_index(bad,0x100000)
        pr,spools,img,ex,model,key=self.make()
        for options in ({"start":-1},{"start":"0"},{"keyhex":"GG"},
                        {"keyhex":"FF"*257},{"token":"SPABCD"},
                        {"entry":NS(raw=key,terminal_offset=-1)}):
            with self.assertRaises(ValueError):
                ex.rows(pr,**options)
        with self.assertRaises(ValueError):
            ex.rows(spools[0])
        model.run_command("DSPPRTQ PRTQ(QSPSIDQ) TOKEN(SP0001)")
        self.assertEqual(1,len(model.rows()))


if __name__=="__main__":
    unittest.main()
