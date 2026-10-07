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

The `feature/as400-dasd-milestone1` work adds a read-only command-line explorer for raw CISC AS/400 DASD images with 520-byte sectors. The storage-header/recovery model is now independently validated against both the surviving B10/0671S15 image and a separate one-disk V2R3 image from Mark/Patrik.

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
as400-dasd dlo-export disk.hda FMPV082760 CKPCSPTH.EXE
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
- list real `*FILE` objects and recovered members inside a library;
- follow member cursors to QDDS/QDDSI storage;
- decode standard 92-byte AS/400 source physical-file records and print their source text;
- recover generic fixed-length QDDS ordinal records using the data-space entry count and entry length;
- identify MI 19/51 record-format objects and recover field names, record offsets, storage lengths, digits, decimal positions, and observed character/zoned/packed types;
- decode recovered database records through those field definitions when a format object survives;
- decode permanent database-member cursors (MI 0D/50), splitting the 30-byte cursor name into file/member names;
- decode the permanent cursor member header, including source type, descriptive text, source-change timestamp, and creation timestamp;
- resolve the documented load-source shadow-log virtual address `000083000000`; the independent one-disk image maps it to LBA 147,520 and contains exactly 64 KiB of nonzero payload there;
- inventory QDOC `*DOC`/`*FLR` DLOs, report any recovered QUSRSYS `QAOSS*` runtime search indexes, and separately identify QSYS DLO command model files;
- cross-reference a 10-character QDOC `SYSOBJNAM` byte-for-byte across recovered object segments to locate candidate index/metadata relationships without assuming their meaning;
- correlate every recovered QDOC `SYSOBJNAM` against recovered QAOSS member records, defaulting to the IBM-documented `QAOSSS14` anchor index;
- write a repeatable text report for comparison between real and initialized/replacement disk images.

On the surviving B10 D1 image, relative record zero is LBA 2,112. On the independent one-disk V2R3 image it is LBA 64. Both images use the same order-15 free-space delimiter and the same virtual-address/extent-size rules. Unknown flag bits remain explicitly unlabeled. The parser never writes to the image.

The second pass currently recovers about 12.7k segment groups from the surviving B10 disk and 43k from the independent V2R3 disk. On the latter it identifies roughly 31.5k EPA objects and 40 permanent contexts/libraries, including QSYS, QGPL, QUSRSYS, and QSYS2. QGPL can already be browsed offline; recovered `19/01` objects include QCLSRC, QCMDSRC, QDDSSRC, and other files. Library membership currently comes from the object's EPA context back-pointer; parsing the context machine index is the next independent cross-check.

Source-member contents are now working as well. The real Mark/Patrik image yields readable CL, RPG, DDS, and COBOL source from recovered QDDS data spaces. On the surviving B10 disk, `PPSITEST/QLBLSRC(PROTO)` recovers 107 source lines. The recovered source identifies its author as `JT HUDGINS`, providing a strong preservation/provenance link to the machine's original consulting/programming use. Recovered source itself is not committed to the public repository.

The member parser is independently validated against a real QGPL/QCLSRC member named `REFRESH2`. It recovers source type `CLP`, the descriptive text `Refresh PkMS demo data - new version (GE 170)`, source-change time `1998-01-03 02:31:14`, and creation time `1998-01-03 02:31:11`.

Generic physical-file records are now working as well. The QDDS primary segment exposes the entry count and a cross-version fixed-entry length used by both the B10 and V2R3 images. The browser can therefore enumerate raw RRNs for non-source members and, when the MI 19/51 format object is available, decode fields. A real B10 `STAREC` format recovers `STASTAT` fields such as `STCOD`, `STNAME`, `MTD`, `YTD`, and `LYR`; the surviving records decode Missouri, Kansas, and "STATES OTHER THAN MISSOURI OR KANSAS" with their numeric statistics.

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

The upper half of the terminal has three navigation panes:

1. **Libraries / views** — recovered libraries plus `<ALL OBJECTS>` and
   `<ORPHANS / MEMBER-ONLY>`.
2. **Files / MI object types** — files for a selected library, or grouped MI
   types in the object view.
3. **Members / objects** — member cursors for a selected file, or individual
   objects for a selected MI type.

The lower pane displays the selected content. Standard source members are shown
as source lines. Other QDDS members show record-layout information and either
decoded fields or raw EBCDIC record previews. Format objects show their recovered
field descriptions.

Three contextual information rows above the normal status line explain the
current selection in **each** navigation pane independently: library/view,
file/object type, and member/object. Selecting the first file or member
automatically therefore no longer hides the meaning of its parent library.
The row corresponding to the focused pane is emphasized. Library descriptions
are loaded from the editable `as400_libraries.json` catalog rather than being
hard coded in the TUI. The catalog is seeded with every library currently recovered in
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
↑ / ↓           move selection or scroll content
PgUp / PgDn     page through lists/content
Home / End      first/last item or top/bottom of content
Enter           drill into the next pane
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
