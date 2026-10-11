"""Saved CISC 0E/09 alert-table 12-byte keys and corroborated MSGF ID links.

Two original AS/400 CISC images exhibit header 60 00 00 0C 00 08,
a six-byte index root at +0x420, and a 1024/2048-byte page size at
+0x42A. Supported keys are 12 bytes. C-prefixed eight-byte EBCDIC
identifier candidates may contain a *seven*-character message ID;
the four trailing bytes and other leading categories remain opaque.
Neither saved alert action semantics nor live alert delivery is decoded.
"""
from dataclasses import dataclass
import fnmatch
import re

from as400_capabilities import read_prefix, section, object_row
from as400_dasd import decode_context_machine_index

MAX_PRIMARY_BYTES = 8 * 1024 * 1024
PAGE_ENTRIES = 50
KEY_LENGTH = 12
HEADER = bytes.fromhex("6000000C0008")
MESSAGE_ID = re.compile(r"[A-Z][A-Z0-9]{2}[0-9A-F]{4}")
FILTER = re.compile(r"[A-Z0-9*?]{1,16}")


@dataclass(frozen=True)
class AlertIndexKey:
    raw: bytes
    terminal_offset: int

    @property
    def message_id_candidate(self):
        """Observed C + seven-character ID shape, never presumed action."""
        if len(self.raw) != KEY_LENGTH or self.raw[0] != 0xC3:
            return None
        token = self.raw[1:8].decode("cp037", errors="replace")
        return token if MESSAGE_ID.fullmatch(token) else None

    @property
    def prefix_lens(self):
        return self.raw[:8].decode("cp037", errors="replace")


def decode_alert_index(data, virtual_address):
    """Conservatively reconstruct only complete 12-byte release-2 keys."""
    if len(data) < 0x42E or data[0x100:0x106] != HEADER:
        raise ValueError("Truncated or unsupported saved alert-table control header")
    root = int.from_bytes(data[0x420:0x426], "big") - virtual_address
    page_size = int.from_bytes(data[0x42A:0x42E], "big")
    if page_size not in (1024, 2048) or root < 0 or root+page_size > len(data):
        raise ValueError("Saved ALRTBL root or page-size lies outside recovered primary")
    traversal = decode_context_machine_index(
        data, root_offset=root, page_size=page_size, strict_pages=True)
    keys = []
    warnings = list(traversal.warnings)
    if not traversal.complete:
        warnings.append("Index traversal incomplete; unknown key material not reconstructed")
    for entry in traversal.entries:
        if len(entry.raw) != KEY_LENGTH:
            warnings.append(
                f"Unsupported ALRTBL key size {len(entry.raw)} at +0x{entry.terminal_element_offset:X}; withheld")
            continue
        keys.append(AlertIndexKey(bytes(entry.raw), entry.terminal_element_offset))
    return tuple(keys), tuple(dict.fromkeys(warnings)), page_size


def action(label, obj, **kwargs):
    return dict(kind="alert_index_action", name=label,
                type="Saved alert table", note="",
                request=dict(obj=obj, **kwargs))


class AlertTableExplorer:
    def __init__(self, image, inventory, message_explorer=None):
        self.image = image
        self.message_explorer = message_explorer
        self._cache = {}
        self._reverse = {}
        self._alerts = {}
        self._messages = {}
        for obj in inventory.objects:
            if obj.type_code == "0E/03":
                self._messages.setdefault(obj.name.upper(), []).append(obj)
            if obj.type_code == "0E/09":
                self._alerts.setdefault(obj.name.upper(), []).append(obj)
        for items in self._alerts.values():
            items.sort(key=lambda o:(o.library_name or "", o.segment.start_lba))
        for items in self._messages.values():
            items.sort(key=lambda o:(o.library_name or "", o.segment.start_lba))

    def entries(self, obj):
        if obj.type_code != "0E/09":
            raise ValueError("Not an alert-table primary")
        origin = (obj.segment.start_lba, obj.segment.virtual_address)
        if origin not in self._cache:
            self._cache[origin] = decode_alert_index(
                read_prefix(self.image, obj.segment, MAX_PRIMARY_BYTES),
                obj.segment.virtual_address)
        return self._cache[origin]

    def alert_rows_for_message_id(self, msgf, identifier):
        """Link a *selected* confirmed MSGF ID to equal C-tag alert key bytes.

        An identical saved identifier does not establish that any alert was
        raised or that the associated table owned the message record.
        Invalid/missing alert roots remain explicitly withheld.
        """
        if msgf.type_code != "0E/03" or not MESSAGE_ID.fullmatch(identifier):
            raise ValueError("Expected an independently selected MSGF message ID")
        tables = self._alerts.get(msgf.name.upper(), ())
        if not tables:
            return []
        candidates = []
        withheld = 0
        for table in tables:
            origin = (table.segment.start_lba, table.segment.virtual_address)
            if origin not in self._reverse:
                try:
                    keys, warnings, _ = self.entries(table)
                except (ValueError, OSError):
                    self._reverse[origin] = None
                else:
                    lookup = {}
                    for key in keys:
                        token = key.message_id_candidate
                        if token:
                            lookup.setdefault(token, []).append(key)
                    self._reverse[origin] = lookup
            indexed = self._reverse[origin]
            if indexed is None:
                withheld += 1
                continue
            candidates.extend((table, key) for key in indexed.get(identifier, ()))
        candidates.sort(key=lambda pair:(pair[0].library_name or "",
                                          pair[0].segment.start_lba,
                                          pair[1].terminal_offset))
        rows = [section("Same-name saved alert-table evidence", [
            f"Recovered 0E/09 alert-table primaries named {msgf.name}: {len(tables)}",
            f"C-tag saved keys containing exact seven-character ID {identifier}: {len(candidates)}",
            f"Alert-table roots withheld/unsupported: {withheld}",
            "This reverse lookup is exact saved ID equality only, not a compiled alert action, pointer or runtime event.",
            "Choose a saved key for original bytes; no alert or command is executed."])]
        for table, key in candidates[:50]:
            link = action(f"Alert key in {table.name}", table, entry=key)
            link["note"] = (f"Alert-table primary LBA {table.segment.start_lba}; "
                            f"terminal +0x{key.terminal_offset:X}; candidate only")
            rows.append(link)
        if len(candidates) > 50:
            rows.append(section("More matching saved keys", [
                f"{len(candidates)-50} additional ambiguous alert keys not expanded.",
                f"Use DSPALRTBL ALRTBL(*ALL/{msgf.name}) MSGID({identifier}) to page them."]))
        if not candidates:
            rows.append(section("No corroborated same-ID alert key", [
                "No supported saved C-tag key with that ID was reconstructed.",
                "An unsupported index cannot prove the alert never existed."]))
        return rows

    def rows(self, obj, start=0, msgid="*", keyhex="", entry=None):
        if not isinstance(start, int) or start < 0:
            raise ValueError("Invalid alert-key window")
        if not isinstance(msgid, str) or not FILTER.fullmatch(msgid):
            raise ValueError("MSGID supports a 1–16-character uppercase literal glob")
        try:
            prefix = bytes.fromhex(keyhex)
        except ValueError:
            raise ValueError("KEYHEX must contain whole hexadecimal bytes") from None
        if len(prefix) > KEY_LENGTH:
            raise ValueError("KEYHEX exceeds the 12-byte saved key")
        keys, warnings, page_size = self.entries(obj)
        if entry is not None:
            if entry not in keys:
                raise ValueError("Alert key does not belong to selected recovered primary")
            candidate = entry.message_id_candidate
            rows = [section("Saved alert-table key", [
                f"ALRTBL {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
                f"Terminal element +0x{entry.terminal_offset:X}; exactly {len(entry.raw)} bytes",
                f"First eight raw CP037 display characters: {entry.prefix_lens!r}",
                f"Candidate seven-character message ID: {candidate or '<unverified>'}",
                f"Four opaque trailing bytes: {entry.raw[8:].hex(' ').upper()}",
                "Original key bytes: " + entry.raw.hex(' ').upper(),
                "C-prefix and message ID are empirical fields. Four tail bytes and other tags are unknown.",
                "No alert routing, message action or live alert interpretation is implied.",
                *warnings])]
            if candidate:
                sources = self._messages.get(obj.name.upper(), ())
                rows.append(section("Same-name message-file candidates", [
                    f"MSGF primaries with identical recovered name: {len(sources)}",
                    "ALRTBL and MSGF name equality is a candidate namespace relationship, not a decoded pointer.",
                    "Only an independently reconstructed exact 7-character MSGF ID can be marked corroborated."]))
                for source in sources:
                    rows.append(object_row(source,
                        "Same-name MSGF primary, not proof this alert key refers to it"))
                    if self.message_explorer is None:
                        continue
                    try:
                        message_rows = self.message_explorer.rows(source, pattern=candidate)
                    except (OSError, ValueError):
                        rows.append(section("MSGF index unavailable", [
                            "Selected same-name message file's saved index could not be reconstructed.",
                            "Alert key remains readable; no alternate record was guessed."]))
                        continue
                    matches = [r for r in message_rows
                               if r.get("kind") == "message_action"
                               and r.get("name") == candidate
                               and r.get("request", {}).get("entry") is not None]
                    if matches:
                        for found in matches:
                            link = dict(found)
                            link["note"] = (
                                f"Corroborated exact MSGF ID in primary LBA {source.segment.start_lba}; "
                                "select for separately validated record/text evidence")
                            rows.append(section("Corroborated saved MSGF ID", [
                                f"Exact supported 7-character MSGF index entry {candidate} found.",
                                "Index ID equality is confirmed; message record storage, payload and alert action remain separate."]))
                            rows.append(link)
                    else:
                        rows.append(section("No corroborated MSGF ID", [
                            f"No supported exact {candidate} ID in this recovered candidate MSGF index.",
                            "No historical absence or alert-rule meaning inferred."]))
                if not sources:
                    rows.append(section("No saved same-name MSGF", [
                        "No recovered message-file primary has this exact name.",
                        "No conclusion about historical library-list or missing-storage resolution."]))
            return rows

        matching = [(i,k) for i,k in enumerate(keys)
                    if k.raw.startswith(prefix) and (
                        msgid == "*" or (k.message_id_candidate is not None and
                                        fnmatch.fnmatchcase(k.message_id_candidate, msgid)))]
        identified = sum(k.message_id_candidate is not None for k in keys)
        rows = [section("Saved alert-table index", [
            f"ALRTBL {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
            f"Saved page size {page_size}; supported 12-byte terminal keys {len(keys)}",
            f"C-prefixed seven-character message-ID candidates {identified}; matching MSGID({msgid}): {len(matching)}",
            "Non-C keys are retained in unfiltered browsing but never guessed to be message IDs.",
            "Select a key for original bytes and on-demand same-name MSGF ID corroboration.",
            "The index's four opaque trailing bytes do not establish storage pointers or alert actions.",
            *warnings])]
        if start:
            rows.append(action("Previous", obj, start=max(0,start-PAGE_ENTRIES),
                               msgid=msgid, keyhex=keyhex))
        if start+PAGE_ENTRIES < len(matching):
            rows.append(action("Next", obj, start=start+PAGE_ENTRIES,
                               msgid=msgid, keyhex=keyhex))
        for i,key in matching[start:start+PAGE_ENTRIES]:
            r = action(key.message_id_candidate or f"Opaque key {i+1}",
                       obj, entry=key)
            r["note"] = (
                f"terminal +0x{key.terminal_offset:X}; "
                f"prefix {key.prefix_lens!r}; 12 saved bytes")
            rows.append(r)
        return rows
