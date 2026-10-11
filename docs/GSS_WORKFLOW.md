# Saved CISC 19/0C GSS offset-table and byte-record inspection

`DSPGSS GSS(*ALL/ADMUVGEP)` selects an individual recovered GSS
primary, shows a page of up to 50 populated saved slot positions,
and opens exact archived byte sequences. Use
`DSPGSS GSS(*ALL/ADMUVGEP) SLOT(11)` to inspect a specific saved
one-based table slot directly. Duplicated offsets retain the
distinct slot numbers; empty or unsupported positions are shown
as unavailable, rather than assigned invented symbols.

## Independent two-image physical evidence

Read-only physical EPA-primary signature and first-page probes
identified 38 named 19/0C GSS candidates on Mark's V2R3 image and
19 on Pete's older B10 image. These are *physical candidates*,
not validated context-recovered application primaries.

All inspected 57 primary headers use a 16-bit `0014` word at
+0x100, a four-byte declared length at +0x102 and a second
declared length at +0x112 that is exactly four less. The stored
length fits their physical primary page counts. Several different
control variants exist and cannot share one guessed decoder.

One independently corroborated, more specific variant is:

| Observed property | Mark V2R3 | Pete B10 |
|---|---:|---:|
| 19/0C 004A/4009 primary candidates | 10 | 5 |
| Matching +0x116 six bytes `0183004A4009` | 10 | 5 |
| Matching +0x120 four bytes `200000F9` | 10 | 5 |
| Two-byte saved slots from primary +0x124 | 176 each | 176 each |
| Nonzero entries in that slot table | 94 each | 94 each |

The first populated offset is `0160`, and each populated 16-bit
offset is **relative to primary +0x124**, not +0x100 or a physical
sector LBA. This anchor is independently testable: on stable
cross-image samples `ADMUVGEP`, `ADMUVGIP`, `ADMUVTIP`,
`ADMUVCIP` and `ADMUVCSP`, these positions point to
`C1`-prefixed saved sequences. Between the 93 pairs of
successive distinct offsets in those examples, each recovered
physical-contiguous sequence ends in `FF00`. The last sequence
does not have that corroborated delimiter; its tail is shown as
`open-tail`, **not** as a fully decoded glyph.

Two Mark variants have alias offsets, so 94 populated slots need
not mean 94 distinct byte records. Some other Mark physical
contiguous-page probes fail a `C1` start check in the later
records. Those failures may be caused by **noncontiguous virtual
extents**; the production browser uses only virtual-address-ordered
recovered extents and withholds damaged/incomplete records.

## What the TUI does and does not know

The code checks saved header words, two mutually confirming length
fields, 176 u16 table slots, in-primary offset bounds, a bounded
per-record length, a leading `C1` marker and an `FF00` boundary
between adjacent distinct pointers. Only up to 64 KiB is read
from a selected virtual primary. Unsupported 0040/0042/0001/0041
variants are withheld pending separate layout research.

The browser shows slot ordinal, exact primary byte offset, alias
status, bounded sequence length and hex chunks. **It does not
claim a mapping to CCSID, a Unicode character, font/glyph, vector
drawing instruction or graphical output.** Naming these things
without period IBM documentation and a verified record interpreter
would make the saved binary evidence appear more certain than it is.

## Validation

`tests/test_gss_workflows.py` exercises 176-slot table parsing,
94 populated invented slot records, empty slots, duplicated
offsets, strict header and length checks, C1/FF00 boundary
withholding, virtual extent gaps, paged TUI selection and Back.
The combined `tools/validate_recent_workflows.py` now includes
GSS in the recent family acceptance queue.

`tools/validate_gss_workflows.py <extracted-image.hda>`
performs one production recovered-object scan, bounds-checks
supported virtual GSS records, exercises slot/detail/Back
navigation and verifies the original SHA-256 before/after.
It prints aggregate counts only and never emits original symbol
bytes. It **must actually be run** on each original before
claiming full recovered-image application acceptance.

GSS is a **partial 45th workflow** in the full 268-type
program. The next gate is verifying the coordinate/segment
encoding and 0040/0042 control variants from applicable CISC
documentation or verified sample geometry.
