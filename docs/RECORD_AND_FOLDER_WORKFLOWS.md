# Explicit records and folder anchors

This increment advances FILE (19/01), FMT (19/51), MEM (0D/50), QDDS
(0B/90), and FLR (19/12). It is part of the full 268-type program.

## Guided 5250 walkthrough

Launch `python3 as400_dasd_tool.py browse5250 /path/to/image.hda`.

1. Use `WRKMBRPDM FILE(library/file)`, select a member, enter **6 + Enter**.
2. Select **Raw bytes** or a specific format candidate. Duplicate candidates
   retain their FILE and FMT LBAs; no format is selected automatically.
3. Select a record to inspect raw bytes or individual decoded fields. Use
   **Next**, **Previous**, and **ALL/LIVE/DELETED/UNKNOWN** filters. Filters apply
   to the current 50-entry ordinal window, not a scan of the entire member.
4. Alternatively, `DSPFD FILE(library/file)` → format → **Records** → member
   retains that exact selected format. Out-of-record fields remain visible as
   mismatches. Back restores the previous selection.
5. Use **9 + Enter** on a member for existing storage-pointer navigation. This change
   fixes the curses key loop, which previously did not accept 9 despite model
   support. PR #21 alone still has that keyboard defect.
6. Use `WRKFLR FLR(*ALL/*)` → folder → **Source** to inspect anchor-key
   occurrences, or **Roots** to navigate the anchor graph independently of
   object identity. Open anchors, parents, children, and candidate DOC/FLR
   primaries. These paths are not certified QDLS paths.

The installer/uninstaller now include the capability, record, and anchor modules;
PR #21 omitted the capability module. Direct-checkout launching avoids that
older installation defect. An isolated text-mode install/import smoke test passes.

Both changes are in the Guided 5250 interface, not the older tape browser.

## Evidence and bounds

Record storage requires one exact direct QDDS pointer target and owner-matched
03B4 groups. Each group's 32-byte header is excluded. Reads use virtual extents,
cache sectors within a window, stop at gaps, reject overlaps, and bound entry
length to 64 KiB. Paging reads at most 50 entries. Ordinals start at the first
recovered group: absence of an earlier group is not independently disproved.
No index order, logical-file selection, live execution, or writable disk access
is implemented. 80/C0 remain live/deleted *hints*. Other statuses stay raw.

The chosen format is a user choice, not proof of ownership. Numeric bytes are
validated before decoding; unknown types and malformed numbers remain raw.
CP037 is a display lens, not a decoded CCSID. Field and record previews are
bounded and label truncation. A non-FMT object cannot be used as a schema.

The anchor graph requires a recovered WOSFMT14 corroborating all 15 observed
field ranges and a complete 193-byte QAOSSS14 member. It is bounded to 20,000
records. All 11 Mark WOSFMT14 descriptors corroborate WOSEFDOC as **20 bytes**
at one-based offset 112, correcting the older 12-byte assumption. None of the
1,885 original records uses nonblank bytes beyond the former 12-byte range;
a synthetic long name verifies the corrected boundary. Parent WOSEPLDN links
to a parent's leading key, which can differ from WOSEFILD.

Deleted/unknown anchors, duplicate identities, missing parents, and cycles are
retained. Key occurrences in the first 64 KiB of DOC/FLR primaries are candidate
associations only. A folder can contain many child keys: Mark's 1,781 candidate
associations across 24 folders do not mean 1,781 folder ownership links.

## Original-image validation

Both original archives were accessible and extracted with CRC validation before
development. Images remain mode 0444. Before/after SHA-256 matches are recorded
in `research/record_workflow_validation.json`; no private contents are included.
The pass used the recovered object inventory caches and freshly recovered
segment metadata. `tools/validate_record_workflows.py IMAGE` reproduces recovery
and validation from an image without requiring those caches.

| Check | Mark | Pete |
|---|---:|---:|
| Member cursors | 3,779 | 944 |
| Direct readers opened | 3,779 | 528 |
| First-window entries | 116,995 | 15,897 |
| Last-window entries | 40,132 | 5,514 |
| Storage warnings among opened readers | 0 | 0 |
| Original record UI walkthroughs | 3 | 3 |
| Explicit-format walkthroughs | 3 | 1 |
| Anchor records | 1,885 | source absent |
| Folder primaries | 24 | 4 |

Three bounded first windows per image matched the preexisting whole-stream
reader. Original model walkthroughs exercised record/raw/Back and format
identity; Mark also exercised folder/anchor/Back. Root selection is checked
against zero parent keys. Synthetic tests cover multi-group gaps/overlaps,
short reads, malformed numbers, ambiguous pointers, wrong schema types,
parent-key ambiguity/cycles, keyboard 6/9, and 80×24/64×16 rendering. These
are not a manual terminal acceptance test on the user's workstation.

## Concrete blockers and next capability work

- Pete: 91 cursors point to no recovered QDDS primary; 325 have no recovered
  owner-matched 03B4 groups. Inspect physical candidates/older-release storage
  layout before changing recovery. Evidence needed: a matching full internal
  address and compatible header, or a corroborated older storage mapping.
  Same-name substitution would hide this problem and is not used.
- Pete: four folders but no recovered QAOSSS14 member. A capture containing
  that member (or independently corroborated older anchor storage) is needed.
- Mark: three anchor paths have missing parents; 1,882 reach roots. Preserve
  the missing references; recover the corresponding leading keys to resolve.
- FILE/FMT and folder ownership remain unproven. Next compare format pointer
  candidates across duplicate FILE primaries and isolate folder self-key fields
  from child-key arrays, with negative controls. Do not promote occurrence to
  ownership without discriminating evidence.
- Continue the ranked type queue. If those structures remain blocked, advance
  index-key navigation (QDDSI/INX) or device configuration inspection with a
  useful Guided workflow. Fifteen types now have partial workflows; 253 remain
  queued. This PR does not complete the 268-type program.
