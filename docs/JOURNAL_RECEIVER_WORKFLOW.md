# CISC JRN ↔ JRNRCV saved internal-address navigation

## Guided 5250 workflow

`DSPJRN JRN(*ALL/*)` selects recovered 09/01 journal primary
identities and displays **two full eight-byte saved receiver addresses**
at primary offsets +0x110 and +0x240, including both address-extender
bytes and all six address bytes. Each complete value can be followed
to *every* recovered 07/01 `*JRNRCV` primary whose
**segment-group owner's full internal address** matches byte-for-byte.
A missing receiver, null saved pointer, or ambiguous duplicate origin
is shown without substituting a similar object name.

`DSPJRNRCV JRNRCV(*ALL/*)` opens a recovered receiver and traverses
these supported journal saved slots *in reverse*. Choose a journal
origin to inspect its saved pointers, and Back returns to the exact
receiver. All commands are offline and read-only. Neither view
claims an active journal, current receiver, in-use journal object,
receiver chain order, journal entry data, or a verified user-level
journal API equivalent.

The supported parser first checks a common journal control prefix:
primary +0x100..+0x103 `00 06 00 1A`, and +0x106..+0x107
`00 0A`. Mark and Pete differ at +0x104..+0x105, whose semantics
are unknown; that field is deliberately not made a cross-release
constant. At least +0x248 bytes must be correctly recovered through
the virtual-extent map before either pointer slot is displayed. A
short or unfamiliar structure is withheld rather than concatenating
unrelated physical sectors.

## Independent original-image results

Read-only physical EPA/YYSGHDR primary-sector signature scans, with
supported `01 91` segment header and 09/01 or 07/01 EPA type:

| Independent primary-header evidence | Mark V2R3 | Pete B10 |
|---|---:|---:|
| 09/01 journal primary signature candidates | 10 | 4 |
| 07/01 journal receiver primary signature candidates | 15 | 11 |
| Journal +0x110 full 8-byte owner-key matches to independently identified receiver primary | 8 | 4 |
| Journal +0x240 full 8-byte owner-key matches to independently identified receiver primary | 8 | 4 |

These counts use the complete **two-byte address extender plus
six-byte address** against the receiver's YYSGHDR owner address.
They are not inferred from the names (although some also have
similar naming conventions). The two unmatched Mark journal
candidates must not be called corrupt or detached: their recorded
targets may be unrecovered, on another disk, in additional virtual
extents, or historical variants.

The physical-contiguous scans also exposed **additional**
full-address occurrences at +0x280 on several Mark samples and
+0x2C0/+0x300/+0x380 and other offsets on Pete, but those are
**not** added to the supported pointer decoder. Their relationships
and possible sequence meaning need independent validation with
properly reassembled virtual extents and applicable period manuals.

**IMPORTANT:** These are physical primary-signature and
contiguous-sector *probe* results, not object counts from the
complete recovered inventory and not a claim of full application
walkthrough success. The production explorer uses the normal
reconstructed `RecoveredSegment.extents` model, not naive physical
contiguity.

## Receiver-owned journal address — independent second evidence path

Read-only inspection of the same archived 07/01 receiver primaries
identified a full **eight-byte saved journal owner address at
receiver primary +0x108**, separately from the journal-side slots.
Both releases have several different leading flags/length words;
the supported cross-release control check only requires a leading
`02` or `03` and +0x106..+0x107 `00 01`, leaving all other
header bits uninterpreted.

| Physical EPA/YYSGHDR candidate evidence | Mark V2R3 | Pete B10 |
|---|---:|---:|
| Receiver +0x108 matches full independently recovered journal owner address | 13 of 15 | 4 of 11 |
| Receiver +0x108 saved null (no decoded journal parent) | 2 of 15 | 7 of 11 |

The new `DSPJRNRCV` display shows its **own** candidate +0x108
parent pointer and links exact matching journal primaries even if
neither journal-side +0x110/+0x240 slot lists the receiver.
`DSPJRN` can also show every receiver whose own saved pointer
matches that selected journal, without duplicating a receiver
already linked through a supported journal-side slot.

These two directions are independent byte evidence, **not** proof
of the current receiver, parent/previous/next receiver semantics,
chain history, entry sequence or any runtime state. Null pointers
and unsupported layouts are distinguished from missing journal
primaries, and full extender/address equality remains mandatory.
Additional synthetic regression tests verify both common release
variants, null parent pointers, six-byte-suffix false positives,
unreadable controls and a direct receiver parent link that exists
without either supported journal-side slot.

## Testing and remaining gates

- `tests/test_journal_receiver_workflows.py` exercises both
  observed release-control variants, exact extender+address equality,
  two slots, null/missing values, duplicate receiver origins,
  unrelated same-address-suffix negatives, malformed/truncated
  headers, discontinuous virtual extents and navigation/Back
  in both directions.
- `tools/validate_journal_receivers.py <extracted-original.hda>`
  builds a normal recovered inventory once and exercises both
  5250 commands, receiver links and Back. It reports aggregate
  counts only, and checks the original SHA-256 before/after.
- The consolidated `tools/validate_recent_workflows.py` also
  includes both types as separate **partial** user-visible
  workflows.

No original disk sectors, receiver entry contents, proprietary
journal records, or private object payloads are committed.
An actual per-image recovered-virtual acceptance pass is still
needed. Historical sender/receiver sequence interpretation,
journal entry formats, other saved pointer slots and exact
journal/receiver field names remain **unverified**.
