# CISC AS/400 MI object survey — ranked research priorities

Generated from the IBM 268-type catalog, audited decoder inventory,
18-PDF unverified lexical index, selected reviewed manual pages, and
complete physical-sector signature surveys of Mark V2R3 / Pete B10.

**Scores are provisional research-planning judgments, NOT objective
measurements of IBM object complexity, version availability,
true live-object counts, or confirmed binary pointers.**

**268** IBM catalog types; **106** have physical primary candidates on at least one image;
**162** had no match with this heuristic.
No signature match does NOT mean the type was absent from the
machine, release, or an incomplete archival image.

Three observed raw MI codes outside the later IBM catalog: 0E/00, 19/C4, 19/ED. Their names remain unknown pending separate research.

## Scoring

Weights: project value 30%, shared unlock 25%, evidence 20%, feasibility 15%, image coverage 10%.
Each factor is 0–5; weighted score is 0–100. Value, leverage and
feasibility are **curated hypotheses**; image coverage and
lexical hits are measurements with explicit limitations. This
ranking intentionally does not equate high counts with usefulness.
The weights and curated overrides are editable in
research/mi_survey_scoring.json.

## Highest research priorities

| Rank | Code | Type | Area | Score | V / U / E / F / C | Mark | Pete | Maturity |
|---:|---|---|---|---:|---|---:|---:|---|
| 1 | 19/01 | *FILE | Database and data access | 97.0 | 5/5/5/4/5 | 1325 | 1009 | partial_decoder |
| 2 | 0D/50 | *MEM | Core metadata and indexes | 93.0 | 5/5/4/4/5 | 505 | 73 | substantial_decoder |
| 3 | 19/05 | *CMD | Commands, programs and 5250 | 92.0 | 5/4/5/4/5 | 3129 | 1117 | evidence_only |
| 4 | 04/01 | *LIB | Core metadata and indexes | 92.0 | 5/5/5/3/4 | 50 | 22 | substantial_decoder |
| 5 | 19/51 | *FMT | Core metadata and indexes | 89.0 | 5/5/3/4/5 | 751 | 311 | partial_decoder |
| 6 | 0B/90 | *QDDS | Core metadata and indexes | 86.0 | 5/5/3/3/5 | 490 | 66 | partial_decoder |
| 7 | 0E/03 | *MSGF | Commands, programs and 5250 | 85.0 | 5/5/4/2/4 | 56 | 38 | identity_only |
| 8 | 02/01 | *PGM | Commands, programs and 5250 | 84.0 | 5/5/4/1/5 | 4346 | 3102 | identity_only |
| 9 | 0C/90 | *QDDSI | Core metadata and indexes | 84.0 | 5/5/3/3/4 | 35 | 18 | partial_decoder |
| 10 | 0E/90 | *QDIDX | Core metadata and indexes | 84.0 | 5/5/3/3/4 | 41 | 22 | evidence_only |
| 11 | 10/01 | *DEVD | Devices and communications | 82.0 | 5/3/5/3/4 | 42 | 12 | evidence_only |
| 12 | 19/16 | *MENU | Commands, programs and 5250 | 82.0 | 5/4/4/2/5 | 574 | 223 | identity_only |
| 13 | 19/02 | *MSGQ | Commands, programs and 5250 | 81.0 | 4/4/5/3/4 | 50 | 31 | evidence_only |
| 14 | 19/52 | *OIRS | Core metadata and indexes | 78.0 | 4/5/3/3/4 | 41 | 33 | evidence_only |
| 15 | 08/01 | *USRPRF | Users and security | 78.0 | 4/4/5/2/4 | 43 | 10 | evidence_only |
| 16 | 12/01 | *CTLD | Devices and communications | 74.0 | 4/4/4/2/4 | 21 | 4 | identity_only |
| 17 | 19/0E | *DOC | Documents and office | 74.0 | 4/3/4/3/5 | 2016 | 258 | partial_decoder |
| 18 | 15/01 | *MODD | Devices and communications | 74.0 | 4/3/5/3/3 | 9 | 4 | evidence_only |
| 19 | 19/12 | *FLR | Documents and office | 72.0 | 4/3/4/3/4 | 24 | 5 | partial_decoder |
| 20 | 11/01 | *LIND | Devices and communications | 72.0 | 4/4/4/2/3 | 5 | 2 | identity_only |
| 21 | 19/06 | *TBL | Database and data access | 72.0 | 4/4/3/2/5 | 631 | 88 | cataloged_only |
| 22 | 06/C1 | *DOCBSS | Documents and office | 69.0 | 4/4/3/3/2 | 1987 | 0 | partial_decoder |
| 23 | 19/03 | *JOBD | Database and data access | 69.0 | 4/3/4/2/4 | 34 | 15 | identity_only |
| 24 | 0E/01 | *JOBQ | Database and data access | 69.0 | 4/3/4/2/4 | 22 | 4 | identity_only |
| 25 | 0E/02 | *OUTQ | Database and data access | 67.0 | 4/3/4/2/3 | 9 | 2 | identity_only |
| 26 | 0E/08 | *RCT | Core metadata and indexes | 67.0 | 4/3/3/2/5 | 172 | 48 | cataloged_only |
| 27 | 0E/C4 | *INTPRF | Users and security | 66.0 | 4/4/2/2/4 | 17 | 4 | identity_only |
| 28 | 18/A0 | *JMQ | Core metadata and indexes | 62.0 | 4/4/2/2/2 | 415 | 0 | cataloged_only |
| 29 | 19/CE | *LDA | Core metadata and indexes | 57.0 | 4/1/3/2/5 | 414 | 20 | cataloged_only |
| 30 | 19/15 | *PNLGRP | Commands, programs and 5250 | 57.0 | 4/1/3/2/5 | 513 | 234 | cataloged_only |

## Full 268-type ranking

Each record retains its later-IBM type description; the survey JSON
also retains original segment tag frequencies and audit/relationship
metadata. Zero below means **no signature match**, not absence.

| # | Type | Code | Domain | Priority | Score | Mark | Pete | Decoder | Manual |
|---:|---|---|---|---|---:|---:|---:|---|---|
| 1 | *FILE | 19/01 | Database and data access | Tier 1 | 97.0 | 1325 | 1009 | partial_decoder | initial_sources |
| 2 | *MEM | 0D/50 | Core metadata and indexes | Tier 1 | 93.0 | 505 | 73 | substantial_decoder | initial_sources |
| 3 | *CMD | 19/05 | Commands, programs and 5250 | Tier 1 | 92.0 | 3129 | 1117 | evidence_only | initial_sources |
| 4 | *LIB | 04/01 | Core metadata and indexes | Tier 1 | 92.0 | 50 | 22 | substantial_decoder | initial_sources |
| 5 | *FMT | 19/51 | Core metadata and indexes | Tier 1 | 89.0 | 751 | 311 | partial_decoder | unreviewed |
| 6 | *QDDS | 0B/90 | Core metadata and indexes | Tier 1 | 86.0 | 490 | 66 | partial_decoder | unreviewed |
| 7 | *MSGF | 0E/03 | Commands, programs and 5250 | Tier 1 | 85.0 | 56 | 38 | identity_only | initial_sources |
| 8 | *PGM | 02/01 | Commands, programs and 5250 | Tier 1 | 84.0 | 4346 | 3102 | identity_only | initial_sources |
| 9 | *QDDSI | 0C/90 | Core metadata and indexes | Tier 1 | 84.0 | 35 | 18 | partial_decoder | unreviewed |
| 10 | *QDIDX | 0E/90 | Core metadata and indexes | Tier 1 | 84.0 | 41 | 22 | evidence_only | unreviewed |
| 11 | *DEVD | 10/01 | Devices and communications | Tier 1 | 82.0 | 42 | 12 | evidence_only | initial_sources |
| 12 | *MENU | 19/16 | Commands, programs and 5250 | Tier 1 | 82.0 | 574 | 223 | identity_only | initial_sources |
| 13 | *MSGQ | 19/02 | Commands, programs and 5250 | Tier 1 | 81.0 | 50 | 31 | evidence_only | initial_sources |
| 14 | *OIRS | 19/52 | Core metadata and indexes | Tier 1 | 78.0 | 41 | 33 | evidence_only | unreviewed |
| 15 | *USRPRF | 08/01 | Users and security | Tier 1 | 78.0 | 43 | 10 | evidence_only | initial_sources |
| 16 | *CTLD | 12/01 | Devices and communications | Tier 2 | 74.0 | 21 | 4 | identity_only | initial_sources |
| 17 | *DOC | 19/0E | Documents and office | Tier 2 | 74.0 | 2016 | 258 | partial_decoder | unreviewed |
| 18 | *MODD | 15/01 | Devices and communications | Tier 2 | 74.0 | 9 | 4 | evidence_only | initial_sources |
| 19 | *FLR | 19/12 | Documents and office | Tier 2 | 72.0 | 24 | 5 | partial_decoder | unreviewed |
| 20 | *LIND | 11/01 | Devices and communications | Tier 2 | 72.0 | 5 | 2 | identity_only | initial_sources |
| 21 | *TBL | 19/06 | Database and data access | Tier 2 | 72.0 | 631 | 88 | cataloged_only | unreviewed |
| 22 | *DOCBSS | 06/C1 | Documents and office | Tier 2 | 69.0 | 1987 | 0 | partial_decoder | unreviewed |
| 23 | *JOBD | 19/03 | Database and data access | Tier 2 | 69.0 | 34 | 15 | identity_only | initial_sources |
| 24 | *JOBQ | 0E/01 | Database and data access | Tier 2 | 69.0 | 22 | 4 | identity_only | initial_sources |
| 25 | *OUTQ | 0E/02 | Database and data access | Tier 2 | 67.0 | 9 | 2 | identity_only | initial_sources |
| 26 | *RCT | 0E/08 | Core metadata and indexes | Tier 2 | 67.0 | 172 | 48 | cataloged_only | unreviewed |
| 27 | *INTPRF | 0E/C4 | Users and security | Tier 2 | 66.0 | 17 | 4 | identity_only | unreviewed |
| 28 | *JMQ | 18/A0 | Core metadata and indexes | Tier 2 | 62.0 | 415 | 0 | cataloged_only | unreviewed |
| 29 | *LDA | 19/CE | Core metadata and indexes | Tier 3 | 57.0 | 414 | 20 | cataloged_only | unreviewed |
| 30 | *PNLGRP | 19/15 | Commands, programs and 5250 | Tier 3 | 57.0 | 513 | 234 | cataloged_only | unreviewed |
| 31 | *SBSD | 19/09 | Database and data access | Tier 3 | 57.0 | 15 | 4 | cataloged_only | unreviewed |
| 32 | *DTAARA | 19/0A | Database and data access | Tier 3 | 55.0 | 37 | 54 | cataloged_only | unreviewed |
| 33 | *MSRVI | 0E/91 | Core metadata and indexes | Tier 3 | 53.0 | 6 | 3 | cataloged_only | unreviewed |
| 34 | *SCHIDX | 0E/07 | Core metadata and indexes | Tier 3 | 53.0 | 1 | 5 | cataloged_only | unreviewed |
| 35 | *SPLCB | 19/C2 | Core metadata and indexes | Tier 3 | 53.0 | 415 | 19 | cataloged_only | unreviewed |
| 36 | *FNTRSC | 19/26 | Documents and office | Tier 3 | 51.0 | 1513 | 592 | cataloged_only | unreviewed |
| 37 | *JRN | 09/01 | Database and data access | Tier 3 | 51.0 | 10 | 4 | identity_only | initial_sources |
| 38 | *CLS | 19/04 | Commands, programs and 5250 | Tier 3 | 49.0 | 26 | 10 | cataloged_only | unreviewed |
| 39 | *DTAQ | 0A/01 | Database and data access | Tier 3 | 49.0 | 3 | 0 | identity_only | initial_sources |
| 40 | *GSS | 19/0C | Devices and communications | Tier 3 | 49.0 | 43 | 21 | cataloged_only | unreviewed |
| 41 | *ALRTBL | 0E/09 | Commands, programs and 5250 | Tier 3 | 47.0 | 2 | 2 | cataloged_only | unreviewed |
| 42 | *FORMDF | 19/28 | Commands, programs and 5250 | Tier 3 | 47.0 | 12 | 5 | cataloged_only | unreviewed |
| 43 | *AUTL | 1B/01 | Users and security | Tier 3 | 45.0 | 2 | 0 | cataloged_only | unreviewed |
| 44 | *BNDDIR | 19/37 | Commands, programs and 5250 | Tier 3 | 45.0 | 5 | 0 | cataloged_only | unreviewed |
| 45 | *JOBSCD | 0E/0C | Database and data access | Tier 3 | 45.0 | 1 | 0 | cataloged_only | unreviewed |
| 46 | *PAGDFN | 19/36 | Commands, programs and 5250 | Tier 3 | 45.0 | 22 | 0 | cataloged_only | unreviewed |
| 47 | *PRDLOD | 19/1D | Devices and communications | Tier 3 | 45.0 | 40 | 0 | cataloged_only | unreviewed |
| 48 | *SQLPKG | 02/02 | Commands, programs and 5250 | Tier 3 | 45.0 | 1 | 0 | cataloged_only | unreviewed |
| 49 | *SRVPGM | 02/03 | Commands, programs and 5250 | Tier 3 | 45.0 | 3 | 0 | cataloged_only | unreviewed |
| 50 | *WSCST | 19/38 | Documents and office | Tier 3 | 45.0 | 66 | 0 | cataloged_only | unreviewed |
| 51 | *PRTQ | 0E/C7 | Other / needs classification | Tier 4 | 43.0 | 15 | 3 | cataloged_only | unreviewed |
| 52 | *COSD | 14/01 | Devices and communications | Tier 4 | 41.0 | 5 | 3 | cataloged_only | unreviewed |
| 53 | *DBRCVR | 19/D4 | Other / needs classification | Tier 4 | 41.0 | 1 | 0 | cataloged_only | unreviewed |
| 54 | *EDTD | 19/08 | Database and data access | Tier 4 | 41.0 | 5 | 2 | cataloged_only | unreviewed |
| 55 | *EDTIDX | 0E/D0 | Other / needs classification | Tier 4 | 41.0 | 4 | 0 | cataloged_only | unreviewed |
| 56 | *JRNRCV | 07/01 | Database and data access | Tier 4 | 41.0 | 0 | 0 | identity_only | initial_sources |
| 57 | *PRDDFN | 19/1B | Other / needs classification | Tier 4 | 41.0 | 3 | 4 | cataloged_only | unreviewed |
| 58 | *QDSP | 19/90 | Core metadata and indexes | Tier 4 | 41.0 | 8 | 0 | cataloged_only | unreviewed |
| 59 | *S36 | 19/19 | Devices and communications | Tier 4 | 41.0 | 1 | 1 | cataloged_only | unreviewed |
| 60 | *SRMIDX | 0E/C8 | Other / needs classification | Tier 4 | 41.0 | 10 | 0 | cataloged_only | unreviewed |
| 61 | *USRIDX | 0E/0A | Database and data access | Tier 4 | 41.0 | 1 | 0 | cataloged_only | unreviewed |
| 62 | *CHTFMT | 19/0D | Documents and office | Tier 4 | 39.0 | 0 | 8 | cataloged_only | unreviewed |
| 63 | *CLD | 19/0B | Other / needs classification | Tier 4 | 39.0 | 7 | 0 | cataloged_only | unreviewed |
| 64 | *CNNL | 17/01 | Devices and communications | Tier 4 | 39.0 | 1 | 0 | cataloged_only | unreviewed |
| 65 | *PDG | 19/30 | Other / needs classification | Tier 4 | 39.0 | 2 | 0 | cataloged_only | unreviewed |
| 66 | *PRDAVL | 19/33 | Other / needs classification | Tier 4 | 39.0 | 2 | 0 | cataloged_only | unreviewed |
| 67 | *S36HLP | 0E/CE | Other / needs classification | Tier 4 | 39.0 | 82 | 1 | cataloged_only | unreviewed |
| 68 | *SPADCT | 1C/01 | Other / needs classification | Tier 4 | 39.0 | 0 | 18 | cataloged_only | unreviewed |
| 69 | *SYSRPYL | 19/D8 | Other / needs classification | Tier 4 | 39.0 | 1 | 0 | cataloged_only | unreviewed |
| 70 | *USRSPC | 19/34 | Other / needs classification | Tier 4 | 39.0 | 1 | 0 | cataloged_only | unreviewed |
| 71 | *EPTAB | 19/D7 | Other / needs classification | Tier 4 | 37.0 | 1 | 1 | cataloged_only | unreviewed |
| 72 | *FSO | 19/E8 | Other / needs classification | Tier 4 | 37.0 | 2 | 1 | cataloged_only | unreviewed |
| 73 | *INAUT | 19/D5 | Users and security | Tier 4 | 37.0 | 2 | 1 | cataloged_only | unreviewed |
| 74 | *MSCSP | 19/EE | Other / needs classification | Tier 4 | 37.0 | 7 | 5 | cataloged_only | unreviewed |
| 75 | *PROCT | 19/DA | Other / needs classification | Tier 4 | 37.0 | 1 | 1 | cataloged_only | unreviewed |
| 76 | *RWCB | 19/C5 | Other / needs classification | Tier 4 | 37.0 | 2 | 1 | cataloged_only | unreviewed |
| 77 | *S36EPT | 19/EA | Other / needs classification | Tier 4 | 37.0 | 1 | 1 | cataloged_only | unreviewed |
| 78 | *SCPFSP | 19/DE | Other / needs classification | Tier 4 | 37.0 | 1 | 1 | cataloged_only | unreviewed |
| 79 | *SDQ | 0E/C2 | Other / needs classification | Tier 4 | 37.0 | 1 | 1 | cataloged_only | unreviewed |
| 80 | *SEPT | 19/C3 | Other / needs classification | Tier 4 | 37.0 | 2 | 1 | cataloged_only | unreviewed |
| 81 | *SWFL | 0E/CD | Other / needs classification | Tier 4 | 37.0 | 2 | 1 | cataloged_only | unreviewed |
| 82 | *UFO | 19/E7 | Other / needs classification | Tier 4 | 37.0 | 1 | 1 | cataloged_only | unreviewed |
| 83 | *WCBT | 19/D0 | Other / needs classification | Tier 4 | 37.0 | 2 | 1 | cataloged_only | unreviewed |
| 84 | *AUT | 0E/C5 | Users and security | Tier 4 | 35.0 | 1 | 0 | cataloged_only | unreviewed |
| 85 | *CCSIDI | 0E/D2 | Other / needs classification | Tier 4 | 35.0 | 3 | 0 | cataloged_only | unreviewed |
| 86 | *CNVTBL | 19/FB | Other / needs classification | Tier 4 | 35.0 | 41 | 0 | cataloged_only | unreviewed |
| 87 | *DCRENO | 19/F5 | Other / needs classification | Tier 4 | 35.0 | 3 | 0 | cataloged_only | unreviewed |
| 88 | *DCTQ | 0A/C4 | Other / needs classification | Tier 4 | 35.0 | 2 | 0 | cataloged_only | unreviewed |
| 89 | *DRX | 0E/D1 | Other / needs classification | Tier 4 | 35.0 | 1 | 0 | cataloged_only | unreviewed |
| 90 | *FACB | 0E/C6 | Other / needs classification | Tier 4 | 35.0 | 2 | 0 | cataloged_only | unreviewed |
| 91 | *HFSD | 19/F7 | Other / needs classification | Tier 4 | 35.0 | 1 | 0 | cataloged_only | unreviewed |
| 92 | *HPQ | 0A/C6 | Other / needs classification | Tier 4 | 35.0 | 1 | 0 | cataloged_only | unreviewed |
| 93 | *ICO | 19/C6 | Other / needs classification | Tier 4 | 35.0 | 0 | 2 | cataloged_only | unreviewed |
| 94 | *INAUTO | 19/F4 | Other / needs classification | Tier 4 | 35.0 | 2 | 0 | cataloged_only | unreviewed |
| 95 | *INITSP | 19/C1 | Other / needs classification | Tier 4 | 35.0 | 1 | 0 | cataloged_only | unreviewed |
| 96 | *JSQ | 0A/F0 | Other / needs classification | Tier 4 | 35.0 | 1 | 0 | cataloged_only | unreviewed |
| 97 | *PRDAVLI | 0E/F1 | Other / needs classification | Tier 4 | 35.0 | 2 | 0 | cataloged_only | unreviewed |
| 98 | *PRODT | 0E/CB | Other / needs classification | Tier 4 | 35.0 | 1 | 0 | cataloged_only | unreviewed |
| 99 | *QTSP | 19/EF | Other / needs classification | Tier 4 | 35.0 | 1 | 0 | cataloged_only | unreviewed |
| 100 | *S36IDX | 0E/CC | Other / needs classification | Tier 4 | 35.0 | 1 | 0 | cataloged_only | unreviewed |
| 101 | *SLFSMS | 0E/C9 | Other / needs classification | Tier 4 | 35.0 | 2 | 0 | cataloged_only | unreviewed |
| 102 | *SMIDX | 0E/F2 | Other / needs classification | Tier 4 | 35.0 | 1 | 0 | cataloged_only | unreviewed |
| 103 | *SNMTBL | 19/F9 | Other / needs classification | Tier 4 | 35.0 | 1 | 0 | cataloged_only | unreviewed |
| 104 | *SRMSPC | 19/F3 | Other / needs classification | Tier 4 | 35.0 | 7 | 0 | cataloged_only | unreviewed |
| 105 | *SVAL | 19/D2 | Other / needs classification | Tier 4 | 35.0 | 2 | 0 | cataloged_only | unreviewed |
| 106 | *SYSBC | 19/D3 | Other / needs classification | Tier 4 | 35.0 | 2 | 0 | cataloged_only | unreviewed |
| 107 | *X4Q | 0E/F0 | Other / needs classification | Tier 4 | 35.0 | 1 | 0 | cataloged_only | unreviewed |
| 108 | *CFGL | 19/18 | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 109 | *CRG | 19/2C | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 110 | *CRQD | 0E/0F | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 111 | *CSI | 19/35 | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 112 | *CSPMAP | 19/22 | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 113 | *CSPTBL | 19/23 | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 114 | *DIR | 0C/01 | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 115 | *DTADCT | 19/20 | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 116 | *EXITRG | 19/13 | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 117 | *FCT | 0E/04 | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 118 | *FIFO | 1E/07 | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 119 | *FNTTBL | 19/2B | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 120 | *FTR | 0E/0B | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 121 | *GDA | 19/CD | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 122 | *IPXD | 19/1E | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 123 | *LOCALE | 19/21 | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 124 | *M36CFG | 19/24 | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 125 | *MEDDFN | 19/1C | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 126 | *MGTCOL | 19/2D | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 127 | *MODULE | 03/01 | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 128 | *NODGRP | 19/2A | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 129 | *NODL | 0E/0E | Devices and communications | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 130 | *NTBD | 19/14 | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 131 | *NWID | 16/01 | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 132 | *NWSD | 1D/01 | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 133 | *OVL | 19/29 | Documents and office | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 134 | *PAGSEG | 19/27 | Documents and office | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 135 | *PSFCFG | 19/25 | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 136 | *QMFORM | 19/32 | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 137 | *QMQRY | 19/31 | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 138 | *QRYDFN | 19/11 | Commands, programs and 5250 | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 139 | *SQLUDT | 19/1F | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 140 | *SSND | 0E/05 | Devices and communications | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 141 | *USRQ | 0A/02 | Other / needs classification | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 142 | *VLDL | 0E/10 | Users and security | Tier 4 | 31.0 | 0 | 0 | cataloged_only | unreviewed |
| 143 | *ACNAME | 19/F0 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 144 | *ADO | 19/E0 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 145 | *AUTHLR | 1B/C1 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 146 | *BLKSF | 1E/05 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 147 | *CBLK | 0F/C1 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 148 | *CDJOBLK | 23/A1 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 149 | *CDTCSLK | 23/A0 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 150 | *CFGSPC | 19/A4 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 151 | *CHRSF | 1E/06 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 152 | *CHRSFC | 1E/C1 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 153 | *CIO | 19/A5 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 154 | *CMTCDRI | 0E/A0 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 155 | *CRGM | 0E/A5 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 156 | *DBCOLES | 19/55 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 157 | *DBDIR | 19/50 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 158 | *DCXITC | 0E/CF | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 159 | *DCXMSQ | 0A/C5 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 160 | *DDIR | 1F/02 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 161 | *DEACR | 0D/52 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 162 | *DEADI | 0C/50 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 163 | *DEADS | 0B/51 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 164 | *DFTJRN | 09/C1 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 165 | *DFTRCV | 07/C1 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 166 | *DIRCR | 0D/51 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 167 | *DIRDS | 0B/50 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 168 | *DIRJ | 1E/50 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 169 | *DLSTMF | 1E/A0 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 170 | *DMPSP | 13/90 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 171 | *DRQ | 0A/C3 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 172 | *DSNXO | 19/E9 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 173 | *DSTMF | 1F/01 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 174 | *DTO | 19/E2 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 175 | *DUO | 19/E3 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 176 | *EXITSP | 19/53 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 177 | *FCNUL | 0E/CA | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 178 | *FCS | 19/58 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 179 | *FIDTBL | 0B/A0 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 180 | *GENIDX | 0E/A4 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 181 | *GENQ | 0A/C8 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 182 | *GRPDLS | 19/59 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 183 | *IDDEDT | 19/EB | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 184 | *IFSIDX | 0E/F3 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 185 | *IGCDCT | 0E/06 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 186 | *IGCINT | 19/E1 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 187 | *IGCSRT | 19/1A | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 188 | *IGCTBL | 19/10 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 189 | *IMGCLG | 19/2E | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 190 | *IMPLREP | 0E/50 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 191 | *INTLIB | 04/C1 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 192 | *IPLJMQ | 18/A1 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 193 | *ISYSLIB | 04/C2 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 194 | *JAR | 19/CA | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 195 | *JRNIX | 0E/A6 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 196 | *JTMMQ | 0A/C1 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 197 | *JVAGRP | 21/50 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 198 | *JVAPGM | 02/50 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 199 | *LIBRCVR | 19/D1 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 200 | *LIRCVR | 19/F2 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 201 | *M36 | 1E/04 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 202 | *MCBSF | 1E/52 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 203 | *MCO | 19/C0 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 204 | *MCOTBL | 19/C8 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 205 | *MDO | 19/C9 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 206 | *MDOC | 19/E6 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 207 | *MNINX | 0E/C1 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 208 | *MNTXT | 19/CB | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 209 | *MQLOCK | 19/DF | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 210 | *NFSP | 19/E5 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 211 | *NWSCFG | 19/39 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 212 | *OCUR | 0D/EF | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 213 | *OHCUR | 0D/EE | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 214 | *OLBSF | 1E/51 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 215 | *OPTBSS | 06/A0 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 216 | *OPTSTMF | 1E/ED | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 217 | *OSSCB | 19/E4 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 218 | *OWCUR | 0D/ED | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 219 | *PCCR | 19/CC | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 220 | *PDFMAP | 0E/11 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 221 | *PDT | 19/C7 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 222 | *POBSF | 1E/B2 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 223 | *PRMGEN | 19/A1 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 224 | *PTCSPC | 19/FC | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 225 | *QDAG | 01/90 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 226 | *QDPCS | 1A/90 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 227 | *QDQ | 0A/90 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 228 | *QFSIDX | 0E/A3 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 229 | *QTAG | 01/EF | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 230 | *QTDS | 0B/EF | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 231 | *QTDSI | 0C/EF | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 232 | *QTIDX | 0E/EF | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 233 | *QTPCS | 1A/EF | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 234 | *QTQ | 0A/EF | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 235 | *RCYAP | 19/A0 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 236 | *RZHRIPD | 19/A3 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 237 | *S36BCH | 19/F1 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 238 | *S36HST | 19/EC | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 239 | *SCO | 19/DC | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 240 | *SECOBJ | 0E/C3 | Users and security | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 241 | *SHRCV | 19/F8 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 242 | *SIQ | 0A/C2 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 243 | *SMBSF | 1E/B1 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 244 | *SMQ | 0A/F1 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 245 | *SOCKET | 1E/03 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 246 | *SORTSEQ | 0E/A7 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 247 | *SQLXSR | 19/49 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 248 | *SRAUTH | 19/CF | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 249 | *SRDS | 19/DB | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 250 | *STMF | 1E/01 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 251 | *STPWIDX | 0E/D3 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 252 | *STREAM | 85/A0 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 253 | *SVRSTG | 19/17 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 254 | *SVRSTGD | 19/54 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 255 | *SYAUTS | 19/F6 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 256 | *SYMLNK | 1E/02 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 257 | *SYSPRTI | 19/D6 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 258 | *TCPIPQ | 0A/C7 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 259 | *TDS | 19/60 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 260 | *TIMZON | 19/2F | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 261 | *TNIPLMQ | 0A/F2 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 262 | *TOKTBL | 0E/A2 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 263 | *UBPSPC | 19/FE | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 264 | *UFCB | 19/D9 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 265 | *WCBTRO | 19/DD | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 266 | *X40 | 19/FA | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 267 | *ZMFINX | 0E/A1 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |
| 268 | *ZMFSPC | 19/A2 | Other / needs classification | Tier 4 | 27.0 | 0 | 0 | cataloged_only | unreviewed |

## Development workstreams

Top items should be treated as *linked milestones*, not isolated
decoder implementations: resolve shared EPA/virtual extents and
context directories first, then file/member/index structures;
use message-file and command definitions to inform menu and
5250 prompting; investigate device/controller/line relationships
using period documentation; put program MI disassembly on a
separate longer-term track.

Investigate the three unmapped codes and zero-match caveats before
assuming the modern catalog is complete for the CISC releases.

## Reproduction and evidence integrity

Run: python3 tools/mi_full_primary_survey.py /path/to/marks.hda.zip
Run: python3 tools/mi_survey_priorities.py --format summary
Run: python3 tools/mi_survey_priorities.py --format json
Use --check-report after updating catalog, reviews, counts or weights.
No raw source disk bytes, full manuals, names, secrets, or
user-profile payloads are committed. The underlying prior MI
research PRs remain independent of this survey.
