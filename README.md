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

A contextual information line above the normal status line explains the selected
library, file, member, or MI object type as you browse. The library notes are
researched from period IBM documentation where possible: for example QGPL is
identified as the General Purpose Library, QIWS as the PC Support/400 host/server
library, and QDOC as the QDLS/document-library backing library rather than a
source library. Tentative identifications remain explicitly labeled as such instead
of being presented as fact. The browser also explains *DOC/*FLR objects and the
QDDS/QDDSI/member relationship. The object detail view repeats known roles so
the recovered structure is useful as an AS/400 learning aid as well as a forensic
browser.

Keys:

```text
← / → / Tab     change pane
↑ / ↓           move selection or scroll content
PgUp / PgDn     page through lists/content
Home / End      first/last item or top/bottom of content
Enter           drill into the next pane
/               search names across recovered objects/members
o               open another DASD image
r               rescan the current image
q / Esc         quit
```

The browser is completely read-only.

See `docs/AS400_DASD_MILESTONE1.md` for the research/validation plan.

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
