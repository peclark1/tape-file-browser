# Original CISC OS/400 V2R3 *CMD research — first evidence checkpoint

Status: **experimental, read-only; compiled command schema not decoded**.

## Evidence sources

- IBM historical descriptions of *CMD vs. command-processing *PGM and command
  source (CMD/PARM/CRTCMD): AS/400 Primer (Ernie Malaga, 1992),
  section "Command (*CMD)" around printed p. 214 and command-source examples.
- IBM QCDRCMDI / CMDI0100 documents retrievable logical attributes. API
  output layout must **not** be assumed to be the CISC on-disk layout.
- Bounded independent read-only scan of Mark's V2R3 marks.hda disk image,
  1,931,265 520-byte physical sectors. No real disk bytes were committed.

## Observed primary layout

Offsets refer to the reassembled 512-byte CISC page payloads in virtual
extent order, with 8-byte physical sector headers removed.

- Primary starts with a 32-byte segment group header; the common EPA starts
  at +0x20, containing MI 19/05 at +0x22, and EBCDIC object name at +0x24.
- In the specimens below two adjacent ten-byte EBCDIC strings occupy
  +0x102..+0x10B and +0x10C..+0x115. They look like command processing
  program and library names, **but this field meaning is not yet validated**.
  The browser labels the strings and offsets tentative.
- A repeated printable descriptor containing a whole command name with
  *LIBL or *NONE is followed **0xB8 bytes later** by an English heading
  corresponding to the command title. This is an empirically corroborated
  **candidate description**, not a documented pointer/string field. Multiple
  distinct candidate descriptions must prevent labeling.

| Command | Mark V2R3 primary LBA | Candidate program/library | Descriptor +offset | Title +offset |
|---|---:|---|---:|---:|
| ADDACC | 77,808 | QOSADACP/QSYS | 0x20C | 0x2C4 |
| ADDAJE | 77,656 | QWDCADA/QSYS | 0x329 | 0x3E1 |
| ADDPFM | 1,511,696 | QDDCPFM/QSYS | 0x385 | 0x43D |
| CRTCMD | 73,304 | QCDRCMD/QSYS | 0xDBD | 0xE75 |
| DSPCMD | 1,490,106 | QCDDCMD/QSYS | 0x266 | 0x31E |
| CALL | 1,516,822 | QCLCALL/QSYS | 0x242 | 0x2FA |
| DLTCMD | 1,540,116 | QLIDLOBJ/QSYS | 0x275 | 0x32D |

These samples establish repeated observable patterns but **do not** prove a
complete command-definition format or that it is invariant across releases.
Primary LBAs apply only to this image and are provided as research locators.

## First Guided 5250 milestone

Enter (or option 5) on a recovered *CMD object opens a read-only Command
Information screen. It shows recovered identity, MI type, virtual address,
primary LBA, page count, bounded sampled bytes, candidate processor strings
with exact offsets, candidate description with clear caveats, and printable
EBCDIC fragments with offsets and an explicit unclassified label.

Parameters, processing-program pointer semantics, defaults and help text
remain **not decoded**; no CL commands are executed. Option 8 retains ordinary
object details; Back/F12 returns to the previous list.

The analysis samples at most 8,192 bytes of the recovered primary in virtual
extent order; at most 64 printable strings, each at most 96 displayed chars.
Unrecovered or truncated data is never replaced with invented contents.
The display-only safe-text layer escapes NUL and other control characters.

## Evidence gates for deeper decoding

1. Validate +0x102/+0x10C against real DSPCMD/QCDRCMDI output or command
   source, and correlate referenced programs with independent recovered
   02/01 *PGM identities. The currently tentative strings are not a verified
   program pointer.
2. Compare more IBM and non-IBM command objects across releases/images and
   independently document any differing descriptor layouts.
3. Recover parameter-count, parameter-table pointer, type, default, and prompt
   data only after repeated structural corroboration and negative tests.
4. Implement authentic F4 parameter screens only after that validation.
5. Revisit the empirical title/descriptor +0xB8 relation before advertising
   it as an architectural offset.

Only aggregate findings, synthetic tests and documented methods may be
committed. Do not commit disk image contents, user records, or proprietary
source code.
