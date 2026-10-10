"""Synthetic tests for the guided offline AS/400 command browser."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

from as400_5250 import (
    Guided5250, _back_or_edit_option, _draw, _safe_display_text, command_matches,
    parse_command, run_curses,
)
from as400_dasd import RecoveredObject
from as400_dasd_tool import _tui_object_type_context, build_parser


def object_record(name, library="QGPL", *, type_code=(0x19, 0x01),
                  hint="*FILE", member_file="", member_name=""):
    return NS(
        name=name, library_name=library,
        object_type=type_code[0], object_subtype=type_code[1],
        type_code=f"{type_code[0]:02X}/{type_code[1]:02X}",
        external_type_hint=hint,
        is_member_cursor=bool(member_name),
        member_file_name=member_file,
        member_name=member_name,
    )


class FakeInventory:
    def __init__(self):
        self.libraries = [object_record("QSYS", "", type_code=(4, 1), hint="*LIB"),
                          object_record("QGPL", "", type_code=(4, 1), hint="*LIB")]
        self.objects = [
            *self.libraries,
            object_record("QCLSRC"),
            object_record("CALC", type_code=(0x19, 0x02), hint="*PGM"),
            object_record("QCLSRC.REFRESH2", type_code=(0x0D, 0x50),
                          member_file="QCLSRC", member_name="REFRESH2"),
            object_record("MISSING.FILE", type_code=(0x0D, 0x50),
                          member_file="LOSTSRC", member_name="ONE"),
        ]
        self.context_entries = [
            NS(library_name="QGPL", is_member_cursor=False,
               display_name_hint="ONLYDIR", type_code="19/01")
        ]

    def in_library(self, name):
        return [o for o in self.objects if o.library_name.upper() == name.upper()]

    def members(self, *, library=None, file_name=None):
        return [o for o in self.objects if o.is_member_cursor
                and (library is None or o.library_name.upper() == library.upper())
                and (file_name is None or o.member_file_name.upper() == file_name.upper())]

    def unresolved_context_entries(self, library=None):
        return [o for o in self.context_entries
                if library is None or o.library_name.upper() == library.upper()]


class Guided5250Tests(unittest.TestCase):
    def make_model(self):
        return Guided5250(FakeInventory(),
            member_info=lambda member: NS(member_type="CLP", text="Sample source"),
            member_loader=lambda library, file, member: [
                f"Source records: {library}/{file}({member.member_name})", "0010  DCL VAR(&N)"])

    def test_cli_exposes_guided_browser_without_replacing_forensic_browser(self):
        parser = build_parser()
        guided = parser.parse_args(["browse5250", "sample.hda"])
        forensic = parser.parse_args(["browse", "sample.hda"])
        self.assertEqual("cmd_browse5250", guided.func.__name__)
        self.assertEqual("sample.hda", guided.image)
        self.assertEqual("cmd_browse", forensic.func.__name__)

    def test_documented_command_object_type_mapping(self):
        cmd = NS(object_type=0x19, object_subtype=0x05)
        file_object = NS(object_type=0x19, object_subtype=0x01)
        self.assertEqual("*CMD", RecoveredObject.external_type_hint.fget(cmd))
        self.assertEqual("*FILE", RecoveredObject.external_type_hint.fget(file_object))
        msgf = NS(object_type=0x0E, object_subtype=0x03)
        self.assertEqual("*MSGF", RecoveredObject.external_type_hint.fget(msgf))
        self.assertIn("message file", _tui_object_type_context(0x0E, 0x03))

    def test_ibm_internal_database_recovery_object_type(self):
        obj = NS(object_type=0x19, object_subtype=0xD4)
        self.assertEqual("*DBRCVR", RecoveredObject.external_type_hint.fget(obj))
        desc = _tui_object_type_context(0x19, 0xD4)
        self.assertIn("Database Recovery Object", desc)
        self.assertIn("not currently decoded", desc)

    def test_interactive_profile_and_menu_object_type_mappings(self):
        expected = {
            (0x0E, 0xC4): ("*INTPRF", "Interactive Profile"),
            (0x19, 0x16): ("*MENU", "menu description"),
        }
        for (obj_type, subtype), (label, meaning) in expected.items():
            with self.subTest(type=f"{obj_type:02X}/{subtype:02X}"):
                obj = NS(object_type=obj_type, object_subtype=subtype)
                self.assertEqual(label, RecoveredObject.external_type_hint.fget(obj))
                detail = _tui_object_type_context(obj_type, subtype)
                self.assertIn(meaning.lower(), detail.lower())
                self.assertIn("not currently decoded", detail)

    def test_five_historical_mi_object_type_labels_and_context(self):
        expected = {
            (0x19, 0xE0): ("*ADO", "Asynchronous Distribution Object"),
            (0x0E, 0xD1): ("*DRX", "Distribution Recipient Index"),
            (0x19, 0xEE): ("*MSCSP", "Permanent Miscellaneous Space"),
            (0x0E, 0x02): ("*OUTQ", "output queue"),
            (0x19, 0x06): ("*TBL", "table object"),
        }
        for (object_type, subtype), (label, meaning) in expected.items():
            with self.subTest(type=f"{object_type:02X}/{subtype:02X}"):
                stub = NS(object_type=object_type, object_subtype=subtype)
                self.assertEqual(
                    label, RecoveredObject.external_type_hint.fget(stub))
                self.assertIn(meaning.lower(),
                              _tui_object_type_context(object_type, subtype).lower())

    def test_recovered_nulls_are_displayed_safely_not_destroyed(self):
        model = Guided5250(FakeInventory())
        # Use an actual embedded NUL and ESC, not textual escape sequences.
        line = "ABC" + chr(0) + "DEF" + chr(27) + "[31m"
        model.member_loader = lambda *_: [line]
        self.assertTrue(model.run_command(
            "DSPPFM FILE(QGPL/QCLSRC) MBR(REFRESH2)"))
        self.assertEqual([line], model.detail)

        class StrictScreen:
            def __init__(self):
                self.written = []
            def getmaxyx(self):
                return (28, 120)
            def erase(self):
                pass
            def refresh(self):
                pass
            def addnstr(self, y, x, text, count, attr=0):
                if chr(0) in text:
                    raise ValueError("embedded null character")
                self.written.append(text[:count])

        model.status = "Status" + chr(0) + "NUL"
        screen = StrictScreen()
        _draw(screen, model)
        display = " ".join(screen.written)
        self.assertIn(r"\x00", display)
        self.assertIn(r"\x1B", display)
        self.assertNotIn(chr(0), display)
        self.assertNotIn(chr(27), display)
        # Original bytes remain present in memory for forensic inspection.
        self.assertEqual([line], model.detail)
        self.assertEqual(r"X\x00Y\x0AZ\x7F", _safe_display_text(
            "X" + chr(0) + "Y" + chr(10) + "Z" + chr(127)))

    def test_enter_on_command_opens_read_only_command_evidence(self):
        model = self.make_model()
        command = object_record("ADDCUSTOM", type_code=(0x19, 0x05), hint="*CMD")
        model.inventory.objects.append(command)
        observed = []
        def loader(obj):
            observed.append(obj)
            return ["Command information from recovered primary", "Unverified fields omitted"]
        model.command_info_loader = loader
        self.assertTrue(model.run_command("WRKOBJPDM LIB(QGPL)"))
        position = next(
            i for i, row in enumerate(model.rows()) if row["name"] == "ADDCUSTOM"
        )
        self.assertTrue(model.open_row(position))  # Enter, no numeric option
        self.assertEqual("command_info", model.screen)
        self.assertEqual("Display Command Information (Recovered)", model.title())
        self.assertEqual([command], observed)
        self.assertIn("Unverified fields omitted", model.detail)
        self.assertTrue(model.back())
        self.assertEqual("objects", model.screen)
        self.assertTrue(model.open_row(position, "8"))  # Ordinary details remain
        self.assertEqual("details", model.screen)
        self.assertEqual([command], observed)  # No duplicate data sampling

    def test_enter_on_other_objects_displays_details_instead_of_invalid_option(self):
        model = self.make_model()
        self.assertTrue(model.run_command("WRKOBJPDM LIB(QGPL)"))
        position = next(
            i for i, row in enumerate(model.rows()) if row["name"] == "CALC"
        )
        self.assertTrue(model.open_row(position))
        self.assertEqual("details", model.screen)

    def test_command_loader_errors_remain_inside_browser(self):
        model = self.make_model()
        command = object_record("BROKEN", type_code=(0x19, 0x05), hint="*CMD")
        model.inventory.objects.append(command)
        model.command_info_loader = lambda obj: (_ for _ in ()).throw(
            ValueError("Damaged sample"))
        self.assertTrue(model.run_command("WRKOBJPDM LIB(QGPL)"))
        position = next(
            i for i, row in enumerate(model.rows()) if row["name"] == "BROKEN"
        )
        self.assertTrue(model.open_row(position))
        self.assertEqual("command_info", model.screen)
        self.assertIn("Damaged sample", "\\n".join(model.detail))

    def test_catalog_supports_descriptions_and_search(self):
        matches = command_matches("wrk")
        self.assertEqual({"WRKLIB", "WRKLIBPDM", "WRKOBJ", "WRKOBJPDM",
                          "WRKMBRPDM", "WRKCMD", "WRKTYP"}, {m.name for m in matches})
        self.assertTrue(all(item.description for item in matches))
        self.assertIn("DSPPFM", [item.name for item in command_matches("contents")])
        self.assertNotIn("WRKACTJOB", [item.name for item in command_matches()])

    def test_named_params_are_parsed_conservatively(self):
        self.assertEqual(("WRKMBRPDM", {"FILE": "QGPL/QCLSRC"}),
                         parse_command("wrkmbrpdm file(QGPL/QCLSRC)"))
        for command in ("WRKACTJOB", "DSPPFM FILE(QGPL/QCLSRC) MBR(X) EXTRA(Y)",
                        "WRKOBJ LIB(QGPL) LIB(QSYS)", "DSPPFM FILE()", "WRKOBJPDM QGPL",
                        "DSPPFM FILE(QGPL/QCLSRC);DLTF X"):
            with self.subTest(command=command):
                with self.assertRaises(ValueError):
                    parse_command(command)

    def test_classic_library_object_member_navigation(self):
        model = self.make_model()
        self.assertEqual(["QGPL", "QSYS"], [r["name"] for r in model.rows()])
        self.assertTrue(model.open_row(0, "12"))
        self.assertEqual("objects", model.screen)
        self.assertEqual("QGPL", model.library)
        rows = model.rows()
        file_index = next(i for i, row in enumerate(rows) if row["name"] == "QCLSRC")
        self.assertTrue(model.open_row(file_index, "12"))
        self.assertEqual("members", model.screen)
        self.assertEqual("QCLSRC", model.file)
        self.assertEqual(["REFRESH2"], [r["name"] for r in model.rows()])
        self.assertTrue(model.open_row(0, "5"))
        self.assertEqual("contents", model.screen)
        self.assertIn("DCL VAR(&N)", "\n".join(model.detail))
        self.assertTrue(model.back())
        self.assertEqual("members", model.screen)
        self.assertTrue(model.back())
        self.assertEqual("objects", model.screen)

    def test_command_navigation_and_missing_primitives(self):
        model = self.make_model()
        self.assertTrue(model.run_command("WRKOBJPDM LIB(QGPL)"))
        objects = model.rows()
        self.assertTrue(any(r["name"] == "LOSTSRC" and r["note"] == "[member-only]"
                            for r in objects))
        self.assertTrue(any(r["name"] == "ONLYDIR" and "[dir]" in r["note"]
                            for r in objects))
        self.assertTrue(model.run_command("WRKMBRPDM FILE(QGPL/LOSTSRC)"))
        self.assertEqual("ONE", model.rows()[0]["name"])
        self.assertTrue(model.run_command("DSPPFM FILE(QGPL/QCLSRC) MBR(REFRESH2)"))
        self.assertIn("REFRESH2", model.location())
        self.assertTrue(model.run_command("WRKLIB LIB(Q*)"))
        self.assertEqual(["QGPL", "QSYS"], [r["name"] for r in model.rows()])

    def test_unsupported_command_cannot_mutate_state(self):
        model = self.make_model()
        before = model._snapshot()
        self.assertFalse(model.run_command("DLTLIB LIB(QGPL)"))
        self.assertEqual(before, model._snapshot())
        self.assertIn("not supported", model.status)
        self.assertFalse(model.run_command("WRKOBJPDM LIB(NOSUCH)"))
        self.assertEqual(before, model._snapshot())
        self.assertIn("existing recovered library", model.status)

    def test_help_and_read_only_object_details(self):
        model = self.make_model()
        self.assertTrue(model.run_command("HELP"))
        self.assertTrue(any("[dir]" in line for line in model.detail))
        model.back()
        model.run_command("WRKOBJPDM LIB(QGPL)")
        index = next(i for i, row in enumerate(model.rows()) if row["name"] == "ONLYDIR")
        self.assertTrue(model.open_row(index, "5"))
        self.assertIn("primary absent", " ".join(model.detail))
        self.assertFalse(model.open_row(0, "9"))
        self.assertIn("No entry selected", model.status)

    def test_backspace_edits_pending_option_or_returns_to_previous_screen(self):
        model = self.make_model()
        self.assertTrue(model.run_command("WRKOBJPDM LIB(QGPL)"))
        self.assertEqual("1", _back_or_edit_option(model, "12"))
        self.assertEqual("objects", model.screen)
        self.assertEqual("", _back_or_edit_option(model, ""))
        self.assertEqual("libraries", model.screen)

    def test_ctrl_b_navigates_back_without_f12_key(self):
        import curses

        model = self.make_model()
        self.assertTrue(model.run_command("WRKOBJPDM LIB(QGPL)"))

        class FakeScreen:
            def __init__(self):
                self.keys = iter((2, curses.KEY_F3))
            def keypad(self, enabled):
                return None
            def getch(self):
                return next(self.keys)

        with patch("as400_5250._draw"), patch("curses.curs_set"):
            run_curses(FakeScreen(), model)
        self.assertEqual("libraries", model.screen)

    def test_missing_member_data_is_reported_not_fabricated(self):
        model = Guided5250(FakeInventory(), member_loader=lambda *_: [])
        self.assertTrue(model.run_command("DSPPFM FILE(QGPL/QCLSRC) MBR(REFRESH2)"))
        self.assertEqual(["No recoverable member contents in this image."], model.detail)


if __name__ == "__main__":
    unittest.main()
