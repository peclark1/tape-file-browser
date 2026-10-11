"""Synthetic MSGF -> ALRTBL reverse saved-ID navigation and negative controls."""
import unittest

from as400_alert_tables import AlertTableExplorer
from as400_5250 import Guided5250
from test_alert_table_workflows import AlertTableTests, alert_fixture
from test_type_capabilities import obj, inventory, Image


class MessageAlertReverseTests(unittest.TestCase):
    def make(self, **options):
        source, targets, image, alerts, model, key = AlertTableTests().make(**options)
        alerts.message_explorer.alert_explorer = alerts
        return source, targets, image, alerts, model, key

    def test_bidirectional_exact_id_navigation_and_back_without_record_storage(self):
        alert, targets, image, explorer, model, key = self.make()
        model.run_command("DSPMSGD MSGF(TESTMSG) MSGID(TST*)")
        self.assertEqual("Summary", model.rows()[0]["name"])
        model.selected=1;model.open_row(1)
        names = [r["name"] for r in model.rows()]
        self.assertIn("Text unavailable",names)
        self.assertIn("Same-name saved alert-table evidence",names)
        refs=[(i,r) for i,r in enumerate(model.rows())
              if r["kind"]=="alert_index_action"]
        self.assertEqual(1,len(refs))
        self.assertIs(refs[0][1]["request"]["obj"], alert)
        self.assertEqual("TST0001",refs[0][1]["request"]["entry"].message_id_candidate)
        i=refs[0][0]
        model.selected=i;model.open_row(i)
        self.assertEqual("Saved alert-table key",model.rows()[0]["name"])
        back_action=next((j for j,r in enumerate(model.rows())
                         if r["kind"]=="message_action"),None)
        self.assertIsNotNone(back_action)
        model.selected=back_action;model.open_row(back_action)
        self.assertEqual("Index evidence",model.rows()[0]["name"])
        model.back();self.assertEqual(back_action,model.selected)
        model.back();self.assertEqual(i,model.selected)
        model.back();self.assertEqual(1,model.selected)

    def test_no_matching_id_and_withheld_unreadable_alert_index_are_distinct(self):
        d,key=alert_fixture(tag="D")
        alert, targets, image, alerts, model, _ = self.make(alert_data=(d,key))
        rows = alerts.alert_rows_for_message_id(targets[0],"TST0001")
        self.assertEqual("No corroborated same-ID alert key",rows[-1]["name"])
        self.assertIn("keys containing exact",rows[0]["lines"][1])
        self.assertIn("0",rows[0]["lines"][1])
        alert, targets, image, alerts, model, _ = self.make()
        image.pages[10]=bytes(512)  # Unsupported saved alert header
        rows=alerts.alert_rows_for_message_id(targets[0],"TST0001")
        self.assertEqual("No corroborated same-ID alert key",rows[-1]["name"])
        self.assertIn("roots withheld/unsupported: 1",rows[0]["lines"][2])
        with self.assertRaises(ValueError):
            alerts.alert_rows_for_message_id(alert,"TST0001")
        with self.assertRaises(ValueError):
            alerts.alert_rows_for_message_id(targets[0],"INVALID")

    def test_duplicate_same_id_origins_and_cached_byte_evidence(self):
        first, targets, image, alerts, model, key = self.make()
        data,key=alert_fixture()
        other=obj("TESTMSG",(0x0e,0x09),200,None)
        other.segment.virtual_address=0x100000
        other.segment.pages=len(data)//512
        from types import SimpleNamespace as NS
        other.segment.extents=(NS(start_lba=200,virtual_address=0x100000,pages=len(data)//512),)
        for i in range(0,len(data),512):
            image.pages[200+i//512]=data[i:i+512]
        model.inventory.objects.append(other)
        service=AlertTableExplorer(image,model.inventory,message_explorer=alerts.message_explorer)
        alerts.message_explorer.alert_explorer=service
        rows=service.alert_rows_for_message_id(targets[0],"TST0001")
        links=[r for r in rows if r["kind"]=="alert_index_action"]
        self.assertEqual(2,len(links))
        self.assertEqual({10,200}, {r["request"]["obj"].segment.start_lba for r in links})
        self.assertEqual(2,len(service._reverse))
        reads=len(image.reads)
        again=service.alert_rows_for_message_id(targets[0],"TST0001")
        self.assertEqual(2,len([r for r in again if r["kind"]=="alert_index_action"]))
        self.assertEqual(reads,len(image.reads))


if __name__=="__main__":
    unittest.main()
