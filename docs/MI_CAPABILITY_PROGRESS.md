# MI capability progress — all 268 types

The full inventory is the continuing work queue. A PR is a review checkpoint, not completion.
Workflow state is independent of binary decoder maturity. Shared type/search navigation does not complete a type.
Queued means a type-specific Guided workflow still needs work/audit; existing forensic decoders may already exist.
Partial means a usable bounded workflow exists and its remaining scope is explicit. No type is claimed universally decoded.

States: delivered 0, partial 15, blocked 0, queued 253.

Generated from `research/mi_capabilities.json` and the ranked research inventory.
See [workflow evidence and validation](TYPE_CAPABILITY_WORKFLOWS.md).

| Rank | MI | Type | Workflow state | Usable workflow | Next material result |
|---:|---|---|---|---|---|
| 1 | 19/01 | *FILE | partial | DSPFD -> explicit format -> member -> paged selectable records; duplicate candidates retain exact origins. | Establish exact FCB format ownership/order and apply independently decoded logical-file selection rules. |
| 2 | 0D/50 | *MEM | partial | 6 selects a format/raw and browses 50-entry windows; 9 follows exact storage links. Back retains record, format and cursor selection. | Locate missing initial groups independently and support pointer-proven recovery where the QDDS primary is absent. |
| 3 | 19/05 | *CMD | partial | Find commands, traverse linked prompt labels/hints, inspect tentative default/value tokens. | Decode subordinate QUAL/ELEM ownership and value conversions; pursue MSGF/CPP links. |
| 4 | 04/01 | *LIB | partial | Library/context navigation with missing-primary directory entries. | Expose context-index incompleteness and candidate resolution as navigable recovery diagnostics. |
| 5 | 19/51 | *FMT | partial | Inspect descriptors and decode selected records using that exact chosen format; mismatched/out-of-record and invalid numeric fields remain visible. | Validate remaining field types, complete schema boundaries and CCSIDs against independent definitions. |
| 6 | 0B/90 | *QDDS | partial | Bounded random record windows with raw status, live/deleted hints, exact payload and selected field decoding; gaps/overlaps are never concatenated away. | Establish initial-group origin and unknown DENT variants; link validated index entries to exact records. |
| 7 | 0E/03 | *MSGF | queued | No type-specific Guided workflow audited yet. | Recover a bounded, verifiable internal message-ID index, first-/second-level text and substitution layout from multiple MSGF primaries; no generic decoding yet. |
| 8 | 02/01 | *PGM | queued | No type-specific Guided workflow audited yet. | Research original CISC MI program template/ODT boundaries and instruction format; distinguish strings/data from executable instructions. |
| 9 | 0C/90 | *QDDSI | partial | Inspect key specifications and field hints; follow exact referencing member cursors. | Navigate validated index entries to recovered records without treating unresolved key fields as decoded. |
| 10 | 0E/90 | *QDIDX | queued | No type-specific Guided workflow audited yet. | Identify reusable generic index page/element structures. |
| 11 | 10/01 | *DEVD | partial | Device identity and bounded class/type/model evidence. | Validate controller association before linking device/controller/line workflows. |
| 12 | 19/16 | *MENU | queued | No type-specific Guided workflow audited yet. | Trace compiled menu to separately recovered display file and message file or program using period-correct source examples; validate binary pointers. |
| 13 | 19/06 | *TBL | partial | DSPTBL: inspect 256 byte mappings/collisions and translate a bounded HEX sample offline. | Establish table purpose/CCSID/variant flags; compare other independently known conversion pairs. |
| 14 | 19/02 | *MSGQ | queued | No type-specific Guided workflow audited yet. | Decode message-entry structure after independent pointer and layout validation. |
| 15 | 19/52 | *OIRS | queued | No type-specific Guided workflow audited yet. | Document stable object-directory attributes and links to *QDIDX. |
| 16 | 08/01 | *USRPRF | partial | Safe identity/relationship view; no credential payload reads. | Add independently established non-sensitive profile relationships, preserving credential exclusion. |
| 17 | 12/01 | *CTLD | queued | No type-specific Guided workflow audited yet. | Research controller-specific layouts and *DEVD attached-controller references. |
| 18 | 19/0E | *DOC | partial | Find DOC primaries and follow all observed QDOC name+F companion candidates. | Strengthen anchor-key candidate associations to verified ownership and retain selected source while navigating document/folder graphs. |
| 19 | 15/01 | *MODD | partial | Mode identity and bounded configuration evidence. | Correlate mode fields with period definitions and link verified communications relationships. |
| 20 | 19/12 | *FLR | partial | WRKFLR -> explicit QAOSSS14 source -> candidate anchors -> parent/child graph and object matches; ambiguity/cycles/missing source remain visible. | Establish stronger object ownership links and user-facing QDLS paths; obtain Pete anchor storage before applying V2R3 layout there. |
| 21 | 11/01 | *LIND | queued | No type-specific Guided workflow audited yet. | Study line/controller/device relationships and period-correct configuration commands. |
| 22 | 06/C1 | *DOCBSS | partial | Inspect validated byte streams including owner-matched contiguous continuations; navigate exact byte ranges. | Add explicit encoding selection and independently validated document-format interpretation; retain raw bytes. |
| 23 | 19/0A | *DTAARA | partial | DSPDTAARA: inspect selector-04 character values by position with exact hex and CP037 lens. | Validate selectors 03/84 against known numeric/logical definitions; scale/storage remains unresolved. |
| 24 | 19/03 | *JOBD | queued | No type-specific Guided workflow audited yet. | Recover non-secret job attributes and references. |
| 25 | 0E/01 | *JOBQ | queued | No type-specific Guided workflow audited yet. | Identify index/layout differences for queue objects. |
| 26 | 0E/02 | *OUTQ | queued | No type-specific Guided workflow audited yet. | Research spool file/entry layout and queue index references. |
| 27 | 0E/08 | *RCT | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 28 | 0E/C4 | *INTPRF | queued | No type-specific Guided workflow audited yet. | Research internal interactive profile role and corroborate links to user profiles. |
| 29 | 18/A0 | *JMQ | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 30 | 19/CE | *LDA | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 31 | 19/15 | *PNLGRP | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 32 | 19/09 | *SBSD | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 33 | 0E/91 | *MSRVI | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 34 | 0E/07 | *SCHIDX | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 35 | 19/C2 | *SPLCB | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 36 | 19/26 | *FNTRSC | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 37 | 09/01 | *JRN | queued | No type-specific Guided workflow audited yet. | Research journal and receiver object storage relationships. |
| 38 | 19/04 | *CLS | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 39 | 0A/01 | *DTAQ | queued | No type-specific Guided workflow audited yet. | Document internal queue layout and test against real CISC samples. |
| 40 | 19/0C | *GSS | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 41 | 0E/09 | *ALRTBL | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 42 | 19/28 | *FORMDF | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 43 | 1B/01 | *AUTL | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 44 | 19/37 | *BNDDIR | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 45 | 0E/0C | *JOBSCD | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 46 | 19/36 | *PAGDFN | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 47 | 19/1D | *PRDLOD | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 48 | 02/02 | *SQLPKG | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 49 | 02/03 | *SRVPGM | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 50 | 19/38 | *WSCST | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 51 | 0E/C7 | *PRTQ | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 52 | 14/01 | *COSD | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 53 | 19/D4 | *DBRCVR | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 54 | 19/08 | *EDTD | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 55 | 0E/D0 | *EDTIDX | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 56 | 07/01 | *JRNRCV | queued | No type-specific Guided workflow audited yet. | Identify receiver entry structure and retention semantics. |
| 57 | 19/1B | *PRDDFN | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 58 | 19/90 | *QDSP | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 59 | 19/19 | *S36 | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 60 | 0E/C8 | *SRMIDX | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 61 | 0E/0A | *USRIDX | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 62 | 19/0D | *CHTFMT | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 63 | 19/0B | *CLD | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 64 | 17/01 | *CNNL | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 65 | 19/30 | *PDG | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 66 | 19/33 | *PRDAVL | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 67 | 0E/CE | *S36HLP | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 68 | 1C/01 | *SPADCT | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 69 | 19/D8 | *SYSRPYL | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 70 | 19/34 | *USRSPC | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 71 | 19/D7 | *EPTAB | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 72 | 19/E8 | *FSO | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 73 | 19/D5 | *INAUT | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 74 | 19/EE | *MSCSP | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 75 | 19/DA | *PROCT | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 76 | 19/C5 | *RWCB | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 77 | 19/EA | *S36EPT | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 78 | 19/DE | *SCPFSP | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 79 | 0E/C2 | *SDQ | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 80 | 19/C3 | *SEPT | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 81 | 0E/CD | *SWFL | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 82 | 19/E7 | *UFO | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 83 | 19/D0 | *WCBT | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 84 | 0E/C5 | *AUT | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 85 | 0E/D2 | *CCSIDI | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 86 | 19/FB | *CNVTBL | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 87 | 19/F5 | *DCRENO | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 88 | 0A/C4 | *DCTQ | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 89 | 0E/D1 | *DRX | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 90 | 0E/C6 | *FACB | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 91 | 19/F7 | *HFSD | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 92 | 0A/C6 | *HPQ | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 93 | 19/C6 | *ICO | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 94 | 19/F4 | *INAUTO | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 95 | 19/C1 | *INITSP | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 96 | 0A/F0 | *JSQ | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 97 | 0E/F1 | *PRDAVLI | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 98 | 0E/CB | *PRODT | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 99 | 19/EF | *QTSP | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 100 | 0E/CC | *S36IDX | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 101 | 0E/C9 | *SLFSMS | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 102 | 0E/F2 | *SMIDX | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 103 | 19/F9 | *SNMTBL | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 104 | 19/F3 | *SRMSPC | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 105 | 19/D2 | *SVAL | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 106 | 19/D3 | *SYSBC | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 107 | 0E/F0 | *X4Q | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 108 | 19/18 | *CFGL | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 109 | 19/2C | *CRG | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 110 | 0E/0F | *CRQD | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 111 | 19/35 | *CSI | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 112 | 19/22 | *CSPMAP | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 113 | 19/23 | *CSPTBL | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 114 | 0C/01 | *DIR | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 115 | 19/20 | *DTADCT | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 116 | 19/13 | *EXITRG | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 117 | 0E/04 | *FCT | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 118 | 1E/07 | *FIFO | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 119 | 19/2B | *FNTTBL | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 120 | 0E/0B | *FTR | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 121 | 19/CD | *GDA | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 122 | 19/1E | *IPXD | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 123 | 19/21 | *LOCALE | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 124 | 19/24 | *M36CFG | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 125 | 19/1C | *MEDDFN | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 126 | 19/2D | *MGTCOL | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 127 | 03/01 | *MODULE | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 128 | 19/2A | *NODGRP | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 129 | 0E/0E | *NODL | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 130 | 19/14 | *NTBD | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 131 | 16/01 | *NWID | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 132 | 1D/01 | *NWSD | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 133 | 19/29 | *OVL | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 134 | 19/27 | *PAGSEG | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 135 | 19/25 | *PSFCFG | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 136 | 19/32 | *QMFORM | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 137 | 19/31 | *QMQRY | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 138 | 19/11 | *QRYDFN | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 139 | 19/1F | *SQLUDT | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 140 | 0E/05 | *SSND | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 141 | 0A/02 | *USRQ | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 142 | 0E/10 | *VLDL | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 143 | 19/F0 | *ACNAME | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 144 | 19/E0 | *ADO | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 145 | 1B/C1 | *AUTHLR | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 146 | 1E/05 | *BLKSF | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 147 | 0F/C1 | *CBLK | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 148 | 23/A1 | *CDJOBLK | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 149 | 23/A0 | *CDTCSLK | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 150 | 19/A4 | *CFGSPC | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 151 | 1E/06 | *CHRSF | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 152 | 1E/C1 | *CHRSFC | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 153 | 19/A5 | *CIO | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 154 | 0E/A0 | *CMTCDRI | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 155 | 0E/A5 | *CRGM | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 156 | 19/55 | *DBCOLES | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 157 | 19/50 | *DBDIR | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 158 | 0E/CF | *DCXITC | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 159 | 0A/C5 | *DCXMSQ | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 160 | 1F/02 | *DDIR | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 161 | 0D/52 | *DEACR | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 162 | 0C/50 | *DEADI | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 163 | 0B/51 | *DEADS | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 164 | 09/C1 | *DFTJRN | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 165 | 07/C1 | *DFTRCV | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 166 | 0D/51 | *DIRCR | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 167 | 0B/50 | *DIRDS | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 168 | 1E/50 | *DIRJ | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 169 | 1E/A0 | *DLSTMF | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 170 | 13/90 | *DMPSP | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 171 | 0A/C3 | *DRQ | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 172 | 19/E9 | *DSNXO | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 173 | 1F/01 | *DSTMF | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 174 | 19/E2 | *DTO | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 175 | 19/E3 | *DUO | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 176 | 19/53 | *EXITSP | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 177 | 0E/CA | *FCNUL | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 178 | 19/58 | *FCS | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 179 | 0B/A0 | *FIDTBL | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 180 | 0E/A4 | *GENIDX | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 181 | 0A/C8 | *GENQ | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 182 | 19/59 | *GRPDLS | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 183 | 19/EB | *IDDEDT | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 184 | 0E/F3 | *IFSIDX | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 185 | 0E/06 | *IGCDCT | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 186 | 19/E1 | *IGCINT | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 187 | 19/1A | *IGCSRT | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 188 | 19/10 | *IGCTBL | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 189 | 19/2E | *IMGCLG | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 190 | 0E/50 | *IMPLREP | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 191 | 04/C1 | *INTLIB | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 192 | 18/A1 | *IPLJMQ | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 193 | 04/C2 | *ISYSLIB | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 194 | 19/CA | *JAR | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 195 | 0E/A6 | *JRNIX | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 196 | 0A/C1 | *JTMMQ | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 197 | 21/50 | *JVAGRP | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 198 | 02/50 | *JVAPGM | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 199 | 19/D1 | *LIBRCVR | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 200 | 19/F2 | *LIRCVR | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 201 | 1E/04 | *M36 | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 202 | 1E/52 | *MCBSF | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 203 | 19/C0 | *MCO | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 204 | 19/C8 | *MCOTBL | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 205 | 19/C9 | *MDO | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 206 | 19/E6 | *MDOC | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 207 | 0E/C1 | *MNINX | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 208 | 19/CB | *MNTXT | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 209 | 19/DF | *MQLOCK | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 210 | 19/E5 | *NFSP | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 211 | 19/39 | *NWSCFG | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 212 | 0D/EF | *OCUR | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 213 | 0D/EE | *OHCUR | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 214 | 1E/51 | *OLBSF | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 215 | 06/A0 | *OPTBSS | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 216 | 1E/ED | *OPTSTMF | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 217 | 19/E4 | *OSSCB | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 218 | 0D/ED | *OWCUR | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 219 | 19/CC | *PCCR | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 220 | 0E/11 | *PDFMAP | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 221 | 19/C7 | *PDT | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 222 | 1E/B2 | *POBSF | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 223 | 19/A1 | *PRMGEN | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 224 | 19/FC | *PTCSPC | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 225 | 01/90 | *QDAG | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 226 | 1A/90 | *QDPCS | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 227 | 0A/90 | *QDQ | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 228 | 0E/A3 | *QFSIDX | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 229 | 01/EF | *QTAG | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 230 | 0B/EF | *QTDS | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 231 | 0C/EF | *QTDSI | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 232 | 0E/EF | *QTIDX | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 233 | 1A/EF | *QTPCS | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 234 | 0A/EF | *QTQ | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 235 | 19/A0 | *RCYAP | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 236 | 19/A3 | *RZHRIPD | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 237 | 19/F1 | *S36BCH | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 238 | 19/EC | *S36HST | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 239 | 19/DC | *SCO | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 240 | 0E/C3 | *SECOBJ | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 241 | 19/F8 | *SHRCV | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 242 | 0A/C2 | *SIQ | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 243 | 1E/B1 | *SMBSF | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 244 | 0A/F1 | *SMQ | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 245 | 1E/03 | *SOCKET | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 246 | 0E/A7 | *SORTSEQ | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 247 | 19/49 | *SQLXSR | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 248 | 19/CF | *SRAUTH | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 249 | 19/DB | *SRDS | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 250 | 1E/01 | *STMF | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 251 | 0E/D3 | *STPWIDX | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 252 | 85/A0 | *STREAM | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 253 | 19/17 | *SVRSTG | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 254 | 19/54 | *SVRSTGD | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 255 | 19/F6 | *SYAUTS | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 256 | 1E/02 | *SYMLNK | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 257 | 19/D6 | *SYSPRTI | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 258 | 0A/C7 | *TCPIPQ | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 259 | 19/60 | *TDS | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 260 | 19/2F | *TIMZON | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 261 | 0A/F2 | *TNIPLMQ | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 262 | 0E/A2 | *TOKTBL | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 263 | 19/FE | *UBPSPC | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 264 | 19/D9 | *UFCB | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 265 | 19/DD | *WCBTRO | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 266 | 19/FA | *X40 | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 267 | 0E/A1 | *ZMFINX | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
| 268 | 19/A2 | *ZMFSPC | queued | No type-specific Guided workflow audited yet. | Review historical references and validate the object format before attempting type-specific field decoding. |
