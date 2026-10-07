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

## Documentation still needed

Before naming more fields, find the strongest available IBM documentation for:

1. permanent context semantics and MI operations on contexts;
2. release-2 machine-index page header/trunk layout;
3. logical machine-index page size and page-pointer interpretation;
4. front-end/common-text key compression;
5. leaf/entry representation for a context mapping object name/type to an
   object/system pointer;
6. whether the context index format differs from the documented generic
   machine-index format in any release-specific way.

If our attached manuals do not contain that detail, broaden the search to the
appropriate IBM AS/400 MI or System/38 architecture manuals and clearly label
that as outside-source research.

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
