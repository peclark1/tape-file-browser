"""Synthetic offline CNVTBL 256-pair navigation and defensive layout tests."""
import unittest
from types import SimpleNamespace as NS

from as400_cnvtbl import (ENTRY_COUNT, TABLE_END, SavedConversionExplorer,
                         decode_cnvtbl)
from as400_5250 import Guided5250, parse_command
from test_type_capabilities import Image, inventory, obj


def fixture(variant=1, *, changed=()):
    data = bytearray(1024)
    data[0x100:0x102] = variant.to_bytes(2, "big")
    for i in range(ENTRY_COUNT):
        data[0x102 + i * 2:0x104 + i * 2] = bytes((i, 0))
    for i in changed:
        data[0x102 + i * 2:0x104 + i * 2] = bytes((i, 0x40))
    return data


class CNVTBLTests(unittest.TestCase):
    def setup(self):
        a = obj("TBT61Q037A94A3Q", (0x19, 0xFB), 10, "QSYS")
        b = obj("TBT61Q273A94A3Q", (0x19, 0xFB), 20, None)
        c = obj("TBT61Q277A94A3Q", (0x19, 0xFB), 30, "QSYS")
        inv = inventory([a, b, c])
        ex = SavedConversionExplorer(
            Image([(a, fixture()), (b, fixture()), (c, fixture(2, changed=(127, 255)))]),
            inv)
        model = Guided5250(inv, conversion_loader=ex.rows)
        return a, b, c, ex, model

    def test_pair_boundaries_variants_and_rejections(self):
        table = decode_cnvtbl(fixture(1), type_code="19/FB")
        self.assertEqual(256, len(table.entries))
        self.assertEqual(b"\x00\x00", table.entries[0])
        self.assertEqual(b"\x7f\x00", table.entries[127])
        self.assertEqual(b"\x80\x00", table.entries[128])
        self.assertEqual(b"\xff\x00", table.entries[255])
        self.assertEqual(2, decode_cnvtbl(fixture(2), type_code="19/FB").raw_variant)
        for size in (0, 0x100, TABLE_END - 1):
            with self.assertRaises(ValueError):
                decode_cnvtbl(fixture()[:size], type_code="19/FB")
        for variant in (0, 3, 256):
            with self.assertRaises(ValueError):
                decode_cnvtbl(fixture(variant), type_code="19/FB")
        with self.assertRaises(ValueError):
            decode_cnvtbl(fixture(), type_code="19/06")

    def test_command_slot_paging_comparison_and_back(self):
        a, b, c, ex, model = self.setup()
        self.assertEqual(("DSPCNVTBL", {"CNVTBL": a.name, "POS": "128"}),
                         parse_command(f"DSPCNVTBL CNVTBL({a.name}) POS(128)"))
        self.assertTrue(model.run_command(f"DSPCNVTBL CNVTBL({a.name})"))
        rows = model.rows()
        self.assertEqual("Saved CNVTBL paired positions", rows[0]["name"])
        self.assertIn("Exact 512-byte saved-entry matches: 1", rows[0]["lines"][5])
        self.assertTrue(any(r.get("object") is b and "0/256" in r["note"] for r in rows))
        self.assertTrue(any(r.get("object") is c and "2/256" in r["note"] for r in rows))
        next_i = next(i for i, row in enumerate(rows) if row["name"] == "Next 32 positions")
        model.selected = next_i
        model.open_row(next_i)
        self.assertIn("Showing 33..64", model.rows()[0]["lines"][3])
        model.back()
        self.assertEqual(next_i, model.selected)
        self.assertTrue(model.run_command(f"DSPCNVTBL CNVTBL({a.name}) POS(128)"))
        self.assertEqual("Saved position 128 (0x7F)", model.rows()[0]["name"])
        self.assertIn("+0x200", model.rows()[0]["lines"][2])
        self.assertEqual("Exact saved pair: 7F 00", model.rows()[0]["lines"][3])
        self.assertTrue(model.run_command(f"DSPCNVTBL CNVTBL({a.name}) POS(256)"))
        self.assertIn("+0x300", model.rows()[0]["lines"][2])

    def test_peers_selection_duplicates_and_navigation(self):
        a, b, c, ex, model = self.setup()
        self.assertTrue(model.run_command("DSPCNVTBL CNVTBL(*ALL/*)"))
        self.assertEqual("type_objects", model.screen)
        item = next(i for i, row in enumerate(model.rows()) if row.get("object") is a)
        model.selected = item; model.open_row(item)
        self.assertEqual("Saved CNVTBL paired positions", model.rows()[0]["name"])
        link = next(i for i, row in enumerate(model.rows()) if row.get("object") is c)
        model.selected = link; model.open_row(link)
        self.assertIn("Raw +0x100 variant 0x0002", model.rows()[0]["lines"][1])
        model.back()
        self.assertEqual(link, model.selected)
        model.back()
        self.assertEqual(item, model.selected)

    def test_invalid_position_and_virtual_gap_withheld_not_replaced(self):
        a, b, c, ex, model = self.setup()
        for command in (f"DSPCNVTBL CNVTBL({a.name}) POS(0)",
                        f"DSPCNVTBL CNVTBL({a.name}) POS(257)",
                        f"DSPCNVTBL CNVTBL({a.name}) POS(abc)"):
            self.assertFalse(model.run_command(command))
        for invalid in (-1, 1, 225, 256):
            with self.assertRaises(ValueError):
                ex.rows(a, start=invalid)
        b.segment.extents = (NS(start_lba=20, virtual_address=b.segment.virtual_address,
                                pages=1), NS(start_lba=21,
                                virtual_address=b.segment.virtual_address + 1024,
                                pages=1))
        fresh = SavedConversionExplorer(ex.image, inventory([a, b, c]))
        rows = fresh.rows(a)
        self.assertIn("withheld: 1", rows[0]["lines"][4])
        with self.assertRaises(ValueError):
            fresh.rows(b)
        self.assertFalse(any(row.get("object") is b for row in rows))


if __name__ == "__main__":
    unittest.main()
