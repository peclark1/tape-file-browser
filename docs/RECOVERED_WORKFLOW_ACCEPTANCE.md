# Acceptance pass for newly added Guided 5250 object families

This checkpoint **does not** claim that original-image application
walkthroughs have been run. Earlier releases used mostly synthetic
regression tests plus independent physical-sector signature surveys.
The goal here is to close that verification gap with a practical,
repeatable **single-scan, read-only** test of the *normal recovered
object model* on both original disk images.

## Test checkout without disturbing installed/stable code

From the existing `tape-file-browser` Git checkout:

```bash
git fetch origin feature/recovered-workflow-acceptance
git worktree add --detach ../tape-file-browser-acceptance origin/feature/recovered-workflow-acceptance
cd ../tape-file-browser-acceptance
python3 -m unittest discover -s tests -q
```

This keeps the existing checkout and installed `as400-dasd`
unchanged. **Do not run `install.sh`** for this acceptance pass.
The project uses Python standard-library facilities for the text TUI.
Both `.hda` images must be extracted from their `.zip` archives
before use, and should be kept on an archival/read-only filesystem or
otherwise protected from writes.

## One recovery/scan per image

```bash
python3 tools/validate_recent_workflows.py /path/to/marks.hda \
  --output /tmp/marks-guided-acceptance.json
python3 tools/validate_recent_workflows.py /path/to/petes.hda \
  --output /tmp/petes-guided-acceptance.json
```

Unlike running thirteen separate validators per image, this single
runner performs **one physical scan and recovered inventory build per
image**, reuses model services, then performs a SHA-256 before/after
check. There are two complete SHA reads per image, independent of the
parser scan. It does not create or modify a file beside the original
images. The output JSON contains only **aggregate type codes, counts,
UI result categories and source hashes**; no object names, credentials,
extracted payload bytes, messages or source code.

Each family reports `recovered_primaries`,
`bounded_views`, `withheld_or_unavailable`,
`views_with_navigable_candidates` and the first supported command's
`ui_summary_ok` or `ui_detail_back_ok`. A family absent from the
recovered inventory is recorded as `ui_walkthroughs_not_possible`,
**not** a parser failure or proof of absence on the historical system.

An actual command/detail/Back failure raises an error and does not
generate a misleading successful report. A valid missing field or
unsupported release-specific layout remains explicitly withheld and
counted. The independent physical-primary census counts in existing
research documents need **not** match the normally recovered inventory.

## Family coverage

| MI | Guided command | Acceptance focus |
|---|---|---|
| 0E/02 | `WRKOUTQ` | Saved key selection and byte detail |
| 0E/01 | `WRKJOBQ` | Queue references and saved index evidence |
| 0E/C4 | `DSPINTPRF` | Credential-safe name-candidate view |
| 19/09 | `DSPSBSD` | Subsystem name evidence and selectable targets |
| 19/04 | `DSPCLS` | Reverse class-name candidates |
| 0E/07 | `DSPSCHIDX` | Saved scheduler index keys |
| 0E/91 | `DSPMSRVI` | Saved service index keys |
| 19/CE | `DSPLDA` | Position-aware saved 1,024-byte local values |
| 19/C2 | `DSPSPLCB` | Qualified spool-name evidence |
| 18/A0 | `DSPJMQ` | Count-checked 16-byte saved slots |
| 19/15 | `DSPPNLGRP` | Tagged compiled symbol details |
| 19/08 | `DSPEDTD` | Saved edit pattern and peer navigation |
| 0E/C7 | `DSPPRTQ` | Saved printer-queue index keys and token-correlated SPLCB origins |

One missing image/release type should not block a different type.
Importantly, this does not test any unimplemented live spool service,
MI disassembler, program execution, UIM screen renderer, or complete
object schema.

## Hands-on 5250 testing

Run the **same** test worktree, without changing your installed stable
application:

```bash
python3 as400_dasd_tool.py browse5250 /path/to/marks.hda
```

Use F4 to browse commands, then run a few of the specific offline
explorer commands:

```text
WRKOUTQ OUTQ(*ALL/*)
DSPLDA LDA(*ALL/QLDA)
DSPJMQ JMQ(*ALL/QJOBMSGQ)
DSPPNLGRP PNLGRP(*ALL/*) NAME(CRT*)
DSPEDTD EDTD(*ALL/QEDIT*)
DSPPRTQ PRTQ(*ALL/QSPSIDQ) TOKEN(SP0002)
```

For Pete, prefer `DSPEDTD EDTD(*ALL/QEDIT*)` and
`DSPPNLGRP PNLGRP(*ALL/*)`; Pete may have no recoverable
18/A0 JMQ primary, so an empty JMQ list would not alone be a failure.
Select a **specific origin** when duplicate names appear, open
details with option 5, and confirm Back returns to the selected object.
Check that "Unavailable" messages distinguish unsupported layouts
from zero matches. Capture any exception, unexpected option behavior,
slow navigation or wrong origin, **without sending proprietary object
contents or credentials**.

To return from the detached worktree, change into your original
checkout; it remains unchanged. Do not merge the PR chain until
you've approved it.

## Review milestone

The current ledger remains **40 partial, 228 queued, 0 universally
completed**. This acceptance harness improves confidence in those
existing capabilities and does **not** advance the type count merely
by running general navigation. The runner's synthetic tests are
included in CI; actual per-image JSON must be generated and reviewed
before a release-specific validation success is claimed.
