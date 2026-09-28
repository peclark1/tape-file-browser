import io
import struct
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from tape_formats import EOM, TMK, convert_tape
from tape_text import format_ebcdic, format_hex
from tape_tool import _picker_entries, main


def write_simh(path, files):
    with open(path, "wb") as handle:
        for records in files:
            for data in records:
                word = len(data)
                handle.write(struct.pack("<I", word))
                handle.write(data)
                if len(data) & 1:
                    handle.write(b"\x00")
                handle.write(struct.pack("<I", word))
            handle.write(struct.pack("<I", TMK))
        handle.write(struct.pack("<I", EOM))


class TapeToolTests(unittest.TestCase):
    def test_text_formatters(self):
        data = "VOL1TEST".encode("cp037")
        self.assertIn("VOL1TEST", format_ebcdic(data))
        dump = format_hex(data)
        self.assertIn("E5 D6 D3 F1", dump)
        self.assertIn("|VOL1TEST|", dump)

    def test_info_files_records_and_show(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "sample.tap"
            write_simh(
                image,
                [
                    ["VOL1VOL01".encode("cp037"), b"\x00\x01\x02"],
                    ["HDR1TEST".encode("cp037")],
                ],
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = main(["info", str(image), "--hash"])
            self.assertEqual(rc, 0)
            self.assertIn("Format:        SIMH", stdout.getvalue())
            self.assertIn("Logical files: 2", stdout.getvalue())
            self.assertIn("Logical SHA-256:", stdout.getvalue())

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = main(["files", str(image)])
            self.assertEqual(rc, 0)
            self.assertIn("File 0: 2 records", stdout.getvalue())
            self.assertIn("File 1: 1 records", stdout.getvalue())

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = main(["records", str(image), "--file", "0"])
            self.assertEqual(rc, 0)
            self.assertIn("Record 1:", stdout.getvalue())
            self.assertIn("Record 2:", stdout.getvalue())

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = main(
                    [
                        "show",
                        str(image),
                        "--file",
                        "0",
                        "--record",
                        "1",
                        "--view",
                        "both",
                    ]
                )
            self.assertEqual(rc, 0)
            self.assertIn("VOL1VOL01", stdout.getvalue())
            self.assertIn("HEX:", stdout.getvalue())

    def test_convert_and_compare(self):
        with tempfile.TemporaryDirectory() as directory:
            tap = Path(directory) / "sample.tap"
            aws = Path(directory) / "sample.aws"
            write_simh(tap, [[b"first", b"second"], [b"third"]])

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = main(["convert", str(tap), str(aws)])
            self.assertEqual(rc, 0)
            self.assertTrue(aws.exists())
            self.assertIn("verified", stdout.getvalue().lower())

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = main(["compare", str(tap), str(aws)])
            self.assertEqual(rc, 0)
            self.assertIn(
                "All selected tape images are logically identical.",
                stdout.getvalue(),
            )


    def test_compare_multiple_images_and_require_two(self):
        with tempfile.TemporaryDirectory() as directory:
            tap = Path(directory) / "sample.tap"
            aws1 = Path(directory) / "sample1.aws"
            aws2 = Path(directory) / "sample2.aws"
            write_simh(tap, [[b"first", b"second"], [b"third"]])
            convert_tape(tap, aws1)
            convert_tape(tap, aws2)

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = main(
                    ["compare", str(tap), str(aws1), str(aws2)]
                )
            self.assertEqual(rc, 0)
            self.assertEqual(stdout.getvalue().count("IDENTICAL"), 2)

            stderr = io.StringIO()
            with redirect_stderr(stderr):
                rc = main(["compare", str(tap)])
            self.assertEqual(rc, 1)
            self.assertIn("at least two", stderr.getvalue())

    def test_picker_includes_parent_directory_first(self):
        with tempfile.TemporaryDirectory() as directory:
            child = Path(directory) / "child"
            child.mkdir()
            (child / "sample.tap").write_bytes(b"")

            entries = _picker_entries(child)
            self.assertTrue(entries)
            self.assertEqual(entries[0], (child.parent.resolve(), True))
            self.assertIn((child / "sample.tap", False), entries)

    def test_missing_file_number_returns_error(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "sample.tap"
            write_simh(image, [[b"only"]])

            stderr = io.StringIO()
            with redirect_stderr(stderr):
                rc = main(["records", str(image), "--file", "99"])
            self.assertEqual(rc, 1)
            self.assertIn("does not exist", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
