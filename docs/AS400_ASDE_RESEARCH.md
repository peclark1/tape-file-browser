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

### Shutdown-module references across both disk images

IBM's System/38 VMC description calls module `#SMSHTDN` the storage-
management shutdown routine responsible for checkpointing the SMVT
after reconciling temporary and permanent directories. This is a
**documented function on System/38**, not a known V2R3 physical
checkpoint address. The readable text layer of the same manual
renders the distinct link/loader SMVT initializer name as
`#SMSMVT1` (digit one); the earlier research probe only included
`#SMSMVTI` (letter I). Because a printed 1/I ambiguity is possible,
retain *both* as separate exact search candidates until the original
printed glyph is verified.

Exact eight-byte CP037 **whole-name** payload scans (counting all
occurrences, not just matching sectors) return:

| Name | Mark V2R3 load-source | Pete B10 non-load-source |
| --- | ---: | ---: |
| `#SMSHTDN` | 10 | 1 |
| `#SMSMVTN` | 332 | 0 |
| `#SMSMVT1` (digit one) | 0 | 0 |
| `#SMSMVTI` (letter I) | 0 | 0 |
| `#SMDR2  ` | 8 | 1 |

The physical **late-image** occurrences are particularly informative:
`#SMDR2` is at Mark physical LBA **1,890,161**, payload +0x0A3;
`#SMSHTDN` is at Mark **1,890,163**, payload +0x079.
On Pete, `#SMDR2` is at physical **573,617**, payload +0x162;
`#SMSHTDN` is at **573,618**, payload +0x0B2.
Those pairs are in short runs whose eight-byte sector headers
start `A0 00 2D` on **both** disks (though the remaining bytes of
the header, positions and physical LBAs differ).

The neighboring sequence of eight-byte module-style names includes
`#SMRUSID`, `#SMRUSIN`, `#SMSGEX`, `#SMSHTDN`, and
`#SMSUBRC` on both images. The recurring names in nearby
physical pages, their broadly preserved order, and the shared
virtual prefix support a **common module-name/linkage-record
interpretation** across releases. They do **not** prove that the
associated shutdown code itself lives at those object-storage
addresses, or that the checkpoint is adjacent to the strings.

**Reproduce:** `as400-dasd storage-labels IMAGE --symbol '#SMSHTDN'
--symbol '#SMDR2' --header-groups 8 --limit 0` (default exact-name
matching). `--header-groups` reports independent eight-byte
sector-header frequencies per searched symbol; it does not
assign a segment type or directory role. The scanner also
includes `#SMSMVT1` and `#SMSMVTI` separately by default.
In an incomplete multi-disk image, the presence or absence
of a module symbol is not evidence for the presence or absence
of a persisted SMVT checkpoint.

**Next gate:** obtain an actual shutdown/initialization *data
reference* or an independent disk-control record that points to
the stored checkpoint. Do not scan arbitrary six-byte values
in object module-reference pages and call the first in-range
value a live SMVT pointer.

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

### Full VMC extent: recurring address-reference families

A read-only two-byte-aligned scan of all 4,096 physical pages belonging to
Mark's previously identified virtual `0x11000000` extent, interpreting
**only** six-byte unsigned big-endian candidates whose value falls inside
the extent's derived virtual span, records:

- **5,216 numeric candidate references** from 2,872 different physical
  source pages, targeting 2,849 distinct physical pages.
- **5,213** of these candidate values begin at a four-byte-aligned source
  offset. Alignment is an observation, not yet a documented pointer-layout
  requirement.
- Strong repeating source-to-target patterns, measured as
  `(source payload offset -> target page delta, target payload offset)`:

| Source offset | Target delta | Target payload offset | Matches |
| --- | ---: | --- | ---: |
| `+0x0F8` | 0 (same page) | `+0x108` | 1,077 |
| `+0x1F8` | +1 (next page) | `+0x008` | 941 |
| `+0x178` | 0 (same page) | `+0x188` | 313 |
| `+0x078` | 0 (same page) | `+0x088` | 277 |

An independent read of the **physical target payloads** strengthens the
record-layout evidence. Among those four pointer-position families, the
following targets begin with the exact raw five-byte sequence
`02 00 00 00 7B` (followed in many examples by an EBCDIC module name
starting with `#`):

| Reference family | Valid in-range VA matches | Target raw-prefix matches |
| --- | ---: | ---: |
| `+0x0F8 -> same +0x108` | 1,077 | 902 |
| `+0x1F8 -> next +0x008` | 941 | 772 |
| `+0x178 -> same +0x188` | 313 | 247 |
| `+0x078 -> same +0x088` | 277 | 225 |

In total, **2,146 of these 2,608 particular VA matches** land on
that repeated raw record prefix. The five bytes are a highly correlated
observed signature, **not** a documented structure name, record size,
pointer field definition, or ASDE header. The `virtual-xref-map` tool
now prints the independent prefix-hit count per pointer pattern as well
as the numeric VA-match count.

A subsequent conservative CP037 interpretation of exactly eight bytes
beginning at **target-prefix +4** yields **572 distinct printable
name-like strings** behind the 2,146 prefix-matched targets. The most
frequently linked examples are `#DBLKMAP` (303 references),
`#SMSMVTN` (126), and `#MSCPQ  ` (118). These are *reference
occurrences*, not distinct loaded modules or a count of SMVT copies.
`virtual-xref-map --names N` now summarizes up to N names with
their reference frequencies. Because this evidence comes from
independently located target bytes, it is stronger than simply counting
all EBCDIC substrings in the physical disk; nevertheless it still
does **not** identify an active SMVT table or its runtime address.

**Reproduce** with
`as400-dasd virtual-xref-map IMAGE 65600 --alignment 2 --top 16`
or restrict to a physical subset using
`--source-start-lba 68860 --sectors 1`.
The command only accepts an **explicit caller-chosen extent** and checks
numeric six-byte values: the statistics do not automatically classify
each value as a genuine pointer, a static-directory entry or a VMC field.

A useful difference between these families: the `+0x0F8` reference
routinely lands at `+0x108`, where fixed-width EBCDIC module names
and associated record bytes are visible; the `+0x1F8` reference
commonly lands on a name/record continuation at `+0x008` of the next
512-byte page. This independently corroborates a recurring **page-spanning
module/reference layout**, but its field names and purpose remain
hypotheses. Some source pages exhibit both local and next-page candidate
references.

**Header nuance:** the initial 4,096-page physical run is delimited
by different virtual header prefixes immediately before LBA 65,600 and
at LBA 69,696. Inside the run, **4,095/4,096** sector headers carry
the common base virtual prefix `0x11000000`; sector 65,601 alone has
prefix `0x11000200`. All 4,096 carry extent-order nibble `0xC`.
Do **not** assume every sector header linearly increments its virtual
field with physical LBA. The candidate target arithmetic uses the
corroborated **extent start** plus page-index offsets, not the per-sector
stored header as an absolute target-page VA.

**Next evidence test:** use recurrent pointers and the linked name
records to find independently corroborated roots, initializer
structures, or a loader/module table that could lead to a resident
SMVT *data structure*. No genuine permanent-directory machine-index
root or ASDE has yet been established.

### Stronger evidence required

Instead of following the first substring hit as a presumed SMVT location,
look for an independently validated **data-structure location or pointer
chain** (startup loader records, compiled nucleus module directories,
a corroborated resident module address, and/or actual static directory entries
that cross-check known disk extents). Keep module-name references, resident
SMVT identification, static-directory entries, and the pageable permanent
machine-index root separate.

### Persisted SMVT checkpoint: bootstrap-sector reconnaissance

**IBM-documented (System/38, not yet proven identical on V2R3 CISC):**
SY21-0889-5, Auxiliary Storage Management chapter 7, printed pp. 7-7
to 7-8, states that auxiliary-storage initialization writes the SMVT
onto drive 1, including the directory-valid bit, segment identifier
generator, **static directory**, free-space values, and an auxiliary
device configuration record. On orderly shutdown, module `#SMSHTDN`
writes an **SMVT checkpoint page** and a directory-good bit. The same
manual's Main Storage Management chapter 8 calls `#SMSMVT` a
nucleus module containing an initialized SMVT and lookaside directory,
while `#SMSMVTI` fixes the table for the link/loader. These are
historical structural clues, not validated addresses in OS/400 V2R3.

**Read-only observed physical sectors in the two images:** inspecting
only physical LBAs **0..63**, without attempting to interpret each
record's binary layout, gives:

| Physical LBA | Mark load-source V2R3 | Pete non-load-source B10 |
| ---: | --- | --- |
| 0 | exact EBCDIC `IMD1` at payload +0 | zero payload |
| 32 | exact `DASD  UNIT  DESC` at +0x40 | same label and offset |
| 33 | `DCT 0300` at +0x18 | `DCT 0100` at +0x18 |
| 52 | `REALLOCATION CONTROL SECTOR` at +0 | same label |
| 54 | nonzero unlabeled binary data | zero payload |
| 55 | exact `DCTX` at +0 | zero payload |
| 60 | `MSD  SEC` at +0 and `DMDMAIN` at +0x18 | zero payload |

Mark has **7** nonzero-payload sectors in this range
(0, 32, 33, 52, 54, 55, 60), Pete has **3**
(32, 33, 52). All these sector headers are eight bytes of zero
in both images, so the existing managed-sector/extent scan correctly
must **not** use the headers to infer their virtual addresses.
The first page of Mark's previously established preassigned
virtual extent begins at LBA 64.

### Independently corroborated DASD unit descriptor geometry

**High-confidence cross-image observation (B10 and V2R3):**
both physical LBA **32** payloads contain exact EBCDIC CP037
`DASD  UNIT  DESC` at offset `+0x40`. The first eight payload
bytes give two big-endian 32-bit values. No IBM manual has yet
established the formal field names, but the arithmetic is exact:

| Independent image | Raw field 1 at +0x00 | Raw field 2 at +0x04 | Sum / actual image sectors |
| --- | ---: | ---: | ---: |
| Mark V2R3 | 64 (`0x40`) | 1,931,201 (`0x1D77C1`) | 1,931,265 / 1,931,265 |
| Pete B10 | 2,112 (`0x840`) | 614,280 (`0x95F88`) | 616,392 / 616,392 |

Independent corroboration: Mark's first nonzero managed-sector
storage header appears at physical LBA **64**, exactly the first raw
value; the immediately preceding header at 63 is all zero. Pete's
image likewise has a nonzero storage header at LBA **2,112** and an
all-zero header at 2,111, even though the first managed page's
**payload** happens to be zero.

Therefore a defensible *observed* interpretation is
`first four bytes = physical relative-record-zero origin` and
`next four = managed-sector count`, with their sum equal to total
disk sectors. This is a **dual-image, independent header and file
length check**; it does not derive from the earlier speculative VMC
name/pointer reference scans. Treat that interpretation as observed
until the formal IBM record layout is found, and do not assume
other words in the record are understood.

### Mark-specific auxiliary descriptor boundary arithmetic

Mark's LBA-32 descriptor has additional, still-unnamed big-endian
32-bit values at payload **+0x08 = 148,224 (`0x24300`)** and
**+0x0C = 64 (`0x40`)**. Pete's corresponding two words are zero.
The Mark-only sum is **physical LBA 148,288**. The independently
read sectors at LBA **148,287** have all-zero headers, while LBA
**148,288** begins a nonzero storage-header run with extent-order
nibble `0x6` (64 pages). The final page indicated by this
size is LBA **148,351**, which also has the run's nonzero header;
the immediately following LBAs **148,352 and 148,353** contain the
exact EBCDIC marker `DELETED EXTENT  ` at payload start.
These observations can be independently reproduced by
`as400-dasd disk-descriptor IMAGE` and `sector` on the four
boundary locations.

This is evidence of a **disk-control-to-storage-boundary relationship**;
it is consistent with a load-source-specific reserved/managed-space
range but neither the official meaning of the two words nor the
post-boundary segment type is established. The `DELETED EXTENT`
token is raw text, not an assignment of free-directory or SMVT
semantics. Crucially, **there is no basis for interpreting LBA
148,288 as an SMVT checkpoint simply because it is a boundary**.

### Raw DCT table at physical LBA 33

Both disk images have an exact CP037 eight-character `DCT NNNN`
label at payload `+0x18`. Their first two bytes form a BE16
candidate count, and the same number of nonzero **32-byte raw slots**
starts at payload `+0x20`:

| Image | DCT label | Raw BE16 at +0x00 | Nonzero 32-byte slots |
| --- | --- | ---: | --- |
| Mark V2R3 load-source | `DCT 0300` | 1 | 1 (at +0x20) |
| Pete B10 non-load-source | `DCT 0100` | 2 | 2 (at +0x20, +0x40) |

Neither image has additional populated 32-byte slots after the
candidate count. The slot lengths/counts are independently
corroborated across two release families and are represented by
`DCTRawEvidence` / `as400-dasd dct-evidence IMAGE`.
Field names, byte meanings, any connection with disk unit IDs,
and the `0100` vs `0300` label suffix are **not decoded**.
The count may reflect devices, but that interpretation requires
more hardware/configuration evidence.

### Bounding the entire physical pre-origin area

Scanning **all physical sectors before the descriptor-correlated
relative-record-zero origin**, not just LBAs 0..63, finds:

- Mark V2R3, LBA 0..63: exactly 7 nonzero-payload sectors
  (0, 32, 33, 52, 54, 55, 60), totaling **198 nonzero payload bytes**.
- Pete B10, LBA 0..2111: exactly 3 nonzero-payload sectors
  (32, 33, 52), totaling **127 nonzero payload bytes**.

All of these sectors have zero eight-byte storage headers. Mark's
physical LBA 55 `DCTX` payload contains only four nonzero bytes;
LBA 60 (`MSD  SEC`, `DMDMAIN`) has 26. This sharply limits
what *actual recorded* bootstrap data survives outside the
sector-header-managed region, and argues against interpreting
these labels as a recovered SMVT/static directory. It does **not**
prove a valid checkpoint cannot be entirely sparse, elsewhere
reserved, or absent in the present capture.

**Reproduce:** `as400-dasd disk-descriptor IMAGE` (default physical
LBA 32). The command insists on the exact EBCDIC payload label,
prints the two raw BE 32-bit values, checks their sum against the
image sector count, and checks the immediately preceding and
at-origin eight-byte storage headers. It **reports mismatches**
rather than forcing them to pass. The input file is read-only.

This geometry record narrows our future SMVT-checkpoint search to
the explicitly managed region on Mark's load-source disk, while
confirming that low physical sectors **before** relative record zero
are not ordinary managed CISC pages. It does **not** identify the
SMVT checkpoint itself.

The repeated physical LBAs and literal labels give a concrete
bootstrap/low-level record comparison. The different `DCT` trailing
versions are *observed text*, not yet a decoded format version.
Nothing here identifies an SMVT checkpoint: in particular,
`DCTX` and `MSD  SEC` are labels and must **not** be assigned
SMVT or directory meanings without more independent evidence.
Nor should a System/38 statement that the checkpoint is on drive 1
be used to assume it occupies the first 64 sectors on V2R3.

**Reproduce:**
`as400-dasd bootstrap-map IMAGE` for default physical LBAs 0..63.
For a larger manually selected range use `--start-lba N --sectors N`
(maximum 4096 per call). The tool records the number of nonzero payloads,
zero-header/nonzero-payload sectors, and exact CP037 marker offsets;
it does not decode system-record contents, persist them, or modify
the image. Tests use only synthetic labels and bytes.

**Next evidence test:** correlate boot/low-level record references and
IBM CISC service/loading documentation to constrain where the
checkpoint is read or written, then inspect any independently
identified candidate for an actual static-directory table of
single-extent ASDEs. Do not blindly search every random 11-byte
window in these sectors as if a matching value were an ASDE.

### Boot preallocation: independently bounded large extents

IBM SY21-0889-5 chapter 7 describes the System/38
`#SMASI` auxiliary-storage initialization path reserving
**two defect-free areas on drive 1 for HMC IMPL segments**, before
allocating other prebuilt segments and writing the SMVT. This
is **System/38 documentation**, not a verified rule for OS/400
V2R3 storage geometry. It provides a limited, testable
hypothesis for the earliest image extents; it does **not**
give a physical SMVT checkpoint address.

A read-only header/descriptor cross-check on Mark's **V2R3
load-source image** begins from the dual-image-correlated
`DASD  UNIT  DESC` first field: physical relative-record
zero at **LBA 64**. Following only explicit extent-order sizes
and comparing *both physical endpoint headers* finds:

| Start–end physical LBAs | Pages | Start header's VA | Last sector has same 5-byte prefix? |
| --- | ---: | --- | --- |
| 64–16,447 | 16,384 | `0x0B000000` | **Yes** |
| 16,448–32,831 | 16,384 | `0x92000000` | **Yes** |
| 32,832–36,927 | 4,096 | `0x92800000` | **No** (last header prefix is `0x92000000`) |

The first two 16,384-sector runs are adjacent, and their first,
last and next-start storage headers all reproduce the
sector-header extent-order arithmetic. Thus they are concrete
early-IPL *investigation ranges*. Their two-in-a-row layout is
consistent with the documented **two reserved areas**, but
there is no data-structure evidence assigning those physical
ranges to HMC, LIC, the SMVT, or anything else in V2R3.

An independent read-only 512-byte payload-occupancy census
illustrates why these ranges cannot simply be labeled checkpoint
pages. Counts are classified by **number of nonzero payload bytes**
(without interpreting or exporting their contents):

| Candidate physical run | Zero-byte payloads | 1–32 nonzero bytes | 33–400 nonzero bytes | 401–512 nonzero bytes |
| --- | ---: | ---: | ---: | ---: |
| 64–16,447 (16,384 pages) | 141 | 177 | 2,884 | 13,182 |
| 16,448–32,831 (16,384 pages) | 3,002 | 27 | 3,981 | 9,374 |
| 32,832–36,927 (4,096 pages) | 0 | 10 | 644 | 3,442 |

The first two runs have substantial, densely populated payloads.
The first includes **four** literal CP037 `SMVT` occurrences,
**two** `STATIC DIRECTORY` phrases, and **two**
`CHECKPOINT` phrases; local context of the latter includes
linked/debug strings such as `#LDCKPCT` and a list of
storage-management **lock names**. These are not the contents
or address of a checkpoint. Treat density and literal text as
bounded triage evidence only; neither can distinguish code,
initialized tables and historical/unreferenced material.
`bootstrap-extents IMAGE --occupancy` reproduces the four
aggregate counts in each reported physical run. It never
emits recovered payload bytes.

**Important diagnostic boundary:** the third 4,096-page
candidate has a different stored 5-byte header prefix on its
first versus last page, despite the next physical sector
independently showing another extent-order header. The
header difference may be due to special first/second-page
encoding. `bootstrap-extents` **stops at the first prefix
disagreement** rather than trusting a contiguity inference
across an unvalidated boundary; it does *not* call that
extent corrupt, invalid, or free.

On Pete's **B10 non-load-source** image the same
descriptor-backed physical origin at LBA **2,112** has a
single extent-order-15 header (a 32,768-page candidate),
but its computed last page, LBA **34,879**, has a **zero
header**. The next sector, LBA 34,880, has another
extent-order-15 header. No analogous preassigned two-extent
conclusion is justified there: free-space delimiters and
unallocated sectors on a partial non-load-source image have
different survival properties.

**Reproduce:** `as400-dasd bootstrap-extents IMAGE --limit 8`.
The diagnostic independently validates LBA-32 descriptor
geometry and origin predecessor before following candidate
extent sizes. It reports first/end/next raw header prefixes
and stops on disagreement. It is intentionally conservative,
does not stream image payloads, and does not read/write
recovered source. Synthetic tests cover two continuous
extents, mismatch stopping, descriptor validation and
read-only behavior.

**Next evidence gate:** find a **real pointer into a persisted
SMVT checkpoint** or identify a static-directory table
that can be independently verified against multiple observed
extents. Two physically adjacent reserved-size allocations
alone cannot establish a checkpoint or a permanent-directory
root. If period CISC loader documentation and these bounded
tests cannot provide a pointer chain, the project should
pause speculative ASDE parsing and advance the next
bounded backlog item (eight compressed QDDSI key families).

## Checkpoint pointer gate (2026-10-09) — research paused

A focused, read-only follow-up compared the small populated physical
pre-relative-record-zero records on Mark and Pete with the **independently
verified physical extent-start LBAs**. Tested 4-byte and 6-byte
big-endian representations of established starts in the recorded
bootstrap payloads, with no change to either image.

On Mark's low-level payloads, the exact matches for known starts
were only the already-understood **physical origin 64**, including
LBA-32 descriptor +0x00 and its already discussed +0x0C word.
One additional raw occurrence of the value 64 exists in the small
LBA-0 bootstrap payload at byte offset +0x07 in four-byte matching;
the surrounding unknown bytes do not identify this as a checkpoint
pointer. Pete's physical LBA-32 descriptor repeats its verified
**origin 2,112**, with no other exact verified extent starts detected
in these low-level records. Searching only those records cannot rule
out a translated or indirect pointer elsewhere in managed storage.

**Source boundary:** IBM's *AS/400 Disk Storage Topics and Tools*,
SG24-5693, appendix B, p.194, calls the **static directory** persistent
VLIC storage containing locations of the permanent directory; it
does **not** supply the checkpoint's physical LBA or a binary
record layout. The System/38 chapter-7 shutdown passage proves only
the System/38 write/checkpoint mechanism, **not** where OS/400 V2R3
stores its SMVT.

**Decision:** No checkpoint, initialized SMVT data table, or
permanent-directory root can currently be established from these
observations. Rather than turn these raw coincidences into field
definitions, **pause speculative ASDE decoding** and continue the
separate, bounded eight-variant QDDSI compressed-key research.
Resume storage-directory work if an independently corroborated CISC
loader/startup data reference or checkpoint page becomes available.
Keep this PR draft and preserve its tested diagnostics.

## Bounded post-QDDSI revisit (2026-10-09) — return to MI program research

PR #13, merged into `main` as commit `8300908`, adds validated
QDDSI compact/long-key evidence, source-record correlation and bounded
diagnostics. Reviewing those findings against the previously recorded ASDE
evidence gives **no new, independently verified checkpoint or directory-root
locator**. This is a *review of already captured evidence*, not a new
real-image search and not proof that a directory cannot be recovered.

**Transferable only after a root is independently identified:** the
machine-index root/node/common-text/page-pointer traversal, virtual-segment
mapping, per-entry evidence preservation and independent cross-validation
approach. QDDSI's object-local active-root pointer at +0x13A is **not** an
established SMVT/global static-directory pointer; QDDSI key materialization,
raw DKYT scalars and the unexplained `3FFF` pattern likewise do not
locate storage-management metadata.

The previous gates stand:
- No surviving physical SMVT checkpoint, static-directory table or
  permanent-directory machine-index root has been independently identified.
- Neither an exact VMC module-name reference nor an extent boundary identifies
  checkpoint contents.
- The original B10 image is non-load-source; the Mark V2R3 load-source
  image remains the more promising future bootstrap reference.
- PR #10's experimental branch is kept **draft and unmerged**. After other
  changes to `main`, GitHub currently does not report it cleanly mergeable.
  Do not resolve that by force-merging an evidence-incomplete decoder.

**Decision:** stop this review here and prioritize MI `*PGM` object-template
identification on a new, independent branch from current `main`.
Revisit PR #10 only when recovered program/loader material or an independently
verified bootstrap data reference supplies a *specific physical or virtual
candidate* to test. No speculative scan or ASDE decoder was added.

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
