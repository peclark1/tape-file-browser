"""Synthetic JMQ saved slot tests; no historical message data committed."""
import unittest
from types import SimpleNamespace as NS
from as400_jmq import (
    JobMessageQueueExplorer, read_jmq_slots, ENTRY_AT, ENTRY_BYTES)
from as400_5250 import Guided5250, parse_command
from test_type_capabilities import obj,inventory,Image


def fixture(count=3,extra=False):
    data=bytearray(16*512)
    data[0x100:0x104]=bytes.fromhex("80000000")
    data[0x800:0x802]=count.to_bytes(2,"big")
    for i in range(count):
        off=ENTRY_AT+i*ENTRY_BYTES
        data[off:off+ENTRY_BYTES]=bytes([0x93,i+1])+bytes(14)
    if extra:data[ENTRY_AT+count*ENTRY_BYTES]=0x93
    return data


class JMQTests(unittest.TestCase):
    def setup(self,count=3,data=None):
        o=obj("QJOBMSGQ",(0x18,0xA0),10,None)
        o.segment.virtual_address=0x100000
        d=fixture(count) if data is None else data
        o.segment.extents=(NS(start_lba=10,virtual_address=0x100000,
                              pages=len(d)//512),)
        inv=inventory([o]);im=Image([(o,d)])
        ex=JobMessageQueueExplorer(im)
        model=Guided5250(inv,jmq_loader=ex.rows,
                          capability_loader=lambda target,sample=None:ex.rows(target))
        return o,im,ex,model

    def test_guarded_count_and_exact_16_byte_entries(self):
        for count in (0,1,3,50,60):
            found,number,warn=read_jmq_slots(fixture(count),type_code="18/A0")
            self.assertEqual(count,len(found))
            self.assertEqual(count,number)
            self.assertFalse(warn)
            if count:
                self.assertEqual(ENTRY_AT,found[0].offset)
                self.assertEqual(16,len(found[-1].raw))
        for data,reason in ((fixture()[:0x800],"Truncated"),
                            (fixture()[:0x813],"Truncated"),
                            (fixture(), "Not a saved")):
            with self.assertRaises(ValueError):
                read_jmq_slots(data,type_code="19/02" if reason=="Not a saved" else "18/A0")

    def test_corrupted_header_or_zero_slot_fails_closed(self):
        for at,value in ((0x100,0),(0x802,1),(ENTRY_AT,0)):
            d=fixture();d[at]=value
            with self.assertRaises(ValueError):
                read_jmq_slots(d,type_code="18/A0")
        d=fixture();d[0x800:0x802]=(257).to_bytes(2,"big")
        with self.assertRaises(ValueError):read_jmq_slots(d,type_code="18/A0")
        _,_,warnings=read_jmq_slots(fixture(extra=True),type_code="18/A0")
        self.assertTrue(any("follows" in w for w in warnings))

    def test_command_paging_selection_and_back(self):
        o,im,ex,model=self.setup(60)
        self.assertEqual(("DSPJMQ",{"JMQ":"QJOBMSGQ"}),
                         parse_command("DSPJMQ JMQ(QJOBMSGQ)"))
        model.run_command("DSPJMQ JMQ(QJOBMSGQ)")
        self.assertEqual("Saved job-message queue slots",model.rows()[0]["name"])
        self.assertEqual(50,sum(r["name"].startswith("Slot ") for r in model.rows()))
        model.selected=1;model.open_row(1)
        self.assertEqual("Slot 51",model.rows()[2]["name"])
        model.selected=2;model.open_row(2)
        self.assertEqual("Saved JMQ slot",model.rows()[0]["name"])
        self.assertEqual("Declared slot ordinal 51",model.rows()[0]["lines"][1][:24])
        model.back();self.assertEqual(2,model.selected)
        model.back();self.assertEqual(1,model.selected)
        self.assertTrue(im.reads)

    def test_virtual_gap_and_missing_origin_diagnostics(self):
        o,im,ex,_=self.setup()
        o.segment.extents=(NS(start_lba=10,virtual_address=0x100000,pages=3),
                           NS(start_lba=13,virtual_address=0x100800,pages=13))
        with self.assertRaises(ValueError):ex.rows(o)
        o,im,ex,_=self.setup()
        for opts in ({"start":-1},{"start":"0"},{"entry":NS(ordinal=1,offset=ENTRY_AT,raw=b"bad")}):
            with self.assertRaises(ValueError):ex.rows(o,**opts)
        with self.assertRaises(ValueError):ex.rows(obj("OTHER",(0x19,1)))


if __name__=="__main__":
    unittest.main()
