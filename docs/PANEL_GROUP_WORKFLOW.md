# Compiled CISC panel-group tagged symbol browsing

## Guided capability

Use `DSPPNLGRP PNLGRP(*ALL/*) NAME(CRT*) AT(0)` to select a recovered
19/15 `*PNLGRP` and inspect its saved **tagged compiled identifier
candidates**. The interface walks 32-KiB reconstructed virtual
windows (use Next/Previous or `AT(32768)` for the next window),
shows 50 symbol rows at a time, filters via a simple `NAME` glob,
and opens each candidate at its exact byte offset with tagged hex and
CP037-display text. A symbol of the form `COMMAND/PANEL` may
correlate by its text prefix to all recovered `*CMD` identities of
the same name; this is **not** an internal pointer or command invocation.
Duplicate/unassigned command primaries are separately selectable.

The supported empirical token shape is:
`13` + one unsigned byte specifying 4–40 bytes + exactly that many
EBCDIC-uppercase name-shaped bytes. The pattern is not a full UIM
compiled record parser; random opaque bytes may coincidentally pass
it, and symbols crossing a 32-KiB scan window boundary can be omitted.
The implementation does not claim actual panel labels, rendering,
UIM menu actions, execution rules, help fields or compiler metadata.

## Two-original-image evidence

Physical-read-only primary-signature census:

| Observation | Mark V2R3 | Pete B10 |
|---|---:|---:|
| Physical EPA primary candidates of type 19/15 | 513 | 234 |
| First four bytes at primary +0x100 | `00000100` (all 513) | `00000050` (all 234) |
| Candidates containing at least one tag-13/name-shaped sequence in the next physically adjacent 64 pages | 121 | 219 |
| Tagged name-shaped sequences in that same **physical** window probe | 12,224 | 32,579 |

The byte patterns include compiled slash-qualified labels such as
`CRTCLPGM/PGM` and `DSPLCLHDW/OUTPUT`. These are only examples
for study and do not prove runtime action membership. **Physical
contiguity is not virtual continuity**: large or duplicated candidate
counts can include unrelated adjacent physical data. The production
browser instead uses `read_range()` for gap-safe, address-ordered
virtual extents. Its full-image results can differ materially from the
physical exploratory totals above; do not quote these counts as valid
recovered compiled symbols.

Earlier documented V2R3/Pete tests found no direct padded ten-byte
PNLGRP-name matches within thousands of UIM-style menu primaries,
and a naive full-address-occurrence hypothesis also failed.
This new **PNLGRP-internal compiled literal browser** therefore
does **not** establish the missing MENU(UIM)→PNLGRP relationship.
It is an independently usable search/inspect/research workflow.

## Reliability and status

Synthetic tests in `tests/test_panel_group_workflows.py` exercise
both release-header variants, proper tag lengths, malformed names,
false positives, exact offsets, hex filter navigation, 50-row and
32-KiB pagination, missing/reordered virtual extents, same-name
command candidate duplicates, and Back. Unsupported headers and
requested offsets fail closed.

The opt-in `tools/validate_panel_groups.py <extracted-image.hda>`
uses the **normal recovered-object inventory**, checks available
virtual windows, follows saved symbol/Back navigation, reports
aggregate counts only, and verifies source SHA-256 before/after.
Do not claim full-image application validation until that script has
actually run on each original, not just the synthetic CI tests.

No original disk-image sectors, recovered application/private text,
proprietary manual pages, or credentials are committed. `*PNLGRP`
remains **partial**, not a completed UIM application or screen decoder.
The next decoding gate is evidence for the tag families, compiled
panel option tables and object-address relationships from applicable
period CISC interface manuals.
