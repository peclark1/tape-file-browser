# Historical CISC OS/400: four connected object types

**Scope:** 19/05 *CMD, 0E/03 *MSGF, 19/16 *MENU, 02/01 *PGM.
All references are 1-based PDF-viewer pages in the user's archived
AS/400 manuals. These are **historical logical associations and empirical
binary clues**, not a published CISC on-disk field schema.

## Command definitions, programs, parameters

*AS/400 Primer* (Ernie Malaga, 1992), PDF p.230: a *CMD is the
interface to its distinct command-processing *PGM. PDF p.234:
compiled program objects do the actual work. Neither passage
describes the stored instruction stream or ODT offsets.

The Primer's worked command source (PDF pp.438–439) specifies
**SNDBRKACT**, parameters **MSG**, **MSGTYPE**, **QSYSOPR**,
processing program **BRK001CL** in its CRTCMD statement, and the
separate CL source for that program. The source gives choices
*INFO/*INQ (default *INFO) for MSGTYPE and *YES/*NO (default
*NO) for QSYSOPR. These are **source-level example values**, NOT
attributes recovered from a compiled SNDBRKACT primary.

*Starter Kit: IBM iSeries & AS/400* (Guthrie/Madden, 2001),
PDF pp.478–480: **PRTOBJAUT** command (OBJ, OBJTYPE parameters)
is accompanied by a separately illustrated command processing
program **PRTOBJAUT1**. Its command source includes PARM and
QUAL statements and an allowed-value list of object types.
PDF pp.518–524: **SNDBRKMSGU** command source and distinct
**SNDBRKMSGV** validity-checking program and **SNDBRKMSGC**
processing program, including PARM/QUAL/DEP examples.
These later sources cannot be substituted for V2R3 disk offsets
or the historical F4 display order.

Draft PR #15 separately implements experimental *CMD keyword/ordinal
recovery; it is not part of the merged main decoder.

## Message file and display/menu relationships

*AS/400 Primer*, PDF p.233: *MSGF stores **message descriptions**,
not general database records; the manual names QSYS/QCPFMSG as
the principal OS message file. It also says a *MENU ties a
**display file** to either a **message file or a program**.
These are logical relationships; the manual does not specify
which bytes are persistent object addresses or links.

*Understanding AS/400 System Operations*, PDF pp.146–147:
predefined messages, variable substitution, severity and first-/
second-level descriptive text. PDF pp.150–153: examples of
WRKMSGD/message-description selection, and commands such as
CRTMSGF, ADDMSGD, DSPMSGD and WRKMSGF; p.172 discusses message
IDs and substitution. These are logical retrieval requirements,
not the internal *MSGF index/entry layout.

*AS/400 Power Tips and Techniques* (Bisel), PDF pp.352–353:
a DDS display-file MSGID field refers to message **USR0001**
in **QGPL/USRMSGF**, created with CRTMSGF/ADDMSGD. Editing the
message description can alter displayed text without recompiling
the display file. This documents a **display-file →
(message-file, message-ID)** dependency, but not its binary
storage-pointer representation.

Do not confuse 0E/03 *MSGF (message definitions) with
19/02 *MSGQ (delivered-message queue). Likewise 19/16 *MENU
may use 19/01 *FILE display-file objects, a message file,
or a program, but no menu/display/program binary link has
yet been confirmed.

## Whole-image physical-primary candidate census

We read all 520-byte sectors from Mark's V2R3 HDA and Pete's B10
HDA. Candidate matching validates the common type/name offset,
a primary page signature, and the observed family-specific
segment-group header variant. **Physical primary candidates are
not active objects**: stale, duplicate and orphaned primaries
may survive, and a full context-index traversal is needed to
identify current objects.

| MI | Type | Group tags | Mark candidates | Pete candidates |
|---|---|---|---:|---:|
| 19/05 | *CMD | 89 | 3129 | 1117 |
| 0E/03 | *MSGF | 90 | 56 | 38 |
| 19/16 | *MENU | 80,81 | 574 | 223 |
| 02/01 | *PGM | 80,81,89 | 4286 | 3081 |

Menu group split: Mark **81=570 / 80=4**, Pete
**80=209 / 81=14**. PGM group split: Mark **81=2791,
89=1494, 80=1**; Pete **81=2744, 89=337**.
The source of these differences is **not established**.

### Preliminary byte/text observations (not field decoders)

- Sample *MSGF primaries, including QIWSMSG and QORMSG from
  both images, have an apparently recurrent +0x100 binary prefix
  starting **60 00 00 2C 00 07**. Its structural role is unknown;
  do not label it message count or index pointer.
- Examined *MENU primaries in both images contain an EBCDIC
  *NOCHG token in an early primary region. Examples from Pete's
  disk contain internal tokens including OPTION1, PROMPT,
  PAGEDOWN, PAGEUP, PRINT and a menu name in physically adjacent
  pages. Text labels are **not** verified displayed menu options
  or executable action pointers. Menu group variants require
  release-sensitive investigation.
- Examined *PGM primaries sometimes carry IBM copyright
  information and symbolic strings. These **do not establish
  an MI instruction stream or ODT layout**.
- Physically adjacent sectors were used only for bounded
  diagnostic examples. Real decoders must reassemble storage
  in **virtual extent order** and reject missing storage.

Reproducible, aggregate-only (no object names or raw bytes exported):

    python3 tools/mi_primary_census.py /path/to/marks.hda.zip
    python3 tools/mi_primary_census.py /path/to/petes.hda.zip

## Next proof obligations

1. **MSGF:** identify a stable message ID/key and associated
   first-/second-level text from several independent messages;
   prove index/data separation, pointer limits and corruption cases.
2. **MENU:** reconstruct menu title and option/action references,
   distinguishing display-file, MSGF and PGM links using
   independent pointer validation and both group variants.
3. **CMD:** build on PR #15 only after independently proving
   prompt/default/allowed-value descriptor linkage and the
   processing program reference.
4. **PGM:** obtain period-correct MI program template/ODT
   documentation; verify true instruction boundaries, relocation
   and pointers before attempting a read-only disassembler.
5. Move registry status forward **only after confirmed binary fields
   and synthetic regression tests**, not from manual syntax or
   extracted EBCDIC strings alone.

No proprietary manual pages, disk sectors, credential material,
or historic user records are committed.
