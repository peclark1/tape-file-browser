# Tape File Browser

A small GTK4 desktop application for browsing SIMH `.tap` tape images, written for IBM System/36 and AS/400 archival work.

The application is intentionally read-only. It indexes the SIMH tape structure, lets you browse logical tape files and individual records, and displays record contents as IBM EBCDIC CP037 text.

## Features

- GTK4 desktop interface
- Native file chooser for `.tap` images
- Three-pane browser:
  - logical tape files
  - records within the selected tape file
  - decoded EBCDIC contents of the selected record
- Displays record length and image/data offsets
- Highlights SIMH records carrying the error flag
- Summarizes record sizes, tape marks, EOM, and gap markers
- Indexes record offsets instead of loading the entire tape image into memory
- Desktop launcher for Ubuntu/GNOME
- Installer can pin the application to the Ubuntu/GNOME dock

## Requirements

On Ubuntu 24.04 or similar:

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

The installer copies the program to:

```text
~/.local/bin/tape-file-browser
```

and installs a desktop launcher as:

```text
~/.local/share/applications/com.peclark.TapeFileBrowser.desktop
```

On GNOME/Ubuntu it also attempts to add **Tape File Browser** to the dock/favorites. To install without changing the dock:

```bash
bash install.sh --no-pin
```

## Run without installing

```bash
python3 tape-file-browser.py
```

You can also open a tape image directly:

```bash
python3 tape-file-browser.py MULIC-pass3.tap
```

After installation:

```bash
tape-file-browser MULIC-pass3.tap
```

## Display format

The text pane decodes each selected record using IBM EBCDIC code page 037. Printable characters are displayed normally and control/non-printable characters are shown as periods.

For example, standard IBM tape labels become immediately readable:

```text
0000: VOL1VOL01 0                         B10C28000100...
0040: HDR1QFILEMCD.0000.B10VOL01...
```

Binary portions of AS/400 save data will naturally still appear mostly as periods or apparently arbitrary characters. The browser does not modify the image.

## SIMH `.tap` handling

Tape File Browser understands the standard SIMH record framing used by the project's tape capture tools:

- 32-bit little-endian record length header
- record payload
- optional pad byte for odd-length records
- matching 32-bit record length trailer
- zero-length tape marks
- end-of-medium and gap markers
- SIMH error-record flag

## COPYTAPE CPTP conversion

The repository also includes `cptp_to_simh.py` for old tape dumps made by
David S. Hayes' `copytape` utility.  Those dumps use a text-framed `CPTP`
format and can combine many original fixed 512-byte QIC blocks into one large
`CPTP:BLK` record.

The converter leaves the original `.img` files untouched, splits each CPTP
block back into 512-byte records by default, preserves tape marks, reconstructs
the terminal double tape mark represented by `CPTP:EOT`, and writes a separate
standard SIMH `.tap` image.

Convert one image alongside the original:

```bash
python3 cptp_to_simh.py V3R1M0_VOL001.img
```

This creates:

```text
V3R1M0_VOL001-fixed.tap
```

Convert an entire set into a separate directory:

```bash
mkdir -p converted
python3 cptp_to_simh.py -o converted V3R1M0_VOL*.img
```

The script refuses to overwrite existing output unless `--force` is given and
prints SHA-256 hashes for both source and converted images by default.  If a
CPTP data block is not divisible by the selected physical block size, conversion
stops rather than guessing.  Use `--block-size` only when the original tape's
fixed block size is known to be something other than 512 bytes.

## AS/400 tape-set validation

After conversion, `validate_as400_tapes.py` can scan a complete IBM Standard
Label tape set and report its structure without modifying any image.

For the six-volume V3R1M0 installation set:

```bash
python3 validate_as400_tapes.py \
    converted/V3R1M0_VOL001-fixed.tap \
    converted/V3R1M0_VOL002-fixed.tap \
    converted/V3R1M0_VOL003-fixed.tap \
    converted/V3R1M0_VOL004-fixed.tap \
    converted/V3R1M0_VOL005-fixed.tap \
    converted/V3R1M0_VOL006-fixed.tap
```

The validator reports:

- tape-image framing and record counts
- tape marks and logical end-of-tape
- `VOL1` volume identifiers
- `HDR1/HDR2`, `EOF1/EOF2`, and `EOV1/EOV2` labels
- each dataset's file id, sequence fields, block/record format, and data size
- cross-volume continuity when a dataset ends with `EOV1`

Optional machine-readable reports can also be written:

```bash
python3 validate_as400_tapes.py \
    --csv v3r1m0-report.csv \
    --json v3r1m0-report.json \
    converted/V3R1M0_VOL*-fixed.tap
```

Pass the volumes in physical volume order.  A cross-volume check is marked
`PASS` when an `EOV1` dataset continues on the next tape with the same file
identity and compatible sequence fields.  The final volume is flagged if it
still ends in `EOV1`, indicating that another volume appears to be required.

## Uninstall

```bash
bash uninstall.sh
```
