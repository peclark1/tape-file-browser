"""Invented compiled-command records: bounded references, never original bytes."""
from types import SimpleNamespace as NS
import unittest

from as400_cmd import (recover_definition_links, command_exploration,
                       parameter_information_lines, prompt_form_lines)
from as400_5250 import Guided5250, _draw, run_curses
from as400_dasd_tool import _tui_command_definition
from unittest.mock import patch
import curses
from test_command_exploration import command, Screen
from test_as400_5250 import FakeInventory


def put16(data, at, value):
    data[at:at+2] = value.to_bytes(2, "big")


def put_record(data, at, text, *, message=None):
    raw = text.encode("cp037")
    if message is not None:
        data[at:at+11] = bytes(2) + message.ljust(7).encode("cp037") + bytes(2)
        put16(data, at+11, len(raw)); data[at+13:at+13+len(raw)] = raw
    else:
        put16(data, at, len(raw)); data[at+2:at+2+len(raw)] = raw


def fixture():
    data = bytearray(4096)
    data[0x17E:0x182] = bytes((0x81,0,3,0))
    for ordinal, (name, start) in enumerate(zip(("ALPHA", "BETA", "GAMMA"), (0x19C,0x1FC,0x25C)),1):
        data[start:start+10] = name.ljust(10).encode("cp037")
        put16(data,start+10,ordinal)
        put16(data,start-27,(start+96-27-0x100) if ordinal<3 else 0)
        put16(data,start+12,{1:0x141,2:0,3:0xE1}[ordinal])  # linked order 1,3,2
        put16(data,start-6,0x600 + ordinal*0x80 - 0x100)
        put_record(data,0x600+ordinal*0x80,('Choose sample','Set count','')[ordinal-1],message='TST000'+str(ordinal))
        data[start+14]=0xFF
    # ALPHA tail: default reference, value list, display-hint reference.
    at=0x1AA
    data[at:at+6]=bytes.fromhex('01 00 06 05 08 00'); at+=6
    data[at:at+17]=bytes.fromhex('02 00 11 00 02 00 00 85 08 00 08 00 85 08 20 08 20');at+=17
    data[at:at+8]=bytes.fromhex('06 00 08 20 00 01 07 00');at+=8
    data[at]=0xFF
    put_record(data,0x800,'*ONE, *TWO',message='')
    put_record(data,0x900,'*ONE');put_record(data,0x920,'*TWO')
    return data


class PromptLinkTests(unittest.TestCase):
    def test_exact_references_labels_hint_values_and_independent_order(self):
        b=fixture();original=bytes(b);links=recover_definition_links(b)
        self.assertEqual((1,3,2),links.prompt_order)
        self.assertEqual(3,len(links.parameters))
        p=links.parameters[0]
        self.assertEqual(('Choose sample','TST0001',0x680),(p.prompt.text,p.prompt.message_id,p.prompt.offset))
        self.assertEqual('*ONE, *TWO',p.hint.text)
        self.assertEqual('*ONE',p.default_candidate.text)
        self.assertEqual(['*ONE','*TWO'],[v.text for v in p.value_candidates])
        self.assertFalse(p.issues)
        self.assertEqual('',links.parameters[2].prompt.text)
        self.assertEqual(original,bytes(b))

    def test_relocation_follows_reference_not_nearest_printable_string(self):
        b=fixture();put_record(b,0xB00,'Relocated title',message='TST9999')
        put16(b,0x196,0xA00)
        self.assertEqual('Relocated title',recover_definition_links(b).parameters[0].prompt.text)
        # Old text still exists; it must not be chosen after the reference breaks.
        put16(b,0x196,0xFFFF)
        result=recover_definition_links(b).parameters[0]
        self.assertIsNone(result.prompt)
        self.assertIn('outside',' '.join(result.issues))

    def test_primary_chain_cycles_omissions_foreign_targets_fail_closed(self):
        for at,value in ((0x181,0x81),(0x181,0),(0x181,0xF00)):
            b=fixture();put16(b,at,value)
            self.assertFalse(recover_definition_links(b).parameters)

    def test_secondary_chain_corruption_falls_back_with_diagnostic(self):
        b=fixture();put16(b,0x1A8,0x81)
        links=recover_definition_links(b)
        self.assertEqual((1,2,3),links.prompt_order)
        self.assertIn('using stored ordinals',links.reason)
        self.assertEqual('Choose sample',links.parameters[0].prompt.text)

    def test_text_record_bounds_charset_and_blank_are_distinct(self):
        self.assertFalse(recover_definition_links(bytes(20)).parameters)
        for mutation in ('length','control','id','descriptor_pointer','bound','zero'):
            b=fixture()
            if mutation=='length':put16(b,0x68B,0xFFFF)
            elif mutation=='control':b[0x68D]=0
            elif mutation=='id':b[0x682]=0
            elif mutation=='descriptor_pointer':put16(b,0x196,0x81)
            elif mutation=='bound':put16(b,0x196,0xF00)
            elif mutation=='zero':put16(b,0x196,0)
            self.assertIsNone(recover_definition_links(b).parameters[0].prompt,mutation)
        truncated=fixture()[:0x690]
        self.assertIsNone(recover_definition_links(truncated).parameters[0].prompt)
        # A blank text with a valid record is represented, not guessed.
        self.assertEqual('',recover_definition_links(fixture()).parameters[2].prompt.text)

    def test_bad_tlv_boundaries_duplicates_and_terminator_withhold_tail(self):
        for mutation in ('zero','overflow','duplicate','unterminated'):
            b=fixture()
            if mutation=='zero':put16(b,0x1AB,0)
            elif mutation=='overflow':put16(b,0x1AB,0xFFFF)
            elif mutation=='duplicate':b[0x1B0]=1
            else:b[0x1C9]=0  # replace FF; next zero-length tail is invalid
            item=recover_definition_links(b).parameters[0]
            self.assertIsNone(item.default_candidate,mutation)
            self.assertEqual((),item.value_candidates,mutation)
            self.assertTrue(item.issues,mutation)
            self.assertIsNotNone(item.prompt)

    def test_value_list_count_and_one_bad_pointer_never_yield_partial_choices(self):
        for at,value in ((0x1B3,3),(0x1B8,0xFFFF)):
            b=fixture();put16(b,at,value)
            item=recover_definition_links(b).parameters[0]
            self.assertEqual((),item.value_candidates)
            self.assertTrue(item.issues)
        b=fixture();b[0x902]=0
        item=recover_definition_links(b).parameters[0]
        self.assertIsNone(item.default_candidate)
        self.assertEqual((),item.value_candidates)

    def test_prompt_references_across_noncontiguous_extents(self):
        data = bytes(fixture())
        obj = command()
        obj.segment.extents = (NS(start_lba=100, pages=2), NS(start_lba=900, pages=6))
        pages = dict(zip([100,101,900,901,902,903,904,905],
                         [data[i:i+512] for i in range(0,len(data),512)]))
        reads = []
        def read_sector(lba):
            reads.append(lba)
            return NS(data=pages[lba])
        view = _tui_command_definition({'image':NS(read_sector=read_sector)},obj)
        item = view.definition.parameters[0]
        self.assertEqual('Choose sample',item.prompt.text)
        self.assertEqual('*ONE',item.default_candidate.text)
        self.assertEqual(list(pages),reads)

    def test_actual_key_loop_selects_prompt_parameter_and_restores_selection(self):
        obj=command();inv=FakeInventory();inv.objects.append(obj)
        model=Guided5250(inv,command_definition_loader=lambda o:command_exploration(o,fixture()))
        model.run_command('DSPCMD CMD(QGPL/TEST)')
        index=next(i for i,r in enumerate(model.rows()) if r['name']=='Prompt form')
        model.selected=index;model.open_row(index)
        screen=Screen(16,64,keys=(curses.KEY_DOWN,10,2,curses.KEY_F3))
        with patch('curses.curs_set'):
            run_curses(screen,model)
        self.assertEqual('command_prompts',model.screen)
        self.assertEqual('GAMMA',model.rows()[model.selected]['name'])

    def test_read_limit_no_follow_outside_8k(self):
        b=fixture()+bytearray(6000)
        put_record(b,0x2200,'Outside sample',message='TST0001')
        put16(b,0x196,0x2100)
        self.assertIsNone(recover_definition_links(b).parameters[0].prompt)

    def test_prompt_form_and_parameter_drilldown_share_attributes_and_keep_back(self):
        obj=command(); inv=FakeInventory(); inv.objects.append(obj)
        model=Guided5250(inv,command_definition_loader=lambda o:command_exploration(o,fixture()))
        model.run_command('DSPCMD CMD(QGPL/TEST)')
        rows=model.rows();index=next(i for i,r in enumerate(rows) if r['name']=='Prompt form')
        model.selected=index;model.open_row(index)
        self.assertEqual('command_prompts',model.screen)
        self.assertEqual(['ALPHA','GAMMA','BETA'],[r['name'] for r in model.rows()])
        row=model.rows()[0]
        self.assertEqual('Choose sample',row['note'])
        self.assertEqual('*ONE, *TWO',row['hint'])
        self.assertEqual("'*ONE'",row['default'])
        self.assertEqual('[stored prompt blank]',model.rows()[1]['note'])
        for height,width in ((16,64),(24,80)):
            screen=Screen(height,width)
            for selected in range(len(model.rows())):
                model.selected=selected;_draw(screen,model)
        model.selected=0;model.open_row(0)
        self.assertIn('Choose sample',' '.join(model.detail))
        model.back();self.assertEqual(0,model.selected)
        model.back();self.assertEqual(index,model.selected)
        index=next(i for i,r in enumerate(model.rows()) if r['name']=='ALPHA')
        self.assertEqual('Choose sample',model.rows()[index]['note'])
        model.open_row(index)
        details='\n'.join(model.detail)
        self.assertIn('+0x0680',details)
        self.assertIn('Tag 01 default candidate',details)
        self.assertIn('message-file pointers',details)
        model.back();model.back();self.assertEqual('libraries',model.screen)
