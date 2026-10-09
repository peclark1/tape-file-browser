# CISC storage-management directories / ASDE research

This is the evidence-first starting point for the phase **after** the DASD
browser/context-index milestone. It does not claim that the permanent-directory
root or a real ASDE has yet been identified in either surviving image.

## Sources and applicability

- IBM, *System/38 Vertical Microcode Logic Overviews and Component
  Descriptions*, SY21-0889-5 (sixth edition, September 1985), Auxiliary Storage
  Management chapter 7, pages 7-9 to 7-12; Main Storage Management chapter 8,
  pages 8-6 and 8-14 to 8-15.
  https://bitsavers.org/pdf/ibm/system38/SY21-0889-5_IBM_System_38_Vertical_Microcode_Logic_Overviews_and_Component_Descriptions_6th_ed_198509.pdf
- IBM, *AS/400 Disk Storage Topics and Tools*, SG24-5693 (2000), appendix B,
  printed pages 193-194. Provides later AS/400 storage-management terminology,
  not a V2R3 CISC binary definition.
  https://www.redbooks.ibm.com/redbooks/pdfs/sg245693.pdf
- Existing independently validated B10 and V2R3 sector-header/second-pass
  reconstructions in `docs/AS400_DASD_MILESTONE1.md`.

System/38 VMC is our strongest available structural reference, **not proof**
that every on-disk byte/offset has remained identical on CISC OS/400 V2R3.

## IBM-documented relationships

These structures must not be confused with `04/01` library/context machine
indexes (an object namespace):

| Structure | Documented role |
| --- | --- |
| Free-space directory | Pageable machine index of unassigned disk extents |
| Permanent directory | Machine index mapping permanent virtual addresses to DASD extents |
| Temporary directory | Corresponding mapping for temporary virtual addresses |
| Lookaside directory | Resident cache of 11-byte single-extent ASDEs |
| Static directory | Resident table for segments needed without consulting pageable directories (including the directories themselves and VMC code) |
| Storage Management Vector Table (SMVT) | Storage-management control block containing the static directory; portions are preserved on DASD at shutdown/critical points |

System/38 chapter 8 describes lookup as static -> lookaside -> permanent or
temporary directory (for non-access-group references). Thus the **static
directory is not another context** and is not necessarily a freely identifiable
standalone on-disk index. Identifying surviving SMVT data and the static roots
must precede interpreting presumed permanent-directory bytes.

IBM says free-space directory entries are **7-byte extent descriptors** with
unit number, extent size, and first relative record. Do not mistake these for
ASDE's different per-entry extent fields without further proof.

For the permanent directory, chapter 7 states that the ASDE records have sizes
**11, 16, 21, or 26 bytes**, holding the first mapped virtual address plus
**one through four extent descriptors** (Figure 7-4 labels base segment
identifier, first page identifier, flags/reserved, and extent descriptors).
As an accounting **hypothesis**, those lengths permit a six-byte prefix and
five additional bytes per descriptor. The raw evidence helper uses only this
length arithmetic, not guessed individual field offsets or names.

**Manual inconsistency to resolve:** chapter 8's searchable transcription gives
`11-,18-,21-, and 28-byte` ASDE sizes, while chapter 7 gives
`11-,16-,21-, and 26-byte`; the same chapter 8 calls lookaside entries
11 bytes. This may be a **6-versus-8 OCR/transcription artifact**, not a true
printed technical disagreement. The chapter 7 arithmetic is internally regular
but **not sufficient to assign a release-specific ASDE byte layout**. Verify
against the original figure and real entries rather than silently choosing.

## Already observed on our two disk images

The existing independent header-based pass validates the 520-byte physical
sector (8-byte header + 512-byte CISC page), records relative-record-zero
origins, recognizes permanent extent candidates, and reconstructs exact
virtual-contiguous segment groups. This supplies the independent side of a
future ASDE-to-sector test; it does **not** itself identify an ASDE.

The completed permanent-context machine-index traversal is useful as a
machine-index *implementation reference*, but its root placement, key
representation, and page/header assumptions must **not** be copied into
storage-directory parsing without validation.

### First independent raw-image reconnaissance

An initial read-only check of the first 8,192 physical sectors in each
available image (counting payloads with at least one nonzero byte, **not**
interpreting a directory) found:

- Mark's single-disk V2R3 image: 8,062 nonzero 512-byte payloads.
  The previously established relative-record origin is LBA 64; that sector
  has a nonzero payload and a nonzero preassigned virtual-address header.
- Pete's surviving B10 **non-load-source** disk: only 3 nonzero payloads in
  the same LBA window (32, 33, 52). Its inferred relative-record origin
  is LBA 2,112.

This supports prioritizing Mark's image for early-boot/SMVT/static-directory
reconnaissance, since Pete's surviving disk is **not** the load-source disk.
It does **not** identify any of these pages as the SMVT or a directory, and
the difference may also reflect disk initialization/layout choices. No raw
image contents are committed.

### Corrected VMC/SMVT module-name reconnaissance

**Correction to the first pass:** the original literal seven-character
search for `#SMSMVT` counted **332 substrings of a different eight-character
name, `#SMSMVTN`**. It found no evidence of the exact eight-character
space-padded name `#SMSMVT ` (IBM's System/38 SMVT module label).
This was a real false-positive category, not evidence that the actual
SMVT was located at LBA 65,673.

A second read-only full-image pass uses **fixed eight-byte EBCDIC CP037
name comparisons**, with trailing EBCDIC space padding only for names shorter
than eight characters. All matches are confined to individual 512-byte
payloads:

| Exact eight-byte candidate name | Mark V2R3 | Pete B10 non-load-source |
| --- | ---: | ---: |
| `#SMSMVT ` (seven-character name + EBCDIC space) | 0 | 0 |
| `#SMSMVTN` (distinct eight-character name) | 332 | 0 |
| `#SMSMVTI` (different eight-character name) | 0 | 0 |
| `#SMACDIR` | 18 | 0 |
| `#SMMSIT ` | 8 | 0 |
| `#SMDR2  ` | 8 | 1 |

The first `#SMSMVTN` match is at LBA 65,673, payload offset `0x118`.
The surrounding bytes contain other fixed-width names such as `#SMTRFIO`;
the name often appears amid groups of module references rather than as an
identified initialized table. The first `#SMACDIR` eight-byte name is at
LBA 68,342, payload offset `0x108`, again near compiled module metadata.
These are **potential linker/name-reference structures**, not identified
resident SMVT records or storage-directory root pointers.

An additional raw-byte corroboration strengthens that *limited* classification:
**324 of 332** `#SMSMVTN` names are immediately preceded (in the same
512-byte payload) by four bytes `02 00 00 00`; **295 of 332** occur in
physical sectors whose eight-byte storage headers are `00 00 11 00 00 0C
00 00` (others are in smaller groups or isolated sectors). Thus many
appear to be entries of a recurring compiled-name/reference representation.
The four-byte prefix itself is **not** assigned a semantic field name.
`storage-labels` prints the preceding four bytes for each listed hit.

**Reproduce with the CLI:** `as400-dasd storage-labels IMAGE` now defaults
to space-padded eight-byte name matching (reporting both `#SMSMVT` and
`#SMSMVTN` separately). To reproduce the older inflated 332 count for
the seven-character prefix, explicitly use
`as400-dasd storage-labels IMAGE --symbol '#SMSMVT' --substring`.
The `--start-lba` and `--sectors` arguments bound the scan. These are
forensic name observations only; there are no inferred ASDE mappings.

**Source applicability:** SY21-0889-5 is a System/38 VMC reference. Its
`#SMSMVT`/SMVT descriptions cannot by themselves establish that a V2R3
AS/400 nucleus uses the identical exact compiled module label, location or
layout. A distinct `#SMSMVTN` name could reflect a release-specific
identifier or another relationship; its role is still unknown.

### Independently cross-checked extent-relative VMC references

This is **positive address evidence**, unlike the earlier name-only search.
On Mark's V2R3 load-source image:

1. Physical **LBA 65,600** begins an observed 4,096-page extent with
   sector header `00 00 11 00 00 0C 00 00` (the known header-order
   interpretation gives base virtual address `0x000011000000`).
   Its physical extent spans **LBA 65,600..69,695**, consistent with the
   adjoining different-address extent at LBA 69,696.
2. The virtual byte address derived for physical **LBA 68,860** is
   `0x000011197800`: `0x000011000000 + (68860 - 65600) * 512`.
3. Two six-byte big-endian values **within LBA 68,860's payload** resolve
   back into that same independently mapped physical page:
   - At payload **+0x178**, value `0x000011197988` points to
     payload **+0x188** (a structured row containing the eight-byte
     `#SMLAD  ` name).
   - At payload **+0x180**, value `0x0000111979A0` points to
     payload **+0x1A0** (a distinct binary entry beginning with
     `08 80 03 EA`).

The exact value-to-target arithmetic and pointer widths can be repeated
with `as400-dasd virtual-xref IMAGE 65600 68860 376` and
`as400-dasd virtual-xref IMAGE 65600 68860 384`.
This command requires the caller to supply a physically corroborated
extent start and a pointer offset; it does **not** locate a directory, choose
a candidate field automatically, or assign a VMC module schema.

The page also contains two `#SMSMVTN` references (payload +0x88 and
+0x198), with a repeated structured header near the first. The agreement
supports the narrower hypothesis that this is compiled VMC
module/linkage metadata with live internal pointers. It does **not**
establish that the initialized SMVT table, static directory, or permanent
directory root begins at this page. Further pointer-following must
distinguish metadata linkage from actual directory contents.

### Stronger evidence required

Instead of following the first substring hit as a presumed SMVT location,
look for an independently validated **data-structure location or pointer
chain** (startup loader records, compiled nucleus module directories,
a corroborated resident module address, and/or actual static directory entries
that cross-check known disk extents). Keep module-name references, resident
SMVT identification, static-directory entries, and the pageable permanent
machine-index root separate.

## Next reproducible experiments (read-only)

1. Inventory candidate VMC/SMVT/static-directory locations from period
   documentation and recovered **real** segment/header evidence. Record why
   each location is a candidate; raw byte resemblance alone is insufficient.
2. Identify a directory machine-index root by corroborated header/tree
   structure and address references, avoiding a full-image random signature
   search promoted as identification.
3. Extract bounded raw terminal candidates from that identified index. Report
   their exact image, virtual address, LBA, segment and offset, plus candidate
   key length. Use the `asde-probe` raw-shape helper only for this initial
   inspection; it is **not an ASDE detector**.
4. Resolve the header/prefix and the 1-4 extent-descriptor encodings by checking
   at least several independent entries against the header-derived extent map:
   device number, relative record origin, page count, virtual address range,
   and exact extent boundaries. Require cross-image testing before promoting
   an architecture-level decoder.
5. Preserve disagreements and possible stale-directory state; do not silently
   force a directory entry to agree with the recovery scan. A partial disk may
   not retain all extents in a segment.

### Deferred until byte-level validation

- Meaning of individual ASDE prefix bytes, flag bits and extent descriptor
  fields.
- Fixed locations or page sizes for the storage-directory machine indexes.
- Assertion that surviving V2R3 static/SMVT state maps directly to the current
  reconstructed permanent-directory contents.

All disk-image reads remain read-only. Do not commit real entries, source text,
or image data; synthetic test bytes may exercise the evidence helpers.
