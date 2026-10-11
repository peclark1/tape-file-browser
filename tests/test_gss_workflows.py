"""Synthetic saved GSS symbol table, record boundaries and Guided navigation.

All 94 synthetic records are invented; no original graphics or image
bytes are committed. Control offsets correspond to empirical two-image
CISC 19/0C 004A/4009 variant.
"""
import unittest
from types import SimpleNamespace as NS

from as400_gss import (
    SavedSymbolExplorer, decode_gss_symbol_slots,
    TABLE_BASE, TABLE_END, SLOT_COUNT)
from as400_5250 import Guided5250, parse_command
from test_type_capabilities import obj, Image, inventory


def gss_fixture(*, records=94, alias=False, corrupt=None):
    if not 1 <= records <= SLOT_COUNT:
        raise ValueError("bad record count")
    body = bytearray(4*512)
    body[0x100:0x102] = bytes.fromhex("0014")
    body[0x116:0x11C] = bytes.fromhex("0183004A4009")
    body[0x120:0x124] = bytes.fromhex("200000F9")
    start=0x160
    for i in range(records):
        offset = start+i*8
        body[TABLE_BASE+i*2:TABLE_BASE+i*2+2]=offset.to_bytes(2,"big")
        at=TABLE_BASE+offset
        blob=bytes([0xC1, i, 0x10, 0x20, 0x30, 0x40, 0xFF, 0x00])
        if i == records-1:
            blob=bytes([0xC1, i, 0x10, 0x20, 0x30, 0x40, 0x50, 0x60])
        body[at:at+8] = blob
    if alias and records < SLOT_COUNT:
        body[TABLE_BASE+records*2:TABLE_BASE+records*2+2] = (
            start+10*8).to_bytes(2,"big")
    end=TABLE_BASE + start + records*8
    length=end-0x100
    body[0x102:0x106]=length.to_bytes(4,"big")
    body[0x112:0x116]=(length-4).to_bytes(4,"big")
    if corrupt is not None:
        body[corrupt[0]] = corrupt[1]
    return body


class SavedGSSTests(unittest.TestCase):
    def setup(self, data=None):
        o=obj("ADMUVGEP",(0x19,0x0C),10,"QSYS")
        data=gss_fixture() if data is None else data
        o.segment.pages=len(data)//512
        o.segment.extents=(NS(start_lba=10,virtual_address=o.segment.virtual_address,
                              pages=o.segment.pages),)
        img=Image([(o,data)])
        inv=inventory([o])
        ex=SavedSymbolExplorer(img)
        model=Guided5250(inv,gss_loader=ex.rows,
                          capability_loader=lambda target,sample=None:ex.rows(target))
        return o,img,ex,model

    def test_table_176_slots_94_records_and_last_tail_is_not_claimed_delimited(self):
        slots,warnings,empty=decode_gss_symbol_slots(
            gss_fixture(),type_code="19/0C")
        self.assertEqual(176,SLOT_COUNT)
        self.assertEqual(94,len(slots))
        self.assertEqual(82,empty)
        self.assertEqual([],list(warnings))
        self.assertEqual(0x284,slots[0].offset)
        self.assertEqual("delimited",slots[0].status)
        self.assertEqual("open-tail",slots[-1].status)
        self.assertEqual("c1",slots[0].raw[:1].hex())
        self.assertEqual("ff00",slots[0].raw[-2:].hex())
        self.assertEqual(list(range(1,95)),[slot.ordinal for slot in slots])

    def test_aliased_slots_preserve_both_origins_without_extra_raw_record(self):
        values, warnings, unused=decode_gss_symbol_slots(
            gss_fixture(alias=True),type_code="19/0C")
        self.assertEqual(95,len(values))
        self.assertEqual(81,unused)
        self.assertEqual(values[10].offset,values[94].offset)
        self.assertEqual(values[10].raw,values[94].raw)
        self.assertTrue(values[94].alias)
        self.assertFalse(values[10].alias)

    def test_command_paging_exact_byte_details_and_back(self):
        o,img,ex,model=self.setup()
        self.assertEqual(("DSPGSS",{"GSS":"ADMUVGEP","SLOT":"11"}),
                         parse_command("DSPGSS GSS(ADMUVGEP) SLOT(11)"))
        model.run_command("DSPGSS GSS(ADMUVGEP)")
        self.assertEqual("Saved GSS symbol slots",model.rows()[0]["name"])
        self.assertEqual(50,len([r for r in model.rows()
                                 if r.get("kind")=="gss_symbol_action"
                                 and r.get("request",{}).get("slot") is not None]))
        next_row=next(i for i,r in enumerate(model.rows()) if r["name"]=="Next 50")
        model.selected=next_row;model.open_row(next_row)
        self.assertEqual("Saved slot 51",model.rows()[2]["name"])
        selection=next(i for i,r in enumerate(model.rows()) if r["name"]=="Saved slot 52")
        model.selected=selection;model.open_row(selection)
        self.assertEqual("Saved GSS byte record",model.rows()[0]["name"])
        self.assertIn("52 of 176",model.rows()[0]["lines"][1])
        self.assertIn("C1",model.rows()[1]["lines"][1])
        model.back();self.assertEqual(selection,model.selected)
        model.back();self.assertEqual(next_row,model.selected)
        model.run_command("DSPGSS GSS(ADMUVGEP) SLOT(11)")
        self.assertEqual("Saved GSS byte record",model.rows()[0]["name"])
        self.assertIn("11 of 176",model.rows()[0]["lines"][1])
        self.assertGreater(len(img.reads),0)

    def test_valid_unpopulated_slot_is_not_guessed_and_unsupported_mode_withheld(self):
        o,img,ex,model=self.setup()
        model.run_command("DSPGSS GSS(ADMUVGEP) SLOT(170)")
        self.assertEqual("Saved slot unavailable",model.rows()[0]["name"])
        model.run_command("DSPGSS GSS(ADMUVGEP) SLOT(177)")
        self.assertIn("SLOT must",model.status)
        for corrupted in ((0x100,0), (0x119,0), (0x120,0), (0x102,0xFF),
                          (0x115,0)):
            with self.assertRaises(ValueError):
                decode_gss_symbol_slots(gss_fixture(corrupt=corrupted),type_code="19/0C")
        with self.assertRaises(ValueError):
            decode_gss_symbol_slots(gss_fixture(),type_code="19/38")

    def test_bad_pointers_and_bad_delimiters_withheld_without_shifting_records(self):
        corrupt = gss_fixture()
        corrupt[TABLE_BASE:TABLE_BASE+2]=(0xFFFF).to_bytes(2,"big")
        with self.assertRaises(ValueError):
            decode_gss_symbol_slots(corrupt,type_code="19/0C")
        first=TABLE_BASE+0x160
        for offset in (first,first+6):
            bad=gss_fixture(corrupt=(offset,0))
            slots,warnings,unused=decode_gss_symbol_slots(bad,type_code="19/0C")
            self.assertEqual(93,len(slots))
            self.assertTrue(warnings)
            self.assertEqual(2,slots[0].ordinal)
        o,img,ex,model=self.setup()
        o.segment.extents=(NS(start_lba=10,virtual_address=o.segment.virtual_address,
                              pages=1),
                           NS(start_lba=11,virtual_address=o.segment.virtual_address+1024,
                              pages=3))
        fresh=SavedSymbolExplorer(img)
        with self.assertRaises(ValueError):
            fresh.rows(o)
        with self.assertRaises(ValueError):
            ex.rows(obj("OTHER",(0x19,0x03)))


if __name__=="__main__":
    unittest.main()
