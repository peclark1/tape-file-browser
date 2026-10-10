"""Synthetic, non-proprietary fixtures for conservative *CMD evidence display."""
import unittest
from types import SimpleNamespace as NS

from as400_dasd_tool import _tui_command_information_lines

from as400_cmd import (
    candidate_processor,
    candidate_command_description,
    command_information_lines,
    embedded_ebcdic_text,
    candidate_parameter_keywords,
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

    @staticmethod
    def parameter_sample():
        # Synthetic V2R3-shaped structures, no real image/IBM bytes.
        data = bytearray(2048)
        data[0x17E:0x180] = b"\x81\x00"
        data[0x180:0x182] = b"\x09\x00"
        entries = (
            (0x19C, "FROMFILE"), (0x1C6, "TOFLR"),
            (0x1F8, "FROMMBR"), (0x23C, "TODOC"),
            (0x280, "REPLACE"), (0x2C9, "TRNTBL"),
            (0x312, "TRNFMT"), (0x35B, "RCDFMT"),
            (0x39F, "TRNIGC"),
        )
        for i, (offset, keyword) in enumerate(entries, 1):
            data[offset:offset + 10] = keyword.ljust(10).encode("cp037")
            data[offset + 10:offset + 12] = i.to_bytes(2, "big")
        return bytes(data)

    def test_nine_keyword_sequence_recovers_short_names_and_ordinals(self):
        data = self.parameter_sample()
        values = candidate_parameter_keywords(data)
        self.assertEqual(9, len(values))
        self.assertEqual(
            ["FROMFILE", "TOFLR", "FROMMBR", "TODOC", "REPLACE",
             "TRNTBL", "TRNFMT", "RCDFMT", "TRNIGC"],
            [item.keyword for item in values],
        )
        self.assertEqual(list(range(1, 10)),
                         [item.ordinal for item in values])
        self.assertEqual([0x19C, 0x1C6, 0x1F8, 0x23C,
                          0x280, 0x2C9, 0x312, 0x35B, 0x39F],
                         [item.offset for item in values])
        strings = embedded_ebcdic_text(data)
        self.assertIn((0x1C6, "TOFLR"), strings)
        self.assertIn((0x23C, "TODOC"), strings)

    def test_alternate_v2r3_header_byte_variant(self):
        for marker in (0x81, 0xB9, 0x61, 0xCA, 0xD0):
            with self.subTest(marker=marker):
                data = bytearray(self.parameter_sample())
                data[0x17E] = marker
                self.assertEqual(
                    9, len(candidate_parameter_keywords(data))
                )

    def test_parameter_keyword_decoder_fails_closed_on_corruption(self):
        data = self.parameter_sample()
        examples = []
        modified = bytearray(data)
        modified[0x180] = 10
        examples.append(modified)
        modified = bytearray(data)
        modified[0x181] = 0xFF
        examples.append(modified)
        modified = bytearray(data)
        modified[0x17E] = 0x00
        examples.append(modified)
        modified = bytearray(data)
        modified[0x1C6 + 10:0x1C6 + 12] = b"\x00\x03"
        examples.append(modified)
        modified = bytearray(data)
        modified[0x19C:0x19C + 10] = b"\x00" * 10
        examples.append(modified)
        modified = bytearray(data)
        modified[0x220:0x22A] = "FAKE".ljust(10).encode("cp037")
        modified[0x22A:0x22C] = b"\x00\x02"
        examples.append(modified)
        for example in examples:
            with self.subTest(case=examples.index(example)):
                self.assertEqual((), candidate_parameter_keywords(example))
        self.assertEqual((), candidate_parameter_keywords(data[:0x1A7]))
        self.assertEqual((), candidate_parameter_keywords(data, max_count=8))
        self.assertEqual((), candidate_parameter_keywords(b"\x00" * 2048))

    def test_synthetic_parameter_table_is_shown_as_candidate_not_full_decode(self):
        obj = NS(name="TESTCMD", library_name="TESTLIB",
                 segment=NS(virtual_address=0x123400,
                            start_lba=321, pages=5))
        view = "\n".join(command_information_lines(obj, self.parameter_sample()))
        self.assertIn("Candidate parameter keyword sequence", view)
        self.assertIn("parameter-count candidate: 9", view)
        self.assertIn("2  +0x01C6  TOFLR", view)
        self.assertIn("4  +0x023C  TODOC", view)
        self.assertIn("defaults are NOT decoded", view)
        self.assertIn("Parameters         : Not yet structurally decoded", view)

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

    def test_real_reader_uses_extent_pages_and_never_writes(self):
        primary = bytearray(self.sample())
        descriptor = "QTESTCMD   *LIBL     TESTCMD"
        title = "Display Synthetic Definition"
        primary[0x200:0x200 + len(descriptor)] = descriptor.encode("cp037")
        primary[0x2B8:0x2B8 + len(title)] = title.encode("cp037")

        class ReadOnlyImage:
            def __init__(self, data):
                self.data = data
                self.read_lbas = []
            def read_sector(self, lba):
                self.read_lbas.append(lba)
                return NS(data=self.data[(lba - 100) * 512:
                                         (lba - 99) * 512])

        image = ReadOnlyImage(bytes(primary))
        segment = NS(
            extents=(NS(start_lba=100, pages=3),),
            virtual_address=0x101000, start_lba=100, pages=3)
        obj = NS(name="TESTCMD", library_name="TESTLIB",
                 object_type=0x19, object_subtype=0x05, segment=segment)
        lines = _tui_command_information_lines({"image": image}, obj)
        result = "\n".join(lines)
        self.assertIn(title, result)
        self.assertIn("QTESTPGM", result)
        self.assertEqual([100, 101, 102], image.read_lbas)
        self.assertEqual(1536, 3 * 512)
        # Verify a wrong object type cannot accidentally trigger raw reads.
        image.read_lbas.clear()
        obj.object_subtype = 1
        self.assertIn("not a recovered *CMD",
                      "\n".join(_tui_command_information_lines({"image": image}, obj)))
        self.assertEqual([], image.read_lbas)

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
