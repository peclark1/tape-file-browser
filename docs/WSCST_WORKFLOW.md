# Saved CISC 19/38 WSCST TRANSFORM names and candidate dependencies

`DSPWSCST WSCST(*ALL/QWPPAN2180)` selects an archived
workstation-customization primary, checks a compiled `TRANSFORM`
outer/inner descriptor pair and lists any strict 30-byte EBCDIC
padded identifier fields at primary +0x824 and +0x1024.
A saved field such as `QWPIBM4208` can be followed to all
normally recovered `*WSCST` primaries with that **exact name**
and their individual original LBA/namespace. Opening a recovered
WSCST also shows all other supported WSCST primaries whose
saved fixed-position fields contain its name. Back returns to
the selected source. Duplicate, unassigned and missing matches
are not collapsed.

These are **saved textual correlations**, *not* proven
compiled inheritance pointers, printer models, active printer
configuration, transforms executed by OS/400 or print-job status.

## Independent first-page physical evidence

Mark's V2R3 disk contains **66** physical EPA signature
candidates of 19/38 `*WSCST`, named for devices and drivers
such as `QWPDEFAULT`, `QWPIBM5204` and `QWPPAN2180`.
Pete's B10 disk had **no matching 19/38 physical primary
signatures** under the conservative survey; this does not
establish that the logical type is historically impossible on B10.

Every one of the 66 Mark physical headers exhibited:

| Primary offset | Saved evidence |
|---|---|
| +0x100 | Big-endian 32-bit `00000034` wrapper size |
| +0x104 | Big-endian 32-bit declared byte count |
| +0x108 | `0002` control code |
| +0x10A | EBCDIC `TRANSFORM ` (10 bytes) |
| +0x114 | Repeated `00000034` wrapper size |
| +0x118 | Declared count less 52 |
| +0x134 | `00000036` inner wrapper |
| +0x138 | Another copy of declared count less 52 |
| +0x13C | EBCDIC `TRANSFRM` (eight bytes) |

Saved optional fields are evaluated **only if fully inside the
object's declared byte extent** and are accepted only when they
form a 1–10 character supported EBCDIC object-name shape,
right-blank-padded to exactly 30 bytes. A loose string scan is
not used by the production decoder.

In a separate read-only *physical-contiguous* exploratory probe:

| Saved candidate field | Mark primaries with field in declared bounds | Valid padded name fields | Name matches to another WSCST physical identity |
|---|---:|---:|---:|
| +0x824 | 55 | 18 | 4 |
| +0x1024 | 24 | 13 | 9 |

The 13 exact-name matches include `QWPPAN2180` naming
`QWPIBM4208` at +0x1024 and `QWPIBM2390`
naming `QWPPAN1124` at +0x824. The other strict names
may be programs, printer resources or opaque identifiers; no
object role is invented. Physical adjacency does **not**
prove virtual-contiguous original storage and the production
reader uses reconstructed virtual extents instead.

## Validation and boundaries

`tests/test_wscst_workflows.py` covers both repeated length
fields, the nested TRANSFRM control marker, strict padded names,
out-of-range optional fields, unknown/mismatched identities,
duplicated/unassigned matched target origins, reverse source
links, malformed variants, virtual-extent gaps and Back.

`tools/validate_wscst_workflows.py <extracted-image.hda>`
runs a normal recovered inventory scan, validates supported
wrappers and original offsets, exercises a forward/reverse
same-name select/Back path and checks the image's SHA-256
before and after. It reports aggregate counts only, never
printer settings or saved source bytes. The combined one-scan
acceptance runner includes WSCST as its eighteenth recent type.

**Neither script has yet completed production full-image
application validation on the original Mark/Pete files.**
Synthetic CI and direct physical-sector candidate counts
cannot substitute for recovered-virtual application testing.
This is a **partial type-specific workflow**, not a complete
printer-control transformation or certified WSCST dependency
decoder. The next gate is period-CISC structure evidence for
the compiled transform action table, reference roles and
secondary storage, including older-release applicability.
