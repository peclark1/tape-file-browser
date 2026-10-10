import unittest
from as400_programs import ProgramExplorer
from as400_5250 import Guided5250
from as400_cmd import command_exploration
from test_type_capabilities import obj,inventory,Image
from test_command_exploration import primary

class ProgramTests(unittest.TestCase):
    def test_reverse_reference_scope_and_command_workflow(self):
        p=obj('PROCESSOR',(2,1));cmd=obj('COMMAND',(0x19,5),20);decoy=obj('PROCESSOR',(2,1),30,'OTHER');profile=obj('SECRET',(8,1),40)
        cmd.segment.pages=4
        data=primary();inv=inventory([p,cmd,decoy,profile]);im=Image([(cmd,data)])
        ex=ProgramExplorer(im,inv);self.assertEqual([cmd],[r['object'] for r in ex.rows(p) if r.get('object')]);self.assertEqual('No name references',ex.rows(decoy)[1]['name']);self.assertNotIn(40,im.reads)
        model=Guided5250(inv,capability_loader=lambda o,sample=None:ex.rows(o),command_definition_loader=lambda o:command_exploration(o,data))
        model.run_command('DSPPGM PGM(QGPL/PROCESSOR)');model.selected=1;model.open_row(1)
        self.assertEqual('command_definition',model.screen);model.back();self.assertEqual(1,model.selected)
        with self.assertRaises(ValueError):ex.rows(profile)

    def test_unassigned_and_missing_source_bytes(self):
        p=obj('PROCESSOR',(2,1),library=None);cmd=obj('COMMAND',(0x19,5),20)
        ex=ProgramExplorer(Image([(cmd,primary())]),inventory([p,cmd]));self.assertIn('unassigned',ex.rows(p)[1]['note'])
        ex=ProgramExplorer(Image([]),inventory([p,cmd]));self.assertEqual('No name references',ex.rows(p)[1]['name']);self.assertEqual(1,ex._errors)
