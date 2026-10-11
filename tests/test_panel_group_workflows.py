"""Synthetic compiled panel-group tagged symbol workflows, no original-image text."""
import unittest
from types import SimpleNamespace as NS

from as400_panel_groups import (
    PanelGroupExplorer, decode_panel_symbols, WINDOW_BYTES, PanelSymbol)
from as400_5250 import Guided5250, parse_command
from test_type_capabilities import obj, inventory, Image


def tagged(name):
    b = name.encode("cp037")
    assert 4 <= len(b) <= 40
    return bytes([0x13,len(b)]) + b


def fixture(*, size=WINDOW_BYTES, header="00000100", extras=()):
    assert size % 512 == 0
    data=bytearray(size)
    data[0x100:0x104]=bytes.fromhex(header)
    data[0x320:0x320+len(tagged("CRTCLPGM/PGM"))]=tagged("CRTCLPGM/PGM")
    data[0x460:0x460+len(tagged("DSPLCLHDW/OUTPUT"))]=tagged("DSPLCLHDW/OUTPUT")
    data[0x530:0x530+len(tagged("DYNAMIC_TRACE"))]=tagged("DYNAMIC_TRACE")
    for at,name in extras:
        blob=tagged(name)
        data[at:at+len(blob)]=blob
    return data


class PanelGroupTests(unittest.TestCase):
    def make(self,data=None,*, header="00000100"):
        d=fixture(header=header) if data is None else data
        primary=obj("QHPANEL",(0x19,0x15),10,None)
        primary.segment.virtual_address=0x100000
        primary.segment.pages=len(d)//512
        primary.segment.extents=(NS(start_lba=10,virtual_address=0x100000,
                                    pages=primary.segment.pages),)
        program=obj("CRTCLPGM",(0x19,0x05),100,"QIWS")
        other=obj("CRTCLPGM",(0x19,0x05),101,None)
        wrong=obj("CRTCLPGM",(0x02,0x01),102,"QIWS")
        inv=inventory([primary,program,other,wrong])
        image=Image([(primary,d)])
        explorer=PanelGroupExplorer(image,inv)
        model=Guided5250(inv,panel_group_loader=explorer.rows,
                         capability_loader=lambda o,sample=None:explorer.rows(o))
        return primary,program,other,wrong,image,explorer,model

    def test_relocated_tagged_symbols_and_header_variants(self):
        for header in ("00000100","00000050"):
            o,program,other,wrong,image,ex,_=self.make(header=header)
            entries,word,nread,capacity=ex.symbols(o)
            self.assertEqual(header.upper(),word)
            self.assertEqual(WINDOW_BYTES,nread)
            self.assertEqual(WINDOW_BYTES,capacity)
            self.assertEqual(["CRTCLPGM/PGM","DSPLCLHDW/OUTPUT","DYNAMIC_TRACE"],
                             [e.text for e in entries])
            self.assertEqual([0x320,0x460,0x530],[e.offset for e in entries])
            self.assertEqual(tagged("CRTCLPGM/PGM"),entries[0].raw)
            self.assertEqual(WINDOW_BYTES//512,len(image.reads)-1)

    def test_exact_length_bounds_and_false_positive_rejection(self):
        b=bytearray(fixture())
        b[0x600:0x602]=bytes([0x13,3])
        b[0x602:0x606]="ABCD".encode("cp037")
        b[0x680:0x682]=bytes([0x13,41])
        b[0x682:0x682+41]=bytes([0xc1])*41
        b[0x700:0x702]=bytes([0x13,8])
        b[0x702:0x70a]=bytes.fromhex("c1c2c30000000000")
        found=decode_panel_symbols(b)
        self.assertEqual(3,len(found))
        self.assertNotIn(0x600,[e.offset for e in found])
        self.assertNotIn(0x680,[e.offset for e in found])
        self.assertNotIn(0x700,[e.offset for e in found])
        for at in (-1,1,"0"):
            with self.assertRaises(ValueError):decode_panel_symbols(b,at)

    def test_search_and_navigable_candidate_command_names_back(self):
        primary,program,other,wrong,im,ex,model=self.make()
        self.assertEqual(("DSPPNLGRP",{"PNLGRP":"QHPANEL","NAME":"DSPL*","AT":"0"}),
                         parse_command("DSPPNLGRP PNLGRP(QHPANEL) NAME(DSPL*) AT(0)"))
        model.run_command("DSPPNLGRP PNLGRP(QHPANEL) NAME(DSPL*) AT(0)")
        self.assertEqual("Compiled panel-group symbols",model.rows()[0]["name"])
        self.assertEqual("DSPLCLHDW/OUTPUT",model.rows()[1]["name"])
        model.selected=1
        model.open_row(1)
        self.assertEqual("Tagged compiled name",model.rows()[0]["name"])
        self.assertIn("DSPLCLHDW/OUTPUT",model.rows()[0]["lines"][3])
        model.back()
        self.assertEqual(1,model.selected)
        model.run_command("DSPPNLGRP PNLGRP(QHPANEL) NAME(CRT*)")
        model.open_row(1)
        self.assertEqual("Command-name candidates",model.rows()[1]["name"])
        names=[r["object"] for r in model.rows() if r.get("object")]
        self.assertEqual([other,program],names)
        self.assertNotIn(wrong,names)
        self.assertTrue(all("name" in r["note"] or "prefix" in r["note"]
                            for r in model.rows() if r.get("object")))

    def test_paging_window_step_and_malformed_extents(self):
        rowsize=2*WINDOW_BYTES
        extras=[(0x900+i*24, f"TEST{i:04d}/SYMBOL") for i in range(55)]
        extras.append((WINDOW_BYTES+0x300,"SECOND/OUTPUT"))
        d=fixture(size=rowsize,extras=extras)
        primary,program,other,wrong,im,ex,model=self.make(d)
        model.run_command("DSPPNLGRP PNLGRP(QHPANEL)")
        self.assertEqual(50,sum(x["kind"]=="panel_symbol_action" and
                                x["request"].get("symbol") is not None
                                for x in model.rows()))
        index=next(i for i,r in enumerate(model.rows()) if r["name"]=="Next symbols")
        model.selected=index;model.open_row(index)
        self.assertTrue(any(r["name"]=="TEST0049/SYMBOL" for r in model.rows()))
        model.back()
        self.assertEqual(index,model.selected)
        otherwin=next(i for i,r in enumerate(model.rows()) if r["name"]=="Next 32 KiB")
        model.open_row(otherwin)
        self.assertIn("SECOND/OUTPUT",[r["name"] for r in model.rows()])
        model.back()
        self.assertEqual(otherwin,model.selected)
        primary.segment.extents=(NS(start_lba=10,virtual_address=0x100000,pages=32),
                                 NS(start_lba=42,virtual_address=0x100000+WINDOW_BYTES+512,pages=31))
        fresh=PanelGroupExplorer(im,inventory([primary]))
        with self.assertRaises(ValueError):fresh.rows(primary,at=WINDOW_BYTES)

    def test_bad_headers_and_requests_fail_closed(self):
        primary,program,other,wrong,im,ex,model=self.make()
        for kwargs in ({"at":1},{"at":-1},{"at":WINDOW_BYTES},
                       {"name":"junk!"},{"start":-1},{"start":"0"}):
            with self.assertRaises(ValueError):ex.rows(primary,**kwargs)
        with self.assertRaises(ValueError):ex.rows(program)
        entry=ex.symbols(primary)[0][0]
        with self.assertRaises(ValueError):
            ex.rows(primary,symbol=PanelSymbol(entry.offset+1,entry.text,entry.raw))
        bad=bytearray(fixture());bad[0x100]=0xAA
        badprimary,*rest=self.make(bad)
        with self.assertRaises(ValueError):rest[-2].rows(badprimary)
        model.run_command("DSPPNLGRP PNLGRP(QHPANEL) AT(1)")
        self.assertIn("AT must",model.status)


if __name__=="__main__":
    unittest.main()
