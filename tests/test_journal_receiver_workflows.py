"""Synthetic CISC JRN/JRNRCV eight-byte address links and Guided navigation."""
import unittest
from types import SimpleNamespace as NS

from as400_5250 import Guided5250, parse_command
from as400_dasd import InternalAddress
from as400_journals import (
    FIRST_AT, SECOND_AT, READ_LIMIT,
    JournalReceiverExplorer, decode_journal_receiver_addresses)
from test_type_capabilities import obj, inventory, Image


def journal_bytes(first, second, *, early=False):
    data = bytearray(2*512)
    data[0x100:0x104] = bytes.fromhex("0006001A")
    data[0x104:0x108] = bytes.fromhex(
        "0000000A" if early else "000A000A")
    data[FIRST_AT:FIRST_AT+8] = first.to_bytes()
    data[SECOND_AT:SECOND_AT+8] = second.to_bytes()
    return data


class JournalReceiverTests(unittest.TestCase):
    def make(self, *, early=False, duplicate=False, second_null=False):
        source = obj("MYJRN", (0x09,0x01), 10,"QGPL")
        receiver_a = obj("MYRCV0001", (0x07,0x01),30,"QGPL")
        receiver_b = obj("MYRCV0002", (0x07,0x01),40,"QGPL")
        first = InternalAddress(0x00D0, 0x00572A000000)
        second = InternalAddress(0x0130,0x003394000000)
        receiver_a.segment.header = NS(owner=first)
        receiver_b.segment.header = NS(owner=second)
        original = [source,receiver_a,receiver_b]
        if duplicate:
            other=obj("DIFFERENT", (0x07,0x01),60,None)
            other.segment.header=NS(owner=first)
            original.append(other)
        else:
            other=None
        source.segment.extents=(NS(start_lba=10,
                                   virtual_address=source.segment.virtual_address,
                                   pages=2),)
        source.segment.header=NS(owner=InternalAddress(0x100,
                                                     source.segment.virtual_address))
        data=journal_bytes(first,InternalAddress(0,0) if second_null else second,
                           early=early)
        inv=inventory(original);image=Image([(source,data)])
        explorer=JournalReceiverExplorer(image,inv)
        model=Guided5250(inv,capability_loader=lambda o,sample=None:
                         explorer.rows(o))
        return source,receiver_a,receiver_b,other,image,explorer,model

    def test_both_cisc_release_control_variants_and_complete_owner_pointer(self):
        a=InternalAddress(0x0004,0x00B8EB000000)
        b=InternalAddress(0x0130,0x003394000000)
        for early in (True,False):
            found=decode_journal_receiver_addresses(journal_bytes(a,b,early=early),
                                                     type_code="09/01")
            self.assertEqual([FIRST_AT,SECOND_AT],[v.offset for v in found])
            self.assertEqual([a,b],[v.address for v in found])
            self.assertEqual(a.to_bytes(),found[0].address.to_bytes())
        with self.assertRaises(ValueError):
            decode_journal_receiver_addresses(journal_bytes(a,b),type_code="07/01")

    def test_forward_exact_address_selection_and_reverse_back(self):
        j,a,b,other,image,ex,model=self.make(early=True)
        self.assertEqual(("DSPJRN",{"JRN":"MYJRN"}),
                         parse_command("DSPJRN JRN(MYJRN)"))
        model.run_command("DSPJRN JRN(MYJRN)")
        self.assertEqual("Saved journal receiver addresses",model.rows()[0]["name"])
        links=[(i,row) for i,row in enumerate(model.rows())
               if row.get("object") is not None]
        self.assertEqual([a,b],[row["object"] for _,row in links])
        self.assertTrue(any("0x110" in row["note"] for _,row in links))
        selected=links[1][0]
        model.selected=selected;model.open_row(selected)
        self.assertEqual("Saved journal receiver identity",model.rows()[0]["name"])
        self.assertIn("Journal saved slots matching this exact address: 1",
                      model.rows()[0]["lines"][2])
        source_idx=next(i for i,row in enumerate(model.rows())
                        if row.get("object") is j)
        model.selected=source_idx;model.open_row(source_idx)
        self.assertEqual("Saved journal receiver addresses",model.rows()[0]["name"])
        model.back();self.assertEqual(source_idx,model.selected)
        model.back();self.assertEqual(selected,model.selected)
        model.run_command("DSPJRNRCV JRNRCV(MYRCV0002)")
        self.assertEqual("Saved journal receiver identity",model.rows()[0]["name"])
        self.assertEqual([j],[r["object"] for r in model.rows() if r.get("object")])

    def test_null_pointer_unassigned_and_duplicate_address_origins(self):
        j,a,b,other,image,ex,model=self.make(duplicate=True,second_null=True)
        rows=ex.rows(j)
        self.assertEqual([a,other],[r["object"] for r in rows if r.get("object")])
        null_section=next(row for row in rows if row["name"]=="Saved slot +0x240")
        self.assertIn("0000:000000000000",null_section["lines"][0])
        rev=ex.rows(other)
        self.assertEqual(1,len([r for r in rev if r.get("object") is j]))
        no_rev=ex.rows(b)
        self.assertEqual("No saved journal slot match",no_rev[-1]["name"])
        self.assertEqual(0,len([r for r in no_rev if r.get("object")]))

    def test_only_complete_eight_byte_address_matches_not_six_byte_suffix(self):
        j,a,b,other,image,ex,model=self.make()
        a.segment.header=NS(owner=InternalAddress(0x0004,0x00572A000000))
        fresh=JournalReceiverExplorer(image,inventory([j,a,b]))
        rows=fresh.rows(j)
        self.assertEqual([b],[r["object"] for r in rows if r.get("object")])
        self.assertIn("0",next(r for r in rows if r["name"]=="Saved slot +0x110")["lines"][2])
        rows=fresh.rows(a)
        self.assertEqual("No saved journal slot match",rows[-1]["name"])

    def test_unsupported_header_truncation_gap_and_reverse_withholding(self):
        j,a,b,other,image,ex,model=self.make()
        raw=journal_bytes(a.segment.header.owner,b.segment.header.owner)
        for bad in (raw[:0x110],raw[:READ_LIMIT-1]):
            with self.assertRaises(ValueError):
                decode_journal_receiver_addresses(bad,type_code="09/01")
        for at in (0x100,0x106):
            bad=bytearray(raw);bad[at]=0xFF
            with self.assertRaises(ValueError):
                decode_journal_receiver_addresses(bad,type_code="09/01")
        j.segment.extents=(NS(start_lba=10,virtual_address=j.segment.virtual_address,pages=1),
                           NS(start_lba=11,virtual_address=j.segment.virtual_address+1024,pages=1))
        fresh=JournalReceiverExplorer(image,inventory([j,a,b]))
        with self.assertRaises(ValueError):
            fresh.rows(j)
        reverse=fresh.rows(a)
        self.assertIn("Unsupported journal source primaries withheld: 1",
                      reverse[0]["lines"][3])
        self.assertEqual("No saved journal slot match",reverse[-1]["name"])
        with self.assertRaises(ValueError):
            fresh.rows(obj("OTHER",(0x19,1)))


if __name__ == "__main__":
    unittest.main()
