"""Synthetic independent saved JRNRCV +0x108 parent-address evidence."""
import unittest

from as400_dasd import InternalAddress
from as400_journals import (
    RECEIVER_READ_LIMIT, JournalReceiverExplorer,
    decode_receiver_saved_journal_address)
from test_journal_receiver_workflows import JournalReceiverTests, journal_bytes
from test_type_capabilities import inventory


def receiver_bytes(parent, *, variant=2):
    data = bytearray(512)
    data[0x100] = variant
    data[0x106:0x108] = bytes.fromhex("0001")
    data[0x108:0x110] = parent.to_bytes()
    return data


class ReceiverJournalBackpointerTests(unittest.TestCase):
    def test_both_release_variants_and_exact_full_address(self):
        owner = InternalAddress(0x0130, 0x003394000000)
        for variant in (2,3):
            payload=receiver_bytes(owner,variant=variant)
            self.assertEqual(owner,decode_receiver_saved_journal_address(
                payload,type_code="07/01"))
        for bad in (receiver_bytes(owner)[:RECEIVER_READ_LIMIT-1],
                    b"", receiver_bytes(owner,variant=4)):
            with self.assertRaises(ValueError):
                decode_receiver_saved_journal_address(bad,type_code="07/01")
        bad=receiver_bytes(owner);bad[0x107]=0
        with self.assertRaises(ValueError):
            decode_receiver_saved_journal_address(bad,type_code="07/01")
        with self.assertRaises(ValueError):
            decode_receiver_saved_journal_address(receiver_bytes(owner),type_code="09/01")

    def test_reverse_direct_parent_is_independent_of_journal_side_slots(self):
        source,a,b,other,image,explorer,model=JournalReceiverTests().make()
        journal_owner=source.segment.header.owner
        # Independent saved receiver bytes can refer to a journal even when
        # neither of the two supported journal-side slots still names it.
        empty=journal_bytes(InternalAddress(0,0),InternalAddress(0,0))
        image.pages[10]=empty[:512];image.pages[11]=empty[512:]
        image.pages[a.segment.start_lba]=receiver_bytes(journal_owner,variant=2)
        image.pages[b.segment.start_lba]=receiver_bytes(InternalAddress(0,0),variant=3)
        ex=JournalReceiverExplorer(image,model.inventory)
        rows=ex.rows(a)
        assert any(row["name"]=="No saved journal slot match" for row in rows)
        own=next(row for row in rows if row["name"]=="Receiver-saved journal pointer")
        self.assertIn("exact same owner address: 1",own["lines"][1])
        self.assertEqual([source],[r["object"] for r in rows if r.get("object") is not None])
        jrows=ex.rows(source)
        summary=next(r for r in jrows if r["name"]=="Receiver-owned saved journal pointers")
        self.assertIn("matches this journal: 1",summary["lines"][0])
        self.assertEqual([a],[r["object"] for r in jrows if r.get("object") is not None])

    def test_null_and_wrong_address_extender_never_promoted_to_pointer(self):
        source,a,b,other,image,explorer,model=JournalReceiverTests().make()
        exact=source.segment.header.owner
        bad_extender=InternalAddress(exact.extender+1,exact.address)
        image.pages[a.segment.start_lba]=receiver_bytes(bad_extender)
        image.pages[b.segment.start_lba]=receiver_bytes(InternalAddress(0,0))
        ex=JournalReceiverExplorer(image,model.inventory)
        self.assertIn("exact same owner address: 0",
                      next(r for r in ex.rows(a)
                           if r["name"]=="Receiver-saved journal pointer")["lines"][1])
        self.assertIn("exact same owner address: 0",
                      next(r for r in ex.rows(b)
                           if r["name"]=="Receiver-saved journal pointer")["lines"][1])
        self.assertEqual(0,len(ex._direct_parent_reverse().get(ex._identity(source),())))
        self.assertEqual(0,ex._receiver_direct_withheld)

    def test_unsupported_receiver_is_withheld_not_guessed_missing(self):
        source,a,b,other,image,explorer,model=JournalReceiverTests().make()
        image.pages[a.segment.start_lba]=bytes(512)
        image.pages[b.segment.start_lba]=receiver_bytes(source.segment.header.owner)
        ex=JournalReceiverExplorer(image,model.inventory)
        rows=ex.rows(source)
        info=next(r for r in rows if r["name"]=="Receiver-owned saved journal pointers")
        self.assertIn("withheld due to unsupported primary layouts: 1",info["lines"][1])
        a_rows=ex.rows(a)
        self.assertEqual("Receiver-saved journal pointer unavailable",
                         next(r["name"] for r in a_rows
                              if r["name"]=="Receiver-saved journal pointer unavailable"))
        b_rows=ex.rows(b)
        self.assertEqual(1,len([r for r in b_rows if r.get("object") is source]))


if __name__=="__main__":
    unittest.main()
