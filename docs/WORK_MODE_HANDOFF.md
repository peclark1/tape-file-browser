# AS/400 CISC Guided 5250 Explorer — Work-mode handoff

**Purpose:** provide a durable, version-controlled technical handoff across normal chat, ChatGPT Work, future assistants, and Joe's testing. Read this file at the **start and end** of each substantial work session. Treat GitHub and verified source bytes as authoritative; this file is a navigation aid that must be refreshed when facts change.

**Status checked:** October 10, 2026 (US Central), against GitHub PR details. Verify live status before acting.

## Explicit records and folder navigation — October 10, 2026

Current work branch: `feature/explicit-record-explorer`, based on PR #21 head
`a6bdcbe4129efb5f2b27bd3e489bf4649522aa98`. Publication status is recorded below.
PR #21's `feature/type-capability-workflows` remains unchanged for user testing.
Main and Joe's stable version are untouched; no merge is authorized.

**Delivered:** member **6** → explicit format/raw choice → 50-entry windows →
record → fields, status filters, paging and Back; DSPFD → format → Records →
member retains the exact selected schema. Member **9** now reaches storage from
the actual curses key loop (PR #21 model supported it, but its key loop did not).
`WRKFLR` → folder → anchor source or roots → parents/children/candidate objects
adds a useful FLR workflow. The installer now includes all three workflow
modules, fixing PR #21's omitted capability module; an isolated installation
smoke test passes. WOSEFDOC's observed field width is corrected from
12 to 20 bytes, corroborated by all 11 recovered Mark WOSFMT14 descriptors.

**Validation:** 242 synthetic tests pass, including actual key-loop 6/9,
malformed/short records, virtual gaps/overlaps, explicit duplicate format
selection, invalid numbers, and anchor ambiguity/cycles. Compilation, shell
syntax, generated-report consistency and whitespace checks pass. Read-only
original validation opened 3,779 Mark and 528 Pete member readers; first and
last windows had no storage warnings. Three original UI record walkthroughs
and whole-stream comparisons per image pass; explicit schema walkthroughs
pass (3 Mark, 1 Pete). Mark's folder graph has 1,885 records, 1,867 parent edges,
1,882 paths reaching roots and 3 missing-parent paths. Both image hashes remain
unchanged and originals remain 0444. Aggregate results only are committed.

**Unresolved:** Pete has 91 cursors with absent QDDS primaries and 325 without
recovered owner-matched 03B4 groups. Its four folders have no recovered anchor
source. Record ordinals do not independently rule out missing initial groups.
Format and anchor key occurrences are candidate associations, not ownership.
CP037 is a display lens; 80/C0 are status hints. No live commands are executed.

See [workflow instructions, evidence and blockers](RECORD_AND_FOLDER_WORKFLOWS.md)
and `research/record_workflow_validation.json`. Capability progress is now
15 partial / 253 queued, independently of decoder maturity. The all-268 mandate
continues; a PR is a review checkpoint.

**Precise next steps:** incorporate the user's PR #21/TUI findings; inspect
Pete's missing storage targets using full internal addresses and older-release
header evidence; discriminate FILE/FMT ownership pointers and FLR self-key vs
child-key arrays using cross-object negative controls. If either is blocked,
advance ranked QDDSI/INX key navigation or device configuration with a complete
Guided workflow. Retain ambiguous/missing evidence rather than guessing.

## Active mandate and cross-type results — October 10, 2026

The accepted program is sustained material improvement across **all 268 documented
MI types**, using the ranked inventory as a queue. Command exploration is one
workstream. Research → implementation → Guided workflow → testing must continue
across type families; a commit/PR is a checkpoint, not program completion.
Generic browsing does not promote 268 types to decoded. This section supersedes
older command-only next-step instructions below.

Branch `feature/type-capability-workflows` is based on #20 at
`2cd7d0bdf6999717f649166e892f940c54690acb`. [PR #21](https://github.com/peclark1/tape-file-browser/pull/21) is open and ready
for review, targeting #20. Implementation commit
`943476c5b7d7a79790768e93ef962a7f3c16ffa1` passed
[GitHub Actions Tests run 38055836048](https://github.com/peclark1/tape-file-browser/actions/runs/38055836048).
The documentation-only publication follow-up leaves the tested implementation
unchanged; the PR head is the authoritative final revision.
Live startup review confirmed #15–#20 all open,
#15–#18 drafts; none merged. Main remains `bcf80ded77bdda86b57b5870bb1cd61c2d68810f`.
Joe's stable checkout is untouched. No merge is authorized.

**Delivered in this pass:** nine types have new or newly integrated Guided paths:
FILE, FMT, MEM, QDDS, QDDSI, TBL, DTAARA, DOC and DOCBSS.

- `WRKTYP` lists all catalog types plus recovered unidentified codes; Enter
  navigates recovered primaries. `WRKOBJ OBJ(*ORPHAN/*) OBJTYPE(*TBL)` searches
  otherwise hard-to-reach namespaces, retaining duplicate origins. Exact catalog
  names take precedence over wildcard interpretation. Unknown raw codes stay raw.
- `DSPFD FILE(library/file)` → every format candidate → selectable field
  descriptors. 5 on a file opens schemas; 12 retains member navigation.
- 9 on a member → exact QDDS/QDDSI pointer targets → layout/key specifications
  → reverse member references → 5 for content. No same-name pointer substitution.
- `DSPTBL TBL(*ALL/QASCII) HEX(C1C2C3)` → 256-byte map, sample result, individual
  byte evidence and collision inspection. HEX is an offline extension.
- `DSPDTAARA DTAARA(*ALL/*)` → selector-04 values by position, exact hex and
  CP037 display. Other selectors are withheld; no inferred numeric conversion.
- `WRKOBJ OBJ(QDOC/*) OBJTYPE(*DOC)` → all name-convention DOCBSS candidates →
  validated byte streams/ranges, including owner-matched contiguous continuations.
  Name matching is not claimed to be an ownership pointer.

**Evidence:** TBL and character DTAARA are new empirical partial decoders. The
other workflows reuse existing validated components with bounded virtual-extent
reads. New readers stop at gaps instead of shifting later bytes into the gap.
FILE format associations remain literal name/address evidence, not decoded FCB
fields; schema completeness and DOC companion ownership are not claimed.
Profile credential payloads remain excluded.

**Validation:** 228 synthetic tests pass, including new malformed/truncated/type
bounds, duplicate identities, exact pointers, continuation validation, UI Back,
keyboard/rendering and orphan isolation. Python compilation, shell syntax,
three generated-report sync checks and whitespace checks pass. Whole-image
recovery/validation runs completed on both originals, followed by real-image
navigation walkthroughs using the already-recovered inventory caches. These
walkthroughs caught and fixed exact *TBL selection; both images then passed
catalog/table/byte, file/format/field and member/storage/reverse/Back paths.
This is not a manual Tilix acceptance test on Joe's workstation.

| Observed result | Mark | Pete |
|---|---:|---:|
| TBL maps opened | 629 | 88 |
| Character DTAARA opened | 35 | 54 |
| DTAARA variants explicitly withheld | 2 | 0 |
| FILE primaries inspected | 1,343 | 942 |
| FCB format candidate links | 1,714 | 454 |
| FMT field descriptors | 13,786 | 4,077 |
| Exact member/storage links | 4,063 | 909 |
| DOCBSS streams validated/opened | 1,832 | 0 recovered |

Counts are normal recovery results, not physical EPA candidate or live-object
counts. Mark's normal recovery identifies 112 raw type codes, unlike the older
104-code conservative physical-signature survey; those different methods must
not be conflated. Aggregate-only results, sizes and unchanged hashes are in
`research/type_capability_validation.json`. No image or private value is committed.
Original files remain 0444 and hashes unchanged after all validation.

**Full queue:** `research/mi_capabilities.json` and generated
`docs/MI_CAPABILITY_PROGRESS.md` contain 14 audited partial workflows (including
five prior ones), 254 queued, zero universally completed. Queued means no audited
type-specific Guided outcome yet; it does not erase existing forensic decoders.
Binary inventory now has 30 reviewed types: 238 catalog-only, 12 identity,
6 evidence, 10 partial, 2 substantial. None means universally complete.

**Remaining issues and precise next work:**

1. Continue FILE/FMT/OIRS/QDDS/QDDSI: carry the user's explicit format selection
   into a selectable record view; do not silently choose the first name match.
   Start `as400_capabilities.py:CapabilityExplorer.file_rows` and existing
   `as400_dasd_tool.py:_resolve_format_fields` / `_tui_member_data_lines`.
2. Research MSGF ID/key → exact text records in virtual order, then MENU/PGM
   links, using the ranked queue. These are still queued, not newly declared
   blocked or completed by generic object browsing. Retain CMD nested QUAL/ELEM
   and value conversion experiments as a parallel queue item, not the whole scope.
3. DTAARA selector 03 (one Mark specimen, length-like word 15) and 84 (one,
   word 1) are specifically withheld. Known numeric/logical definitions and
   several corresponding values/display outputs would resolve storage/scale
   ambiguities. The program proceeded to DOC/DOCBSS instead of waiting.
4. DOC/FLR: use independently validated QDLS anchor/path relationships to
   navigate folders; replace companion-name conventions only with stronger
   evidence. Pete has no normally recovered DOCBSS samples to validate that path.
5. Keep iterating across remaining ranked families. Do not treat this review
   checkpoint or partial-workflow count as completion of the full inventory.

Reproduce with `python as400_dasd_tool.py browse5250 /path/to/image.hda` and
commands above. Original validation: `python tools/validate_type_capabilities.py
/path/to/image.hda`. Detailed bounds/source notes:
[TYPE_CAPABILITY_WORKFLOWS.md](TYPE_CAPABILITY_WORKFLOWS.md).

## Scope correction — October 10, 2026

PR #19 is an **intermediate keyword-browsing increment**, not completion of
Interactive Command Exploration. The user explicitly rejected stopping after
that increment. Continue research across related structures, integrate and test
real prompting/definition capabilities, or demonstrate a genuine blocker and
implement the next useful capability. Tests/commits/PR publication are gates,
not a reason to stop. Missing schema documentation alone is not a blocker.

A matching source/compiled-object/F4 triplet would strengthen validation, but
is NOT a prerequisite to testing pointer/boundary hypotheses using the available
images. No additional user permission is needed for the already authorized
read-only research, feature-branch implementation, testing and PR publication.
Main and Joe's stable checkout remain protected; do not merge without approval.

Continuation branch: `feature/command-prompt-links`, based on #19 at `9dd282f`.
The original session record below is historical and superseded by this correction.

## Continuation results — October 10, 2026

**Working capability delivered:** a navigable read-only prompt form with
per-parameter linked labels and display hints, tentative default/value tokens,
exact reference evidence, and Back restoring the selected prompt. Open
`DSPCMD CMD(QIWS/CPYTOPCD)`, select **Prompt form**, use arrows/Page keys and
Enter to inspect a parameter. The top heading distinguishes linked text from
candidate default/value meanings. No commands execute or values are editable.

This resolves the earlier prompt-link "blocker": testing relative references
on the existing images was sufficient to establish the empirical layout.
`as400_cmd.py:recover_definition_links` validates the ordinal descriptor chain,
a secondary chain, exact length-prefixed prompt records and bounded tag/length
attribute records. CPYTOPCD's secondary order ends TRNIGC, RCDFMT, while
stored ordinal order ends RCDFMT, TRNIGC. No modern ordering is imposed.
TRNIGC's blank historical prompt is preserved rather than invented.

**Validation:** 212 synthetic tests pass, including relocated references,
cycles, malformed/truncated records, incomplete lists, fragmented extent reads,
8 KiB cap and keyboard/rendering at 80x24 and 64x16. Compilation, shell syntax,
inventory/priority synchronization and diff whitespace checks pass. Full
original-image validator runs pass for Mark and Pete; hashes match the
previous session and remain unchanged after validation. 2,571 / 476 complete
keyword tables have validated primary descriptor chains; 13,851 / 2,889
nonblank prompt labels and 16,163 / 2,538 nonblank display hints are linked.
These counts are not unique live objects or proofs of complete semantics.

**Scope still unfinished:** type/translation semantics, definitive defaults,
complete choices/ranges/required flags, nested QUAL/ELEM, MSGF/CPP pointer
relationships, historical F4 behavior and Pete's identity inconsistencies.
The milestone has moved beyond keyword browsing; the entire roadmap is not
complete. The [prompt-link record](CMD_PROMPT_LINKS.md) gives exact structures,
negative tests, original-image findings and remaining experiments.

**Precise next work:** start in `recover_definition_links` tag 01/02 handling.
Follow both value references and conversion bytes for CPYTOPCD REPLACE and
TRNFMT, contrast CRTCMD MAXPOS binary/numeric cases, then establish subordinate
file/library qualifier ownership using explicit references. Do not wait for
external documentation before testing those relationships. Preserve candidate
labels until semantics are established. Keep scope-based acceptance checks;
PR publication and passing tests alone are not completion criteria.

Git: continuation branch `feature/command-prompt-links` targets #19's
`feature/interactive-command-explorer` at `9dd282f`. [PR #20](https://github.com/peclark1/tape-file-browser/pull/20) is open for review.
Implementation commit `03a2ad11eb0d66feee36e4c1220ecf1084c17132` passed
[GitHub Actions Tests run 38053877451](https://github.com/peclark1/tape-file-browser/actions/runs/38053877451).
A documentation-only follow-up records publication and corpus ordering counts;
the PR head identifies that final revision. PR #19's title/body now explicitly
mark it as intermediate and link #20. #15–#19 are still open and unmerged.
Main and Joe's stable checkout remain unchanged; no merges are authorized.

## Latest capability session — October 9–10, 2026

**Intermediate increment delivered (milestone unfinished):** an intentional safe subset
of historical command-definition recovery. Branch
`feature/interactive-command-explorer`, based on `feature/mi-full-corpus-survey`
commit `f3bb5394d3d9be9f426176ae459917ac4519c168`.
[PR #19](https://github.com/peclark1/tape-file-browser/pull/19) is open,
ready for review, targeting the #18 survey branch. Implementation commit:
`430b64e87b920b9bad46a6e46cc6bc4345b5707d`; this handoff publication adds a
metadata-only follow-up. GitHub Actions Tests run
[38024171555](https://github.com/peclark1/tape-file-browser/actions/runs/38024171555)
passed on the implementation commit. Main remains `bcf80ded`; no merge or
stable-checkout update occurred. Final PR head is the authoritative current
revision; no additional implementation changes follow the tested commit.

- `WRKCMD CMD(*ALL/CPY*)` searches all recovered *CMD identities, including
  unassigned primaries; duplicates retain library and LBA. `DSPCMD CMD(QIWS/CPYTOPCD)` opens the definition, as does Enter/5 in normal object
  navigation. Stored keywords are selectable; Enter shows field offsets,
  ordinal, origin and unknown attributes. Back restores the selected row.
- Summary includes recovery diagnostics and library-assignment provenance;
  Evidence retains unclassified text; PGM matches navigates matching recovered
  program identities without claiming a validated CPP pointer.
- Details wrap at ordinary terminal widths. F4 still selects implemented
  offline browser operations. No CL execution or editable parameter values.
- Selectively incorporated #15's decoder/tests/research, then added structured
  diagnostics, duplicate-keyword rejection, UI integration and regression tests.
  No pending branch was merged into main. #15 itself remains unchanged.
- Startup live review: #15–18 all open drafts, no submitted reviews, each head's
  PR-triggered GitHub Actions Tests run successful. Stack topology below holds.

**Validation:** 201 synthetic tests passed (`python3 -m unittest discover -s tests -v`), module compilation, shell syntax, both generated-report checks,
 and `git diff --check`. Frontend key-loop/rendering tests cover 80x24 and
 64x16; original-image model workflows cover CPYTOPCD (9), CRTCMD (27),
 ADDPFM (6), DSPCMD (2) on Mark plus unassigned ADDPFM (5) on Pete.
 This is not a manual test in Joe's Tilix environment.

Both ZIPs extracted successfully with CRC validation; original HDA sizes are
1,004,257,800 and 320,523,840 bytes. Extracted images are mode 0444, outside
Git, opened read-only; SHA-256 unchanged after full original-image validation.
Normal recovery found 3,118 / 1,098 commands, of which 2,571 / 476 have complete
empirical keyword sequences. Pete has 1,096 unassigned command primaries;
these are now reachable with `WRKCMD CMD(*ORPHAN/*)`. They are distinct from
physical-signature counts and do not establish active/consistent commands.

**Evidence and blockers:** keywords/count/ordinals are empirical partial
decoding; types/defaults/choices/prompts/CPP pointers and historical F4 order
remain unknown. Pete CPYTOPCD and CRTCMD have missing required ordinal slots.
Pete's library-assigned STRDFU primary contains CRTDUPOBJ-like payload clues;
it is expressly excluded as a semantically validated example. Exact LBAs,
offsets, negative evidence and required comparison inputs are in
[the capability record](INTERACTIVE_COMMAND_EXPLORATION.md).

**Next session:** start at `as400_cmd.py:recover_parameter_keywords`,
`as400_5250.py:Guided5250.explore_command`, and the capability record's
blockers. Test bounded descriptor/prompt pointer hypotheses against the available
virtual-order primaries. Seek a period-correct source/compiled-object/DSPCMD or F4
triplet as corroboration, not an assumed prerequisite. Separately compare Pete LBA 587728 EPA/context and
payload against another capture to investigate stale/reused/renamed storage;
do not rename it from text clues. Until that evidence exists, retain the
safe browsing workflow and prioritize user-tested navigation improvements.
Joe can reproduce with `python3 as400_dasd_tool.py browse5250 /path/to/marks.hda`,
then the WRKCMD/DSPCMD commands above. Opt-in whole-image checks are in
`tools/validate_command_exploration.py`; see capability record for exact commands.

## Repository and branch topology

- Repository: https://github.com/peclark1/tape-file-browser
- `main` includes Guided 5250 Explorer via merged PR #14. Its stable code should remain usable by Joe.
- [PR #15](https://github.com/peclark1/tape-file-browser/pull/15): `feature/cmd-parameter-evidence` **draft**, targets `main`. A separate experimental *CMD keyword/ordinal decoder, including the five-character `TOFLR` and `TODOC` strings. **Not incorporated into PRs #16–18.**
- [PR #16](https://github.com/peclark1/tape-file-browser/pull/16): `feature/mi-object-research-inventory` **draft**, targets `main`; 268-type inventory and documentation framework.
- [PR #17](https://github.com/peclark1/tape-file-browser/pull/17): `feature/mi-cmd-msgf-menu-pgm-research` **draft**, targets the #16 branch; documented command/message/menu/program relationships and two-image census.
- [PR #18](https://github.com/peclark1/tape-file-browser/pull/18): `feature/mi-full-corpus-survey` **draft**, targets the #17 branch; 268-type prioritized survey and complete physical-sector candidate census.
- **Stack order:** `main ← #16 ← #17 ← #18`; #15 is independent. Don't assume a checkout of `main` includes research in draft branches. Do not directly push experimental changes to `main` or merge pending PRs without review/approval.
- When implementing command enhancements that require #15 and survey foundations, deliberately create a new **capability branch** from the right source and integrate or cherry-pick relevant changes only after checking conflicts, tests, and current PR state. Do not blindly merge the entire branches together.

## Essential project facts

- App is a **read-only** GTK4/tape/browser and experimental CISC OS/400 DASD explorer, with terminal Guided 5250 mode via `as400-dasd browse5250 /path/to/image.hda` (or entry point verified in the checked-out README). Supports libraries, objects, members, records, source views, and evidence-labeled forensic screens.
- Historical CISC AS/400 sectors are **520 bytes physical**, usually comprising an **8-byte physical header** and **512-byte logical payload**. Reassemble object data through **virtual extents**, not an unsupported assumption of contiguous physical pages.
- IBM published 268 later-version MI catalog labels: **102 external and 166 internal**. **Not** all are certified to exist in V2R3.
- Initial survey decoder audit: **28 type-specific reviews**; **240 catalog-only**. Maturity labels distinguish object identity, unclassified byte evidence, partial decoding and substantial decoding; none claims a universal complete decoder.
- Surveyed two private HDA archives: Mark V2R3 (`marks.hda.zip`) and Pete B10 (`petes.hda.zip`). A conservative complete physical-primary signature survey observed **109 raw MI codes** across both (106 in the published later IBM catalog); **0E/00, 19/C4, 19/ED** remain unidentified. These are **physical candidate signatures**, not an inventory of live/context-confirmed objects.
- Mark: **1,931,265** 520-byte sectors, **20,271** candidate primary pages, **104** raw MI codes; Pete: **616,392** sectors, **7,570** candidates, **64** raw MI codes. **162 of the 268 names** had no signature match; this does not demonstrate absence.
- A local archive contains **17 AS/400 PDF manuals** plus a separate disk-storage Redbook (**18 PDFs**). The automated exact-token pass recorded **764** mentions covering **86** types. Automated lexical matches are **unverified leads**, distinct from manually verified PDF-page citations.
- `*CMD` main-branch viewer shows command identity and empirical printable-text/processor candidates. Draft #15 adds conservative structured keyword/ordinal evidence, NOT complete default/prompt/CPP pointer decoding.

## Source-of-truth files (on their indicated branches)

| Path | Why read it |
|---|---|
| `README.md` | User-facing operation and current entry points |
| `docs/MI_OBJECT_INVENTORY.md` | All 268 type names with audited maturity |
| `research/mi_object_reviews.json` | Implementation symbols, associated interfaces and programs, relationships with evidence qualifiers, next research steps |
| `research/manual_sources.json` | Local manual filenames and confirmed PDF page locations |
| `docs/MI_MANUAL_SCAN_FIRST_PASS.md` | Unverified 18-PDF lexical leads |
| `docs/MI_INTERACTIVE_OBJECT_RELATIONSHIPS.md` | Documented *CMD/*MSGF/*MENU/*PGM relationships and two-image evidence |
| `research/mi_full_image_census.json` | Aggregated full-image raw MI candidate counts, no raw records |
| `research/mi_lexical_type_coverage.json` | Per-type automated PDF name hits (not field descriptions) |
| `research/mi_survey_scoring.json` | Editable value/unlock/evidence/feasibility/coverage assumptions |
| `docs/MI_SURVEY_PRIORITIES.md` | All 268 preliminary research priorities |
| `docs/MI_FULL_SURVEY_V1.md` | Survey method, uncertainty and proposed workstreams |
| `docs/AS400_CMD_PARAMETER_RESEARCH.md` (**#15 branch**) | Experimental V2R3 parameter count/keyword/ordinal evidence |
| `docs/WORK_MODE_HANDOFF.md` | This continuity record: update after each work milestone |

## Development philosophy — accepted by user

**Capability-driven, not decoder-driven.** A substantial Work session should iterate through analysis → implementation → integration → tests → evaluation **until either** (a) an independently demonstrable improvement in the user's actual application workflow exists, **or** (b) a concrete blocker is documented and the effort pivots to the next best capability. Finding one byte offset, writing a research note, creating a PR, or passing a single test is not by itself the definition of done.

Use the 268-type inventory and scores as **research prioritization**, not a rigid alphabetical task list. Favor reusable infrastructure across object families. Avoid a polished but falsely decoded screen.

## Proposed first capability milestone: Useful Command Exploration

**User-visible goal:** In Guided 5250, open multiple recovered `*CMD` objects and browse a structured, read-only approximation of their command definitions, substantially more useful than today's flat EBCDIC string list. Preserve IBM's historic vocabulary and clear evidence qualifiers.

**Initial specimens:** `QIWS/CPYTOPCD` (9 observed V2R3 keywords including 5-character `TOFLR` and `TODOC`), `CRTCMD`, `ADDPFM`, `DSPCMD`, plus independent commands on another image where context-confirmed. Command parameters should be traversable in logical order with object origin and raw offsets accessible. Correlate prompt text, choice values, defaults, and processing-program/message-file names **only when structurally established**; otherwise clearly label unknown/unverified information. Nothing should execute.

**Useful acceptance checks:**

1. From normal Guided 5250 navigation, select a real `*CMD`, enter the improved command-definition view, browse parameters, and return/back out using consistent keys; terminal layout works at ordinary dimensions.
2. At least three independent representative commands are presented with correct independently validated parameter keyword counts and names where recoverable. `CPYTOPCD` visibly includes its 9 correctly spelled names, including `TOFLR`, `TODOC`, and `TRNIGC`; don't silently impose modern IBM i F4 field ordering on V2R3.
3. Distinguish *verified binary fields*, *correlated candidate clues*, and *unknown* in the interface. Do not misidentify a printable string as a verified parameter descriptor, default, or CPP pointer.
4. Preserve read-only guarantees, bounded offset/extent reads, corrupted/truncated-image behavior, and tests using synthetic data. Run the entire relevant automated suite and, where available, inspect a real image read-only. If original image bytes are inaccessible to Work, state that limitation and give reproducible test steps for the user's Ubuntu setup.
5. Update documentation and the inventory's maturity status only to the degree warranted by evidence. Include a short 'what the user can now do' demonstration in the PR.

**Escalation/pivot:** If message/prompt/CPP link structure cannot be reliably recovered after a reasonable evidence-driven exploration, write the exact blocker (sample/offsets/attempted methods/negative evidence/what input would resolve it). Deliver a safe usable subset of command browsing if possible; otherwise pivot to a visible file/member/record navigation enhancement. Do not call documentation-only progress a completed capability milestone.

## Safety and engineering boundaries

- **Never write or modify `.hda` images.** Prefer read-only opening and virtual-extent-aware reconstruction.
- Never commit the actual disk images, manual PDF payloads, original private account records, passwords, user-profile credential bytes, or large recovered proprietary source fragments.
- Avoid printing unbounded *USRPRF raw bytes; show only safe non-sensitive identities and independently established correlations.
- **Do not assume IBM API receiver layouts equal original CISC on-disk layouts.** Separate historic documented logical behavior, observed bytes, tentative hypotheses, and verified offsets.
- Unknown/undocumented MI codes must remain raw code values until independently identified; do not fabricate types or infer fields from adjoining numbers.
- Keep output deterministic; synthetic positive and negative tests; test incomplete images and duplicate names; preserve historical original-image immutability.
- Use a new capability feature branch/PR, working through substantial improvements before finishing; preserve coherent commits, link blockers and tests, and do not merge to main without authorization.

## Work-session startup checklist

1. Confirm access to the repository and this handoff; inspect `git status`, default branch, open PRs (#15–18), their dependencies, review state and current CI. Report any differences from the recorded state.
2. Read the current `README.md`, the inventory, survey, *CMD research, and test entry points from the correct feature branches. Inspect actual code before assuming earlier chat descriptions are current.
3. Set a **demonstrable user workflow** as the milestone and note baseline vs acceptance tests. Work over related components and iterate rather than stopping on an isolated discovery.
4. Check whether the two archival images and historical manuals are accessible in the Work environment. Their existence in the user's ChatGPT Project does **not** prove they are present on Work's computer; never pretend to test raw bytes that cannot be read.
5. Commit code and documentation to an appropriate **new branch**. Update this handoff with the final session state.

## Required end-of-session continuity record

Before ending a substantial Work session, update this file (or a link from it) with:

- **User-visible capability delivered:** exact before/after path through the app and example specimen names.
- **Git state:** base branch, feature branch, PR URL, last commit SHA, CI/test commands and results.
- **Evidence status:** which fields are verified, which are merely suggested by raw strings, and what remains unknown.
- **Blockers or pivots:** precise reason, objects/specimens tried, next proof/input needed and chosen alternative.
- **Next session starting point:** first file/function to inspect, specific next action, and how Joe/user can reproduce the new behavior.

Do not rely on a final chat summary as the only durable record. Update the version-controlled project handoff and reference it in the closing message.
