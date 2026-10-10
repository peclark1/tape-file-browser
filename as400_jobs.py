"""JOBD qualified queue-name evidence with conservative reverse JOBQ navigation."""
import re
from as400_capabilities import read_prefix,section,object_row
from as400_menus import qualified_name


def job_description_names(data):
    if len(data)<0x120:raise ValueError('Truncated job-description name fields')
    if data[0x100:0x102]!=b'\x02\x40':raise ValueError('Unsupported job-description prefix')
    queue,library=qualified_name(data,0x10c)
    user=data[0x102:0x10c].decode('cp037').rstrip(' ')
    if not re.fullmatch(r'\*?[A-Z#$@][A-Z0-9_#$@]{0,9}',user):raise ValueError('Unsupported profile-name candidate')
    return user,queue,library


class JobExplorer:
    def __init__(self,image,inventory):
        self.image,self.inventory=image,inventory;self._descriptions=None

    def _load(self):
        if self._descriptions is not None:return
        self._descriptions=[]
        for obj in self.inventory.objects:
            if obj.type_code!='19/03':continue
            try:names=job_description_names(read_prefix(self.image,obj.segment,512));error=None
            except (OSError,ValueError) as exc:names=None;error=str(exc)
            self._descriptions.append((obj,names,error))

    def rows(self,obj):
        self._load()
        if obj.type_code=='19/03':return self.description_rows(obj)
        if obj.type_code!='0E/01':raise ValueError('Not a job description or job queue')
        rows=[section('Queue relationships',[f'JOBQ {obj.library_name or "<unassigned>"}/{obj.name}; LBA {obj.segment.start_lba}',
              'These are saved job-description name references, not jobs currently waiting or running.',
              'No runtime queue contents, routing, authority or active state is inferred.'])]
        for desc,names,error in self._descriptions:
            if names is None:continue
            user,queue,library=names
            if queue!=obj.name:continue
            if obj.library_name==library:
                note='stored queue name/library match; association remains empirical'
            elif obj.library_name is None:
                note=f'unassigned queue candidate; JOBD stores library {library}'
            elif library in ('*LIBL','*CURLIB'):
                note=f'{library} candidate; runtime library list unknown'
            else:continue
            rows.append(object_row(desc,note))
        if len(rows)==1:rows.append(section('No referring descriptions',['No supported recovered JOBD names this queue under the stated matching rules.']))
        return rows

    def description_rows(self,obj):
        names=job_description_names(read_prefix(self.image,obj.segment,512))
        user,queue,library=names
        rows=[section('Description evidence',[f'JOBD {obj.library_name or "<unassigned>"}/{obj.name}; LBA {obj.segment.start_lba}',
              f'Profile-name candidate +0x102: {user}',f'Queue name/library +0x10C/+0x116: {library}/{queue}',
              'Fixed-width name evidence, not full job-description attribute decoding.',
              'Queue/library matching is not an internal-address pointer. All duplicate origins remain selectable.',
              'Special profile values are retained as tokens; no runtime profile or authority is inferred.'])]
        matches=[]
        for target in self.inventory.objects:
            if target.type_code!='0E/01' or target.name!=queue:continue
            if target.library_name==library:note='exact stored queue/library name candidate'
            elif target.library_name is None:note=f'unassigned candidate; expected library {library}'
            elif library in ('*LIBL','*CURLIB'):note=f'{library} candidate; runtime order unknown'
            else:continue
            matches.append(object_row(target,note))
        rows.extend(matches)
        if not matches:rows.append(section('Queue not recovered',[f'No matching queue candidate for {library}/{queue}; the stored reference remains visible.']))
        if not user.startswith('*'):
            profiles=[o for o in self.inventory.objects if o.type_code=='08/01' and o.name==user]
            rows.append(section('Profile correlation',[f'{len(profiles)} profile identities match {user}. Name correlation only; credentials are never read.']))
            rows.extend(object_row(o,'profile-name candidate only; safe identity view') for o in profiles)
        return rows
