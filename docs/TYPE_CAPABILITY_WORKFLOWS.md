# Cross-type Guided workflows

This checkpoint advances nine MI types beyond their previous Guided behavior;
it does not complete the 268-type program. The [full queue](MI_CAPABILITY_PROGRESS.md)
tracks workflow outcomes independently of decoder maturity. Existing forensic
features remain available. All image access is read-only.

## User workflows

| Start in Guided 5250 | What becomes possible |
|---|---|
| `WRKTYP` or `WRKTYP TYPE(*ALL)` | Browse every catalog type plus unidentified recovered raw codes; Enter lists its recovered primaries, including unassigned ones. Zero is not proof of absence. |
| `WRKOBJ OBJ(*ORPHAN/*) OBJTYPE(*TBL)` | Search across namespaces by name/type or raw code such as `19/ED`. Duplicate primaries retain origin; 8 displays it. Generic navigation is not a decoder. |
| `DSPFD FILE(library/file)` | Select FCB format candidates, inspect their field descriptors, and return to the same selection. Name and address occurrence evidence remain distinct. 12 on a file still opens members; 5 opens format candidates. |
| 9 on a member | Follow exact cursor QDDS/QDDSI addresses; inspect storage layout/key specifications; follow a reverse cursor reference and use 5 to open member content. No same-name storage fallback in this workflow. |
| `DSPTBL TBL(*ALL/QASCII) HEX(C1C2C3)` | Inspect a recovered 256-byte map, view the sample result (`41 42 43` on reference QASCII), select each input/output pair and inspect collisions. HEX is a bounded offline extension; no CL executes. |
| `DSPDTAARA DTAARA(*ALL/*)` | Choose a character data-area primary, browse value positions and inspect exact hex with a CP037 reference rendering. Unsupported selectors produce an explicit diagnostic. |
| `WRKOBJ OBJ(QDOC/*) OBJTYPE(*DOC)` | Follow all name-convention companion candidates to DOCBSS, then select exact byte ranges of a validated stream. Unknown document format/encoding stays unknown. |

`WRKTYP` and the `HEX` parameter are explorer extensions, not claims of historical
CL compatibility. Existing library, command and member navigation is retained.
Back restores selection; views wrap at 80x24 and 64x16. Primary headers, payloads
and controls are never executed. No images, recovered private data or manual
pages belong in the repository.

## Decoding and bounds

- All new primary reads traverse virtual extents, stop at virtual gaps, and
  reject short logical sectors. Format/FCB/key metadata reads cap at 64 KiB.
  Missing evidence stays missing. This does not replace the older forensic readers.
- FILE/FMT/MEM/QDDS/QDDSI use existing empirically established parsers. FILE
  associations are exact ten-byte padded-name occurrences with independent
  internal-address occurrence evidence; they are not proven ownership fields.
  Duplicate formats are explicitly selectable. Field discovery remains partial.
- A member's +0x128 / +0x300 pointers link QDDSI / QDDS by full internal address
  **and MI type**. Reverse navigation uses those same pointers; unreadable
  cursor counts are visible. It does not certify live membership.
- TBL MI 19/06: bytes +0x100..+0x1FF form an empirical single-byte map, indexed
  by the input byte. All 256 output values are legal; non-bijective maps are
  not "repaired." Input samples are limited to 64 bytes. Purpose, CCSIDs and
  following flags remain undecoded. Physical map recovery is not proof of
  runtime use, or universal support for every historic table form.
- DTAARA MI 19/0A selector 04: observed big-endian u16 length at +0x101,
  exact character bytes at +0x103. Length must be 1..2000 and fit the recovered
  prefix. CP037 is a rendering choice, not a claimed decoded CCSID. Spaces and
  NULs are preserved; allocation padding is excluded.
- DOC to DOCBSS uses the existing QDOC `name + F` convention, **not a pointer**.
  Byte-stream recovery independently validates duplicate lengths at +0x106 and
  +0x112, allocation, the primary prefix and any exact-owner 0F90 continuation
  groups in contiguous virtual order. Total declared length is u16-bounded.
  Hex is authoritative; ASCII/CP037 are reference lenses. No format is guessed.

## Original-image research

Both ZIP archives were extracted with CRC validation in the preceding continuation;
this pass rechecked extracted sizes, mode 0444 and SHA-256 before development.

- Mark: 1,004,257,800 bytes; SHA-256 `49e4e989fcc6732ffb21bd0d0a610ffcf9afd582d5cd84e3af8f02ccc8593898`.
- Pete: 320,523,840 bytes; SHA-256 `1fc2e7be114d74a8e8f386565e38a636c76bde529161d93bd53bbeed8a0955f6`.

Normal recovery exposes 629 / 88 TBL primaries. Every one supplies the full
map window. Mark QASCII LBA 1837442 and QEBCDIC LBA 1837600 compose to identity
for **all 256 inputs**. QASCII on both images maps the synthetic test text
`ABC abc 012` from CP037 to ASCII. QSYSTRNTBL on both maps that test text to
uppercase CP037. Pete QASCII is LBA 584154. These checks support observed byte
semantics; names alone were not used to synthesize maps.

Mark has 37 recovered DTAARA primaries: 35 selector-04 character forms, one
selector 03, one selector 84. Pete has 54, all selector 04. Declared character
lengths range from 10 to 750 bytes on Mark and 13 to 750 on Pete and fit the
recovered primaries. Exact length extraction is tested; no private values are
published. The two unsupported forms are a **specific remaining subtask**:
selector 03's length-like word is 15, selector 84's is 1; neither value is
interpreted as text or a number. Independent known definitions/display output
and multiple values are needed to establish storage, scale and logical encoding.
Work proceeded to document byte-stream navigation instead of waiting on them.

The supplied AS/400 Primer (1992), PDF pages 230, 294–295 (printed 214,
278–279), establishes data-area purpose and position/length retrieval semantics.
It does not establish these binary offsets. The byte layout is image evidence.
Modern IBM [collating-sequence documentation](https://www.ibm.com/docs/ssw_ibm_i_74/db2/rbafzsortsequence.htm)
is logical context for table usage only; no modern receiver layout is imported.

## Validation and continuing work

Synthetic tests cover wrong types, short headers/values, unsupported selectors,
invalid samples, virtual gaps, read caps, exact pointer/type matching, duplicate
names, malformed document lengths, continuation ownership/contiguity, UI drilling,
Back, keyboard navigation and terminal rendering. No original bytes are fixtures.

Opt-in aggregate-only whole-image validation (never writes the image):

```sh
python tools/validate_type_capabilities.py /path/to/marks.hda
python tools/validate_type_capabilities.py /path/to/petes.hda
python -m unittest discover -s tests -v
python tools/mi_capability_progress.py --check-report
```

See the living handoff for final corpus counts, tests and PR state. Next work
continues through the ranked queue: actual record selection from field/index
views, MSGF ID/text indexing and MENU/PGM relationships, folder/path traversal,
and unsupported data-area forms. Existing CMD QUAL/ELEM and conversion work
remains queued too; it must not consume the entire cross-type program again.
