# AS/400 CISC Guided 5250 Explorer — Work-mode handoff

**Purpose:** provide a durable, version-controlled technical handoff across normal chat, ChatGPT Work, future assistants, and Joe's testing. Read this file at the **start and end** of each substantial work session. Treat GitHub and verified source bytes as authoritative; this file is a navigation aid that must be refreshed when facts change.

**Status checked:** October 9, 2026 (US Central), against GitHub PR details. Verify live status before acting.

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
- Current initial decoder audit: **28 type-specific reviews**; **240 catalog-only**. Maturity labels distinguish object identity, unclassified byte evidence, partial decoding and substantial decoding; none claims a universal complete decoder.
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
