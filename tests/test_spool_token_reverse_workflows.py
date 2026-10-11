"""Synthetic forward/reverse saved PRTQ <-> SPLCB token correlation tests.

All token correlations are read-only evidence; none assert spool ownership.
"""
import unittest

from as400_5250 import Guided5250
from as400_spool_controls import SpoolControlExplorer
from test_printer_queue_workflows import PrinterQueueTests


class SpoolTokenReverseTests(unittest.TestCase):
    def make(self,**kwargs):
        printer,spools,image,queue,_,key=PrinterQueueTests().make(**kwargs)
        # Preserve separate recovered origins in the normal test inventory.
        from test_type_capabilities import inventory
        inv=inventory([printer,*spools])
        service=SpoolControlExplorer(image,inv,printer_queue_explorer=queue)
        model=Guided5250(inv,printer_queue_loader=queue.rows,
                          capability_loader=lambda obj,sample=None:
                          service.rows(obj) if obj.type_code=="19/C2"
                          else queue.rows(obj))
        return printer,spools,image,queue,service,model

    def test_back_link_from_each_ambiguous_spool_control_origin(self):
        printer,spools,image,queue,service,model=self.make()
        for spool in spools:
            rows=service.rows(spool)
            section=next(r for r in rows if r["name"]=="Printer-queue token candidates")
            self.assertIn("same SPdddd token: 1",section["lines"][0])
            links=[r for r in rows if r["kind"]=="printer_queue_action"]
            self.assertEqual(1,len(links))
            self.assertIs(links[0]["request"]["obj"],printer)
            entry=links[0]["request"]["entry"]
            self.assertEqual("SP0002",entry.token_candidate)
        model.run_command("DSPSPLCB SPLCB(*ALL/QSPSCB)")
        self.assertEqual("type_objects",model.screen)
        i=next(i for i,r in enumerate(model.rows()) if r.get("object") is spools[1])
        model.selected=i;model.open_row(i)
        self.assertEqual("Saved spool-control evidence",model.rows()[0]["name"])
        j=next(j for j,r in enumerate(model.rows()) if r["kind"]=="printer_queue_action")
        model.selected=j;model.open_row(j)
        self.assertEqual("Saved printer-queue key",model.rows()[0]["name"])
        model.back();self.assertEqual(j,model.selected)
        model.back();self.assertEqual(i,model.selected)

    def test_no_match_is_not_claimed_empty_and_bad_queue_is_withheld(self):
        printer,spools,image,queue,service,model=self.make(spool_tags=("SP9999",))
        rows=service.rows(spools[0])
        self.assertEqual("No recovered printer-key match",
                         next(r for r in rows if r["name"]=="No recovered printer-key match")["name"])
        self.assertFalse(any(r["kind"]=="printer_queue_action" for r in rows))
        printer,spools,image,queue,service,model=self.make()
        image.pages[12]=bytes(512)  # the sector with saved +0x420 root
        rows=service.rows(spools[0])
        summary=next(r for r in rows if r["name"]=="Printer-queue token candidates")
        self.assertIn("withheld from token matching: 1",summary["lines"][1])
        self.assertEqual("No recovered printer-key match",
                         next(r for r in rows if r["name"]=="No recovered printer-key match")["name"])

    def test_reverse_service_is_reused_between_origins(self):
        printer,spools,image,queue,service,model=self.make()
        before=len(image.reads)
        service.rows(spools[0])
        after=len(image.reads)
        service.rows(spools[1])
        self.assertLess(len(image.reads)-after,after-before)
        self.assertEqual(0,service._printer_withheld)


if __name__=="__main__":
    unittest.main()
