import unittest
from types import SimpleNamespace as NS
from as400_afp import decode_resource, coded_font_references, field_pairs, AFPExplorer
from as400_5250 import Guided5250
from test_type_capabilities import obj, inventory, Image


def sf(code,payload=b'',flags=0):
    return b'\x5a'+(8+len(payload)).to_bytes(2,'big')+bytes.fromhex(code)+bytes([flags])+b'\0\1'+payload


def resource(stream):
    data=bytearray(512)+stream;data[256:260]=(len(data)-256).to_bytes(4,'big')
    return data+bytes((-len(data))%512)


def coded(control=b'\x19\x01',flags=0):
    group='CHARSET '.encode('cp500')+'CODEPAGE'.encode('cp500')+bytes(9)
    return resource(sf('D3A88A')+sf('D3A78A',control)+sf('D38C8A',group,flags)+sf('D3A98A'))


def extent(o,data):
    o.segment.extents=(NS(start_lba=o.segment.start_lba,virtual_address=o.segment.virtual_address,pages=len(data)//512),)


class AFPTests(unittest.TestCase):
    def test_framing_bounds_and_exact_wrapper_end(self):
        fields=decode_resource(coded());self.assertEqual(4,len(fields));self.assertEqual(512,fields[0].offset)
        for cut in (0,259,511,550):
            with self.assertRaises(ValueError):decode_resource(coded()[:cut])
        for at,value in ((512,0),(513,0xff),(514,7)):
            data=bytearray(coded());data[at]=value
            with self.assertRaises(ValueError):decode_resource(data)
        data=bytearray(coded());data[259]+=1
        with self.assertRaises(ValueError):decode_resource(data)

    def test_control_flags_reserved_bytes_and_scope(self):
        refs,warnings=coded_font_references(decode_resource(coded()))
        self.assertFalse(warnings);self.assertEqual(['CHARSET','CODEPAGE'],[r['name'] for r in refs])
        for data in (coded(b'\x18\x01'),coded(flags=0x80)):
            refs,warnings=coded_font_references(decode_resource(data));self.assertFalse(refs);self.assertTrue(warnings)
        fields=decode_resource(coded())
        refs,warnings=coded_font_references(fields[1:]);self.assertFalse(refs);self.assertTrue(warnings)
        pairs,warnings=field_pairs(fields);self.assertEqual({0:3,3:0},pairs);self.assertFalse(warnings)
        self.assertTrue(field_pairs(fields[:-1])[1])
        self.assertTrue(field_pairs(decode_resource(resource(sf('D3A989'))))[1])
        bad=bytearray(coded());bad[512+9+11+9+20]=1
        self.assertTrue(coded_font_references(decode_resource(bad))[1])

    def test_dependencies_duplicates_missing_kind_mismatch_and_back(self):
        font=obj('CODED',(0x19,0x26));charset=obj('CHARSET',(0x19,0x26),30)
        duplicate=obj('CHARSET',(0x19,0x26),40,'OTHER');wrong=obj('CODEPAGE',(0x19,0x26),50)
        data=coded();cs=resource(sf('D3A889')+sf('D3A989'))
        for o,d in [(font,data),(charset,cs),(duplicate,cs),(wrong,cs)]:extent(o,d)
        inv=inventory([font,charset,duplicate,wrong]);ex=AFPExplorer(Image([(font,data),(charset,cs),(duplicate,cs),(wrong,cs)]),inv)
        model=Guided5250(inv,afp_loader=ex.rows);model.run_command('DSPAFP OBJ(QGPL/CODED)')
        model.selected=3;model.open_row(3)
        self.assertEqual([charset,duplicate],[r['object'] for r in model.rows() if r.get('object')])
        self.assertTrue(any(r['name']=='Resource kind mismatch' for r in model.rows()))
        i=next(i for i,r in enumerate(model.rows()) if r.get('object') is charset)
        model.selected=i;model.open_row(i);self.assertEqual('AFP resource',model.rows()[0]['name'])
        model.back();self.assertEqual(i,model.selected);model.back();self.assertEqual(3,model.selected)
        ex=AFPExplorer(Image([(font,data)]),inventory([font]))
        self.assertEqual(2,sum(r['name']=='Resource missing' for r in ex.rows(font,field=2)))
        for kwargs in ({'start':-1},{'field':99},{'byte_start':-1}):
            with self.assertRaises(ValueError):ex.rows(font,**kwargs)

    def test_field_and_payload_pagination(self):
        o=obj('FORM',(0x19,0x28));data=resource(sf('D3EEEE',b'x'*300)*51);extent(o,data)
        ex=AFPExplorer(Image([(o,data)]),inventory([o]))
        next_row=next(r for r in ex.rows(o) if r['name']=='Next')
        self.assertEqual(3,len(ex.rows(**next_row['request'])))
        next_bytes=next(r for r in ex.rows(o,field=0) if r['name']=='Next bytes')
        self.assertEqual('Payload +0100',ex.rows(**next_bytes['request'])[2]['name'])
