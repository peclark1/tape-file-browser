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

## TUI implications

When context traversal is reliable, the browser should be able to explain more
than just a library's friendly description. Useful evidence to show includes:

- membership source: context index, EPA back-pointer, or both;
- disagreement/incomplete-recovery warnings;
- recovered context entry count;
- unresolved/dangling context entries;
- documented library purpose from the editable library catalog.

This keeps the semantic browsing model useful while preserving the forensic
evidence behind it.
