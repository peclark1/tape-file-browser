# Saved SCHIDX and MSRVI index-key explorer

## What is useful in Guided 5250

Two new read-only commands show supported, recovered release-2 machine-index
key evidence:

- `DSPSCHIDX SCHIDX(*ALL/*) KEYHEX(C1)`
- `DSPMSRVI MSRVI(*ALL/*) KEYHEX(C1)`

Select any returned 0E/07 `*SCHIDX` or 0E/91 `*MSRVI` recovered
primary. Matching keys are paged in 50-key windows; select one for the
full reconstructed key bytes in 16-byte chunks. The hex and CP037 views
are **display lenses** only, not field decoders. Back restores selection.
Unsupported layouts and damaged pages are withheld or reported. The
browsers are fully offline and cannot execute an OS/400 scheduler/service
action.

## Observed release-specific index control fields

Independent read-only probes of Pete's B10 and Mark's V2R3 physical
primary candidates identified index prefixes and the same control-field
locations as several independently decoded machine-index families.
SCHIDX was observed with prefix `E0 00 00 ?? 00 2E`,
MSRVI with `20 00 00 ?? 00 16` at primary +0x100.
The byte marked ?? is deliberately **not** interpreted. On both releases
the six-byte root absolute address is read at +0x420 and the four-byte
page-size value at +0x42A. The supported physical page sizes are 1024
or 2048 bytes. Release-2 prefix/common-text reconstruction and used-page
bounds are checked by `decode_context_machine_index(...,strict_pages=True)`.

Index terminals are treated as **opaque variable-length keys**; only
bounded lengths of 1–256 bytes are exposed, not guessed record structures.
The four-byte scalar at +0x106 is shown for provenance with an explicit
warning when it differs from recovered key count. It is not called a
live-job count, service record count or stored active-entry count.

Physical EPA-signature candidates are not interchangeable with complete
recovered objects. Unknown terminal sizes and failed or partial trees
remain diagnostic evidence, not negative proof that no scheduler or
service data existed.

## Validation and limitations

`tests/test_archival_index_workflows.py` covers both 1 KiB and 2 KiB
pages, relocated roots, 47/81-byte synthetic terminals, mismatched
scalars, truncation/invalid pages, selection, hex filtering and Back.
`tools/validate_archival_indexes.py` is an opt-in aggregate,
SHA-256-before/after read-only checker against an original extracted
`.hda`; it is **not** equivalent to running that full-image validation
until actual per-image results have been recorded.

No verified scheduler targets, scheduled-job identity, action semantics,
MSRVI service-record pointer, record content, or timestamp ordering is
provided. Later IBM APIs do not establish CISC on-disk offsets.
These remain two **partial** workflows in the continuing 268-type
capability program, rather than completed decoders.
