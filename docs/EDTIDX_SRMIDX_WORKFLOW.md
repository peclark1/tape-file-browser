# Saved CISC EDTIDX and SRMIDX machine-index key exploration

## Independent physical-first-page observations

Read-only full 520-byte-sector EPA primary-signature scans found:

| Type | Mark V2R3 first-primary candidates | Pete B10 |
|---|---:|---:|
| 0E/D0 `*EDTIDX` | 4 | 0 |
| 0E/C8 `*SRMIDX` | 10 | 0 |

All four Mark 0E/D0 first pages have six exact raw bytes
`20 00 00 16 00 12` at primary +0x100. Their physically adjacent
+0x420 offsets preserve plausible six-byte saved root addresses,
and +0x42A gives 2048 bytes (`00000800`).

The Mark 0E/C8 first pages show three independently repeated
raw patterns at +0x100: `20 00 00 16 00 06`,
`20 00 00 16 00 0C` or `60 00 00 32 00 1B`.
Nine have physically adjacent +0x420 six-byte root-looking data
and +0x42A equal `00000800`; one late first-page candidate
has a zero physically adjacent +0x420 area, whose actual
virtual continuation **must not be guessed**.

These are observations of **physical raw sectors only**.
The live application reads the recovered virtual extents and
requires a strict supported primary header, a bounded root,
page size 1024 or 2048, and a valid release-2 machine-index
root traversal before offering any keys. Missing/stale roots
are withheld rather than silently replaced with physical
neighbors. Key bytes and stored tree order remain opaque;
no editor action or service-state semantics have been proven.

## Guided 5250

```text
DSPEDTIDX EDTIDX(*ALL/*) KEYHEX(C1)
DSPSRMIDX SRMIDX(*ALL/*) KEYHEX(C1)
```

The existing saved-index workflow now supports both types:
choose a specific recovered object origin, page through
50 reconstructed terminal keys, filter by a hex prefix,
inspect exact binary/CP037 display lenses and tree-terminal
offsets, then Back to the previous selection.

**Do not** call these editor commands, live service resources,
record bodies, ownership pointers or machine-index semantics.
No raw source-image sectors or recovered user data are in Git.

## Test and acceptance

```bash
python3 -m unittest discover -s tests -p 'test_archival_index_workflows.py' -v
python3 -m unittest discover -s tests
python3 as400_dasd_tool.py browse5250 /path/to/marks.hda
```

Synthetic tests cover all strict saved variants, corrupt headers,
unavailable roots, supported page sizes, navigation and Back.
The independent raw primary survey has **not yet** been replaced
by real recovered-object TUI testing on Mark and Pete.
