# CISC OS/400 V2R3 command parameter-keyword evidence

This records the imported PR #15 evidence checkpoint. Current interactive
workflow, diagnostics and cross-image limitations: [capability record](INTERACTIVE_COMMAND_EXPLORATION.md).

Status: experimental, read-only, evidence-gated partial decoding of keyword
names/count/ordinals; **NOT** a complete PARM, prompt, or validation decoder.

## Empirical V2R3 layout

Analyzed first 8 KiB of eight recovered command primaries (seven distinct
names) on Mark's original raw V2R3 disk. All eight agree:

- Primary +0x17E contains a **variable nonzero byte** (usually 81, but
  also B9, 61, CA, D0 and other values); +0x17F is zero. The byte at
  +0x17E is NOT a fixed marker and its meaning is unknown. The apparent
  count is at +0x180, with +0x181 zero.
- First parameter-like keyword: primary +0x19C.
- Keywords occupy ten EBCDIC bytes, space-padded; immediately after
  each is a two-byte big-endian ordinal (00 01, 00 02, ...).
- Four zero bytes immediately precede each keyword.
- Subsequent keywords are at variable intervals (<128 bytes in this sample).

| Name / primary LBA | Count | Recovered ordered keywords |
|---|---:|---|
| CPYTOPCD / 1,448,288 | 9 | FROMFILE, TOFLR, FROMMBR, TODOC, REPLACE, TRNTBL, TRNFMT, RCDFMT, TRNIGC |
| CRTCMD / 73,304 | 27 | CMD, PGM, SRCFILE, SRCMBR, REXSRCFILE, REXSRCMBR, REXCMDENV, REXEXITPGM, VLDCKR, MODE, TYPE, ALLOW, ALWOBS, ALWLMTUSR, MAXPOS, PMTFILE, MSGF, HLPPNLGRP, HLPID, HLPSCHIDX, CURLIB, PRDLIB, PMTOVRPGM, AUT, REPLACE, TEXT, NATIVE |
| ADDPFM / 1,511,696 | 6 | FILE, MBR, EXPDATE, SHARE, TEXT, SRCTYPE |
| DSPCMD / 1,490,106 | 2 | CMD, OUTPUT |
| CALL / 1,516,822 | 2 | PGM, PARM |
| DLTCMD / 1,540,116 | 2 | CMD, TYPE |
| ADDACC / 77,808 | 2 | ACC, TEXT |
| ADDACC / 1,564,378 | 2 | ACC, TEXT |

The second ADDACC primary corroborates the pattern on separately located
storage. Some primaries contain additional, later name+ordinal sequences
that may represent nested definitions or other data. The new decoder
requires the exact first-keyword +0x19C anchor to reject such decoys.

## Broader physical-image census (corroboration beyond selected examples)

Using a read-only streaming scan of the complete physical sectors (520
bytes each), identified possible 19/05 EPA primaries. This counts raw
physical candidate pages, including possibly superseded objects, rather
than current, context-resolved operating-system commands.

| Raw disk image | 19/05 primary candidates | Nonzero +0x180 with first ordinal 1 | Zero-count candidates |
|---|---:|---:|---:|
| Mark V2R3 | 3,129 | 2,990 | 139 |
| Pete B10 | 1,117 | 1,069 | 48 |
| Combined | 4,246 | 4,059 | 187 |

Every nonzero-count candidate in **both** samples had its first keyword
ordinal at +0x1A6/+0x1A7 equal to 00 01. The high byte of the value
at +0x17E varies among candidates in *both* images; require it to be
nonzero and +0x17F to be zero, rather than accepting only 81 00.
The 187 zero-count cases need separate validation; do not assume they
have a decodable parameter table.

These single-primary-page checks corroborate the *opening* of the
structure, not all later variable-length descriptor links. Fully
recovering the remaining name/ordinal sequence was separately verified
on eight Mark command objects and three additional CPYFRMPCD primaries
whose nine descriptors can be read in physical contiguous order.
All three CPYFRMPCD cases yielded the same nine names: FROMFLR,
TOFILE, FROMDOC, TOMBR, MBROPT, TRNTBL, TRNFMT, TRNIGC, IGCSOSI.
The names also agree with the documented IBM command reference:
https://www.ibm.com/docs/en/i/7.5?topic=ssw_ibm_i_75%2Fcl%2Fcpyfrmpcd.html

## The CPYTOPCD reference

| Ordinal | Primary offset | Keyword |
|---:|---:|---|
| 1 | +0x019C | FROMFILE |
| 2 | +0x01C6 | TOFLR |
| 3 | +0x01F8 | FROMMBR |
| 4 | +0x023C | TODOC |
| 5 | +0x0280 | REPLACE |
| 6 | +0x02C9 | TRNTBL |
| 7 | +0x0312 | TRNFMT |
| 8 | +0x035B | RCDFMT |
| 9 | +0x039F | TRNIGC |

All nine names agree with the published IBM command reference:
https://www.ibm.com/docs/en/i/7.5.0?topic=ssw_ibm_i_75%2Fcl%2Fcpytopcd.html

The prior text scanner omitted TOFLR and TODOC: they are five-character
names, shorter than its six-character minimum. The new scanner permits
five characters, and the structural display shows all nine by exact
position and ordinal.

Other surviving strings include prompt-like text (From file, To folder,
From member, To document, Replace document, Translate table, Format of PC
data, Record format), special values (*CURLIB, *FIRST, *FROMMBR, *NO,
*YES, *TEXT, *NOTEXT), and IWS14xx IDs. Although embedded in the *CMD,
their pointer relationships and parameter validation/default semantics
are NOT YET DECODED.

**Ordering caveat:** the V2R3 CPYTOPCD ordinal list puts RCDFMT before
TRNIGC, whereas modern IBM i documentation displays these in the
opposite order. The V2R3 ADDPFM order also differs from the modern
published presentation (EXPDATE, SHARE, TEXT versus TEXT, EXPDATE,
SHARE). This could reflect OS/400 release differences, descriptor order
distinct from F4 prompt order, or something else. Do not assume the
on-disk ordinal always describes the interactive F4 display order.

Additional IBM reference for ADDPFM:
https://www.ibm.com/docs/it/i/7.4.0?topic=ssw_ibm_i_74%2Fcl%2Faddpfm.html

## Implemented partial decoder

The bounded helper candidate_parameter_keywords validates a nonzero
unknown byte at +0x17E and zero at +0x17F, one-byte count in the
range 1–64, ten-byte EBCDIC keyword,
four preceding zero bytes, exact two-byte ordinal, +0x19C anchor,
and unique subsequent matches within successive 256-byte windows.
A malformed, incomplete or ambiguous sequence results in **no decoded
parameter list**. It samples at most 8192 virtual-order primary bytes,
never writes an image, and has synthetic corruption/ambiguity tests.

The guided view shows count, keywords, ordinals and raw offsets. It
explicitly leaves types, defaults, prompts, validation rules and CPP
linkage undecoded. Unclassified EBCDIC text evidence remains available.

## Next research gates

- Identify variable-length descriptor boundaries and pointers
  independently in several commands; test against malformed inputs.
- Identify the actual relationship from keyword descriptors to IWS14xx
  prompt text and value/choice arrays, including nested QUAL/ELEM.
- Validate F4 prompt order against historical V2R3 output.
- Promote individual fields only after binary-structure corroboration;
  avoid source fabrication or guessed metadata.
- Eventually add an authentic, NON-EXECUTING command-prompt view.

Only aggregate findings, synthetic tests, and observations are committed.
Original disk bytes are not placed in the repository.
