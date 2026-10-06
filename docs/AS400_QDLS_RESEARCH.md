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

The current inventory does not yet show a recovered `QUSRSYS/QAOSS*` *FILE.
That can mean either the relevant file objects/members were not recovered by the
current pass or the context relationship is still unresolved. It does not prove
that the original system lacked the DLO indexes.

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
- A full-image scan found 1,987 printable MI `06/C1` objects. For 1,972
  of them, a conservative ordinary layout passes all current checks: the
  16-bit values at +0x106 and +0x112 agree, the declared payload fits after the
  first 512-byte page, and the nonzero allocation value at +0x10A is a
  512-byte multiple large enough for the payload. Fifteen objects need separate
  study rather than being forced through this layout.
- Two known PC Support examples independently validate the ordinary layout.
  `FMPV082760F` declares 2,688 payload bytes; the next page begins with an
  `MZ` DOS executable header and the DOS header itself also describes a
  2,688-byte file. `FMPV195818F` declares 424 bytes; the next page begins
  `PKGF\r\n` and contains the expected Data Queue package member list.
  This is strong evidence that the byte stream begins exactly one page after
  the DOCBSS metadata for these ordinary objects.

Printable strings inside a QDOC object are **hints**, not automatically
authoritative path metadata. The `DPWN524712` case is stronger because the
document's own error-log text explicitly supplies both document and folder names.

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

`as400-dasd dlo-export IMAGE SYSOBJNAM OUTPUT`

- finds a recovered QDOC `*DOC` and a unique same-base `SYSOBJNAM+"F"`
  `*DOCBSS`;
- validates the duplicated observed length fields before extracting anything;
- reads exactly the declared byte count beginning after the first DOCBSS page;
- refuses ambiguous companions, invalid lengths, or accidental overwrite of an
  existing output unless `--force` is requested;
- never writes to the DASD image.

## Next experiments

1. Decode the repeated binary descriptor structure in the V2R3
   `WOSFMT14/QAOSSS14` schema region and determine the field ordering/length
   metadata without assigning semantics beyond the embedded IBM names.
2. Use `dlo-index-scan` and raw-image cross-checks to locate actual
   `QAOSSS14` anchor records containing known SYSOBJNAM values.
3. Determine how a QDOC `*DOC` references its same-base `*DOCBSS` object
   and where the workstation byte stream begins/ends inside that object.
4. Validate the `*DOCBSS` relationship across many documents before adding
   export support.
5. Reconstruct the parent-folder reference using the independently known
   `DPWN524712 -> BULLETIN/BULLET1.RFT` example.
6. Cross-check any proposed SYSOBJNAM -> DLO-name/folder mapping against more
   than one object before promoting it from hypothesis to decoded structure.
7. Once parent folder identifiers are understood, reconstruct full QDLS paths
   and expose them in the TUI while retaining SYSOBJNAM as forensic metadata.
