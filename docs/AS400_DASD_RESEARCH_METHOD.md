# CISC AS/400 DASD research method

This project is both a recovery tool and a historical systems-research project.
For each major subsystem or object class, use a documentation-first,
evidence-driven workflow rather than decoding bytes in isolation.

## 1. Documentation survey first

Before changing a decoder, identify the best sources we already have for the
structure, function, and normal use of the thing being studied.

Prefer, in roughly this order:

1. IBM architecture / Machine Interface / System/38 internals documentation.
2. IBM release-appropriate OS/400 manuals and service documentation.
3. IBM Redbooks and system-builder material.
4. Period operator/programmer books for user-visible terminology and examples.
5. Later IBM documentation when it clearly describes an inherited concept.

Record the release/architecture applicability. A later RISC or V4 description can
supply terminology and concepts without proving a V2R3 CISC byte layout.

## 2. Separate three kinds of knowledge

Every research note and decoder should distinguish:

- **Documented** — explicitly described by a source.
- **Observed** — repeatable evidence in one or more real images.
- **Hypothesis** — a proposed interpretation that still needs corroboration.

Do not promote an observed offset or bit to an architectural field name merely
because it behaves plausibly.

## 3. Understand function as well as layout

The goal is not only to parse structures. Capture enough documented operational
context to explain what the object/library/file does and how OS/400 uses it.

When useful, surface that context in the TUI so browsing a recovered system also
teaches the user what the selected item represents. Keep the evidence status
visible when a description is inferred or research-pending.

## 4. Validate structure against real media

After the documentation pass:

1. derive the smallest testable structural expectations;
2. compare them against the independent V2R3 image and the surviving B10 image
   when the structure should be architecture-level;
3. preserve representative regression fixtures;
4. add bounded forensic/raw views when semantics are incomplete;
5. only then promote the interpretation into a normal semantic decoder.

## 5. Cross-check independent directions

Prefer bidirectional or independent checks. Examples:

- EPA object -> context back-pointer versus context index -> object entry;
- sector-header extent reconstruction versus permanent/static directory data;
- file/member metadata versus QDDS/QDDSI storage;
- object-internal relationship pointers versus name-based correlations.

A decoder is much stronger when two independent structures agree.

## 6. Keep research notes with the code

For each substantial subsystem, keep a short note under `docs/` containing:

- sources consulted;
- documented terminology and behavior;
- observations from real images;
- unresolved questions;
- implementation implications;
- TUI/context information worth exposing.

This prevents rediscovering the same evidence and makes later interpretations
auditable.
