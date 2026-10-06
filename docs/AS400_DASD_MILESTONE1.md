# CISC AS/400 DASD Explorer — Milestone 1

## Scope

This milestone adds a read-only command-line structure explorer for raw CISC
AS/400 DASD images. The primary target is the IBM AS/400 9404 B10 using IBM
0671S15 520-byte DASD.

The important design rule is to keep **documented facts** separate from
**experimental interpretations**. We know the physical sector size and CISC page
size. We do not yet have a sufficiently validated byte/bit definition of the
entire eight-byte storage-management header to hard-code it as authoritative.

The first real B10 image has now been analyzed. That changed the milestone from
a generic header-pattern experiment into an evidence-backed extent
reconstructor. Unknown flag bits are still reported conservatively, but the
virtual-page and extent-size interpretation is now checked against real
power-of-two extent boundaries and the documented storage-recovery behavior.

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

## Header interpretation validated on the B10 image

The uploaded `HD60_520_D1_IMAGE_PASS2.hda` is exactly 616,392 x 520-byte
sectors. Its headers reveal a consistent structure:

- the first five bytes act as a 39-bit virtual page identity plus one low status
  bit; shifting the 39-bit page number by nine reconstructs the 512-byte-aligned
  virtual byte address;
- the low nibble of byte 5 behaves as an extent-size exponent:
  `extent_pages = 1 << order`;
- byte 6 is zero in every one of the 616,392 headers in this image, matching the
  documented reserved field;
- the low five bits of byte 7 are retained as pointer field C; the remaining
  control-bit semantics are not yet named.

For example:

```text
LBA 231488  00 A1 C3 01 00 05 00 00  -> VA 00A1C3010000, 32 pages
LBA 231489  00 A1 C3 01 02 05 00 00  -> VA 00A1C3010200
LBA 231520  00 A1 C3 01 40 04 00 00  -> VA 00A1C3014000, 16 pages
```

The second header advances exactly one 512-byte page, while the extent order
matches the power-of-two physical allocation.

## Region reconstruction

The scanner now detects the storage-management origin by looking for a repeated
power-of-two free-space delimiter pattern rather than hard-coding a B10 LBA.

On the surviving B10 disk it finds:

```text
managed origin:       LBA 2,112
delimiter header:     00 00 FC 00 00 0F 00 00
delimiter extent:     32,768 pages
delimiter repeats:    7
```

Those seven extents cover LBA 2,112 through 231,487. The first allocated extent
then begins at LBA 231,488. Alignment is evaluated relative to the detected
storage-management origin.

For allocated extents larger than one page, the first two headers must agree on
extent order and the second virtual address must equal the first plus 512 bytes.
This mirrors IBM's documented recovery use of the first pages of an extent.

On the full B10 image the current reconstruction recognizes 587,748 of 614,280
managed sectors (95.7%), comprising 229,376 free pages and 358,372 pages in
29,198 allocated extent candidates. The remaining 26,532 sectors are retained
as unresolved regions rather than guessed.

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

The scanner resolves `0x000083000000` through reconstructed extents. It is not
present on the surviving D1 image, which is consistent with this not being the
load-source disk. A one-disk P02/load-source image would be especially valuable
as an independent check of both the header interpretation and this known
address.

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

Reports the detected managed-storage origin, free-space delimiter extents,
allocated extent candidates, unresolved regions, extent-size distribution,
largest candidate virtual chains, the B10 validation anchor, and largest
physical extents.

```bash
as400-dasd map disk5.hda --top 25
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

The surviving B10 D1 image has completed this validation step. The next
high-value comparison is an independent CISC image, especially the one-disk P02
image from Mark/Patrik. If the same page-address, extent-order, and delimiter
rules hold there, we can treat this as architecture-level behavior rather than a
B10-specific fit.

The implementation step after that is to identify the permanent/static
directories and associate reconstructed virtual chains with machine objects.

## Testing

Regression tests now include a sanitized real B10 fixture containing only the
eight-byte storage headers for the first 240,000 sectors. The 512-byte page
payloads are not included.

That compact fixture verifies:

- the managed-storage origin at LBA 2,112;
- delimiter header `0000fc00000f0000`;
- seven 32,768-page free extents;
- byte 6 reserved-field behavior;
- 434 allocated extent candidates covering 7,872 pages in the captured window;
- the first 32-page and 16-page extent addresses and boundaries.

Synthetic tests continue to cover geometry, malformed images, sector reads, and
CLI header display. GitHub Actions runs the complete tape + DASD unit-test suite
on pushes and pull requests.

Run all project tests with:

```bash
python3 -m unittest discover -s tests -v
```

## Safety

All Milestone 1 DASD operations are read-only. The code contains no path that
opens a DASD image for writing.

Write support should remain out of scope until the storage structures are
substantially better understood and validated.
