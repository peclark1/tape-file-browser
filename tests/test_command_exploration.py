"""Synthetic workflow and corruption regressions. No historical disk payloads."""
import curses
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

from as400_cmd import command_exploration, recover_parameter_keywords
from as400_5250 import Guided5250, _draw, run_curses
from as400_dasd_tool import _tui_command_definition
from test_as400_5250 import FakeInventory, object_record


def primary(names=("FIRST", "TOFLR", "TODOC")):
    data = bytearray(2048)
    data[0x17E:0x182] = bytes((0x81, 0, len(names), 0))
    for ordinal, name in enumerate(names, 1):
        start = 0x19C + (ordinal - 1) * 64
        data[start:start + 10] = name.ljust(10).encode("cp037")
        data[start + 10:start + 12] = ordinal.to_bytes(2, "big")
    data[0x102:0x116] = "PROCESSOR ".encode("cp037") + "QGPL      ".encode("cp037")
    return bytes(data)


def command(name="TEST", library="QGPL", lba=100):
    obj = object_record(name, library, type_code=(0x19, 5), hint="*CMD")
    obj.segment = NS(start_lba=lba, virtual_address=0x120000 + lba * 512,
                     pages=4, extents=(NS(start_lba=lba, pages=4),))
    return obj


class Screen:
    def __init__(self, height=24, width=80, keys=()):
        self.height, self.width, self.keys = height, width, iter(keys)
        self.written = []
    def getmaxyx(self): return self.height, self.width
    def erase(self): self.written = []
    def refresh(self): pass
    def keypad(self, enabled): pass
    def getch(self): return next(self.keys)
    def addnstr(self, y, x, text, count, attr=0):
        assert 0 <= y < self.height and 0 <= x < self.width
        assert count <= self.width - x
        assert all(ord(c) >= 32 for c in text)
        self.written.append(text[:count])


class ExplorationTests(unittest.TestCase):
    def model(self):
        inv = FakeInventory()
        inv.objects += [command(), command(library="OTHER", lba=200),
                        command(library=None, lba=300)]
        pgm = object_record("PROCESSOR", type_code=(2, 1), hint="*PGM")
        pgm.segment = NS(start_lba=400, virtual_address=0xABCD)
        inv.objects.append(pgm)
        return Guided5250(inv, command_definition_loader=lambda o: command_exploration(o, primary()))

    def test_search_duplicates_orphans_and_exact_origin_survive_back(self):
        model = self.model()
        self.assertTrue(model.run_command("DSPCMD CMD(TEST)"))
        self.assertEqual("commands", model.screen)
        self.assertEqual(3, len(model.rows()))
        model.selected = 2
        obj = model.rows()[2]["object"]
        model.open_row(2)
        self.assertEqual("command_definition", model.screen)
        self.assertEqual(obj.library_name or "<unassigned>", model.library)
        i = next(i for i, r in enumerate(model.rows()) if r["name"] == "TODOC")
        model.selected = i
        model.open_row(i)
        self.assertIn("+0x021C", " ".join(model.detail))
        self.assertIn("Unknown / not decoded:", model.detail)
        model.back()
        self.assertEqual(i, model.selected)
        model.back()
        self.assertEqual(2, model.selected)
        self.assertEqual(3, len(model.rows()))
        model.run_command("WRKCMD CMD(*ORPHAN/*)")
        self.assertEqual(1, len(model.rows()))
        self.assertEqual(300, model.rows()[0]["object"].segment.start_lba)
        model.run_command("WRKCMD CMD(QGPL/TE*)")
        self.assertEqual(1, len(model.rows()))
        model.run_command("DSPCMD CMD(NOTHERE)")
        self.assertEqual([], model.rows())
        self.assertIn("No recovered", model.status)

    def test_normal_library_entry_and_related_program_are_nonexecuting(self):
        model = self.model()
        model.inventory.objects = [o for o in model.inventory.objects if o.library_name is not None]
        model.run_command("WRKOBJPDM LIB(QGPL)")
        index = next(i for i, row in enumerate(model.rows()) if row["name"] == "TEST")
        model.open_row(index)
        self.assertEqual("command_definition", model.screen)
        model.back()
        self.assertEqual("objects", model.screen)

    def test_candidate_program_lookup_does_not_claim_pointer_validation(self):
        model = self.model()
        model.run_command("DSPCMD CMD(QGPL/TEST)")
        i = next(i for i, r in enumerate(model.rows()) if r["kind"] == "related")
        model.open_row(i)
        self.assertEqual("related_programs", model.screen)
        self.assertEqual(1, len(model.rows()))
        self.assertIn("unverified", model.status)
        model.open_row(0)
        self.assertIn("not a verified CPP link", " ".join(model.detail))
        self.assertEqual("QGPL", model.library)
        model.back(); model.back()
        self.assertEqual("command_definition", model.screen)

    def test_failed_decode_still_offers_origin_and_evidence(self):
        model = self.model()
        damaged = primary()[:0x1F0]
        model.command_definition_loader = lambda o: command_exploration(o, damaged)
        model.run_command("DSPCMD CMD(QGPL/TEST)")
        self.assertFalse(any(r["type"].startswith("#") for r in model.rows()))
        self.assertIn("Missing ordinal 3", model.status)
        model.open_row(0)
        self.assertIn("complete sequence withheld", " ".join(model.detail))
        model.back(); model.open_row(1)
        self.assertTrue(model.detail)
        model.back()
        model.command_definition_loader = lambda o: (_ for _ in ()).throw(ValueError("Short read"))
        model.run_command("DSPCMD CMD(QGPL/TEST)")
        self.assertIn("Short read", " ".join(model.detail))

    def test_failure_diagnostics_and_no_partial_or_duplicate_parameters(self):
        self.assertIn("Short", recover_parameter_keywords(bytes(40)).reason)
        for count in (0, 65, 255):
            data = bytearray(primary()); data[0x180] = count
            self.assertFalse(recover_parameter_keywords(data).parameters)
        duplicate = recover_parameter_keywords(primary(("SAME", "SAME")))
        self.assertIn("Duplicate", duplicate.reason)
        data = bytearray(primary()); data[0x220:0x230] = bytes(16)
        self.assertFalse(recover_parameter_keywords(data).parameters)
        # Another second-ordinal record in the allowed search range is ambiguous.
        data = bytearray(primary()); data[0x280:0x28C] = data[0x1DC:0x1E8]
        self.assertIn("Ambiguous ordinal 2", recover_parameter_keywords(data).reason)

    def test_fragmented_reader_uses_virtual_extent_order_and_type_gate(self):
        data = primary(); reads = []
        obj = command()
        obj.segment.extents = (NS(start_lba=100, pages=1), NS(start_lba=500, pages=3))
        pages = {100: data[:512], 500: data[512:1024],
                 501: data[1024:1536], 502: data[1536:]}
        def read(lba):
            reads.append(lba)
            return NS(data=pages[lba])
        view = _tui_command_definition({"image": NS(read_sector=read)}, obj)
        self.assertEqual([100, 500, 501, 502], reads)
        self.assertEqual(["FIRST", "TOFLR", "TODOC"], [p.keyword for p in view.recovery.parameters])
        obj.object_type = 8
        with self.assertRaises(ValueError):
            _tui_command_definition({"image": NS(read_sector=read)}, obj)
        self.assertEqual(4, len(reads))

    def test_curses_keyboard_workflow_and_terminal_sizes(self):
        model = self.model()
        model.run_command("WRKCMD CMD(QGPL/TEST)")
        screen = Screen(keys=(10, curses.KEY_DOWN, curses.KEY_DOWN,
                              curses.KEY_DOWN, 10, 2, 2, curses.KEY_F3))
        with patch("curses.curs_set"):
            run_curses(screen, model)
        self.assertEqual("commands", model.screen)
        model.open_row(0)
        for height, width in ((24, 80), (16, 64)):
            screen = Screen(height, width)
            _draw(screen, model)
            if height == 24:
                self.assertIn("TOFLR", " ".join(screen.written))
            model.open_row(0)
            for scroll in range(20):
                model.scroll = scroll
                _draw(screen, model)
            model.back()

    def test_search_rejects_injection_without_changing_navigation(self):
        model = self.model()
        for text in ("DSPCMD CMD(QGPL/TEST);DLTCMD CMD(TEST)",
                     "WRKCMD CMD(A/B/C)", "WRKCMD CMD([A])", "TEST FIRST(X)"):
            before = model._snapshot()
            self.assertFalse(model.run_command(text))
            self.assertEqual(before, model._snapshot())
