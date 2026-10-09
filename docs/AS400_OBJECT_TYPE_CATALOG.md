# IBM MI object-type reference catalog

The CISC AS/400 disk explorer now ships machine-interface (MI) object
type/subtype **name references** taken from IBM documentation. This is
*not* an object decoder or a list of objects installed in any particular
OS/400 release.

## IBM sources and reproducibility

- [IBM i 7.5 external object types](https://www.ibm.com/docs/en/i/7.5.0?topic=objects-external-object-types):
  `as400_external_types.tsv`, 102 documented type/subtype pairs.
- [IBM i 7.5 internal object types](https://www.ibm.com/docs/en/i/7.5.0?topic=concepts-internal-object-types):
  `as400_internal_types.tsv`, 166 documented type/subtype pairs.
- [IBM System i V5R4 Programming API overview and concepts](https://public.dhe.ibm.com/systems/power/docs/systemi/v5r4/en_US/api.pdf),
  pages 64–69, supplies a **second IBM reference** for earlier code values.
  In particular, its table verifies `*EDTIDX = 0ED0` and
  `*OWCUR = 0DED`. The modern IBM i web table displays **OED0** and
  **ODED** with the letter O (not valid hexadecimal), so these two
  corrections are based on the independent IBM PDF, **not inference**.

The 268 included mappings are uniquely keyed by the full two-byte MI
type/subtype combination. There are no cross-category collisions. The
external and internal categories come from IBM's separate tables. Entries
include the IBM English description and the table URL from which they
were transcribed.

### Historical caveat

IBM i 7.5 describes a later system than Mark's OS/400 V2R3. **A valid
modern mapping does not establish that the type existed in V2R3**, or that
its contents/creation syntax were identical. The catalog deliberately
does *not* create missing objects in a recovered image.

The project also uses existing first-hand recovery research to explain
certain object roles (QDDS, QDDSI, QDIDX, OIRS etc.). That structural
knowledge is separate from the catalog's basic type names. Detailed
object-role text may be more specific than IBM's category description;
both are shown where available.

One previous heuristic called MI `19/51` `*FORMAT`. IBM's table names
this internal subtype **`*FMT`** (file format). The new display now follows
the published IBM name. It does not change record-format recovery.

## Browser behavior

- All recovered primary objects use their catalog name, e.g.
  `19/05 → *CMD`, `19/16 → *MENU`, `19/D4 → *DBRCVR`.
- A category marker `[internal]` appears for internal types in Guided 5250.
  These should **not** be treated as ordinary, interactive PDM objects.
- Recovered directory-only identities are labeled when their MI codes
  are known, retaining `[dir] primary absent` to avoid implying their
  primary storage was found.
- The forensic inspector and Guided 5250 object details retain the
  original code plus the IBM description/category/provenance.
- Unlisted and malformed codes remain `XX/YY` (no fabricated type).
- The CLI and browser never execute CL operations or modify disk images
  to identify object types.

### Quick lookup

From the repository checkout:

```bash
python3 as400_dasd_tool.py types 19/D4
python3 as400_dasd_tool.py types 0E/C4
python3 as400_dasd_tool.py types 19/16
python3 as400_dasd_tool.py types --category internal
python3 as400_dasd_tool.py types --category external
```

After installing:

```bash
as400-dasd types 19/D4
as400-dasd types --category external
```

No image argument or disk scan is required for this reference command.

## Updating the catalogs

`as400_external_types.tsv` and `as400_internal_types.tsv` are human-readable
UTF-8 files. Each non-comment record has three pipe-separated fields:

```text
1905|*CMD|Command
19D4|*DBRCVR|Database recovery object
```

Record validation in `as400_object_types.py` is strict: four uppercase
hexadecimal digits, a nonempty `*NAME`, a nonempty description, no
duplicate code within either file, and no overlap between files. Bad
catalog data fails visibly rather than being assigned a misleading name.

To add or correct an entry, verify the complete code and label against
IBM's actual type tables, update the appropriate file and its source
provenance, and add a regression test. On-disk structural discoveries
belong in separate recovery parsers, not the type-name catalog.

The source documentation and mapping do not grant permission to reproduce
other IBM proprietary material; these brief nomenclature entries are
maintained as factual reference data.
