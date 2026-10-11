# CISC 19/08 edit-description pattern comparison

The read-only Guided 5250 explorer implements
`DSPEDTD EDTD(*ALL/QEDIT*)`, selecting distinct recovered 19/08
`*EDTD` primaries by name/library/LBA. Each supported primary
presents a bounded candidate 30-byte punctuation/zero pattern with
1-based positions, literal CP037 rendering with blanks preserved,
exact hex, an optional short sign token, and an observed Y/N-shaped
flag. Selecting a peer edit description allows comparisons and Back
returns to the exact prior selection.

## Two independently sampled original CISC images

Direct read-only 512-byte physical primary sampling (no assumption
of adjacent physical sectors) found:

| Image | 19/08 signature candidates | Supported observed instances |
|---|---:|---|
| Mark V2R3 | 5 | QEDIT5, QEDIT6, QEDIT7, QEDIT8, QEDIT9 |
| Pete B10 | 2 | QEDIT6, QEDIT8 |

All seven have an EBCDIC decimal digit corresponding to the final
digit of their QEDIT name at primary +0x100; a 30-byte printable
punctuation and blank region at +0x124..+0x141; a one-byte
sign-token length at +0x188; sign-token bytes beginning +0x189
(`CR`, `-`, or empty in these instances); and an EBCDIC
Y/N-shaped byte at +0x1C9. The QEDIT6 and QEDIT8 saved patterns,
sign tokens and flags agree between Pete and Mark.

Observed +0x124 region includes saved comma- and dash-shaped bytes,
blanks and a `0` glyph. The software preserves these raw positions,
but does **not** claim that it understands edit-description numerical
rules, decimal location, negative-value insertion, output CCSID or
whether the Y/N flag is a particular historical formatting option.
Later IBM i edit-code behavior is not automatically the stored CISC
19/08 on-disk layout.

The decoder checks a complete first virtual sector, matching
supported leading EBCDIC digit, printable 30-byte pattern, short
printable sign, corroborated Y/N variant, and QEDITd/name equality
when that conventional identity is used. Other layouts are
withheld rather than silently interpreted. The peer list is based on
recovered type identity alone, not guessed binary pointers.

## Validation and status

`tests/test_edit_description_workflows.py` covers numeric header,
30-byte template position/length, comma/zero glyphs, blank preservation,
`CR` and `-` signs, Y/N variants, truncation, corrupt or nonprintable
bytes, wrong-type identity, virtual extent gaps, exact-origin peer
selection and Back.

`tools/validate_edit_descriptions.py <image.hda>` is an opt-in
read-only **complete recovered-object** audit with before/after
SHA-256 checks and aggregate counts. It does not print recovered
application data and must actually be run on both originals before
claiming full-image validation.

No original recovered data, user-private values or documentation
scans are committed. `*EDTD` is counted as an audited **partial
user-visible workflow**, not a complete numerical edit interpreter.
The next research gate is verified numeric input/output examples and
period CISC storage documentation for real field semantics.
