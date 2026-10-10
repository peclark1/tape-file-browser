# Interactive Command Exploration: delivered workflow and evidence

October 9–10, 2026. Experimental, read-only capability on
`feature/interactive-command-explorer`, based on survey branch `f3bb539`.
The three relevant decoder/test/research files from independent draft #15
(`08bd88d`) were selectively incorporated and reviewed; no branches merged.

## What the user can do

Start `python3 as400_dasd_tool.py browse5250 /path/to/marks.hda`.

1. Type `WRKCMD CMD(*ALL/CPY*)`; select `QIWS/CPYTOPCD`, Enter.
   Alternatively navigate a library's normal object list and open a *CMD,
   or use `DSPCMD CMD(QIWS/CPYTOPCD)` directly.
2. Select a keyword with arrows/Page Down, Enter to inspect its ordinal,
   primary-relative keyword/ordinal/anchor offsets, origin, and unknown fields.
   All nine CPYTOPCD keywords appear, including TOFLR, TODOC and TRNIGC.
3. Backspace/F12/Ctrl+B returns to the same selected parameter, then command.
   Summary includes library-assignment provenance and the full failure reason
   for unsupported/incomplete tables. Evidence retains unclassified text.
4. PGM matches lists recovered *PGM identities matching both tentative library
   and program strings. Enter displays their origin; **name equality is not a
   decoded CPP pointer**. An empty list is not proof that no processor exists.
5. `DSPCMD CMD(CRTCMD)` retains duplicate library/primary choices. At a chosen
   QSYS/CRTCMD, Page Down traverses all 27 stored keyword ordinals.
6. On Pete, use `WRKCMD CMD(*ORPHAN/ADDPFM)` and inspect individual LBAs.
   No QSYS assignment is invented for an unassigned primary.

`WRKCMD` accepts CMD(name), CMD(library/name), `*`/`?` patterns, `*ALL`
(all libraries, including unassigned), and `*ORPHAN` (unassigned only).
These are offline explorer operations, not a general CL interpreter.
F4 still searches the **implemented browser operations**, not historical
command prompting. No parameter values or executable command lines are built.

At 80x24 and 64x16, detail text wraps rather than discarding qualifiers off
screen. Lists page normally; duplicate names retain distinct primary LBAs.

## Evidence boundaries

- Verified read locations: 520-byte physical sectors, 512-byte payloads;
  primary prefix is reassembled through existing recovered virtual extents.
  The loader samples at most 8,192 bytes and rejects non-CMD objects first.
- Empirical partial decoder: observed count byte +0x180, first keyword +0x19C,
  ten EBCDIC bytes, four preceding NULs, following two-byte big-endian ordinal;
  subsequent matches are bounded and unambiguous. All expected ordinals must
  be present. Missing, conflicting, duplicate, oversized or invalid sequences
  are withheld, not filled with guesses. Zero count is not asserted to mean
  a verified parameterless command.
- Unknown: descriptor lengths/links, PARM types, lengths, required flags,
  choices, defaults, prompt/message links, QUAL/ELEM, actual CPP pointers,
  and historical F4 presentation order. Nearby strings remain unclassified.
- Identity and payload may be stale/inconsistent. A successful structural
  parse does not prove that the fields belong to a currently active command.
  Library provenance (EPA back-pointer versus directory memberships) is shown.
- Inventory maturity moves only *CMD from Evidence to Partial. No MENU,
  MSGF or PGM maturity is promoted by this name-based navigation.

## Original-image validation

Both supplied ZIPs passed extraction/CRC checks. Extracted originals were
chmod 0444, accessed through `DASDImage` read-only `rb` methods, and kept
outside the repository. SHA-256 before and after the acceptance runs matched:

| Image | Bytes | SHA-256 |
|---|---:|---|
| Mark | 1,004,257,800 | `49e4e989fcc6732ffb21bd0d0a610ffcf9afd582d5cd84e3af8f02ccc8593898` |
| Pete | 320,523,840 | `1fc2e7be114d74a8e8f386565e38a636c76bde529161d93bd53bbeed8a0955f6` |

| Recovered-object measure | Mark | Pete |
|---|---:|---:|
| CMD primaries accepted by normal segment/object recovery | 3,118 | 1,098 |
| Assigned a library by existing recovery | 3,118 | 2 |
| Complete empirical keyword sequences | 2,571 | 476 |
| Unassigned commands exposed by search | 0 | 1,096 |

These are **not** the earlier physical-signature census (3,129 / 1,117),
and are **not** live OS/400 command counts or semantic correctness totals.

Independently checked reference rows (names/counts also compared with the
prior #15 observations, retaining original-release ordering):

| Image / recovered context | Primary LBA | Keywords | Validation scope |
|---|---:|---:|---|
| Mark QIWS/CPYTOPCD | 1,448,288 | 9 | Full expected sequence, every UI parameter and Back |
| Mark QSYS/ADDPFM | 1,864,496 | 6 | FILE MBR EXPDATE SHARE TEXT SRCTYPE |
| Mark QSYS/DSPCMD | 1,866,708 | 2 | CMD OUTPUT |
| Mark QSYS/CRTCMD | 73,304 | 27 | Full stored sequence including NATIVE |
| Pete unassigned ADDPFM | 587,516 | 5 | FILE MBR EXPDATE SHARE TEXT; library unknown |

Reproduce without exporting recovered private content:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile *.py tools/validate_command_exploration.py
bash -n install.sh uninstall.sh
python3 tools/mi_object_inventory.py --check-report
python3 tools/mi_survey_priorities.py --check-report
python3 tools/validate_command_exploration.py /path/to/marks.hda --specimens marks
python3 tools/validate_command_exploration.py /path/to/petes.hda --specimens petes
```

The opt-in validator prints aggregates, digests and the explicit IBM reference
specimens only. Its specimen profiles target these exact archives; another
image/release may legitimately fail the expectations. No original bytes,
manual pages, passwords, or recovered private records enter Git.
Synthetic tests exercise parsing corruption, ambiguity, short input, duplicate
keywords, noncontiguous extent reads, type gating, search ambiguity/orphans,
normal object entry, nested Back, candidate-program lookup, read errors,
command injection rejection, and frontend keyboard/rendering at both sizes.

## Concrete blockers, negative evidence, and next experiments

### Prompt/default/choice links

Inspected virtual-order CPYTOPCD, CRTCMD, ADDPFM and DSPCMD primaries on Mark,
and the available Pete counterparts. Candidate text/default-like tokens occur
outside the validated keyword fields; none of the current evidence establishes
which descriptor bytes address them or distinguish defaults from alternatives.
For example, Mark CPYTOPCD keywords span +0x019C..+0x039F. Following bytes
vary between descriptors; treating adjacency or arbitrary small integers as
pointers would attach text without proof. Historical Primer PDF pp.438–439
was rechecked from the supplied archive: its PARM/DFT/VALUES/PROMPT source
explains the logical relationship but supplies no compiled-byte layout.

Required evidence: period-correct command source plus its matching compiled
V2R3 object and DSPCMD/F4 output, preferably variants changing just one
PROMPT/DFT/VALUES attribute. Alternatively an authoritative CISC compiled
command layout with independently verified pointer bases and bounds.
**Pivot delivered:** useful search/parameter/origin/evidence navigation without
assigning those unknown attributes. No fake editable F4 screen.

### Pete missing keyword slots / inconsistent identity

- CPYTOPCD LBA 307,992 has count byte 9; ordinal sequence 1–8 is found but
  the required ordinal 9/TRNIGC is absent from the accepted window. The 4 KiB
  virtual-order prefix does not contain the TRNIGC string. Do not silently
  report eight parameters or copy Mark's ninth keyword.
- CRTCMD LBA 308,024 declares 19; expected next ordinal 7 is not recovered.
  TYPE is absent from the sampled prefix; several later ordinals are also
  missing. A different historical layout or damaged/stale bytes is possible;
  the available evidence does not distinguish them.
- Pete primary LBA 587,728 has EPA name STRDFU and existing recovery assigns
  QSYS2900, but +0x102/+0x10C names read QLICRDUP/QSYS. The validated stored
  keyword sequence is OBJ FROMLIB OBJTYPE TOLIB NEWOBJ DATA; +0x596 has
  CRTDUPOBJ text and the empirical +0xB8 title at +0x64E reads Create
  Duplicate Object. All four pages form one recovered extent; the conflict
  is not caused by our UI joining physically separate command objects.
  Do **not** count this as a semantically validated STRDFU definition.

Next proof: compare original sector headers/EPA/context directory references
with another capture or matching release's command source/display. Investigate
stale/reused storage or copying/renaming before altering the core recovery
rules. No empirical basis currently justifies automatically renaming the
object or selecting a supposedly correct library. The validator deliberately
uses the unassigned ADDPFM specimen for Pete instead of this conflict.
