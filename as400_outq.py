"""Read-only saved OUTQ/JOBQ machine-index browsing, not live queues.

Observed on both CISC images: 0E/02 and 0E/01 primaries +0x100 begins 20 00 00 30
00 20; a six-byte root address occurs at +0x420, and the page-size word
at +0x42A is 2048 (Mark) or 1024 (Pete). Supported terminal keys have
48 bytes. The numeric scalars near +0x108 have NOT been established as
active entry counts. Key offsets and token meanings remain hypotheses.
"""
from dataclasses import dataclass

from as400_dasd import decode_context_machine_index
from as400_capabilities import read_prefix, section

OUTQ_HEADER = bytes.fromhex("200000300020")
OUTQ_KEY_SIZE = 48
MAX_PRIMARY_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class OutputQueueKey:
    raw: bytes
    terminal_offset: int

    @property
    def control_like(self):
        # Observed in otherwise nearly empty queues. Do not name this
        # deleted/empty/live until period documentation confirms it.
        return self.raw[0] == 0xFA

    @property
    def form_candidate(self):
        # +0x20..29 contains an observed EBCDIC '*STD' token in several
        # Mark entries. Other bytes are never guessed to be a form name.
        if self.control_like:
            return None
        token = self.raw[0x20:0x2A].decode("cp037", errors="replace").rstrip(" ")
        if not token or len(token) > 10:
            return None
        if not all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789*#$@_" for c in token):
            return None
        return token


def decode_output_queue_index(data, virtual_address):
    """Decode only bounded, fully reconstructed 48-byte release-2 keys."""
    if len(data) < 0x42E or data[0x100:0x106] != OUTQ_HEADER:
        raise ValueError("Truncated or unsupported OUTQ control prefix")
    root = int.from_bytes(data[0x420:0x426], "big") - virtual_address
    size = int.from_bytes(data[0x42A:0x42E], "big")
    if root < 0 or root + size > len(data):
        raise ValueError("OUTQ root page is outside recovered primary")
    traversal = decode_context_machine_index(
        data, root_offset=root, page_size=size, strict_pages=True)
    warnings = list(traversal.warnings)
    keys = []
    for entry in traversal.entries:
        if len(entry.raw) != OUTQ_KEY_SIZE:
            warnings.append(
                f"Unsupported OUTQ terminal length {len(entry.raw)} at "
                f"+0x{entry.terminal_element_offset:X}; withheld")
            continue
        keys.append(OutputQueueKey(bytes(entry.raw), entry.terminal_element_offset))
    if not traversal.complete:
        warnings.append("Index traversal incomplete; displayed keys are only recovered evidence")
    # No primary counter is equated to the number of historical spool entries.
    return tuple(keys), tuple(dict.fromkeys(warnings))


def outq_action(name, obj, **kwargs):
    return dict(kind="outq_action", name=name, type="Saved OUTQ evidence",
                note="", request=dict(obj=obj, **kwargs))


class OutputQueueExplorer:
    def __init__(self, image):
        self.image = image
        self._cache = {}

    def entries(self, obj):
        if obj.type_code not in ("0E/02", "0E/01"):
            raise ValueError("Not a recovered output or job queue")
        key = (obj.segment.start_lba, obj.segment.virtual_address)
        if key not in self._cache:
            data = read_prefix(self.image, obj.segment, MAX_PRIMARY_BYTES)
            self._cache[key] = decode_output_queue_index(
                data, obj.segment.virtual_address)
        return self._cache[key]

    def rows(self, obj, start=0, keyhex="", form="", entry=None):
        if not isinstance(start, int) or start < 0:
            raise ValueError("Invalid output-queue window")
        try:
            prefix = bytes.fromhex(keyhex)
        except ValueError:
            raise ValueError("KEYHEX must consist of whole hexadecimal bytes") from None
        if len(prefix) > OUTQ_KEY_SIZE:
            raise ValueError("KEYHEX exceeds 48 bytes")
        if form and (len(form) > 10 or not all(
            c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789*#$@_" for c in form)):
            raise ValueError("FORM must be a ten-character-or-shorter literal candidate")
        keys, warnings = self.entries(obj)
        kind = "JOBQ" if obj.type_code == "0E/01" else "OUTQ"
        if kind == "JOBQ" and form:
            raise ValueError("FORM is not a verified JOBQ key attribute")
        if entry is not None:
            if entry not in keys:
                raise ValueError("Queue key does not belong to this recovered primary")
            key = entry.raw
            rows = [section(f"Saved {kind} key", [
                f"{kind} {obj.library_name or '<unassigned>'}/{obj.name}; "
                f"primary LBA {obj.segment.start_lba}",
                f"Terminal +0x{entry.terminal_offset:X}; 48 bytes; "
                f"control-like marker: {'yes' if entry.control_like else 'no'}",
                (f"Candidate form token at +0x20: {entry.form_candidate or '<unverified>'}"
                 if kind == "OUTQ" else "No JOBQ key fields have verified meanings"),
                ("Form token is an observed byte pattern, not a verified spool-file attribute."
                 if kind == "OUTQ" else "Never infer live jobs or saved job identities from these bytes."),
                "All other fields are opaque; no live entries, job states, "
                "spooled content or chronological ordering inferred.",
                *warnings])]
            for offset in range(0, OUTQ_KEY_SIZE, 8):
                chunk = key[offset:offset+8]
                rows.append(section(f"Key +0x{offset:02X}", [
                    chunk.hex(" ").upper(),
                    repr(chunk.decode("cp037", errors="replace"))]))
            return rows

        active = [(i, e) for i, e in enumerate(keys)
                  if not e.control_like and e.raw.startswith(prefix)
                  and (not form or e.form_candidate == form)]
        controls = sum(e.control_like for e in keys)
        rows = [section(f"Saved {kind} index", [
            f"{kind} {obj.library_name or '<unassigned>'}/{obj.name}; "
            f"primary LBA {obj.segment.start_lba}",
            f"Supported 48-byte terminals {len(keys)}; "
            f"control-like {controls}; candidate entries matching filters {len(active)}",
            "Tree order is archival index order, not verified spool/job chronology.",
            "FA-prefixed keys are control-like and excluded from the entry list, "
            "but retained in the total; their meaning remains unknown.",
            ("Select a candidate for exact 48-byte keys and possible form token."
             if kind == "OUTQ" else "Select any non-control key for exact bytes; job identity remains unknown."),
            *warnings])]
        if start:
            rows.append(outq_action("Previous", obj, start=max(0, start-50),
                                    keyhex=keyhex, form=form))
        if start + 50 < len(active):
            rows.append(outq_action("Next", obj, start=start+50,
                                    keyhex=keyhex, form=form))
        for index, e in active[start:start+50]:
            token = e.form_candidate
            row = outq_action(f"Key {index+1}", obj, entry=e)
            row["note"] = (
                f"terminal +0x{e.terminal_offset:X}; "
                (f"form candidate {token or '<unknown>'}; "
                 if kind == "OUTQ" else "job key (opaque); ")
                f"prefix {e.raw[:8].hex().upper()}")
            rows.append(row)
        return rows
