"""Conservative, bounded read-only observations of original CISC OS/400 *CMD.

These are observations of recovered bytes, NOT a decoder of the complete
compiled command-definition format. IBM's QCDRCMDI API is a logical
interface and its format offsets must not be assumed to be on-disk offsets.
"""

import re
from dataclasses import dataclass


_NAME = re.compile(r"^[A-Z#$@_][A-Z0-9#$@_]{0,9}$")
_RUN = re.compile(r"[\x20-\x7e]{5,}")


def _object_name(raw):
    """A narrow *candidate* EBCDIC object name; reject undecodable bytes."""
    if len(raw) != 10:
        return None
    try:
        text = raw.decode("cp037").rstrip(" ")
    except UnicodeError:
        return None
    return text if _NAME.fullmatch(text) else None


def candidate_processor(primary_prefix):
    """Return candidate PGM/LIB strings observed at raw offsets +102/+10C.

    Independent observation on multiple V2R3 IBM *CMD primaries shows two
    adjacent ten-byte EBCDIC names here. Their apparent command-processor
    role has NOT been established by decoding the command's on-disk schema.
    Return None if either field does not resemble an object name.
    """
    if len(primary_prefix) < 0x116:
        return None
    name = _object_name(primary_prefix[0x102:0x10C])
    library = _object_name(primary_prefix[0x10C:0x116])
    if not name or not library:
        return None
    return name, library


def embedded_ebcdic_text(primary_prefix, *, scan_bytes=8192, max_items=64):
    """Bounded EBCDIC printable runs with verified *byte offsets*.

    Strings are not interpreted as parameter names, descriptions, or pointer
    fields. A run can contain adjacent fields and spurious printable bytes.
    Results are therefore presented as evidence, never authoritative schema.
    """
    if scan_bytes <= 0 or max_items <= 0:
        return ()
    data = bytes(primary_prefix[:min(scan_bytes, 8192)])
    decoded = data.decode("cp037", errors="replace")
    result = []
    # Skip the common segment/EPA headers and fixed candidate program field.
    for match in _RUN.finditer(decoded, 0x160):
        value = match.group().strip()
        if len(value) < 5 or sum(letter.isalpha() for letter in value) < 4:
            continue
        # Extremely long runs are often EBCDIC blank space, not field data.
        value = re.sub(r"\s+", " ", value)
        if len(value) > 96:
            value = value[:95] + "…"
        result.append((match.start(), value))
        if len(result) >= min(max_items, 64):
            break
    return tuple(result)


@dataclass(frozen=True)
class ParameterKeywordEvidence:
    """Observed keyword and ordinal; NOT a complete decoded PARM statement."""

    ordinal: int
    offset: int
    keyword: str


@dataclass(frozen=True)
class ParameterRecovery:
    """All-or-nothing recovery with an actionable failure reason."""

    parameters: tuple = ()
    declared_count: int | None = None
    reason: str = ""


def recover_parameter_keywords(primary_prefix, *, max_count=64):
    """Validate the empirical V2R3 keyword sequence; never guess missing rows.

    The count is an observed byte, not proof of the number of display prompts.
    Search bounds and anchors deliberately match the reviewed PR #15 decoder.
    No parameter types, defaults, prompt links or descriptor lengths are inferred.
    """
    data = bytes(primary_prefix[:8192])
    if len(data) < 0x182:
        return ParameterRecovery(reason="Short primary: count header at +0x180 unavailable.")
    count = data[0x180]
    def failed(reason):
        return ParameterRecovery(declared_count=count, reason=reason)
    if data[0x17E] == 0 or data[0x17F] != 0 or data[0x181] != 0:
        return failed("Unrecognized count-header shape at +0x17E..+0x181.")
    if count == 0:
        return failed("Zero count byte; zero-parameter semantics not established.")
    if not 1 <= count <= min(max_count, 64):
        return failed("Count exceeds the supported 1..64 parameter bound.")

    def keyword_at(offset, ordinal):
        if offset < 4 or offset + 12 > len(data):
            return None
        if data[offset - 4:offset] != bytes(4):
            return None
        name = _object_name(data[offset:offset + 10])
        if name is None or int.from_bytes(data[offset + 10:offset + 12], "big") != ordinal:
            return None
        return name

    first = keyword_at(0x19C, 1)
    if first is None:
        return failed("Missing/invalid first keyword and ordinal at +0x019C.")
    found = [ParameterKeywordEvidence(1, 0x19C, first)]
    previous = 0x19C
    for ordinal in range(2, count + 1):
        end = min(len(data) - 12, previous + 12 + 256)
        possibilities = [(offset, name) for offset in range(previous + 12, end + 1)
                         if (name := keyword_at(offset, ordinal)) is not None]
        if len(possibilities) != 1:
            why = "Missing" if not possibilities else "Ambiguous"
            return failed(f"{why} ordinal {ordinal} after +0x{previous:04X}; "
                          "complete sequence withheld.")
        offset, name = possibilities[0]
        if name in {p.keyword for p in found}:
            return failed(f"Duplicate keyword at ordinal {ordinal}; sequence withheld.")
        found.append(ParameterKeywordEvidence(ordinal, offset, name))
        previous = offset
    return ParameterRecovery(tuple(found), count,
                             "Complete empirical keyword/ordinal sequence recovered.")


def candidate_parameter_keywords(primary_prefix, *, max_count=64):
    """Compatibility helper: only return complete unambiguous sequences."""
    return recover_parameter_keywords(primary_prefix, max_count=max_count).parameters


@dataclass(frozen=True)
class LinkedText:
    offset: int
    text: str
    message_id: str = ""


@dataclass(frozen=True)
class ParameterDefinition:
    keyword: ParameterKeywordEvidence
    prompt: LinkedText | None = None
    hint: LinkedText | None = None
    default_candidate: LinkedText | None = None
    value_candidates: tuple = ()
    issues: tuple = ()


@dataclass(frozen=True)
class DefinitionLinks:
    parameters: tuple = ()
    prompt_order: tuple = ()
    reason: str = ""


def _u16(data, offset):
    return int.from_bytes(data[offset:offset + 2], "big")


def _linked_text(data, offset, floor, *, prompt=False):
    """Decode a bounded referenced record, never search nearby printable runs.

    Prompt records: two opaque bytes, seven-byte message ID (or blanks),
    two opaque bytes, u16 text byte length, EBCDIC text. Literal records:
    u16 byte length followed by EBCDIC. Unknown flags are not interpreted.
    """
    header = 13 if prompt else 2
    if offset < floor or offset + header > len(data):
        raise ValueError("Referenced text header is outside the recovered text region.")
    size = _u16(data, offset + header - 2)
    if size > 512 or offset + header + size > len(data):
        raise ValueError("Referenced text length is unsupported or truncated.")
    text = data[offset + header:offset + header + size].decode("cp037")
    if any(not 32 <= ord(c) <= 126 for c in text):
        raise ValueError("Referenced value is not supported printable EBCDIC text.")
    mid = ""
    if prompt:
        raw_id = data[offset + 2:offset + 9].decode("cp037")
        if raw_id != " " * 7 and not re.fullmatch(r"[A-Z][A-Z0-9]{6}", raw_id):
            raise ValueError("Referenced prompt has an unsupported message-ID shape.")
        mid = raw_id.strip()
    return LinkedText(offset, text, mid)


def recover_definition_links(primary_prefix, recovery=None):
    """Empirical CISC descriptor links, independently checked across both images.

    D=keyword-27; D+0 is next ordinal descriptor; keyword+12 is a second
    descriptor chain (presentation-order candidate). References are u16
    offsets relative to primary +0x100. Keyword-6 references prompt text.
    Tail after keyword+14 is tag/u16-total-length records terminated by FF.
    Tag 06 length 8 references display-hint text; tag 01/02 values are
    linked candidate defaults/special values, NOT verified validation rules.
    """
    data = bytes(primary_prefix[:8192])
    recovery = recovery or recover_parameter_keywords(data)
    ps = recovery.parameters
    if not ps:
        return DefinitionLinks(reason="No complete keyword table; prompt links withheld.")
    by_descriptor = {p.offset - 27: p for p in ps}
    floor = max(p.offset + 14 for p in ps)
    if any(p.offset + 14 > len(data) for p in ps):
        return DefinitionLinks(reason="Descriptor link fields truncated.")

    def chain(field):
        current, seen, order = 0x181, set(), []
        while current:
            if current in seen or current not in by_descriptor:
                raise ValueError("Descriptor chain cycles or points outside the keyword table.")
            seen.add(current)
            p = by_descriptor[current]
            order.append(p.ordinal)
            pointer = _u16(data, current if field == 0 else p.offset + 12)
            current = 0x100 + pointer if pointer else 0
        if len(order) != len(ps):
            raise ValueError("Descriptor chain omits recovered keywords.")
        return tuple(order)
    try:
        if chain(0) != tuple(p.ordinal for p in ps):
            raise ValueError("Descriptor chain disagrees with stored ordinals.")
    except ValueError as exc:
        return DefinitionLinks(reason=str(exc))
    try:
        order = chain(1)
        reason = "Both descriptor chains validated; F4 ordering remains empirical."
    except ValueError as exc:
        order = tuple(p.ordinal for p in ps)
        reason = f"Secondary order unavailable ({exc}); using stored ordinals."
    definitions = []
    for p in ps:
        issues = []
        prompt = hint = default = None
        values = ()
        pointer = _u16(data, p.offset - 6)
        try:
            if pointer:
                prompt = _linked_text(data, 0x100 + pointer, floor, prompt=True)
            else:
                issues.append("No prompt reference stored.")
        except ValueError as exc:
            issues.append("Prompt: " + str(exc))
        # Follow explicit TLV lengths; a bad tail cannot consume the next PARM.
        next_starts = [d for d in by_descriptor if d > p.offset - 27]
        limit = min(next_starts) if next_starts else len(data)
        cursor = p.offset + 14
        records = {}
        try:
            while True:
                if cursor >= limit:
                    raise ValueError("Missing descriptor-tail terminator.")
                tag = data[cursor]
                if tag == 0xFF:
                    break
                if cursor + 3 > limit:
                    raise ValueError("Truncated descriptor-tail header.")
                size = _u16(data, cursor + 1)
                if size < 3 or cursor + size > limit:
                    raise ValueError("Invalid descriptor-tail length.")
                if tag in records:
                    raise ValueError("Ambiguous repeated descriptor-tail tag.")
                records[tag] = (cursor, size)
                cursor += size
            if 6 in records:
                at, size = records[6]
                if size != 8 or _u16(data, at + 4) != 1:
                    issues.append("Display-hint record shape unsupported.")
                else:
                    hint = _linked_text(data, 0x100 + _u16(data, at + 6),
                                        max(floor, cursor + 1), prompt=True)
        except ValueError as exc:
            issues.append("Descriptor tail: " + str(exc))
            records = {}
        # Values are exposed as tentative meanings, even when bytes are exact.
        if 1 in records:
            at, size = records[1]
            if size == 6:
                try:
                    default = _linked_text(data, 0x100 + _u16(data, at + 4),
                                           max(floor, cursor + 1))
                except ValueError:
                    issues.append("Tag 01 value is binary, unsupported or unavailable.")
            else:
                issues.append("Tag 01 value-record shape unsupported.")
        if 2 in records:
            at, size = records[2]
            count = _u16(data, at + 3) if size >= 7 else 0
            if not 1 <= count <= 64 or size != 7 + 5 * count:
                issues.append("Tag 02 value-list shape unsupported.")
            else:
                try:
                    values = tuple(_linked_text(data,
                        0x100 + _u16(data, at + 8 + 5 * index),
                        max(floor, cursor + 1)) for index in range(count))
                except ValueError:
                    issues.append("Tag 02 list contains unsupported or unavailable values; list withheld.")
                    values = ()
        definitions.append(ParameterDefinition(p, prompt, hint, default, values, tuple(issues)))
    return DefinitionLinks(tuple(definitions), order, reason)


def prompt_form_lines(obj, links):
    """Non-executing prompt form using explicit per-parameter links."""
    lines = [f"Recovered prompt form: {obj.library_name or '<unassigned>'}/{obj.name}",
             "Read only: no values can be entered; nothing executes.",
             "Labels/hints: empirical binary links. Defaults/values: candidates.",
             "Linked presentation order is not verified against historical F4.", ""]
    if not links.parameters:
        return lines + [links.reason, "Use Summary/Evidence for remaining recovered information."]
    by_ordinal = {p.keyword.ordinal: p for p in links.parameters}
    for ordinal in links.prompt_order:
        item = by_ordinal[ordinal]
        label = (item.prompt.text if item.prompt and item.prompt.text
                 else "[stored prompt blank]" if item.prompt else "[prompt unavailable]")
        lines.append(f"{item.keyword.keyword} — {label}")
        if item.hint and item.hint.text:
            lines.append(f"  Display hint: {item.hint.text}")
        lines.append("  Default candidate: " + (repr(item.default_candidate.text)
                     if item.default_candidate else "unknown / unsupported"))
        if item.value_candidates:
            lines.append("  Linked value candidates: " + ", ".join(repr(v.text) for v in item.value_candidates))
        if item.issues:
            lines.append("  Some attributes unavailable; open the parameter for details.")
        lines.append("")
    lines.extend(["Types, required flags, complete validation rules and CPP pointers remain unknown.",
                  links.reason])
    return lines


@dataclass(frozen=True)
class CommandExploration:
    recovery: ParameterRecovery
    summary: tuple
    evidence: tuple
    processor: tuple | None
    definition: DefinitionLinks


def command_exploration(obj, primary_prefix):
    """Build a bounded display model shared by the guided UI and validation."""
    data = bytes(primary_prefix[:8192])
    recovery = recover_parameter_keywords(data)
    links = recover_definition_links(data, recovery)
    summary = (
        f"Command: {obj.library_name or '<unassigned>'}/{obj.name}",
        "Read-only definition exploration; nothing executes.",
        "Verified recovered origin:",
        f"  Primary LBA: {obj.segment.start_lba:,}",
        f"  Virtual address: {obj.segment.virtual_address:012X}",
        f"  Sample: {len(data):,} bytes in virtual extent order (8 KiB limit)",
        "Library assignment is recovered context, not proof of active status.",
        f"  EPA library: {getattr(obj, 'epa_library_name', None) or 'unavailable'}",
        "  Directory memberships: " + (", ".join(getattr(obj, 'context_library_names', ())) or "unavailable"),
        "Stored identity and payload may be stale or inconsistent.",
        "A complete keyword sequence does not prove semantic consistency.",
        "" if obj.library_name else "Unassigned: library context unavailable; not assumed to be QSYS.",
        "Empirical parameter recovery:",
        f"  Count byte +0x180: {recovery.declared_count}",
        f"  {recovery.reason}",
        "Recovered ordinal order is NOT verified historical F4 prompt order.",
        links.reason,
        f"  Linked nonblank prompts: {sum(bool(p.prompt and p.prompt.text) for p in links.parameters)}",
        "Prompt labels/hints follow bounded empirical references.",
        "Default/value meanings are candidates; full validation rules unknown.",
        "Unknown: types, required flags, message-file and CPP pointers.",
        "Candidate processor lookup matches names only; it does not prove a link.",
    )
    return CommandExploration(recovery, summary,
                              tuple(command_information_lines(obj, data)),
                              candidate_processor(data), links)


def parameter_information_lines(obj, parameter, definition=None):
    """Show exact evidence without assigning adjacent strings to this parameter."""
    lines = [
        f"Command: {obj.library_name or '<unassigned>'}/{obj.name}",
        f"Parameter keyword: {parameter.keyword}",
        f"Stored ordinal: {parameter.ordinal} (not verified F4 order)",
        "Empirically validated binary fields:",
        f"  EBCDIC keyword: primary +0x{parameter.offset:04X}, 10 bytes",
        f"  Big-endian ordinal: +0x{parameter.offset + 10:04X}, 2 bytes",
        f"  Four NUL anchor bytes: +0x{parameter.offset - 4:04X}",
        f"Origin: primary LBA {obj.segment.start_lba:,}",
        f"Virtual primary address: {obj.segment.virtual_address:012X}",
        "Offsets refer to reassembled payload, excluding sector headers.",
        "", "Unknown / not decoded:",
        "  Data type, length, required/optional and complete validation rules",
        "  Prompt text, message-file links, QUAL/ELEM relationships",
        "Use Back, then Evidence for unclassified whole-command text.",
        "Adjacent strings are not attributed to this parameter.",
        "Nothing can be entered or executed here.",
    ]

    if definition is not None:
        extra = ["Linked parameter attributes (empirical byte references):"]
        for title, record in (("Prompt", definition.prompt), ("Display hint", definition.hint)):
            if record is None:
                extra.append(f"  {title}: unavailable")
            else:
                extra.extend([f"  {title}: {record.text or '[stored blank]'}",
                              f"    Record +0x{record.offset:04X}; message ID: {record.message_id or '[blank]'}"])
        extra.append(f"  Prompt reference field: +0x{parameter.offset - 6:04X}; base +0x0100")
        extra.append("Tentative semantics (not full validation rules):")
        if definition.default_candidate:
            value = definition.default_candidate
            extra.append(f"  Tag 01 default candidate: {value.text!r} at +0x{value.offset:04X}")
        else:
            extra.append("  Default: unknown / unsupported")
        for value in definition.value_candidates:
            extra.append(f"  Tag 02 value candidate: {value.text!r} at +0x{value.offset:04X}")
        extra.extend("  " + issue for issue in definition.issues)
        lines[3:3] = extra + [""]
        lines = [line for line in lines if line != "  Prompt text, message-file links, QUAL/ELEM relationships"]
        lines.append("Unknown: message-file pointers, QUAL/ELEM roles and complete validation.")
    return lines


def candidate_command_description(primary_prefix, command_name):
    """Find a tentative description by repeated V2R3 positional correlation.

    On six independently sampled IBM commands (ADDACC, ADDAJE, ADDPFM,
    CRTCMD, DSPCMD, CALL), a printable descriptor containing the *whole*
    command name and *LIBL or *NONE is followed 0xB8 bytes later by a
    human-readable command heading. The relation is EMPIRICAL, not an IBM
    published on-disk field definition. Return no candidate if conflicting
    values or invalid structure appear.
    """
    name = str(command_name).strip().upper()
    if not _NAME.fullmatch(name):
        return None
    data = bytes(primary_prefix[:8192])
    decoded = data.decode("cp037", errors="replace")
    found = set()
    for match in _RUN.finditer(decoded, 0x160):
        possible = match.group()
        if "*LIBL" not in possible and "*NONE" not in possible:
            continue
        if not re.search(rf"(?<![A-Z0-9#$@_]){re.escape(name)}(?![A-Z0-9#$@_])", possible):
            continue
        begin = match.start() + 0xB8
        if begin >= len(decoded):
            continue
        end = begin
        while end < len(decoded) and end - begin < 80 and "\x20" <= decoded[end] <= "\x7e":
            end += 1
        text = decoded[begin:end].strip()
        if 4 <= len(text) <= 80 and sum(c.isalpha() for c in text) >= 3:
            found.add(text)
    if len(found) != 1:
        return None
    return next(iter(found))


def command_information_lines(obj, primary_prefix):
    """Read-only 5250-style screen lines based on independently observed data."""
    name = getattr(obj, "name", "<unknown>")
    library = getattr(obj, "library_name", None) or "<orphan>"
    segment = obj.segment
    lines = [
        "Display Command Information — recovered image",
        "",
        f"Command  . . . . . . . . . : {name}",
        f"Library  . . . . . . . . . : {library}",
        "Object type  . . . . . . . : *CMD (MI 19/05)",
        "",
        "Verified recovered object information",
        f"  Primary virtual address : {segment.virtual_address:012X}",
        f"  Primary physical LBA    : {segment.start_lba:,}",
        f"  Primary declared pages  : {segment.pages:,}",
        f"  Sampled primary bytes   : {len(primary_prefix):,}",
        "",
        "Command-definition fields — research status",
        "  Processing program : Not yet verified from on-disk format",
        "  Parameter types/values : Not yet structurally decoded",
        "  Defaults/prompting  : See linked prompt view; semantics remain partial",
    ]
    tentative_description = candidate_command_description(primary_prefix, name)
    if tentative_description:
        lines.extend([
            "",
            "Candidate description (empirical V2R3 text relation, not decoded)",
            f"  {tentative_description}",
        ])
    keywords = candidate_parameter_keywords(primary_prefix)
    if keywords:
        lines.extend([
            "",
            "Candidate parameter keyword sequence (V2R3 structural evidence)",
            f"  Raw +0x180 parameter-count candidate: {len(keywords)}",
            "  Ten-byte EBCDIC keywords with ordinal at +10; prompt semantics",
            "  and defaults are NOT decoded from the descriptor fields.",
        ])
        lines.extend(
            f"   {entry.ordinal:>2}  +0x{entry.offset:04X}  {entry.keyword}"
            for entry in keywords
        )
    maybe = candidate_processor(primary_prefix)
    if maybe:
        lines.extend([
            "",
            "Candidate processor names (tentative; not validated pointers)",
            f"  Raw +0x102 PGM text : {maybe[0]}",
            f"  Raw +0x10C LIB text : {maybe[1]}",
        ])
    lines.extend([
        "",
        "Embedded EBCDIC text evidence (unclassified; offsets in primary)",
        "  These are strings, NOT verified command parameters or help text.",
    ])
    evidence = embedded_ebcdic_text(primary_prefix)
    if not evidence:
        lines.append("  No qualifying text found within the bounded sample.")
    else:
        lines.extend(f"  +0x{offset:04X}  {value}" for offset, value in evidence)
    lines.extend([
        "",
        "Forensic note: an incomplete single-disk image may omit owned storage.",
        "No commands are executed. The original image is never modified.",
        "F12/Backspace: previous screen",
    ])
    return lines
