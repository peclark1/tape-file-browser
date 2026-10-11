# Internal-profile identity exploration — CISC 0E/C4

This is a **credential-safe name-correlation workflow**, not a decoder of profile
attributes, signon authentication, authorities or security internals.

## Guided workflow

`DSPINTPRF INTPRF(*ALL/*)` selects recovered 0E/C4 internal-profile primaries
with their original library context/LBA. `DSPINTPRF INTPRF(*ALL/QSECOFR)`
selects an individual candidate by name, if unambiguous. Inside the detail
view, exact-name 08/01 `*USRPRF` primaries appear as selectable links.
Each candidate retains its origin, including duplicate and unassigned
identities. Option 5 opens the existing safe user-profile identity view;
Back returns to the selected internal profile.

The decoder uses the **existing recovered object inventory only**. It does not
read internal-profile payloads or user-profile credential/authorization bytes.
Name equality is a *candidate relationship*, not a proven CISC internal pointer.
No active user, password, authority, logon eligibility, object ownership, or
historic account continuity is inferred. Absence of a recovered matching
primary does not prove the historical user was absent.

## Two independent image observations

A direct raw-sector primary-header census found:

| Image | Physical 0E/C4 INTPRF candidates | Candidates whose names occur in 08/01 USRPRF physical primary headers |
|---|---:|---:|
| Mark V2R3 | 17 | 17 (16 distinct names, one duplicated) |
| Pete B10 | 4 | 1 |

These are **physical-header candidates**, not necessarily objects surviving
the complete virtual-extent recovery, and the right column is **name match
only**. No names, credentials or object body bytes from the images appear in
this repository. The original images were mapped read-only, never changed.

The difference in coverage is one reason the browser must report missing
matches explicitly: it would be unjustified to manufacture a user-profile
pointer or to conclude that the B10 image lacks older history.

## Remaining evidence gates

Research period System/38/CISC profile structures before interpreting INTPRF
contents. Independently establish a pointer relationship if possible **without
inspecting or exposing sensitive profile information**. Until then the viewer
remains identity-only, and the profile names and LBA are provenance, not
system-security statements.

This is one partial family in the 268-type program. Continue to the next
ranked families after regression and user acceptance checks.
