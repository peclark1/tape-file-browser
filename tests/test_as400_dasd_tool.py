import io
import tempfile
import unittest
from types import SimpleNamespace
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from as400_dasd import PAGE_SIZE
from as400_dasd_tool import (
    _DLO_MODEL_FILES,
    _DLO_RUNTIME_INDEX_FILES,
    _dlo_export_pair,
    _dlo_filename_hint,
    _dlo_schema_descriptor_layout,
    _dlo_schema_marker_evidence,
    _dlo_preview_strings,
    _find_byte_occurrences,
    _load_library_catalog,
    _qaosss14_path,
    _qaosss14_unresolved_parent_records,
    _scan_ebcdic_sysobjnam,
    _tui_context_lines,
    _tui_library_context,
    _tui_object_type_context,
    _tui_viewer_target,
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

        docbss = _tui_object_type_context(0x06, 0xC1)
        self.assertIn("*DOCBSS", docbss)
        self.assertIn("Document byte string space", docbss)

        oirs = _tui_object_type_context(0x19, 0x52)
        self.assertIn("*OIRS", oirs)
        self.assertIn("Object Information Repository", oirs)

        qdidx = _tui_object_type_context(0x0E, 0x90)
        self.assertIn("*QDIDX", qdidx)
        self.assertIn("*OIRS", qdidx)

    def test_tui_detail_target_follows_focused_hierarchy_level(self):
        state = {
            "focus": 0,
            "left_items": [{"kind": "library", "label": "QGPL"}],
            "left_index": 0,
            "mid_items": [{"kind": "file", "label": "QCLSRC"}],
            "mid_index": 0,
            "right_items": [{"kind": "member", "label": "REFRESH2"}],
            "right_index": 0,
        }
        self.assertEqual(_tui_viewer_target(state), "left")
        state["focus"] = 1
        self.assertEqual(_tui_viewer_target(state), "mid")
        state["focus"] = 2
        self.assertEqual(_tui_viewer_target(state), "right")
        state["focus"] = 3
        self.assertEqual(_tui_viewer_target(state), "right")

        state["right_items"] = []
        self.assertEqual(_tui_viewer_target(state), "mid")
        state["mid_items"] = []
        self.assertEqual(_tui_viewer_target(state), "left")

    def test_tui_keeps_context_for_library_file_and_member_visible(self):
        member = SimpleNamespace(
            member_file_name="QCLSRC",
            member_name="REFRESH2",
        )
        state = {
            "left_items": [
                {
                    "kind": "library",
                    "library": "QGPL",
                    "label": "QGPL",
                }
            ],
            "left_index": 0,
            "mid_items": [
                {
                    "kind": "file",
                    "name": "QCLSRC",
                    "members": [member],
                    "label": "QCLSRC",
                }
            ],
            "mid_index": 0,
            "right_items": [
                {
                    "kind": "member",
                    "object": member,
                    "source_type": "CLP",
                    "label": "REFRESH2",
                }
            ],
            "right_index": 0,
        }

        library_line, file_line, member_line = _tui_context_lines(state)
        self.assertIn("QGPL", library_line)
        self.assertIn("General Purpose Library", library_line)
        self.assertIn("QCLSRC", file_line)
        self.assertIn("*FILE", file_line)
        self.assertIn("REFRESH2", member_line)
        self.assertIn("*MEM", member_line)

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

    def test_library_catalog_has_categories_and_evidence_status(self):
        catalog = _load_library_catalog()
        self.assertEqual(catalog["QGPL"]["category"], "Core System")
        self.assertEqual(catalog["QGPL"]["status"], "documented")
        self.assertEqual(catalog["QFNTCPL"]["category"], "Printing & Graphics")
        self.assertEqual(catalog["QSDE"]["status"], "research-pending")
        self.assertEqual(catalog["QSYSV2R2M0"]["status"], "inferred")

        qgpl = _tui_library_context("QGPL")
        self.assertIn("[Core System]", qgpl)

        qsde = _tui_library_context("QSDE")
        self.assertIn("Unresolved", qsde)
        self.assertIn("research-pending", qsde)

    def test_library_catalog_can_be_overridden_by_field(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base.json"
            override = Path(directory) / "override.json"
            base.write_text(
                (
                    '{"libraries":{"QGPL":{'
                    '"description":"Base QGPL note",'
                    '"category":"Core System",'
                    '"status":"documented"}}}'
                ),
                encoding="utf-8",
            )
            override.write_text(
                '{"libraries":{"QGPL":{"description":"Custom QGPL note"}}}',
                encoding="utf-8",
            )
            catalog = _load_library_catalog([base, override])
            self.assertEqual(
                catalog["QGPL"]["description"],
                "Custom QGPL note",
            )
            self.assertEqual(catalog["QGPL"]["category"], "Core System")
            self.assertEqual(catalog["QGPL"]["status"], "documented")

    def test_scan_ebcdic_sysobjnam_matches_exact_ten_byte_names(self):
        targets = {
            "FMPV082760".encode("cp037"): "FMPV082760",
            "DPWN524712".encode("cp037"): "DPWN524712",
        }
        data = (
            b"\x00\x01"
            + "FMPV082760".encode("cp037")
            + b"\x02\x03"
            + "DPWN524712".encode("cp037")
        )
        self.assertEqual(
            _scan_ebcdic_sysobjnam(data, targets),
            [(2, "FMPV082760"), (14, "DPWN524712")],
        )

    def test_dlo_filename_hint_requires_simple_pc_style_name(self):
        self.assertEqual(
            _dlo_filename_hint(
                ["S1011111", "CKPCSPTH.EXE", "other text"]
            ),
            "CKPCSPTH.EXE",
        )
        self.assertEqual(
            _dlo_filename_hint(["BULLETIN/BULLET1.RFT"]),
            "",
        )
        self.assertEqual(
            _dlo_filename_hint(["no extension here"]),
            "",
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

    def test_find_byte_occurrences_including_overlaps(self):
        self.assertEqual(
            _find_byte_occurrences(b"AAAA", b"AA"),
            [0, 1, 2],
        )
        self.assertEqual(_find_byte_occurrences(b"ABC", b"Z"), [])
        self.assertEqual(_find_byte_occurrences(b"ABC", b""), [])

    def test_tui_dlo_export_pair_from_qdoc_and_docbss(self):
        doc = SimpleNamespace(
            object_type=0x19,
            object_subtype=0x0E,
            library_name="QDOC",
            name="FMPV082760",
        )
        companion = SimpleNamespace(
            object_type=0x06,
            object_subtype=0xC1,
            library_name=None,
            name="FMPV082760F",
        )
        inventory = SimpleNamespace(objects=[doc, companion])

        found_doc, found_companion, error = _dlo_export_pair(
            inventory,
            doc,
        )
        self.assertIs(found_doc, doc)
        self.assertIs(found_companion, companion)
        self.assertEqual(error, "")

        found_doc, found_companion, error = _dlo_export_pair(
            inventory,
            companion,
        )
        self.assertIs(found_doc, doc)
        self.assertIs(found_companion, companion)
        self.assertEqual(error, "")

    def test_tui_dlo_export_pair_refuses_ambiguous_companion(self):
        doc = SimpleNamespace(
            object_type=0x19,
            object_subtype=0x0E,
            library_name="QDOC",
            name="FMPV082760",
        )
        companion1 = SimpleNamespace(
            object_type=0x06,
            object_subtype=0xC1,
            library_name=None,
            name="FMPV082760F",
        )
        companion2 = SimpleNamespace(
            object_type=0x06,
            object_subtype=0xC1,
            library_name=None,
            name="FMPV082760F",
        )
        inventory = SimpleNamespace(
            objects=[doc, companion1, companion2]
        )

        _found_doc, found_companion, error = _dlo_export_pair(
            inventory,
            doc,
        )
        self.assertIsNone(found_companion)
        self.assertIn("ambiguous", error)

    def test_dlo_schema_marker_evidence_preserves_literal_names(self):
        field = "WOSEDOCN".encode("cp037")
        alias = "XOSEDOCN".encode("cp037")
        marker = "WOSFMT14".encode("cp037")
        related = (
            "QAOSSS14".encode("cp037")
            + "QAOSSI25".encode("cp037")
            + "QAOSSI66".encode("cp037")
            + "WOSEDNGC".encode("cp037")
        )
        window = (
            b"\x00\x01"
            + field
            + alias
            + marker
            + b"\x00\xC1"
            + related
            + b"\x00\x21"
        )
        marker_offset = window.index(marker)
        evidence = _dlo_schema_marker_evidence(
            window,
            marker_offset,
            "WOSFMT14",
        )
        self.assertEqual(
            evidence,
            (
                "WOSEDOCN",
                (
                    "QAOSSS14",
                    "QAOSSI25",
                    "QAOSSI66",
                    "WOSEDNGC",
                ),
            ),
        )

    def test_dlo_schema_descriptor_layout_reads_one_based_offset_length(self):
        field = "WOSEDOCN".encode("cp037")
        alias = "XOSEDOCN".encode("cp037")
        marker = "WOSFMT14".encode("cp037")
        related = (
            "QAOSSS14".encode("cp037")
            + "QAOSSI25".encode("cp037")
            + "QAOSSI66".encode("cp037")
            + "WOSEDNGC".encode("cp037")
        )
        window = (
            field
            + alias
            + marker
            + b"\x00\xC1"
            + related
            + bytes.fromhex("0021002c")
            + b"\x00" * 24
        )
        marker_offset = window.index(marker)
        self.assertEqual(
            _dlo_schema_descriptor_layout(
                window,
                marker_offset,
                "WOSFMT14",
            ),
            (
                "WOSEDOCN",
                (
                    "QAOSSS14",
                    "QAOSSI25",
                    "QAOSSI66",
                    "WOSEDNGC",
                ),
                33,
                44,
            ),
        )

    def test_qaosss14_unresolved_parent_records(self):
        root_key = bytes.fromhex("0102030405060708")
        missing_key = bytes.fromhex("1112131415161718")
        zero = b"\x00" * 8

        root = SimpleNamespace(
            rrn=1,
            leading_key=root_key,
            parent_key=zero,
        )
        child = SimpleNamespace(
            rrn=2,
            leading_key=bytes.fromhex("2122232425262728"),
            parent_key=root_key,
        )
        gap = SimpleNamespace(
            rrn=3,
            leading_key=bytes.fromhex("3132333435363738"),
            parent_key=missing_key,
        )

        unresolved = _qaosss14_unresolved_parent_records(
            (root, child, gap)
        )
        self.assertEqual(len(unresolved), 1)
        self.assertIs(unresolved[0][0], gap)
        self.assertEqual(unresolved[0][1], ())

    def test_dlo_parent_gaps_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(
            ["dlo-parent-gaps", "marks.hda", "--raw-scan"]
        )
        self.assertEqual(args.command, "dlo-parent-gaps")
        self.assertTrue(args.raw_scan)
        self.assertEqual(args.context, 24)
        self.assertEqual(args.limit, 50)

    def test_dlo_schema_subcommand_defaults_to_wosfmt14(self):
        parser = build_parser()
        args = parser.parse_args(["dlo-schema", "marks.hda"])
        self.assertEqual(args.command, "dlo-schema")
        self.assertEqual(args.format_name, "WOSFMT14")
        self.assertIsNone(args.family)

    def test_qaosss14_parent_key_reconstructs_qdls_path(self):
        zero = b"\x00" * 8
        folder_key = bytes.fromhex("0102030405060708")
        document_key = bytes.fromhex("1112131415161718")
        folder = SimpleNamespace(
            rrn=677,
            leading_key=folder_key,
            record_key=folder_key,
            parent_key=zero,
            short_name="QIWSFLR",
            long_name="QIWSFLR",
        )
        document = SimpleNamespace(
            rrn=695,
            leading_key=document_key,
            record_key=document_key,
            parent_key=folder_key,
            short_name="CKPCSPTH.EXE",
            long_name="CKPCSPTH.EXE",
        )

        path, complete = _qaosss14_path(
            document,
            (folder, document),
        )
        self.assertTrue(complete)
        self.assertEqual(
            path,
            "QIWSFLR/CKPCSPTH.EXE",
        )

    def test_qaosss14_parent_link_uses_leading_key_not_wosefild(self):
        zero = b"\x00" * 8
        folder_leading = bytes.fromhex("07c60c120a342b3b")
        folder_field = bytes.fromhex("07c90b050f1e2c2d")
        child_leading = bytes.fromhex("07c60c120a342f0c")
        child_field = bytes.fromhex("07c90b050f1e2e03")
        folder = SimpleNamespace(
            rrn=1870,
            leading_key=folder_leading,
            record_key=folder_field,
            parent_key=zero,
            short_name="QGFSWOF1",
            long_name="The Bulletin Board folder for SWO users",
        )
        child = SimpleNamespace(
            rrn=1871,
            leading_key=child_leading,
            record_key=child_field,
            parent_key=folder_leading,
            short_name="BULLET1.RFT",
            long_name="AS/400 Office Training Information",
        )

        path, complete = _qaosss14_path(child, (folder, child))
        self.assertTrue(complete)
        self.assertEqual(path, "QGFSWOF1/BULLET1.RFT")
        self.assertNotEqual(child.parent_key, folder.record_key)

    def test_qaosss14_path_marks_unresolved_parent_partial(self):
        document = SimpleNamespace(
            rrn=1871,
            leading_key=bytes.fromhex("0102030405060708"),
            record_key=bytes.fromhex("2122232425262728"),
            parent_key=bytes.fromhex("1112131415161718"),
            short_name="BULLET1.RFT",
            long_name="AS/400 Office Training Information",
        )
        path, complete = _qaosss14_path(document, (document,))
        self.assertFalse(complete)
        self.assertEqual(path, "BULLET1.RFT")

    def test_dlo_paths_subcommand_accepts_specific_sysobjnam(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "dlo-paths",
                "marks.hda",
                "FMPV082760",
                "FMPV195818",
            ]
        )
        self.assertEqual(args.command, "dlo-paths")
        self.assertEqual(
            args.sysobjnam,
            ["FMPV082760", "FMPV195818"],
        )
        self.assertFalse(args.show_unmatched)

    def test_dlo_export_subcommand_requires_explicit_output(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "dlo-export",
                "marks.hda",
                "FMPV082760",
                "CKPCSPTH.EXE",
            ]
        )
        self.assertEqual(args.command, "dlo-export")
        self.assertEqual(args.sysobjnam, "FMPV082760")
        self.assertEqual(args.output, "CKPCSPTH.EXE")
        self.assertFalse(args.force)

    def test_dlo_index_scan_subcommand_defaults_to_anchor_index(self):
        parser = build_parser()
        args = parser.parse_args(["dlo-index-scan", "marks.hda"])
        self.assertEqual(args.command, "dlo-index-scan")
        self.assertIsNone(args.file_name)
        self.assertFalse(args.all_indexes)
        self.assertEqual(args.context, 24)

    def test_dlos_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "dlos",
                "marks.hda",
                "--class",
                "doc",
                "--strings",
                "2",
                "--model-fields",
            ]
        )
        self.assertEqual(args.command, "dlos")
        self.assertEqual(args.image, "marks.hda")
        self.assertEqual(args.object_class, "doc")
        self.assertEqual(args.strings, 2)
        self.assertTrue(args.model_fields)

        xref = parser.parse_args(
            [
                "dlo-xref",
                "marks.hda",
                "FMPV082760",
                "--ascii",
                "--library",
                "QUSRSYS",
                "--hex-context",
            ]
        )
        self.assertEqual(xref.command, "dlo-xref")
        self.assertEqual(xref.sysobjnam, ["FMPV082760"])
        self.assertTrue(xref.ascii)
        self.assertEqual(xref.library, "QUSRSYS")
        self.assertTrue(xref.hex_context)

    def test_documented_dlo_runtime_index_catalog(self):
        self.assertEqual(
            _DLO_RUNTIME_INDEX_FILES,
            (
                "QAOSSS10",
                "QAOSSS11",
                "QAOSSS12",
                "QAOSSS13",
                "QAOSSS14",
                "QAOSSS15",
                "QAOSSS17",
                "QAOSSS18",
            ),
        )

    def test_dlo_model_file_catalog(self):
        self.assertEqual(
            _DLO_MODEL_FILES["QAOSIQDL"],
            ("QRYDOCLIB output model", "OSQDL"),
        )
        self.assertEqual(
            _DLO_MODEL_FILES["QADSPFLR"],
            ("DSPFLR folder-list model", "FLRDTL"),
        )

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
