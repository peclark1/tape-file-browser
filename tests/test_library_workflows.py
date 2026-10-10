import unittest
from as400_libraries import LibraryExplorer
from as400_dasd import ContextDirectoryEntry
from as400_5250 import Guided5250
from test_type_capabilities import obj, inventory


def entry(lib, target, offset=0, address=True):
    return ContextDirectoryEntry(lib.name, lib.object_address, b'',
                                 target.object_type, target.object_subtype,
                                 target.object_address if address else None,
                                 target.name.encode('cp037'), offset, 2)


class LibraryTests(unittest.TestCase):
    def test_exact_scope_duplicates_missing_and_navigation(self):
        lib = obj('SAME', (4,1)); other = obj('SAME', (4,1), 20)
        target = obj('TARGET', (2,1), 30); duplicate = obj('TARGET', (2,1), 40)
        duplicate.object_address = target.object_address
        missing = obj('MISSING', (2,1), 50)
        inv = inventory([lib, other, target, duplicate])
        inv.context_entries = [entry(lib,target), entry(lib,missing,1), entry(other,target,2)]
        ex = LibraryExplorer(inv)
        rows = ex.rows(lib)
        refs = [r for r in rows if r.get('request',{}).get('entry')]
        self.assertEqual(2, len(refs))
        self.assertEqual([target, duplicate], [r['object'] for r in ex.rows(lib,entry=inv.context_entries[0]) if r.get('object')])
        self.assertEqual(1, len([r for r in ex.rows(lib,mode='MISSING') if r.get('request',{}).get('entry')]))
        model = Guided5250(inv,library_loader=ex.rows)
        model.show_evidence(dict(obj=lib),ex.rows)
        i = next(i for i,r in enumerate(model.rows()) if r.get('request',{}).get('entry'))
        model.selected = i; model.open_row(i); self.assertEqual(3,len(model.rows()))
        model.back(); self.assertEqual(i,model.selected)
        with self.assertRaises(ValueError): ex.rows(lib,entry=inv.context_entries[2])

    def test_paging_unknown_address_and_invalid_requests(self):
        lib = obj('LIB', (4,1)); target = obj('TARGET', (2,1), 30)
        inv = inventory([lib]); inv.context_entries = [entry(lib,target,i,False) for i in range(51)]
        ex = LibraryExplorer(inv)
        rows = ex.rows(lib); next_row = next(r for r in rows if r['name']=='Next')
        second = ex.rows(**next_row['request'])
        self.assertEqual(1,len([r for r in second if r.get('request',{}).get('entry')]))
        self.assertEqual('MISSING',ex.status(inv.context_entries[0]))
        for kwargs in ({'start':-1},{'start':'1'},{'mode':'BAD'}):
            with self.assertRaises(ValueError): ex.rows(lib,**kwargs)
        with self.assertRaises(ValueError): ex.rows(target)
