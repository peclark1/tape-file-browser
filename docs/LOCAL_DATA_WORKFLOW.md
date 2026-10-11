# CISC job-local data-area (QLDA) byte-window workflow

The offline Guided browser now exposes `DSPLDA LDA(*ALL/QLDA)` on recovered
19/CE `*LDA` primaries. It presents 128-byte selectable windows, exact
1-based value positions, raw hex, a CP037 display lens, and counts of blank
versus other bytes. Selecting Next/Previous and Back preserves the current
primary and position. Duplicate `QLDA` names retain original LBA/namespace
selection rather than being silently deduplicated.

## Independent original-image evidence

Direct read-only physical primary probing produced:

| Original archive | 19/CE QLDA signature candidates | Prefix +0x100 `D3F0055F` | Boundary +0x15D `040400` |
|---|---:|---:|---:|
| Mark V2R3 | 414 | 414 | 414 |
| Pete B10 | 20 | 20 | 20 |

The contiguous-physical-sector probe additionally found a candidate
1,024-byte EBCDIC region at +0x160..+0x560. On 409 of Mark's 414
physically adjacent samples, and all 20 Pete samples, the 1,024 bytes
were all `40` (EBCDIC blank). Four Mark samples do not show the
expected `01` post-window marker at +0x560 in the **physical-contiguous
probe**; this is not proof of a different format because virtual
extents can be noncontiguous and the probe does not perform production
segment recovery. The strict application decoder checks the full
reassembled virtual region plus both control markers and the post-window
`01` before displaying the 1,024 bytes. A gap or unsupported variant is
reported rather than showing possibly shifted or merged bytes.

**This is a candidate saved 1,024-byte LDA value region**, independently
compatible with the known fixed-length local data-area abstraction,
but not an independently established active job association, CCSID,
job status, or credential-free guarantee. Never call saved local values
current job data. Some rare values could contain binary or sensitive
application content; the tool is read-only and does not publish it.

## Validation

- `tests/test_local_data_workflows.py` uses synthetic data for exact
  1,024-byte boundaries, malformed/truncated controls, virtual
  discontinuities, 128-byte pagination, duplicate origins and Back.
- `tools/validate_local_data.py <extracted-image.hda>` performs complete
  recovered-object selection, byte-window/Back walkthrough, SHA-256
  before-and-after checks, and prints **aggregate counts only**.

The physical candidate survey is not a substitute for complete recovered
object and image-wide navigation validation. Keep this type **partial**
until the suspected data origin, nonblank payload interpretation and
historic job association are independently verified.
