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
- [ ] Locate `QAOSSS14` or its unresolved storage: IBM documents its anchor
      record as one of the places that stores each DLO's 10-character
      SYSOBJNAM, making it the highest-value QAOSS target.
- [ ] Locate/identify the other documented document/folder search indexes:
      `QAOSSS10`-`QAOSSS15`, `QAOSSS17`, and `QAOSSS18`.
- [x] Add a raw `dlo-schema` evidence scanner for `WOSFMTxx` /
      `QAOSS*` associations, including the observed `QAOSSS14` and
      `QAOSSY14` families, without guessing abbreviation meanings.
- [ ] Decode the binary descriptor fields and the relevant QAOSS record
      formats, or identify their unresolved storage objects if normal
      library/file recovery does not expose them.
- [ ] Map QDOC system object names (SYSOBJNAM) to user-facing DLO names.
- [ ] Reconstruct parent/child folder relationships and complete QDLS paths.
- [ ] Verify known examples such as PC Support folders/files against the
      reconstructed hierarchy.
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

## Browser and documentation

- [x] Add curses DASD browser.
- [x] Add contextual object/library explanations in the TUI.
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
- [ ] Show reconstructed QDLS paths in the TUI once QAOSS decoding is proven.
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
