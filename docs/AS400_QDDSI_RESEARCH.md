# AS/400 QDDSI / keyed-file research

This note records the current evidence for CISC database member storage and the
MI `0C/90` QDDSI objects. The working model is deliberately split into
documented System/38 architecture, observations from the two real images, and
items that still need byte-level validation.

## Goal

Move from arrival/RRN browsing toward a read-only view of access-path/keyed
order while preserving the distinction between:

- the `0B/90` QDDS data space that owns physical member entries;
- the `0C/90` QDDSI data-space index/access path;
- the `0D/50` permanent member cursor;
- the `19/51` record-format object.

The first milestone is now stronger than the original plan: direct cursor
pointers identify QDDS/QDDSI, QDDSI key specifications can be correlated with
recovered record formats, and simple machine-index keys can be tied back to
QDDS ordinals.

## Strong IBM documentation

IBM's *System/38 Vertical Microcode Logic Overviews and Component Descriptions*,
SY21-0889-5, Database Management section, documents the structures that match
the recovered CISC objects.

### Data space

A data space has three or more segment groups:

1. the first contains YYSGHDR/EPA/object-specific header and data-segment
   pointers;
2. the second contains YYSGHDR, the **field table**, and associated space;
3. the third and subsequent groups contain status bytes and data-space entries.

IBM also states that the data segment groups form one logical contiguous entry
address space after the 32-byte segment-group headers are excluded.

This gives the recovered `02A4` second segment groups a documented role rather
than merely an observed one.

### Data space index

A data space index contains an object-specific header, key specifications,
selection specifications, and a general **machine index**. IBM Figure 2-5
places that machine index on a 2-KB boundary and shows base, root, and secondary
pages.

The key specification area begins with a DKEY row for each data space covered
by the index. Each DKEY row identifies the data space and points to a DKYT.
The DKYT has one row per key field and describes field position/location,
length/fork information, and ordering attributes. DKYT row order is the
composite-key field order.

IBM further documents that the machine-index key is the user key plus a
machine-supplied database-relative-address suffix containing the adjusted data
space number, ordinal, and internal flags. The first user entry has ordinal 1.
This suffix makes otherwise duplicate user keys unique and lets the index locate
the data-space entry.

## Direct member-cursor pointers

The earlier resolver began with a same-30-byte-name correlation. Both real
images show a much stronger relationship:

- member cursor `+0x128` -> QDDSI internal address when an index is present;
- member cursor `+0x300` -> QDDS internal address.

On the independent single-disk V2R3 image, all 3,779 sampled/recovered member
cursors resolve their non-null `+0x300` QDDS pointer, and all 284 non-null
`+0x128` QDDSI pointers resolve.

The surviving B10 disk is especially useful because a direct pointer can remain
even when the pointed-to primary segment is on the missing companion disk. The
resolver now retains that expected address and uses it to collect surviving
secondary segments instead of reducing the result to "QDDS not recovered."

## PPSITEST FUNDDEF and ACCTDEF reclassification

The original hypothesis was:

`QDDSI present + QDDS absent -> perhaps logical/access-path-only member`.

The real-image evidence now disproves that shortcut for these two members.

### FUNDDEF

- member cursor: `00ED:0014FD000000`
- direct QDDSI pointer: `00ED:0014EC000000` (16-page primary recovered)
- direct QDDS pointer: `00ED:00093A000000` (primary not on this disk)
- surviving `02A4` secondary segment owner:
  `00ED:00093A000000`

The recovered `02A4` field table describes two fields and matches the
recovered `FUNDREC` 19/51 format:

- packed FUNDNO at record position 1, two digits / two storage bytes;
- character FUNDDESC at record position 3, length 40.

PDM also identifies FUNDDEF as `PF-DTA`.

### ACCTDEF

- member cursor: `00ED:001BBA000000`
- direct QDDSI pointer: `00ED:001BA7000000`
- direct QDDS pointer: `00ED:001B8D000000` (primary not on this disk)
- surviving `02A4` secondary segment owner:
  `00ED:001B8D000000`

Its field table independently matches recovered format `ACCTREC`:

- FUNDNO packed, record position 1;
- ACCTNO packed, record position 3;
- SUBNO packed, record position 6;
- ACCTDEF character, record position 8, length 40.

Neither missing QDDS has a recovered `03B4` entry-data segment on Pete's disk.
That is consistent with AS/400 scatter loading: cursor/index/schema pieces can
survive on one disk while the QDDS primary and record-bearing segment groups
were on the lost disk.

The QDDSSRC members for FUNDDEF and ACCTDEF have recoverable QDDS primary
metadata but their source-record data segments are also absent on the surviving
disk, so the DDS source cannot currently be read from Pete's image.

## QDDSI key-specification observations

For the ordinary indexes examined so far, the primary segment points to a DKEY
area at segment-relative `0x400`. The DKEY area in turn points to a DKYT that
starts at `0x440` in the small examples.

Do not promote every byte offset here to an architecture-wide constant yet;
the important point is that the values line up with IBM's documented logical
DKEY/DKYT fields.

Examples:

### FUNDDEF QDDSI

At `+0x400` the DKEY data identifies QDDS
`00ED:00093A000000`. The key description reports one key field, two user-key
bytes, and six bytes in the stored composite key. That is exactly
`FUNDNO` (two-byte packed) plus the four-byte database-relative-address
suffix.

The single DKYT row has length 2 and record location 1, matching FUNDNO.

### ACCTDEF QDDSI

The DKEY data identifies QDDS `00ED:001B8D000000`, with three key fields,
seven user-key bytes, and an eleven-byte stored composite key. Seven bytes is
exactly:

- FUNDNO: 2
- ACCTNO: 3
- SUBNO: 2

The three DKYT rows point to record positions 1, 3, and 6 with lengths 2, 3,
and 2, matching the recovered ACCTREC format and preserving the composite-key
order.

### Independent V2R3 cross-check

A real DBUUSERS example has one 10-byte character key field. Its DKYT row has
length 10 and record position 1, and its machine-index root contains the
contiguous key:

`EBCDIC("*PUBLIC   ") + 00 00 00 01`

The four-byte suffix therefore resolves directly to user ordinal 1, exactly as
the IBM description predicts.

Other V2R3 examples with multiple recovered QDDS records show the same pattern:
known user-key bytes are followed by a four-byte suffix whose ordinal matches
the corresponding recovered QDDS RRN. Some complete keys are not contiguous,
which is expected because the release-2 binary-radix machine index can move
common leading text into common-text nodes.

## Broad V2R3 traversal validation

A fresh pass over Mark's recovered V2R3 image finds 281 recovered primary
`0C/90` QDDSI segment groups whose DKEY/DKYT metadata parses conservatively.
Of those, 171 currently report zero keys and 110 contain populated DKEY rows.

The active machine-index root is not fixed at segment offset `0x1000`.
Across all 110 populated indexes, an observed six-byte QDDSI pointer at
`+0x13A` identifies a machine-index control area, and a six-byte pointer at
control-area `+0x20` identifies the active root page. The resulting root
offsets are:

- `+0x1000`: 102 indexes;
- `+0x1800`: 7 indexes;
- `+0x2800`: 1 index.

These pointer offsets are real-image observations, not yet promoted to IBM
field names. Following them removes the earlier false "special root" category.

The database-relative address also resolves the multi-DKEY ambiguity. IBM
documents that it contains an adjusted data-space number and encoded ordinal.
In every ordinary V2R3 tree that can currently be reconstructed, the four-byte
suffix has this observed form:

`DKEY-row byte | three-byte ordinal`

The first byte equals the zero-based DKEY row number, and the final three bytes
resolve to the corresponding QDDS ordinal. This lets one machine index contain
different DKEY key lengths without forcing a global key shape.

IBM also documents fork-character rows when an index covers data spaces with
different key lengths. The mixed-key QASULE examples reproduce that structure:
zero-length/zero-location non-field DKYT rows account for the extra ordering
bytes interleaved among the field bytes. Consuming those ordering bytes while
concatenating only real field rows reconstructs the user-key bytes for
QASULE01, QASULE02, QASULE03, QASULE05, and QASULE06.

With dynamic root resolution and DKEY-specific key shapes, 102 of the 110
populated QDDSIs traverse completely. Those 102 indexes contain 128,191
machine-index entries. For every one of those entries:

- the four-byte suffix selects a populated DKEY row whose machine-key length
  matches the recovered key;
- the final three bytes form an ordinal within the recovered QDDS range for
  that DKEY data space;
- the number of entries attributed to each DKEY equals that row's reported
  key count.

The final eight populated indexes form a narrow long/compact-key family:

- `QAOKLAKA`
- `QAOKLDKA`
- `QAOKL10A`
- `QAOKS01A`
- `QAOKS02A`
- `QAOKS03A`
- `QAOKS04A`
- `QAOKS05A`

Their terminal paths are shorter than the DKEY machine-key lengths, so the
full user-key bytes are not reconstructed. That is no longer treated as a
failed traversal. IBM's machine-index description permits compressed/common
text and documents a maximum machine-index entry length of 128 bytes, while
some of these DKEY layouts report larger machine-key lengths. The conservative
decoder therefore preserves only the tree text actually present and the
ordinary four-byte database reference; it does not pad or invent omitted key
bytes. Repeated `3FFF`-like values remain raw evidence with no assigned
meaning.

Across these eight indexes the tree yields 156 terminal database references.
Every reference selects a valid populated DKEY row and resolves to one of the
13 recovered QDDS ordinals for the shared `QAOKP09A` data space. Including
the 128,191 complete-key entries from the other 102 populated indexes, all 110
populated recovered V2R3 QDDSIs now enumerate **128,347 keyed terminal
references** in tree order.

This completes the functional QDDSI/keyed-record milestone: ordinary and
multi-DKEY access paths can be enumerated in keyed order, and the browser can
resolve their database references to QDDS RRNs without pretending that every
compressed index exposes the full literal user key. Recovering the omitted
user-key bytes for the eight long/compact variants remains a useful research
follow-up rather than a prerequisite for keyed navigation.

## The eight QAOK variants: independently corroborated DKYT length accounting

A targeted **read-only real-image pass** on Mark's V2R3 load-source disk
read only the recovered QDDSI `0C/90` primary-segment key-specification
tables for the eight unresolved long/compact indexes. The exact object
name, `0C/90` EPA type, primary sector header, DKEY row, and DKYT
pointer were verified before comparing these numbers. No live keys or
database rows are committed here.

For **each populated DKEY row** there is an exact and previously
unrecognized length identity:

`DKEY user_key_length = sum(positive DKYT length_or_fork values)
                         + 2 * count(positive-length DKYT rows with
                                     raw sequence_attributes == 0x01)`

The two extra bytes per `0x01`-sequence row are an **observed
arithmetic relationship** only: we have *not* established whether
these bytes are delimiters, field-length prefixes, ordering controls,
or part of another representation. The zero-length `0x40`-sequence
rows remain zero-length fork/control candidates and do not affect the
field-length sum.

| QDDSI index | Populated DKEY row(s) | Terminal references | Raw positive field lengths | Raw `seq=01` field count | Field-byte sum | User / machine key lengths |
| --- | --- | ---: | --- | ---: | ---: | --- |
| `QAOKLAKA` | 0 | 13 | 47 | 1 | 47 | 49 / 76 |
| `QAOKLDKA` | 0 | 13 | 18, 64 | 1 | 82 | 84 / 132 |
| `QAOKL10A` | 1 | 13 | 10, 64 | 1 | 74 | 76 / 120 |
| `QAOKS01A` | 0 | 13 | 64 | 1 | 64 | 66 / 102 |
| `QAOKS02A` | 0 and 1 | 26 | 40, 64 | 2 | 104 | 108 / 164 |
| `QAOKS03A` | 0 and 1 | 26 | 10, 40, 64 | 2 | 114 | 118 / 181 |
| `QAOKS04A` | 0 and 1 | 26 | 8, 40, 64 | 2 | 112 | 116 / 178 |
| `QAOKS05A` | 0 and 1 | 26 | 8, 40, 64 | 2 | 112 | 116 / 178 |

All populated rows point to the independently recovered `QAOKP09A`
data-space internal address `0001:003D09000000`; 13 QDDS
RRNs survive there. The `QAOKLDKA` and `QAOKL10A`
also carry *zero-count* DKEY rows referencing the separate
`QAOKP05A` data space. The table deliberately excludes these
zero-count rows when counting active keyed entries.

**Why simple record slicing is not justified:** `QAOKP09A`
declares a 352-byte QDDS entry including one status byte
(351 record-data bytes). The `QAOKLAKA` positive-length
DKYT row has raw location **326** and raw length **47**,
which exceeds that 351-byte record boundary regardless of
the usual one-based offset correction. Several other QAOK
rows have positive lengths and a raw location of **zero**
(an ambiguity that the ordinary field-name join correctly
declines to resolve). Therefore copying those regions out
of the QDDS record and calling them a reconstructed machine
key would invent a release-specific field-layout rule.

**Additional capacity caution:** the DKEY-reported machine
key lengths **132, 164, 178 and 181** exceed the
128-byte machine-index entry limit quoted by the older
System/38 manual. This is not a demonstrated contradiction
in the underlying data; the number may represent a logical
uncompressed length, or the releases may differ. Neither
explanation is validated. The decoder continues to expose
only verified tree text and database references.

The backend now reports `declared_field_bytes`,
`user_length_over_field_bytes`, `sequence_01_field_count`,
and the narrow `qaok_two_byte_pattern_matches` **arithmetic**
predicate on each DKEY spec. The CLI/TUI keys view reports
the unexplained length difference while keeping partial-key
entries partial. No omitted bytes are padded, inferred, or
used for sorting. Synthetic regressions reproduce all eight
observed populated-row shapes and preserve negative cases.

### Second independent check: DKYT field-location spacing (V2R3)

A separate, read-only examination of every **populated DKEY row** in
Mark's eight QAOK indexes found an additional relationship *within*
the adjacent raw DKYT locations, not derived from the DKEY user-key
length:

`next_DKYT_location - current_DKYT_location
   = current_DKYT_length + (2 if current_sequence_byte == 0x01 else 0)`

The rule applies to consecutive positive-length rows only. The observed
zero-length fork/control rows in `QAOKLDKA`/`QAOKL10A` interrupt the
sequence, so no assumed contiguity across those rows is counted.

| QAOK family | Raw DKYT lengths | Sequence bytes | Raw DKYT locations | Matching adjacent pairs per active DKEY |
| --- | --- | --- | --- | ---: |
| `QAOKS02A` | 40, 64 | 01, 01 | 0, 42 | 1 / 1 |
| `QAOKS03A` | 10, 40, 64 | 00, 01, 01 | 0, 10, 52 | 2 / 2 |
| `QAOKS04A` | 8, 40, 64 | 00, 01, 01 | 0, 8, 50 | 2 / 2 |
| `QAOKS05A` | 8, 40, 64 | 00, 01, 01 | 0, 8, 50 | 2 / 2 |

Each of these four indexes has **two populated DKEY rows with the same
shape**. Across all eight rows, **14/14 adjacent field-location
differences agree**, with no mismatches. The four other QAOK indexes
have either only one positive-length row or an intervening zero-length
fork/control row; no adjacent positive-length pair is scored for them.

This is **independent** corroboration for two bytes of storage/key-layout
overhead, because it uses raw DKYT location differences rather than
the DKEY `user_key_length` scalar. The raw sequence byte `0x01`
might identify an IBM variable-length format, but **that bit is not
yet decoded**.

**IBM documentation, later release / analogy only:** IBM's V5R2
*DDS for Physical and Logical Files* and modern IBM i/RPG
variable-length format descriptions explain that `VARLEN` fields
can carry **two bytes of current-length information** in addition
to their declared maximum field length. See IBM's
`https://www.ibm.com/docs/en/i/7.4.0?topic=type-variable-length-character-graphic-ucs-2-formats`
and V5R2 IBM DDS document
`https://public.dhe.ibm.com/systems/power/docs/systemi/v5r2/pt_PT/rzakbmst.pdf`.
Neither later source establishes what the V2R3 DKYT byte `0x01`
means, or says that the *on-disk* QDDS row has exactly the same
representation as an RPG in-memory variable-length field. Thus
"two-byte length prefix" is now a **specific plausible hypothesis**,
not a decoded key-field type.

**Record-level countercheck — important negative result:** the
`QAOKP09A` recovered data segment's logical 20 pages must be
assembled in *virtual address order*, from a **4-page physical extent
at LBA 1,632,280** and a **16-page physical extent at LBA
1,632,160**. After excluding only the single 32-byte segment
header, all 14 352-byte entries (default + 13 user RRNs) have
the independently validated live DENT status `0x80`.
If one naively interprets the raw `QAOKS02A` DKYT locations
0 and 42 as literal offsets into each 351-byte record-data
portion, their first two bytes do **not** both behave as
two-byte big-endian lengths: for all 13 user records, the
word at 0 is zero despite nonzero following data, while
the word at 42 exceeds the respective 64-byte field
maximum in every record. This **rejects that specific direct
record-offset / unsigned-length-prefix model**. It does
not reject the possibility of a length prefix in an
intermediate machine-key representation. The recovered record
bytes, actual names and field contents are not included in
the repository.

The backend now exposes `qaok_adjacent_stride_counts` as a
**matched/tested evidence count** and the CLI/TUI displays that
count when the prior length relation holds. It does not
extract, synthesize, interpolate or alter the missing key
bytes. A mixed success/failure synthetic pair and fork-row
exclusion preserve that distinction.

**Next evidence gate:** identify a format-specific key
materialization or conversion rule from relevant CISC-era
documentation, then independently validate the candidate
against the QDDS record values and *actual* recovered
machine-index key/order on all 13 user RRNs. Until then all
156 QAOK database references remain navigable, with their
literal keys clearly marked partial.

**Next experiment:** compare the per-record key-field
materializations to documented IBM key conversion rules,
one field family at a time. Any recovered literal bytes
must agree with both independent QDDS row evidence and
the actual machine-index path ordering before they are
promoted to a real decoded user key. Do not interpret
`seq=0x01` as a specific variable-length or prefix
field until that cross-check succeeds.

## FUNDDEF surviving key evidence

FUNDDEF's QDDSI reports one key and its root page contains a six-byte candidate
composite key at the expected location:

`F0 00 00 00 00 01`

The final four bytes identify ordinal 1. The first two bytes are consistent with
IBM's documented positive packed-decimal key conversion: force the sign nibble
to F and move it to the high nibble. With FUNDNO defined as a two-digit packed
field, `F0 00` is therefore strong evidence for a surviving indexed FUNDNO
value of zero.

This does **not** recover FUNDDESC; those record bytes appear to have been on
the missing disk.

ACCTDEF's recovered QDDSI currently reports zero keys and has no populated root
page. Treat that as "zero keys represented by the surviving access path" rather
than an unconditional claim that no historical ACCTDEF rows ever existed; an
index can have maintenance/recovery state that we have not decoded yet.

## Machine-index placement and first traversal

The recovered QDDSIs match IBM's high-level layout well:

- sparse/base-page material begins around the 2-KB boundary;
- the active root is reached through the observed control/root pointer chain
  rather than a fixed segment offset;
- larger indexes use additional dense pages consistent with secondary pages.

The ordinary active root pages now provide enough repeated structure to walk
small single-page trees conservatively. Bytes `+4..+5` of the root page are
the free-byte count and `+6..+7` are the absolute first-free offset. The latter
bounds the used portion of the page; the free-byte count can also include holes
inside the current tree, so it is not always simply `page_size - used_bytes`.
The observed roots resolve to 2048-byte logical pages.

Real QDDSI trees also corrected the earlier provisional node-bit decoding:

- node bit 20 (zero) means common text is present;
- bit 19 is left/right direction;
- bits 18-16 select the key bit being tested;
- the low 16 bits are the XOR displacement;
- bit 21 is preserved but remains unnamed.

A successor cluster is found by XORing the current node's 16-bit displacement
with the offset of the node that led into the current cluster. The cluster has
left and right three-byte branch elements, followed by a common-text element
when requested by the originating node. Real common/terminal text also shows
that the seven-bit text-length field is stored as byte-count minus one: encoded
zero represents one byte.

The first read-only traversal reconstructed complete keys from ordinary
one-page indexes:

- `DBUUSERS`: `*PUBLIC   ` plus database reference `00000001`, resolving to
  QDDS RRN 1;
- `QAEASTUL`: two entries sharing a common 13-byte prefix, with RRN hints 1
  and 2;
- `QASNADSQ`: a nested tree reconstructs `TGTSYS`, `TGTSYSAS`, and
  `TGTSYSLN` key values with RRN hints 9, 10, and 11;
- `QAO1CVNP`: six entries with two DKYT key fields and a four-byte composite
  user key. The reconstructed user-key bytes exactly equal the first four
  bytes of QDDS RRNs 1 through 6, while the appended references resolve to
  those same RRNs.

This is the first actual machine-index traversal in the DASD explorer rather
than a known-key search. It validates common-text reconstruction, nested XOR
links, left/right enumeration, and the ordinary four-byte RRN hint against
independent QDDS data.

## Multi-page access-path traversal

The next real-image pass established the ordinary page-pointer relationship as
well. Large QDDSI objects are recovered as virtual segment groups assembled
from multiple physical extents, so page traversal must use the reconstructed
virtual segment rather than assume physical LBA contiguity.

Four unrelated V2R3 indexes contain root-page pointers whose three-byte
elements have segment-table index zero. Their low page-offset field advances
in values such as `0x18`, `0x20`, and `0x28`; the pointed logical page begins
at segment byte offset `page_offset << 8` (256-byte units). Secondary pages
use the same node/text representation and free-byte/first-free constraints as
the active root page.

Following those pointers while carrying the accumulated common-key prefix
produces exact complete traversals:

- `QACJINFO`: 36/36 keys, four logical pages, three page pointers;
- `QAQAATPY`: 99/99 keys, three pages, two page pointers;
- `QAEBAUDL`: 584/584 keys, five pages, four page pointers;
- `QADBXDIC`: 2615/2615 keys, eleven pages, ten page pointers.

For every one of these indexes, the recovered four-byte ordinal hints form an
exact permutation of `1..N`. That is substantially stronger than matching a
few known keys: thousands of tree entries, common-text paths, node links, and
page transitions independently resolve to the complete QDDS ordinal domain.

The decoder follows only page pointers whose segment-table index is zero.
A nonzero segment-table index is retained and reported as unresolved evidence;
no cross-segment interpretation is guessed until a real example or IBM layout
documents it.

## Additional MI 19/51 field type: DBCS Open

A full-segment pass over recovered V2R3 `19/51` record-format objects exposes
field type byte `0x06` in formats where the shorter first-page probes did not.

The important independent cross-check comes from recovered DDS metadata on the
same V2R3 image: fields whose `19/51` descriptors use internal type `0x06`
are defined with DDS data type **O**. IBM DDS terminology identifies `O` as
**DBCS Open**. This is stronger than guessing from record bytes because some of
the real values happen to contain ordinary SBCS-looking digits or text while
others contain mixed/binary-looking data.

The backend therefore labels `0x06` as `DBCS-OPEN`, but deliberately does
**not** decode its value bytes as code page 037. Reliable rendering requires the
applicable DBCS CCSID and shift-state representation; until those are recovered,
the browser preserves the field value as raw hexadecimal evidence.

This mapping is an observed V2R3 result independently corroborated by the
recovered DDS definition. It should not be generalized to additional unknown
internal type bytes without the same level of evidence.

### Independent eight-index DKEY census on Mark V2R3

A separate **read-only direct physical-page** inspection located all
eight surviving `0C/90` primary objects using the *combination*
of the exact eight-byte EBCDIC name at payload +0x24 and MI type
bytes `0C 90` at +0x22. This is stronger than a disk-wide substring
match because the index primary's object header and the DKEY/active-root
pointers corroborate the selected address.

The first physical sector supplies the six-byte virtual-address base;
the primary's recovered first pages show DKEY count at segment +0x11E,
six-byte DKEY pointer at +0x12A resolving to +0x400, and an active
machine-index root reached by the independently observed control
pointer chain at +0x13A and control +0x20. Each active root has
page type `0xCC`. Physical sectors were read directly from the
archived image; **only numerical structural metadata**, never
recovered user-key bytes or source records, is reported here.

| QDDSI object | Primary LBA | Populated DKEY key counts | DKEY user/machine key lengths (populated rows) | Active root offset |
| --- | ---: | --- | --- | --- |
| `QAOKLAKA` | 1,578,960 | 13 | 49/76 | +0x1000 |
| `QAOKLDKA` | 1,574,256 | 13 + 0 | 84/132 | +0x1000 |
| `QAOKL10A` | 1,588,128 | 0 + 13 | 76/120 | +0x1000 |
| `QAOKS01A` | 1,589,344 | 13 | 66/102 | +0x1000 |
| `QAOKS02A` | 1,588,704 | 13 + 13 | 108/164, both rows | +0x1800 |
| `QAOKS03A` | 1,588,144 | 13 + 13 | 118/181, both rows | +0x1800 |
| `QAOKS04A` | 1,588,800 | 13 + 13 | 116/178, both rows | +0x1800 |
| `QAOKS05A` | 1,588,832 | 13 + 13 | 116/178, both rows | +0x1800 |

**Independent numerical cross-check:**
`13 + 13 + 13 + 13 + 26 + 26 + 26 + 26 = 156`,
exactly the number of partial terminal database references
already independently enumerated through the index trees.
The zero-count DKEY rows in `QAOKLDKA` and `QAOKL10A` are
preserved rather than silently omitted or reclassified.
Only the **populated** row's length pair is printed above for
those two indexes.

Several declared machine-key lengths exceed the 128-byte
machine-index entry-length limit discussed in the historical
System/38 material. This is an *observed disparity* between a DKEY
length field and that historical text, not proof of a particular
compression algorithm or a V2R3 architectural exception.
The live disk's index root, DKEY row, and terminal may encode
different notions of key length. No bytes have been synthesized
to make the lengths agree.

**Scope caveat:** the first extent header and the pointer-target
pages were checked, but not every following physical page has an
identical eight-byte header; the early object group can contain
noncontiguous or sparse physical payloads. Do not use the raw
16-sector probe to assert the entire virtual object has been
recovered contiguously. The production parser follows the
validated recovered segment model; the census only corroborates
the **local primary metadata**.

## Compact-key evidence audit (2026-10-09)

After a bounded, unsuccessful SMVT-checkpoint pointer search, the
development priority moved back to the eight QAOK long/compact-key
QDDSI variants. The existing machine-index traversal already gives
**complete terminal database references** but not complete user-key
bytes for those variants; we must not conflate the two.

New `audit_partial_data_space_index_keys(layout, traversal)`
returns per-**DKEY** aggregate evidence without constructing keys:

- number of partial terminal entries compared with the DKEY's
  declared `key_count`;
- minimum/maximum **actual recovered tree-key body lengths**,
  excluding the separately validated four-byte database reference;
- minimum/maximum numerical difference between the DKEY-declared
  **machine** key length and `len(tree evidence) + 4`;
- number and distinct count of positive or otherwise observed
  three-byte ordinal hints, plus their min/max values.

The numerical length difference does **not** identify where omitted
key bytes belong, whether compression is reversible, or whether any
common prefix/suffix can be reconstructed. Complete-key entries
are excluded from the partial-only grouping. The helper rejects
out-of-range DKEY numbers, four-byte reference/DKEY mismatches and
impossibly longer tree paths. The ordinary QDDSI traversal remains
the source of terminal bytes and already bounds the index itself.

The existing `as400-dasd member IMAGE LIB FILE MEMBER` report now
shows the per-DKEY audit whenever traversal returns partial keys.
This provides an immediate *repeatable comparison* for QAOKLAKA,
QAOKLDKA, QAOKL10A and QAOKS01A..QAOKS05A without exposing user
data in committed fixtures. Initial regression tests use the
existing QAOK-style synthetic `3FFF 00000001` terminal
(102-byte declared machine key, 2 bytes of tree body, and 4 bytes
of reference, hence **96 bytes numerical shortfall**), plus a
two-DKEY synthetic partial-index case. The values are *synthetic
fixture checks*, not eight real-image audit results.

### Third independent check: the raw `3FFF` pair tracks DKYT field count

The per-DKEY audit was then run against the **actual recovered tree text** for
all eight V2R3 QAOK access paths. This produced a new corpus-wide relationship
without reconstructing a single missing user-key byte:

- every one of the **156 partial terminal bodies** contains exactly one raw
  non-overlapping `3F FF` byte pair for each **positive-length DKYT row**
  belonging to its selected DKEY;
- equivalently, the field-count relation holds for **156/156 terminals**;
- `QAOKS01A`, `QAOKS02A`, and `QAOKS03A` have terminal bodies made only
  from one, two, or three such byte pairs before the four-byte database
  reference;
- `QAOKS04A` and `QAOKS05A` carry a varying literal prefix followed by
  three pairs; `QAOKLAKA` carries a varying literal prefix followed by one;
- `QAOKLDKA` and `QAOKL10A` each have two pairs with one intervening
  byte associated with their existing zero-length fork/control-row shape.

This is an inventory of a **raw byte pattern**, not a declaration that
`3FFF` is a delimiter, terminator, length word, or any other field. The
production code therefore reports the pair count, the number of
positive-length DKYT rows, the number of terminals where those counts agree,
the non-`3FFF` byte range, and the trailing-pair run. It does **not** strip
the pairs or use them to synthesize a key.

Crucially, this is **not the same relationship** as the earlier two-byte
DKEY/DKYT length accounting. `QAOKS04A` and `QAOKS05A`, for example, have
three positive-length fields and therefore three observed `3FFF` pairs, but
only two fields have raw sequence byte `0x01`; their declared user-key
length exceeds the sum of field lengths by four bytes, not six. Therefore a
`3FFF` pair cannot simply be identified with the two extra bytes previously
correlated with each `seq=01` row.

A direct raw-page check also rules out a traversal artifact. Stored
**common-text** regions themselves contain these `3FFF` pairs in seven of
the eight access paths (and terminal text carries the pair in all eight).
The missing bytes therefore are not explained by an unvisited common-text
element in the current tree walker.

There is a useful period-documentation boundary here. SY21-0889-5, pp.
2-16 through 2-18, says database management builds each key field before
inserting the resulting bit strings into the general machine index, applying
field-specific force/collating/numeric/order conversions as required. That
supports treating the machine-index text as a **materialized key
representation**, not as a guaranteed byte-for-byte copy of the QDDS record.
The manual does not define this observed V2R3 `3FFF` pattern, so its meaning
remains open.

Two record-level correlations narrow the next experiment while staying
within already nonzero DKYT-location evidence:

- for all 13 active `QAOKLDKA` RRNs, the candidate 18-byte record region at
  the nonzero DKYT location is all zero and the tree body preserves exactly
  18 zero bytes before its first `3FFF` pair;
- for all 13 active `QAOKL10A` RRNs, the analogous ten-byte region is
  EBCDIC blank-filled, while the tree body has no literal field bytes before
  its first pair.

Those correlations led to a stronger direct-field reconstruction.

### Direct QDDS-field reconstruction for four QAOK access paths

The shared `QAOKP09A` QDDS primary itself is a 20-page logical segment.
Its field-description area begins at logical +0x400 with a count of **36**,
followed by repeated 32-byte descriptor rows. The descriptor semantics are
still only partially decoded, but several rows can be independently joined to
DKYT rows because **both the declared maximum/storage length and the nonzero
one-based record location agree**.

Four QAOK access paths have such direct joins:

- `QAOKLAKA`: DKYT length 47 / location 326 agrees with QDDS descriptor
  row 34. In every one of the 13 live user RRNs, the two bytes immediately
  preceding the field's data area form a big-endian value in range 7..17.
  That value equals the number of following literal field bytes represented
  in the machine-index tree. The entire recovered compact tree body is
  exactly those current bytes followed by one raw `3FFF` pair: **13/13**.
  This gives a concrete corpus-level explanation for this row's
  `47 + 2 = 49` declared user-key accounting: a two-byte current-length
  value is physically present for the 47-byte maximum field.
- `QAOKS01A`: its length-64 / location-50 DKYT row agrees with QDDS
  descriptor row 7. The corresponding two-byte current-length slot is zero
  in all 13 live RRNs; the compact tree body is just one raw `3FFF` pair:
  **13/13**.
- `QAOKLDKA`: the fixed 18-byte / location-188 row agrees with QDDS
  descriptor row 21, while its length-64 / location-50 row again agrees with
  row 7. All 13 records preserve the fixed 18 zero bytes literally, then the
  raw pair, the existing one-byte fork/control value, and the empty
  length-64 field's raw pair: **13/13**.
- `QAOKL10A`: the fixed 10-byte / location-178 row agrees with QDDS
  descriptor row 20, and the length-64 row again agrees with row 7. The
  ten-byte source field is EBCDIC blank-filled in all 13 RRNs; its padding is
  absent from the compact tree, which consists of a raw pair, the existing
  fork/control byte, and the empty length-64 field's raw pair: **13/13**.

Thus **52/52 terminal bodies** in these four indexes can now be reproduced
from independently recovered QDDS record evidence without inventing omitted
user-key bytes. This is stronger than the earlier length-only correlation.

The later IBM AS/400 DDS/RPG descriptions of variable-length character data
are useful corroboration only: they describe a two-byte current length in
addition to the declared maximum data area. They do not prove that the raw
V2R3 DKYT sequence byte `0x01` names that facility, nor do they define the
observed `3FFF` compact-tree marker. The direct `QAOKLAKA` and
`QAOKS01A` record bytes establish the two-byte current-length behavior
independently for these real V2R3 fields.

The four `QAOKS02A`..`QAOKS05A` layouts remain indirect: some positive
DKYT locations are zero or behave as offsets within an intermediate key
layout rather than literal QDDS record positions. Nevertheless, the QDDS
field table supplies matching source *shapes*: an empty 40-byte
variable-length candidate, the independently verified empty 64-byte field,
blank-filled ten-byte candidates, and eight-byte fixed candidates. These
explain why the S02/S03 bodies are marker-only and why S04/S05 carry one
trimmed literal prefix followed by three markers, but the source-field
mapping is not yet unique enough to promote into the decoder.

### Additional raw DKYT tail scalars

The previously unnamed DKYT tail also carries two repeatable numerical
relationships across every populated QAOK DKEY. Production diagnostics now
expose these only by raw byte offset:

- raw word **+0x12** is a running count of positive `length_or_fork`
  values, with +1 for the observed zero-length `seq=0x40` fork/control
  row;
- raw word **+0x14** advances by
  `ceil(3 * (L + 1) / 2)` for each positive field of raw length `L`,
  again +1 across the observed zero-length fork/control row;
- for every populated compact QAOK DKEY, the **final +0x14 word + 4**
  equals the DKEY-declared machine-key length.

These words are *not named fields*. Ordinary indexes can carry similar raw
values without using them as their literal machine-key length, so the
relationship is recorded as QAOK corpus evidence rather than generalized
architecture.

One UI correction follows from the same work: a positive raw DKYT location is
no longer printed as a QDDS record offset unless a recovered 19/51 format
field independently matches both offset and length. Uncorroborated locations
are now explicitly labelled raw/unverified.

#### Independent physical-object identity check (read-only, 2026-10-09)

A fresh exact-byte search of the original 1,004,257,800-byte
`marks.hda` image (1,931,265 physical sectors at 520 bytes each)
located the following header-validated primary pages. Matches require
the eight-byte CP037 name at physical sector byte +0x2C (payload +0x24)
**and** the expected MI type/subtype at physical byte +0x2A
(payload +0x22), rather than searching names alone.

| Physical LBA | Raw type/subtype | Name |
| ---: | --- | --- |
| 1,632,236 | `0B/90` | `QAOKP09A` |
| 1,578,864 | `0C/90` | `QAOKP09A` |
| 1,588,704 | `0C/90` | `QAOKS02A` |
| 1,588,144 | `0C/90` | `QAOKS03A` |
| 1,588,800 | `0C/90` | `QAOKS04A` |
| 1,588,832 | `0C/90` | `QAOKS05A` |

This confirms a practical disambiguation requirement: `QAOKP09A`
occurs as **both** a QDDS data-space primary (`0B/90`) and a QDDSI
index primary (`0C/90`). Name-only scans can silently select the
wrong object. The `0B/90` first page has a segment-group size field
of 20 pages, consistent with the previously reconstructed 20-page
logical primary. The immediately following physical sectors do not
show monotonically increasing logical page headers, and nearby LBAs
also contain other objects; **physical contiguity is not a valid
replacement for the recovered virtual-segment map**. This check
corroborates object identity only. It does not uniquely associate
the indirect DKYT locations in S02..S05 with QDDS source fields and
does not resolve the raw `3FFF` pattern.

#### Independent QAOKP09A physical QDDS field census (2026-10-09)

A second read-only check used the original Mark V2R3 image and reconstructed
the **separate** `0B/90` QDDS primary and its `03/B4` owned data-space
segment in their validated logical extent order. The first QDDS primary
pages are at LBA 1,632,236..239, with the remaining physical portions
at 1,578,830..831, 1,587,564..565, 1,588,276..279,
1,589,492..495 and 1,591,776..779. The `03/B4` space uses
LBA 1,632,280..283 followed logically by 1,632,160..175.
These are **physical sector lists**, not assumptions that an object is
one contiguous disk run. Each physical sector contributes its 512-byte
payload after its 8-byte storage header.

The QDDS primary at logical +0x400 has the observed 36-row,
32-byte-per-row table (`0x0024` count). Relevant raw rows in that
table independently report the following length/location pairs:

| Zero-based descriptor row | Raw type | Raw length | Raw location |
| ---: | --- | ---: | ---: |
| 7 | `0x0009` | 64 | 50 |
| 10 | `0x0009` | 40 | 60 |
| 17 | `0x0009` | 10 | 160 |
| 20 | `0x0009` | 10 | 178 |
| 21 | `0x0004` | 18 | 188 |
| 24 | `0x0009` | 40 | 212 |
| 27 | `0x0004` | 64 | 254 |
| 30–31 | `0x0004` | 8 each | 287, 295 |
| 34 | `0x0004` | 47 | 326 |

The raw type values are **not** newly decoded field semantics. The
presence of two different 40-byte candidates, multiple 10-byte
candidates and multiple 8-byte candidates is important: matching a
DKYT *length alone* would be ambiguous even before considering its
potential intermediate-layout location. The 64-byte field at raw
location 50 has a separate candidate of raw type `0x0004` at
location 254. The QDDS table does not, by itself, establish which
candidate any indirect QAOKS02A..S05A DKYT row uses.

For the reconstructed `03/B4` data space, sector payload offset
`0x20 + 352*n` (`n=0..13`) holds byte `0x80` in **all 14**
records. This independently corroborates a 352-byte physical
record slot (including its status byte), with one default entry and
13 active entries, against the 13 user ordinals of the QAOK indexes.
It does not prove a mapping between any `seq=01` raw DKYT row and
one of the descriptor candidates.

### Thirteen-record candidate value census (read-only)

The same independently reconstructed `03/B4` record space was compared
record-by-record for user RRNs 1..13. For each descriptor row below, bytes
were taken at its observed one-based location within the recovered record
payload and for its raw declared length. The comparisons do not interpret
raw descriptor type codes or translate the values into QDDSI key material.

| QDDS descriptor row | Length / location | Distinct byte strings among 13 user RRNs | Observed characteristic |
| ---: | --- | ---: | --- |
| 7 | 64 / 50 | 1 | all zero bytes |
| 10 | 40 / 60 | 1 | all zero bytes |
| 17 | 10 / 160 | 1 | all EBCDIC blank bytes (`40`) |
| 20 | 10 / 178 | 1 | all EBCDIC blank bytes (`40`) |
| 21 | 18 / 188 | 1 | all zero bytes |
| 24 | 40 / 212 | 1 | all zero bytes |
| 27 | 64 / 254 | 13 | variable bytes |
| 30 | 8 / 287 | 3 | 11 blanks and 2 differing nonblank strings |
| 31 | 8 / 295 | 3 | 11 blanks and 2 differing nonblank strings |
| 34 | 47 / 326 | 13 | variable bytes |

For the two eight-byte rows, the two nonblank instances occur at user RRNs
7 and 10 in **both** rows. This coincidence is useful evidence for a later
paired-field hypothesis, but it does **not** establish that the two bytes
sequences are interchangeable or that either field is selected by S04/S05.

**Overlapping descriptor discovery (independently checked on every
user record):** the raw location/length of descriptor row 27
(64 bytes at one-based 254) encompasses **both** eight-byte descriptors:
row 30 (287..294) and row 31 (295..302). Relative to the first byte of
row 27, these are slices `[33:41]` and `[41:49]`, respectively.
Byte-for-byte comparisons of each independently sliced value from the
reconstructed 352-byte records agree for **13/13** RRNs for each of the
two nested descriptors (**26/26** comparisons). The descriptor table
therefore contains overlapping storage views here; the 64-byte row
and two eight-byte rows must *not* be treated as three independent
record-storage regions. Their field semantics and their roles in
S04/S05 indexing remain unresolved.

Among the 13 records, rows 30 and 31 have unusual nonblank contents
at exactly RRNs 7 and 10; the overlap shows these occurrences are
already inside the variable 64-byte region rather than independent
corroborating values. Next compare the **actual recovered S04/S05
tree prefixes** for these RRNs and all other ordinals before mapping
any DKYT row to a particular QDDS descriptor. The overlap is
structurally exact but does not yet establish a key-materialization
rule or a meaning for `3FFF`.

**Important negative result:** length-matched rows 10/24 (40 bytes) and
17/20 (10 bytes) are observationally indistinguishable across the current
13 records: a source-value match alone cannot uniquely identify them.
Unlike those pairs, the two 64-byte candidates have different variability
(row 7 all zero, row 27 distinct for every user RRN), which could reject
a proposed source-field assignment when contrasted with the corresponding
tree body. This is a bounded corpus result only. No automatic source
mapping or compact-key reconstruction is justified yet.

**Evidence gate:** before resolving S02..S05, distinguish the source
fields using descriptor identity and 13-per-record value comparisons,
not only raw length/location similarity. Preserve the existing 104
partial tree bodies and complete database-reference suffixes until
that comparison produces an unambiguous field-materialization rule.

#### Verified literal-prefix sources in QAOKS04A/QAOKS05A (2026-10-09)

A **read-only, RRN-matched machine-index traversal** of the original Mark
V2R3 disk provides a decisive source-field comparison. Each S04/S05 index
primary is a **physically contiguous 16-page segment** with its control
pointer at logical +0x1000 and active root page at +0x1800. Reconstructing
the machine-index node/common-text paths from the raw index pages produces
**26 terminal references** per index: 13 RRNs for each of two populated DKEY
rows, with no unresolved page pointers or traversal errors. For every entry,
the partial tree body contains a nonempty literal prefix followed by exactly
three raw `3F FF` pairs and then the intact four-byte DB reference.

The independent `QAOKP09A` 36-row QDDS field table at logical +0x400
identifies **descriptor row 1: length 8, one-based record location 9** and
**descriptor row 2: length 8, one-based record location 17**. These map
respectively to zero-based offsets 8 and 16 within the 351-byte record
payload, after the data-space entry's separate one-byte status.

| Access path | Raw QDDS source candidate | Comparison | Result |
| --- | --- | --- | --- |
| `QAOKS04A` | Descriptor row 1, data `[8:16]` | Strip trailing CP037/EBCDIC blanks (`0x40`) and compare *every* literal prefix before the first raw `3FFF` | **26/26** DKEY/RRN terminal matches |
| `QAOKS05A` | Descriptor row 2, data `[16:24]` | Same literal byte comparison | **26/26** matches |

These are **52/52 recovered terminal bodies** across S04/S05 reproduced
exactly as `candidate.rstrip(0x40) + (3FFF * 3)`, followed by the
independently verified database reference. Because each index repeats the
same 13 RRN values under two populated DKEY rows, this represents **26
distinct index/RRN prefix observations**, mirrored across DKEY groups—not
52 independent source-record values. No archived user strings are committed.

The critical discriminators were RRNs 7 and 10: the two paths have
different-length literal prefixes for these records. The S04 prefix is
always byte-for-byte identical to QDDS `[8:16]` with right blanks removed;
S05 is always identical to `[16:24]`. Across the 13 RRNs, S04 prefix lengths
range **2..8**, and S05 **4..8**. This defeats the earlier suggestion
that the literal prefixes could derive from the overlapping 64-byte field
at raw location 254 or its eight-byte subfields: those regions are not
needed to account for either recovered literal prefix.

Both S04 and S05 have **identical raw DKYT field shapes** under each DKEY:
8-byte `seq=00` at raw location zero, 40-byte `seq=01` at raw
location 8, and 64-byte `seq=01` at raw location 50. The first raw
location zero therefore cannot by itself identify a physical QDDS record
offset. The independent field table plus RRN-correlated bytes is necessary
to distinguish S04's source from S05's. Exact matching is a strong
**source-field materialization observation**, but it does **not** yet give a
decoder for the two later fields or the semantics of `3FFF`.

A pure backend helper
`audit_partial_index_literal_prefix_candidate(traversal, records,
record_offset=..., field_length=...)` now counts such literal matches,
including empty-value and missing-record cases, using **caller-supplied**
record offsets. It never changes the recovered keys or treats a raw
`3FFF` pair as a proven field delimiter. Synthetic regressions use only
fabricated data, including negative candidate comparisons and two DKEY
rows.

**Revised evidence gate:** S04/S05 literal prefixes are accounted for
(**52/52 terminal bodies**). All **104** S02..S05 entries remain
partial *logical keys*: further work must establish the middle/final
40/64-byte source identities, compact `3FFF` representation and raw
+0x14 transform without synthesizing maximum-length padding. The
S02/S03 tree bodies are marker-only and can match empty candidate
fields, which does not uniquely identify their source descriptors.

#### Raw pair-position diagnostic (incremental)

The partial-key audit additionally records the minimum and maximum **byte
offset of the first raw `3F FF` pair** among terminals in each DKEY group.
The member report exposes this range alongside existing pair counts and
trailing-run evidence. A varying first-pair offset is useful for isolating
paths with varying literal prefixes, especially QAOKS04A/QAOKS05A, while
an offset of zero can be contrasted with marker-only paths. This is a
diagnostic capability, **not** a new corpus-level finding or a decoded field
boundary. Its regression uses synthetic examples with offsets 0, 1 and 3.
No complete user-key bytes are produced.

**Next actual decoding gate:** resolve the intermediate/source-field mapping
for `QAOKS02A`..`QAOKS05A`, then determine what the `3FFF` field marker
and raw +0x14 length transform represent architecturally. Any complete-key
decoder must reproduce the real QDDS-to-tree materialization and ordering for
all 156 RRNs without padding or interpolating missing maximum-field bytes.

## Next implementation steps

1. Keep the eight long/compact QAOK variants as an explicit partial-key
   research follow-up; preserve their tree evidence and complete database
   references without inventing omitted user-key bytes.
2. Keep DKEY-aware keyed-record presentation in the CLI/TUI: only map an index
   entry to the displayed member when its DKEY row points to that member's
   QDDS, and label partial key evidence explicitly.
3. Resume the permanent context/library machine-index work using the validated
   QDDSI lessons: dynamic roots, node XOR links, common/terminal text,
   page-pointer traversal, and conservative handling of compressed keys.

## Research discipline

- Treat SY21-0889-5 terminology as the architectural baseline.
- Use both real images where a claim is intended to be architecture-level.
- Label B10-only offsets/layout details as observations until independently
  reproduced.
- Never infer "logical file" solely from a missing QDDS primary on one disk.
- Keep all DASD access read-only.
