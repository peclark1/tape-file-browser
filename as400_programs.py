"""Program reference exploration; does not decode or execute MI instructions."""
from as400_cmd import candidate_processor
from as400_menus import menu_references
from as400_capabilities import read_prefix,section,object_row


class ProgramExplorer:
    def __init__(self,image,inventory):
        self.image,self.inventory=image,inventory;self._references=None;self._errors=0

    def _build(self):
        self._references={}
        for source in self.inventory.objects:
            if source.type_code not in ('19/05','19/16'):continue
            try:
                prefix=read_prefix(self.image,source.segment,512)
                if source.type_code=='19/05':
                    pair=candidate_processor(prefix)
                    if pair:
                        name,library=pair
                        self._references.setdefault((name,library),[]).append((source,'CMD processor-name candidate +0x102/+0x10C'))
                else:
                    _,refs=menu_references(prefix)
                    for role,kind,at,name,library in refs:
                        if kind=='02/01':self._references.setdefault((name,library),[]).append((source,f'P-menu qualified-name candidate +0x{at:X}'))
            except (OSError,ValueError):self._errors+=1

    def rows(self,obj):
        if obj.type_code!='02/01':raise ValueError('Not a program primary')
        if self._references is None:self._build()
        refs=[]
        for (name,library),sources in self._references.items():
            if name!=obj.name:continue
            if obj.library_name==library:qualifier='stored library-name match'
            elif obj.library_name is None:qualifier=f'unassigned program; expected library {library}'
            elif library in ('*LIBL','*CURLIB'):qualifier='runtime library list unknown'
            else:continue
            refs.extend((source,note+'; '+qualifier)for source,note in sources)
        rows=[section('Program references',[f'PGM {obj.library_name or "<unassigned>"}/{obj.name}; LBA {obj.segment.start_lba}',
              f'Recovered CMD/P-menu name-reference candidates: {len(refs)}; unreadable/unsupported source primaries: {self._errors}',
              'This is a reverse name-reference view, not a call graph or proof of CPP linkage.',
              'Select a command to inspect its recovered parameter/prompt definition, or a P menu for its target evidence.',
              'MI instructions, ODT, program attributes and dynamic callers remain undecoded.',
              'Duplicate program primaries receive the same name-based candidates; no active copy is selected.'])]
        rows.extend(object_row(source,note)for source,note in refs)
        if not refs:rows.append(section('No name references',['No supported command or P-menu reference matched under the stated rules; not proof that this program is unused.']))
        return rows
