import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from as400_dasd import PAGE_SIZE
from as400_dasd_tool import (
    _dlo_preview_strings,
    _load_library_catalog,
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

        qgpl = _tui_library_context("QGPL")
        self.assertIn("General Purpose Library", qgpl)
        self.assertIn("default current library", qgpl)

        qiws = _tui_library_context("QIWS")
        self.assertIn("PC Support/400", qiws)
        self.assertIn("file transfer", qiws)

        qmu400 = _tui_library_context("QMU400")
        self.assertIn("System/36 Migration Assistant", qmu400)

        doc = _tui_object_type_context(0x19, 0x0E)
        self.assertIn("document-library document", doc)
        self.assertIn("user-facing document name may differ", doc)

        member = _tui_object_type_context(0x0D, 0x50)
        self.assertIn("member cursor", member)

    def test_library_catalog_covers_recovered_mark_p02_libraries(self):
        catalog = _load_library_catalog()
        recovered = {
            "#CGULIB",
            "#DBULIB",
            "#DFULIB",
            "#DSULIB",
            "#LIBRARY",
            "#SDALIB",
            "#SEULIB",
            "QDSNX",
            "QGPL",
            "QIWS",
            "QIWS2D",
            "QIWS2S",
            "QIWSFD",
            "QIWSFS",
            "QIWSPD",
            "QIWSPS",
            "QIWSTL",
            "QMGU",
            "QMU400",
            "QPFRDATA",
            "QQALIB",
            "QSDE",
            "QSPL",
            "QSSP",
            "QSYS",
        }
        self.assertTrue(recovered.issubset(catalog))

    def test_library_catalog_can_be_overridden(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "libraries.json"
            path.write_text(
                '{"libraries":{"QGPL":{"description":"Custom QGPL note"}}}',
                encoding="utf-8",
            )
            catalog = _load_library_catalog([path])
            self.assertEqual(
                catalog["QGPL"]["description"],
                "Custom QGPL note",
            )

    def test_dlo_preview_strings_are_forensic_hints(self):
        data = (
            "FMPV082760".encode("cp037")
            + b"\x00\x01"
            + "CKPCSPTH.EXE".encode("cp037")
            + b"\x00"
            + "S1011111".encode("cp037")
        )
        hints = _dlo_preview_strings(
            data,
            internal_name="FMPV082760",
            limit=2,
        )
        self.assertEqual(hints, ["CKPCSPTH.EXE", "S1011111"])

    def test_dlos_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(
            ["dlos", "marks.hda", "--class", "doc", "--strings", "2"]
        )
        self.assertEqual(args.command, "dlos")
        self.assertEqual(args.image, "marks.hda")
        self.assertEqual(args.object_class, "doc")
        self.assertEqual(args.strings, 2)

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
