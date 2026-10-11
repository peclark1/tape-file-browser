"""Read-only CISC 0E/C7 PRTQ saved index keys and SPLCB token candidates.

Two original CISC disk archives exhibit release-2 index controls:
PRTQ +0x420 six-byte root address and +0x42A page-size (Mark 2048,
Pete 1024). Opaque terminal prefixes may contain a 10-byte EBCDIC
SPdddd followed by blanks; that text is not a proven spool ID.
SPLCB +0x1C5 can contain an equal token. Equality is ONLY a
candidate relationship, not a spool ownership or object pointer.
"""
from dataclasses import dataclass
import re

from as400_capabilities import read_prefix, section, object_row
from as400_dasd import decode_context_machine_index
from as400_spool_controls import decode_spool_slots

MAX_PRIMARY_BYTES = 8 * 1024 * 1024
MAX_KEY_BYTES = 256
PAGE_ENTRIES = 50
TAG = re.compile(r"SP[0-9]{4}")
VALID_HEADERS = ((0x20, 0x1A), (0x30, 0x2C))


@dataclass(frozen=True)
class PrinterQueueKey:
    raw: bytes
    terminal_offset: int

    @property
    def token_candidate(self):
        if len(self.raw) < 10:
            return None
        prefix = self.raw[:10]
        if prefix[6:10] != b"\x40" * 4:
            return None
        token = prefix[:6].decode("cp037", errors="replace")
        return token if TAG.fullmatch(token) else None


def decode_printer_queue_index(data, virtual_address):
    if len(data) < 0x42E:
        raise ValueError("Incomplete recovered PRTQ index header")
    header = data[0x100:0x106]
    if (len(header) != 6 or header[:3] not in (bytes.fromhex("200000"),
                                               bytes.fromhex("300000")) or
            header[4] != 0 or (header[0], header[5]) not in VALID_HEADERS):
        raise ValueError("Unknown CISC PRTQ release/control-header variant")
    root = int.from_bytes(data[0x420:0x426], "big") - virtual_address
    page_size = int.from_bytes(data[0x42A:0x42E], "big")
    if (page_size not in (1024, 2048) or root < 0 or
            root + page_size > len(data)):
        raise ValueError("PRTQ saved index root/page-size is outside recovered primary")
    traversal = decode_context_machine_index(
        data, root_offset=root, page_size=page_size, strict_pages=True)
    warnings = list(traversal.warnings)
    if not traversal.complete:
        warnings.append("Incomplete tree traversal; no missing key material synthesized")
    result = []
    for e in traversal.entries:
        n = len(e.raw)
        if not 1 <= n <= MAX_KEY_BYTES:
            warnings.append(f"PRTQ terminal of length {n} withheld at +0x{e.terminal_element_offset:X}")
            continue
        result.append(PrinterQueueKey(bytes(e.raw), e.terminal_element_offset))
    return tuple(result), tuple(dict.fromkeys(warnings)), page_size


def action(name, obj, **kwargs):
    return dict(kind="printer_queue_action", name=name,
                type="Saved printer-queue index", note="",
                request=dict(obj=obj, **kwargs))


class PrinterQueueExplorer:
    def __init__(self, image, inventory):
        self.image = image
        self._cache = {}
        self._spools = tuple(o for o in inventory.objects
                             if o.type_code == "19/C2")
        self._tokens = None
        self._unreadable_spools = 0

    def entries(self, obj):
        if obj.type_code != "0E/C7":
            raise ValueError("Not a recovered printer-queue index")
        identity = (obj.segment.start_lba, obj.segment.virtual_address)
        if identity not in self._cache:
            data = read_prefix(self.image, obj.segment, MAX_PRIMARY_BYTES)
            self._cache[identity] = decode_printer_queue_index(
                data, obj.segment.virtual_address)
        return self._cache[identity]

    def _spool_token_index(self):
        if self._tokens is None:
            tokens = {}
            unreadable = 0
            for o in self._spools:
                try:
                    data = read_prefix(self.image, o.segment, 0x1CB)
                    _, _, token = decode_spool_slots(
                        data, type_code=o.type_code)
                except (ValueError, OSError):
                    unreadable += 1
                    continue
                if token:
                    tokens.setdefault(token, []).append(o)
            for objs in tokens.values():
                objs.sort(key=lambda o:(o.library_name or "", o.name,
                                        o.segment.start_lba))
            self._tokens = tokens
            self._unreadable_spools = unreadable
        return self._tokens

    def rows(self, obj, start=0, keyhex="", token="", entry=None):
        if not isinstance(start, int) or start < 0:
            raise ValueError("Invalid PRTQ key window")
        try:
            prefix = bytes.fromhex(keyhex)
        except ValueError:
            raise ValueError("KEYHEX must be complete hexadecimal bytes") from None
        if len(prefix) > MAX_KEY_BYTES:
            raise ValueError("KEYHEX exceeds 256 bytes")
        if token and not TAG.fullmatch(token):
            raise ValueError("TOKEN must match SP followed by exactly four digits")
        entries, warnings, page_size = self.entries(obj)
        if entry is not None:
            if entry not in entries:
                raise ValueError("Selected key is not in this recovered PRTQ primary")
            tok = entry.token_candidate
            rows = [section("Saved printer-queue key", [
                f"PRTQ {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
                f"Exact terminal +0x{entry.terminal_offset:X}; key length {len(entry.raw)} bytes",
                f"SPdddd-shaped prefix candidate: {tok or '<unverified>'}",
                "SPdddd candidate is a byte pattern, not a verified spool owner, job or file ID.",
                "Tree order and original bytes do not establish queue chronology or printing state.",
                *warnings])]
            for offset in range(0, len(entry.raw), 16):
                part = entry.raw[offset:offset+16]
                rows.append(section(f"Key bytes +0x{offset:X}", [
                    part.hex(" ").upper(),
                    repr(part.decode("cp037", errors="replace"))]))
            if tok:
                matches = self._spool_token_index().get(tok, ())
                rows.append(section("SPLCB token-name candidates", [
                    f"Recovered SPLCB primaries containing the same SPdddd bytes: {len(matches)}",
                    f"Saved token: {tok}; unresolved SPLCB layouts: {self._unreadable_spools}",
                    "Exact token equality ONLY. No pointer, ownership, live spool entry or job identity proven."]))
                rows.extend(object_row(o, "Exact saved SPdddd token match only; choose original SPLCB origin")
                            for o in matches)
                if not matches:
                    rows.append(section("No spool-control token match", [
                        "No normally recovered SPLCB primary has this supported saved token.",
                        "No conclusion about historical spool existence or completeness."]))
            return rows

        selected = [(i, e) for i,e in enumerate(entries)
                    if e.raw.startswith(prefix) and
                    (not token or e.token_candidate == token)]
        candidate_count = sum(e.token_candidate is not None for e in entries)
        rows = [section("Saved printer-queue index", [
            f"PRTQ {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
            f"Page size {page_size}; reconstructed supported keys {len(entries)}",
            f"SPdddd-shaped prefix candidates {candidate_count}; matching filters {len(selected)}",
            "SPdddd tokens and tree order are saved byte evidence, not certified spool queue state.",
            "Select a key for exact hex/CP037 bytes and candidate SPLCB token matches.",
            *warnings])]
        if start:
            rows.append(action("Previous", obj, start=max(0,start-PAGE_ENTRIES),
                               keyhex=keyhex, token=token))
        if start + PAGE_ENTRIES < len(selected):
            rows.append(action("Next", obj, start=start+PAGE_ENTRIES,
                               keyhex=keyhex, token=token))
        for i, e in selected[start:start+PAGE_ENTRIES]:
            row = action(f"Key {i+1}", obj, entry=e)
            row["note"] = (f"terminal +0x{e.terminal_offset:X}; "
                           f"token {e.token_candidate or '<none>'}; "
                           f"{len(e.raw)} opaque bytes")
            rows.append(row)
        return rows
