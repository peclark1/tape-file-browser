# AI coding/work-session orientation for AS/400 ZuluSCSI / Tape File Browser

**Read [docs/WORK_MODE_HANDOFF.md](docs/WORK_MODE_HANDOFF.md) first** before substantial AS/400 CISC DASD / Guided 5250 development. That document records the current milestone, feature-branch/PR topology, research sources, historical decoding caveats, evidence thresholds, tests, and the required end-of-session continuity update. Verify live GitHub state instead of assuming the document is always current.

## Non-negotiable engineering boundaries

- Original AS/400 disk/tape images are archival evidence: **read only**. Never commit original images, extracted proprietary manual pages, credential data, or private recovered content.
- Later IBM object-type catalogs and modern receiver APIs are *not* evidence of identical CISC V2R3 on-disk byte layouts.
- Clearly distinguish **verified binary fields**, **tentative string/offset evidence**, and **unknowns**. Treat physical EPA candidate counts as distinct from library-context-confirmed objects.
- Cover every new parser with bounds/short-input and malformed-record tests. Reassemble segmented primary data using virtual extents, not assumed physical contiguity.
- Keep `main` and Joe's stable checkout protected; check pending PR stack and work in an appropriate feature branch. Don't silently merge or delete branches.
- Deliver improvements by **user-visible capability**, continuing research + code + UI + tests through a meaningful workflow result or a documented blocker with a pivot. A research note or one extra metadata field is not itself completion.
- PR #19 keyword/offset browsing is an intermediate increment, not completion
  of command prompting. Test concrete structural hypotheses against available
  images before declaring a missing format description a blocker. If blocked,
  continue with a useful capability; report remaining scope honestly.
- Before the end of any substantial work session, update the living handoff with the delivered workflow, branch/PR, tests, verified vs unknown data, blockers and next steps.

## Full-inventory mandate

The accepted goal is material tool progress across **all 268 documented types**.
Use the ranked inventory as a continuing queue. For each type/family, research,
implement, integrate, test and evaluate a usable workflow, or record a concrete
blocker and proceed to another useful family. A completed increment, commit or PR
is a review checkpoint, not completion of this program. Do not repeatedly narrow
work back to *CMD. Shared navigation does not count as 268 completed decoders.
Track per-type workflow status independently of binary decoder maturity in
`research/mi_capabilities.json` and `docs/MI_CAPABILITY_PROGRESS.md`.

## Primary references

- [docs/MI_OBJECT_INVENTORY.md](docs/MI_OBJECT_INVENTORY.md): all 268 catalog types and audited decoder status
- [docs/MI_SURVEY_PRIORITIES.md](docs/MI_SURVEY_PRIORITIES.md): full research ranking and two-image coverage
- [docs/MI_FULL_SURVEY_V1.md](docs/MI_FULL_SURVEY_V1.md): high-level survey methodology
- [docs/MI_INTERACTIVE_OBJECT_RELATIONSHIPS.md](docs/MI_INTERACTIVE_OBJECT_RELATIONSHIPS.md): CMD, MSGF, MENU, PGM research
- [docs/WORK_MODE_HANDOFF.md](docs/WORK_MODE_HANDOFF.md): active capability milestone and continuity

Read the source and tests rather than relying exclusively on README summaries.
