# QDLS / QDOC reverse-engineering notes

This note keeps **IBM-documented behavior**, **real-image observations**, and
**working hypotheses** separate while the DASD explorer reconstructs Document
Library Services (QDLS) metadata.

## IBM-documented facts

- QDLS presents document library objects (DLOs) as a folder/document hierarchy.
- DLOs in the system ASP are stored as internal objects in library `QDOC`;
  user ASPs use `QDOCnnnn`.
- The internal classes relevant here are `*DOC` and `*FLR`.
- The internal system object name (`SYSOBJNAM`) is a 10-character name unique
  on the system. It is not necessarily the user-facing QDLS name.
- A user-assigned document/folder name is at most 12 characters.
- A DLO also has a 24-character library-assigned document name (`DOCID`).
- `RTVDLONAM` can return a folder path up to 63 characters.
- IBM documents a set of database search-index files in `QUSRSYS` whose names
  begin with `QAOSS`; these files track the system's DLOs.
- IBM recovery documentation names the document/folder search-index files
  explicitly: `QAOSSS10` through `QAOSSS15`, plus `QAOSSS17` and
  `QAOSSS18`.
- IBM support documents a particularly strong structural clue: the DLO system
  object name is stored in the document header, document profile, the
  **"anchor record" in QUSRSYS/QAOSSS14**, and the entry in the parent folder
  that points to the document. `RCLDLO` synchronizes these copies.
- IBM support documents `QAOSSS18` as the file used to track documents that
  are checked in/out; its first eight bytes are the document's LADN and can be
  given to `DSPDLONAM DLO(*LADNTSP)`.
- Other `QAO*` files in `QUSRSYS` support distribution and text-search
  functions.
- IBM's MI object-type table identifies type/subtype `06/C1` as
  `*DOCBSS`, **Document byte string space**, a Document Library Services
  internal object class.


IBM references:

- https://www.ibm.com/docs/en/i/7.4.0?topic=objects-how-system-stores-uses-document-library
- https://www.ibm.com/support/pages/document-library-objects-dlo-information
- https://www.ibm.com/docs/en/i/7.5.0?topic=r-retrieve-document-library-object-name
- https://www.ibm.com/docs/en/i/7.6.0?topic=d-display-document-library-object-name
- https://www.ibm.com/docs/en/i/7.4.0?topic=changes-task-6-applying-journaled-qaosdiajrn-journal
- https://www.ibm.com/support/pages/where-system-name-stored-dlo
- https://www.ibm.com/support/pages/node/640501
- IBM System i Application Programming Interface (API) Concepts, MI object-type
  table (lists `*DOCBSS` as `06C1`).


## Important distinction: QUSRSYS runtime indexes vs QSYS model files

The current recovered Mark/Patrik file/member inventory contains several
DLO-related `QSYS` physical files such as:

| QSYS file | IBM-documented use | Record format |
| --- | --- | --- |
| `QADSPDOC` | `DSPFLR TYPE(*DOC)` output model | `DOCDTL` |
| `QADSPFLR` | `DSPFLR TYPE(*FLR)` output model | `FLRDTL` |
| `QAOSIQDL` | `QRYDOCLIB` output model | `OSQDL` |
| `QAOSIRTV` | `RTVDOC` output model | `OSRTVD` |

These are definitions/templates used when CL commands create output files.
They must **not** be mistaken for the `QUSRSYS/QAOSS*` runtime search indexes.

Direct raw-image and recovered-object inspection now locates
`QUSRSYS/QAOSSS14` itself on the V2R3 disk, so the earlier "not yet visible"
state is superseded. The exact recovered pieces are:

| Object | MI type | Virtual address | LBA |
| --- | --- | ---: | ---: |
| QAOSSS14 file | 19/01 `*FILE` | `00AC04000000` | 1,810,748 |
| QAOSSS14 member cursor | 0D/50 `*MEM` | `00AC13000000` | 1,506,920 |
| QAOSSS14 data space | 0B/90 QDDS | `00AC0A000000` | 1,812,520 |
| QAOSSS14 data-space index | 0C/90 QDDSI | `00AC0C000000` | 548,448 |

The recovered `*FILE` context pointer is `0001:000283000000`, the recovered
QUSRSYS library/context address. The QDDS header reports 1,885 user entries,
record length 193, and entry length 194 (one status byte plus the 193-byte
record).

IBM command/model-file references:

- https://www.ibm.com/docs/en/i/7.6.0?topic=cc-database-files-device-files-used-by-cl-commands
- https://www.ibm.com/docs/en/i/7.5.0?topic=q-query-document-library
- https://www.ibm.com/docs/en/i/7.4.0?topic=ssw_ibm_i_74/cl/dspflr.html
- https://www.ibm.com/docs/en/i/7.4.0?topic=ssw_ibm_i_74/cl/rtvdoc.html

## Period evidence for the QRYDOCLIB bridge

A 1992 MC Press utility uses `QRYDOCLIB` output to correlate QDLS documents
with `QDOC` objects. It states that the QRYDOCLIB output supplies system object
names together with folder/document names. Its `OSQDL` logical-file key uses
`QDLFLR` and `QDLDNM`, and its RPG code uses `QDLONM` to locate the
corresponding `QDOC` object-description record.

That is useful corroboration for our goal, but the explorer should still derive
field offsets/types from the recovered V2R3 `QAOSIQDL/OSQDL` format object
rather than hard-code a third-party layout.

Reference:

- https://mcpressonline.com/programming-other/cl/fat-folder-finder

## Real-image observations

The independent V2R3 image has recovered `QDOC` `*DOC`/`*FLR` objects
whose 10-character internal names include forms such as `FMPVnnnnnn` and
`DPWNnnnnnn`.

Examples already observed during this project include:

- `FMPV082760` with printable metadata containing `CKPCSPTH.EXE` and
  `S1011111`.
- `FMPV195818` with printable metadata including `DTAQ.PKG`.
- `DPWN524712` previously correlated to the user-facing DLO
  `BULLETIN/BULLET1.RFT`.
- Direct inspection of the complete V2R3 image independently reconfirmed that
  correlation: the `DPWN524712` object is followed in its recovered storage
  region by `BULLET1.RFT`, document text, and a document error-log entry that
  explicitly names document `BULLET1.RFT` and folder `BULLETIN`.
- The same image contains MI `06/C1` objects named `FMPV082760F` and
  `FMPV195818F`. IBM names this type `*DOCBSS` (Document byte string
  space). Their base names exactly match QDOC documents `FMPV082760` and
  `FMPV195818`; nearby DLO metadata names `CKPCSPTH.EXE` and
  `DTAQ.PKG`, respectively.
- No `DPWN524712F` companion was found in the same raw-image check. That is
  consistent with the possibility that RFT/Office documents and workstation
  byte-stream documents use different backing forms, but the distinction is
  still a hypothesis rather than a decoded rule.
- The V2R3 image also contains a dense IBM metadata/schema region naming
  `WOSFMT10` through `WOSFMT18` alongside `QAOSSS10` through
  `QAOSSS18`. Entries associated with `WOSFMT14/QAOSSS14` include field-like
  names such as `WOSEDOCN`, `WOSEDOCT`, `WOSESYSC`, `WOSEOWNR`, and
  others. This is strong structural evidence for the runtime DLO-index formats,
  but the binary descriptor layout is not decoded yet.
- The same V2R3 image also contains a parallel `QAOSSY14` descriptor family
  tied to `WOSFMT14`, with `QAOSSGxx` related identifiers where the
  `QAOSSS14` family uses `QAOSSIxx`. The suffix distinction is not yet
  interpreted; both are recorded as observations only.
- Exact field-like identifiers repeatedly associated with `WOSFMT14` include
  `WOSEDOCD`, `WOSEDOCT`, `WOSESYSC`, `WOSEDOCN`, `WOSESLVL`,
  `WOSEFILD`, `WOSECRTD`, `WOSELCDT`, `WOSEINTS`, `WOSEFDOC`,
  `WOSEPLDN`, `WOSEWIPI`, `WOSEIXDT`, `WOSEOCDT`, and
  `WOSEOWNR`. Their abbreviations are deliberately left unexpanded until an
  IBM definition or independent structural proof is found.
- The repeated descriptor words immediately following these identifiers decode
  consistently as **1-based field offsets and lengths** in the 193-byte
  QAOSSS14 record. The currently recovered layout is:

| IBM field id | 1-based offset | length |
| --- | ---: | ---: |
| `WOSEFILD` | 17 | 8 |
| `WOSEDOCD` | 25 | 4 |
| `WOSEDOCN` | 33 | 44 |
| `WOSEDOCT` | 77 | 2 |
| `WOSESYSC` | 83 | 13 |
| `WOSEOWNR` | 96 | 16 |
| `WOSEFDOC` | 112 | 12 |
| `WOSEPLDN` | 132 | 8 |
| `WOSEWIPI` | 142 | 1 |
| `WOSESLVL` | 147 | 1 |
| `WOSECRTD` | 150 | 6 |
| `WOSELCDT` | 156 | 8 |
| `WOSEOCDT` | 164 | 8 |
| `WOSEIXDT` | 180 | 8 |
| `WOSEINTS` | 189 | 2 |

  The field names are preserved exactly; the tooling does not invent
  expansions for them.
- The earlier broad full-image scan found 1,987 printable **EPA-like**
  `06/C1` signatures at the expected within-page offset. That count was too
  permissive to call every hit an object: it did not require a page-aligned
  storage header or require the segment-group owner address to equal the
  candidate primary virtual address.
- Re-running the classification with those structural primary-object checks
  leaves **1,832 page-aligned primary candidates**. Of those, **1,826** use the
  conservative ordinary layout and **6** are the validated overflow family
  described below.
- The remaining **9** members of the old "15 unusual" set are not alternate
  DOCBSS layouts. Every one sits on a storage header whose virtual address is
  256 bytes off a 512-byte page boundary, and every one has a segment-group
  owner address different from that header virtual address. They are therefore
  raw EPA-like byte coincidences/non-primary data, not structurally valid
  DOCBSS primaries. Their apparent duplicate-length mismatches must not be used
  to invent another export format.
- Two known PC Support examples independently validate the ordinary layout.
  `FMPV082760F` declares 2,688 payload bytes; the next page begins with an
  `MZ` DOS executable header and the DOS header itself also describes a
  2,688-byte file. `FMPV195818F` declares 424 bytes; the next page begins
  `PKGF\r\n` and contains the expected Data Queue package member list.
  This is strong evidence that the byte stream begins exactly one page after
  the DOCBSS metadata for these ordinary objects.

- QAOSSS14 now provides an independent mapping from QDOC objects to anchor
  records. For `FMPV082760`, the matching RRN is 695. Its
  `WOSEFDOC` field is `CKPCSPTH.EXE`; its `WOSEPLDN` value uniquely
  matches the **leading 8-byte key** of RRN 677, whose short name is
  `QIWSFLR` and whose parent is zero. In this PC Support case the anchor
  components independently agree with the known user-facing QDLS names,
  yielding **`QIWSFLR/CKPCSPTH.EXE`**.
- The same method maps `FMPV195818` uniquely to RRN 313 and then to the
  leading key of parent RRN 283, yielding **`QIWSFL2/DTAQ.PKG`**. Again,
  those components are independently consistent with the known PC Support
  folder/file naming.
- `DPWN524712` uniquely correlates to QAOSSS14 RRN 1871. Its 44-byte
  `WOSEDOCN` value is `AS/400 Office Training Information`, while its
  12-byte `WOSEFDOC` value is `BULLET1.RFT`. Its `WOSEPLDN` value
  matches the **leading key** of RRN 1870. RRN 1870 is a root folder anchor
  with short name `QGFSWOF1` and long text
  `The Bulletin Board folder for SWO users`. Its leading key and
  `WOSEFILD` differ, which proves parent traversal cannot universally use
  `WOSEFILD`. Independently, the QDOC document's own error-log text names
  the user-facing folder `BULLETIN`; therefore `QGFSWOF1` must not be
  silently relabeled as the QDLS folder name.
- Across all 1,885 recovered QAOSSS14 user records, 1,870 have a nonzero
  parent key. **1,867** of those resolve uniquely through another record's
  leading key. Only RRNs 1883-1885 remain unresolved by this rule. Fourteen
  records have a leading key different from `WOSEFILD`; the BULLET/SWO
  examples are among them.
- These examples also show that `WOSEDOCN` is not simply "the filename":
  it can contain a longer document title, while `WOSEFDOC` carries the
  12-character short component in the examples decoded so far.

Printable strings inside a QDOC object are **hints**, not automatically
authoritative path metadata. The `DPWN524712` case is stronger because the
document's own error-log text explicitly supplies both document and folder names.

## Extended DOCBSS continuation segments

The first non-ordinary `*DOCBSS` family is now decoded far enough for safe
read-only export.

Six real V2R3 objects have duplicated payload lengths that are valid but exceed
the bytes available after the primary segment's first 512-byte metadata page:

- `FMPV131790F` — 65,428 bytes;
- `FMPV160496F` — 65,026 bytes;
- `FMPV181282F` — 65,428 bytes;
- `FMPV205432F` — 65,116 bytes;
- `FMPV252046F` — 65,428 bytes;
- `GNGT110572F` — 65,504 bytes.

Each of these has an owner-matched secondary segment group of type `0F90`
immediately following the 128-page primary in virtual storage. The secondary
segment independently carries one 512-byte metadata/header page, and the
workstation byte stream resumes at secondary offset `+0x200`.

The text examples continue readable ASCII exactly across that boundary; the
binary examples likewise continue their binary stream. This makes the observed
logical payload form:

```text
primary 06/C1:  bytes +0x200 .. end
continuation 0F90: bytes +0x200 .. end
[next contiguous 0F90 continuation if required]
stop exactly at the duplicated declared payload length
```

The implementation now follows that form conservatively. It uses only
owner-matched `0F90` segment groups in virtual-address order, requires the
needed continuation groups to be contiguous, skips each continuation group's
first metadata page, and stops at the declared payload length rather than
including allocation padding.

Many ordinary DOCBSS objects also own `0F90` segment groups even though their
declared payload already fits in the primary. Those extra groups are **not**
blindly concatenated. Continuations are consumed only when the declared payload
requires bytes beyond the primary capacity.

This resolves the clearly validated overflow family and expands both CLI and
TUI export coverage. With the nine raw false-positive signatures removed by
normal primary-segment structural checks, **all structurally valid DOCBSS
primary candidates in the current V2R3 corpus are now classified as ordinary
or overflow-continuation form**. This is a corpus result, not a claim that all
AS/400 releases must use only these two physical forms.

## Deleted QAOSSS14 tail records

The former "three unresolved parent gaps" at RRNs 1883-1885 are no longer
treated as live hierarchy failures. All three have DENT status `0xC0`, the
same deleted-entry form independently excluded from the live QAOSSS14 QDDSI
access path.

Their shared `WOSEPLDN` parent value occurs only in those three deleted
records and has no surviving live leading-key anchor. They are therefore best
preserved as historical/deleted records with an unavailable deleted parent,
not counted among the live QAOSSS14 hierarchy gaps.

## Current tooling

`as400-dasd dlos IMAGE`

- inventories recovered QDOC `*DOC`/`*FLR` objects;
- reports their internal `SYSOBJNAM`;
- shows short EBCDIC metadata hints;
- reports recovered `QUSRSYS/QAOSS*` runtime indexes when available;
- separately reports the recovered QSYS DLO command model files;
- with `--model-fields`, decodes their recovered MI 19/51 field definitions.
- reports same-base `*DOCBSS` companions when a recovered `06/C1`
  object named `SYSOBJNAM+"F"` is present.


`as400-dasd dlo-xref IMAGE SYSOBJNAM`

- scans recovered object segments for EBCDIC references to a 10-character
  `SYSOBJNAM`;
- optionally searches ASCII as well;
- reports the containing library/object, byte offset, and nearby EBCDIC
  context;
- suppresses the object's own header by default so cross-references stand out.

The xref scanner is intentionally structural: finding the same SYSOBJNAM in a
database/index object is evidence of a relationship without assuming the
meaning of the surrounding bytes.

`as400-dasd dlo-paths IMAGE [SYSOBJNAM ...]`

- loads the recovered 193-byte QAOSSS14 anchor records;
- correlates a QDOC object when its QAOSSS14 `WOSEFILD` key occurs uniquely
  in that object's recovered bytes;
- follows unique `WOSEPLDN -> leading-record-key` links to reconstruct a
  complete or partial **QAOSSS14 anchor hierarchy**;
- prints the internal SYSOBJNAM, QAOSSS14 RRN, short name, and anchor
  hierarchy without claiming every anchor component is the user-facing QDLS
  folder name.

`as400-dasd dlo-schema IMAGE`

- scans raw DASD bytes for exact `WOSFMTxx` markers in a streaming pass;
- extracts the adjacent literal 8-character IBM field identifier and contiguous
  `QAOSS*`/`WOS*` identifiers;
- can isolate a family such as `QAOSSS14` or `QAOSSY14`;
- reports only literal associations and does not assign meanings to unknown
  abbreviations or binary descriptor fields.

`as400-dasd dlo-export IMAGE SYSOBJNAM OUTPUT`

- finds a recovered QDOC `*DOC` and a unique same-base `SYSOBJNAM+"F"`
  `*DOCBSS`;
- validates the duplicated observed length fields before extracting anything;
- reads exactly the declared byte count beginning after the first DOCBSS page;
- refuses ambiguous companions, invalid lengths, or accidental overwrite of an
  existing output unless `--force` is requested;
- never writes to the DASD image.

`as400-dasd dlo-parent-gaps IMAGE`

- isolates QAOSSS14 records whose nonzero `WOSEPLDN` value has zero or
  multiple leading-key matches;
- with `--raw-scan`, searches for that exact eight-byte value elsewhere in
  the raw image and classifies the containing recovered segment/object;
- provides a targeted way to investigate the exceptional parent relationships
  without weakening the traversal rule that already resolves the other
  records.

## Next experiments

1. Apply the same direct recovery approach to `QAOSSS10`-`QAOSSS13`,
   `QAOSSS15`, `QAOSSS17`, and `QAOSSS18`, preserving each recovered
   WOSFMT descriptor before assigning semantics.
2. Keep deleted QAOSSS14 RRNs 1883-1885 as forensic history rather than live
   hierarchy gaps; their shared parent anchor is not present among the live
   recovered records.
3. Determine where the user-facing folder name differs from the QAOSSS14
   anchor short name (for example `BULLETIN` versus `QGFSWOF1`) and which
   QAOSS/QDOC structure carries that mapping.
4. Determine which QAOSSS14 field or related structure carries IBM's
   documented DLO system object name; the V2R3 QDOC correlation currently uses
   the observed binary `WOSEFILD` key rather than pretending a plain EBCDIC
   SYSOBJNAM is present in the 193-byte record.
5. Validate QAOSSS14 anchor reconstruction over a larger random sample of QDOC
   documents and folders, including non-PC-Support content.
6. Keep DOCBSS classification release-scoped. The current V2R3 corpus is now
   fully classified after removing nine non-page-aligned/non-primary raw
   signatures; future images may still expose additional physical forms.
7. Once the user-facing-folder mapping is understood, add optional recursive
   export that mirrors the recovered QDLS directory tree while continuing to
   preserve internal SYSOBJNAM metadata.
