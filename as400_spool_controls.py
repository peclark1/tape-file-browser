"""Saved 19/C2 SPLCB identity/name-slot navigation (offline, evidence-only).

Observed on two CISC archives: qualified-name-shaped EBCDIC padded
ten-byte slots at +0x1AE and +0x1B8, and a sometimes present SPdddd
token at +0x1C5. Field roles are *not* established spool/job semantics.
"""
import re
from as400_capabilities import read_prefix, section, object_row

NAME = re.compile(r"[A-Z#$@][A-Z0-9_#$@]{0,9}")
TOKEN = re.compile(r"SP[0-9]{4}")
READ_LIMIT = 0x1CB
SLOT_A = 0x1AE
SLOT_B = 0x1B8
TOKEN_AT = 0x1C5


def strict_name(raw):
    """Accept only an entire ten-byte EBCDIC name with blank right padding."""
    if len(raw)!=10:
        raise ValueError("Incomplete saved name slot")
    if raw == bytes(10):
        return None
    text=raw.decode("cp037", errors="replace").rstrip(" ")
    if not NAME.fullmatch(text) or text.ljust(10).encode("cp037")!=raw:
        return None
    return text


def decode_spool_slots(data, *, type_code):
    if type_code!="19/C2" or len(data)<READ_LIMIT:
        raise ValueError("Truncated or unsupported spool-control primary")
    raw_a=data[SLOT_A:SLOT_A+10]
    raw_b=data[SLOT_B:SLOT_B+10]
    raw_token=data[TOKEN_AT:TOKEN_AT+6]
    first=strict_name(raw_a)
    second=strict_name(raw_b)
    token=raw_token.decode("cp037",errors="replace")
    tag=token if TOKEN.fullmatch(token) else None
    return first,second,tag


class SpoolControlExplorer:
    def __init__(self,image,inventory,printer_queue_explorer=None):
        self.image=image
        self.inventory=inventory
        self._printer_queue_explorer=printer_queue_explorer
        self._printer_sources=tuple(o for o in inventory.objects if o.type_code=="0E/C7")
        self._printer_token_index=None
        self._printer_withheld=0
        self._by_qualified={}
        for target in inventory.objects:
            if not target.name or target.type_code=="19/C2":
                continue
            key=((target.library_name or "").upper(),target.name.upper())
            self._by_qualified.setdefault(key,[]).append(target)
        for group in self._by_qualified.values():
            group.sort(key=lambda item:(item.type_code,item.segment.start_lba))
        self._cache={}

    def printer_token_candidates(self):
        """Build a read-only reverse index of saved PRTQ SPdddd key prefixes.

        The same-token join is *not* proof of spool ownership. An
        unsupported saved index is counted, never treated as empty.
        """
        if self._printer_token_index is None:
            from as400_printer_queues import PrinterQueueExplorer
            reader=(self._printer_queue_explorer or
                    PrinterQueueExplorer(self.image,self.inventory))
            refs={};withheld=0
            for prtq in self._printer_sources:
                try:
                    keys,warnings,size=reader.entries(prtq)
                except (ValueError,OSError):
                    withheld+=1
                    continue
                for key in keys:
                    token=key.token_candidate
                    if token:
                        refs.setdefault(token,[]).append((prtq,key))
            for values in refs.values():
                values.sort(key=lambda pair:(pair[0].library_name or "",
                                             pair[0].name,
                                             pair[0].segment.start_lba,
                                             pair[1].terminal_offset))
            self._printer_token_index=refs
            self._printer_withheld=withheld
        return self._printer_token_index

    def rows(self,obj):
        if obj.type_code!="19/C2":
            raise ValueError("Not a spool-control primary")
        key=(obj.segment.start_lba,obj.segment.virtual_address)
        if key not in self._cache:
            data=read_prefix(self.image,obj.segment,READ_LIMIT)
            self._cache[key]=(decode_spool_slots(data,type_code=obj.type_code),
                              data[SLOT_A:SLOT_B+10].hex(" ").upper(),
                              data[TOKEN_AT:TOKEN_AT+6].hex(" ").upper())
        (name,library,tag),raw_pair,raw_tag=self._cache[key]
        complete=bool(name and library)
        rows=[section("Saved spool-control evidence",[
            f"Recovered SPLCB {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
            f"First padded name slot +0x{SLOT_A:X}: {name or '<unresolved>'}",
            f"Second padded name slot +0x{SLOT_B:X}: {library or '<unresolved>'}",
            f"SPdddd-shaped token +0x{TOKEN_AT:X}: {tag or '<unresolved>'}",
            f"Name slots hex: {raw_pair}",
            f"Token bytes hex: {raw_tag}",
            "These are saved fixed-offset patterns; slot roles, spool owner/job identity and runtime state are unproven.",
            "Only recovered object identity metadata is compared; no target body bytes are read.",
            "Names and tokens may be stale; token SPdddd is not a certified spool ID."])]
        if tag and self._printer_sources:
            from as400_printer_queues import action as printer_action
            candidates=self.printer_token_candidates().get(tag,())
            rows.append(section("Printer-queue token candidates",[
                f"Saved PRTQ terminals with the same SPdddd token: {len(candidates)}",
                f"Unresolved PRTQ primaries withheld from token matching: {self._printer_withheld}",
                "This is an exact saved byte comparison, NOT spool/file ownership, active printing or a pointer.",
                "Select a candidate to view its full opaque index key and original queue origin."]))
            for queue,key in candidates[:50]:
                link=printer_action(f"Saved key in {queue.name}",queue,entry=key)
                link["note"]=(f"PRTQ primary LBA {queue.segment.start_lba}; "
                              f"key element +0x{key.terminal_offset:X}; exact token evidence")
                rows.append(link)
            if len(candidates)>50:
                rows.append(section("Additional candidates withheld",[
                    f"{len(candidates)-50} more matches not expanded in this view.",
                    f"Use DSPPRTQ PRTQ(*ALL/*) TOKEN({tag}) to browse them in bounded pages."]))
            elif not candidates:
                rows.append(section("No recovered printer-key match",[
                    "None in the supported recovered index trees; other roots may be missing.",
                    "Do not infer that a historical spool relationship was absent."]))
        if complete:
            targets=self._by_qualified.get((library,name),())
            rows.append(section("Qualified-name candidates",[
                f"Recovered object primaries with identity {library}/{name}: {len(targets)}",
                "Exact name and recovered library match only, not an internal pointer or spool relationship."]))
            rows.extend(object_row(t,"SPLCB name-slot identity match only; choose specific type/origin")
                        for t in targets)
            if not targets:
                rows.append(section("No matching primary",[
                    "Stored qualified-name candidate remains visible; no target recovered.",
                    "Do not infer missing historical spool data from this scan."]))
        elif name or library:
            rows.append(section("Incomplete name pair",[
                "One of the two saved ten-byte slots is absent or unsupported.",
                "No qualified-name target has been guessed."]))
        else:
            rows.append(section("No qualified-name pair",[
                "Neither saved slot forms a supported qualified-name candidate.",
                "Spool context and identity remain opaque."]))
        return rows
