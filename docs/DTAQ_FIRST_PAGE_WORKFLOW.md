# Bounded saved CISC DTAQ first-page raw pairs

Three independent Mark V2R3 physical 0A/01 first-primary signature
candidates have EPA name `QNMACDQ` (LBA 1759088, 1871066, 1872555).
Pete B10 has no matching 0A/01 first-page primary candidates under
the conservative physical EPA signature scan; this is not proof of
historical OS/400 release absence.

One Mark first page begins `4000` at primary +0x100, two begin
`5000`. All three share a strict 12-byte control sequence
`50 00 00 00 00 10 00 00 00 10 00 00` at +0x140 and nine
16-byte raw pairs beginning +0x170. Each pair begins `6C00`,
ends `0000`, and contains two six-byte address-shaped values
with identical high three bytes within a pair. Across these
nine positions the first low-three-byte sequence ranges +0x160,
+0x170, ...,+0x1E0, while the second ranges +0x7B0,+0x750,
...,+0x4B0. Only **this exact nine-pair layout** is supported.

The next physical sectors **differ in layout across candidates**.
They are NOT proof of adjacent virtual pages or queue contents.
This feature never dereferences the saved bytes as verified MI
addresses or claims a decoded queue root, entry payload, depth,
capacity, FIFO/LIFO order, or current live state.

## User-visible Guided 5250 workflow

```text
DSPDTAQ DTAQ(*ALL/QNMACDQ)
DSPDTAQ DTAQ(*ALL/QNMACDQ) SLOT(9)
```

Select an original source by its library/LBA; inspect all nine
selectable saved raw records and drill into first/second exact
six-byte candidates and primary offsets, then Back. Navigate to
other same-name candidate primaries and compare relative low-three
byte pairs with independent identities preserved.

Unreadable/truncated or unsupported variants are withheld.
The source images are opened read-only and no raw saved data is
included in the tests, reports, or repository.

```bash
python3 -m unittest discover -s tests -p 'test_dtaq_workflows.py' -v
python3 -m unittest discover -s tests
python3 as400_dasd_tool.py browse5250 /path/to/marks.hda
```

The source first-page structural observations are independent raw
physical scans. Complete normal recovered virtual-object execution on
the original image and user terminal acceptance remain pending.
