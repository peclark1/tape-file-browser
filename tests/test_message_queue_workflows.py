import unittest
from types import SimpleNamespace as NS
from as400_message_queues import MessageQueueExplorer,message_references
from as400_messages import MessageExplorer
from as400_5250 import Guided5250
from test_type_capabilities import obj,inventory,Image
from test_message_workflows import fixture

class MessageQueueTests(unittest.TestCase):
    def test_compound_reference_boundaries_and_decoys(self):
        b=bytearray(512);pattern=b'\x09'+('MSGS'.ljust(10)+'*LIBL'.ljust(10)).encode('cp037')+b'\x06'+'TST0001'.encode('cp037')
        b[0x100:0x100+len(pattern)]=pattern
        refs=message_references(b);self.assertEqual(1,len(refs));self.assertEqual('TST0001',refs[0].identifier)
        self.assertFalse(message_references(b[:0x11c]))
        for offset in [0x100,0x115,0x116]:
            bad=bytearray(b);bad[offset]=0;self.assertFalse(message_references(bad))
        b[:len(pattern)]=pattern;self.assertEqual(1,len(message_references(b)))

    def test_queue_reference_to_exact_id_and_back(self):
        q=obj('QUEUE',(0x19,2));m=obj('MSGS',(0x0e,3),20)
        m.segment.virtual_address=0x100000;m.segment.owner_key='owner'
        d=fixture();m.segment.extents=(NS(start_lba=20,virtual_address=0x100000,pages=len(d)//512),)
        b=bytearray(1024);b[0x100:0x11d]=b'\x09'+('MSGS'.ljust(10)+'QGPL'.ljust(10)).encode('cp037')+b'\x06'+'TST0001'.encode('cp037')
        inv=inventory([q,m]);im=Image([(q,b),(m,d)]);queues=MessageQueueExplorer(im,inv);messages=MessageExplorer(im,inv,NS(segments=[]))
        model=Guided5250(inv,queue_loader=queues.rows,message_loader=messages.rows)
        model.run_command('DSPMSG MSGQ(QUEUE)');model.selected=1;model.open_row(1);model.open_row(1)
        self.assertEqual(['Summary','TST0001'],[r['name'] for r in model.rows()]);model.back();model.back();self.assertEqual(1,model.selected)
        queues._definitions[m.segment.start_lba]=(set(),())
        self.assertEqual('ID not recovered',queues.reference_rows(q,message_references(b)[0])[1]['name'])
