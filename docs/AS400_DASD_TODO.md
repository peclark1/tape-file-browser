# CISC AS/400 DASD Explorer - Active TODO

This checklist keeps implementation work separate from hypotheses. A checkbox is
only completed when the behavior is implemented and covered by tests or
repeatable real-image validation.

## Current priority

### Permanent-context directory reconstruction

The functional database/QDDSI keyed-record milestone is now complete and the
permanent-context work resumes as the current architectural priority. Apply the
same documentation-first discipline before naming page-header fields; use the
validated QDDSI machine-index traversal as implementation guidance without
assuming that context indexes use identical placement or control structures.

### Database / QDDSI and keyed-file reconstruction — milestone checkpoint

Ordinary, multi-page, and multi-DKEY recovered V2R3 access paths now enumerate
keyed terminal references and resolve their database-relative addresses to the
appropriate QDDS RRNs. The eight long/compact QAOK variants retain partial tree
key evidence while still providing complete DKEY/ordinal references. See
`docs/AS400_QDDSI_RESEARCH.md`.

- [x] Inventory the existing backend: member cursors (0D/50) already resolve
      same-named QDDS (0B/90) data spaces and optional QDDSI (0C/90) index
      objects; decoded QDDS records and MI 19/51 formats are already available.
- [x] Record the operational distinction supported by the available IBM
      documentation: database records and access paths are separate enough for
      access paths to be journaled and rebuilt independently. Treat the later
      V4-era documentation as semantic corroboration, not proof of the V2R3
      QDDSI byte layout.
- [x] Revisit PPSITEST/ACCTDEF and PPSITEST/FUNDDEF. Direct 0D/50 cursor
      pointers prove that both had QDDS data spaces even though the QDDS
      primaries are absent from Pete's surviving disk. Their recovered 02A4
      second segment groups point back to those missing QDDS objects, so
      "QDDSI present + QDDS absent => logical file" is no longer a valid
      inference for a partial multi-disk image.
- [x] Attempt the QDDSSRC/ACCTDEF and QDDSSRC/FUNDDEF semantic cross-check.
      Their QDDS primary metadata survives, but their 03B4 source-record data
      segments do not. PDM PF-DTA identification plus direct QDDS pointers and
      the recovered field tables provide the stronger physical-file evidence.
- [x] Inventory the first QDDSI structures. The cursor directly identifies
      QDDS/QDDSI; the QDDSI DKEY area identifies the indexed QDDS and points to
      a DKYT; DKYT field lengths/record locations match recovered 19/51 formats.
- [x] Locate period documentation: System/38 VMC manual SY21-0889-5 documents
      data-space second-segment field tables, DKEY/DKYT key specifications,
      use of the general machine index, key conversions, and the appended
      database-relative-address/ordinal suffix.
- [x] Add a conservative DKEY/DKYT decoder that exposes data-space pointers,
      key counts/lengths, and raw DKYT field attributes/locations without
      naming unresolved bits. The ordinary real-image layouts parse across both
      images; joining field rows to friendly 19/51 names remains the next UI
      step.
- [x] Traverse ordinary single-page QDDSI machine-index roots and emit user
      keys plus the observed four-byte RRN/ordinal reference. DBUUSERS
      reconstructs `*PUBLIC` -> RRN 1; QAEASTUL and QASNADSQ validate
      common-text plus nested XOR node traversal; multi-field QAO1CVNP
      reconstructs six 4-byte user keys whose bytes exactly match QDDS RRNs
      1-6.
- [x] Follow ordinary same-segment QDDSI machine-index page pointers
      (`segment_table_index == 0`, page-offset field in 256-byte units). Real
      multi-page V2R3 indexes now traverse exactly: QACJINFO 36/36,
      QAQAATPY 99/99, QAEBAUDL 584/584, and QADBXDIC 2615/2615 keys,
      with each recovered four-byte ordinal set forming exactly `1..N`.
      Nonzero segment-table-index pointers remain deliberately unresolved.
- [x] Surface documented access-path/key context and recovered keyed-order
      evidence in the CLI/TUI while retaining arrival/RRN order and raw/partial
      diagnostics for undecoded indexes.
- [x] Join DKYT field locations/lengths to friendly recovered 19/51 field
      names when the match is exact; retain raw field evidence otherwise.
- [x] Follow the observed QDDSI active-root pointer instead of assuming a
      fixed +0x1000 root. On Mark's V2R3 image the 110 non-empty indexes use
      +0x1000 (102), +0x1800 (7), and +0x2800 (1).
- [x] Decode mixed-key-shape multi-DKEY indexes by matching the ordinary
      four-byte database-relative address back to its zero-based DKEY row and
      reconstructing user-key bytes around documented fork/control rows.
- [ ] Decode the eight remaining long/compressed-key QDDSI variants
      (QAOKLAKA, QAOKLDKA, QAOKL10A, QAOKS01A, QAOKS02A,
      QAOKS03A, QAOKS04A, and QAOKS05A) before treating keyed traversal as
      universal. Their tree entry counts are recovered, but complete machine
      keys are represented indirectly/compressed.

### Permanent-context directory reconstruction — active checkpoint

The next architectural milestone is to reconstruct each permanent
context/library's own directory and use it as an independent
`context -> object` view. Before decoding a structure, survey the available
period documentation for its purpose, terminology, and externally visible
behavior; keep documented facts separate from real-image observations and
hypotheses. See `docs/AS400_DASD_RESEARCH_METHOD.md` and
`docs/AS400_CONTEXT_DIRECTORY_RESEARCH.md`.

- [x] Survey the current manual set for object/library, single-level-storage,
      and storage-directory terminology. Record the important distinction
      between the storage-management **permanent directory** (virtual-address
      to DASD mapping) and a permanent **context/library machine index**
      (object namespace).
- [x] Locate strong IBM System/38 VMC documentation for context semantics,
      the logical context-entry format, and the release-2 machine-index
      binary-radix-tree element model.
- [x] Recover IBM's documented logical-page header field **names and order**
      from the System/38 machine-index material/patent family: in-use pages
      carry root node, page type, free-byte count, first-free-byte offset,
      backpointer information, and current tree; free pages carry page type,
      free-chain count, and next-free-page pointer. Expose this context in
      `context-page` without guessing field widths or byte offsets.
- [x] Establish the first eight bytes of the in-use release-2 page header by
      independent real-image corroboration: +0x00 root node (3 bytes), +0x03
      page type (1), +0x04 free-byte value (2), +0x06 first-free low address
      (2). Across both images 51 context roots are type 0xCC and all 815
      pointer-target pages are type 0x55. The backend now exposes this prefix
      conservatively as `MachineIndexPageHeader`.
- [x] Establish the context-specific 1,024-byte logical page size and the
      physical child-page boundary: type-0x55 pages carry six backpointer bytes
      at +0x08..+0x0D and current-tree storage begins at +0x0E; type-0xCC
      trunks can begin tree storage at +0x08. All 866 traversed context pages
      validate first-free within the page and total free bytes >= unused tail.
- [x] Separate the child-backpointer encoding by image/release evidence.
      Mark V2R3 uses (origin-low16, shared-high16, current-low16): 770/804
      child pages reconstruct a valid parent node-state pair and 768 are the
      immediate pointer state. Pete's older B10 image uses a different rotated
      48-bit virtual-address form (word2:word3:word1), with 7/11 references
      landing on recovered parent-tree nodes.
- [x] Explain the remaining backtracking/resume-state exceptions at the
      architectural level. IBM's published machine-index traversal describes
      child-page backpointer information as the state used to return to the
      parent page and resume processing, so it need not equal the incoming
      page-pointer source node. Preserve the release-specific V2R3/B10 raw
      encodings rather than forcing one layout.
- [ ] Locate authoritative data-area field names/exact release-specific
      backpointer encoding (ideally SY21-0892 or equivalent) before assigning
      names to the three raw two-byte words.
- [x] Add `context-xref`, a read-only diagnostic that correlates objects already
      assigned through EPA back-pointers with the documented logical context
      entry form `T S NL N @` and reports raw address/name-entry occurrences
      without assuming compressed entries are contiguous.
- [x] Run the first `context-xref` pass on Mark/Patrik `QGPL`. The
      primary 56-page context segment contained only 3/165 object-address
      hits and no contiguous `N+@`/full entries; this exposed that the first
      diagnostic was incorrectly scanning only the primary segment group.
- [x] Update `context-xref` to search every recovered segment group owned by
      the context and report locations as `segment VA + offset`.
- [x] Re-run Mark/Patrik `QGPL` across all three context-owned segment
      groups (69 pages total). The hit count remained 3/165, ruling out the
      primary-only scan as the reason for the low match rate.
- [x] Test the literal `base + 0x20` interpretation of IBM's "EPA header
      address" wording on both images. It matched 0/165 QGPL objects and 0/6
      PPSITEST objects, while raw base/object addresses matched 3/165 and 1/6.
      Do not label +0x20 as the documented `@` encoding.
- [x] Add key-side evidence scanning: exact `T+S+NL+N` plus the longest
      contiguous key suffix above a configurable threshold. This follows IBM's
      documented common-text/terminal-text compression model and avoids relying
      on unresolved `@` semantics.
- [x] Re-run Mark/Patrik `QGPL` and B10 `PPSITEST` with key-tail
      evidence. QGPL produced >=5-byte key tails for 92/165 EPA-assigned
      objects; PPSITEST produced 6/6. Duplicate suffixes can map multiple
      candidate objects to the same raw text location, so a tail hit alone is
      not treated as a unique decoded entry.
- [x] Add 512-byte storage-page clustering and candidate logical-page-size
      scoring. The scorer uses IBM's documented three-byte text element
      (length + page displacement) and tests whether plausible text elements
      point to or cover the observed key tails without assuming header/trunk
      alignment.
- [x] Re-run the two contexts with page clustering/reference scoring.
      PPSITEST concentrates all 20 distinct tail locations in two 512-byte
      storage pages; QGPL shows broader clusters. Raw page-size scores are not
      decisive: PPSITEST has 0 exact starts at 512/1024/2048 but 5 at 4096,
      while QGPL's raw exact count rises with larger page sizes.
- [x] Add element-phase scoring (element offset modulo 3 within each candidate
      logical page). This discounts some chance three-byte values: a real
      release-2 element stream should show stronger alignment coherence than
      arbitrary data even while the page-header/trunk origin is unknown.
- [x] Re-run QGPL and PPSITEST with phase-aware scores. QGPL's 512-byte
      model is strongly phase-coherent (104/131 covering references in phase 2);
      PPSITEST's 512-byte model is also strongly coherent (15/16 in phase 0),
      but the phase differs. The 4096-byte PPSITEST exact-start score is not
      sufficient by itself to select a page size.
- [x] Add a primary-segment page-origin scan. It tests candidate machine-index
      starts from the minimum known YYSGHDR+EPA footprint (0x78) through the
      first 512-byte storage page and scores 512/1024/2048/4096-byte models.
      This addresses the major flaw in treating segment offset zero as logical
      page zero.
- [x] Run both coarse and exhaustive origin scans on B10 `PPSITEST`. For
      512-byte pages, origin `0x1E0` preserves the strongest suffix evidence:
      16/20 distinct tails covered, 15 in one modulo-3 phase, with 2 exact
      starts. Exhaustive scanning also finds origins with 3 exact starts but
      much weaker coverage; because the known evidence is only a key suffix,
      coverage is the more appropriate primary ranking signal.
- [x] Rank page-origin candidates by phase-coherent suffix coverage before
      exact-start count, and teach `context-page` to accept a nonzero logical
      page `--origin` plus any three-byte element phase.
- [x] Probe PPSITEST's 512-byte candidate at origin `0x1E0`, phase 2.
      The real page-3 stream contains `4A0085` at element offset `0xCB`
      (text length 74, displacement `0x85`), exactly targeting the recovered
      `FUNDDEF` key-tail location. Additional phase-2 elements cover the
      `ACCTDEF` tail, and page 4 contains `7C0002` at offset `0x20`
      (length 124, displacement `0x02`) covering the `PROTO` tail at
      `0x5B`. Preserve 512/origin-0x1E0/phase-2 as a strongly supported
      PPSITEST working model, not yet a full page/trunk decoder.
- [x] Resume context traversal and independently establish the ordinary
      small-context root boundary. Non-empty eight-page 04/01 contexts on both
      real images place a release-2 root node at segment +0x800; the first
      conservative walker follows nodes/common text/terminal text without
      assuming the unresolved page-header field widths.
- [x] Validate context -> object references independently. Mark's V2R3 image
      yields 229/229 small-context terminal entries whose compact six-byte
      references resolve recovered object primaries with matching MI type/
      subtype. Pete's partial B10 disk yields 141 terminals, 80 direct-primary
      matches, and PPSITEST additionally identifies two missing primaries through
      surviving owned secondary segment groups.
- [x] Follow and validate context machine-index page pointers in a larger
      context. Mark's 56-page QGPL context follows 13 segment-table-index-zero
      pointers to same-segment child pages and reconstructs exactly 165 terminal
      entries; all 165 resolve the same recovered objects/type-subtypes as the
      independent EPA back-pointer direction.
- [ ] Decode/follow nonzero context segment-table-index pointers when a real
      example is isolated. A corpus-wide pass over both images now covers 56
      recovered contexts, 21,983 terminal entries, and 815 page pointers; all
      815 observed pointers use segment-table index zero, so there is currently
      no specimen from which to infer the nonzero form.
- [x] Promote validated context-derived references into an independent
      library-membership source. ObjectInventory preserves EPA and context-index
      provenance separately, uses a unique context-only membership when the EPA
      direction is absent, and retains disagreement evidence rather than
      silently reconciling it.
- [x] Surface directory-only context entries in the TUI. Missing primaries can
      retain type/subtype, compact address, ordinary/member name hints, surviving
      owned-segment evidence, and raw terminal bytes; global search includes
      these directory-only names.

### QDLS / document-library reconstruction (follow-up cleanup)

- [x] Recognize QDOC `19/0E` as `*DOC` and `19/12` as `*FLR`.
- [x] Add TUI context explaining QDOC versus ordinary source/database libraries.
- [x] Add `as400-dasd dlos` to inventory recovered DLOs and surface printable
      metadata hints without claiming they are authoritative QDLS names.
- [x] Identify QUSRSYS `QAOSS*` files as the IBM-documented search indexes
      that track DLOs; `dlos` reports recovered runtime candidates when present.
- [x] Distinguish those QUSRSYS runtime indexes from the recovered QSYS DLO
      command model files (`QAOSIQDL`, `QAOSIRTV`, `QADSPDOC`,
      `QADSPFLR`) and expose their recovered field definitions.
- [x] Add `dlo-xref` to search recovered object segments for byte-level
      references to a 10-character QDOC SYSOBJNAM without assuming structure.
- [x] Run direct V2R3-image probes for known objects such as
      `FMPV082760`, `FMPV195818`, and `DPWN524712`; preserve the
      resulting correlations in the QDLS research notes.
- [x] Locate `QUSRSYS/QAOSSS14` and its complete recovered storage set on
      the V2R3 image: `*FILE` 19/01, `*MEM` 0D/50, QDDS 0B/90, and
      QDDSI 0C/90.
- [x] Locate the complete documented V2R3 document/folder search-index set:
      `QAOSSS10`-`QAOSSS15`, `QAOSSS17`, and `QAOSSS18`, including
      their recovered *FILE/member/QDDS objects where present.
- [x] Add a raw `dlo-schema` evidence scanner for `WOSFMTxx` /
      `QAOSS*` associations, including the observed `QAOSSS14` and
      `QAOSSY14` families, without guessing abbreviation meanings.
- [x] Decode the V2R3 `WOSFMT14/QAOSSS14` descriptor offsets/lengths and
      the corresponding 193-byte QDDS record layout while preserving unknown
      IBM field abbreviations verbatim.
- [x] Correlate QDOC objects to QAOSSS14 anchor records through the observed
      8-byte `WOSEFILD` value embedded in recovered QDOC bytes.
- [x] Reconstruct QAOSSS14 parent links when a `WOSEPLDN` value uniquely
      matches another record's **leading 8-byte key**. This corrects the
      earlier assumption that the parent key always matched `WOSEFILD`.
- [x] Verify the PC Support hierarchy independently. In these records the
      anchor names also match the known user-facing QDLS components:
      `FMPV082760 -> QIWSFLR/CKPCSPTH.EXE` and
      `FMPV195818 -> QIWSFL2/DTAQ.PKG`.
- [x] Resolve the BULLET1/BULLET2/BULLET3 parent anchor: their `WOSEPLDN`
      points to QAOSSS14 RRN 1870 by its leading record key. RRN 1870's
      anchor short name is `QGFSWOF1`; the independently observed
      user-facing folder name remains `BULLETIN`.
- [x] Resolve the apparent QAOSSS14 parent gaps at RRNs 1883-1885 as deleted
      historical rows rather than live hierarchy failures. All three have the
      validated deleted DENT form 0xC0 and their shared parent key has no live
      leading-key anchor; deleted rows remain available for forensic display.
- [ ] Determine the semantics of the remaining WOSFMT14 binary/field values;
      do not expand identifiers such as `WOSEFILD`/`WOSEPLDN` from their
      spelling alone.
- [x] Identify MI `06/C1` as IBM `*DOCBSS` (Document byte string space)
      and correlate `FMPV082760F` / `FMPV195818F` companions with their
      same-base QDOC documents on the real V2R3 image.
- [x] Decode the ordinary V2R3 `*DOCBSS` payload boundary: one 512-byte
      metadata page followed by the workstation byte stream, with observed
      duplicate 16-bit payload-length fields at +0x106/+0x112.
- [x] Add conservative read-only `dlo-export` for `*DOCBSS` objects whose
      duplicated lengths agree and fit the recovered segment/allocation.
- [x] Decode the validated overflow `*DOCBSS` family: when the duplicated
      payload length exceeds primary capacity, owner-matched contiguous 0F90
      segment groups continue the stream after their own first 512-byte metadata
      page. CLI/TUI export now consumes only the continuation bytes required by
      the declared payload length.
- [ ] Classify the remaining unusual `*DOCBSS` layouts before treating export
      as universal; do not concatenate auxiliary 0F90 segments when the declared
      payload already fits in the primary.

## Permanent-context directory cross-check

- [x] Decode IBM's documented release-2 three-byte machine-index element
      primitives.
- [x] Add `context-page` forensic probing against recovered context segments.
- [x] Locate the ordinary small-context machine-index root/trunk at +0x800
      by independent cross-image validation; exact generic page-header field
      widths remain unresolved.
- [x] Follow same-segment (segment-table-index-zero) machine-index page
      pointers in larger contexts; QGPL validates 13 pointers and 165/165
      context-derived object references.
- [ ] Decode/follow nonzero segment-table-index context page pointers when a
      real example is isolated; neither real image contains one among the 815
      context page pointers recovered so far.
- [x] Reconstruct node/common-text/terminal-text paths in ordinary small
      contexts.
- [x] Traverse ordinary small context -> object compact references.
- [x] Cross-check context -> object results against EPA object -> context
      back-pointers on both real images.
- [x] Demonstrate recovery of unresolved object membership/addressability:
      PPSITEST terminals identify two missing member-cursor primaries whose
      inferred addresses own surviving secondary segment groups.
- [x] Integrate context-index membership into the browser inventory model and
      expose EPA/context provenance plus directory-only missing-primary entries
      in the TUI/search workflow.

## Database decoding

- [x] Recover QDDS fixed-length ordinal entries.
- [x] Decode standard 92-byte source physical-file records.
- [x] Recover MI `19/51` field descriptors.
- [x] Decode verified character, binary, zoned-decimal, and packed-decimal
      fields.
- [ ] Decode additional verified MI `19/51` field types.
- [ ] Refine FCB -> format resolution for logical and multiple-format files.
- [ ] Decode the data-space entry-status byte beyond preserving its raw value.
      IBM documents flags for valid/deleted/cross-segment-boundary states, but
      the bit assignments still need independent confirmation.
- [x] Parse QDDSI/data-space-index DKEY/DKYT key specifications and preserve
      unresolved attributes as raw values.
- [x] Traverse ordinary QDDSI machine-index roots and same-segment secondary
      pages in keyed order; preserve nonzero segment-table-index pointers as
      unresolved evidence rather than guessing their target segment.
- [x] Join DKYT key fields to friendly recovered 19/51 format-field names in
      CLI/TUI presentation when offset/length matches are exact.

## Storage-directory / recovery internals

- [ ] Identify static/permanent directory objects.
- [ ] Parse ASDE/extent descriptors directly as an independent check of the
      header-based recovery map.
- [ ] Improve permanent/temporary sector-header indicator decoding.
- [ ] Reduce dependence on structural corroboration for ambiguous candidates.

## Program object / MI decoding

IBM documents enough of the original-program-model/non-bound MI architecture to
make a real MI disassembler a realistic goal. The remaining hard part for this
offline disk browser is recovering the correct program-template representation
from the encapsulated on-disk *PGM object and matching the instruction encoding
to this CISC release.

- [x] Add bounded forensic *PGM browsing (owned segments, EBCDIC strings,
      hex/EBCDIC primary-segment preview).
- [ ] Identify the program-template / observability components stored in a real
      V2R3 CISC *PGM object and compare them with IBM MATPG materialization
      formats.
- [ ] Decode the documented program-template header and component offsets.
- [ ] Decode ODT/ODV/OES entries so instruction operands can be typed and
      symbolized rather than displayed as raw indexes.
- [ ] Build a release-appropriate MI opcode/form table from IBM's AS/400
      Machine Interface Functional Reference and, if useful, the system's own
      QPROCT instruction table.
- [ ] Add an MI instruction-stream disassembler with branch/entry-point labels
      and typed ODT operands.
- [ ] Add control-flow/basic-block reconstruction and a conservative
      MI-pseudo-source view.
- [ ] Use BOM/debug/observability information when present, but do not imply
      that original RPG/COBOL/CL source names or control structures can always
      be reconstructed.

## Browser and documentation

- [x] Add curses DASD browser.
- [x] Redesign the mature DASD TUI around the recovered object model without
      replacing the proven three-pane navigation: add a persistent breadcrumb
      plus Summary/Data/Keys/Storage/Evidence/Raw inspector views.
- [x] Promote directory-only context terminals into normal per-library MI-type
      groups beside recovered objects while retaining explicit `[dir]`
      provenance markers and context-only/conflict evidence.
- [ ] Make navigation-list ordering identity-first rather than recovery-state-first:
      sort mixed file/member/object/directory entries by logical AS/400 name,
      use recovery state only as a secondary tie-breaker, and remove plain
      "recovered" as if it were a completeness grade. Reserve compact markers
      for exceptional states such as `[dir]`, `[ctx]`, member-only/partial,
      and evidence conflict `!`.
- [x] Add forensic `*PGM` browsing with owned-segment summary, printable
      strings, and a bounded hex/EBCDIC primary-segment preview.
- [x] Add a generic bounded raw-object fallback for object classes without a
      specialized decoder.
- [x] Add semantic `*USRPRF` / `*MSGQ` views with cautious same-name
      profile/queue correlation, owned-segment summaries, bounded EBCDIC text
      hints, and a raw fallback.
- [x] Preserve the real B10 `JHUDGINS` observation that the `19/02 *MSGQ`
      EPA+0x38 internal address resolves exactly to the owning-object address of
      the recovered same-name `08/01 *USRPRF`; expose it as an observed link
      without assigning an undocumented field name.
- [ ] Compare recovered `*MSGQ` object storage with IBM MI `MATQAT`
      (Materialize Queue Attributes) semantics: queue type, current/maximum
      message count, extension value, key length, and maximum message size.
      Do not assume the MATQAT materialization layout is the on-disk layout.
- [x] Add `*FILE` storage-evidence summaries (source member types, resolved
      formats, QDDS/QDDSI counts) so source/database/logical-access-path cases
      are described from recovered evidence rather than guessed from names.
- [x] Improve database-member presentation with recovered field layouts,
      DENT-byte terminology, and raw bytes when decoded fields are blank.
- [x] Explain the documented QGPL/QAAPFILE logical-file case instead of
      presenting its lack of independent QDDS rows as a generic recovery error.
- [x] Add contextual object/library explanations in the TUI.
- [x] Keep library/view, file/object-type, and member/object context visible
      through the navigation panes plus breadcrumb so an automatic child
      selection never hides its parent hierarchy.
- [x] Make the lower inspector follow the focused hierarchy level, so focusing
      a library or file shows its own view even when a child is automatically
      selected; separate human-facing summary/data from storage/evidence/raw
      forensic views.
- [ ] Add an in-TUI help/guide page (for example `?` or `h`) that explains
      the screen layout, navigation panes, breadcrumb, inspector views, and
      context-sensitive keys without requiring the README.
- [ ] Include a concise terminology glossary in TUI help for recovery-specific
      concepts such as recovered primary/object, directory-only `[dir]`,
      context-index-only `[ctx]`, evidence conflict `!`, QDDS/QDDSI, DENT,
      member cursor, context/library, keyed versus arrival/RRN order, and raw
      forensic views. Keep definitions evidence-aware so "recovered" means
      what the browser actually proved or reconstructed rather than implying
      the entire original object necessarily survives.
- [x] Add validated `*DOCBSS` workstation-file export to the TUI with
      explicit destination prompting and overwrite confirmation.
- [x] Move library descriptions to editable `as400_libraries.json`.
- [x] Seed the catalog with every library recovered in the current Mark-P02
      file/member inventory, marking uncertain entries explicitly.
- [x] Add functional subsystem categories and documented/inferred/research-pending
      evidence status to the library catalog, and expose that context in the TUI.
- [ ] Resolve the remaining uncertain library identities, especially `#DBULIB`,
      `QSDE`, and the exact role of `QSYSV2R2M0`, before promoting them to
      documented status.
- [ ] Move MI object-type descriptions to a similarly editable/researchable
      catalog if the list grows enough to justify it.
- [x] Show uniquely reconstructed QAOSSS14 QDLS names/paths in the TUI while
      retaining the internal QDOC SYSOBJNAM for forensic identity.
- [x] Add keyed-record presentation after QDDSI traversal became stable,
      retaining arrival/RRN order as an independent view and labeling partial
      key evidence explicitly.
- [ ] Consider GTK integration only after the read-only CLI/TUI data model is
      stable.

## Research discipline

For every new interpretation:

1. Prefer IBM documentation for structure and terminology.
2. Validate against at least one real image; use both real images when the
   structure should be architecture-level.
3. Label observations and hypotheses separately.
4. Do not assign names to unknown bits or fields from pattern matching alone.
5. Keep all DASD access read-only.
