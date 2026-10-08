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
