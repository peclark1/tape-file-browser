"""Conservative, bounded read-only observations of original CISC OS/400 *CMD.

These are observations of recovered bytes, NOT a decoder of the complete
compiled command-definition format. IBM's QCDRCMDI API is a logical
interface and its format offsets must not be assumed to be on-disk offsets.
"""

import re


_NAME = re.compile(r"^[A-Z#$@_][A-Z0-9#$@_]{0,9}$")
_RUN = re.compile(r"[\x20-\x7e]{6,}")


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
        if len(value) < 6 or sum(letter.isalpha() for letter in value) < 4:
            continue
        # Extremely long runs are often EBCDIC blank space, not field data.
        value = re.sub(r"\s+", " ", value)
        if len(value) > 96:
            value = value[:95] + "…"
        result.append((match.start(), value))
        if len(result) >= min(max_items, 64):
            break
    return tuple(result)


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
