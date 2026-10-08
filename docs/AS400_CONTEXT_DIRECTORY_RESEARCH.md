# Permanent context / library directory research

## Why this is the current priority

The explorer currently recovers permanent context/library objects and assigns
many recovered objects to libraries using the object's EPA context back-pointer.
That direction works well, but it is only one side of the relationship.

The next milestone is to reconstruct the permanent context's own machine index
and obtain an independent `context -> object` directory. That should both
validate existing membership and recover objects whose EPA-side context
information is incomplete or ambiguous.

## Documentation reconnaissance

### Object and library model

The period manual set gives useful user-visible context:

- *Understanding AS/400 System Operations* describes AS/400 data as objects,
  with an object description/header plus a functional portion. It describes
  libraries as groups of related objects and explains that object identity
  includes object type as well as name.
- The same source explains single-level storage as one virtual address space
  below the Machine Interface, spanning main and auxiliary storage.

These are conceptual/operator-level descriptions. They help explain what a
library/context represents to the user, but they do **not** document the CISC
context machine-index byte layout.

### Storage-management directories are a different layer

IBM's *AS/400 Disk Storage Topics and Tools* defines several storage-management
terms that are easy to confuse with the context/library work:

- the **free space directory** is a pageable machine index tracking unassigned
  sectors on CISC systems;
- the **permanent directory** maps permanent virtual addresses to their DASD
  locations;
- the **static directory** stores persistent VLIC information such as the disk
  location of the permanent directory.

Those structures concern storage address/location management. The
`04/01` permanent context/library machine index we are researching is an
object namespace. Similar machine-index machinery may be reused, but the
storage-management permanent directory and a permanent context are not the
same structure and should not be named interchangeably.

### What the code already implements

The parser already has a conservative release-2 machine-index primitive:

- three-byte elements;
- text elements;
- decision nodes;
- page-pointer elements;
- documented bit/displacement fields for those element classes.

It also has a `context-page` forensic probe that decodes caller-selected,
three-byte-aligned elements from a recovered `04/01` context segment.

What is intentionally missing is automatic recognition of the index page
header/trunk, pointer following, front-end-compressed key reconstruction, and
full context traversal.

## Stronger IBM documentation now located

The IBM *System/38 Vertical Microcode Logic Overviews and Component
Descriptions Manual*, SY21-0889-5 (sixth edition, September 1985), gives us
substantially stronger architectural evidence than the higher-level AS/400
manuals.

### Documented context semantics

The Context Management section states that contexts store **addressability to
system objects**. Addressability to a system object can be in only one context
at a time. Once addressed by a context, an object can be located through
Resolve System Pointer or late binding.

For permanent contexts, the first segment group contains:

1. segment-group header;
2. EPA header;
3. a machine index containing the actual context entries.

The manual explicitly gives the logical machine-index entry as:

```text
T S NL N @
1 1  1 * 8     (bytes)
```

where:

- `T` is object type;
- `S` is the user-defined qualifier/subtype;
- `NL` is the name length after trailing blanks are removed;
- `N` is the user-specified object name;
- `@` is the eight-byte address of the object's EPA header.

It also documents dangling-entry validation by comparing segment extender,
object name, and the object's back-pointer to the addressing context. This is a
particularly useful independent cross-check for our EPA-derived membership.

### Documented release-2 machine-index model

The Machine Index Management section says release-2 indexes use three-byte
elements, may span as many as 64 segment groups (1 GB), and support multiple
page sizes. The index is a binary radix tree containing page pointers, text
elements, nodes, and clusters.

Common text represents leading bytes shared by multiple entries. Terminal text
contains the uncompressed residue, with one terminal text element per index
entry. A search starts at the root node of the trunk page and follows tested
argument bits, common text, and page pointers until terminal text is reached.

The generic machine-index documentation also states that an index entry has a
**prefix** used as the search key and a **suffix** containing information
associated with that key, and that the maximum entry length is 128 bytes.

IBM's later MATCTX documentation remains useful as a semantic cross-check:
materialized context entries are ordered by object type, subtype, then object
name. Later IBM i API documentation explicitly says that the MI term
`context` is synonymous with an IBM i library. These later sources do not prove
the V2R3 physical byte layout, so they are kept as semantic corroboration only.

### Logical-page header field names/order

IBM patent **US4774657A, Index key range estimator** explicitly ties its binary
radix-tree implementation to the System/38 machine-index design. Its Appendix A
repeats the three-byte node/page-pointer/text-element model, states that logical
index pages can range from 512 through 32768 bytes, and explains that page
backpointer information is used when a search backs from a child page to its
parent.

The searchable text of the German family publication **DE3788750T2** preserves
the labels and order from the page-format figure. An **in-use** logical page is
shown with:

1. root node of the page;
2. page type;
3. number of free bytes;
4. offset to the first free byte on the page;
5. backpointer information;
6. current tree.

A **free** page is shown with:

1. unused;
2. page type;
3. number of free pages in the free chain;
4. pointer to the next free page.

This is enough to improve our forensic page descriptions, but **not** enough to
decode bytes safely. The field widths are conveyed in the source figure and are
not reliably represented in the searchable text we have. We therefore preserve
the documented field names/order in `context-page` while deliberately leaving
their offsets undecoded.

### Operator-level library semantics

The attached period book *Understanding AS/400 System Operations* provides
useful browser-facing context independent of the low-level layout. It states
that a library (`*LIB`) is a special object that serves as a directory for a set
of objects, and explains that object identity within a library includes object
type as well as object name. Consequently, two different object types may share
a name in the same library, while two objects of the same type may not.

That wording is now reflected in the `*LIB` TUI description alongside the MI
context/machine-index explanation.

### What remains unknown

The exact release-2 **page-header field widths and byte offsets**, the precise
location of the trunk within a recovered V2R3 context segment, and the physical
prefix/suffix split for a context entry are not yet sufficiently
documented/validated for us to hard-code them.

The new `context-xref` diagnostic therefore uses only the documented expanded
entry form and known EPA-derived object identities. It searches a recovered
context segment for:

- the object's eight-byte internal address;
- contiguous `N + @`;
- the full expanded `T + S + NL + N + @`.

Because the binary-radix tree can move common leading bytes out of terminal
text, absence of a contiguous full entry is **not** treated as a failure. Address
locations instead give us evidence for finding terminal-text regions and
constraining the eventual page-header/trunk decoder.

## Documentation still needed

Before automatically traversing context pages, continue looking for the exact
release-2 page-header/trunk data-area definition. IBM's System/38 documentation
explicitly references **Vertical Microcode Data Areas, SY21-0892**, which is the
best-looking next source for the missing widths/offsets if a scan can be located.
Do not infer those byte offsets solely from repeated patterns in one image.

## First real-image xref result

The first `context-xref` run against the independent Mark/Patrik V2R3
`QGPL` context reported 165 EPA-assigned objects but found the candidate
8-byte object address for only three of them in the **primary** 56-page context
segment. The three primary-segment hits were:

- `0D/50 QLBLSRC1  DFHAID` at primary offset `0x2573`;
- `19/01 QMAPSRC1` at primary offset `0x3165`;
- `0D/50 QUDSSRC   QAWUUDSSRC` at primary offset `0x3843`.

None had contiguous `N + @` or a complete expanded `T S NL N @` byte
sequence.

That result immediately exposed an implementation limitation rather than
justifying a structural conclusion: the initial diagnostic searched only the
context's primary segment group. IBM's release-2 machine-index documentation
allows an index to span multiple segment groups. `context-xref` now searches
**all recovered segment groups with the context's owning-object key** and
reports each hit as `segment-VA + offset`.

The all-owned-segments rerun searched three QGPL-owned segment groups
(69 pages total) and produced **exactly the same 3/165 base-address hits**.
So the missing matches were not hiding in the two additional recovered segment
groups.

The next run tested a literal interpretation of IBM's phrase "address of the
EPA header" as `primary-segment VA + 0x20`. That produced **0/165** matches
in Mark/Patrik QGPL and **0/6** in B10 PPSITEST, while the base/object address
still appeared for 3/165 and 1/6 respectively.

That makes the literal +0x20 interpretation too strong. The System/38 manual
does say `@` is the eight-byte address of the EPA header, but MI system-pointer
semantics identify an object by its **base segment**. The object header comprises
the base-segment header plus EPA header, so the documentation's wording should
not be converted into a physical byte displacement without the missing VMC
data-area/addressing detail.

The diagnostic now treats the base/object address and the literal +0x20 byte
location as separate forensic candidates rather than labeling either one as
proven `@`.

The more productive next discriminator is the documented **key side** of the
entry. Generic machine-index documentation says entries have a prefix used as
the search key and a suffix holding information associated with that key.
Common-text compression removes leading key bytes, while each entry retains
terminal text containing the uncompressed residue. `context-xref` therefore
now reports both the complete `T+S+NL+N` key and the longest contiguous suffix
of that key above a configurable threshold. Clusters of long key-tail locations
should identify terminal-text regions without depending on unresolved `@`
address semantics.

The surviving B10 image does not recover QGPL, but `PPSITEST` is a useful
first cross-image context: it is eight pages and has six EPA-assigned objects.
The `JHUDGINS` context currently has zero EPA-assigned objects, making it a
better later test for whether context traversal can recover membership that the
EPA-backpointer direction misses.

### Key-tail validation on both images

The key-tail pass produced a much stronger signal:

- Mark/Patrik `QGPL`: 92/165 EPA-assigned objects had a contiguous suffix of
  at least five bytes from the documented `T+S+NL+N` key.
- B10 `PPSITEST`: all 6/6 assigned objects had such a suffix.
- PPSITEST's first observed tail locations are tightly grouped at offsets
  `0x865`, `0x8B6`, `0x96D`, and `0xA3B`, which places all six object
  candidates in just two 512-byte storage pages.
- Some candidates deliberately collide on the same raw suffix location:
  `ACCTDEF` and `FUNDDEF` each appear through more than one recovered object
  identity, and QGPL examples such as several `VERIFY` members share one raw
  suffix occurrence. This is expected evidence that suffix matching locates
  text but does **not** by itself identify a unique index entry.

IBM's machine-index description gives us the next independent check: a text
element is a three-byte element containing a text length and a displacement to
the actual text within the logical page. The diagnostic now groups distinct
tail locations by 512-byte storage page and scores candidate logical page sizes
(512 through 32768 bytes) by looking for plausible text elements that either
start exactly at, or cover, the observed key-tail bytes. Because the
page-header/trunk offset is still unknown, every possible byte alignment is
tested and the result is reported only as a score, not as a decoded pointer.

The first page-size score is useful but not yet decisive. In QGPL, raw exact
starts increase from 12 at 512-byte pages to 64 at 16384-byte pages, while
coverage remains high across several sizes. In PPSITEST, 512-byte pages cover
16 of the 20 distinct tail locations but produce no exact starts; 4096-byte
pages produce five exact starts while covering eight. Larger pages also create
more possible three-byte values whose displacement can fall within the page, so
raw hit count alone can favor them by chance.

There is a stronger structural discriminator available from the same
documentation: release-2 machine-index elements are three bytes. Even before we
know the header/trunk origin, candidate elements can be grouped by their offset
modulo three within a proposed logical page. Real tree elements should show
better **phase coherence** than arbitrary page data. The scorer now reports,
for each candidate page size, total exact/covering references plus the strongest
phase and its support.

The phase-aware rerun sharpened the result but also exposed a wrong
assumption in our comparison. QGPL's 512-byte candidate has strong phase-2
coherence (104 of 131 covering references), while PPSITEST's 512-byte candidate
has strong phase-0 coherence (15 of 16). PPSITEST's raw 4096-byte model has
three of five exact references in phase 1.

We should **not** require unrelated contexts to use the same logical page size
or segment-relative phase. IBM's machine-index implementation supports multiple
logical page sizes, and—more importantly—our current scorer has been treating
segment offset zero as logical-page origin even though the documented first
context segment contains YYSGHDR and EPA material before the machine index.

PPSITEST gives an additional structural constraint: its only recovered context
segment is exactly eight 512-byte storage pages (4096 bytes). A complete
4096-byte machine-index page cannot follow even the minimum known
YYSGHDR+EPA footprint inside that segment. The attractive 4096-byte exact-start
score is therefore best treated as a false-positive/raw-displacement effect
unless later documentation shows a different storage model.

The diagnostic now scans candidate **first logical-page origins** from the
minimum known header footprint (0x78) through the first 512-byte storage page,
with an 8-byte step by default and an optional one-byte exhaustive pass. For
each origin it rescans 512/1024/2048/4096-byte page models.

The real PPSITEST scan materially narrows the 512-byte model. The coarse pass
put origin `0x1E0` first, with 16/20 distinct known tail locations covered and
15 of those references in one modulo-3 phase; it also has two exact starts.
The exhaustive pass surfaced `0x105` and `0x0BD` with three exact starts,
but they cover only 7 and 10 tails respectively. Since our evidence is the
longest known **suffix** of a logical key, a valid text element is expected to
often begin before the observed suffix. Exact-start count is therefore a weaker
criterion than phase-coherent coverage. Origin ranking now reflects that.

This makes `0x1E0` the best current 512-byte PPSITEST candidate, not a decoded
fact. With that origin, the observed `FUNDDEF`, `ACCTDEF`, and `ADDFUND`
tails fall in logical page 3, while `PROTO` falls in logical page 4. The
`context-page` diagnostic now accepts a nonzero `--origin` and an arbitrary
element-stream phase so those specific pages can be inspected directly.

The targeted byte-level probe provides the structural confirmation we wanted.
Using the 512-byte page model, origin `0x1E0`, and phase 2:

- logical page 3 starts at segment offset `0x7E0`;
- the recovered `FUNDDEF` key tail at segment offset `0x865` is therefore
  page-relative `0x85`;
- the phase-2 element at page offset `0xCB` is raw `4A0085`, decoded by the
  documented release-2 element format as text length 74 and displacement
  `0x85`: an exact start reference to that known tail;
- the phase-2 element at `0xE3` is `5600C6` (length 86, displacement
  `0xC6`), whose text range covers the `ACCTDEF` tail at page-relative
  `0xD6`; another phase-2 element at `0x1B8` (`2B00C4`) also covers it;
- logical page 4 starts at segment offset `0x9E0`; its phase-2 element at
  `0x20` is `7C0002` (length 124, displacement `0x02`), covering the
  recovered `PROTO` tail at page-relative `0x5B`.

This is materially stronger than the earlier statistical scores: documented
three-byte text elements in one coherent phase now point into the independently
recovered key text at the expected page-relative locations. It does **not** yet
identify the page-header/root-node boundary or reconstruct a complete context
entry, so 512/origin-0x1E0/phase-2 remains a strongly supported PPSITEST working
model rather than an architectural constant.

That checkpoint has now been resumed. Ordinary root placement,
node/common-text traversal, same-segment page-pointer following, and compact
context-derived object references are validated across both real images.
Validated context references are now a second membership source in the browser;
the remaining structural work is exact page-header data-area semantics and any
nonzero segment-table-index pointer form that a future image exposes.

## First real context-tree traversal

Returning to this work after the QDDSI machine-index milestone produced the
first direct `context -> object` traversal.

### Ordinary small-context root placement

The earlier `0x1E0` page-origin scoring was useful for locating text evidence,
but direct tree walking exposed a stronger structure. In ordinary non-empty
eight-page `04/01` context segments, both real images independently place a
release-2 node at **segment offset `+0x800`**, followed immediately by page
type `0xCC`.

This is not being promoted to an architecture-wide constant for every context
size. It is, however, strongly reproduced for the ordinary eight-page context
population and is now the conservative default used by the first context
walker.

### Tree mechanics

Starting at `+0x800`, the same IBM-documented release-2 node mechanics already
validated for QDDSI work without alteration:

- node XOR displacement locates the two-branch cluster;
- common-text elements supply shared leading bytes;
- terminal-text elements supply the remaining bytes;
- text displacements are absolute low-16 segment offsets in these small
  one-segment contexts.

The initial walker stopped at page-pointer elements. Same-segment pointer
following has since been validated on larger contexts as described below.

### Independent V2R3 validation

On Mark's V2R3 image, 17 non-empty ordinary eight-page contexts traverse from
`+0x800` without a node/text structural warning. They yield **229 terminal
entries**.

For all **229/229**, the final six terminal bytes identify a recovered object
primary and the first two reconstructed bytes agree with that object's MI
type/subtype.

The six-byte object reference is observed as:

```text
2-byte segment extender
4 high bytes of the 48-bit object address
```

Appending two zero address bytes therefore reconstructs the page-aligned
eight-byte internal object address. Keep this as an observed compact context
reference until the exact period data-area definition is located.

### B10/PPSITEST validation and recovery value

Pete's surviving B10 disk provides the important partial-volume cross-check.
Across its ordinary small contexts the walker reconstructs **141 terminal
entries**; **80** point to object primaries that are present on the surviving
disk and all 80 type/subtype pairs agree.

For `PPSITEST` specifically, the tree contains **13 terminal entries**.
Six resolve directly to the six EPA-assigned recovered primaries already known
from the reverse direction.

Two additional terminals do something more useful: their compact references
point to object primaries that are absent, but surviving segment groups have
YYSGHDR owners exactly equal to the inferred addresses:

- `QDDSSRC / ADDFUNDD` member cursor candidate ->
  `00ED:001C35000000`;
- `QLBLSRC / ADDFUND` member cursor candidate ->
  `00EC:0005D9000000`.

That is the first concrete demonstration that the context index can recover
object identity/addressability that the EPA-primary inventory alone cannot.
The remaining unmatched PPSITEST terminals include `19/01 *FILE` candidates
whose primaries/owned groups do not survive on this disk.

### Larger-context page-pointer validation

Mark's V2R3 `QGPL` provides the first multi-page context traversal. Its
recovered 56-page primary context segment is assembled from four virtual-order
extents (8 + 16 + 16 + 16 pages). Starting from the ordinary root at
`+0x800`, the tree encounters 13 page-pointer elements.

All 13 have segment-table index zero. Their low field is in the same observed
256-byte units already validated for QDDSI, producing targets such as
`+0x0C00`, `+0x1000`, `+0x1800`, and `+0x4400`. Every target begins with
a release-2 node and a page-type byte; the secondary pages use `0x55` while
the trunk/root page uses `0xCC`.

Following those pointers, while carrying the accumulated common-text prefix
into the child page, reconstructs **165 terminal entries** with no structural
warning. That exactly equals the 165 QGPL objects previously assigned through
the independent EPA back-pointer direction.

All **165/165** terminal compact references resolve recovered object primaries,
and all 165 reconstructed leading type/subtype pairs agree with those objects.

This is the first complete two-way library-directory cross-check:

```text
object EPA -> QGPL context        165 objects
QGPL context -> compact object    165 objects
agreement                          165 / 165
```

It also validates one important generic page-header observation. The ordinary
QGPL trunk starts at `+0x800`; pointer targets fall on 1024-byte boundaries
from that base. The bytes immediately following each three-byte root node fit
the documented page-type position (`0xCC` trunk, `0x55` secondary). The
subsequent free-byte/first-free fields still are not assigned hard-coded
semantics until the missing data-area definition is located, because the trunk
can contain internal free regions and its raw free count need not equal only
the unused tail.

### Corpus-wide traversal and compact-name validation

The QGPL result generalizes across the recovered context population rather than
being a one-library special case.

Across Mark's independent V2R3 image:

- 40 permanent `04/01` contexts are recovered;
- their context trees yield **21,592 terminal entries**;
- **804** machine-index page pointers are encountered;
- every observed page pointer has segment-table index **0**;
- **21,531** terminals resolve a recovered primary with matching MI
  type/subtype;
- 61 references do not have a recovered primary, and 59 of those addresses
  still own one or more recovered secondary segment groups.

Across Pete's surviving B10 disk:

- 16 permanent `04/01` contexts are recovered;
- their trees yield **391 terminal entries**;
- **11** page pointers are encountered, again all segment-table index **0**;
- **206** terminals resolve surviving primaries with matching MI type/subtype;
- 185 directory references point to primaries absent from this disk, with 57
  of those inferred addresses still owning recovered secondary segment groups.

The current two-image corpus therefore supplies **815 real context page
pointers and zero nonzero-segment-table-index examples**. There is nothing
responsible to reverse-engineer for that form yet; support remains explicitly
deferred until another image provides a real specimen.

The physical terminal also exposes a highly reproducible compact name form.
For ordinary single-component object names, EBCDIC blank padding is represented
by `40 + positive-count`. The `0D/50 *MEM` key uses two fixed ten-byte name
components: the first component can use `40 + F6..FF` as an observed
two's-complement padding count, and the second uses a positive trailing blank
count.

A conservative decoder that handles only those two observed forms round-trips
the exact 30-byte EPA name for **21,715 / 21,737** resolved context terminals
across the two images. The remaining 22 Mark entries are special composite-key
object types and are deliberately left undecoded. On Pete's partial disk the
decoder also yields name hints for **all 185/185** directory references whose
primaries are absent.

That makes the missing-primary evidence directly useful. Examples include
ordinary `*FILE`, `*PGM`, and `*MEM` references such as
`PPSITEST/QDDSSRC(ADDFUNDD)` and
`PPSITEST/QLBLSRC(ADDFUND)`, even when no EPA primary survives.

### Browser integration

`ObjectInventory` now retains the reconstructed context-directory terminals
alongside recovered EPA objects. Recovered primaries preserve two independent
membership provenance fields:

- EPA back-pointer membership;
- one or more context-index memberships.

A unique context-index membership can supply the resolved library when the EPA
direction is absent. If the two directions disagree, the existing EPA
assignment is preserved rather than silently reconciled, while the conflicting
context evidence remains visible.

The curses browser now shows, for each library:

- total context-index entries;
- references resolved to recovered primaries;
- directory-only references;
- EPA/context agreement, EPA-only, context-only, and conflict counts;
- context traversal warnings.

Directory-only entries appear as a separate library group. Their detail view
shows the compact name hint when supported, type/subtype, inferred object
address, surviving owned secondary segments, and the raw terminal bytes.
Global browser search includes those directory-only names as well, so objects
known only from a surviving library directory remain discoverable on partial
images.

### Page-header prefix corroboration across both images

The first eight bytes of an in-use release-2 machine-index page can now be
treated more strongly than the earlier documentation-only description.

A corpus-wide pass over the 56 recovered permanent contexts visits **866**
in-use context pages:

- **51** trunk/root pages, all with page type `0xCC`;
- **815** page-pointer targets, all with page type `0x55`.

Across both images the physical prefix is reproduced at the same offsets:

```text
+0x00..+0x02   three-byte root node
+0x03          page type
+0x04..+0x05   documented free-byte value
+0x06..+0x07   documented first-free-byte low address
```

Those widths/positions are independently consistent with the already validated
QDDSI page parser, but the context result does not depend on QDDSI placement:
the context roots and all 815 child pages were located through the context
tree itself.

The exact accounting semantics of the two-byte free-byte value remain
deliberately conservative. Some real pages have internal free/tree-management
space, so `used tail + free_bytes` is not always a simple page-size identity.
Likewise, the bytes following `+0x07` still contain the documented
backpointer information/current-tree structures whose exact widths have not
yet been tied to an authoritative data-area definition.

The backend now exposes this validated eight-byte prefix as
`MachineIndexPageHeader` rather than continuing to leave all page-header bytes
opaque.

### Context page size, free space, and child backpointer area

A second corpus-wide pass over every page reached by the context walker narrows
the physical page layout further.

All **815** real page-pointer targets are aligned on 1,024-byte boundaries from
the ordinary trunk origin at `+0x800`, and every decoded first-free address
falls within that 1,024-byte page. Together with the 51 traversed trunk pages,
the current two-image context corpus therefore contains **866 independently
validated 1,024-byte in-use context pages**.

The documented free-byte and first-free fields have a reproducible relationship:
on all 866 pages, the total free-byte value is at least the unused tail from
first-free through the end of the 1,024-byte page. The excess is retained as
**non-tail free space** rather than being assigned an undocumented allocator
meaning. This explains why treating `free_bytes` as simply "bytes after
first-free" failed on some pages.

Child page type `0x55` has a six-byte area immediately after the common
eight-byte prefix:

```text
+0x00..+0x02   root node
+0x03          page type = 0x55
+0x04..+0x05   total free-byte value
+0x06..+0x07   first-free low address
+0x08..+0x0D   six-byte backpointer area
+0x0E...       current-tree storage
```

The six bytes are preserved as three raw 16-bit words. Their exact field names
remain unresolved, but their structural role is no longer speculative. When
the first and third words are expanded in the parent page, **770/815** child
pages produce a valid parent `(origin-node, current-node)` traversal state.
For **768/815**, that pair is exactly the immediate node state containing the
page pointer. The exceptions are important: IBM documents the backpointer as
the state used to resume a search in the parent after a child page is exhausted,
so it must not be mislabeled as merely "the page-pointer source."

The middle 16-bit word is still unresolved. Ordinary examples are often small,
while some real system contexts contain substantially larger values. Until a
data-area definition or an independent behavioral correlation is found, the
backend exposes all three words only as raw backpointer evidence.

Trunk page type `0xCC` has no corresponding six-byte child-backpointer area;
its current-tree storage can begin immediately after the common prefix at
`+0x08`. This is reproduced by the reachable-tree layout in 48/51 non-empty
trunks. The backend now exposes the validated 1,024-byte context page size,
tail/non-tail free-space accounting, child backpointer bytes, and observed tree
storage boundaries without assigning names to the unresolved words.

### What is still deliberately unresolved

The terminal byte stream is **not** being forced into the documented expanded
logical `T S NL N @` representation. The ordinary compact address and name
forms are now independently validated enough for conservative browser hints,
but the 22 special V2R3 composite-key terminals remain raw. Their separators/
control bytes need their own documentation or repeated structural evidence
before being named.

Likewise, the exact widths/semantics of the bytes after the root node and page
type in the physical page header remain open. The new evidence establishes a
reproducible root boundary and a working one-segment tree traversal, not the
complete generic page-header data area.

## Real-image validation plan
Once the documentation model is firm:

1. Start with a small, well-known recovered library such as QGPL.
2. Locate candidate index header/trunk signatures inside its recovered
   `04/01` segment.
3. Decode one page without following pointers and reconstruct candidate keys.
4. Compare candidate object names/types with objects already assigned to QGPL
   through EPA context back-pointers.
5. Repeat against a second context and, where feasible, the second real image.
6. Follow page pointers only after the one-page model is reproducible.
7. Use context-derived membership to classify currently unresolved objects.

The strongest success criterion is agreement between two independent
directions:

`object EPA -> context`

and

`context machine index -> object`.

## TUI status

The browser now exposes the context-directory evidence directly:

- membership source: context index, EPA back-pointer, or both;
- disagreement/incomplete-recovery warnings;
- recovered context entry count;
- unresolved/directory-only entries;
- surviving owned segments for a missing primary;
- compact name/type/address hints with raw-terminal fallback;
- documented library purpose from the editable library catalog.

This keeps the semantic browsing model useful while preserving the forensic
evidence behind it. Directory-only references are also included in global
search, which is especially useful on Pete's partial multi-disk image.
