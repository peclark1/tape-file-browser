"""Synthetic (non-archival) OUTQ index and Guided navigation regression tests."""
import unittest
from types import SimpleNamespace as NS

from as400_5250 import Guided5250
from as400_outq import (OutputQueueExplorer, decode_output_queue_index,
                       OUTQ_HEADER)
from test_type_capabilities import obj, inventory, Image


def outq_fixture(*, root=0x800, size=1024, control=False):
    data = bytearray(root + size)
    base = 0x100000
    data[0x100:0x106] = OUTQ_HEADER
    data[0x420:0x426] = (base + root).to_bytes(6, "big")
    data[0x42A:0x42E] = size.to_bytes(4, "big")
    key = bytearray(48)
    key[0:8] = bytes.fromhex("c1f300000000003c")
    key[0x20:0x2A] = "*STD".ljust(10).encode("cp037")
    if control:
        key[0:2] = bytes.fromhex("fa0b")
    end = root + 14 + len(key)
    data[root:root+8] = (bytes.fromhex("970008cc") +
                           (size-14-len(key)).to_bytes(2,"big") +
                           end.to_bytes(2,"big"))
    data[root+8:root+14] = bytes([47]) + (root+14).to_bytes(2,"big") + bytes.fromhex("600000")
    data[root+14:end] = key
    return data


class OutputQueueTests(unittest.TestCase):
    def fixture_model(self, data=None):
        item = obj("QPRINT",(0x0E,0x02))
        item.segment.virtual_address = 0x100000
        buf = outq_fixture() if data is None else data
        item.segment.extents = (NS(start_lba=10,
                                   virtual_address=0x100000,
                                   pages=len(buf)//512),)
        inv = inventory([item])
        ex = OutputQueueExplorer(Image([(item,buf)]))
        return item, ex, Guided5250(inv, outq_loader=ex.rows)

    def test_root_size_and_form_observation(self):
        for size, root in ((1024,0x800),(2048,0x1000),(2048,0x1800)):
            found,warn = decode_output_queue_index(outq_fixture(root=root,size=size),0x100000)
            self.assertFalse(warn)
            self.assertEqual(1,len(found))
            self.assertEqual("*STD",found[0].form_candidate)
            self.assertEqual(48,len(found[0].raw))
            self.assertFalse(found[0].control_like)

    def test_control_marker_is_not_a_live_entry(self):
        key,warn = decode_output_queue_index(outq_fixture(control=True),0x100000)
        self.assertTrue(key[0].control_like)
        self.assertIsNone(key[0].form_candidate)
        item,ex,_ = self.fixture_model(outq_fixture(control=True))
        rows = ex.rows(item)
        self.assertIn("control-like 1",rows[0]["lines"][1])
        self.assertEqual(1,len(rows))

    def test_bad_input_and_unsupported_keys(self):
        d = outq_fixture()
        for truncated in (d[:0],d[:256],d[:0x42D]):
            with self.assertRaises(ValueError):
                decode_output_queue_index(truncated,0x100000)
        bad = bytearray(d);bad[0x100] = 0
        with self.assertRaises(ValueError):decode_output_queue_index(bad,0x100000)
        bad = bytearray(d);bad[0x420:0x426] = (0x200000).to_bytes(6,"big")
        with self.assertRaises(ValueError):decode_output_queue_index(bad,0x100000)
        bad = bytearray(d);bad[0x42A:0x42E] = (4096).to_bytes(4,"big")
        with self.assertRaises(ValueError):decode_output_queue_index(bad,0x100000)
        bad = bytearray(d);bad[0x808]=46
        found,warnings = decode_output_queue_index(bad,0x100000)
        self.assertEqual((),found)
        self.assertTrue(any("length 47" in w for w in warnings))
        bad=bytearray(d);bad[0x806:0x808]=(0x810).to_bytes(2,"big")
        found,warnings=decode_output_queue_index(bad,0x100000)
        self.assertFalse(found);self.assertTrue(warnings)

    def test_key_filter_details_and_back(self):
        item,ex,model = self.fixture_model()
        model.run_command("WRKOUTQ OUTQ(QPRINT) KEYHEX(C1) FORM(*STD)")
        self.assertEqual(["Saved OUTQ index","Key 1"],[x["name"] for x in model.rows()])
        model.selected = 1
        model.open_row(1)
        self.assertIn("*STD",model.rows()[0]["lines"][2])
        self.assertEqual(7,len(model.rows()))
        model.back()
        self.assertEqual(1,model.selected)
        model.run_command("WRKOUTQ OUTQ(QPRINT) FORM(OTHER)")
        self.assertEqual(1,len(model.rows()))
        for kwargs in ({"start":-1},{"keyhex":"GG"},{"keyhex":"FF"*49},
                       {"form":"something invalid!"}):
            with self.assertRaises(ValueError):ex.rows(item,**kwargs)
        unknown = ex.entries(item)[0][0]
        with self.assertRaises(ValueError):
            ex.rows(item,entry=NS(raw=unknown.raw,terminal_offset=-1))

    def test_command_is_not_execution(self):
        item,ex,model = self.fixture_model()
        model.run_command("WRKOUTQ OUTQ(*ALL/QPRINT)")
        self.assertEqual("capabilities",model.screen)
        model.run_command("WRKOUTQ OUTQ(QPRINT) KEYHEX(GG)")
        self.assertIn("non-hexadecimal",model.status)
        self.assertIn("not verified spool/job chronology",ex.rows(item)[0]["lines"][2].lower())


if __name__ == "__main__":
    unittest.main()
