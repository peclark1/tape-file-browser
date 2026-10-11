"""Synthetic CISC ALRTBL index keys and corroborated MSGF navigation.

No original image bytes or private message text are embedded in these tests.
"""
import unittest
from types import SimpleNamespace as NS

from as400_alert_tables import AlertIndexKey, AlertTableExplorer, decode_alert_index
from as400_messages import MessageExplorer
from as400_5250 import Guided5250, parse_command
from test_message_workflows import fixture as message_fixture
from test_type_capabilities import Image, inventory, obj


def alert_fixture(*, page_size=1024, root=0x800, tag="C", mid="TST0001"):
    data = bytearray(root+page_size)
    data[0x100:0x106] = bytes.fromhex("6000000c0008")
    data[0x420:0x426] = (0x100000+root).to_bytes(6, "big")
    data[0x42A:0x42E] = page_size.to_bytes(4, "big")
    key = tag.encode("cp037") + mid.encode("cp037") + bytes.fromhex("12345678")
    assert len(key) == 12
    end = root + 14 + len(key)
    data[root:root+8] = (bytes.fromhex("970008cc") +
                         (page_size-14-len(key)).to_bytes(2, "big") +
                         end.to_bytes(2, "big"))
    data[root+8:root+14] = (bytes([len(key)-1]) +
                           (root+14).to_bytes(2, "big") +
                           bytes.fromhex("600000"))
    data[root+14:end] = key
    return data,key


class AlertTableTests(unittest.TestCase):
    def make(self, *, alert_data=None, msgf=True, msg_name="TESTMSG"):
        d, key = alert_fixture() if alert_data is None else alert_data
        source = obj("TESTMSG", (0x0e,0x09), 10, "QSYS")
        source.segment.virtual_address = 0x100000
        source.segment.pages = len(d)//512
        source.segment.extents = (NS(start_lba=10, virtual_address=0x100000,
                                     pages=len(d)//512),)
        objects = [source]
        raw = [(source,d)]
        if msgf:
            target = obj(msg_name, (0x0e,0x03), 100, "QSYS")
            messages = message_fixture()
            target.segment.virtual_address = 0x100000
            target.segment.pages = len(messages)//512
            target.segment.extents = (NS(start_lba=100, virtual_address=0x100000,
                                         pages=len(messages)//512),)
            target.segment.owner_key = ("message-owner",)
            objects.append(target)
            raw.append((target,messages))
        inventory_ = inventory(objects)
        image = Image(raw)
        mex = MessageExplorer(image,inventory_,NS(segments=[]))
        alerts = AlertTableExplorer(image,inventory_,message_explorer=mex)
        model = Guided5250(inventory_,alert_loader=alerts.rows,
                            message_loader=mex.rows,
                            capability_loader=lambda o,sample=None:
                                alerts.rows(o) if o.type_code=="0E/09"
                                else mex.rows(o))
        return source, objects[1:], image, alerts, model, key

    def test_release_page_sizes_relocated_roots_and_exact_terminal(self):
        for page,root in ((1024,0x800),(2048,0x1000),(2048,0x1800)):
            data,key = alert_fixture(page_size=page,root=root)
            keys,warnings,size = decode_alert_index(data,0x100000)
            self.assertFalse(warnings)
            self.assertEqual(size,page)
            self.assertEqual(1,len(keys))
            self.assertEqual(key,keys[0].raw)
            self.assertEqual(root+8,keys[0].terminal_offset)
            self.assertEqual("TST0001",keys[0].message_id_candidate)
            self.assertEqual("CTST0001",keys[0].prefix_lens)

    def test_unsupported_keys_are_opaque_and_not_message_ids(self):
        data,key = alert_fixture(tag="D",mid="TST0001")
        found,warnings,size = decode_alert_index(data,0x100000)
        self.assertEqual(1,len(found))
        self.assertIsNone(found[0].message_id_candidate)
        self.assertEqual([],list(warnings))
        for keybytes in (b"",bytes(11),
                         b"\xc3" + b"BAD!001" + bytes(4),
                         b"\xc3" + b"\xff"*7 + bytes(4)):
            self.assertIsNone(AlertIndexKey(keybytes,5).message_id_candidate)

    def test_message_id_cross_correlated_and_selectable_text_evidence(self):
        source, targets, image, alerts, model, key = self.make()
        self.assertEqual(("DSPALRTBL",{"ALRTBL":"TESTMSG","MSGID":"TST*"}),
                         parse_command("DSPALRTBL ALRTBL(TESTMSG) MSGID(TST*)"))
        model.run_command("DSPALRTBL ALRTBL(TESTMSG) MSGID(TST*)")
        self.assertEqual("Saved alert-table index",model.rows()[0]["name"])
        self.assertEqual("TST0001",model.rows()[1]["name"])
        model.selected=1
        model.open_row(1)
        self.assertEqual("Saved alert-table key",model.rows()[0]["name"])
        self.assertEqual("Corroborated saved MSGF ID",
                         next(r["name"] for r in model.rows()
                              if r["name"]=="Corroborated saved MSGF ID"))
        matches=[(i,r) for i,r in enumerate(model.rows())
                 if r["kind"]=="message_action"]
        self.assertEqual(1,len(matches))
        index,link = matches[0]
        self.assertEqual(targets[0],link["request"]["obj"])
        self.assertEqual("TST0001",link["name"])
        model.selected=index
        model.open_row(index)
        self.assertEqual("Index evidence",model.rows()[0]["name"])
        self.assertEqual("Text unavailable",model.rows()[-1]["name"])
        model.back()
        self.assertEqual(index,model.selected)
        model.back()
        self.assertEqual(1,model.selected)
        self.assertTrue(image.reads)

    def test_missing_msgf_and_mismatched_id_are_not_false_correlations(self):
        source, targets, image, alerts, model, key = self.make(msgf=False)
        detail = alerts.rows(source,entry=alerts.entries(source)[0][0])
        self.assertEqual("No saved same-name MSGF",detail[-1]["name"])
        self.assertFalse(any(r["kind"]=="message_action" for r in detail))
        source, targets, image, alerts, model, key = self.make(msg_name="OTHERMSG")
        detail = alerts.rows(source,entry=alerts.entries(source)[0][0])
        self.assertEqual("No saved same-name MSGF",detail[-1]["name"])
        data,key = alert_fixture(mid="ZZZFFFF")
        source, targets, image, alerts, model, key = self.make(alert_data=(data,key))
        detail = alerts.rows(source,entry=alerts.entries(source)[0][0])
        self.assertEqual("No corroborated MSGF ID",detail[-1]["name"])
        self.assertFalse(any(r["kind"]=="message_action" for r in detail))

    def test_invalid_pages_prefixes_and_filters_fail_closed(self):
        data,key=alert_fixture()
        for cut in (0,256,0x42D):
            with self.assertRaises(ValueError):
                decode_alert_index(data[:cut],0x100000)
        for offset,replace in ((0x100,b"\x00"),
                               (0x105,b"\x01"),
                               (0x42A,(4096).to_bytes(4,"big")),
                               (0x420,(0x200000).to_bytes(6,"big"))):
            bad=bytearray(data)
            bad[offset:offset+len(replace)]=replace
            with self.assertRaises(ValueError):
                decode_alert_index(bad,0x100000)
        source, targets, image, alerts, model, key=self.make()
        for args in ({"start":-1},{"start":"0"},{"keyhex":"GG"},
                     {"keyhex":"FF"*13},{"msgid":"@INVALID"},
                     {"entry":NS(raw=key,terminal_offset=-1)}):
            with self.assertRaises(ValueError):
                alerts.rows(source,**args)
        with self.assertRaises(ValueError):
            alerts.rows(targets[0])
        model.run_command("DSPALRTBL ALRTBL(TESTMSG) MSGID(ZZZ*)")
        self.assertEqual(1,len(model.rows()))


if __name__=="__main__":
    unittest.main()
