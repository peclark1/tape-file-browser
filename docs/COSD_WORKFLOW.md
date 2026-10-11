# CISC *COSD saved eight-slot profile explorer

## Usable Guided workflow

`DSPCOSD COSD(*ALL/#*)` lists independently recovered type 14/01 COSD
primaries. Select one to inspect its corroborated eight 48-byte saved
slots (original primary offsets +0x150..+0x2CF); select slot 1..8
for exact raw bytes and offsets. `DSPCOSD COSD(QSYS/#INTER) SLOT(8)`
goes directly to one saved slot. Peer selections compare the same
slot bytes across distinct recovered origins, report differences and
allow Back without losing selection.

The raw +0x100 variant is 00000001 in five Mark V2R3 physical
candidates and 000000DF in three Pete B10 physical candidates. The
saved padded name at +0x130 is cross-checked against the independent
EPA object identity; +0x138 name size, +0x13A eight-slot count,
+0x13C flag and each exact two-byte slot prefix are strictly
validated. The common names #BATCH, #BATCHSC and #INTER have
corroborated byte-identical +0x130..+0x2CF spans across releases.
A valid saved representation is **not** a verified runtime profile,
CPU priority, job routing or resource policy.

## Evidence and constraints

Original physical-primary evidence is an independent preliminary
source survey, **not** a completed normal recovered-object Guided
walkthrough. The production decoder reads bounded virtual extents
and fails closed on missing or unsupported bytes. Peers are distinct
historical origins and same-name equality does not prove ownership.
No source HDA payload is embedded in tests or committed.

`tests/test_cosd_workflows.py` supplies synthetic release variant,
boundary, malformed/truncated, virtual-gap, origin-compare, selector,
and navigation/Back regressions. Confirm CI on the exact branch head.
The full original-image acceptance run on *both* read-only HDAs
remains outstanding. Wider binary field semantics require
historical CISC documentation and independent corroboration.

The COSD type stays **partial**, with the remaining semantic work
in `research/mi_capabilities.json`.
