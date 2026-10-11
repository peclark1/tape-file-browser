# Offline saved OUTQ machine-index workflow

This is a partial capability in the continuing 268-type CISC MI program, not a model of a live output queue.

## Guided 5250 use

- `WRKOUTQ OUTQ(*ALL/*)`: list recovered output-queue primaries and their origins.
- `WRKOUTQ OUTQ(*ALL/QPRINT) FORM(*STD)`: filter on an **observed byte token**, not certified printer-form metadata.
- `WRKOUTQ OUTQ(*ALL/QPRINT) KEYHEX(C1)`: filter on a literal prefix of 48-byte index keys.
- Select an entry with 5/Enter; examine exact hex and CP037 display lenses in eight-byte slices; F12/Back restores selection.
- All actions are read-only and bounded. No spool jobs are processed or OS/400 commands executed.

The standalone `as400_outq.py` is included in both install/uninstall workflows.

## Independent binary evidence

Both `marks.hda` (V2R3) and `petes.hda` (earlier B10) were inspected directly read-only, independently of the UI implementation. The observed 0E/02 primary-body prefix +0x100..105 is `20 00 00 30 00 20`; +0x420 contains an absolute six-byte tree root address. +0x42A is a four-byte page-size field: 2048 on examined Mark specimens, 1024 on examined Pete specimens. The existing strict release-2 machine-index traversal reconstructs 48-byte terminal keys using these fields. The new decoder does not assume a fixed physical root offset or concatenate across missing virtual extents.

A direct-contiguous-page exploratory probe of nine candidate Mark primary segments and two Pete segments produced supported 48-byte terminals. Mark `PRT010002` contained seven reconstructed terminal keys; `QPRINT` included a candidate `*STD` EBCDIC token in one key. Two Mark `QEZJOBLOG` physical-contiguous probes could not reconstruct the complete fragmented index and **are not counted as validated full-image traversals**. The app uses its proper reconstructed virtual extents; real-image end-to-end UI validation remains open. Other outputs included `FA`-prefixed control-like terminals. Their semantics have not been established: the GUI counts them separately and does not label them deleted, live, empty, or spool jobs.

The +0x108 and neighboring scalars have NOT been established as the count of currently enqueued spool entries. No count equality is asserted. The label `FORM` is a convenient *candidate-key filter* for the observed +0x20..+0x29 EBCDIC token; it does not establish a historical DDS or SLIC field name. Key order is machine-index traversal order, not proven chronological spool order. Spool identities, device association, file contents, entry status and object-pointer meanings remain unknown.

## Safeguards and tests

Unsupported prefixes, wrong page size, missing roots, invalid/free page boundaries and keys other than 48 bytes fail closed or emit diagnostics. Duplicate origins remain distinct. Synthetic fixtures exercise older/newer page sizes, relocated roots, key filtering, candidate token display, FA-prefixed control markers, selection/back, malformed terminals and truncated inputs. No real image bytes, credentials, private names or recovered spool contents are committed.

## Next evidence gate

Recover all 0E/02 roots using the production virtual-extent recovery on both images; compare the terminal fields with period IBM output-queue data-structure sources and independent SAV/restore metadata before declaring entry identity, spool/queue status or record semantics. Continue to other ranked types even while these semantics remain blocked.
