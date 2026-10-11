# Saved CISC 0E/09 alert-table keys and message-definition references

## Guided 5250 workflow

Use `DSPALRTBL ALRTBL(*ALL/QPQMSGF) MSGID(PQT*)` to select a
recovered alert-table primary. The explorer traverses supported saved
release-2 machine-index keys in 50-key windows, filters exact raw
`KEYHEX(C3)` prefixes or candidate `MSGID(PQT*)` strings, and
opens each 12-byte key with its original byte offset, hex and CP037
display lenses.

The **empirical** key structure is 12 bytes: the first byte can be a
`C` tag (`C3` CP037); the next seven bytes can then be an exact
seven-character message identifier; the **four trailing bytes remain
opaque**. Other key prefixes, especially `D`-tagged entries, are
retained for byte inspection but never guessed to be message IDs.

When a `C`-prefixed candidate exists, the viewer reports recovered
`*MSGF` primaries with the same name as the alert table. It then
checks each candidate's actual supported 44-byte MSGF index
independently. **Only if an identical seven-character message ID is
present** does the explorer expose a navigable message-definition
record action. Selecting that action opens the established
`MessageExplorer` with its separate exact-owner storage checks:
literal CP037 text may appear where verified; compressed and
unavailable storage remains explicitly opaque or missing.

A matching table/file name by itself does **not** prove linkage.
Even an exact MSGF ID match does **not** prove a live alert was
sent, an action occurred, or that any of the four trailing bytes
contain a valid binary pointer. No saved alert or message is executed.

## Independent read-only two-image evidence

Both archive copies contain two physical EPA signature candidates for
0E/09, with names `QCPFMSG` and `QPQMSGF`. Supported observed
header controls at primary +0x100..+0x105:
`60 00 00 0C 00 08`. A six-byte root absolute address is stored
at +0x420 and a four-byte page-size value at +0x42A.

| Physical-contiguous primary probe | Mark V2R3 | Pete B10 |
|---|---:|---:|
| Saved page size | 2048 | 1024 |
| `QPQMSGF` reconstructed 12-byte keys | 41 | 41 |
| C-tagged `QPQMSGF` seven-character message ID candidates | 26 | 26 |
| `QCPFMSG` reconstructed 12-byte keys | 2,708 | Not recovered by physical adjacency |

All 41 `QPQMSGF` keys on both releases were found **byte-identical
and in the same tree order**, despite different saved index page sizes.
The remaining fifteen keys are D-tagged variants. On Mark, independent
physical-contiguous index decoding of its `QPQMSGF *MSGF` yielded
295 valid 44-byte message entries, including **all 26** C-tagged
alert ID candidates. The seven-character ID comparison is exact.

Pete's physical-contiguous `QCPFMSG` alert index and sampled
`QPQMSGF` message-file index did **not** support complete tree
reconstruction, potentially due fragmented virtual extents. No
conclusion of missing historical alerts, absent messages or invalid
OS/400 object is justified. The production explorer uses properly
ordered recovered **virtual extents**, strict tree bounds and
distinct missing/unsupported warnings.

These numbers describe **physical signature and adjacency probes**,
not full recovered-app validation. They are kept separate from
normally recovered object counts and TUI acceptance results.

## Reverse navigation from saved message definitions

The existing `DSPMSGD MSGF(*ALL/QPQMSGF) MSGID(PQT*)` message
record-detail viewer now uses the same cached alert-key index for
its **reverse** link: after selecting an independently decoded
message definition ID, the screen lists matching `C`-tagged
saved alert-table terminal keys with that exact seven-character
ID and the same recovered *object name*. Select a saved alert key
to inspect its original 12 bytes, then Back to return to the
selected message definition.

This reverse view remains available when the MSGF 0280 text/record
storage is unavailable on Pete's earlier image: selected message
ID/index evidence alone suffices for the tentative alert-key match.
Unreadable alert roots are counted and withheld rather than silently
treated as no alert. All duplicate alert origins are retained and a
50-key display cap provides a `DSPALRTBL` filtered follow-up.

The forward and reverse views are **exact saved ID correlations only**.
Neither direction proves a historical alert action, owner pointer,
rule activation or message delivery.

## Tests and evidence gates

`tests/test_alert_table_workflows.py` covers both page sizes,
relocated roots, exact 12-byte terminal bytes, D/non-C keys,
bad headers and damaged page bounds, no or mismatched saved MSGF
ID, corroborated exact ID to established MSGF record viewer, and
select/detail/Back navigation. No original HDA bytes or private
message text are stored in the synthetic tests.

`tools/validate_alert_tables.py <extracted-original.hda>`
builds the production recovered inventory, reuses per-MSGF exact
ID sets, checks current saved tree roots, exercises 5250
navigation and Back, prints **aggregate counts only**, and
verifies original SHA-256 before and after. The one-pass combined
validator `tools/validate_recent_workflows.py` also includes
`*ALRTBL`, now the fourteenth recent type under acceptance.

**Neither validator has yet been run to completion against the
original HDA files in the complete production recovered model**.
Synthetic CI and independent physical-sector audits do not substitute
for that gate. The type remains **partial** until period CISC
message/alert control structures, the C/D variants, unknown trailing
four bytes and record ownership can be established independently.
