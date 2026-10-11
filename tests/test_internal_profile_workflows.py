"""Credential-safe INTPRF identity relationship tests with synthetic primaries."""
import unittest

from as400_internal_profiles import InternalProfileExplorer
from as400_5250 import Guided5250, parse_command
from test_type_capabilities import obj, inventory, Image


class InternalProfileTests(unittest.TestCase):
    def test_exact_name_duplicates_and_unassigned(self):
        internal = obj("QEXAMPLE", (0x0E, 0xC4), 10, None)
        one = obj("QEXAMPLE", (0x08, 0x01), 20, "QSYS")
        two = obj("QEXAMPLE", (0x08, 0x01), 30, None)
        near = obj("QEXAMPL2", (0x08, 0x01), 40, "QSYS")
        inv = inventory([internal, one, two, near])
        service = InternalProfileExplorer(inv)
        rows = service.rows(internal)
        self.assertEqual([two, one], [r["object"] for r in rows if r.get("object")])
        self.assertIn("2 exact-name", rows[0]["lines"][2])
        self.assertTrue(any("Name equality" in line for line in rows[0]["lines"]))
        model = Guided5250(inv, capability_loader=lambda o, sample=None:service.rows(o),
                           config_info_loader=lambda o:["Recovered identity only",o.name])
        model.run_command("DSPINTPRF INTPRF(QEXAMPLE)")
        self.assertEqual("capabilities", model.screen)
        self.assertEqual("QEXAMPLE", model.rows()[1]["name"])
        model.selected = 1; model.open_row(1)
        self.assertEqual("config_info", model.screen)
        model.back()
        self.assertEqual(1, model.selected)

    def test_missing_user_profile_retains_internal_identity(self):
        internal = obj("PENDING", (0x0E, 0xC4), 10, None)
        unrelated = obj("PENDING", (0x19, 0x03), 20, "QSYS")
        ex = InternalProfileExplorer(inventory([internal, unrelated]))
        rows = ex.rows(internal)
        self.assertEqual("No name match", rows[-1]["name"])
        self.assertIn("not evidence",rows[-1]["lines"][1])
        with self.assertRaises(ValueError):
            ex.rows(unrelated)

    def test_selection_is_identity_only_and_never_reads_image(self):
        internal = obj("PROFILE", (0x0E, 0xC4), 10, None)
        user = obj("PROFILE", (0x08, 0x01), 20)
        inv = inventory([internal,user])
        image = Image([])
        ex = InternalProfileExplorer(inv)
        self.assertEqual(2, len(ex.rows(internal)))
        self.assertEqual([], image.reads)
        self.assertEqual(("DSPINTPRF",{"INTPRF":"*ALL/PROFILE"}),
                         parse_command("DSPINTPRF INTPRF(*ALL/PROFILE)"))
        model = Guided5250(inv, capability_loader=lambda o, sample=None:ex.rows(o))
        model.run_command("DSPINTPRF INTPRF(*ORPHAN/PROFILE)")
        self.assertTrue(model.rows())


if __name__ == "__main__":
    unittest.main()
