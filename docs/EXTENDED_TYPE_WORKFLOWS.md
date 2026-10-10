# Message, index, configuration, menu and directory workflows

This is a checkpoint in the continuing 268-type program, not its completion.
All commands below are offline Guided 5250 operations. Nothing executes on OS/400.

## What to try

| Workflow | Guided path | What remains unresolved |
|---|---|---|
| Program reference exploration | `DSPPGM PGM(*ALL/name)` -> CMD/P-menu candidate -> definition | Not a call graph; CPP pointers, ODT and instructions remain unknown |
| Saved message references | `DSPMSG MSGQ(*ALL/*)` -> compound reference -> matching MSGF ID | Entry boundaries, active state, chronology and delivered text are unknown |
| Job relationships | `DSPJOBD JOBD(*ALL/*)` -> queue -> referring descriptions; `WRKJOBQ JOBQ(*ALL/*)` | Name-based references, not active job state |
| Message descriptions | `DSPMSGD MSGF(*ALL/QIWSMSG) MSGID(IWN*)` -> ID -> First/Second | Compressed text, substitutions, ancillary attributes, older text-storage layout |
| Database keys | Member 9 -> QDDSI -> Browse keyed entries -> key -> candidate member record -> raw bytes | Partial key materialization, missing initial record groups; RRN remains a hint |
| Configuration | `DSPDEVD DEVD(*ALL/*)` -> device -> controller -> line; also DSPCTLD/DSPLIND | Full-address occurrences are candidates, not certified active attachments |
| Menus | `DSPMNU MENU(*ALL/ASSIST)` or `DSPMNU MENU(*ALL/PCOMNU)` -> target candidate | Only observed P/F forms; UIM forms and menu options/actions remain undecoded |
| Directory evidence | `WRKTYP TYPE(*QDIDX)` -> index -> entry -> repository cross-check / primary candidate | Same-name repository/library scope is provisional; no live-object claim |
| Repository evidence | `WRKTYP TYPE(*OIRS)` -> repository -> candidate index -> entry | Missing indexes and mismatching slots are explicitly retained |

Duplicate names retain origin/LBA. Enter selects; F12 returns to the previous
selection. Lists have selectable Next/Previous windows of 50 entries.
No message, directory or index screen substitutes a same-name object for an
unresolved address. Menu target matching is explicitly name-based.

## MSGF evidence

Observed `0E/03` prefix +100..105 is `6000002c0007`. The stored count is the
four-byte +106 scalar. A six-byte active-root reference at +420 is relative to
the primary virtual address; +42A is the four-byte page-size scalar (1024 on
examined older images, 2048 on examined V2R3 images). Release-2 traversal uses
these independently observed values rather than assuming context placement.
Strict message/directory traversal rejects page-size/type/alignment/free-range
violations, cycles, missing pages, and out-of-used-page node/text references.

Supported message terminals are 44 bytes: seven-byte ID, with candidate
first/second/ancillary record offsets at +9/+13/+21 (four bytes each). On Mark,
one exact-owner `0280` secondary per nonempty MSGF corroborates each pointer at
secondary offset `32 + stored_offset`: four-byte inclusive length, role tag at
+4, repeated ID at +5..11. First/second payload begins at +16 and its two-byte
length is at +14. Tags 01/02 carry literal text; 81/82 stay opaque compressed
payloads; tag 10 ancillary payload is not interpreted. All lengths, repeated
IDs, tags and recovered virtual ranges are checked before display. No text
search is used to manufacture an association.

Plain text is a CP037 display lens, not a decoded CCSID. Substitution markers
are not expanded. Severity and other terminal fields remain undecoded.
The text-record bound is 64 KiB; index reads stop at 8 MiB or the first virtual
gap. Multiple owner-matched secondary candidates cause withholding, not an
arbitrary first choice. Pete currently exposes IDs but lacks the matching
normally recovered `0280` storage. Seven older-image index count mismatches
remain visible; no missing entries are fabricated.

## QDDSI evidence

Existing DKEY/DKYT and tree decoders now feed paginated selectable entries in
stored traversal order. Partial keys retain tree evidence and never acquire
invented user-key bytes. A candidate record link requires an exact match of
**both** cursor QDDSI pointer and cursor QDDS pointer against the selected
DKEY's data-space address. Duplicate matching cursors stay separate. The
record window starts at the positive ordinal hint and initially uses raw bytes.
A missing first data group is still not independently ruled out, so these are
candidate record links, not a proof that every displayed ordinal is historical.

## Configuration and menus

Configuration search reads only DEVD and CTLD bounded primary bytes, compares
full eight-byte internal addresses to CTLD/LIND identities, and excludes the
common EPA region. It does not read profile credentials or scan unrelated
object payloads. Mark DEVD matches occur at +128, older Pete matches at +118;
controller/line occurrences vary. This is useful navigation evidence, not a
field-schema declaration. Device details remain accessible.

Menu +100 observed P (`D7`) carries program/library names at +130/+13A.
Observed F (`C6`) carries display-file/library there and message-file/library at
+144/+14E. Every name is a bounded ten-byte field. Type, name and explicit
library must match; *LIBL/*CURLIB retain all origins without pretending to know
a historical job's library list. Two P examples and two duplicate F primaries
were found on Mark; Pete's normally recovered menus are U variants. The U
variant remains explicitly unsupported. Program target selection opens a reverse CMD/P-menu name-reference view. This
is a workflow improvement, not a program-payload decoder or disassembler.

Period references rechecked locally: AS/400 Primer PDF p.233 distinguishes
message descriptions and the menu/display-file/message-file/program logical
relationship. Understanding AS400 System Operations PDF pp.146–147 describes
IDs, first/second text and substitutions. Neither supplies persistent offsets.

## QDIDX/OIRS evidence

Supported QDIDX control prefix is `60000018000c`, using independently checked
active-root/page-size values as above. Its 24-byte terminals contain a two-byte
type and ten-byte name; the +16 four-byte ordinal points to a candidate OIRS
512-byte slot. A same-name OIRS is only a candidate until the slot's +4..15
repeats the exact type/name key. All duplicates are checked individually.
Only these safe identity fields/results are displayed; no arbitrary OIRS
payload, profile material or inferred attributes are shown.

All 17,611 Mark identities matched their predicted slots. A one-byte shifted
identity control failed for all 17,611. Pete's 254 index entries currently have
no same-name recovered repository. A library/type/name primary match is shown
as another candidate, never as a recovered pointer. Missing primary and
repository cases preserve the surviving index evidence.

## Remaining experiments and pivots

- MSGF compressed records: role/length/ID framing is corroborated, but dictionary
  and token semantics are not. Implement a bounded decompressor only after
  independent multi-message checks; do not present printable runs as full text.
- MENU: a bounded +100..+FFF full-address search in 573 Mark / 187 Pete menu
  primaries found no recovered FILE, PGM or MSGF address matches. This rejects
  that narrow pointer hypothesis, not all linking possibilities. P/F qualified
  names yielded useful navigation; UIM offset/descriptor ownership is next.
- JOBD continuation: +10C/+116 queue/library names match assigned queues for
  34/34 Mark primaries. Pete's normally recovered queues are unassigned, so exact
  library matching alone found none; retaining labeled unassigned candidates
  resolves 10/15 descriptions. Five remain unresolved. +102 profile-name
  correlations only navigate safe identity views, never profile payloads.
- MSGQ continuation: bounded compound `09 + name(10) + library(10) + 06 + ID(7)`
  occurrences link 97/97 Mark and 93/96 Pete references to IDs actually recovered
  from candidate message indexes. Three Pete references remain unresolved.
  Offsets are byte-occurrence order, NOT message chronology. This does not decode
  queue-entry boundaries, sender/time/severity or substitution bodies.
- Pete MSGF follow-up: no matching text-secondary owner was recovered even when
  only the virtual owner address was compared, ignoring the extender. A raw
  whole-image search found no contiguous FMX0010 string; its index ID is
  reconstructed from tree pieces. This is negative evidence for simple missing
  owner metadata, not proof that all message text is absent or irrecoverable.
- JOBQ/OUTQ: a preliminary shared-tree probe recovered 48-byte terminals on both
  images; entry field semantics and active-vs-stale meaning are not established.
  This is a research lead, not a completed queue-management capability.
- PGM continuation: reverse command/P-menu name candidates now provide a path
  into command definitions. 773 Mark and 218 Pete program primaries have such
  candidates (2,479 / 418 links). Duplicated primaries may share candidates;
  these counts are not distinct callers or a call graph.
- SBSD/CLS bounded probe: no full-address occurrences to recovered JOBD, JOBQ,
  CLS or PGM primaries were found in the first 16 KiB of 14/4 SBSD and 26/10 CLS
  primaries. Mark QBASE pointers at +118/+128/+138 address ranges not represented
  by recovered segments (the QBASE primary has six pages). Resolving those
  tables needs a verified storage mapping/continuation, not guessed offsets.
- PGM instructions, delivered MSGQ records, OIRS attributes, library ownership pointers and numeric/logical
  DTAARA remain queued or partial as recorded in the capability ledger.

## Validation

`python3 -m unittest discover -s tests -v` includes synthetic malformed records,
relocated roots, both page sizes, duplicate origins, wrong IDs/types/pointers,
missing secondary storage, partial keys and navigation/Back checks.
`python3 tools/validate_extended_workflows.py /path/to/image.hda` performs
read-only corpus and model-path checks, emits aggregates only, and verifies the
image hash before/after. It does not replace a human terminal acceptance test.

## Library recovery diagnostics

`WRKTYP TYPE(*LIB)` -> recovered primary -> option 5 opens recovery diagnostics.
Entries are scoped by the full context address; filters show all, missing,
ambiguous or resolved references in 50-entry windows. Select a reference to see
all exact reconstructed address/type primary candidates. Duplicate candidates
are retained, including same-address copies; missing primaries remain visible
with owned-segment counts. No payload is synthesized from those counts.
Warnings in the existing inventory are keyed by library name, and the view
explicitly warns that these may include another same-name context.

Original validation: 40 Mark contexts, 21,531 resolved / 61 missing references;
16 Pete contexts, 206 resolved / 185 missing references. Three reference ->
candidates -> Back walkthroughs pass on each image. Synthetic duplicate-address,
same-name/different-context, unknown-address, filter and paging cases pass.
Library maturity remains partial; this adds recovery diagnostics rather than
claiming completeness.

## Output-queue next probe

A bounded first-4-KiB search of JOBD, DEVD and LDA primaries for recovered OUTQ
fixed-width names found one Mark JOBD occurrence at +0x17E followed by QGPL, and
none on Pete. Treating +0x17E as a general qualified-name field failed on 33 of
34 Mark and all 15 Pete descriptions. The general-layout hypothesis is rejected;
this does not prove other queue references or saved spool files are absent.

## Reference code translate tables (RCT)

`DSPRCT RCT(*ALL/*) KEYHEX(E2)` filters the observed eight-byte keys by byte
prefix. Select a key to inspect a corroborated opaque record in 256-byte
windows. No service actions or field meanings are inferred from those bytes.

The empirical header is `6000000c0008` at +0x100; count is u32 +0x106,
root address is six bytes +0x420 and page size is u32 +0x42A. Strict generic
machine-index traversal yields 12-byte terminals: key8 + u32 offset.
Mark has a unique exact-owner 0280 secondary for each RCT; record address is
secondary +32+offset and the leading u16 is an inclusive length. Key variants:
D/F: record[2:6] equals key[1:5]; S: record[2:4] equals key[1:3];
P: record[2:8] equals key[0]+key[2:6]+key[1]. Unused key bytes must be zero.
These variants are byte patterns, not established semantic names.

All 171 Mark indexes / 36,794 terminals and all 47 Pete indexes / 8,451 terminals
match stored counts with no traversal warnings. All 36,794 Mark records pass
full length and repeated-key checks: D 4,591, F 10,557, S 21,536, P 110.
Pete has no exact-owner recovered 0280 segments, so records remain unavailable.
Three model key -> record/diagnostic -> Back walkthroughs pass per image.
Synthetic tests cover short headers, invalid pages, count discrepancies, all
four repeated-key variants, length/key mismatches, missing/duplicate storage,
filtering and byte pagination.

Rejected hypothesis: neither terminal bytes[0:8] nor [4:12] matches a recovered
full object address. The validated offset relationship supersedes that guess.

## Job-private structure probe

Bounded first-4-KiB full-address searches of 410 Mark JMQ and 409 Mark / 20 Pete
LDA primaries found no addresses matching recovered JMQ, LDA, JOBD, JOBQ or MSGQ
primaries. This rejects only that simple direct-address navigation hypothesis.
LDA prefixes consistently differ from the supported character DTAARA selector;
reusing the DTAARA decoder would be unjustified. These families remain queued.
