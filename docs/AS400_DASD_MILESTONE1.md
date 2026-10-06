# CISC AS/400 DASD Explorer — Milestone 1

## Scope

This milestone adds a read-only command-line structure explorer for raw CISC
AS/400 DASD images.

The original target was the surviving IBM AS/400 9404 B10 disk image. We now
also have an independent single-disk V2R3 image from Mark/Patrik. The second
image is especially important because it lets us distinguish architecture-level
CISC AS/400 behavior from patterns that could have been peculiar to one B10
disk.

The guiding rule remains: documented facts, independently reproduced behavior,
and unresolved hypotheses are kept separate.

## Confirmed physical model

Both images use the CISC 520-byte DASD format:

```text
520-byte physical DASD sector
    8-byte storage-management header
  512-byte CISC storage page
```

The two images currently used for validation are:

```text
Surviving B10 D1 image
  616,392 sectors
  320,523,840 bytes

Mark/Patrik single-disk V2R3 image
  1,931,265 sectors
  1,004,257,800 bytes
```

The parser rejects input whose size is not an exact multiple of 520 bytes.

## Why the scanner starts with sector headers

IBM System/38 storage-management documentation describes auxiliary-storage pages
as self-defining. If the storage directories are invalid, recovery scans every
DASD header.

The documented recovery algorithm:

1. reads from relative record zero to the end of auxiliary storage;
2. recognizes permanent extent candidates when the virtual address is permanent
   and the relative record number is aligned to the power-of-two extent size;
3. recognizes large free extents from a preassigned virtual-address delimiter;
4. bypasses the remaining headers in a recognized extent;
5. combines zeroed, temporary, stale, and misaligned headers into reclaimable
   free space;
6. performs a second pass over permanent candidates to reconstruct segments.

That is now the model used by `as400-dasd`.

## Sector-header interpretation

The System/38 VMC manual describes the eight bytes as:

```text
5 bytes   virtual page address
1 byte    indicators
1 byte    reserved
1 byte    pointer/control information
```

The two independent real images agree on the following field behavior.

### Five-byte virtual-page field

The first five bytes are the high five bytes of the 48-bit page-aligned virtual
address. The missing low byte is zero:

```text
virtual_address = int(header[0:5], big-endian) << 8
```

Because CISC pages are 512 bytes, a valid page-start address has bit 8 clear, so
the low bit of the stored five-byte field is zero for validated extent starts.

Examples from the B10 image:

```text
LBA 231488  00 A1 C3 01 00 05 00 00
             -> VA 00A1C3010000

LBA 231489  00 A1 C3 01 02 05 00 00
             -> VA 00A1C3010200
```

The second sector advances exactly one 512-byte page.

### Extent size

The low nibble of the indicators byte is the base-2 logarithm of the extent
length in pages:

```text
extent_pages = 1 << (header[5] & 0x0f)
```

Observed real-image sizes range from 1 page through 32,768 pages.

### Reserved byte

Header byte 6 is zero in every sector header examined in both full images.

### Pointer/control byte

The final byte is preserved and displayed. IBM describes pointer-location
information here, including a five-bit field C, but the complete bit semantics
are not yet decoded by this project.

## Inferring relative record zero

IBM's recovery rules use a device-relative record number rather than the raw
image LBA.

Both real images contain the same order-15 preassigned large-free-space
delimiter:

```text
00 00 FC 00 00 0F 00 00
```

Its extent length is 32,768 pages. Therefore:

```text
relative_record_zero = delimiter_LBA mod 32768
```

This independently produces:

```text
B10 surviving disk:           relative record zero = LBA 2,112
Mark/Patrik V2R3 disk:        relative record zero = LBA 64
```

Large permanent extents independently align to the same inferred origins,
providing additional validation.

## B10 surviving disk results

For `HD60_520_D1_IMAGE_PASS2.hda`:

```text
sectors:                    616,392
relative record zero:         2,112

explicit large-free:
  7 extents
  229,376 pages

permanent extent candidates:
  27,730 extents
  356,904 pages

reclaimable by directory recovery:
  427 regions
  28,000 pages

structured permanent + explicit-free coverage:
  586,280 / 614,280 managed pages
  95.4%
```

The first permanent candidates are:

```text
LBA 231488   32 pages   VA 00A1C3010000
LBA 231520   16 pages   VA 00A1C3014000
LBA 231536    8 pages   VA 00A1C3016000
LBA 231544    2 pages   VA 00A1C3017000
LBA 231546    1 page    VA 00A1C3017400
```

The known load-source shadow-log address `000083000000` is not present on this
disk, consistent with the surviving disk not being the load source.

## Independent Mark/Patrik V2R3 image results

The uploaded `HD60_imaged.hda` is exactly 1,931,265 x 520-byte sectors.

The payload contains EBCDIC strings including:

```text
SMSP02
V2R3M0
QSYS
QGPL
LICENSED INTERNAL CODE - PROPERTY OF IBM
```

The image therefore independently contains a complete early CISC OS/400
environment. `SMSP02` corroborates the P02 provenance, although it is treated
as an image/system identifier rather than by itself as proof of the hardware
model.

The recovery scan finds:

```text
relative record zero:            LBA 64

explicit large-free:
  1 extent
  32,768 pages

permanent extent candidates:
  88,685 extents
  1,238,250 pages

reclaimable by directory recovery:
  16,173 regions
  660,183 pages

structured permanent + explicit-free coverage:
  1,271,018 / 1,931,201 managed pages
  65.8%
```

The lower structured percentage is not considered a parse failure. IBM's own
recovery procedure explicitly returns zeroed, temporary, stale, and misaligned
headers to free space. This image contains substantially more such material than
the surviving B10 disk.

The beginning of the disk provides particularly strong independent confirmation
of the extent rules:

```text
LBA     64   16,384 pages   VA 00000B000000
LBA 16,448   16,384 pages   VA 000092000000
LBA 32,832    4,096 pages   VA 000092800000
LBA 36,928    2,048 pages   VA 000092A00000
LBA 38,976    1,024 pages   VA 000053000000
LBA 40,000      512 pages   VA 000082000000
```

All are aligned to relative-record zero LBA 64 and their second-page headers
advance exactly 512 bytes.

## Load-source shadow-log validation

The 9404 Service Guide documents a 64-KB shadow error log at virtual address:

```text
0000 8300 0000
```

The independent one-disk image resolves this address exactly:

```text
VA 000083000000
  -> LBA 147,520
  -> header 00 00 83 00 00 08 00 00
  -> extent-order 8
```

The payload provides a striking additional check:

```text
LBA 147520-147647   128 pages / 64 KiB   all 128 pages contain data
LBA 147648-147775   next 128 pages        all 128 pages are zero
```

So the documented 64-KB load-source structure is visible at exactly the
documented virtual address. This is the strongest independent validation so far
of the virtual-address decoding.


## Second recovery pass: segment groups

The second IBM recovery pass is now implemented. Permanent extent candidates
are processed in virtual-address order. The first page of a plausible segment
group supplies the segment-group header and total page count; subsequent extents
must begin exactly at the next expected virtual address until the declared
segment length is satisfied.

On the two full real images the current implementation recovers:

```text
Surviving B10 D1
  recovered segment groups:  12,712
  primary/self segments:       9,330
  secondary segments:          3,382
  unrecovered candidates:      5,557

Mark/Patrik V2R3
  recovered segment groups:  43,095
  primary/self segments:      31,654
  secondary segments:         11,441
  unrecovered candidates:      1,526
```

The independent image is especially useful because most secondary segment
headers point back to a recovered primary segment on the same disk. The B10
surviving disk resolves far fewer such owner links, which is consistent with
important primary storage having lived on its missing load-source disk.

The segment-group parser currently exposes the 32-byte YYSGHDR fields needed
for recovery:

```text
16-bit segment type
16-bit segment size in pages
flag/domain fields
8-byte owning-object address
8-byte space address
```

Unknown flag meanings remain unlabeled.

## EPA object discovery and libraries

For recovered primary segments, the parser now reads the common EPA object
header immediately following YYSGHDR. It extracts the MI object type/subtype,
30-byte EBCDIC object name, context pointer, and object-space pointer.

This is enough to recover real permanent contexts/libraries and to assign many
objects to them using each object's EPA context back-pointer.

On the Mark/Patrik image the current pass recovers approximately:

```text
EPA object identities:             31,533
permanent contexts/libraries:           40
objects assigned to known context: 21,531
```

Recovered libraries include `QSYS`, `QGPL`, `QUSRSYS`, `QSYS2`,
`QSRV`, `QPFRDATA`, `QRECOVERY`, `QSYS38`, `QUSRTOOL`, `QDOC`,
`QSPL`, and others.

Examples:

```text
QSYS     VA 000233000000  LBA 76,024
QGPL     VA 000274000000  LBA 76,968
QUSRSYS  VA 000283000000  LBA 77,144
QSYS2    VA 00028C000000  LBA 77,272
```

The object-to-library relationship is not inferred from name proximity. For
example, the recovered `QCLSRC` object has MI type/subtype `19/01` and an EPA
context pointer of:

```text
0001:000274000000
```

which points exactly to the recovered QGPL context at virtual address
`000274000000`.

That means the CLI can now perform the first genuinely AS/400-like offline
directory operation:

```bash
as400-dasd libraries HD60_imaged.hda
as400-dasd ls HD60_imaged.hda QGPL
as400-dasd ls HD60_imaged.hda QGPL --type 19/01
as400-dasd objects HD60_imaged.hda --name QCLSRC
```

Representative QGPL `19/01` objects recovered from the real image include
`QCLSRC`, `QCMDSRC`, `QDDSSRC`, `QDKTSRC`, `QFMTSRC`, `QFTNSRC`,
and other files.

The B10 surviving image also produces real EPA objects and permanent contexts.
Examples include the program-like `QOOADGPM` object (MI `02/01`) and library
contexts such as `QRPG`, `QSDE`, `JHUDGINS`, `MSICKBERT`,
`PPSIPROTO`, and `PPSITEST`. Major system contexts such as QSYS/QGPL are
not expected to be complete on that surviving non-load-source disk.

A provenance note for the B10 image is especially interesting: the recovered
`JHUDGINS` library likely corresponds to **John Hudgins**, the father of the
friend from whom the physical AS/400 collection came. The family ran a
consulting/programming business in the 1980s and 1990s and reportedly used this
AS/400 for software development. That makes `JHUDGINS` a plausible original
user/application library rather than an IBM-supplied system context. This is
provenance supplied by the collection owner and is kept separate from the
on-disk structural evidence.


## Source-member contents: working

The browser can now go beyond file/member metadata and recover the contents of
standard AS/400 source physical-file members.

IBM documents data-space entries as a one-byte status followed by the entry
fields, with the third and subsequent data-space segment groups forming one
logical entry stream with the 32-byte segment-group headers omitted. The real
source members examined here use the standard 92-byte source record payload:

```text
1 byte    data-space entry status
6 bytes   source sequence
6 bytes   source date
80 bytes  source text
--------------------------------
93 bytes  on-disk data-space entry
```

The parser reconstructs the recovered QDDS data segment groups in virtual
address order, removes each segment-group header, verifies the default source
entry, and decodes valid 93-byte entries.

The `files` command also unions recovered `*FILE` objects with file names
inferred from surviving member cursors. This matters on the B10 because a file's
primary object can reside on the missing load-source disk while member cursors
and even complete member data survive on the remaining disk; those entries are
reported as `member-only` rather than omitted.

New CLI commands:

```bash
as400-dasd files   disk.hda QGPL
as400-dasd members disk.hda QGPL QCLSRC
as400-dasd source  disk.hda QGPL QCLSRC REFRESH2
as400-dasd cat     disk.hda QGPL QCLSRC REFRESH2
```

`source` shows sequence/date plus the source text. `cat` emits only the
80-byte source-text field, which is convenient for saving recovered source to a
normal text file.

This was validated directly against both uploaded real images.

### Mark/Patrik V2R3 image

`QGPL/QCLSRC(REFRESH2)` resolves through:

```text
0D50 member cursor
  -> 0B90 QDDS data space
  -> recovered 03B4 data segment group(s)
  -> 93-byte source entries
```

The parser recovers 71 source lines from the member. The first data-space entry
is the documented default entry and is omitted from normal source output.

Additional real source members tested successfully include:

```text
QGPL/QRPGSRC(PROOF)
QGPL/QDDSSRC(QDSIGNON)
QGPL/QCBLSRC(VERIFY)
```

The same 93-byte entry model produces readable RPG, DDS, and COBOL source.

### Surviving B10 disk

Most importantly for preservation, the surviving B10 disk contains at least one
complete user source member that can now be recovered:

```text
PPSITEST/QLBLSRC(PROTO)
  107 source lines recovered
```

The source identifies its author as `JT HUDGINS` and declares the target
computer as `IBM-AS400`. This strongly supports the collection provenance that
the system was used by the Hudgins consulting/programming business. The source
itself is **not** committed to this public repository; only the parser and
synthetic regression coverage are stored here.

Some other B10 source-member data segments are only partially present on the
surviving disk, which is consistent with single-level storage having scattered
parts across the missing load-source disk. The parser reports those as
incomplete rather than fabricating records.

## Generic physical-file records and record formats

The browser can now recover fixed-length data-space records from non-source
physical-file members as well as source members.

The QDDS primary segment contains scalar values used by the data-space access
path. Across both real CISC images, the following fields have been reproduced:

```text
+0x11A  4 bytes  user-entry count
+0x11E  4 bytes  force count
+0x13C  4 bytes  fixed data-space entry length
```

The ordinal-zero default entry is in addition to the user-entry count. For the
normal fixed-length members examined so far, each entry is one status byte
followed by the record payload, so:

```text
record_length = entry_length - 1
```

The independent V2R3 image also contains duplicate/later length scalars near
+0x1E4/+0x1EC. They corroborate ordinary fixed records but are absent on the
older B10 and disagree for a handful of special system data spaces, so the
cross-version +0x13C field is used as the authoritative boundary.

Real examples:

```text
QGPL/QCLSRC(REFRESH2)          71 records   92-byte payload / 93-byte entry
QGPL/PTFSUM(PTFSUM)          1941 records   80-byte payload / 81-byte entry
DBUUSERS(DBUUSERS)              1 record     22-byte payload / 23-byte entry
PDPICKORG(PDPICKDEMO)         1880 records  452-byte payload / 453-byte entry
B10 QLBLSRC(PROTO)             107 records   92-byte payload / 93-byte entry
```

New commands expose these records even before their field schema is known:

```bash
as400-dasd records disk.hda QGPL PTFSUM PTFSUM
as400-dasd record  disk.hda QGPL PTFSUM PTFSUM 1
```

The raw view preserves the entry status byte, RRN, EBCDIC preview, and hex.

This has also been exercised against ordinary non-source data on the complete
Mark/Patrik image. `PDPICKORG(PDPICKDEMO)` has 1,880 user entries, a
452-byte payload, and a recovered `PD00RC` format with 95 fields. Its first
records decode meaningful business/application values such as company `01`,
division `01`, control `1001`, style `04402`, and color `CA`.
`DBUUSERS(DBUUSERS)` has a 22-byte payload whose `GURUSERS` format
recovers fields such as `USRNAM`, authorization flags, and a packed numeric
field; the surviving row identifies `*PUBLIC`. These checks use the real disk
at development time, but the record payloads are not committed to the public
repository.

### MI 19/51 record-format objects

The database record-format object has now been identified in the real images as
MI type/subtype `19/51`. Its EPA name is the record-format name.

The repeated field descriptions contain a stable prefix that exposes:

- field name and reference name;
- field type;
- record offset;
- storage length;
- digit count;
- decimal positions.

Observed and independently verified type codes include:

```text
00  binary integer
02  zoned decimal
03  packed decimal
04  character
```

The binary case is independently corroborated by IBM's documented System/38
key-conversion rules, which treat binary fields as signed two's-complement
values.

For the standard QCLSRC record format this reconstructs:

```text
SRCSEQ   ZONED  offset  0  length  6  digits 6  decimals 2
SRCDAT   ZONED  offset  6  length  6  digits 6  decimals 0
SRCDTA   CHAR   offset 12  length 80
```

A larger Mark/Patrik format, `PD00RC`, additionally validates packed-decimal
fields such as a 7-digit value stored in four packed bytes.

The CLI therefore supports:

```bash
as400-dasd fields  disk.hda QGPL PDPICKORG
as400-dasd records disk.hda QGPL PDPICKORG PDPICKDEMO --decoded
as400-dasd record  disk.hda QGPL PDPICKORG PDPICKDEMO 1 --decoded
```

Automatic format selection searches the recovered *FILE FCB for names of
surviving 19/51 format objects. `--format NAME` can be used when the FCB is
missing/ambiguous but the format object survives.

### First structured user-database decode from the surviving B10

The surviving B10 contains a `STAREC` 19/51 format object and the
`STASTAT(STASTAT)` QDDS/member data even though its original library context
and *FILE primary object do not appear to survive on this disk.

The recovered 128-byte format contains:

```text
RECTYP  CHAR    off   0 len  3
FILL1   CHAR    off   3 len  5
STCOD   CHAR    off   8 len  1
STNAME  CHAR    off   9 len 40
MTD     ZONED   off  49 len  5
YTD     ZONED   off  54 len  6
LYR     ZONED   off  60 len  6
FILL2   CHAR    off  66 len 61
ACTCOD  CHAR    off 127 len  1
```

The three surviving records decode as:

```text
RRN 1  STCOD=1  STNAME=MISSOURI
       MTD=0  YTD=3896  LYR=3996

RRN 2  STCOD=2  STNAME=KANSAS
       MTD=0  YTD=190   LYR=188

RRN 3  STCOD=3  STNAME=STATES OTHER THAN MISSOURI OR KANSAS
       MTD=0  YTD=26    LYR=20
```

This is the first demonstrated structured decode of a non-source user database
from the raw surviving B10 disk.

For incomplete disk sets, member-oriented commands accept `*` as the library
name so orphaned member cursors can still be addressed:

```bash
as400-dasd records disk.hda '*' STASTAT STASTAT --decoded --format STAREC
```

## Context machine-index decoding: groundwork

IBM's machine indexes are binary radix trees. The VMC documentation describes
release-2 indexes as using three-byte elements, and IBM patent US4774657
Appendix A publishes the three element formats: text elements, decision nodes,
and page pointers.

The core now decodes those documented three-byte primitives. A forensic command
can apply the decoder to a recovered library context while we determine the
remaining index-page header and trunk layout:

```bash
as400-dasd context-page HD60_imaged.hda QGPL 4
as400-dasd context-page HD60_imaged.hda QGPL 4 --offset 0x0 --count 48
as400-dasd context-page HD60_imaged.hda QGPL 0 --page-size 4096
```

This is intentionally not yet presented as a complete context-index traversal.
IBM permits logical index pages from 512 through 32768 bytes. The next work is
to locate the index page header/trunk inside the context object, follow page
pointers, and reconstruct front-end-compressed keys.

One practical finding is already important: QGPL's recovered segment is
multi-extent and physically scattered. Context-index parsing must therefore use
the recovered segment in virtual-address order, not assume physical
contiguity. The parser's `read_segment_bytes()` path now provides that view.

## Database member cursors and member metadata

The next database layer is now partially decoded.

IBM documents MI type/subtype `0D50` as a permanent database-file member
cursor. The 30-byte MI object name is laid out as:

```text
bytes  0- 9   file name
bytes 10-19   member name
bytes 20-29   blanks
```

The CLI therefore supports:

```bash
as400-dasd members disk.hda QGPL
as400-dasd members disk.hda QGPL QCLSRC
as400-dasd members disk.hda QGPL QCLSRC --long
```

The permanent cursor's YYSGHDR `SPACE` address identifies its associated-space
offset within the recovered segment. IBM's documented cursor layout places a
four-byte offset at associated-space +4; adding that value locates the member
header. The member header begins with five system pointers followed by fields
including descriptive text, source type, source-change time, and creation time.

This has been verified against the real Mark/Patrik image. For
`QGPL/QCLSRC(REFRESH2)`:

```text
MI object:              0D/50
virtual address:        00F3C2000000
physical LBA:           1,668,664
segment pages:          5
associated-space:       +0x440
member-header offset:   +0x8D0
source type:            CLP
source changed:         1998-01-03 02:31:14
created:                1998-01-03 02:31:11
text:                   Refresh PkMS demo data - new version (GE 170)
```

The same decoder successfully extracts member-header metadata from 3,682 of the
3,779 recovered `0D50` cursor objects on that image in an exploratory full-disk
probe. Other real examples include `QRPGSRC(PROOF)`,
`QRPGSRC(PROOF38)`, and `QDDSSRC(QDSIGNON)`.

This moves the disk browser beyond merely identifying `*FILE` objects: it can
now enumerate many file members and recover their source-member metadata.

### Important limitation

Library membership is currently reconstructed from the EPA **object -> context**
back-pointer. We have not yet parsed the context's machine-index entries in the
opposite direction. Parsing that index will provide an excellent independent
cross-check and should identify objects whose context relationship is currently
unresolved.

## Meaning of "reclaimable"

The CLI deliberately uses the phrase `reclaimable-by-recovery`, not simply
`free`.

IBM documents that directory recovery returns all of these to the free-space
directory:

- zeroed headers;
- temporary headers;
- permanent headers found on the wrong power-of-two boundary;
- other headers not accepted as permanent extent candidates.

Therefore the recovery map describes what the recovery algorithm can reconstruct
from headers alone. It does not claim every reclaimable sector was unused at the
moment the image was captured.

## Current commands

### Geometry

```bash
as400-dasd info disk.hda
```

### High-level recovery map

```bash
as400-dasd map disk.hda
as400-dasd map disk.hda --top 25
```

### Physical extent/reclaimable regions

```bash
as400-dasd regions disk.hda
as400-dasd regions disk.hda --no-reclaimable
```

### Recovered segment groups

```bash
as400-dasd segments disk.hda
as400-dasd segments disk.hda --primary-only
```

### Recovered libraries, files, and objects

```bash
as400-dasd libraries disk.hda
as400-dasd files disk.hda QGPL
as400-dasd objects disk.hda
as400-dasd ls disk.hda QGPL
as400-dasd ls disk.hda QGPL --type 19/01
```

### Source member contents

```bash
as400-dasd members disk.hda QGPL QCLSRC
as400-dasd source disk.hda QGPL QCLSRC REFRESH2
as400-dasd cat disk.hda QGPL QCLSRC REFRESH2
```

### One-sector inspection

```bash
as400-dasd sector disk.hda 147520
```

Shows the raw header, decoded virtual address, extent size, indicator fields,
EBCDIC payload preview, and hex.

### Repeatable report

```bash
as400-dasd scan disk.hda --report disk-dasd-report.txt
```

All DASD commands are read-only.

## Regression fixtures and CI

No full user disk image is stored in the repository.

CI uses compact sanitized metadata fixtures. The extent fixtures contain only
selected real eight-byte sector headers and their original LBA positions. A
second small fixture contains only 128 bytes of selected first-page metadata
(YYSGHDR plus the beginning of the EPA header) for QSYS, QGPL, QCLSRC, and a
B10 program object. No database/member record payloads are included.

### B10 fixture

The B10 fixture verifies:

- relative record zero at LBA 2,112;
- seven order-15 free-space delimiters;
- the first real permanent extent boundaries;
- the virtual-address and extent-size decoding;
- the reserved-byte behavior.

### Independent P02/V2R3 fixture

The second fixture verifies:

- relative record zero at LBA 64;
- the same preassigned free-space delimiter;
- independent 16,384-, 4,096-, 2,048-, 1,024-, 512-, 256-, and 128-page
  real extents;
- the documented virtual address `000083000000`;
- its physical mapping to LBA 147,520.

GitHub Actions runs the complete tape + DASD test suite on pushes and pull
requests.

```bash
python3 -m unittest discover -s tests -v
```

## Next layer

The project has now crossed from a DASD recovery map into offline AS/400 object
browsing: segment groups, EPA object names, permanent contexts/libraries, and
object-to-library back-pointers are working on the real images.

The next research/implementation targets are:

- finish traversal of the permanent-context binary-radix machine index and
  cross-check its context -> object entries against the EPA object -> context
  back-pointers;
- identify the static/permanent directory objects and parse their ASDE/extent
  descriptors directly;
- improve permanent/temporary indicator decoding so fewer candidates require
  structural corroboration;
- decode additional MI 19/51 field types beyond the currently verified
  character/zoned/packed cases;
- refine FCB -> format resolution for logical and multiple-format files;
- decode data-space entry-status semantics (active/deleted/other states);
- follow QDDSI/keyed indexes so records can also be presented in keyed order;
- integrate these read-only structures into the GTK/TUI browser after the CLI
  model is stable.

The immediate next milestone is now **broader typed database decoding and
keyed/indexed-file support**, while context-index traversal continues as an
independent directory cross-check.

## Safety

All DASD operations remain read-only. The code contains no path that opens a
DASD image for writing.


## Interactive text-mode DASD browser

A curses browser now sits directly on top of the read-only DASD backend. It
follows the same terminal-oriented design philosophy as `tape-tool browse`
and adds no third-party Python dependency.

Run it with an image:

```bash
as400-dasd browse petes.hda
```

or with no image to start in a file picker:

```bash
as400-dasd browse
```

The upper half of the screen contains three navigation panes:

```text
Libraries / views  ->  Files / MI types  ->  Members / objects
```

The lower half is a full-width content/details viewer.

Library mode includes both recovered *FILE objects and member-only files, which
is important for the surviving B10 where scatter loading left member cursors on
the surviving disk while the *FILE primary object may have lived on the missing
load-source disk.

Two special top-level views are always available:

- `<ALL OBJECTS>` groups every recovered EPA object by MI type/subtype.
- `<ORPHANS / MEMBER-ONLY>` exposes recoverable material whose library context
  was not recovered.

Selecting a member automatically tries the richest safe interpretation in this
order:

1. standard source-member decoding;
2. generic QDDS record recovery;
3. decoded MI 19/51 fields when an applicable record format is recovered;
4. raw EBCDIC record previews when field metadata is unavailable.

Selecting an MI 19/51 format object displays its recovered field definitions.
Selecting an ordinary object displays its MI identity, virtual address, physical
LBA, segment type/owner, and EPA context.

The browser also supports a global name search with `/`, opening a different
image with `o`, and rescanning the current image with `r`. All operations
remain read-only.



## Additional DLO recovery targets

- Reconstruct the QDLS document/folder hierarchy from QDOC `*DOC`/`*FLR`
  objects plus the QUSRSYS `QAO*` DLO index metadata, so internal object names
  can be presented as user-facing folder/document paths.
- Identify the payload-storage objects associated with binary DLOs and support
  safe export of the original workstation-file bytes.
