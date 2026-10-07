# CISC AS/400 DASD Explorer - Active TODO

This checklist keeps implementation work separate from hypotheses. A checkbox is
only completed when the behavior is implemented and covered by tests or
repeatable real-image validation.

## Current priority

### QDLS / document-library reconstruction

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
- [ ] Resolve the three remaining QAOSSS14 records (RRNs 1883-1885) whose
      nonzero parent key has no matching leading key in the recovered
      QAOSSS14 record set. A `dlo-parent-gaps --raw-scan` diagnostic now
      locates those keys elsewhere in the raw image and classifies recovered
      containing objects for the next evidence pass.
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
- [ ] Decode the small set of large/extended `*DOCBSS` variants that fail the
      conservative ordinary-layout checks before treating export as universal.

## Permanent-context directory cross-check

- [x] Decode IBM's documented release-2 three-byte machine-index element
      primitives.
- [x] Add `context-page` forensic probing against recovered context segments.
- [ ] Locate the context machine-index page header and trunk automatically.
- [ ] Follow machine-index page pointers.
- [ ] Reconstruct front-end-compressed keys.
- [ ] Traverse context -> object entries.
- [ ] Cross-check context -> object results against EPA object -> context
      back-pointers.
- [ ] Use the context index to recover currently unresolved object membership.

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
- [ ] Parse QDDSI/data-space-index key specifications.
- [ ] Traverse the QDDSI machine index and present records in keyed order.

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
- [x] Add forensic `*PGM` browsing with owned-segment summary, printable
      strings, and a bounded hex/EBCDIC primary-segment preview.
- [x] Add a generic bounded raw-object fallback for object classes without a
      specialized decoder.
- [x] Add semantic `*USRPRF` / `*MSGQ` views with cautious same-name
      profile/queue correlation, owned-segment summaries, bounded EBCDIC text
      hints, and a raw fallback.
- [x] Add `*FILE` storage-evidence summaries (source member types, resolved
      formats, QDDS/QDDSI counts) so source/database/logical-access-path cases
      are described from recovered evidence rather than guessed from names.
- [x] Improve database-member presentation with recovered field layouts,
      DENT-byte terminology, and raw bytes when decoded fields are blank.
- [x] Explain the documented QGPL/QAAPFILE logical-file case instead of
      presenting its lack of independent QDDS rows as a generic recovery error.
- [x] Add contextual object/library explanations in the TUI.
- [x] Keep library/view, file/object-type, and member/object context visible
      simultaneously so an automatic child selection never hides its parent
      pane's meaning.
- [x] Make the lower Content/details pane follow the focused hierarchy level,
      so focusing a library or file shows its own full context even when a
      child is automatically selected.
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
- [ ] Add keyed-record navigation after QDDSI traversal is stable.
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
