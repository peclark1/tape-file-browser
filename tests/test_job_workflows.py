import unittest
from as400_jobs import JobExplorer,job_description_names
from as400_5250 import Guided5250
from test_type_capabilities import obj,inventory,Image

class JobTests(unittest.TestCase):
    def fixture(self,user='*RQD'):
        b=bytearray(1024);b[0x100:0x102]=b'\x02\x40'
        b[0x102:0x120]=(user.ljust(10)+'QUEUE'.ljust(10)+'QGPL'.ljust(10)).encode('cp037')
        return b

    def test_queue_matches_orphans_decoys_reverse_and_back(self):
        d=obj('DESC',(0x19,3));q=obj('QUEUE',(0x0e,1),20);orphan=obj('QUEUE',(0x0e,1),30,None)
        decoy=obj('QUEUE',(0x0e,1),40,'OTHER');profile=obj('USER',(8,1),50)
        inv=inventory([d,q,orphan,decoy,profile]);im=Image([(d,self.fixture('USER'))]);ex=JobExplorer(im,inv)
        rows=ex.rows(d);self.assertEqual([q,orphan,profile],[r['object'] for r in rows if r.get('object')])
        self.assertEqual([d],[r['object'] for r in ex.rows(orphan) if r.get('object')]);self.assertNotIn(50,im.reads)
        model=Guided5250(inv,capability_loader=lambda o,sample=None:ex.rows(o))
        model.run_command('DSPJOBD JOBD(DESC)');model.selected=2;model.open_row(2)
        self.assertEqual('QUEUE',model.file);self.assertIn('unassigned',model.rows()[1]['note'])
        model.back();self.assertEqual(2,model.selected)
        model.run_command('WRKJOBQ JOBQ(*ORPHAN/QUEUE)');self.assertEqual('QUEUE',model.file)

    def test_malformed_fields_and_missing_queue(self):
        d=obj('DESC',(0x19,3));im=Image([(d,self.fixture())]);ex=JobExplorer(im,inventory([d]))
        self.assertEqual('Queue not recovered',ex.rows(d)[1]['name'])
        for cut in [0,0x100,0x11f]:
            with self.assertRaises(ValueError):job_description_names(self.fixture()[:cut])
        b=self.fixture();b[0x100]=0
        with self.assertRaises(ValueError):job_description_names(b)
        b=self.fixture();b[0x10c]=0
        with self.assertRaises(ValueError):job_description_names(b)
