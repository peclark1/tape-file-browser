# Saved CISC PRTQ keys and SPLCB token candidates

`DSPPRTQ PRTQ(*ALL/QSPSIDQ) TOKEN(SP0002)` is a new offline
Guided 5250 workflow for internal 0E/C7 printer-queue index primaries.
It reconstructs saved machine-index terminal keys, pages 50 at a time,
filters by exact `KEYHEX` prefix or a strict `SPdddd` text
candidate, and opens each key's full hex/CP037 display bytes.
A key starting with a ten-byte EBCDIC `SPdddd` followed by four
blanks may also provide selectable **same-token candidate**
relationships to normally recovered `*SPLCB` primaries. Every
duplicate physical origin is retained; missing references are
diagnostics, not evidence of absence.

The string `SPdddd` has **no certified spool owner/file identity**.
Cross-object equality is an empirical join, **not** a decoded CISC
internal pointer, active spool ownership, printer destination or
historical print job status. All actions are read-only.

## Independent original-image observations

Read-only physical EPA-primary sector surveys on Mark V2R3 and Pete
B10 found the following:

| Physical-sector observation | Mark V2R3 | Pete B10 |
|---|---:|---:|
| 0E/C7 `*PRTQ` signature candidates | 15 | 3 |
| +0x420 root address inside declared primary and +0x42A supported saved page size | 7 | 3 |
| Supported saved index page size in those candidates | 2048 | 1024 |

Headers at primary +0x100..+0x105 include
`20 00 00 ?? 00 1A` and, in Mark,
`30 00 00 ?? 00 2C`. Byte `??` and other scalars
remain uninterpreted.

In one Pete `QSPSIDQ` candidate, direct contiguous-physical
read of the first supported index page independently reconstructed
**two 26-byte saved keys**, both beginning with an
`SPdddd`-shaped EBCDIC identifier. One, `SP0002`, matched the
independently observed +0x1C5 token in **two separate** Pete
`*SPLCB` physical primaries; the other had no identical SPLCB
token in that physical survey. **This makes ambiguity visible, not
proof of spool ownership.**

Some Mark PRTQ physical-contiguous page probes produced invalid
internal tree offsets, and several older-looking Mark signatures
did not yield an in-primary root under that heuristic. This can
occur when the primary's virtual storage is noncontiguous in physical
sector order or a different control layout exists. The application
uses strict release-2 tree decoding over **properly reconstructed
virtual extents**, not raw physical adjacency. We do not claim all
Mark/Pete keys have been recovered or that empty physical probes
prove an empty queue.

## Bounds, tests and next evidence gate

- `decode_context_machine_index(..., strict_pages=True)` performs
  the established used-page/terminal-tree checks. Roots and 1024/2048
  page sizes must be within the requested recovered data.
- Unsupported headers, roots, partial trees and unsupported terminal
  sizes are explicitly withheld or warned; opaque keys are at most
  256 bytes.
- Only the first **ten exact bytes** of a key are used for the
  token candidate, and four must be EBCDIC blanks (`40`).
  No arbitrary substrings, approximate matching, or guessed
  job sequence numbers are used.
- `tests/test_printer_queue_workflows.py` validates both page sizes,
  relocated roots, released header variants, proper element versus
  payload byte offsets, ambiguous token candidates, missing targets,
  malformed indexes, filtering, selected origin and Back.
- `tools/validate_printer_queues.py <image.hda>` performs optional
  **full recovered-object** read-only checks on an original disk
  image with SHA-256 comparison before and after and reports
  **aggregate-only counts**. A combined 13-family runner is also
  included at `tools/validate_recent_workflows.py`.

Actual full-image recovered-virtual acceptance remains to be run;
the physical-sector observations above do not substitute for it.
The type remains **partial**, not a fully decoded printer-queue
object. Confirm spool-key schema, receiver/record pointers and token
field roles using applicable period CISC references before assigning
printing semantics.
