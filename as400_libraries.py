"""Library recovery diagnostics from reconstructed context references."""
from collections import Counter, defaultdict
from as400_capabilities import object_row, section


def action(name, obj, **request):
    return dict(kind='library_action', name=name, type='Recovery', note='',
                request=dict(obj=obj, **request))


class LibraryExplorer:
    def __init__(self, inventory):
        self.inventory = inventory
        self._objects = defaultdict(list)
        self._entries = defaultdict(list)
        for obj in inventory.objects:
            self._objects[(obj.object_address.key, obj.object_type, obj.object_subtype)].append(obj)
        for entry in inventory.context_entries:
            self._entries[entry.context_address.key].append(entry)

    def candidates(self, entry):
        if entry.object_address is None:
            return ()
        return self._objects.get((entry.object_address.key, entry.object_type, entry.object_subtype), ())

    def status(self, entry):
        count = len(self.candidates(entry))
        return 'AMBIGUOUS' if count > 1 else 'RESOLVED' if count else 'MISSING'

    def rows(self, obj, start=0, mode='ALL', entry=None):
        if obj.type_code != '04/01':
            raise ValueError('Not a library context')
        if not isinstance(start, int) or start < 0 or mode not in ('ALL', 'MISSING', 'AMBIGUOUS', 'RESOLVED'):
            raise ValueError('Invalid library recovery window')
        entries = self._entries.get(obj.object_address.key, ())
        if entry is not None:
            if not any(e is entry for e in entries):
                raise ValueError('Entry is outside the selected context')
            matches = self.candidates(entry)
            rows = [section('Context reference', [
                f'LIB {obj.name}; context LBA {obj.segment.start_lba}',
                f'{entry.display_name_hint or "<undecoded name>"}; {entry.type_code}; terminal +0x{entry.terminal_element_offset:X}',
                f'{self.status(entry)}: {len(matches)} exact address/type primary candidates; owned segments {entry.owned_segment_count}',
                'Address and name are reconstructed context-index hints. All matching primaries are retained.',
                'Owned segments alone do not recover a missing primary or certify an active object.',
            ])]
            rows.extend(object_row(candidate, 'exact reconstructed address/type candidate') for candidate in matches)
            return rows
        counts = Counter(self.status(e) for e in entries)
        warnings = getattr(self.inventory, 'context_warnings', {}).get(obj.name, ())
        rows = [section('Library recovery', [
            f'LIB {obj.name}; context LBA {obj.segment.start_lba}; recovered references {len(entries)}',
            f'Resolved {counts["RESOLVED"]}; missing primary {counts["MISSING"]}; ambiguous {counts["AMBIGUOUS"]}',
            'Entries are scoped by full context address, not shared library name.',
            'Recovered references are not a completeness or live-object guarantee.',
            'Warnings below are recorded by library NAME and may include another same-name context.',
            *warnings,
        ])]
        rows.extend(action('Show ' + choice.lower(), obj, mode=choice) for choice in ('ALL', 'MISSING', 'AMBIGUOUS', 'RESOLVED') if choice != mode)
        selected = [e for e in entries if mode == 'ALL' or self.status(e) == mode]
        if start:
            rows.append(action('Previous', obj, start=max(0, start-50), mode=mode))
        if start+50 < len(selected):
            rows.append(action('Next', obj, start=start+50, mode=mode))
        for e in selected[start:start+50]:
            row = action(e.display_name_hint or '<undecoded name>', obj, mode=mode, entry=e)
            row['type'] = e.type_code
            row['note'] = f'{self.status(e)}; terminal +0x{e.terminal_element_offset:X}; owned segments {e.owned_segment_count}'
            rows.append(row)
        if not selected:
            rows.append(section('No recovered references', ['No entries match this filter; this does not prove an empty original library.']))
        return rows
