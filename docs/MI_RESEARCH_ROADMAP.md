# AS/400 CISC MI object decoder research roadmap

**Scope:** Read-only forensic recovery of OS/400 CISC object structures on
archived DASD images; preservation and interpretation, NOT an AS/400 emulator.
The IBM type names in the published external/internal tables identify 268
MI combinations; they are **not** a claim that every type is present on
either image or was available in a particular OS/400 release.

## Foundation established

- The authoritative IBM names/categories remain in the two existing TSV
  files at the repository root. Do not fork these into a second, stale
  list of type names.
- research/mi_object_reviews.json stores **audited overrides** keyed by
  four-digit MI code. Every type absent there is **Catalog only**.
- research/manual_sources.json inventories the 18 available historical
  PDFs. Indexed filenames are not treated as inspected contents.
  Manually verified PDF page references are recorded separately.
- docs/MI_OBJECT_INVENTORY.md is the reproducible 268-type overview.
  Run: python3 tools/mi_object_inventory.py --check-report
- The inventory script can also emit --format json or --type-code 19/05.
  Decoder and manual evidence remain separate from the IBM type catalog.

The maturity statuses are mutually exclusive:

| Status | Required evidence |
|---|---|
| Catalog only | IBM catalog name; no type-specific decoding audited |
| Identity | Common EPA/type/name recovery, no decoded payload fields |
| Evidence | Specialized viewer / string / pointer correlation, provisional |
| Partial | Independently corroborated type-specific fields or relationships, with tests |
| Substantial | Important type-specific structures and workflows recovered across specimens; not necessarily complete |

There is deliberately **no fully decoded state** in this first audit. None
of the existing object decoders is established as complete on all releases.

## Manual/research workflow

1. Select a type by actual image presence, practical value, and dependency
   impact. Never assume a cataloged modern IBM i type existed in V2R3.
2. Review indexed historical manuals. For each finding record document ID,
   **1-based PDF viewer page**, release/date (if established), precise
   claim, and whether it is a logical interface or documented binary layout.
   Preserve exact IBM terminology. Do not conflate a command/API receiver
   field with a permanent on-disk offset.
3. Map logical relationships to other types, commands, APIs and processing
   programs. Mark each relationship **documented, observed, or tentative**;
   avoid assuming two same-named objects share a pointer.
4. Select two or more *independent* recovered specimens, ideally across
   Mark's V2R3 and Pete's older B10 images. Distinguish a primary page
   candidate from a live context-resolved object. Store aggregate evidence
   and byte offsets; do not commit original object bytes.
5. Isolate structural hypotheses with strict bounds, version gates,
   pointer validation, corruption-negative cases and read-only I/O.
   If the evidence conflicts, show unknown rather than fabricate fields.
6. Add an evidence-labeled decoder and 5250/forensic display. Separate
   verified attributes from raw hints and explicitly expose undecoded
   fields.
7. Add unit tests with **synthetic** data, run whole CI, and human-test
   on a real image before promoting maturity. Update implementation and
   sources in the review registry; regenerate the 268-type overview.
8. Request review/merge when stable, preserving main while experiments
   live on feature branches.

User profile rule: do not dump, catalog, or export credentials, password
material or arbitrary unverified *USRPRF bytes in a general-purpose report.
The dedicated viewer deliberately avoids raw profile sampling.

## Initial workstreams (dependency-first)

### A. Core storage and database metadata

- *LIB 04/01 — substantially decoded context/library membership and
  machine-index traversal; investigate nonzero segment-table references.
- *MEM 0D/50, *FILE 19/01, *QDDS 0B/90, *QDDSI 0C/90,
  *FMT 19/51 — improve pointer/key/format variants and fragmented
  storage; these foundations unlock many other file/object analyses.

### B. Interactive system definitions

- *CMD 19/05 — on main: command identity/title and empirical clues.
  Draft PR #15 adds validated candidate ordinal/keyword sequences,
  but **does not** decode parameter types, defaults, or prompts.
- *MSGF 0E/03 — recover referenced message/prompt text, message IDs
  and lookup semantics before claiming relationships to command
  keywords.
- *MENU 19/16 — correlate menu object, display file, message file,
  and program references from period manuals. Recreate only read-only
  informational navigation.
- *PGM 02/01 — investigate MI program template, ODT and instruction
  decoding as a separate major milestone; do not interpret *CMD
  metadata as executable MI.

### C. Configuration and communications

- *DEVD 10/01 — validate candidate device class/type/model triplet,
  then controller pointers through period-correct DSPDEVD/CRTDEV*.
- *CTLD 12/01, *LIND 11/01 — research controller/line descriptions
  so the *DEVD viewer can show a genuine recovered topology.
- *MODD 15/01 — establish V2R3 APPC/APPN mode parameters through
  documented interfaces and cross-command specimens.

### D. Security, queues, and communications

- *USRPRF 08/01, *INTPRF 0E/C4, *MSGQ 19/02 — safely
  validate ordinary, non-secret metadata and separately observed links.
- *JOBQ 0E/01, *OUTQ 0E/02, *DTAQ 0A/01, journal and receiver
  types — establish index/entry storage models and preserve unknowns.

### E. Document/OfficeVision storage

- *DOC 19/0E, *FLR 19/12, *DOCBSS 06/C1 — complete the
  QAOSS index relationships and validate workstation stream length/
  export handling against additional originals.

## Documentation indexing — transparent progress

The supplied archive contains 17 PDFs, and the disk-storage Redbook is
the 18th source. Four selected PDFs have **initial page-level manual
reviews**, covering object roles, command-processing program concepts,
security/communications setup, and disk-object metadata. The remaining
14 are inventoried **but not yet reviewed**. These are research leads,
not claims of documentation coverage for all 268 types.

Next documentation pass:

1. Inspect IBM CISC System Builder / V1R2–V3R6 reference and the
   contemporary installation/service manuals for precise release
   terminology, MI/device/storage context and dates.
2. Index historical *CMD/*PGM, *FILE/*MEM, *DEVD/*CTLD, *MODD and
   *USRPRF chapters/commands by PDF page. Collect associated commands
   and program references only when directly supported by text.
3. Review the remaining published type names, prioritize types found in
   the recovered images, and distinguish absent from not-searched.
4. Preserve separate evidence logs for OS/400 V2R3, the B10 corpus,
   V5R4 IBM API references, and current IBM i catalog tables.

**Do not treat automated lexical PDF hits as verified citations.** A hit
is only a pointer to a page for human confirmation. OCR-less PDFs and
pages with extraction defects must remain unindexed/unverified rather
than being guessed.

## Coordination with Joe and PRs

This inventory branch does not merge or supersede draft PR #15. Once
the foundation is reviewed and merged, keep each object-family decoder
on its own PR. Joe can use the same inventory to see source evidence,
decoder maturity, remaining blockers and exact validation criteria.

The source inventory is version-controlled but the disk images and
full historical PDF/manual payloads remain out of the public GitHub repo.
