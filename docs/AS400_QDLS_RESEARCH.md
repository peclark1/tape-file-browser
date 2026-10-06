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
- Other `QAO*` files in `QUSRSYS` support distribution and text-search
  functions.

IBM references:

- https://www.ibm.com/docs/en/i/7.4.0?topic=objects-how-system-stores-uses-document-library
- https://www.ibm.com/support/pages/document-library-objects-dlo-information
- https://www.ibm.com/docs/en/i/7.5.0?topic=r-retrieve-document-library-object-name
- https://www.ibm.com/docs/en/i/7.6.0?topic=d-display-document-library-object-name

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

Printable strings inside a QDOC object are **hints**, not yet authoritative path
metadata. The correlation must be independently reconstructed.

## Current tooling

`as400-dasd dlos IMAGE`

- inventories recovered QDOC `*DOC`/`*FLR` objects;
- reports their internal `SYSOBJNAM`;
- shows short EBCDIC metadata hints;
- reports recovered `QUSRSYS/QAOSS*` runtime indexes when available;
- separately reports the recovered QSYS DLO command model files;
- with `--model-fields`, decodes their recovered MI 19/51 field definitions.

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

## Next experiments

1. Run `dlos --model-fields` on the V2R3 image and record the recovered field
   names/offsets for `OSQDL`, `DOCDTL`, `FLRDTL`, and `OSRTVD`.
2. Run `dlo-xref` for known QDOC objects, beginning with
   `FMPV082760`, `FMPV195818`, and `DPWN524712`.
3. Classify every non-self match by library/object type. A repeated cluster in
   one unidentified data/index file may expose the missing QAOSS structure even
   if the file's normal context/name relationship is not yet recovered.
4. When a candidate database member is identified, use the existing
   QDDS/member/format decoder to recover its fixed records and field
   definitions.
5. Cross-check any proposed SYSOBJNAM -> DLO-name/folder mapping against more
   than one object before promoting it from hypothesis to decoded structure.
6. Once parent folder identifiers are understood, reconstruct full QDLS paths
   and expose them in the TUI while retaining SYSOBJNAM as forensic metadata.
