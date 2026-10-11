"""RCT index -> corroborated opaque records; no service-action interpretation."""
from dataclasses import dataclass
from as400_dasd import decode_context_machine_index
from as400_capabilities import read_prefix, section
from as400_records import read_range


@dataclass(frozen=True)
class ReferenceCodeEntry:
    key: bytes
    offset: int
    terminal_offset: int


def decode_reference_index(data, virtual_address):
    if len(data) < 0x42e or data[0x100:0x106] != bytes.fromhex('6000000c0008'):
        raise ValueError('Unsupported or truncated RCT header')
    count = int.from_bytes(data[0x106:0x10a], 'big')
    if not count:
        return (), ('Stored count is zero; no tree traversed.',)
    tree = decode_context_machine_index(
        data, root_offset=int.from_bytes(data[0x420:0x426], 'big')-virtual_address,
        page_size=int.from_bytes(data[0x42a:0x42e], 'big'), strict_pages=True)
    entries = []; warnings = list(tree.warnings)
    for terminal in tree.entries:
        if len(terminal.raw) != 12:
            warnings.append(f'Unsupported terminal length at +0x{terminal.terminal_element_offset:X}; withheld')
            continue
        entries.append(ReferenceCodeEntry(terminal.raw[:8], int.from_bytes(terminal.raw[8:12], 'big'), terminal.terminal_element_offset))
    if len(entries) != count:
        warnings.append(f'Stored count {count}; recovered supported entries {len(entries)}')
    return tuple(entries), tuple(dict.fromkeys(warnings))


def validate_reference_record(entry, record):
    """Length and repeated key only. Record body semantics remain unknown."""
    if len(record) < 8 or int.from_bytes(record[:2], 'big') != len(record):
        raise ValueError('Truncated or inconsistent RCT record length')
    key = entry.key
    if len(key) != 8:
        raise ValueError('Invalid RCT key length')
    if key[0] in (0xc4, 0xc6) and key[5:] == b'\0'*3:
        matches = record[2:6] == key[1:5]
    elif key[0] == 0xe2 and key[3:] == b'\0'*5:
        matches = record[2:4] == key[1:3]
    elif key[0] == 0xd7 and key[6:] == b'\0'*2:
        matches = record[2:8] == key[:1]+key[2:6]+key[1:2]
    else:
        raise ValueError('Unsupported RCT key variant; record withheld')
    if not matches:
        raise ValueError('RCT repeated key mismatch; record withheld')
    return bytes(record)


def action(name, obj, **request):
    return dict(kind='reference_action', name=name, type='RCT evidence', note='',
                request=dict(obj=obj, **request))


class ReferenceCodeExplorer:
    def __init__(self, image, inventory, segments):
        self.image = image
        self._indexes = {}; self._storage = {}
        for segment in segments.segments:
            if segment.header.segment_type == 0x0280:
                self._storage.setdefault(segment.owner_key, []).append(segment)

    def entries(self, obj):
        key = obj.segment.start_lba
        if key not in self._indexes:
            self._indexes[key] = decode_reference_index(read_prefix(self.image, obj.segment, 8*1024*1024), obj.segment.virtual_address)
        return self._indexes[key]

    def record(self, obj, entry):
        candidates = self._storage.get(obj.segment.owner_key, ())
        if len(candidates) != 1:
            raise ValueError(f'Exact-owner 0280 storage candidates: {len(candidates)}; no substitute selected')
        segment = candidates[0]
        length = int.from_bytes(read_range(self.image, segment, 32+entry.offset, 2), 'big')
        if not 8 <= length <= 65535:
            raise ValueError('Invalid RCT record length')
        return validate_reference_record(entry, read_range(self.image, segment, 32+entry.offset, length))

    def rows(self, obj, start=0, keyhex='', entry=None, byte_start=0):
        if obj.type_code != '0E/08':
            raise ValueError('Not a reference code translate table')
        if not isinstance(start, int) or start < 0 or not isinstance(byte_start, int) or byte_start < 0:
            raise ValueError('Invalid RCT window')
        try:
            prefix = bytes.fromhex(keyhex)
        except ValueError:
            raise ValueError('KEYHEX must contain whole hexadecimal bytes') from None
        if len(prefix) > 8:
            raise ValueError('KEYHEX exceeds the eight-byte index key')
        if entry is not None:
            record = self.record(obj, entry)
            rows = [section('Corroborated record', [
                f'RCT {obj.name}; primary LBA {obj.segment.start_lba}; key {entry.key.hex().upper()}',
                f'Exact-owner secondary +0x{32+entry.offset:X}; inclusive u16 length {len(record)}',
                'Repeated key matches the supported D/F/S/P layout. Other fields remain opaque.',
                'Hex and CP037 are byte-display lenses, not decoded service advice or certified text.',
                f'Byte window {byte_start}..{min(byte_start+256,len(record))} (end exclusive).'])]
            if byte_start:
                rows.append(action('Previous bytes', obj, entry=entry, byte_start=max(0,byte_start-256)))
            if byte_start+256 < len(record):
                rows.append(action('Next bytes', obj, entry=entry, byte_start=byte_start+256))
            for at in range(byte_start, min(byte_start+256, len(record)), 32):
                chunk = record[at:at+32]
                rows.append(section(f'+{at:04X}', [chunk.hex(' ').upper(), repr(chunk.decode('cp037'))]))
            return rows
        entries, warnings = self.entries(obj)
        matches = [e for e in entries if e.key.startswith(prefix)]
        rows = [section('Reference index', [
            f'RCT {obj.name}; primary LBA {obj.segment.start_lba}; entries {len(entries)}; matching {len(matches)}',
            'Twelve-byte terminals: eight-byte key and empirical secondary offset.',
            'Select a key for exact-owner, length and repeated-key validation; missing storage remains explicit.',
            'D/F/S/P key prefixes are observed variants; service meanings and record attributes remain undecoded.',
            *warnings])]
        if start:
            rows.append(action('Previous', obj, start=max(0,start-50), keyhex=keyhex))
        if start+50 < len(matches):
            rows.append(action('Next', obj, start=start+50, keyhex=keyhex))
        for e in matches[start:start+50]:
            row = action(e.key.hex().upper(), obj, entry=e)
            row['note'] = f'terminal +0x{e.terminal_offset:X}; secondary offset +0x{e.offset:X}'
            rows.append(row)
        return rows
