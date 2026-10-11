# CISC V2R3 binding-directory entry and service-program reference explorer

## Guided 5250 usage

`DSPBNDDIR BNDDIR(*ALL/QILE) NAME(QLE*)` opens an individually
recovered **19/37 `*BNDDIR`** primary. It traverses validated
48-byte saved records in 50-entry windows, with exact 1-based entry
ordinal and primary byte offset, EBCDIC display/hex of the entire
record, a ten-byte padded object-name candidate, ten-byte
library-search token, two-byte MI target type and 26 remaining
opaque bytes.

When the stored type is `02/03` (*SRVPGM) or `03/01` (*MODULE),
the tool compares the saved name and raw type with independently
recovered object primaries. Only **candidate identities** are linked.
All original LBA/namespace variants remain selectable, including
duplicate names. Explicit library tokens filter the candidate
namespace exactly; the observed `*LIBL` token does **not** resolve
the archived system library list, choose a particular library, or
prove binding/activation.

`DSPSRVPGM SRVPGM(*ALL/*)` starts from an individually selected
recovered 02/03 service-program primary and reverses these saved
name/type correlations back to the exact binding directory and
entry offset. Selecting that record shows its 48 source bytes and
Back preserves the selected program/source. No service-program
exports/imports, external procedure names, call sites or actual
linker decisions are decoded. In particular, a name/type match is
**not** a resolved linker pointer.

## Original image evidence and supported boundaries

A direct read-only physical primary-signature survey of the
independent Mark V2R3 image identified five 19/37 BNDDIR
candidates. Pete's B10 image had **no 19/37 primary candidate
under this signature heuristic**, so **do not assume this layout
works on an older CISC release**.

On all five examined Mark physical-contiguous primary candidates,
the saved header and array agreed:

- primary +0x100..+0x103: `00 01 00 00`
- primary +0x104..+0x107: unsigned big-endian 32-bit entry count
- primary +0x112..+0x113: unsigned 16-bit record stride `00 30` (48)
- primary +0x116..+0x117: unsigned 16-bit byte size equal to count × 48
- primary +0x130: beginning of complete fixed 48-byte entries
- record +0..+9: EBCDIC name, blank-padded to ten bytes
- record +10..+19: EBCDIC library token, blank-padded to ten bytes
- record +20..+21: raw two-byte MI object type, `02 03` or `03 01`
- record +22..+47: **opaque 26-byte tail**, no address roles assigned

| Mark binding directory primary | Saved entries | Target MI type |
|---|---:|---|
| QSNAPI | 1 | `02/03` service program |
| QLECWI | 1 | `02/03` service program |
| QILE | 3 | `02/03` service program |
| QC2TEMP | 52 | `03/01` module |
| QC2LE | 4 | `02/03` service program |
| **Total** | **61** | 9 service-program, 52 module entries |

All 61 tested entries had `*LIBL` as their saved library
search token. Of the nine service-program entries, nine names
matched an independently observed `02/03` service-program
primary signature candidate by **name and MI type**. Mark's
physical primary census found 21 `02/03` signature candidates
overall, but no `03/01` module primary signatures corresponding
to the 52 QC2TEMP entries. That does not prove the modules were
absent from the historical system: module contents might be in
other disks, segmented storage, temporary objects or previously
discarded primary extents.

These totals are **direct physical-primary probes**, not counts
from a complete application-level recovered virtual-extent
walkthrough. The Guided viewer uses ordered virtual extents via
`read_prefix()` and withholds truncated records, unsupported
header/stride/size, malformed EBCDIC names and excessive counts.
The exact historical use of the opaque 26-byte tail and
actual library-list resolution are **unverified**. A single-release
Mark layout is not applied speculatively to Pete.

## Regression and reproducibility

`tests/test_binding_directory_workflows.py` covers Mark-style
0/1/3/52-record arrays, precise 48-byte fields, unknown target
types, *LIBL ambiguity, absent modules, wrong-type decoys,
duplicate same-name service-program origins, missing target
library, 50-entry pagination, invalid counts/strides/names,
virtual extent gaps, and selected entry → service program →
reverse source → Back.

`tools/validate_binding_directories.py <extracted-original.hda>`
recovers the *normal* production inventory, validates complete
binding record arrays, counts independent target name/type
matches, exercises both Guided commands and Back, and computes
archived SHA-256 **before and after** without printing private
names, recovered bytes or program contents. The consolidated
`tools/validate_recent_workflows.py` also covers both families.

Until those validators actually run on the original extracted
images, whole-image application acceptance remains outstanding.
These are two bounded **partial** workflows, not fully decoded
BNDDIR/SRVPGM objects or a runnable binder.
