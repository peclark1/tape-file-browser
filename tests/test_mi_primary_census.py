"""Synthetic tests for read-only CISC physical candidate counting."""
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.mi_primary_census import KNOWN, census, open_hda, primary_candidate


def sector(code, name, *, variant=None):
    code = code.upper()
    group = variant if variant is not None else min(KNOWN[code][1])
    page = bytearray(512)
    page[0] = 1
    page[1] = group
    page[2:4] = (8).to_bytes(2, "big")
    page[0x20:0x22] = b"\x80\x00"
    page[0x22:0x24] = bytes.fromhex(code)
    page[0x24:0x42] = name.ljust(30).encode("cp037")
    return b"\x00" * 8 + bytes(page)


class PrimaryCensusTests(unittest.TestCase):
    def test_all_four_variants_and_distinct_names(self):
        data = b"".join([
            sector("1905", "CRTEXAMPLE"),
            sector("1905", "CRTEXAMPLE"),
            sector("1916", "TESTMENU", variant=0x81),
            sector("1916", "OLDMENU", variant=0x80),
            sector("0E03", "TESTMSGF", variant=0x90),
            sector("0201", "TESTPGM", variant=0x89),
            sector("0201", "TESTPGM", variant=0x81),
        ])
        got = census(io.BytesIO(data), chunk_sectors=2)
        self.assertEqual(7, got["input_sectors"])
        results = got["results"]
        self.assertEqual(2, results["1905"]["primary_candidates"])
        self.assertEqual(1, results["1905"]["distinct_primary_names"])
        self.assertEqual(2, results["1916"]["distinct_primary_names"])
        self.assertEqual({"80": 1, "81": 1},
                         results["1916"]["segment_group_variants"])
        self.assertEqual(1, results["0E03"]["primary_candidates"])
        self.assertEqual(2, results["0201"]["primary_candidates"])
        self.assertNotIn("CRTEXAMPLE", json.dumps(got))

    def test_rejects_false_positives_and_truncation(self):
        good = sector("1905", "GOOD")
        self.assertEqual(("1905", "GOOD", 0x89),
                         primary_candidate(good[8:]))
        corrupt = bytearray(good)
        corrupt[8 + 0x20] = 0
        self.assertIsNone(primary_candidate(bytes(corrupt[8:])))
        corrupt = bytearray(good)
        corrupt[8 + 1] = 0x90
        self.assertIsNone(primary_candidate(bytes(corrupt[8:])))
        corrupt = bytearray(good)
        corrupt[8 + 2:8 + 4] = b"\x00\x00"
        self.assertIsNone(primary_candidate(bytes(corrupt[8:])))
        corrupt = bytearray(good)
        corrupt[8 + 0x24:8 + 0x42] = b"\x00" * 30
        self.assertIsNone(primary_candidate(bytes(corrupt[8:])))
        self.assertIsNone(primary_candidate(good[:300]))
        with self.assertRaises(ValueError):
            census(io.BytesIO(good + b"\x00"))

    def test_plain_hda_and_single_member_zip(self):
        data = sector("0E03", "MSGTEST")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plain = root / "test.hda"
            plain.write_bytes(data)
            with open_hda(plain) as stream:
                self.assertEqual(
                    1, census(stream)["results"]["0E03"]["primary_candidates"]
                )
            compressed = root / "test.zip"
            with zipfile.ZipFile(compressed, "w") as zf:
                zf.writestr("image.hda", data)
            with open_hda(compressed) as stream:
                self.assertEqual(
                    1, census(stream)["results"]["0E03"]["primary_candidates"]
                )
            invalid = root / "multiple.zip"
            with zipfile.ZipFile(invalid, "w") as zf:
                zf.writestr("first.hda", data)
                zf.writestr("second.hda", data)
            with self.assertRaises(ValueError):
                with open_hda(invalid):
                    pass


if __name__ == "__main__":
    unittest.main()
