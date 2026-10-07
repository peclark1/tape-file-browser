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

The ordinary one-DKEY traversal is now validated beyond hand-picked examples.
A repeatable pass over Mark's recovered V2R3 QDDSI primaries found 277 plausible
`01B4` QDDSI primary segment groups. Reassembling fragmented segment groups in
virtual-address order and applying the current conservative walker produced:

- 229 complete one-DKEY traversals;
- 42 multi-DKEY indexes, deliberately rejected by the current walker rather
  than guessed;
- 2 special indexes whose active machine-index root does not use the ordinary
  root-node shape;
- 2 special long-key indexes whose compressed text is not yet reconstructed
  correctly;
- 2 segment groups whose full virtual chain is not recovered by the current
  header-based extent reconstruction.

Every one of the 229 complete traversals resolves its DKEY data-space address
to a recovered QDDS primary. In 226 cases the ordinary database-reference
suffix behaves as the simple four-byte RRN/ordinal hint used by the browser and
falls within the recovered QDDS range. Three special cases demonstrate why the
code correctly labels this value an `ordinal_hint` rather than claiming that
every database-relative-address encoding is a plain RRN.

This changes the remaining problem substantially: ordinary one-DKEY tree
walking is no longer the research blocker. The next database/index work is the
exception set -- multi-DKEY indexes, special root/text layouts, and the few
database-reference variants that need more of IBM's documented adjusted data
space number/internal-flag interpretation.

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

The recovered 16-page QDDSIs match IBM's high-level layout well:

- sparse/base-page material begins around the 2-KB boundary;
- the active root page in populated examples is at segment offset `0x1000`;
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

The first read-only traversal deliberately stops at page pointers, but it
reconstructs complete keys from ordinary one-page indexes:

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

1. Join DKYT field positions/lengths to friendly recovered 19/51 field names in
   CLI/TUI presentation.
2. Add keyed-record navigation that keeps raw RRN/arrival order available as an
   independent view.
3. Exercise the keyed view on both simple character keys and multi-field/binary
   keys, and preserve partial/raw fallback for unsupported pointer variants.
4. Reuse the now-validated machine-index traversal lessons when permanent
   context/library directory work resumes, without assuming the QDDSI page
   placement is identical to a context index.

## Research discipline

- Treat SY21-0889-5 terminology as the architectural baseline.
- Use both real images where a claim is intended to be architecture-level.
- Label B10-only offsets/layout details as observations until independently
  reproduced.
- Never infer "logical file" solely from a missing QDDS primary on one disk.
- Keep all DASD access read-only.
