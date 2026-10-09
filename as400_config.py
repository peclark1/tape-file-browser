"""Conservative read-only inspection of CISC OS/400 profile/configuration objects.

NOT a structural decoder for OS/400 V2R3 *USRPRF, *DEVD or *MODD.
IBM DSP*/QSYRUSRI/QDCRDEVD API return layouts are not on-disk offsets.

For security, NEVER scan, display, or export arbitrary *USRPRF primary bytes:
credential or authentication material may be present. The user-profile
viewer intentionally shows only verified object identity, storage metadata,
and separately recovered object-name correlations.
"""
from __future__ import annotations

import re

KINDS = {
    (0x08, 0x01): ("*USRPRF", "Display User Profile", "DSPUSRPRF"),
    (0x10, 0x01): ("*DEVD", "Display Device Description", "DSPDEVD"),
    (0x15, 0x01): ("*MODD", "Display Mode Description", "DSPMODD"),
}
_TEXT_RUN = re.compile(r"[\x20-\x7e]{6,}")
_SAFE_NAME = re.compile(r"^[A-Z0-9#@$_.-]{1,10}$")


def config_type(obj):
    return KINDS.get((obj.object_type, obj.object_subtype))


def _ebcdic_text(data):
    return data.decode("cp037", errors="replace").rstrip(" \x00")


def device_identity_candidates(prefix):
    """Observed V2R3 *DEVD identity positions; empirical, not API offsets.

    Across all 42 device-description primary candidates in Mark's V2R3
    raw image, +0x100 contains a two-digit EBCDIC class-like value,
    +0x104 a four-character type-like value (e.g. 3197, 5251, PEER),
    and +0x108 four characters resembling a model (e.g. '  D1', 0011).
    Recognize only byte patterns observed, preserve exact raw text, and
    avoid treating the interpretation as architecturally verified.
    """
    if len(prefix) < 0x10C:
        return ()
    raw_class = prefix[0x100:0x102].decode("cp037", errors="replace")
    raw_type = prefix[0x104:0x108].decode("cp037", errors="replace")
    raw_model = prefix[0x108:0x10C].decode("cp037", errors="replace")
    if raw_class not in ("01", "11", "31"):
        return ()
    if not re.fullmatch(r"[A-Z0-9]{4}", raw_type):
        return ()
    if not re.fullmatch(r"[A-Z0-9 ]{4}", raw_model):
        return ()
    return (
        (0x100, raw_class, "candidate category/class code"),
        (0x104, raw_type, "candidate device type code"),
        (0x108, raw_model, "candidate device model code"),
    )


def mode_name_candidates(prefix, expected_name):
    """Observed first-page strings, not validated named CISC fields.

    On the nine recovered V2R3 *MODD primaries, the first eight bytes at
    primary +0x120 repeat the first eight chars of the EPA name, and the
    eight at +0x12C usually hold #CONNECT or another mode-related name.
    We deliberately DO NOT interpret +0x12C as a decoded field.
    """
    if len(prefix) < 0x134:
        return ()
    name = _ebcdic_text(prefix[0x120:0x128]).upper()
    other = _ebcdic_text(prefix[0x12C:0x134]).upper()
    if not name or name != str(expected_name).upper()[:8]:
        return ()
    result = [(0x120, name, "repeats recovered object name")]
    if _SAFE_NAME.fullmatch(other):
        result.append((0x12C, other, "adjacent name-like bytes, meaning unknown"))
    return tuple(result)


def config_text_evidence(prefix, *, offset=0x100, limit=2048, max_items=14):
    """Bounded unclassified EBCDIC clues from non-user-profile objects.

    Never call on *USRPRF objects; the caller enforces object type. Results
    can contain unrelated data; no security/telecom configuration semantics
    should be inferred from printable bytes alone.
    """
    data = bytes(prefix[:min(max(0, limit), 2048)])
    if len(data) <= offset or max_items <= 0:
        return ()
    decoded = data.decode("cp037", errors="replace")
    results = []
    for hit in _TEXT_RUN.finditer(decoded, offset):
        raw = hit.group()
        value = raw.strip()
        if len(value) < 6 or sum(ch.isalpha() for ch in value) < 4:
            continue
        results.append((hit.start(), value[:88]))
        if len(results) >= min(max_items, 14):
            break
    return tuple(results)


def configuration_information_lines(obj, prefix=b"", *, namesake_objects=(),
                                    owned_segments=()):
    """A familiar but evidence-labeled display for three MI object classes."""
    spec = config_type(obj)
    if spec is None:
        return ["Not a recognized profile/device/mode description primary."]
    name, title, ibm_command = spec
    segment = obj.segment
    lines = [
        f"{title} — recovered image (read-only)",
        "",
        f"Object name  . . . . . : {obj.name}",
        f"Library  . . . . . . . : {obj.library_name or '<unresolved>'}",
        f"Object type  . . . . . : {name} (MI {obj.object_type:02X}/{obj.object_subtype:02X})",
        f"Original OS/400 command : {ibm_command} (reference only; not executed)",
        "",
        "Verified recovered storage",
        f"  Primary virtual address : {segment.virtual_address:012X}",
        f"  Primary physical LBA    : {segment.start_lba:,}",
        f"  Primary declared pages  : {segment.pages:,}",
        f"  Recovered owned segments: {len(owned_segments):,}",
    ]
    for child in list(owned_segments)[:8]:
        role = "primary" if child.is_primary else "secondary"
        lines.append(
            f"    {role}: VA {child.virtual_address:012X} "
            f"LBA {child.start_lba:,} pages {child.pages:,}"
        )
    if len(owned_segments) > 8:
        lines.append(f"    ... {len(owned_segments) - 8:,} other recovered segments")
    lines.extend(["", "Same-name recovered objects (correlation only)"])
    others = sorted(
        [item for item in namesake_objects if item is not obj
         and item.name.upper() == obj.name.upper()],
        key=lambda item: (item.type_code,
                          item.library_name or "",
                          item.segment.virtual_address),
    )
    if others:
        for related in others[:12]:
            lines.append(
                f"  {related.external_type_hint or related.type_code:<11} "
                f"{related.library_name or '<unresolved>'}/{related.name} "
                f"VA {related.segment.virtual_address:012X}"
            )
        if len(others) > 12:
            lines.append(f"  ... {len(others)-12:,} further same-name objects")
    else:
        lines.append("  No separate same-name primary recovered.")
    lines.append("  Matching names do NOT prove logon, device, or pointer linkage.")

    if name == "*USRPRF":
        lines.extend([
            "",
            "User profile fields — not yet structurally decoded",
            "  User status, groups, initial menu, job description: unknown",
            "  Device assignments and authorities: unknown",
            "  Profile/interactive-profile structure: research pending",
            "  Credential/password bytes: intentionally NEVER displayed",
            "  No unclassified string scanning of user-profile storage.",
        ])
    elif name == "*DEVD":
        lines.extend([
            "",
            "Device configuration (V2R3 candidate offsets; not verified fields)",
            "  Device category/model/controller: not structurally decoded",
            "  Configuration strings below are raw evidence, not device fields.",
        ])
        candidates = device_identity_candidates(prefix)
        if candidates:
            for offset, value, meaning in candidates:
                lines.append(f"    +0x{offset:03X} {value!r:<8} — {meaning}")
            lines.append(
                "  Correlation: same offsets in 42/42 sampled V2R3 *DEVD "
                "primaries; field semantics remain provisional."
            )
        else:
            lines.append("  No matching candidate identity pattern in sample.")
    else:
        lines.extend([
            "",
            "Mode description attributes — not yet structurally decoded",
            "  LU6.2 mode characteristics/session limits: unknown",
            "  Empirical V2R3 name-like positions in primary:",
        ])
        candidates = mode_name_candidates(prefix, obj.name)
        if candidates:
            for offset, value, explanation in candidates:
                lines.append(f"    +0x{offset:03X} {value:<10} — {explanation}")
        else:
            lines.append("    No validated name-correlated candidate in sample.")

    if name != "*USRPRF":
        lines.extend([
            "",
            "Bounded EBCDIC text evidence (unclassified; not decoded fields)",
            "  Offsets refer to sampled virtual-order primary bytes.",
        ])
        evidence = config_text_evidence(prefix)
        if evidence:
            for offset, text in evidence:
                lines.append(f"  +0x{offset:03X}  {text}")
        else:
            lines.append("  No qualifying printable strings found in bounded sample.")
        lines.append(f"  Primary bytes sampled: {len(prefix):,} (maximum 2,048)")
    lines.extend([
        "",
        "IBM command/API documentation describes logical output, NOT disk offsets.",
        "Incomplete image/storage can omit related objects and configuration.",
        "F12/Backspace/Ctrl+B: previous screen",
    ])
    return lines
