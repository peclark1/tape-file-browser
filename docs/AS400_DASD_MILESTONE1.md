# CISC AS/400 DASD Explorer — Milestone 1

## Scope

This milestone adds a read-only command-line structure explorer for raw CISC
AS/400 DASD images. The primary target is the IBM AS/400 9404 B10 using IBM
0671S15 520-byte DASD.

The important design rule is to keep **documented facts** separate from
**experimental interpretations**. We know the physical sector size and CISC page
size. We do not yet have a sufficiently validated byte/bit definition of the
entire eight-byte storage-management header to hard-code it as authoritative.

The first executable milestone therefore performs evidence-driven structure
analysis and reports confidence explicitly.

## Confirmed physical model

For the target CISC systems:

```text
520-byte physical DASD sector
    8-byte storage-management header
  512-byte CISC storage page
```

The surviving IBM 0671S15 used in the B10 project reports 616,392 sectors of
520 bytes each.

The parser rejects input whose size is not an exact multiple of 520 bytes.

## Why the scanner starts with the sector headers

IBM System/38 storage-management documentation describes auxiliary-storage pages
as self-defining and describes recovery logic that can rebuild storage
directories by scanning DASD records and reconstructing virtual-address and
extent relationships.

Early CISC AS/400 documentation preserves the same broad architecture:
single-level storage, six-byte virtual storage addresses/SIDs, storage
management directories, extents, and scatter-loaded objects.

That makes the sector header the most useful starting point for an offline
browser.

## Current header strategy

Direct 9404 documentation describes a six-byte virtual storage address, but the
exact placement and bit allocation inside the eight-byte DASD header still needs
validation on a real B10 image.

Milestone 1 therefore evaluates candidate layouts instead of asserting one:

- six-byte windows beginning at header byte 0, 1, or 2;
- big-endian and little-endian interpretations;
- address increments of 1 (page-number interpretation);
- address increments of 512 bytes (byte-address interpretation).

For each candidate, the scanner measures how often adjacent physical sectors
advance by the expected stride.

The strongest candidate is reported as a **header hypothesis**, never as a
confirmed decoded field.

## Region reconstruction

Once a candidate layout is selected, the scanner identifies:

- consecutive all-zero headers;
- consecutive all-FF headers;
- long physical runs whose inferred address advances by the selected stride;
- remaining unclassified areas.

A sequential address run is only emitted when at least four consecutive sectors
match by default. The threshold is configurable with `--min-run`.

The terms `zero-header`, `ff-header`, `address-run`, and `unclassified`
are intentionally descriptive. Milestone 1 does **not** equate zero headers with
free space or address runs with a particular IBM object type.

## Multi-disk behavior

The `map` and `scan` commands accept multiple images:

```bash
as400-dasd map disk5.hda disk6.hda
```

For a disk set, the report shows:

- whether the independently selected header hypothesis agrees across disks;
- total sectors scanned;
- inferred virtual-address coverage from sequential runs on each image.

This is important because AS/400 single-level storage can scatter pieces of an
object across multiple disk units in an ASP.

## B10 validation anchor

The 9404 Service Guide documents a 64-KB shadow error log maintained on the
load-source disk at virtual address:

```text
0000 8300 0000
```

The current scanner automatically searches for `0x000083000000` using its best
header hypothesis and reports any matching LBA.

Finding that address at the beginning of a coherent 64-KB region would be a
strong validation signal for the selected header interpretation.

## Commands

### Geometry

```bash
as400-dasd info disk5.hda
as400-dasd info disk5.hda disk6.hda
```

No full scan is required. This verifies file size, sector count, and the fixed
520/8/512 geometry.

### High-level map

```bash
as400-dasd map disk5.hda disk6.hda
```

Reports header classes, the strongest address hypothesis, confidence, longest
sequential runs, the B10 validation anchor, and a multi-disk overview.

Useful development options:

```bash
as400-dasd map disk5.hda --limit 100000
as400-dasd map disk5.hda --min-run 8 --top 25
```

### Physical regions

```bash
as400-dasd regions disk5.hda
as400-dasd regions disk5.hda --only-runs
```

This is the detailed LBA-oriented view.

### Raw sector inspection

```bash
as400-dasd sector disk5.hda 12345
```

Shows:

- LBA and byte offset;
- raw eight-byte header;
- candidate six-byte address interpretations;
- EBCDIC preview of the 512-byte page;
- payload hex dump.

### Repeatable report

```bash
as400-dasd scan disk5.hda disk6.hda --report dasd-report.txt
```

The report is intended for comparing:

- the surviving original B10 disk;
- a load-source image;
- initialized/replacement ZuluSCSI images;
- images before and after AS/400 storage-management operations.

## What Milestone 1 does not claim yet

The current code does not yet identify:

- the static directory;
- the permanent directory;
- the free-space directory;
- exact extent-descriptor fields;
- segment-group headers;
- machine objects;
- contexts/libraries;
- user-visible `*FILE`, `*PGM`, and other OS/400 objects.

Those are the next layers.

The current region map is intended to give us the evidence needed to implement
them without inventing byte layouts.

## Immediate real-image validation plan

The first run against a B10 image should capture:

```bash
as400-dasd info DISK.hda
as400-dasd map DISK.hda --top 30
as400-dasd scan DISK.hda --max-regions 500 --report DISK-dasd-report.txt
```

Then inspect:

1. which six-byte header candidate wins;
2. whether the winning model has a high sequential ratio;
3. whether the same model wins independently on both disks;
4. whether `000083000000` resolves on the load-source image;
5. the longest sequential address runs and their alignment;
6. transition sectors immediately before/after those runs;
7. EBCDIC/hex contents at candidate structure boundaries.

If the header hypothesis is strongly validated, the next implementation step is
to replace the heuristic address decoder with the documented/tested field
layout and begin recovery-style extent reconstruction.

## Testing

Synthetic tests currently verify:

- exact 520-byte geometry;
- sector reads and bounds;
- rejection of malformed image sizes;
- selection of a synthetic six-byte big-endian / 512-byte-stride address model;
- separation of sequential runs by zero-header gaps;
- lookup of the known B10 validation address under a selected layout;
- CLI output for `info`, `map`, `regions`, and `sector`.

Run all project tests with:

```bash
python3 -m unittest discover -s tests -v
```

## Safety

All Milestone 1 DASD operations are read-only. The code contains no path that
opens a DASD image for writing.

Write support should remain out of scope until the storage structures are
substantially better understood and validated.
