# Saved CISC 19/C2 SPLCB name-slot exploration

`DSPSPLCB SPLCB(*ALL/QSPSCB)` selects a recovered spool-control primary
and displays evidence from the first bounded primary page. It reports
two saved ten-byte EBCDIC right-blank-padded name slots (+0x1AE and
+0x1B8), a six-byte `SPdddd`-shaped token (+0x1C5), original hex
bytes, and selectable recovered primaries whose **name and assigned
library** exactly match the two slots.

## Two-image raw physical evidence

| Field/pattern on recovered physical primary header candidates | Mark V2R3 | Pete B10 |
|---|---:|---:|
| 19/C2 QSPSCB candidate primary identities | 415 | 19 |
| Both saved slots form a ten-byte qualified-name-shaped pair | 56 | 5 |
| Both saved names occur in the physical primary name census | 56 | 5 |
| Six-byte SP followed by four decimal digits | 391 | 15 |

These are direct **physical candidate** observations from the original
images and do not establish pointer ownership or equal counts in the
normal recovered inventory. All observations above were made read-only.
The remainder of the physical specimens have missing, zeroed or
unsupported slot data. They must not be assigned an invented spool
destination.

A pair such as a recovered object name and library is shown as a
**candidate name correlation only**. No spool owner, job identifier,
printer device, queue assignment, active spool file, or job chronology
is decoded from these bytes. In particular, the `SPdddd` pattern is
not certified as a spool-file number. Qualified-name matching does
not imply an internal address pointer.

## Safety and regression

The parser accepts only strict ten-byte EBCDIC names with right-blank
padding, no NULs or replacement characters; incomplete or invalid
fields remain unresolved with raw hex. Every same-qualified recovered
origin stays selectable, and a missing primary is reported rather than
conjuring a target. The screen never reads target object contents,
credentials or spool payloads.

`tests/test_spool_control_workflows.py` tests valid/invalid padding,
release-common patterns, duplicate target origin, missing/incomplete
references and Back. `tools/validate_spool_controls.py` is an opt-in
original-image checker that runs the production recovered-object workflow,
exercises select/Back when possible, emits aggregate counts only and
compares SHA-256 before/after. Until it runs on both extracted original
images, do not claim whole-image acceptance. This is a **partial**
family in the ongoing full 268-type roadmap.

Next evidence gate: locate period CISC spool-control structure definitions
or corroborated internal-address references before interpreting the saved
name-slot purpose or nearby status/control words.
