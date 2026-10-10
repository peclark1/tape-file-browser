# Archived subsystem and class name evidence

These read-only workflows are bounded candidate-name navigation, **not**
decoded OS/400 subsystem/class membership or a live subsystem simulator.

## Guided usage

- `DSPSBSD SBSD(*ALL/*)` — list all recovered subsystem descriptions, preserving duplicate library/physical origins. Open a subsystem for independently recovered matching `*JOBQ`, `*CLS` and `*PGM` names appearing as exact ten-byte, EBCDIC-space-padded sequences in its contiguous recovered virtual primary bytes.
- `DSPCLS CLS(*ALL/*)` — open a recovered class and navigate backward to subsystem primaries containing its exact name as a ten-byte occurrence.
- Enter/5 selects an evidence-qualified candidate, F12/Back restores the selection. Page windows are limited to 50; searches to the first 16 KiB per primary. Unrecovered virtual gaps truncate reads instead of stitching unrelated sectors.

A source `*SBSD` often contains its own name at +0x327 (and other offsets). These **self-name echoes are counted separately and withheld** from the candidate link list, because a self-name occurrence is not independent evidence of a job-queue or class link.

## Cross-image observations

Both originals were scanned physically read-only for candidate `19/09`
primaries; the physical primary candidate census found **15 Mark V2R3** and
**4 Pete B10** candidates. Bounded sample bytes showed ten-character
EBCDIC names of recovered JOBQ/CLS/PGM primaries occurring at several offsets
in Mark's subsystem objects. A system-wide subgroup of SBSDs contains its
own padded name near +0x327. The Pete sample also exhibits saved self-name
occurrences. These are *physical primary candidates*, not a certified
complete set of recovered or active subsystems.

Every displayed object candidate must exist independently in the recovered
inventory, with its original name, type, library and primary LBA. We do
**not** decode field identifiers at the occurrence positions; overlapping
ten-byte literals might be coincidence or stale configuration. Matching
class/job-queue/program identity does not prove runtime class assignment,
queued jobs, an initial program, library-list resolution, or actual internal
address references.

The current code never writes disk data. The source primary search is
bounded by 16 KiB and the first virtual gap. It does not consult profile
passwords or users' credentials. No actual recovered text, names, contents,
credentials, or raw image fragments are committed in synthetic tests.

## Next investigations

Use period CISC/System/38 subsystem/configuration references to locate and
verify actual record-table boundaries, slot types, qualified names and
direct/indirect pointers. Validate across both images with explicit negative
controls, rather than promoting ten-byte occurrences to binary pointers.
Test on the real terminal as a separate acceptance step. Advance JMQ/LDA,
PNLGRP and other queued types independently when the structures remain
unresolved.

See `research/mi_capabilities.json` for separate partial-workflow statuses
for `*SBSD` and `*CLS`.
