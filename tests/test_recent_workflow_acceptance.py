"""Synthetic one-scan acceptance runner: command, selection, detail and Back.

All input bytes are invented fixtures; original HDA files are never in CI.
"""
import unittest
from as400_dasd import InternalAddress
from test_type_capabilities import Image, inventory, obj

from tools.validate_recent_workflows import assess, WORKFLOWS


class RecentWorkflowAcceptanceTests(unittest.TestCase):
    def test_all_recent_types_and_commands_are_explicit(self):
        self.assertEqual(12, len(WORKFLOWS))
        self.assertEqual(12, len({item[0] for item in WORKFLOWS}))
        self.assertEqual({"0E/02", "0E/01", "0E/C4", "19/09", "19/04",
                          "0E/07", "0E/91", "19/CE", "19/C2", "18/A0",
                          "19/15", "19/08"}, {x[0] for x in WORKFLOWS})
        empty = assess(Image([]), inventory([]))
        self.assertEqual(12, len(empty))
        self.assertTrue(all(entry["counts"]["ui_walkthroughs_not_possible"] == 1
                            for entry in empty.values()))

    def test_lda_command_real_selection_and_paging(self):
        from test_local_data_workflows import LocalDataTests
        source, image, _, model = LocalDataTests().setup()
        counts = assess(image, model.inventory)
        self.assertEqual(1, counts["19/CE"]["counts"]["bounded_views"])
        self.assertEqual(1, counts["19/CE"]["counts"]["ui_summary_ok"])

    def test_edtd_peer_selection_and_back(self):
        from test_edit_description_workflows import EditDescriptionTests
        eight, six, five, image, _, model = EditDescriptionTests().setup()
        result = assess(image, model.inventory)
        self.assertEqual(3, result["19/08"]["counts"]["recovered_primaries"])
        self.assertEqual(3, result["19/08"]["counts"]["bounded_views"])
        self.assertEqual(1, result["19/08"]["counts"]["ui_detail_back_ok"])

    def test_panel_symbol_selection_and_back(self):
        from test_panel_group_workflows import PanelGroupTests
        primary, prog, other, wrong, image, _, model = PanelGroupTests().make()
        data = assess(image, model.inventory)
        self.assertEqual(1, data["19/15"]["counts"]["bounded_views"])
        self.assertEqual(1, data["19/15"]["counts"]["ui_detail_back_ok"])

    def test_jmq_saved_slot_selection_and_back(self):
        from test_jmq_workflows import JMQTests
        primary, image, _, model = JMQTests().setup()
        result = assess(image, model.inventory)
        self.assertEqual(1, result["18/A0"]["counts"]["bounded_views"])
        self.assertEqual(1, result["18/A0"]["counts"]["ui_detail_back_ok"])

    def test_outq_saved_index_selection_and_back(self):
        from test_outq_workflows import OutputQueueTests
        primary, explorer, model = OutputQueueTests().fixture_model()
        data = assess(explorer.image, model.inventory)
        self.assertEqual(1, data["0E/02"]["counts"]["bounded_views"])
        self.assertEqual(1, data["0E/02"]["counts"]["ui_detail_back_ok"])

    def test_invalid_source_is_explicitly_withheld_not_counted(self):
        from test_local_data_workflows import LocalDataTests
        primary, image, _, model = LocalDataTests().setup()
        image.pages[10] = bytes(512)
        result = assess(image, model.inventory)
        self.assertEqual(0, result["19/CE"]["counts"].get("bounded_views", 0))
        self.assertEqual(1, result["19/CE"]["counts"]["withheld_or_unavailable"])
        self.assertEqual(1, result["19/CE"]["counts"]["ui_walkthroughs_not_possible"])

    def test_report_does_not_expose_recovered_names_or_values(self):
        from test_edit_description_workflows import EditDescriptionTests
        a, b, c, image, _, model = EditDescriptionTests().setup()
        result = assess(image, model.inventory)
        rendered = repr(result)
        for secret in ("QEDIT8", "QEDIT6", "QEDIT5", "CR"):
            self.assertNotIn(secret, rendered)


if __name__ == "__main__":
    unittest.main()
