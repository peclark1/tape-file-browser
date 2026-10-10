# Tape File Browser

Tools for browsing, inspecting, comparing, and converting SIMH and AWS tape images, plus an experimental read-only CISC AS/400 DASD structure explorer, written for IBM System/36 and AS/400 archival work.

The project separates the tape backend from three user interfaces:

- **Core/backend** — `tape_formats.py`, with SIMH/AWS parsing, conversion, verification, and hashing
- **CLI** — `tape-tool` subcommands for scripted/server use
- **TUI** — `tape-tool browse`, an interactive curses text user interface
- **GUI** — `tape-file-browser`, the GTK4 graphical desktop interface
- **AS/400 DASD core** — `as400_dasd.py`, a read-only parser for raw 520-byte CISC DASD images
- **AS/400 DASD CLI/TUI** — `as400-dasd`, with scripted commands plus an interactive curses browser

The core, CLI, and TUI do not require GTK or X.

Browsing is read-only. Conversion writes a new output image and then reopens it to verify the logical tape structure and every record payload before reporting success.

## Features

- GTK4 graphical interface (GUI) with multi-image workspace
- GUI native multi-file open dialog and per-image navigation state
- GUI image checkboxes and full-width compare-results pane
- Command-line interface (CLI) requiring no X/GTK libraries
- Interactive curses text user interfaces (TUIs) for both tape and AS/400 DASD browsing over SSH/server consoles
- TUI file-open dialog with multi-select
- Multiple simultaneously open tape images with an Images pane
- Mouse or keyboard switching between open images
- Mark two or more open images and compare them from inside the TUI
- Opens SIMH `.tap` and AWS/Hercules `.aws` tape images
- Three-pane browser:
  - logical tape files
  - records within the selected tape file
  - decoded EBCDIC contents of the selected record
- Displays record length and image/data offsets
- Highlights SIMH records carrying the error flag
- Summarizes record sizes, tape marks, EOM, and SIMH gap markers
- Indexes record offsets instead of loading the entire tape image into memory
- Converts SIMH -> AWS and AWS -> SIMH
- Compares SIMH/AWS images for logical record-by-record equivalence
- EBCDIC and hex/EBCDIC record views in the text-mode tools
- Verifies conversions record-by-record with SHA-256 payload hashes
- Supports standard multi-chunk AWS records
- Desktop launcher for Ubuntu/GNOME
- Installer can pin the application to the Ubuntu/GNOME dock

## Guided 5250 record and folder exploration

[PR #22](https://github.com/peclark1/tape-file-browser/pull/22), branch
`feature/explicit-record-explorer`, adds member **6 + Enter** for
explicit format selection and paged record/field inspection; **9 + Enter** opens storage
and fixes the previous key-loop omission. `DSPFD` → format → **Records** retains
the selected schema. `WRKFLR FLR(*ALL/*)` opens folder anchor-source/root navigation.
These are read-only offline workflows; uncertain associations are labeled.

Run `python3 as400_dasd_tool.py browse5250 /path/to/image.hda` from that checkout.
See [testing instructions and evidence](docs/RECORD_AND_FOLDER_WORKFLOWS.md).
PR #21's testing branch is unchanged; the follow-up is separate and unmerged.

## Requirements

The core, CLI, and TUI use only the Python standard library. On normal Linux Python installations, the curses module is included as well.

The GTK4 desktop browser additionally needs:

```bash
sudo apt install python3-gi gir1.2-gtk-4.0
```

## Install

Clone the repository and run:

```bash
git clone https://github.com/peclark1/tape-file-browser.git
cd tape-file-browser
bash install.sh
```

The normal installer installs the GTK4 GUI plus the CLI/TUI tools:

```text
~/.local/bin/tape-file-browser
~/.local/bin/tape-tool
~/.local/bin/as400-dasd
~/.local/bin/tape_formats.py
~/.local/bin/tape_text.py
~/.local/bin/as400_dasd.py
```

and installs a desktop launcher as:

```text
~/.local/share/applications/com.peclark.TapeFileBrowser.desktop
```

On GNOME/Ubuntu it also attempts to add **Tape File Browser** to the dock/favorites. To install without changing the dock:

```bash
bash install.sh --no-pin
```

For a server with no X/GTK libraries, install the text-mode interfaces only:

```bash
bash install.sh --text-mode
```

That installs the tape CLI/TUI, the experimental `as400-dasd` CLI, and their shared parser modules while skipping the GTK application, desktop launcher, and GNOME integration. `--headless` remains accepted as a compatibility alias for `--text-mode`.

## Screenshots

### GTK4 GUI
<img width="2616" height="1658" alt="Tape File Browser GTK4 GUI" src="https://github.com/user-attachments/assets/5a3ceea0-3551-4d70-a549-532b5fd33bba" />

### TUI
<img width="3560" height="2422" alt="Tape File Browser Text Mode UI" src="https://github.com/user-attachments/assets/d01c317c-0231-4ba4-a09c-c59ef82c398e" />

## Run without installing

```bash
python3 tape-file-browser.py
```

You can also open one or more images directly:

```bash
python3 tape-file-browser.py MULIC-pass3.tap
python3 tape-file-browser.py MULIC-pass3.tap MULIC-pass3.aws
```

After installation:

```bash
tape-file-browser MULIC-pass3.tap
```

### GTK4 graphical interface (GUI)

The GUI uses the same workspace model as the TUI: **Images**, **Tape files**, and **Records** across the upper portion of the window, with a full-width **Record view / Compare results** pane below.

**Open…** accepts multiple tape images at once. Each open image keeps its own tape-file and record position when you switch between images. Check two or more images in the Images pane and click **Compare** to run the same logical tape verification used by the CLI/TUI. **Close** removes only the active image from the workspace, while **Convert…** operates on the active image.

For the TUI:

```bash
tape-tool browse
tape-tool browse MULIC-pass3.tap
tape-tool browse MULIC-pass3.tap MULIC-pass3.aws
```

With no filename, the TUI opens its file picker immediately. Press `o` at any time to open more tape images. The file picker supports marking multiple files with Space and opening them together. It shows an explicit `<DIR> ../` entry for the parent directory; Backspace is also available as a parent-directory shortcut.

The TUI uses three navigation panes across the upper portion of the terminal — **Images**, **Tape files**, and **Records** — with a full-width **Record view / Compare results** pane below them. The wider lower pane is intended for hex/EBCDIC data, long paths, and comparison output. Selecting an image switches the other panes to that image. Keyboard navigation always works; terminals with mouse reporting can also select images/files/records by clicking.

In the Images pane, Space marks an image for comparison. Mark two or more images and press `c`; each selected image is compared against the first selected image using the same logical record/payload verification as the CLI converter.

## Command-line interface (CLI)

`tape-tool` exposes the core without importing GTK:

```bash
tape-tool info MULIC-pass3.tap --hash
tape-tool files MULIC-pass3.tap
tape-tool records MULIC-pass3.tap --file 4
tape-tool show MULIC-pass3.tap --file 4 --record 1
tape-tool show MULIC-pass3.tap --file 4 --record 1 --view hex
tape-tool browse MULIC-pass3.tap
```

To compare two or more containers record-by-record:

```bash
tape-tool compare MULIC-pass3.tap MULIC-pass3.aws
tape-tool compare original.tap copy1.aws copy2.tap
```

The first image is the reference. A successful comparison verifies logical file/tape-mark structure, every record length, and every record payload for each additional image.

## Experimental CISC AS/400 DASD explorer

The repository includes an experimental, read-only explorer for raw CISC AS/400 DASD images with 520-byte sectors. The storage-header/recovery model and the higher-level object/context/database reconstruction have been independently exercised against both the surviving B10/0671S15 image and a separate one-disk V2R3 image.

Current commands:

```bash
as400-dasd browse disk.hda
as400-dasd browse
as400-dasd info disk.hda
as400-dasd map disk.hda
as400-dasd regions disk.hda
as400-dasd sector disk.hda 12345
as400-dasd segments disk.hda
as400-dasd libraries disk.hda
as400-dasd objects disk.hda
as400-dasd ls disk.hda QGPL --type 19/01
as400-dasd files disk.hda QGPL
as400-dasd members disk.hda QGPL QCLSRC --long
as400-dasd source disk.hda QGPL QCLSRC REFRESH2
as400-dasd cat disk.hda QGPL QCLSRC REFRESH2
as400-dasd fields disk.hda QGPL PDPICKORG
as400-dasd dlos disk.hda
as400-dasd dlos disk.hda --model-fields
as400-dasd dlo-xref disk.hda FMPV082760 FMPV195818 DPWN524712
as400-dasd dlo-index-scan disk.hda
as400-dasd dlo-schema disk.hda --family QAOSSS14
as400-dasd dlo-paths disk.hda FMPV082760 FMPV195818
as400-dasd dlo-parent-gaps disk.hda --raw-scan
as400-dasd dlo-export disk.hda FMPV082760 CKPCSPTH.EXE
as400-dasd context-xref disk.hda QGPL
as400-dasd context-page disk.hda QGPL 0 --offset 0
as400-dasd records disk.hda QGPL PDPICKORG PDPICKDEMO --decoded
as400-dasd record disk.hda QGPL PDPICKORG PDPICKDEMO 1 --decoded
as400-dasd scan disk.hda --report dasd-report.txt
```

The current milestone can:

- browse a DASD image interactively in a three-pane curses TUI: libraries/views, files or MI object types, and members/objects, with a full-width content/detail pane;
- open another image from inside the TUI, search recovered names, inspect source members, browse raw/decoded database records, and inspect MI object metadata;
- validate exact 520-byte image geometry;
- expose each eight-byte header separately from its 512-byte CISC storage page;
- inspect individual sectors with hex and EBCDIC output;
- decode the five-byte virtual-page field into the 48-bit page-aligned virtual address while leaving unresolved indicator bits unlabeled;
- decode power-of-two extent sizes from the low nibble of the indicators byte;
- use IBM's preassigned large-free-space delimiter to infer device-relative record zero;
- reconstruct explicit free extents, permanent extent candidates, reclaimable-by-recovery regions, and candidate virtual chains;
- perform the second directory-recovery pass and reconstruct multi-extent segment groups;
- parse common EPA object headers from recovered primary segments;
- recover permanent contexts/libraries and assign objects to them through EPA context back-pointers;
- traverse ordinary release-2 permanent-context machine indexes, reconstruct
  compact object/member identities, cross-check context -> object membership
  against EPA object -> context back-pointers, and retain directory-only
  identities when an object primary is absent;
- list real `*FILE` objects and recovered members inside a library;
- follow member cursors through their direct QDDS/QDDSI pointers, retaining the expected storage address and surviving owned secondary segments even when a primary segment is missing from a partial multi-disk image;
- decode QDDSI DKEY/DKYT key specifications conservatively, including indexed data-space addresses, key counts/lengths, and raw key-field locations/attributes;
- audit **partial** QDDSI tree-key evidence by DKEY row in `as400-dasd member IMAGE LIB FILE MEMBER`: observe lengths, numerical gaps to declared machine-key length, and intact four-byte ordinal references without filling in missing key bytes;
- decode standard 92-byte AS/400 source physical-file records and print their source text;
- recover generic fixed-length QDDS ordinal records using the data-space entry count and entry length;
- identify MI 19/51 record-format objects and recover field names, record offsets, storage lengths, digits, decimal positions, and independently validated binary, zoned, packed, character, and DBCS-Open type mappings;
- decode recovered database records through those field definitions when a format object survives;
- preserve literal *FILE FCB format-name occurrences in on-disk order and expose exact internal-address matches as independent format-association evidence without assigning undocumented FCB field names;
- decode permanent database-member cursors (MI 0D/50), splitting the 30-byte cursor name into file/member names;
- decode the permanent cursor member header, including source type, descriptive text, source-change timestamp, and creation timestamp;
- resolve the documented load-source shadow-log virtual address `000083000000`; the independent one-disk image maps it to LBA 147,520 and contains exactly 64 KiB of nonzero payload there;
- inventory QDOC `*DOC`/`*FLR` DLOs, report any recovered QUSRSYS `QAOSS*` runtime search indexes, and separately identify QSYS DLO command model files;
- cross-reference a 10-character QDOC `SYSOBJNAM` byte-for-byte across recovered object segments to locate candidate index/metadata relationships without assuming their meaning;
- correlate every recovered QDOC `SYSOBJNAM` against recovered QAOSS member records, defaulting to the IBM-documented `QAOSSS14` anchor index;
- write a repeatable text report for comparison between real and initialized/replacement disk images.

On the surviving B10 D1 image, relative record zero is LBA 2,112. On the independent one-disk V2R3 image it is LBA 64. Both images use the same order-15 free-space delimiter and the same virtual-address/extent-size rules. Unknown flag bits remain explicitly unlabeled. The parser never writes to the image.

The second pass currently recovers about 12.7k segment groups from the surviving B10 disk and 43k from the independent V2R3 disk. On the latter it identifies roughly 31.5k EPA objects and 40 permanent contexts/libraries, including QSYS, QGPL, QUSRSYS, and QSYS2. QGPL can already be browsed offline; recovered `19/01` objects include QCLSRC, QCMDSRC, QDDSSRC, and other files. Library membership is now preserved from both independent directions: EPA object -> context back-pointers and permanent-context machine-index -> object references. The browser keeps disagreement evidence rather than silently reconciling it, and context terminals can preserve directory-only names/types/addresses when a primary object is missing from the image.

Source-member contents are now working as well. The real image yields readable CL, RPG, DDS, and COBOL source from recovered QDDS data spaces. On the surviving B10 disk, `PPSITEST/QLBLSRC(PROTO)` recovers 107 source lines. The recovered source identifies its author as `JT HUDGINS`, providing a strong preservation/provenance link to the machine's original consulting/programming use. Recovered source itself is not committed to the public repository.

The member parser is independently validated against a real QGPL/QCLSRC member named `REFRESH2`. It recovers source type `CLP`, the descriptive text `Refresh PkMS demo data - new version (GE 170)`, source-change time `1998-01-03 02:31:14`, and creation time `1998-01-03 02:31:11`.

Generic physical-file records are now working as well. The QDDS primary segment exposes the entry count and a cross-version fixed-entry length used by both the B10 and V2R3 images. The browser can therefore enumerate raw RRNs for non-source members and, when the MI 19/51 format object is available, decode fields. A real B10 `STAREC` format recovers `STASTAT` fields such as `STCOD`, `STNAME`, `MTD`, `YTD`, and `LYR`; the surviving records decode Missouri, Kansas, and "STATES OTHER THAN MISSOURI OR KANSAS" with their numeric statistics.

### IBM AS/400 object-type catalog

The DASD browser now recognizes **268 IBM-documented MI type/subtype
identifiers**: 102 external types and 166 internal types, from IBM's
published object-type tables. Recovered primary objects and directory-only
identities display familiar names such as `*CMD`, `*MENU`, `*OUTQ`,
`*DBRCVR` and `*INTPRF`. Guided 5250 marks internal types as
`[internal]` and retains `[dir] primary absent` for missing primaries.
Forensic details include the original MI code and the IBM classification
and description.

The source tables describe modern IBM i, **not a guaranteed V2R3
installation inventory**. Unknown codes remain raw; no objects or data are
invented. A historical IBM V5R4 PDF independently confirms corrected
hexadecimal values for two typographical errors in the modern web table.

Look up codes without scanning a disk image:

```bash
as400-dasd types 19/D4
as400-dasd types 0E/C4
as400-dasd types 19/16
as400-dasd types --category internal
```

See [object-type catalog documentation](docs/AS400_OBJECT_TYPE_CATALOG.md)
for the IBM source URLs, category distinctions, data files, and maintenance
rules. The install script includes both type tables.

### MI decoding inventory and research roadmap

To coordinate work on all IBM MI object types, the repository now has a
[complete 268-type decoder progress inventory](docs/MI_OBJECT_INVENTORY.md),
a [research/implementation roadmap](docs/MI_RESEARCH_ROADMAP.md), and a
machine-readable audited review registry (research/mi_object_reviews.json).
These track **what is actually decoded** separately from mere recognition
of a documented object name. The first conservative audit reviews 28 types;
the remaining 240 intentionally read **Catalog only** until individually
audited. Draft *CMD parameter PR #15 is not merged and is not counted as
a main-branch decoder.

Inspect or regenerate the inventory from the source checkout:

```bash
python3 tools/mi_object_inventory.py --format summary
python3 tools/mi_object_inventory.py --type-code 19/05
python3 tools/mi_object_inventory.py --format markdown > docs/MI_OBJECT_INVENTORY.md
python3 tools/mi_object_inventory.py --check-report
```

The 18 historical PDF filenames and initial page-level citations are
tracked in research/manual_sources.json. We ran an initial full
**18-PDF exact-object-name lexical scan**, yielding **764 matches across
86 IBM object-type names**. Those are only page leads; five PDFs have
selected pages independently reviewed so far. See
[the first-pass manual scan findings](docs/MI_MANUAL_SCAN_FIRST_PASS.md)
for the results and method limitations. PDF files and source disk images
are **not** committed to the repository.

For offline *unverified lexical leads* in the supplied PDF archive:

```bash
python3 tools/mi_manual_scan.py --archive "/path/to/as400 manuals.zip" \
  --redbook "/path/to/AS400_Disk_Storage_Topics_and_Tools_sg245693.pdf" \
  --output /tmp/mi_manual_hits.json
```

Every lexical hit requires human review before a page is cited as
support for an object field, relationship or API. This tool does not
perform OCR or silently treat an API receiver format as an on-disk
CISC object format.

### Full 268-type MI image survey and research prioritization

The [full survey report](docs/MI_FULL_SURVEY_V1.md) compares all IBM
type labels with every candidate primary found in **both** historical
520-byte-sector disk images, our existing decoder audit, and the
historical PDF source index. Its
[complete weighted ranked list](docs/MI_SURVEY_PRIORITIES.md)
includes 268 types, individual factor scores, and raw signature
candidate counts. The model weights value 30%, dependency leverage
25%, research evidence 20%, feasibility 15%, coverage 10%.

The physical scanner is **read-only** and produces **aggregate-only**
results; it does not output object names or raw image data:

```bash
python3 tools/mi_full_primary_survey.py /path/to/marks.hda.zip \
  --output /tmp/marks-mi-survey.json
python3 tools/mi_full_primary_survey.py /path/to/petes.hda.zip \
  --output /tmp/petes-mi-survey.json

python3 tools/mi_survey_priorities.py --format summary
python3 tools/mi_survey_priorities.py --format json
python3 tools/mi_survey_priorities.py --check-report
```

The survey found **109 raw MI codes** across the two images, including
**106** names in the modern IBM catalog and three raw/unmapped codes
(0E/00, 19/C4, 19/ED). A missing physical signature is **not proof
of absence** from OS/400 or the disk. Candidate primaries can be stale
orphans; context-resolved live objects are a separate evidence tier.

The ranking is **provisional research planning**, not a validated
measure of complexity or a plan to decode 268 binary formats at once.
Edit research/mi_survey_scoring.json as additional evidence arrives
or the project's objectives change. No existing object decoder
is modified by this research branch.

### Historical CMD, MSGF, MENU and PGM research

The [interconnected object research](docs/MI_INTERACTIVE_OBJECT_RELATIONSHIPS.md)
records exact PDF-page evidence of command processing-program links,
parameters, message descriptions and display/menu associations.
A new read-only primary census tool can compare the four MI types
on either archived 520-byte-sector image, including zipped HDA files:

```bash
python3 tools/mi_primary_census.py "/path/to/marks.hda.zip"
python3 tools/mi_primary_census.py "/path/to/petes.hda.zip"
```

Results are **physical primary candidates**, not a list of active
objects, and the tool emits no recovered object names or raw contents.
No compiled MSGF/MENU/PGM binary field decoder is claimed by the
documentation. Draft command work in PR #15 is still separate.

### AS/400 user, device and mode object viewers (experimental)

The Guided 5250 Explorer now opens evidence-labeled, read-only screens
for recovered `*USRPRF` (08/01), `*DEVD` (10/01) and `*MODD` (15/01).
Select the object and press Enter (or use option 5). Option 8 still opens
generic object details. The command prompt recognizes the following
**non-executing** display operations:

```text
DSPUSRPRF USRPRF(QSYSOPR)
DSPDEVD DEVD(QCONSOLE)
DSPMODD MODD(QPCSUPP)
```

A name that resolves to multiple recovered primaries will be rejected as
ambiguous, not silently assigned to an arbitrary copy. Select its exact
primary in the object list. The viewers display independently recovered
identity and address metadata, owned-segment counts, and **same-name
objects as hints**, not as proof of a user/device relationship.
Device/mode evidence is bounded and unclassified; the on-disk attributes
are **not fully decoded**. The new `*USRPRF` viewer **does not read
or print raw authentication-bearing profile bytes**.

See [profile/device/mode research](docs/AS400_CONFIG_OBJECT_RESEARCH.md)
for the real V2R3 samples, nine-mode candidate offsets, provenance,
limitations and next validation steps.

### Cross-type Guided workflows (PR #21)

On [`feature/type-capability-workflows`, PR #21](https://github.com/peclark1/tape-file-browser/pull/21)
(stacked on pending #20), use `WRKTYP`
to browse all MI types and `WRKOBJ OBJ(*ORPHAN/*) OBJTYPE(*TBL)` to find
unassigned primaries. `DSPFD` opens selectable format candidates and fields;
9 on a member follows exact storage pointers and reverse member links.
`DSPTBL TBL(*ALL/QASCII) HEX(C1C2C3)` inspects a byte map and offline sample;
`DSPDTAARA DTAARA(*ALL/*)` displays supported character values by position.
`WRKOBJ OBJ(QDOC/*) OBJTYPE(*DOC)` follows candidate byte-string companions.

All operations are read-only. Shared browsing does not complete type decoding.
See [workflows and evidence](docs/TYPE_CAPABILITY_WORKFLOWS.md),
[the full 268-type capability queue](docs/MI_CAPABILITY_PROGRESS.md), and
[the current handoff](docs/WORK_MODE_HANDOFF.md) for limitations and PR state.

### Guided 5250 Explorer (first milestone)

The **guided 5250** mode uses the same read-only CISC DASD parser as the
three-pane forensic browser, but presents a familiar library -> object ->
member -> contents workflow. It is **not** a 5250 protocol emulator,
a live OS/400 installation, or a complete PDM implementation.

Start it without installing:

```bash
python3 as400_dasd_tool.py browse5250 marks.hda
```

Or after installing with `bash install.sh --text-mode`:

```bash
as400-dasd browse5250 marks.hda
as400-dasd browse5250                # choose an image
as400-dasd browse marks.hda          # original three-pane forensic UI
```

Navigation:
- Up/Down select an entry; Enter opens the selected library, file, or member.
- Type **12** then Enter to work with a selected library or file.
- Type **5** then Enter to display a selected member or object details.
- Enter (or **5**) on a recovered **`*CMD`** opens **Explore Command Definition**.
  Choose **Prompt form** for selectable linked labels, display hints and
  candidate defaults/value tokens. Enter opens the selected parameter's
  offsets and known/unknown fields. Summary shows origin and recovery failures;
  Evidence preserves tentative whole-command text. PGM matches follows candidate
  names without claiming a decoded processing-program pointer.
- `WRKCMD CMD(*ALL/CPY*)` searches recovered command identities across libraries.
  `DSPCMD CMD(QIWS/CPYTOPCD)` opens a specific definition; duplicate primaries
  remain separate, labeled by library and LBA. `WRKCMD CMD(*ORPHAN/*)` exposes
  commands whose library context could not be recovered.
- Parameters, defaults and commands cannot be entered or executed. Stored order
  is not verified historical F4 order; a valid keyword sequence does not prove
  that recovered identity and payload are semantically consistent.
- Type **8** on a command object to see ordinary object details instead.
- F4 opens the searchable command catalog with descriptions; type to filter,
  Up/Down to select, Tab to insert an example, Enter to run.
- Type a command directly or press `/` to enter one.
- F1/`?` gives help; F12, **Backspace** (when no numeric option is pending),
  or **Ctrl+B** goes back. F3 exits.
- Page Up/Down scroll entries or displayed member contents.

**Tilix note:** Tilix assigns F12 to its **View session sidebar** shortcut
by default. Reassign/disable that shortcut under Tilix Preferences > Shortcuts
to pass F12 to the browser, or use the Backspace / Ctrl+B alternatives.

Implemented **read-only** command subset: `WRKLIB`, `WRKLIBPDM`,
`WRKOBJ`, `WRKOBJPDM`, `WRKMBRPDM`, `DSPPFM`, `WRKCMD`, `DSPCMD`,
`DSPUSRPRF`, `DSPDEVD`, `DSPMODD`, `DSPFD`, `DSPTBL`, `DSPDTAARA`,
`WRKTYP` (explorer extension), and `HELP`.

Examples:

```text
WRKLIBPDM LIB(Q*)
WRKOBJPDM LIB(QGPL)
WRKMBRPDM FILE(QGPL/QCLSRC)
DSPPFM FILE(QGPL/QCLSRC) MBR(REFRESH2)
WRKCMD CMD(*ALL/CPY*)
DSPCMD CMD(QIWS/CPYTOPCD)
```

See [command exploration evidence and validation](docs/INTERACTIVE_COMMAND_EXPLORATION.md)
and [linked prompt browsing, research and limitations](docs/CMD_PROMPT_LINKS.md).

Only the listed subset and explicitly supported named parameters are accepted.
Other OS/400 commands, including live-job and destructive commands, are
**not executed**. Real recovered image data is shown, with **[dir]** for
directory-only identities and **[member-only]** when member cursors survive
without their file primary. Unrecoverable content is not fabricated.

The `*CMD` inspector uses a bounded 8 KiB virtual-order primary sample,
with at most 64 EBCDIC string clues. It does **not** execute commands or
interpret a plausible on-disk string as a validated parameter/default.
See [V2R3 *CMD research notes](docs/AS400_CMD_RESEARCH.md) for actual
specimen comparisons, tentative offset relationships, and evidence gates.

The guided renderer escapes any recovered NUL, ESC, or other control
characters for **display only** (for example, `\\x00`); the source bytes
are retained by the parser. This prevents damaged or unusual member contents
from crashing the curses terminal interface.

The type-label catalog also recognizes `19/E0` (`*ADO`), `0E/D1`
(`*DRX`), `19/EE` (`*MSCSP`), `0E/02` (`*OUTQ`) and
`19/06` (`*TBL`). The first three are **internal** system
object types, not ordinary user-facing PDM objects; the labels are
type identifications, not claims that their contents can be decoded.

The guided UI and existing forensic UI remain separate during evaluation.
No raw image contents are committed to public repository fixtures.

### AS/400 DASD text-mode browser

The interactive DASD browser uses only the Python standard-library `curses`
module, matching the project's existing tape TUI. No Textual/GTK/X dependency
is required.

Open an image directly:

```bash
as400-dasd browse petes.hda
```

Or start with the file picker:

```bash
as400-dasd browse
```

The upper half of the terminal keeps the proven three-pane navigation model,
but the presentation now follows the recovered AS/400 object model more closely:

1. **Library / view** — recovered libraries plus `<ALL OBJECTS>` and
   `<ORPHANS / MEMBER-ONLY>`.
2. **File / object type** — files for a selected library or grouped MI object
   types.
3. **Member / object** — member cursors, recovered objects, and context-directory
   entries whose primary object is missing.

A breadcrumb immediately below the title keeps the complete navigation path
visible, for example `marks.hda > QGPL > QCLSRC > REFRESH2`.
Directory-only context terminals are now grouped beside primary-backed objects
by MI type rather than hidden in a separate catch-all bucket; they remain
explicitly marked `[dir]`. Mixed lists are sorted by logical AS/400 identity
first, with recovery state used only as a secondary distinction; normal
primary-backed entries therefore do not carry a generic "recovered" badge.

The lower pane is a purpose-specific inspector with six views:
**Summary, Data, Keys, Storage, Evidence, and Raw**. Summary emphasizes what the
selected AS/400 item is; Data shows source/database or decoded document content;
Keys isolates QDDSI/context-index evidence; Storage shows QDDS/QDDSI and
recovered segment groups; Evidence keeps recovery provenance and literal
cross-reference evidence separate from normal browsing; Raw retains bounded
hex/EBCDIC forensic access. The active view stays visually distinct even when a
navigation pane has keyboard focus. Views with no meaningful data are dimmed
but remain selectable so the absence is explicit. Selection changes choose a
useful default (for example Data for source/database members and Evidence for a
directory-only identity), while a manual inspector choice remains in effect
until the logical selection changes.

Standard source members are shown as source lines in the Data view. Other QDDS
members show the recovered field layout plus decoded records; when all decoded
fields are blank, the browser includes raw EBCDIC and hexadecimal bytes instead
of leaving an apparently empty RRN line. The leading per-entry byte is labeled
**DENT** (Data Space Entry Status) rather than generic "status". In the current
V2R3 corpus, 0x80 is independently validated as the ordinary live/valid form
and 0xC0 as the deleted form, with 0x40 accounting for that observed state
difference; other documented DENT states/bits remain raw until independently
established.

Program objects (`*PGM`) now get a forensic program view: recovered owned
segments, printable EBCDIC strings from the primary-segment prefix, and a
hex/EBCDIC view of the first 512 bytes. The browser does not pretend this
is source code or a decoded instruction stream; program-template, instruction
stream, and ODT decoding remain separate reverse-engineering work. `*USRPRF`
and `*MSGQ` objects get semantic-first views with owned-segment/text evidence
before their raw prefix. On the real B10 `JHUDGINS` sample, the `*MSGQ`
EPA+0x38 internal address resolves exactly to the recovered same-name
`*USRPRF` owning-object address; the browser exposes that observation while
leaving the field's formal meaning unnamed until independently documented.
Other object types without a specialized decoder get a smaller hex/EBCDIC
raw-object prefix so they are still inspectable instead of producing metadata
only. Format objects show their recovered field descriptions.

The breadcrumb plus three navigation panes keep parent context visible even
when a child item is automatically selected. The inspector follows the focused
hierarchy level: focus the left pane for the selected library, the middle pane
for a file/object type, or the right pane for the selected member/object.
Focusing the inspector retains the deepest selected item. Inspector views can
be changed with `[`/`]` or directly with keys `1` through `6`.

For a recovered `*FILE`, the Evidence view also shows the exact FCB byte
offsets where each recovered 19/51 format name occurs and, when present, the
independent internal-object-address occurrence. This keeps a convenient
multi-format view without pretending that undocumented FCB field offsets or
semantics have been decoded.

Library descriptions are loaded from the editable `as400_libraries.json`
catalog rather than being hard coded in the TUI. The catalog is seeded with every library currently recovered in
the Mark-P02 file/member inventory, plus several common system libraries such as
QDOC, QUSRSYS, QHLPSYS, and QTEMP. Descriptions are researched from period IBM
documentation where possible. Each catalog entry also carries a functional
`category` and an evidence `status` (`documented`, `inferred`, or
`research-pending`). The TUI prefixes library context with the category and
shows the evidence status when the meaning is not yet documented.

For example, QGPL is identified as the General Purpose Library, QIWS as the
PC Support/400/host-server library, QMU400 as the OS/400 System/36 Migration
Assistant library, and QDOC as the QDLS/document-library backing library rather
than a source library. The browser also explains *DOC/*FLR objects and the
QDDS/QDDSI/member relationship. The object detail view repeats known roles so
the recovered structure is useful as an AS/400 learning aid as well as a forensic
browser.

The browser also carries a small amount of file-specific context where period
IBM documentation gives us an exact identification. For example,
`QGPL/QAAPFILE` is labeled as the AFP Utilities **symbol-set symbol-definitions
logical file**. Its members can therefore legitimately lack an independent QDDS
record stream; the TUI explains that condition instead of reporting it as an
undifferentiated recovery failure. The related `QAAPFILE$`, `QAAPFILE#`, and
`QAAPFILE@` entries are labeled as the small, medium, and large symbol-set
definition files respectively.

When installed, the base catalog is copied to:

```text
~/.local/share/tape-file-browser/as400_libraries.json
```

An optional user override can be placed at:

```text
~/.config/tape-file-browser/as400_libraries.json
```

Only the entries or fields being added or changed need to be present in the
override file; fields are merged over the base catalog so changing a description
does not discard its category or evidence status. Set
`AS400_DASD_LIBRARY_CONFIG` to use an additional catalog file with the highest
priority. Running directly from a source checkout also reads the repository copy
beside `as400_dasd_tool.py`.

Keys:

```text
← / → / Tab     change pane
↑ / ↓           move selection or scroll inspector content
PgUp / PgDn     page through lists/inspector content
Home / End      first/last item or top/bottom of inspector content
Enter           drill into the next pane / inspector
[ / ]           previous / next inspector view
1 .. 6          Summary / Data / Keys / Storage / Evidence / Raw
? / h           built-in help, terminology, and recovery-state glossary
/               search names across recovered objects/members
e               export selected QDOC document / *DOCBSS workstation bytes
o               open another DASD image
r               rescan the current image
q / Esc         quit
```

The browser is completely read-only with respect to the DASD image. When a
selected QDOC `*DOC` has a unique, validated same-base `*DOCBSS` companion,
the detail pane shows **DLO export: available (press e)**. Pressing `e`
prompts for an output filename, validates the DOCBSS length metadata again,
refuses to overwrite the DASD image, and asks before replacing an existing
output file. A `*DOCBSS` object can also be selected directly and exported
through its matching QDOC document.
When the selected QDOC document has a unique QAOSSS14 anchor correlation, the
detail pane also shows the recovered QAOSSS14 RRN, 12-byte short name, longer
name/title, and complete or partial reconstructed QDLS path. Export prefers the
QAOSSS14 short name as its default filename. If no anchor mapping is available,
the older conservative printable-metadata filename hint remains the fallback.

For QDLS/document-library work, `as400-dasd dlos disk.hda` lists recovered
QDOC `*DOC`/`*FLR` objects using their 10-character internal system object
names and shows short printable EBCDIC metadata hints. IBM recovery
documentation names the document/folder search-index files explicitly as
`QUSRSYS/QAOSSS10` through `QAOSSS15`, plus `QAOSSS17` and
`QAOSSS18`; `dlos` now reports the recovery status of each one separately.
It also distinguishes QSYS command model files such as `QAOSIQDL`,
`QAOSIRTV`, `QADSPDOC`, and `QADSPFLR`. Use `--model-fields` to
show recovered MI 19/51 field definitions for those models.

`as400-dasd dlo-xref disk.hda FMPV082760 FMPV195818 DPWN524712` searches
other recovered object segments for byte-level references to several QDOC
`SYSOBJNAM` values in a single recovery pass. IBM specifically documents an
"anchor record" in `QAOSSS14` as one of the places that stores the DLO system
object name, so objects containing many such references are especially useful
candidates even when their normal library/file relationship has not yet been
reconstructed. The tooling deliberately does **not** label printable strings or
cross-references as proven QDLS paths until the relevant structures are decoded.

For recovered documents with an IBM `*DOCBSS` (MI `06/C1`) companion,
`as400-dasd dlo-export IMAGE SYSOBJNAM OUTPUT` can now extract the workstation
byte stream conservatively. The V2R3 layout has a metadata page followed by the
byte stream; two observed length fields must agree and the payload must fit the
recovered segment before export is allowed. Existing output files are not
replaced unless `--force` is supplied. This does not yet reconstruct the
user-facing QDLS path, so export is addressed by the 10-character internal
SYSOBJNAM.

`as400-dasd dlo-index-scan disk.hda` remains the literal EBCDIC
SYSOBJNAM probe. The V2R3 QAOSSS14 records do not expose the useful QDOC
correlation as a plain 10-character name; the recovered relationship instead
uses an 8-byte `WOSEFILD` value embedded in the QDOC object's bytes.

`as400-dasd dlo-paths disk.hda [SYSOBJNAM ...]` performs that decoded
correlation. The recovered QUSRSYS/QAOSSS14 QDDS has 193-byte records.
Repeated `WOSFMT14/QAOSSS14` descriptors provide the field offsets and
lengths, and a unique `WOSEPLDN -> leading-record-key` link is followed as a parent
relationship. The command reports complete and partial **QAOSSS14 anchor
hierarchies** while retaining the internal QDOC SYSOBJNAM. On the real V2R3
image the PC Support examples independently agree with the known user-facing
names, producing `QIWSFLR/CKPCSPTH.EXE` and
`QIWSFL2/DTAQ.PKG`. Other anchor short names are not automatically treated
as QDLS folder names; for example the BULLET1 parent anchor is `QGFSWOF1`
while independent QDOC evidence identifies the user-facing folder as
`BULLETIN`.

`as400-dasd dlo-parent-gaps disk.hda` isolates QAOSSS14 records whose
nonzero parent key does not resolve uniquely through another record's leading
key. With `--raw-scan`, it searches for each exact eight-byte key elsewhere
in the DASD image and reports the raw offset/LBA plus the recovered
segment/object containing the hit when possible. This keeps the exceptional
cases separate from the leading-key rule that already resolves almost all
other anchor records.

`as400-dasd dlo-schema disk.hda` scans the raw image for literal IBM
`WOSFMTxx` metadata associations without loading the whole DASD image into
memory. It defaults to `WOSFMT14` and reports the nearby 8-character field
identifier plus concatenated `QAOSS*`/`WOS*` identifiers exactly as stored.
It now also reports the repeated big-endian descriptor offset/length values;
for QAOSSS14 these reproduce the 193-byte record layout as 1-based field
offsets and lengths. Use `--family QAOSSS14` or `--family QAOSSY14` to
isolate one observed descriptor family. Unknown abbreviations are deliberately
left unexpanded.

See `docs/AS400_DASD_MILESTONE1.md` for the research/validation plan,
`docs/AS400_DASD_TODO.md` for the active backlog, and
`docs/AS400_QDLS_RESEARCH.md` for the current documented facts, observations,
and QDLS experiments.

## Converting tape images

With an image open in the GUI, click **Convert…**. A SIMH image defaults to an `.aws` output name and an AWS image defaults to `.tap`.

The preferred headless conversion interface is:

```bash
tape-tool convert MULIC-pass3.tap MULIC-pass3.aws
tape-tool convert MULIC-pass3.aws MULIC-pass3-roundtrip.tap
```

The GTK executable also retains its command-line conversion option when GTK is installed.

After writing the output, Tape File Browser reopens it and verifies:

- logical file count
- tape-mark count and placement
- record count in each logical tape file
- every record length
- SHA-256 of every record payload

The completion report also includes a logical-tape SHA-256 that is independent of SIMH/AWS container framing.

### Metadata that cannot map directly

Record payloads and tape marks map cleanly between the two formats. Some SIMH-specific metadata does not have an AWS equivalent:

- SIMH error-record flags are reported as a warning and omitted from AWS metadata; record payload bytes are preserved.
- SIMH gap markers are reported as a warning and omitted.
- A SIMH EOM marker maps naturally to physical end-of-file in AWS.

AWS uses 16-bit chunk lengths. Records larger than 65,535 bytes are emitted as standard multi-chunk AWS records and reassembled transparently by the browser.

## Display format

The text pane decodes each selected record using IBM EBCDIC code page 037. Printable characters are displayed normally and control/non-printable characters are shown as periods.

For example, standard IBM tape labels become immediately readable:

```text
0000: VOL1VOL01 0                         B10C28000100...
0040: HDR1QFILEMCD.0000.B10VOL01...
```

Binary portions of AS/400 save data will naturally still appear mostly as periods or apparently arbitrary characters. Browsing never modifies the image.

## Tape container handling

### SIMH `.tap`

Tape File Browser understands the standard SIMH record framing used by the project's tape capture tools:

- 32-bit little-endian record length header
- record payload
- optional pad byte for odd-length records
- matching 32-bit record length trailer
- zero-length tape marks
- end-of-medium and gap markers
- SIMH error-record flag

### AWS `.aws`

AWS records use a 6-byte little-endian block header:

- 16-bit current chunk length
- 16-bit previous chunk length
- flags byte 1
- flags byte 2

The browser recognizes NEWREC, ENDREC, and tape-mark flags and can assemble records spanning multiple AWS chunks.

## Tests

The standard-library unit tests cover SIMH/AWS round trips, warning behavior for nonportable SIMH metadata, multi-chunk AWS records, AWS images without a trailing tape mark, the tape command-line tools, synthetic DASD/segment/object cases, sanitized real extent-header fixtures from both independent CISC AS/400 images, and selected real segment/EPA metadata, sanitized QDDS count/length scalars, and sanitized MI 19/51 field-descriptor prefixes from both real images. The fixtures contain no database/member record payloads or recovered source code. GitHub Actions runs the same suite on pushes and pull requests:

```bash
python3 -m unittest discover -s tests -v
```

## Uninstall

```bash
bash uninstall.sh
```

### Extended Guided workflows (experimental feature branch)

See [message/index/configuration/menu/directory workflows](docs/EXTENDED_TYPE_WORKFLOWS.md)
for `DSPMSGD`, `DSPCTLD`, `DSPLIND`, `DSPMNU`, keyed-record navigation, and
`WRKTYP TYPE(*QDIDX)` / `WRKTYP TYPE(*OIRS)`. These are read-only recovered
views with explicit missing/partial/candidate evidence. They do not execute CL.

Guided evidence workflows in PR #23 include `DSPJOBD`, `WRKJOBQ`, `DSPMSG`,
`DSPPGM`, and library recovery diagnostics (`WRKTYP TYPE(*LIB)`, then option 5).
See [extended workflows](docs/EXTENDED_TYPE_WORKFLOWS.md) for verified fields,
candidate relationships and unresolved storage. These operate on recovered
read-only evidence, not a running AS/400.

`DSPRCT` adds filtered reference-code index/record browsing. `DSPAFP` explores
embedded font, form-definition and page-definition fields, including coded-font
dependencies and explicit missing resources. Neither executes service actions
or renders/prints AFP resources.

### Saved OUTQ index browsing (offline)

Use `WRKOUTQ OUTQ(*ALL/QPRINT)` to inspect recovered 48-byte index keys. `FORM(*STD)` filters the observed EBCDIC candidate at key offset +0x20; `KEYHEX(C1)` filters exact key prefixes. Selecting a key shows its full hex/CP037 bytes. FA-prefixed control-like keys are counted separately; this is **not** a live spool queue, a spooled-file decoder, or a reconstruction of job order. Details and evidence limits: [OUTQ workflow](docs/OUTQ_WORKFLOW.md).

### Internal-profile identity explorer (offline)

Run `DSPINTPRF INTPRF(*ALL/*)` to browse recovered CISC internal-profile identities and follow exact-name user-profile candidates. The viewer uses only already recovered object identity metadata and never opens profile credential bodies. Missing or duplicated matches are reported without inventing pointers. See [evidence and limitations](docs/INTERNAL_PROFILE_WORKFLOW.md).

### Saved subsystem and class candidates (offline)

Use `DSPSBSD SBSD(*ALL/*)` to browse exact ten-byte padded-name occurrences referring to recovered `*JOBQ`, `*CLS`, and `*PGM` identities, or `DSPCLS CLS(*ALL/*)` for reverse candidate navigation. This is *not* decoded subsystem/class assignment; self-name echoes, duplicates and unknown ownership remain explicit. [Evidence and safeguards](docs/SUBSYSTEM_NAME_WORKFLOWS.md).

### Saved scheduler and service indexes (offline)

Use `DSPSCHIDX SCHIDX(*ALL/*)` and `DSPMSRVI MSRVI(*ALL/*)` to select recovered CISC machine-index key evidence, page through supported terminals, apply `KEYHEX(C1)`, and inspect opaque hex/CP037 bytes. Neither command decodes historical actions or service records. See [documented evidence limits](docs/ARCHIVAL_INDEX_WORKFLOWS.md).
