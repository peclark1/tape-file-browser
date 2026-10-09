"""Synthetic, non-proprietary fixtures for conservative *CMD evidence display."""
import unittest
from types import SimpleNamespace as NS

from as400_cmd import (
    candidate_processor,
    candidate_command_description,
    command_information_lines,
    embedded_ebcdic_text,
)


class CommandEvidenceTests(unittest.TestCase):
    @staticmethod
    def sample():
        data = bytearray(4096)
        data[0x102:0x10C] = "QTESTPGM".ljust(10).encode("cp037")
        data[0x10C:0x116] = "QTEST".ljust(10).encode("cp037")
        data[0x280:0x280 + len("Synthetic Command")] = (
            "Synthetic Command".encode("cp037")
        )
        data[0x2C0:0x2C0 + len("Example parameter prompt")] = (
            "Example parameter prompt".encode("cp037")
        )
        return bytes(data)

    def test_candidate_processor_is_observational_and_strict(self):
        sample = self.sample()
        self.assertEqual(("QTESTPGM", "QTEST"), candidate_processor(sample))
        self.assertIsNone(candidate_processor(sample[:0x110]))
        invalid = bytearray(sample)
        invalid[0x102:0x10C] = b"\x00" * 10
        self.assertIsNone(candidate_processor(invalid))
        invalid = bytearray(sample)
        invalid[0x10C:0x116] = b"\x00" * 10
        self.assertIsNone(candidate_processor(invalid))

    def test_candidate_description_requires_correlated_anchor_and_exact_name(self):
        data = bytearray(self.sample())
        anchor = "QTESTCMD   *LIBL     TESTCMD"
        title = "Create Sample Command"
        data[0x400:0x400 + len(anchor)] = anchor.encode("cp037")
        data[0x4B8:0x4B8 + len(title)] = title.encode("cp037")
        self.assertEqual(
            title, candidate_command_description(bytes(data), "TESTCMD"))
        self.assertIsNone(
            candidate_command_description(bytes(data), "TEST"))
        data[0x400:0x400 + len(anchor)] = b"\x00" * len(anchor)
        self.assertIsNone(
            candidate_command_description(bytes(data), "TESTCMD"))
        # The original recovered bytes are not replaced with the heuristic.
        self.assertEqual(self.sample(), self.sample())

    def test_bounded_text_scan_preserves_primary_byte_offsets(self):
        sample = self.sample()
        found = embedded_ebcdic_text(sample)
        self.assertIn((0x280, "Synthetic Command"), found)
        self.assertIn((0x2C0, "Example parameter prompt"), found)
        self.assertEqual((), embedded_ebcdic_text(sample, scan_bytes=0))
        self.assertEqual((), embedded_ebcdic_text(sample, max_items=0))
        self.assertEqual(1, len(embedded_ebcdic_text(sample, max_items=1)))
        self.assertNotIn((0x2C0, "Example parameter prompt"),
                         embedded_ebcdic_text(sample, scan_bytes=0x2C0))
        # Binary bytes are not treated as free-form text.
        self.assertFalse(embedded_ebcdic_text(b"\x00" * 2000))

    def test_evidence_screen_declines_to_invent_parameter_meanings(self):
        obj = NS(name="TESTCMD", library_name="TESTLIB",
                 segment=NS(virtual_address=0x123400, start_lba=321, pages=5))
        lines = command_information_lines(obj, self.sample())
        screen = "\n".join(lines)
        self.assertIn("TESTLIB", screen)
        self.assertIn("*CMD (MI 19/05)", screen)
        self.assertIn("0x102 PGM text : QTESTPGM", screen)
        self.assertIn("0x10C LIB text : QTEST", screen)
        self.assertIn("Synthetic Command", screen)
        self.assertIn("Parameters         : Not yet structurally decoded", screen)
        self.assertIn("NOT verified command parameters", screen)

    def test_short_data_does_not_create_processor_or_fake_help(self):
        obj = NS(name="EMPTY", library_name=None,
                 segment=NS(virtual_address=0, start_lba=0, pages=1))
        lines = command_information_lines(obj, bytes(100))
        screen = "\n".join(lines)
        self.assertNotIn("Candidate processor names", screen)
        self.assertIn("No qualifying text", screen)
        self.assertIn("<orphan>", screen)


if __name__ == "__main__":
    unittest.main()
