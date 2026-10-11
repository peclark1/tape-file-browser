# Saved CISC 18/A0 JMQ 16-byte slot exploration

The read-only Guided 5250 browser supports
`DSPJMQ JMQ(*ALL/QJOBMSGQ)`. Select an individual archived 18/A0
job-message queue primary by original LBA/namespace, page through
the recovered 16-byte saved slots (50 per window), and select a slot
for the exact bytes, location and two eight-byte CP037 display lenses.

## Original-image evidence

The V2R3 Mark image contains **415** physical EPA signature candidates
of 18/A0 `QJOBMSGQ` in the sampled primary census. Pete's older B10
image has **none under that physical-signature heuristic**, which does
not prove the logical type was absent on the running machine.

Read-only physical-contiguous probes of Mark's 415 candidates found:

| Observation | Candidate count |
|---|---:|
| +0x100 4-byte prefix `80 00 00 00` | 415 |
| +0x800 u16 count and 14 zero control bytes at +0x802..+0x80F | 410 |
| Declared number of complete, nonzero 16-byte slots beginning +0x810 | 410 |
| Following 16-byte slot zero | 409 |

The remaining five candidates may involve virtual fragmentation or
variant control fields; **physical adjacency is not proof of virtual
contiguity**. The production reader uses ordered virtual extents and
rejects incomplete headers and declared slots, never silently mixing
adjacent physical sectors. It reads a bounded subset of the primary.

The stored u16 is a **saved slot count**, not a certified live delivered
message count, queue depth, message timestamp, job identifier or
service entry status. The one supported case with a nonzero 16-byte slot
after the declared count emits a warning instead of inventing extra
entries. Each slot is opaque; no internal pointers, message text,
timestamps or recovery sequence are inferred. The sixteen-byte grouping
is empirical and has not been checked against an IBM period record schema.

## Validation

- `tests/test_jmq_workflows.py`: synthetic zero/one/multi-record cases,
  malformed counts and zero entries, extra following slot, 50-slot
  navigation, exact byte positions, Back and missing virtual extents.
- `tools/validate_jmq_workflows.py`: opt-in full recovered-object
  walkthrough on an original extracted HDA with before/after SHA-256
  checks and aggregate counts **only**.

This is a **partial** type in the full 268-type MI plan. No recovered
message text or archival payloads are committed. The next evidence gate
is identifying the byte fields and independently linking the saved
16-byte slot targets to corroborated recovered objects or records.
