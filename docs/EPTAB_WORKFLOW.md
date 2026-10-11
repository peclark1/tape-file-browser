# CISC *EPTAB saved 16-bit word exploration

## What the Guided 5250 viewer can do

Use `DSPEPTAB EPTAB(*ALL/QDMEPTB) WORD(0045)` to select a
recovered 19/D7 `*EPTAB` object and browse a bounded **512-slot
big-endian unsigned 16-bit word region**. `WORD(0045)` searches
for an **exact four-hex-digit saved value**, not a character,
translation entry or source-code mnemonic. Leave `WORD` unset to
page through all 512 positions (50 rows per screen). Select any
saved word for its original primary byte offset, original two
hex bytes, zero-based slot index, integer value, and raw value
frequency. Back returns to the exact selected position.

The browser reports counts for raw words `0045`, `0000` and
other values, without asserting that `0045` is an empty value,
default glyph, or special control code. We do **not** yet know
whether this stored region is a character converter, editing
table, IBM internal state, or something else. The first four
saved words are demonstrably part of a fixed control prefix;
therefore **not all 512 positions can be called a mapping table**.

## Independently verified Mark/Pete archive evidence

There is one 19/D7 signature candidate, named `QDMEPTB`,
on each archived image. Each is a three-page saved primary.
The full +0x100..+0x5FF region is **byte-for-byte equal**
between Mark V2R3 and Pete B10 after reconstructing the
third page by its actual **virtual address**.

Pete's first two EPTAB data pages are physically adjacent,
but its third page is not:

| Source image | First physical page LBA | Next physical LBA | Actual third virtual page LBA |
|---|---:|---:|---:|
| Mark V2R3 | 1,858,680 | 1,858,681 | 1,858,682 |
| Pete B10 | 584,158 | 584,159 | **583,824** |

The third Pete page carries the correct next virtual sector address.
Reading the physically adjacent LBA 584,160 would instead bring in
bytes from a different segment. The independent source addresses
were checked read-only using each sector's five-byte virtual
address header; no original image was changed.

The corroborated saved region has:

- `+0x100..+0x107`: fixed eight-byte prefix
  `00 10 00 0E 00 0F 06 B0`
- `+0x100..+0x4FF`: 1,024 bytes, representable as
  exactly 512 consecutive u16 big-endian saved words
- `+0x500..+0x5FF`: 256 zero bytes in both objects,
  **not** included in the 512-word presentation

The saved 512 u16 words are identical across both original
archives. The empirical distribution is 301 words equal to
`0045`, 105 equal to `0000`, and 106 other word values;
74 distinct values overall. All positional words, including
the leading control prefix, are retained, not interpreted away.
Data outside the supported 19/D7 byte region remains opaque.

## Checks and remaining evidence gaps

`tests/test_eptab_workflows.py` exercises 512 exact slots,
corroborated prefix, exact hex value filtering, end offset,
50-word pagination through positions 500..511, selection/Back,
zero and repeated words, malformed header and short/virtual-gap
reconstruction. No actual image bytes are copied into these
fixtures.

`tools/validate_eptab_words.py <extracted-image.hda>` uses the
normal recovered-object inventory, SHA-256 before/after, selected
TUI view and Back, aggregate slot statistics, and a SHA-256
of the bounded saved word region to compare independent images.
The combined read-only acceptance tool also includes `19/D7`,
now nineteen recently advanced families.

Whole-image application recovered-object acceptance is still
pending until these validators are actually executed on each
archived HDA. No claim about CISC `*EPTAB` runtime semantics
or full object decoding is warranted by numerical patterns alone.
This remains a substantive **partial** Guided workflow.
