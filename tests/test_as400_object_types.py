"""IBM MI object catalog: provenance, mapping and fail-closed validation tests."""
import unittest
import io
from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace as NS

from as400_object_types import (
    EXTERNAL_SOURCE, INTERNAL_SOURCE, catalog, lookup, merge_catalogs,
    parse_catalog, type_hint,
)
from as400_dasd import RecoveredObject
from as400_5250 import Guided5250
from as400_dasd_tool import _tui_object_type_context, main


class CatalogTests(unittest.TestCase):
    def test_ibm_internal_external_census(self):
        values = list(catalog().values())
        external = [item for item in values if item.category == "external"]
        internal = [item for item in values if item.category == "internal"]
        self.assertEqual(102, len(external))
        self.assertEqual(166, len(internal))
        self.assertEqual(268, len(values))
        self.assertTrue(all(item.source == EXTERNAL_SOURCE for item in external))
        self.assertTrue(all(item.source == INTERNAL_SOURCE for item in internal))
        self.assertTrue(all(item.display_code == item.code[:2] + "/" + item.code[2:]
                            for item in values))
        self.assertEqual(268, len({item.type_pair for item in values}))

    def test_previously_unknown_codes_and_familiar_examples(self):
        mapping = {
            "1905": ("*CMD", "external"),
            "1916": ("*MENU", "external"),
            "0E03": ("*MSGF", "external"),
            "0E02": ("*OUTQ", "external"),
            "1906": ("*TBL", "external"),
            "19D4": ("*DBRCVR", "internal"),
            "0EC4": ("*INTPRF", "internal"),
            "0ED1": ("*DRX", "internal"),
            "19E0": ("*ADO", "internal"),
            "19EE": ("*MSCSP", "internal"),
            "1951": ("*FMT", "internal"),
            "0ED0": ("*EDTIDX", "internal"),
            "0DED": ("*OWCUR", "internal"),
            "19D7": ("*EPTAB", "internal"),
            "0E90": ("*QDIDX", "internal"),
            "0B90": ("*QDDS", "internal"),
            "0C90": ("*QDDSI", "internal"),
        }
        for code, (name, category) in mapping.items():
            with self.subTest(code=code):
                item = lookup(code)
                self.assertEqual(name, item.name)
                self.assertEqual(category, item.category)
                self.assertEqual(name, type_hint(*item.type_pair))
                stub = NS(object_type=item.type_pair[0],
                          object_subtype=item.type_pair[1])
                self.assertEqual(name, RecoveredObject.external_type_hint.fget(stub))
                self.assertIn(name, _tui_object_type_context(*item.type_pair))

    def test_unknown_and_malformed_codes_do_not_get_misleading_labels(self):
        for code in ("FFFF", "??/??", "OED0", "ODED", "0E/FF", "zz05", ""):
            with self.subTest(code=code):
                self.assertIsNone(lookup(code))
        self.assertEqual("", type_hint(0xFE, 0xFF))
        self.assertIsNone(lookup(257, 0))
        self.assertIsNone(lookup(-1, 0))
        self.assertIsNone(lookup(0x19, -1))
        self.assertIsNone(lookup(None))
        self.assertIsNone(lookup("1905/3"))
        self.assertEqual("*CMD", lookup("19/05").name)

    def test_cli_lookup_and_filter_without_disk_image(self):
        with io.StringIO() as stream, redirect_stdout(stream):
            self.assertEqual(0, main(["types", "19/D4"]))
            result = stream.getvalue()
        self.assertIn("*DBRCVR", result)
        self.assertIn("internal", result)
        self.assertIn("www.ibm.com/docs", result)
        with io.StringIO() as stream, redirect_stdout(stream):
            self.assertEqual(0, main(["types", "--category", "external"]))
            result = stream.getvalue()
        self.assertIn("*MENU", result)
        self.assertNotIn("*DBRCVR", result)
        self.assertIn("102 IBM documented types", result)
        with io.StringIO() as stream, redirect_stderr(stream):
            self.assertEqual(1, main(["types", "FE/FF"]))
            self.assertIn("unknown MI object code", stream.getvalue())

    def test_tsv_parser_rejects_invalid_entries_and_duplicates(self):
        args = dict(category="internal", source="synthetic")
        expected = parse_catalog(["19D4|*DBRCVR|Database recovery"], **args)
        self.assertEqual("*DBRCVR", expected["19D4"].name)
        for bad in (
            ["OED0|*BAD|Invalid hexadecimal"],
            ["19D4|BAD|Missing prefix"],
            ["19D4|*NAME|"],
            ["19D4|*NAME"],
            ["19D4|*NAME|Valid|Unexpected"],
            ["19D4|*DBRCVR|One", "19D4|*OTHER|Two"],
            ["19D4|*NAME|Okay", "19d4|*NAME|Duplicate/wrong case"],
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    parse_catalog(bad, **args)
        with self.assertRaises(ValueError):
            parse_catalog(["1905|*CMD|Command"], category="wrong", source="test")

    def test_external_internal_collisions_rejected(self):
        external = parse_catalog(["1905|*CMD|Command"], category="external",
                                 source="external")
        internal = parse_catalog(["1905|*SOMETHING|Incorrect"], category="internal",
                                 source="internal")
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            merge_catalogs(external, internal)

    def test_guided_rows_and_details_distinguish_internal_external(self):
        internal = NS(name="RECOVERY", object_type=0x19, object_subtype=0xD4,
                      is_member_cursor=False, type_code="19/D4",
                      external_type_hint="*DBRCVR")
        external = NS(name="MENUOBJ", object_type=0x19, object_subtype=0x16,
                      is_member_cursor=False, type_code="19/16",
                      external_type_hint="*MENU")
        directory = NS(library_name="TESTLIB", is_member_cursor=False,
                       display_name_hint="DIRONLY", type_code="0E/C4")
        inventory = NS(
            libraries=[],
            objects=[NS(library_name="TESTLIB")],
            in_library=lambda lib: [internal, external],
            members=lambda **_: [],
            unresolved_context_entries=lambda lib: [directory],
        )
        model = Guided5250(inventory)
        model._goto("objects", library="TESTLIB")
        rows = {row["name"]: row for row in model.rows()}
        self.assertEqual("*DBRCVR", rows["RECOVERY"]["type"])
        self.assertEqual("[internal]", rows["RECOVERY"]["note"])
        self.assertEqual("*MENU", rows["MENUOBJ"]["type"])
        self.assertEqual("", rows["MENUOBJ"]["note"])
        self.assertEqual("*INTPRF", rows["DIRONLY"]["type"])
        self.assertEqual("[dir] primary absent", rows["DIRONLY"]["note"])
        self.assertTrue(model.open_row(
            next(i for i, row in enumerate(model.rows())
                 if row["name"] == "RECOVERY"), "8"))
        self.assertIn("IBM object class: internal", model.detail)
        self.assertTrue(any("19/D4" in line for line in model.detail))
        self.assertTrue(any("V2R3 presence unverified" in line for line in model.detail))


if __name__ == "__main__":
    unittest.main()
