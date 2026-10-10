# Recovered command prompt browsing — empirical linked records

October 10, 2026. Continues intermediate PR #19 from `9dd282f` on
`feature/command-prompt-links`. This is a working prompt-browsing increment;
complete command semantics, nested QUAL/ELEM, message-file linkage and CPP
pointer decoding remain unfinished. It does not execute commands.

## Delivered workflow

In Guided 5250 enter `DSPCMD CMD(QIWS/CPYTOPCD)` and select **Prompt form**.
Arrows/Page Up/Page Down select parameters. Each row group displays:

- Stored keyword and empirical linked prompt label (or an explicit blank /
  unavailable label).
- Linked display hint, when its record is supported.
- `Default?` and `Values?` candidates, with their tentative meanings identified
  in the fixed screen heading. They are not editable fields or validation rules.

Enter opens exact references, message IDs, value-record offsets, unsupported
attributes and remaining unknowns. Back returns to the same prompt row, then
the definition. This works at 80x24 and 64x16. Ordinary definition rows now
show linked prompt labels too. The legacy unclassified string screen remains
available as Evidence.

Examples exercised: Mark QIWS/CPYTOPCD, QSYS/ADDPFM, QSYS/DSPCMD,
QSYS/CRTCMD; Pete unassigned ADDPFM at LBA 587516. CPYTOPCD REPLACE has a
linked prompt, hint, two value tokens and a separate first-value reference.
Its TRNIGC prompt text is actually blank: the UI does not copy a modern label.

## Structural experiments and results

All offsets below refer to virtual-order 512-byte payloads, excluding the
8-byte physical sector headers. Every decoder operates on an 8 KiB prefix.

Let K be a previously validated top-level keyword offset; D = K - 27.
All described references are unsigned big-endian 16-bit offsets relative to
primary **+0x100**, not absolute physical addresses or modern API receivers.

| Field / structure | Observed relationship | Qualification |
|---|---|---|
| D + 0 | Next top-level descriptor; zero terminates | All nodes must correspond to the recovered keyword set in ordinal order |
| K + 12 | Second descriptor chain; zero terminates | Complete acyclic chain or fall back to stored ordinal order with diagnostic |
| K - 6 | Reference to parameter prompt record | Validate bounds, message-ID shape and exact EBCDIC text length |
| K + 14 onward | Tag / u16 total byte length / payload; FF terminator | Walk lengths, never scan for a tag; bounded before next descriptor |
| Tag 06, length 8 | Count at +4 is 1; reference at +6 to display-hint record | Other shapes unsupported |
| Tag 01, length 6 | Reference at +4 to candidate value | Default role remains tentative; conversion/type byte not interpreted |
| Tag 02, length 7+5*n | Count at +3; five-byte entries, first reference at entry+1 | Candidate tokens only; second reference and conversion byte not interpreted |

A prompt/hint record consists of two opaque bytes, a seven-byte message ID
(or seven EBCDIC blanks), two opaque bytes, a two-byte text length, then
exactly that many EBCDIC bytes. Literal value records use a two-byte length
and text. The opaque bytes are not labeled as field lengths, flags or types.
Only printable EBCDIC text with length <=512 is supported. Binary values,
out-of-range links and unsupported text are omitted with diagnostics.

### Independent corroboration / negative checks

- Across **all 2,571 Mark and 476 Pete complete keyword tables**, the D+0
  chain visits the recovered keyword descriptors in ordinal order, without
  cycles or unmatched nodes. No new keyword tables are inferred from pointers.
- The second chain is **not always identical**: Mark CPYTOPCD orders its last
  two keywords TRNIGC, RCDFMT; ADDPFM orders FILE, MBR, TEXT, EXPDATE, SHARE,
  SRCTYPE. These are stored links, not a reordering imposed by modern docs.
- Prompt records relocate between independent ADDPFM and DSPCMD specimens;
  following the same relative-reference fields still recovers their labels.
- Tag 06 references land on exact length-prefixed display-hint records.
  Tag 01/02 references land on literal records, including input tokens whose
  paired second references can point to compact translated values. Those
  translation semantics are not decoded or executed.
- Synthetic tests move a prompt while leaving the old valid text in place;
  decoding follows the changed reference. Broken references do not fall back
  to the old text. Tests cover cycles, omitted/foreign descriptors, truncated
  headers/text, invalid text/IDs, TLV overruns/repeated tags/missing terminators,
  incomplete value lists, the 8 KiB cap and noncontiguous physical extents.

IBM's later [CPYTOPCD](https://www.ibm.com/docs/en/i/7.5?topic=ssw_ibm_i_75%2Fcl%2Fcpytopcd.html)
and [ADDPFM](https://www.ibm.com/docs/en/i/7.4.0?topic=ssw_ibm_i_74%2Fcl%2Faddpfm.html)
references independently corroborate selected labels, special values and the
secondary ordering. They do **not** establish V2R3 binary offsets, complete
historic choices, default conversion semantics or historical F4 behavior.
Modern CPYTOPCD has additional TRNIGC values and a label absent from the
sampled historical prompt. Nothing is backfilled from those later references.
Historical source examples indexed in the handoff likewise establish logical
concepts, not this binary layout. A matching period-correct source/object/F4
triplet is useful further corroboration, not a prerequisite to this research.

## Original-image validation

The original ZIPs were re-extracted, CRC checked, and HDA files set to 0444.
Both hashes match the prior session; validation hashes before/after also match:

- Mark: 1,004,257,800 bytes; SHA-256
  `49e4e989fcc6732ffb21bd0d0a610ffcf9afd582d5cd84e3af8f02ccc8593898`.
- Pete: 320,523,840 bytes; SHA-256
  `1fc2e7be114d74a8e8f386565e38a636c76bde529161d93bd53bbeed8a0955f6`.

| Aggregate across recovered complete keyword tables | Mark | Pete |
|---|---:|---:|
| Descriptor-link tables | 2,571 | 476 |
| Nonblank linked prompt labels | 13,851 | 2,889 |
| Nonblank linked display hints | 16,163 | 2,538 |
| Linked default candidates | 11,335 | 1,896 |
| Linked value candidates | 22,128 | 3,947 |
| Parameters with some unsupported attributes | 714 | 127 |

These are aggregate recovered references, not unique messages, active OS/400
objects, verified defaults or full validation-rule counts. Inconsistent/stale
identity concerns from Pete remain unchanged; STRDFU/CRTDUPOBJ is not a
semantically validated specimen. The two-image validator prints only aggregates
and the existing explicit IBM reference specimens, never a private-content dump.

Reproduction:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile *.py tools/validate_command_exploration.py
python3 tools/mi_object_inventory.py --check-report
python3 tools/mi_survey_priorities.py --check-report
bash -n install.sh uninstall.sh
python3 tools/validate_command_exploration.py /path/to/marks.hda --specimens marks
python3 tools/validate_command_exploration.py /path/to/petes.hda --specimens petes
```

## Remaining work and precise continuation

1. **Typed values / defaults:** the parser deliberately leaves the tag 01 type
   byte and tag 02 conversion byte/second reference opaque. Follow both halves
   of the mapping for REPLACE (*NO/*YES) and TRNFMT (*TEXT/*NOTEXT); contrast
   numeric/binary MAXPOS and blank-valued cases. Establish data-type widths and
   conversions before promoting candidate defaults or advertising validation.
2. **Nested qualifiers/elements:** FROMFILE currently links its top-level label
   but has no tag-06 hint; subordinate descriptors outside the recovered keyword
   set contain additional references. Test address/ownership relationships for
   file/library qualifiers and list elements. Do not attach nearby text by order.
3. **MSGF / CPP:** inline message IDs do not prove a MSGF pointer. Follow actual
   object/address relationships before joining external messages or invoking a
   program inspector as a proven CPP. No execution is in scope.
4. **Unsupported corpus cases:** classify the 714 / 127 per-parameter issue
   cases without exporting names/content. Determine which are binary values,
   unsupported tags, malformed data or prefix truncation before enlarging reads.
5. **Pete inconsistencies:** preserve the documented STRDFU/CRTDUPOBJ conflict
   and incomplete keyword tables. They do not block valid independent specimens.

Start in `as400_cmd.py:recover_definition_links`; UI entry is
`Guided5250.explore_command` and the `command_prompts` renderer. Keep iterating
from observed structures to usable capabilities; neither this PR nor a passing
test count means the entire capability roadmap is complete.
