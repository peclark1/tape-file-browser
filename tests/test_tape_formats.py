import struct
import tempfile
import unittest
from pathlib import Path

from tape_formats import (
    AWS_MAX_CHUNK,
    EOM,
    ERR,
    GAP,
    TMK,
    AwsTapeImage,
    SimhTapeImage,
    convert_tape,
    verify_logical_tapes,
)


def write_simh(
    path,
    files,
    *,
    error_first=False,
    gap_after_first=False,
    eom=True,
    trailing_mark=True,
):
    with open(path, "wb") as handle:
        first_record = True
        for file_index, records in enumerate(files):
            for record_index, data in enumerate(records):
                word = len(data)
                if error_first and first_record:
                    word |= ERR
                first_record = False
                handle.write(struct.pack("<I", word))
                handle.write(data)
                if len(data) & 1:
                    handle.write(b"\x00")
                handle.write(struct.pack("<I", word))
                if gap_after_first and file_index == 0 and record_index == 0:
                    handle.write(struct.pack("<I", GAP))

            if trailing_mark or file_index < len(files) - 1:
                handle.write(struct.pack("<I", TMK))

        if eom:
            handle.write(struct.pack("<I", EOM))


class TapeFormatTests(unittest.TestCase):
    def test_simh_to_aws_and_back(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sample.tap"
            aws = Path(directory) / "sample.aws"
            roundtrip = Path(directory) / "roundtrip.tap"
            files = [
                [b"ABC", bytes(range(32)), b"VOL1".ljust(80, b" ")],
                [b"xyz" * 100, b"last-record"],
            ]
            write_simh(source, files)

            report = convert_tape(source, aws)
            self.assertTrue(report.verified)
            self.assertEqual(report.records, 5)
            self.assertEqual(report.tape_marks, 2)
            self.assertFalse(report.warnings)

            source_image = SimhTapeImage(source)
            aws_image = AwsTapeImage(aws)
            verify_logical_tapes(source_image, aws_image)

            report2 = convert_tape(aws, roundtrip)
            self.assertTrue(report2.verified)
            roundtrip_image = SimhTapeImage(roundtrip)
            verify_logical_tapes(source_image, roundtrip_image)

    def test_error_and_gap_generate_aws_warnings(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "warnings.tap"
            aws = Path(directory) / "warnings.aws"
            write_simh(
                source,
                [[b"first", b"second"]],
                error_first=True,
                gap_after_first=True,
            )

            report = convert_tape(source, aws)
            warnings = "\n".join(report.warnings)
            self.assertIn("error-record", warnings)
            self.assertIn("gap marker", warnings)
            self.assertTrue(report.verified)

    def test_large_record_uses_multichunk_aws(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "large.tap"
            aws = Path(directory) / "large.aws"
            payload = bytes(i % 251 for i in range(AWS_MAX_CHUNK + 1234))
            write_simh(source, [[payload]])

            report = convert_tape(source, aws)
            self.assertTrue(report.verified)
            self.assertTrue(any("multi-chunk" in warning for warning in report.warnings))

            image = AwsTapeImage(aws)
            self.assertEqual(image.files[0].records[0].length, len(payload))
            self.assertEqual(image.read_record(image.files[0].records[0]), payload)

    def test_aws_without_trailing_mark(self):
        with tempfile.TemporaryDirectory() as directory:
            aws = Path(directory) / "no-mark.aws"
            payload = b"hello"
            with open(aws, "wb") as handle:
                handle.write(struct.pack("<HHBB", len(payload), 0, 0xA0, 0))
                handle.write(payload)

            image = AwsTapeImage(aws)
            self.assertEqual(len(image.files), 1)
            self.assertEqual(image.tape_mark_count, 0)
            self.assertEqual(image.read_record(image.files[0].records[0]), payload)


if __name__ == "__main__":
    unittest.main()
