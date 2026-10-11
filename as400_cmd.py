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
class CommandExploration:
    recovery: ParameterRecovery
    summary: tuple
    evidence: tuple
    processor: tuple | None


def command_exploration(obj, primary_prefix):
    """Build a bounded display model shared by the guided UI and validation."""
    data = bytes(primary_prefix[:8192])
    recovery = recover_parameter_keywords(data)
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
        "Unknown: types, defaults, choices, prompts, required flags, CPP pointers.",
        "Candidate processor lookup matches names only; it does not prove a link.",
    )
    return CommandExploration(recovery, summary,
                              tuple(command_information_lines(obj, data)),
                              candidate_processor(data))


def parameter_information_lines(obj, parameter):
    """Show exact evidence without assigning adjacent strings to this parameter."""
    return [
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
        "  Data type, length, required/optional, defaults and choices",
        "  Prompt text, message-file links, QUAL/ELEM relationships",
        "Use Back, then Evidence for unclassified whole-command text.",
        "Adjacent strings are not attributed to this parameter.",
        "Nothing can be entered or executed here.",
    ]


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
        "  Defaults/prompting  : Not yet structurally decoded",
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
