# Tape File Browser

A small GTK4 desktop application for browsing SIMH and E11-style `.tap` tape images, written for IBM System/36 and AS/400 archival work.

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
- Summarizes record sizes, tape marks, logical EOT, EOM, and gap markers
- Auto-detects SIMH padding versus E11 unpadded odd-length records
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

## SIMH / E11 `.tap` handling

Tape File Browser understands both closely related 32-bit tape-image layouts:

- SIMH: odd-length record payloads are padded to an even byte boundary
- E11: odd-length record payloads are not padded
- 32-bit little-endian record length header and matching trailer
- zero-length tape marks
- double tape mark as logical end-of-tape
- end-of-medium and gap markers
- SIMH error-record flag

The two layouts are identical until an odd-length record is encountered, so the
browser auto-detects the variant at the first odd-length record.

## Uninstall

```bash
bash uninstall.sh
```
