"""Bounded record windows with explicit format choice for Guided 5250."""
from dataclasses import dataclass
from as400_dasd import DataSpaceLayout, DataSpaceRecord, MemberStoragePointers, decode_format_fields
from as400_capabilities import read_prefix, section, CapabilityExplorer

WINDOW_ENTRIES = 50
MAX_ENTRY_BYTES = 65536


def read_range(image, segment, offset, length, cache=None):
    """Read an exact virtual range; never concatenate around a missing extent."""
    if offset < 0 or length < 0 or offset + length > segment.pages * 512:
        raise ValueError('Range is outside the declared segment')
    previous_end = None
    for extent in segment.extents:
        if not isinstance(extent.virtual_address, int) or extent.pages < 1:
            raise ValueError('Invalid recovered virtual extent')
        if previous_end is not None and extent.virtual_address < previous_end:
            raise ValueError('Overlapping recovered virtual extents')
        previous_end = extent.virtual_address + extent.pages * 512
    cache = {} if cache is None else cache
    result = bytearray();position = segment.virtual_address + offset;remaining = length
    for extent in segment.extents:
        end = extent.virtual_address + extent.pages * 512
        if end <= position:
            continue
        if extent.virtual_address > position:
            raise ValueError('Missing virtual extent in requested record range')
        while remaining and position < end:
            relative = position - extent.virtual_address
            lba = extent.start_lba + relative // 512
            if lba not in cache:
                data = image.read_sector(lba).data
                if len(data) != 512:
                    raise ValueError('Short sector in requested record range')
                cache[lba] = data
            at = relative % 512;take = min(remaining, 512-at)
            result.extend(cache[lba][at:at+take]);position += take;remaining -= take
        if not remaining:
            return bytes(result)
    if remaining:
        raise ValueError('Incomplete recovered record range')
    return bytes(result)


@dataclass(frozen=True)
class RecordWindow:
    layout: DataSpaceLayout
    records: tuple
    start: int
    stop: int
    readable_entries: int
    warning: str


class StorageCatalog:
    """Immutable recovered identities indexed once per image, not every page."""
    def __init__(self,inventory,segments):
        self.qdds={};self.groups={}
        for obj in inventory.objects:
            if obj.type_code=='0B/90':self.qdds.setdefault(obj.object_address.key,[]).append(obj)
        for seg in getattr(segments,'segments',()):
            if seg.header.segment_type==0x03B4:self.groups.setdefault(seg.owner_key,[]).append(seg)


class RecordReader:
    def __init__(self, image, inventory, segments, member, catalog=None):
        if not member.is_member_cursor:
            raise ValueError('Record browsing requires a recovered member cursor')
        self.image = image
        pointers = MemberStoragePointers.from_cursor_segment(read_prefix(image, member.segment, 0x308))
        if pointers.data_space is None:
            raise ValueError('No direct QDDS pointer; record browsing will not substitute a name match')
        catalog = catalog or StorageCatalog(inventory,segments)
        matches = catalog.qdds.get(pointers.data_space.key,())
        if len(matches) != 1:
            raise ValueError(f'Direct QDDS pointer has {len(matches)} matching primaries; choose no implicit substitute')
        self.qdds = matches[0]
        self.layout = DataSpaceLayout.from_primary_segment(read_prefix(image,self.qdds.segment,512))
        if not 1 < self.layout.entry_length <= MAX_ENTRY_BYTES:
            raise ValueError('Entry length exceeds the supported 64 KiB bound')
        owned = sorted(catalog.groups.get(pointers.data_space.key,()),
                       key=lambda s:(s.virtual_address,s.start_lba))
        self.groups = [];self.warning = ''
        expected = None
        for seg in owned:
            if expected is not None and seg.virtual_address < expected:
                raise ValueError('Duplicate/overlapping data groups; no physical copy was chosen')
            if expected is not None and seg.virtual_address != expected:
                self.warning = 'Gap/overlap between data groups: later groups withheld.'
                break
            if seg.pages < 1:
                raise ValueError('Empty data group')
            self.groups.append(seg);expected = seg.virtual_address + seg.pages*512
        if not self.groups:
            raise ValueError('No recovered owner-matched 03B4 record groups')
        capacity = sum(s.pages*512-32 for s in self.groups)
        self.readable_entries = min(capacity//self.layout.entry_length,self.layout.expected_entries_with_default)
        if self.readable_entries < self.layout.expected_entries_with_default:
            self.warning += ' Recovered capacity is smaller than the declared entry range.'

    def window(self, start=0):
        if not isinstance(start,int) or start < 0 or start >= self.layout.expected_entries_with_default:
            raise ValueError('Start ordinal is outside the declared range')
        stop = min(start+WINDOW_ENTRIES,self.readable_entries)
        records=[];cache={};warning=self.warning
        for ordinal in range(start,stop):
            offset=ordinal*self.layout.entry_length;remaining=self.layout.entry_length;entry=bytearray()
            try:
                for seg in self.groups:
                    size=seg.pages*512-32
                    if offset >= size:
                        offset -= size;continue
                    take=min(remaining,size-offset)
                    entry.extend(read_range(self.image,seg,32+offset,take,cache))
                    remaining-=take;offset=0
                    if not remaining:break
                if remaining:raise ValueError('Incomplete entry')
            except (ValueError,OSError) as exc:
                warning += f' Entry {ordinal} withheld: {exc}; later entries in this window not read.'
                break
            records.append(DataSpaceRecord(ordinal,entry[0],bytes(entry[1:1+self.layout.record_length]),
                                           bytes(entry[1+self.layout.record_length:])))
        return RecordWindow(self.layout,tuple(records),start,max(start,stop),self.readable_entries,warning.strip())


def status_label(record):
    if record.ordinal == 0:return 'Default'
    return 'Live hint' if record.status == 0x80 else 'Deleted hint' if record.status == 0xC0 else f'Raw {record.status:02X}'


def field_value(field, data):
    raw=field.raw_value(data)
    if len(raw)!=field.storage_length:return '<outside record; schema mismatch>'
    if field.type_code==0x00 and (len(raw)>8 or field.decimal_positions>31):
        return '<unsupported binary width/scale; inspect hex>'
    if field.type_code in (2,3):
        if not raw or field.decimal_positions>31 or field.digits>63:
            return '<unsupported numeric dimensions; inspect hex>'
        if field.type_code==2:
            valid=(all(b&15<=9 for b in raw) and all(b>>4==15 for b in raw[:-1]) and raw[-1]>>4 in range(10,16))
        else:
            nibbles=[n for b in raw for n in (b>>4,b&15)]
            valid=all(n<=9 for n in nibbles[:-1]) and nibbles[-1] in range(10,16)
        if not valid:return '<invalid numeric encoding; inspect hex>'
    if field.type_code not in (0,2,3,4):return '<raw type; encoding unknown>'
    if len(raw)>256:return repr(raw[:256].decode('cp037'))+' [first 256 bytes only]' if field.type_code==4 else '<oversize numeric field; inspect hex>'
    return repr(field.decode_value(data)) if field.type_code==4 else field.decode_value(data)


def action(name, member, fmt=None, start=0, status='ALL', mode='records', note=''):
    return dict(kind='record_action',name=name,type='Records',note=note,
                request=dict(member=member,fmt=fmt,start=start,status=status,mode=mode))


class RecordExplorer:
    def __init__(self,image,inventory,segments):
        self.image,self.inventory,self.segments=image,inventory,segments
        self.capabilities=CapabilityExplorer(image,inventory,segments)
        self.catalog=StorageCatalog(inventory,segments)

    def rows(self,member,fmt=None,start=0,status='ALL',mode='choose'):
        if mode=='choose':return self.choices(member)
        if status not in ('ALL','LIVE','DELETED','UNKNOWN'):
            raise ValueError('Unknown record status filter')
        reader=RecordReader(self.image,self.inventory,self.segments,member,self.catalog)
        window=reader.window(start)
        if fmt is not None and fmt.type_code!='19/51':raise ValueError('Selected schema is not a record format')
        fields=decode_format_fields(read_prefix(self.image,fmt.segment,65536)) if fmt is not None else ()
        summary=[f'Member: {member.library_name or "<unassigned>"}/{member.member_file_name}({member.member_name})',
                 f'Cursor LBA: {member.segment.start_lba}; direct QDDS LBA: {reader.qdds.segment.start_lba}',
                 f'Format: {fmt.name} LBA {fmt.segment.start_lba}' if fmt else 'Format: raw bytes (no automatic choice)',
                 'A chosen candidate is not proof of schema ownership. Out-of-record fields remain visible.',
                 f'Declared entries incl. default: {window.layout.expected_entries_with_default}; capacity permits: {window.readable_entries}',
                 f'Window: {start}..{max(start,window.stop-1)}; recovered: {len(window.records)}; filter: {status}',
                 f'Payload bytes: {window.layout.record_length}; entry bytes: {window.layout.entry_length}',
                 'Ordinals count from the first recovered data group; a missing initial group is not independently ruled out.',
                 '80/C0 are V2R3 live/deleted hints. Other status forms stay raw, especially on older images.',
                 window.warning or 'No storage gap encountered in this window.']
        rows=[section('Summary',summary),action('Choose format',member,mode='choose')]
        for choice in ('ALL','LIVE','DELETED','UNKNOWN'):
            if choice!=status:rows.append(action(choice,member,fmt,start,choice,note='Filter this ordinal window'))
        if start:rows.append(action('Previous',member,fmt,max(0,start-WINDOW_ENTRIES),status))
        if start+WINDOW_ENTRIES<window.readable_entries:
            rows.append(action('Next',member,fmt,start+WINDOW_ENTRIES,status))
        for record in window.records:
            if status=='LIVE' and (record.ordinal==0 or record.status!=0x80):continue
            if status=='DELETED' and (record.ordinal==0 or record.status!=0xC0):continue
            if status=='UNKNOWN' and (record.ordinal==0 or record.status in (0x80,0xC0)):continue
            rows.append(dict(kind='record_entry',name=f'#{record.ordinal}',type=status_label(record),
                             note=f'status {record.status:02X}; {len(record.data)} bytes',record=record,fields=fields,
                             origin=summary[:4]))
        return rows

    def choices(self,member):
        rows=[section('Evidence',['Choose a format explicitly or keep raw bytes.',
              'Candidates follow exact FCB name/address occurrences, not proven ownership.',
              'Duplicate FILE/FMT primaries remain separate; nothing is selected automatically.']),
              action('Raw bytes',member)]
        for file in self.inventory.objects:
            if file.type_code!='19/01' or file.name.upper()!=member.member_file_name.upper() or file.library_name!=member.library_name:
                continue
            try:candidates=self.capabilities.file_rows(file)
            except (OSError,ValueError) as exc:
                rows.append(section('Unavailable',[str(exc)]));continue
            for row in candidates:
                if row.get('object'):
                    fmt=row['object'];rows.append(action(fmt.name,member,fmt,note=f'FMT LBA {fmt.segment.start_lba}; FILE LBA {file.segment.start_lba}; '+row['note']))
        return rows


def record_rows(record, fields, origin):
    rows=[section('Raw bytes',[*origin,f'Ordinal {record.ordinal}; status 0x{record.status:02X} ({status_label(record)})',
          'Exact payload (first 1024 bytes):',*[f'+{i:04X}: {record.data[i:i+16].hex(" ").upper()}' for i in range(0,min(len(record.data),1024),16)],
          f'Payload bytes: {len(record.data)}; extra entry bytes: {len(record.extra_raw)}',
          'Longer payloads are not fully shown in this preview.' if len(record.data)>1024 else 'All payload bytes shown.'])]
    for field in fields:
        raw=field.raw_value(record.data);value=field_value(field,record.data)
        row=section(field.name,[*origin,f'Ordinal {record.ordinal}; status 0x{record.status:02X}',
               f'Field {field.name}; {field.type_name}; offset {field.offset}; bytes {field.storage_length}',
               f'Digits {field.digits}; scale {field.decimal_positions}',f'Value: {value}',
               'Hex (first 256 bytes): '+raw[:256].hex(' ').upper(),
               'Field exceeds record bounds.' if len(raw)!=field.storage_length else 'CP037 is a display lens; no CCSID was decoded.'],note=value)
        row['type']=field.type_name;rows.append(row)
    return rows
