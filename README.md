# Tape File Browser

Tools for browsing, inspecting, comparing, and converting SIMH and AWS tape images, written for IBM System/36 and AS/400 archival work.

The project has three layers:

- `tape_formats.py` — headless parsing/conversion core with no GUI dependency
- `tape-tool` — command-line tools plus an interactive curses text-mode browser
- `tape-file-browser` — GTK4 desktop browser

Browsing is read-only. Conversion writes a new output image and then reopens it to verify the logical tape structure and every record payload before reporting success.

## Features

- GTK4 desktop interface
- Headless command-line interface requiring no X/GTK libraries
- Interactive curses text-mode browser for SSH/server use
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

The headless core and `tape-tool` use only the Python standard library. On normal Linux Python installations, the curses module is included as well.

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

The normal installer installs both the GTK browser and headless tools:

```text
~/.local/bin/tape-file-browser
~/.local/bin/tape-tool
~/.local/bin/tape_formats.py
~/.local/bin/tape_text.py
```

and installs a desktop launcher as:

```text
~/.local/share/applications/com.peclark.TapeFileBrowser.desktop
```

On GNOME/Ubuntu it also attempts to add **Tape File Browser** to the dock/favorites. To install without changing the dock:

```bash
bash install.sh --no-pin
```

For a server with no X/GTK libraries, install only the headless tools:

```bash
bash install.sh --headless
```

That installs `tape-tool` plus the shared parser/converter modules and skips the GTK application, desktop launcher, and GNOME integration.

## Run without installing

```bash
python3 tape-file-browser.py
```

You can also open either format directly:

```bash
python3 tape-file-browser.py MULIC-pass3.tap
python3 tape-file-browser.py MULIC-pass3.aws
```

After installation:

```bash
tape-file-browser MULIC-pass3.tap
```

For the text-mode browser:

```bash
tape-tool browse MULIC-pass3.tap
tape-tool browse MULIC-pass3.aws
```

The curses browser has three panes for logical files, records, and record contents. Use Left/Right or Tab to change panes, Up/Down and Page Up/Page Down to navigate, and `e`, `x`, or `b` for EBCDIC, hex, or both.

## Headless command-line tools

`tape-tool` exposes the core without importing GTK:

```bash
tape-tool info MULIC-pass3.tap --hash
tape-tool files MULIC-pass3.tap
tape-tool records MULIC-pass3.tap --file 4
tape-tool show MULIC-pass3.tap --file 4 --record 1
tape-tool show MULIC-pass3.tap --file 4 --record 1 --view hex
tape-tool browse MULIC-pass3.tap
```

To compare two containers record-by-record:

```bash
tape-tool compare MULIC-pass3.tap MULIC-pass3.aws
```

A successful comparison verifies logical file/tape-mark structure, every record length, and every record payload.

## Converting tape images

With an image open in the GUI, click **Convert…**. A SIMH image defaults to an `.aws` output name and an AWS image defaults to `.tap`.

The preferred headless conversion interface is:

```bash
tape-tool convert MULIC-pass3.tap MULIC-pass3.aws
tape-tool convert MULIC-pass3.aws MULIC-pass3-roundtrip.tap
```

The older GTK executable also retains its command-line conversion option when GTK is installed.

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

The standard-library unit tests cover SIMH/AWS round trips, warning behavior for nonportable SIMH metadata, multi-chunk AWS records, AWS images without a trailing tape mark, and the headless command-line tools:

```bash
python3 -m unittest discover -s tests -v
```

## Uninstall

```bash
bash uninstall.sh
```
