"""Bounded SBSD/CLS fixed-width name-occurrence navigation.

This is *not* a decoder for IBM subsystem entries or class assignments.
It only cross-checks exact ten-byte EBCDIC padded name occurrences against
other independently recovered object identities. No association is promoted
to an internal pointer, owned object, active job queue, or run-time state.
"""
import re
from as400_capabilities import object_row, read_prefix, section


TARGET_CODES = ("0E/01", "19/04", "02/01")  # JOBQ, CLS, PGM
MAX_PREFIX = 16 * 1024
MAX_OCCURRENCES = 512
NAME = re.compile(r"[A-Z#$@][A-Z0-9_#$@]{3,9}")


def action(name, obj, *, start=0):
    return dict(kind="subsystem_action", name=name, type="Name occurrences",
                note="", request=dict(obj=obj, start=start))


class SubsystemExplorer:
    def __init__(self, image, inventory):
        self.image = image
        self.inventory = inventory
        self._patterns = {}
        for target in inventory.objects:
            if target.type_code not in TARGET_CODES:
                continue
            if not NAME.fullmatch(target.name.upper()):
                continue
            token = target.name.upper().ljust(10).encode("cp037")
            self._patterns.setdefault(token, []).append(target)
        self._subsystems = tuple(o for o in inventory.objects if o.type_code == "19/09")
        self._cache = {}
        self._reverse = None

    def _evidence(self, obj):
        if obj.type_code != "19/09":
            raise ValueError("Not an SBSD primary")
        key = (obj.segment.start_lba, obj.segment.virtual_address)
        if key not in self._cache:
            data = read_prefix(self.image, obj.segment, MAX_PREFIX)
            matches = []
            self_offsets = set()
            truncated = False
            # +0x100 keeps the common EPA header/name from being treated as a
            # claimed subsystem relationship. Offset 0x327 often repeats the
            # subsystem's own name and is tracked but not followed.
            for at in range(0x100, max(0,len(data)-9)):
                for target in self._patterns.get(data[at:at+10], ()):
                    if target.name.upper() == obj.name.upper():
                        self_offsets.add(at)
                        continue
                    if len(matches) >= MAX_OCCURRENCES:
                        truncated = True
                        break
                    matches.append((at,target))
                if truncated:
                    break
            matches.sort(key=lambda pair:(pair[0],pair[1].type_code,
                                          pair[1].name,pair[1].library_name or "",
                                          pair[1].segment.start_lba))
            self._cache[key] = (tuple(matches), len(self_offsets), truncated, len(data))
        return self._cache[key]

    def _reverse_index(self):
        if self._reverse is None:
            rev = {}
            for source in self._subsystems:
                try:
                    found,_,_,_ = self._evidence(source)
                except (ValueError,OSError):
                    continue
                for offset,target in found:
                    if target.type_code == "19/04":
                        key = (target.segment.start_lba,
                               target.segment.virtual_address)
                        rev.setdefault(key, []).append((offset, source))
            self._reverse = rev
        return self._reverse

    def rows(self, obj, start=0):
        if not isinstance(start,int) or start<0:
            raise ValueError("Invalid subsystem name-evidence window")
        if obj.type_code == "19/04":
            key = (obj.segment.start_lba,obj.segment.virtual_address)
            matches = sorted(self._reverse_index().get(key, ()),
                             key=lambda p:(p[1].name,p[0],p[1].segment.start_lba))
            rows = [section("Class reference candidates",[
                f"Recovered CLS {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
                f"Subsystem primaries with exact ten-byte name occurrences: {len(matches)}",
                "This is a reverse string-occurrence index, not a proven class assignment.",
                "No class attributes, live jobs or subsystem runtime state interpreted."])]
        elif obj.type_code == "19/09":
            found,self_count,truncated,read_size=self._evidence(obj)
            matches = [(offset,target) for offset,target in found]
            rows = [section("Subsystem name candidates",[
                f"Recovered SBSD {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
                f"Primary bytes examined: {read_size}; non-self target occurrences: {len(matches)}; self-name occurrences withheld: {self_count}",
                "Exact ten-byte EBCDIC padded target-name occurrences after +0x100, not verified structure members.",
                "Candidate types: JOBQ, CLS, PGM. No active queue, class assignment, "
                "program invocation or historical pointer relationship inferred.",
                *(['Evidence window capped; additional occurrences withheld.'] if truncated else [])])]
        else:
            raise ValueError("Not a subsystem description or class")
        if start:
            rows.append(action("Previous",obj,start=max(0,start-50)))
        if start+50 < len(matches):
            rows.append(action("Next",obj,start=start+50))
        for offset,target in matches[start:start+50]:
            rows.append(object_row(target,
                f"Ten-byte name occurrence at SBSD +0x{offset:X}; name evidence only"))
        if not matches:
            rows.append(section("No cross-name evidence",[
                "No supported non-self target names were found in the bounded recovered region.",
                "This is not proof that the subsystem has no saved configuration relationships."]))
        return rows
