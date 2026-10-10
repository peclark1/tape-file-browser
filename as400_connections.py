"""Navigate exact recovered address occurrences between DEVD, CTLD and LIND.

An address occurrence is evidence, not a decoded attachment/ownership field.
Only these non-credential configuration families are read by this service.
"""
from as400_capabilities import read_prefix,section,object_row
from as400_config import device_identity_candidates

FAMILIES={'10/01','12/01','11/01'}
PAIRS={('10/01','12/01'),('12/01','11/01')}
LIMIT=4096


class ConnectionExplorer:
    def __init__(self,image,inventory):
        self.image,self.inventory=image,inventory
        self._links=None
        self._errors=[]

    def _build(self):
        self._links=[];self._errors=[]
        objects=[o for o in self.inventory.objects if o.type_code in FAMILIES]
        targets={kind:{} for kind in FAMILIES}
        for obj in objects:
            raw=obj.object_address.to_bytes()
            if any(raw):targets[obj.type_code].setdefault(raw,[]).append(obj)
        for source in objects:
            target_kind={'10/01':'12/01','12/01':'11/01'}.get(source.type_code)
            if target_kind is None:continue
            try:prefix=read_prefix(self.image,source.segment,LIMIT)
            except (OSError,ValueError):
                self._errors.append(source);continue
            # Exclude common EPA identity/context fields; retain all duplicates.
            for at in range(0x100,len(prefix)-7):
                for target in targets[target_kind].get(prefix[at:at+8],()):
                    self._links.append((source,target,at))

    def rows(self,obj):
        if obj.type_code not in FAMILIES:raise ValueError('Unsupported configuration family')
        if self._links is None:self._build()
        lines=[f'{obj.name}; type {obj.type_code}; primary LBA {obj.segment.start_lba}',
               'Links match complete eight-byte internal addresses in +0x100..+0xFFF.',
               'They are candidate configuration relationships, NOT decoded attachment fields.',
               'Only DEVD -> CTLD and CTLD -> LIND type pairs are considered.',
               'All matching primaries/offsets are retained. Reverse links use the same evidence.',
               f'Unreadable source primaries: {len(self._errors)}; no link does not establish disconnection.']
        if obj.type_code=='10/01':
            try:
                for at,value,meaning in device_identity_candidates(read_prefix(self.image,obj.segment,512)):
                    lines.append(f'+0x{at:X}: {value!r}; {meaning}')
            except (OSError,ValueError) as exc:lines.append(str(exc))
        rows=[section('Relationship evidence',lines)]
        for source,target,at in self._links:
            if source is obj:rows.append(object_row(target,f'outgoing address occurrence +0x{at:X}; candidate only'))
            if target is obj:rows.append(object_row(source,f'incoming address occurrence +0x{at:X}; candidate only'))
        if len(rows)==1:rows.append(section('No recovered links',['No supported full-address occurrence in the bounded recovered bytes.',
                 'Other encodings, missing storage and release-specific structures remain possible.']))
        return rows
