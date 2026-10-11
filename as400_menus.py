"""Bounded P/F menu qualified-name evidence; UIM internals are not decoded."""
import re
from as400_capabilities import read_prefix,section,object_row


def qualified_name(data,offset):
    if offset+20>len(data):raise ValueError('Truncated menu name/library pair')
    name=data[offset:offset+10].decode('cp037').rstrip(' ')
    library=data[offset+10:offset+20].decode('cp037').rstrip(' ')
    if not re.fullmatch(r'[A-Z#$@][A-Z0-9_#$@]{0,9}',name):raise ValueError('Unsupported menu target name')
    if library not in ('*LIBL','*CURLIB') and not re.fullmatch(r'[A-Z#$@][A-Z0-9_#$@]{0,9}',library):
        raise ValueError('Unsupported menu target library')
    return name,library


def menu_references(data):
    if len(data)<0x101:raise ValueError('Truncated menu header')
    variant=data[0x100]
    if variant==0xd7:roles=(('Program','02/01',0x130),)
    elif variant==0xc6:roles=(('Display file','19/01',0x130),('Message file','0E/03',0x144))
    else:return variant,()
    refs=[]
    for role,kind,at in roles:
        name,library=qualified_name(data,at)
        refs.append((role,kind,at,name,library))
    return variant,tuple(refs)


class MenuExplorer:
    def __init__(self,image,inventory):
        self.image,self.inventory=image,inventory

    def rows(self,obj):
        if obj.type_code!='19/16':raise ValueError('Not a menu primary')
        data=read_prefix(self.image,obj.segment,512)
        variant,refs=menu_references(data)
        rows=[section('Menu evidence',[f'Menu {obj.library_name or "<unassigned>"}/{obj.name}; LBA {obj.segment.start_lba}',
              f'Observed variant +0x100: {variant:02X}',
              'P/F qualified-name pairs are empirically corroborated, not object-address pointers.',
              'Candidates must match the role type and exact stored name; explicit libraries constrain matches.',
              '*LIBL/*CURLIB cannot be resolved offline; every matching recovered origin is retained.',
              'No menu option or program executes.'])]
        if not refs:
            rows.append(section('Variant not decoded',['UIM/other menu option and action structures remain unknown.',
                        'An empty candidate list does not mean this menu has no actions.']))
        for role,kind,at,name,library in refs:
            candidates=[o for o in self.inventory.objects if o.type_code==kind and o.name==name and
                        (library in ('*LIBL','*CURLIB') or o.library_name==library)]
            rows.append(section(role,[f'Stored pair +0x{at:X}: {library}/{name}',
                        f'Matching recovered primaries: {len(candidates)}',
                        'Name-based correlation only; library-list order and active object identity remain unknown.']))
            rows.extend(object_row(o,f'{role} qualified-name candidate at +0x{at:X}') for o in candidates)
        return rows
