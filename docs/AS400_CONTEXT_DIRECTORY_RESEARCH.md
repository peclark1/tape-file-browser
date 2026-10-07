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

### What remains unknown

The exact release-2 **page-header byte layout**, the precise location of the
trunk within a recovered V2R3 context segment, and the physical prefix/suffix
split for a context entry are not yet sufficiently documented/validated for us
to hard-code them.

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
release-2 page-header/trunk data-area definition, preferably in IBM's VMC data
area/module material. Do not infer those byte offsets solely from repeated
patterns in one image.

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
