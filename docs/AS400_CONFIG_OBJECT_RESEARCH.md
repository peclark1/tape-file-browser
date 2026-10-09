# Original CISC AS/400 V2R3 profile / device / mode research

Status: **first read-only evidence viewer implemented; the three compiled
configuration-object formats are NOT decoded yet.**

## Historical documentation and logical interfaces

The original AS/400 reference manuals in this project describe *USRPRF
(user profile), *DEVD (device description), and *MODD (mode description);
these are different IBM MI classes, not three variants of a user record.
The 1992 AS/400 Primer and "Understanding AS/400 System Operations"
include the operator-facing Work/Display workflows.

IBM's documented logical commands are DSPUSRPRF, DSPDEVD and DSPMODD.
Later IBM APIs QSYRUSRI (USRI0100 and other formats) and QDCRDEVD
(DEVD0100 / category-specific formats) describe information that a
running system can return. **API receiver offsets are not demonstrated
to be the CISC 512-byte on-disk primary format.** They must not be applied
to the recovered bytes without independent validation.

Useful external references:
- https://www.ibm.com/docs/en/i/7.4.0?topic=ssw_ibm_i_74%2Fcl%2Fdspusrprf.html
- https://www.ibm.com/docs/en/i/7.5?topic=ssw_ibm_i_75%2Fapis%2Fqsyrusri.html
- https://www.ibm.com/docs/en/i/7.5.0?topic=q-retrieve-device-description-qdcrdevd
- https://www.ibm.com/docs/en/i/7.5.0?topic=d-display-mode-description

## Original-image evidence: Mark V2R3

We scanned the **unaltered raw image** for recovered-looking 512-byte
payload primary pages with correct EPA type/subtype in a page-aligned
position. This is a **physical candidate census**, not the fully
context-resolved object inventory and not an active-object count.

| MI type | Objects | Primary candidates observed |
|---|---|---:|
| 08/01 | *USRPRF | 43 |
| 10/01 | *DEVD | 42 |
| 15/01 | *MODD | 9 |
| 0E/C4 | *INTPRF | 17 |

Repeated names are observed among recovered primaries. The fact that an
object with a name survives does not establish current system account,
device assignment, or active status. A same-name USRPRF, INTPRF, MSGQ or
DEVD could be related, but **name matching does not prove pointer
relationships**. Our earlier *MSGQ -> *USRPRF EPA+0x38 investigation is
separate and does not prove these other links.

The nine 15/01 *MODD candidate primaries all exhibit an 8-byte EBCDIC
value at the primary's virtual-order **+0x120** that matches the first
eight characters of their recovered object name. A second 8-byte value
at +0x12C is usually "#CONNECT" but sometimes repeats a named mode.
This is robust **observed text placement**, not proof of the real
field's meaning, pointer semantics, or a universal version-invariant
layout. The viewer only reports these as candidates.

42 *DEVD candidates span display, printer, communications and other
names. EBCDIC strings sometimes appear in their first four pages, but
the layout is not yet independently correlated to device category,
model, or attached controller. The viewer displays a capped
**unclassified string sample**, never invented IBM field labels.

*USRPRF primaries can contain authentication/secrets. To avoid
unnecessary exposure, the dedicated view **does not sample or dump
any raw profile primary bytes**. It only displays recovered EPA identity,
virtual/physical address metadata, owned-segment metadata, and separately
recovered same-name object references. It never exposes passwords,
password hashes or profile bytes as text. Full security/profile field
decoding needs carefully reviewed and explicitly safe named-field parsers.

## Guided 5250 implementation

Enter or option 5 on a recovered *USRPRF, *DEVD or *MODD opens the
dedicated, read-only object-information display. Option 8 still shows
generic object details. F12/Backspace/Ctrl+B goes back.

The command prompt also accepts the implemented **non-executing**
subsets DSPUSRPRF USRPRF(name), DSPDEVD DEVD(name) and DSPMODD MODD(name).
Only exact recovered MI types are used. Multiple same-name object
primaries produce an ambiguity message; the user must navigate to the
individual recovered object in the list rather than have a stale
version silently selected.

- Shared formatter: as400_config.py; three supported exact MI pairs.
- The DISK reader takes at most 2,048 bytes of a DEVD/MODD primary.
  It reads **zero** raw USRPRF bytes.
- Non-profile display strings are bounded to 14 runs, 88 chars each,
  with original offsets, and are explicitly UNCLASSIFIED.
- Forensic object identity comes from common EPA/segment recovery;
  any duplicate, missing or incomplete primary remains visible with
  appropriate provenance.

## Next evidence gates for genuine on-disk decoding

1. For *USRPRF: identify fields independently using known historical
   profiles, period-correct DSPUSRPRF listings if obtainable, and repeated
   size/pointer structures. Do NOT identify, export, or present credential
   structures. Candidate decoded fields must be safe, repeatable, and
   cross-object validated.
2. For *DEVD: compare at least one identifiable *DSP and one *PRT or
   *TAP device against real-era CRTDEVD*/DSPDEVD listings, then verify
   category/model/controller representations in multiple objects.
3. For *MODD: establish the actual semantic meaning of observed
   +0x120/+0x12C fields from independent evidence and compare all
   nine specimens. Do not equate printed strings with parameters.
4. Integrate positively validated named fields into each viewer
   **after** testable byte-level documentation and synthetic
   negative/corruption fixtures; leave unverified data raw.
5. Check secondary owned segments and context-index membership for
   correlations without assuming linear physical sector continuation.

No original disk image/user-profile data, extracted account names, or
other real object bytes belong in public repository fixtures.
