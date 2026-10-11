# Saved CISC product load and product definition comparison

## Real archival image observations (physical-primary candidates only)

A read-only full-image EPA-signature pass, followed by bounded first-page
checks, found:

| Type | Mark V2R3 | Pete B10 |
|---|---:|---:|
| 19/1D PRDLOD | 40 physical candidates, 38 distinct EPA names | 0 |
| 19/1B PRDDFN | 3 physical candidates | 4 |

All 40 Mark 19/1D first pages have big-endian 0x0000014A at primary
+0x100, 24 printable EBCDIC bytes at +0x104..+0x11B, the
EBCDIC `00010200` token at +0x15C and a 10-byte padded +0x164
literal self-name exactly equal to the independent EPA object name
(40/40 matches). This strongly establishes **stored name echo**
but not the significance of the 24-byte token. There are repeated
24-byte token bodies across multiple object origins, which the UI
compares by raw byte equality only.

For PRDDFN, all four Pete first pages declare raw +0x100 length 496
(0x1F0), with 52 printable EBCDIC bytes at +0x104..+0x137 and
12 printable EBCDIC bytes at +0x138..+0x143. Saved examples
correspond to literal IBM text, but neither string has an independently
established structural field name, vendor-identifier role, license
entitlement or release-number interpretation. Three Mark V2R3 PRDDFN
candidates instead have raw +0x100 values 703, 26353, and 32053,
and the same 64-byte region entirely filled with EBCDIC blanks.
They use an **alternate unknown layout**; the UI explicitly withholds
a synthetic text interpretation.

On Mark there are two matching names across PRDLOD and PRDDFN
(QPZ0050 and QSZ0050); on Pete no PRDLOD primary signatures
occur. This independently supports candidate same-name navigation,
but **not** a proven dependency or binary ownership relationship.
The full recovered-object app run is still pending; a physical
first-page survey does not establish virtual extent completeness.

## Actual Guided 5250 workflows

```text
DSPPRDLOD PRDLOD(*ALL/QSZ0050)
DSPPRDDFN PRDDFN(*ALL/QSZ0050)
DSPPRDDFN PRDDFN(*ALL/Q5728PC1)
```

Each origin retains original namespace and LBA. For supported PRDLOD
objects, inspect observed raw bytes and selectable other-load peers
with identical 24-byte tokens. Navigate the same-name PRDDFN
candidate and Back to the saved selection; the reverse view
also lists duplicate/unassigned PRDLOD matches. Pete B10 PRDDFN
objects display bounded literal text regions and show their lack
of recovered matching load candidates without claiming historical
absence. Mark unknown PRDDFN variants retain identity links and
show their raw +0x100 values but do not parse nonexistent text.

Source code never writes disk images or executes CL and does not
commit any original saved product text. Type-specific decoders
reject unsupported layouts, short virtual read, name mismatch and
unprintable purported token bytes. Synthetic fixture values are invented.

## Verification

```bash
python3 -m unittest discover -s tests -p 'test_product_workflows.py' -v
python3 -m unittest discover -s tests
python3 as400_dasd_tool.py browse5250 /path/to/marks.hda
python3 as400_dasd_tool.py browse5250 /path/to/petes.hda
```

Normal recovered-virtual-extent image validation, and user terminal
acceptance, remain required before declaring either type universally
decoded. These are two **partial** capabilities.
