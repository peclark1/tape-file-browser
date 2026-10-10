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


def candidate_parameter_keywords(primary_prefix, *, max_count=64):
    """Recover a structurally corroborated V2R3 compiled keyword sequence.

    Across eight distinct sampled command primaries, the candidate parameter
    count occurs at primary +0x180, the first ten-byte blank-padded EBCDIC
    keyword at +0x19C, and its big-endian ordinal follows at +10.
    Further keyword/ordinal pairs occur in increasing byte order with variable
    descriptor lengths. A four-byte NUL prefix anchors each candidate.

    This is observational recovery, not a published format or validation of
    PARM semantics, types, defaults, prompts, or pointers. Fail closed unless
    the complete expected ordinal sequence is present and unambiguous.
    """
    data = bytes(primary_prefix[:8192])
    if len(data) < 0x1A8 or data[0x17E:0x180] != b"\x81\x00":
        return ()
    count = data[0x180]
    if data[0x181] != 0 or not 1 <= count <= min(max_count, 64):
        return ()

    def keyword_at(offset, ordinal):
        if offset < 4 or offset + 12 > len(data):
            return None
        if data[offset - 4:offset] != b"\x00" * 4:
            return None
        name = _object_name(data[offset:offset + 10])
        if name is None or int.from_bytes(
            data[offset + 10:offset + 12], "big"
        ) != ordinal:
            return None
        return name

    first_offset = 0x19C
    first = keyword_at(first_offset, 1)
    if first is None:
        return ()
    found = [ParameterKeywordEvidence(1, first_offset, first)]
    previous = first_offset

    for ordinal in range(2, count + 1):
        # The largest observed gap in the independent test corpus is <128B.
        # Allow some slack, but never search unrelated help/text pages.
        end = min(len(data) - 12, previous + 12 + 256)
        possibilities = [
            (offset, keyword)
            for offset in range(previous + 12, end + 1)
            if (keyword := keyword_at(offset, ordinal)) is not None
        ]
        if len(possibilities) != 1:
            return ()
        offset, keyword = possibilities[0]
        found.append(ParameterKeywordEvidence(ordinal, offset, keyword))
        previous = offset
    return tuple(found)


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
        "  Parameters         : Not yet structurally decoded",
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
