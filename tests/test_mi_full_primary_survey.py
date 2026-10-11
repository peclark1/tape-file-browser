"""Synthetic validation of full MI primary signature scans, including unknown types."""
import io
import json
import tempfile
from pathlib import Path
import unittest
import zipfile

from tools.mi_full_primary_survey import candidate_primary, open_image, survey


def fake_sector(code, name, tag, *, bad_pages=False):
    page = bytearray(512)
    page[0] = 1
    page[1] = tag
    page[2:4] = b"\x00\x00" if bad_pages else (3).to_bytes(2, "big")
    page[0x20:0x22] = b"\x80\x00"
    page[0x22:0x24] = bytes.fromhex(code)
    page[0x24:0x42] = name.ljust(30).encode("cp037")
    return b"\x00" * 8 + bytes(page)


class FullMISurveyTests(unittest.TestCase):
    def test_arbitrary_codes_and_group_variants_not_hardcoded_to_cmd(self):
        stream = b"".join([
            fake_sector("0201", "PGMTEST", 0x81),
            fake_sector("0201", "PGMTEST", 0x82),
            fake_sector("0201", "PGMTEST", 0x89),
            fake_sector("0201", "OTHERPGM", 0x91),
            fake_sector("19ED", "UNKNOWN", 0x80),
            fake_sector("0E00", "UNKNOWN2", 0x90),
            fake_sector("19D4", "RECOVERY", 0x80),
        ])
        report = survey(io.BytesIO(stream), chunk_sectors=2)
        self.assertEqual(7, report["candidate_primary_pages"])
        self.assertEqual(4, report["distinct_mi_codes_observed"])
        self.assertEqual(4, report["by_type"]["0201"]["physical_primary_candidates"])
        self.assertEqual(2, report["by_type"]["0201"]["distinct_name_strings"])
        self.assertEqual({"81":1, "82":1, "89":1, "91":1},
                         report["by_type"]["0201"]["segment_group_variants"])
        self.assertEqual(1, report["by_type"]["19ED"]["physical_primary_candidates"])
        self.assertNotIn("PGMTEST", json.dumps(report))
        self.assertNotIn("RECOVERY", json.dumps(report))

    def test_corrupt_and_false_positive_signature_do_not_become_counts(self):
        valid = fake_sector("1905", "HELLO", 0x89)
        bad = bytearray(valid)
        bad[8 + 0x20] = 0
        no_pages = fake_sector("1905", "HELLO", 0x89, bad_pages=True)
        invalid_name = bytearray(valid)
        invalid_name[8 + 0x24:8 + 0x42] = b"\x00" * 30
        self.assertIsNone(candidate_primary(bytes(bad)))
        self.assertIsNone(candidate_primary(no_pages))
        self.assertIsNone(candidate_primary(bytes(invalid_name)))
        report = survey(io.BytesIO(
            valid + bytes(bad) + no_pages + bytes(invalid_name)),
            chunk_sectors=1)
        self.assertEqual(1, report["candidate_primary_pages"])
        self.assertEqual(1, report["near_candidate_rejections"]["zero_declared_pages"])
        self.assertEqual(1, report["near_candidate_rejections"]["invalid_ebcdic_name"])
        self.assertIsNone(candidate_primary(valid[:300]))
        with self.assertRaises(ValueError):
            survey(io.BytesIO(valid + b"tail"))

    def test_plain_and_zip_input_read_only(self):
        raw = fake_sector("0E03", "MESSAGES", 0x90)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hda = root / "test.hda"
            hda.write_bytes(raw)
            with open_image(hda) as stream:
                self.assertEqual(1, survey(stream)["candidate_primary_pages"])
            zip_path = root / "test.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("one.hda", raw)
            with open_image(zip_path) as stream:
                self.assertEqual(1, survey(stream)["candidate_primary_pages"])
            self.assertEqual(raw, hda.read_bytes())
            bad = root / "bad.zip"
            with zipfile.ZipFile(bad, "w") as zf:
                zf.writestr("one.hda", raw)
                zf.writestr("two.hda", raw)
            with self.assertRaises(ValueError):
                with open_image(bad):
                    pass


if __name__ == "__main__":
    unittest.main()
