import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from as400_dasd import PAGE_SIZE
from as400_dasd_tool import (
    _tui_library_context,
    _tui_object_type_context,
    build_parser,
    main,
)


def make_header(address, order=0):
    page_number = address >> 9
    page_word = page_number << 1
    return page_word.to_bytes(5, "big") + bytes([order, 0, 0])


def write_simple_image(path):
    # Storage-map behavior is covered by the real header-only regression
    # fixture in test_as400_dasd.py.
    with open(path, "wb") as handle:
        for i in range(12):
            handle.write(make_header(0x100000 + i * PAGE_SIZE))
            handle.write(
                ("QGPL TEST%02d" % i)
                .encode("cp037")
                .ljust(PAGE_SIZE, b"\x40")
            )


class DASDToolTests(unittest.TestCase):
    def test_info_and_sector(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "sample.hda"
            write_simple_image(image)

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = main(["info", str(image)])
            self.assertEqual(rc, 0)
            self.assertIn("Sector size:   520 bytes", stdout.getvalue())
            self.assertIn("Sector count:  12", stdout.getvalue())

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = main(
                    ["sector", str(image), "0", "--hex-bytes", "32"]
                )
            self.assertEqual(rc, 0)
            text = stdout.getvalue()
            self.assertIn(
                "virtual byte address:     0x000000100000", text
            )
            self.assertIn("QGPL TEST00", text)



    def test_tui_context_describes_known_as400_roles(self):
        qdoc = _tui_library_context("QDOC")
        self.assertIn("QDLS", qdoc)
        self.assertIn("not a source library", qdoc)

        doc = _tui_object_type_context(0x19, 0x0E)
        self.assertIn("document-library document", doc)
        self.assertIn("user-facing document name may differ", doc)

        member = _tui_object_type_context(0x0D, 0x50)
        self.assertIn("member cursor", member)

    def test_browse_subcommand_accepts_optional_image(self):
        parser = build_parser()

        args = parser.parse_args(["browse"])
        self.assertEqual(args.command, "browse")
        self.assertIsNone(args.image)

        args = parser.parse_args(["browse", "marks.hda"])
        self.assertEqual(args.command, "browse")
        self.assertEqual(args.image, "marks.hda")

    def test_bad_image_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "bad.hda"
            image.write_bytes(b"bad")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                rc = main(["info", str(image)])
            self.assertEqual(rc, 1)
            self.assertIn("not divisible", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
