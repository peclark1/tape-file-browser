"""Safety and recovery-boundary tests for CISC profile/device/mode viewers."""
import unittest
from types import SimpleNamespace as NS

from as400_config import (
    configuration_information_lines, config_text_evidence, config_type,
    mode_name_candidates,
)
from as400_5250 import Guided5250
from as400_dasd_tool import _tui_config_information_lines


def make_obj(name, pair, *, lba=20):
    seg = NS(
        virtual_address=0x1000 + lba * 512,
        start_lba=lba,
        pages=4,
        extents=(NS(start_lba=lba, pages=4),),
        owner_key=(1, 0x1000 + lba * 512),
        is_primary=True,
    )
    return NS(
        name=name,
        library_name="QSYS",
        object_type=pair[0],
        object_subtype=pair[1],
        type_code=f"{pair[0]:02X}/{pair[1]:02X}",
        external_type_hint={
            (8, 1): "*USRPRF",
            (16, 1): "*DEVD",
            (21, 1): "*MODD",
            (14, 196): "*INTPRF",
        }.get(pair, ""),
        segment=seg,
        is_member_cursor=False,
    )


class ConfigurationViewTests(unittest.TestCase):
    def test_mode_candidate_fields_remain_tentative(self):
        prefix = bytearray(512)
        prefix[0x120:0x128] = "QRMTWSC".ljust(8).encode("cp037")
        prefix[0x12C:0x134] = "#CONNECT".encode("cp037")
        self.assertEqual(
            ((0x120, "QRMTWSC", "repeats recovered object name"),
             (0x12C, "#CONNECT", "adjacent name-like bytes, meaning unknown")),
            mode_name_candidates(bytes(prefix), "QRMTWSC"),
        )
        self.assertEqual((), mode_name_candidates(bytes(prefix), "BADNAME"))
        self.assertEqual((), mode_name_candidates(bytes(prefix[:0x120]), "QRMTWSC"))
        prefix[0x12C:0x134] = b"\x00" * 8
        self.assertEqual(1, len(mode_name_candidates(bytes(prefix), "QRMTWSC")))

    def test_text_scan_is_bounded_and_not_interpreted_as_fields(self):
        prefix = bytearray(4096)
        marker = "Synthetic device description"
        prefix[0x170:0x170 + len(marker)] = marker.encode("cp037")
        self.assertIn((0x170, marker), config_text_evidence(prefix))
        self.assertEqual((), config_text_evidence(prefix[:0x150]))
        self.assertNotIn((0x170, marker),
                         config_text_evidence(prefix, limit=0x170))
        self.assertEqual(1, len(config_text_evidence(prefix, max_items=1)))

    def test_profile_view_never_reads_raw_secret_bearing_primary(self):
        profile = make_obj("TESTUSER", (8, 1))
        terminal = make_obj("TESTUSER", (16, 1), lba=60)
        inter = make_obj("TESTUSER", (14, 196), lba=80)

        class ProhibitedImage:
            def read_sector(self, lba):
                raise AssertionError("Unsafe raw *USRPRF read attempted")

        state = NS()
        state = {
            "image": ProhibitedImage(),
            "inventory": NS(objects=[profile, terminal, inter]),
            "segments": NS(segments=[profile.segment, terminal.segment]),
        }
        lines = _tui_config_information_lines(state, profile)
        output = "\n".join(lines)
        self.assertIn("Display User Profile", output)
        self.assertIn("TESTUSER", output)
        self.assertIn("*DEVD", output)
        self.assertIn("*INTPRF", output)
        self.assertIn("Matching names do NOT prove", output)
        self.assertIn("NEVER displayed", output)
        self.assertNotIn("EBCDIC text evidence", output)
        self.assertIn("Recovered owned segments: 1", output)

    def test_device_and_mode_read_limited_primary_bytes(self):
        mode = make_obj("QPCSUPP", (21, 1))
        prefix = bytearray(4 * 512)
        prefix[0x120:0x128] = "QPCSUPP".ljust(8).encode("cp037")
        prefix[0x12C:0x134] = "#CONNECT".encode("cp037")
        class Image:
            def __init__(self):
                self.calls = []
            def read_sector(self, lba):
                self.calls.append(lba)
                return NS(data=bytes(prefix[(lba-20)*512:(lba-19)*512]))
        image = Image()
        state = {
            "image": image,
            "inventory": NS(objects=[mode]),
            "segments": NS(segments=[mode.segment]),
        }
        result = "\n".join(_tui_config_information_lines(state, mode))
        self.assertIn("Display Mode Description", result)
        self.assertIn("+0x12C #CONNECT", result)
        self.assertIn("not yet structurally decoded", result)
        self.assertEqual([20, 21, 22, 23], image.calls)
        # Changing type should leave on-disk data unaltered and never
        # change object structure interpretation.
        device = make_obj("TESTDEVD", (16, 1))
        self.assertEqual("*DEVD", config_type(device)[0])
        lines = configuration_information_lines(device)
        self.assertIn("attached controller: unknown", "\n".join(lines))

    def test_enter_routes_three_types_back_to_list(self):
        profile = make_obj("USERA", (8, 1))
        device = make_obj("DSP01", (16, 1), lba=25)
        mode = make_obj("MODEA", (21, 1), lba=30)
        all_objects = [profile, device, mode]
        inventory = NS(
            libraries=[],
            objects=all_objects,
            in_library=lambda name: all_objects,
            members=lambda **kw: [],
            unresolved_context_entries=lambda name: [],
            context_entries=[],
        )
        viewed = []
        model = Guided5250(inventory, config_info_loader=lambda o: (
            viewed.append(o), [f"Specialized viewer for {o.name}"])[1])
        model._goto("objects", library="QSYS")
        for item in all_objects:
            position = next(
                i for i, row in enumerate(model.rows()) if row["name"] == item.name
            )
            self.assertTrue(model.open_row(position))
            self.assertEqual("config_info", model.screen)
            self.assertIn(item.name, model.detail[0])
            self.assertTrue(model.back())
            self.assertEqual("objects", model.screen)
        self.assertEqual(all_objects, viewed)

    def test_original_display_commands_are_read_only_and_exact_type_only(self):
        profile = make_obj("USERA", (8, 1))
        device = make_obj("DSP01", (16, 1), lba=25)
        mode = make_obj("MODEA", (21, 1), lba=30)
        inventory = NS(
            libraries=[],
            objects=[profile, device, mode],
            in_library=lambda name: [],
            members=lambda **kw: [],
            unresolved_context_entries=lambda name: [],
            context_entries=[],
        )
        model = Guided5250(
            inventory, config_info_loader=lambda obj: [f"Read-only {obj.name}"])
        for command, expected in (
            ("DSPUSRPRF USRPRF(USERA)", "USERA"),
            ("DSPDEVD DEVD(DSP01)", "DSP01"),
            ("DSPMODD MODD(MODEA)", "MODEA"),
        ):
            with self.subTest(command=command):
                self.assertTrue(model.run_command(command))
                self.assertEqual("config_info", model.screen)
                self.assertIn(expected, model.detail[0])
                self.assertTrue(model.back())
        for command in (
            "DSPUSRPRF USRPRF(DSP01)",
            "DSPDEVD DEVD(USERA)",
            "DSPMODD MODD(USERA)",
            "DSPUSRPRF USRPRF(NOUSER)",
            "DSPDEVD DEVD(QSYS/DSP01)",
            "DSPMODD MODD(MODEA) BADARG(X)",
        ):
            with self.subTest(command=command):
                self.assertFalse(model.run_command(command))
                self.assertNotEqual("config_info", model.screen)
        # Same-name duplicates are not silently chosen by pointer/order.
        duplicate = make_obj("USERA", (8, 1), lba=160)
        inventory.objects.append(duplicate)
        self.assertFalse(model.run_command("DSPUSRPRF USRPRF(USERA)"))
        self.assertIn("matching USERA objects", model.status)
        self.assertNotEqual("config_info", model.screen)

    def test_wrong_type_and_truncated_data_do_not_fabricate_fields(self):
        unrelated = make_obj("WHATEVER", (25, 5))
        self.assertIsNone(config_type(unrelated))
        self.assertIn("not", configuration_information_lines(unrelated)[0].lower())
        mode = make_obj("SAMPLE", (21, 1))
        screen = "\n".join(configuration_information_lines(mode, bytes(30)))
        self.assertIn("not yet structurally decoded", screen)
        self.assertIn("No validated name-correlated candidate", screen)


if __name__ == "__main__":
    unittest.main()
