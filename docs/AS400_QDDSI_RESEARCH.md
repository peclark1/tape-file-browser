# AS/400 QDDSI / keyed-file research

This note applies the project research method to the next DASD-browser priority:
database access paths and the recovered MI `0C/90` QDDSI objects.

## Goal

Move from arrival/physical record browsing toward a read-only view of keyed
order and logical-file/access-path structure. The first milestone is deliberately
small: prove how one recovered QDDSI relates to one decoded member and recover
enough references to order known QDDS records.

Do not assume that QDDSI is identical to the generic permanent-context machine
index merely because both are indexes. Reuse documented machine-index
primitives only when the object bytes independently support that interpretation.

## Documented functional context

The currently indexed IBM material gives useful behavioral context but not yet
the V2R3 QDDSI physical layout.

IBM's *AS/400 Disk Storage Topics and Tools* (SG24-5693, 2000) treats database
access paths separately from the record images themselves:

- journal management can include access paths as well as database records;
- an IPL can present an **Edit Rebuild of Access Paths** display;
- that display identifies file, library, member, whether the access path is
  keyed, and rebuild time.

This is later V4-era documentation, so it is semantic corroboration only. It
does support an important browser concept: an access path is persistent
database structure with its own maintenance/rebuild behavior, not merely a
different presentation of bytes in the QDDS record stream.

The current attached/indexed manual set has not yet yielded a direct definition
of the internal `QDDSI` name or a byte-level data-space-index layout. Before
assigning names to QDDSI fields, search period database/DDS/VLIC documentation
from the early AS/400/System/38 family.

## Existing implementation / observed evidence

The recovery backend already distinguishes:

- `19/01 *FILE` — external file object;
- `0D/50 *MEM` — member cursor;
- `0B/90 QDDS` — internal data space backing the member record stream;
- `0C/90 QDDSI` — optional same-named internal index object associated with
  member storage;
- `19/51 *FORMAT` — recovered record-format metadata.

`resolve_member_storage()` matches QDDS/QDDSI to a member by the exact
30-byte file/member name and prefers the same pointer extender / explicit
address evidence. This relationship has been observed on the independent V2R3
image, but the detailed QDDSI contents are not yet decoded.

The tool can already decode QDDS fixed-length records and verified field types,
which gives us the independent side of the next cross-check: any proposed QDDSI
record reference must resolve to a real recovered RRN/record.

## First research questions

1. Which small recovered member has a QDDSI and a clean decoded QDDS record
   stream?
2. Does the member cursor or file FCB contain a direct pointer to QDDSI that can
   replace same-name correlation?
3. Is the QDDSI primary segment followed by secondary owned segment groups, and
   what segment types/sizes occur?
4. Can key field names, field lengths, RRNs, or known record values be located
   in the QDDSI bytes without assuming structure?
5. Does QDDSI contain recognizable three-byte machine-index elements, or a
   different index representation?
6. Can one candidate index entry be correlated with a decoded record and then
   repeated across a second key value/member?

## Initial validation plan

Start with the B10 `PPSITEST` application material because it is small enough
to inspect manually. Run `member-storage` for the recovered application
members to identify which one actually has QDDSI. Prefer a database member such
as `ACCTDEF(ACCTDEF)` or `FUNDDEF(FUNDDEF)` over the QDDSSRC/QLBLSRC source
members.

Once a QDDSI-bearing member is identified:

1. preserve its QDDS/QDDSI VAs, LBAs, pages, and owned segments;
2. inspect its decoded format and several representative records;
3. search QDDSI bytes for the documented key field values and record
   references;
4. only after that evidence pass, introduce a QDDSI-specific decoder.

## TUI implications

When enough semantics are proven, a keyed member view should explain:

- physical/member records versus an access path;
- whether the recovered member has a QDDSI/index;
- known key fields and ascending/descending attributes when documented;
- arrival/RRN order versus recovered keyed order;
- whether the view is decoded, partially inferred, or raw forensic fallback.

The browser should never imply that the on-disk order of QDDS records is the
same thing as the logical keyed access path.
