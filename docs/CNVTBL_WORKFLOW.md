# CISC saved CNVTBL table-position explorer — physical evidence and guided workflow

**Scope:** an empirical, read-only MI 19/FB (`*CNVTBL`) two-byte-pair structure,
not a decoding of historic OS/400 CCSIDs or a claims that saved pairs contain
Unicode values. No conversion is performed.

## Independently observed evidence, October 10, 2026

Read-only complete 520-byte physical sector EPA-signature survey of both
provided archival disk images, without writing the sources:

| Image | 19/FB physical primary candidates | Raw +0x100 | Saved pair interval |
|---|---:|---|---|
| Mark V2R3 | 41 (41 distinct raw names) | 21 `0001`, 20 `0002` | 256 two-byte entries at +0x102..+0x301 |
| Pete B10 | 0 | not observed | not observed |

All 41 inspected first primary pages begin the 256-pair region at +0x102,
with the entry at position 128 starting at +0x200 (next logical page).
A direct physical-neighbor check found table-like continuation in all 41,
but **the physical neighbor check cannot establish correct saved virtual
extent assembly**. The production decoder uses the existing virtual-ordered,
gap-sensitive `read_prefix` path and requires the full 0x302-byte range.

In particular, the layout visibly stores adjacent pairs such as
`00 00 / 01 00 / 02 00`. We do **not** assume that they
are 16-bit little-endian characters, IBM big-endian numeric words,
CCSID code points or mappings in either direction; preserving the two
bytes avoids promoting an unsupported interpretation. A zero hit on
Pete does not establish historic OS/400 absence.

## Material Guided 5250 workflow

```text
DSPCNVTBL CNVTBL(*ALL/TBT*)
DSPCNVTBL CNVTBL(*ALL/TBT61Q037A94A3Q) POS(128)
```

Pick any returned recovered `*CNVTBL` origin, page forward/backward through
32 saved positions, Enter to inspect an exact two-byte entry and primary
byte offset, and Back to return to the original selected row. The table view
also compares exact bytes with other supported recovered 19/FB primaries,
showing exact-match counts and per-pair difference totals, and allows
navigating to a peer and back. Names and origins are not collapsed.

- Only raw +0x100 variants `0001` and `0002` are supported.
- Malformed/truncated or gap-separated primary content is withheld.
- Unsupported comparison peers are counted rather than called unequal.
- No raw disk payload or private recovered strings are committed.
- Real-image sector observations remain separate from normal recovered
  object/UI acceptance. That full-app test is still required.

## Tests

```bash
python3 -m unittest discover -s tests -p 'test_cnvtbl_workflows.py' -v
python3 -m unittest discover -s tests
python3 as400_dasd_tool.py browse5250 /path/to/marks.hda
```

These synthetic tests use invented table bytes and cover 256 positions
(including logical-page boundary), header variants and type guards,
unavailable/gapped sectors, duplicate-origin peer comparison, command
routing, selection and Back. Manually verify the normal recovered-object
view on Mark's extracted original, including fields in the second virtual
page. Do not imply that a standalone physical-primary scan is the same
as full app validation.
