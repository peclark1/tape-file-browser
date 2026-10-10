# AS/400 MI object decoding inventory

Generated from the two IBM type TSV catalogs and the audited
research/mi_object_reviews.json registry. Rebuild with the
tools/mi_object_inventory.py command-line script.

**Cataloged is NOT decoded or confirmed present in OS/400 V2R3.**
IBM object names come from later published tables; research states
describe the audited capabilities in this repository only.

**268 types**: 102 external; 166 internal. **28 reviewed types**, **19 with indexed historical manual pages**.

## Decoder maturity

| Status | Count |
|---|---:|
| Catalog only | 240 |
| Identity | 12 |
| Evidence | 7 |
| Partial | 7 |
| Substantial | 2 |

## Full IBM type inventory

| MI | IBM type | Category | Decoder | Historical manual pages |
|---|---|---|---|---|
| 19/F0 | *ACNAME | internal | Catalog only | — |
| 19/E0 | *ADO | internal | Catalog only | — |
| 0E/09 | *ALRTBL | external | Catalog only | — |
| 0E/C5 | *AUT | internal | Catalog only | — |
| 1B/C1 | *AUTHLR | internal | Catalog only | — |
| 1B/01 | *AUTL | external | Catalog only | — |
| 1E/05 | *BLKSF | external | Catalog only | — |
| 19/37 | *BNDDIR | external | Catalog only | — |
| 0F/C1 | *CBLK | internal | Catalog only | — |
| 0E/D2 | *CCSIDI | internal | Catalog only | — |
| 23/A1 | *CDJOBLK | internal | Catalog only | — |
| 23/A0 | *CDTCSLK | internal | Catalog only | — |
| 19/18 | *CFGL | external | Catalog only | — |
| 19/A4 | *CFGSPC | internal | Catalog only | — |
| 1E/06 | *CHRSF | external | Catalog only | — |
| 1E/C1 | *CHRSFC | internal | Catalog only | — |
| 19/0D | *CHTFMT | external | Catalog only | — |
| 19/A5 | *CIO | internal | Catalog only | — |
| 19/0B | *CLD | external | Catalog only | — |
| 19/04 | *CLS | external | Catalog only | — |
| 19/05 | *CMD | external | Evidence | primer-1992 p.230,438,439; starter-2001 p.478,479,480,518,519,520 |
| 0E/A0 | *CMTCDRI | internal | Catalog only | — |
| 17/01 | *CNNL | external | Catalog only | — |
| 19/FB | *CNVTBL | internal | Catalog only | — |
| 14/01 | *COSD | external | Catalog only | — |
| 19/2C | *CRG | external | Catalog only | — |
| 0E/A5 | *CRGM | internal | Catalog only | — |
| 0E/0F | *CRQD | external | Catalog only | — |
| 19/35 | *CSI | external | Catalog only | — |
| 19/22 | *CSPMAP | external | Catalog only | — |
| 19/23 | *CSPTBL | external | Catalog only | — |
| 12/01 | *CTLD | external | Identity | primer-1992 p.230 |
| 19/55 | *DBCOLES | internal | Catalog only | — |
| 19/50 | *DBDIR | internal | Catalog only | — |
| 19/D4 | *DBRCVR | internal | Catalog only | — |
| 19/F5 | *DCRENO | internal | Catalog only | — |
| 0A/C4 | *DCTQ | internal | Catalog only | — |
| 0E/CF | *DCXITC | internal | Catalog only | — |
| 0A/C5 | *DCXMSQ | internal | Catalog only | — |
| 1F/02 | *DDIR | external | Catalog only | — |
| 0D/52 | *DEACR | internal | Catalog only | — |
| 0C/50 | *DEADI | internal | Catalog only | — |
| 0B/51 | *DEADS | internal | Catalog only | — |
| 10/01 | *DEVD | external | Evidence | primer-1992 p.230,231; operations p.615 |
| 09/C1 | *DFTJRN | internal | Catalog only | — |
| 07/C1 | *DFTRCV | internal | Catalog only | — |
| 0C/01 | *DIR | external | Catalog only | — |
| 0D/51 | *DIRCR | internal | Catalog only | — |
| 0B/50 | *DIRDS | internal | Catalog only | — |
| 1E/50 | *DIRJ | internal | Catalog only | — |
| 1E/A0 | *DLSTMF | internal | Catalog only | — |
| 13/90 | *DMPSP | internal | Catalog only | — |
| 19/0E | *DOC | external | Partial | — |
| 06/C1 | *DOCBSS | internal | Partial | — |
| 0A/C3 | *DRQ | internal | Catalog only | — |
| 0E/D1 | *DRX | internal | Catalog only | — |
| 19/E9 | *DSNXO | internal | Catalog only | — |
| 1F/01 | *DSTMF | external | Catalog only | — |
| 19/0A | *DTAARA | external | Catalog only | — |
| 19/20 | *DTADCT | external | Catalog only | — |
| 0A/01 | *DTAQ | external | Identity | primer-1992 p.231 |
| 19/E2 | *DTO | internal | Catalog only | — |
| 19/E3 | *DUO | internal | Catalog only | — |
| 19/08 | *EDTD | external | Catalog only | — |
| 0E/D0 | *EDTIDX | internal | Catalog only | — |
| 19/D7 | *EPTAB | internal | Catalog only | — |
| 19/13 | *EXITRG | external | Catalog only | — |
| 19/53 | *EXITSP | internal | Catalog only | — |
| 0E/C6 | *FACB | internal | Catalog only | — |
| 0E/CA | *FCNUL | internal | Catalog only | — |
| 19/58 | *FCS | internal | Catalog only | — |
| 0E/04 | *FCT | external | Catalog only | — |
| 0B/A0 | *FIDTBL | internal | Catalog only | — |
| 1E/07 | *FIFO | external | Catalog only | — |
| 19/01 | *FILE | external | Partial | primer-1992 p.231 |
| 19/12 | *FLR | external | Partial | — |
| 19/51 | *FMT | internal | Partial | — |
| 19/26 | *FNTRSC | external | Catalog only | — |
| 19/2B | *FNTTBL | external | Catalog only | — |
| 19/28 | *FORMDF | external | Catalog only | — |
| 19/E8 | *FSO | internal | Catalog only | — |
| 0E/0B | *FTR | external | Catalog only | — |
| 19/CD | *GDA | internal | Catalog only | — |
| 0E/A4 | *GENIDX | internal | Catalog only | — |
| 0A/C8 | *GENQ | internal | Catalog only | — |
| 19/59 | *GRPDLS | internal | Catalog only | — |
| 19/0C | *GSS | external | Catalog only | — |
| 19/F7 | *HFSD | internal | Catalog only | — |
| 0A/C6 | *HPQ | internal | Catalog only | — |
| 19/C6 | *ICO | internal | Catalog only | — |
| 19/EB | *IDDEDT | internal | Catalog only | — |
| 0E/F3 | *IFSIDX | internal | Catalog only | — |
| 0E/06 | *IGCDCT | external | Catalog only | — |
| 19/E1 | *IGCINT | internal | Catalog only | — |
| 19/1A | *IGCSRT | external | Catalog only | — |
| 19/10 | *IGCTBL | external | Catalog only | — |
| 19/2E | *IMGCLG | external | Catalog only | — |
| 0E/50 | *IMPLREP | internal | Catalog only | — |
| 19/D5 | *INAUT | internal | Catalog only | — |
| 19/F4 | *INAUTO | internal | Catalog only | — |
| 19/C1 | *INITSP | internal | Catalog only | — |
| 04/C1 | *INTLIB | internal | Catalog only | — |
| 0E/C4 | *INTPRF | internal | Identity | — |
| 18/A1 | *IPLJMQ | internal | Catalog only | — |
| 19/1E | *IPXD | external | Catalog only | — |
| 04/C2 | *ISYSLIB | internal | Catalog only | — |
| 19/CA | *JAR | internal | Catalog only | — |
| 18/A0 | *JMQ | internal | Catalog only | — |
| 19/03 | *JOBD | external | Identity | primer-1992 p.232 |
| 0E/01 | *JOBQ | external | Identity | primer-1992 p.232 |
| 0E/0C | *JOBSCD | external | Catalog only | — |
| 09/01 | *JRN | external | Identity | primer-1992 p.232 |
| 0E/A6 | *JRNIX | internal | Catalog only | — |
| 07/01 | *JRNRCV | external | Identity | primer-1992 p.232 |
| 0A/F0 | *JSQ | internal | Catalog only | — |
| 0A/C1 | *JTMMQ | internal | Catalog only | — |
| 21/50 | *JVAGRP | internal | Catalog only | — |
| 02/50 | *JVAPGM | internal | Catalog only | — |
| 19/CE | *LDA | internal | Catalog only | — |
| 04/01 | *LIB | external | Substantial | primer-1992 p.217,218,230; operations p.110,111,112 |
| 19/D1 | *LIBRCVR | internal | Catalog only | — |
| 11/01 | *LIND | external | Identity | primer-1992 p.233; operations p.615 |
| 19/F2 | *LIRCVR | internal | Catalog only | — |
| 19/21 | *LOCALE | external | Catalog only | — |
| 1E/04 | *M36 | external | Catalog only | — |
| 19/24 | *M36CFG | external | Catalog only | — |
| 1E/52 | *MCBSF | internal | Catalog only | — |
| 19/C0 | *MCO | internal | Catalog only | — |
| 19/C8 | *MCOTBL | internal | Catalog only | — |
| 19/C9 | *MDO | internal | Catalog only | — |
| 19/E6 | *MDOC | internal | Catalog only | — |
| 19/1C | *MEDDFN | external | Catalog only | — |
| 0D/50 | *MEM | internal | Substantial | operations p.110,112 |
| 19/16 | *MENU | external | Identity | primer-1992 p.233 |
| 19/2D | *MGTCOL | external | Catalog only | — |
| 0E/C1 | *MNINX | internal | Catalog only | — |
| 19/CB | *MNTXT | internal | Catalog only | — |
| 15/01 | *MODD | external | Evidence | operations p.597,615 |
| 03/01 | *MODULE | external | Catalog only | — |
| 19/DF | *MQLOCK | internal | Catalog only | — |
| 19/EE | *MSCSP | internal | Catalog only | — |
| 0E/03 | *MSGF | external | Identity | primer-1992 p.233; operations p.146,147,150,151,152,153,172; power-tips p.352,353 |
| 19/02 | *MSGQ | external | Evidence | primer-1992 p.233 |
| 0E/91 | *MSRVI | internal | Catalog only | — |
| 19/E5 | *NFSP | internal | Catalog only | — |
| 19/2A | *NODGRP | external | Catalog only | — |
| 0E/0E | *NODL | external | Catalog only | — |
| 19/14 | *NTBD | external | Catalog only | — |
| 16/01 | *NWID | external | Catalog only | — |
| 19/39 | *NWSCFG | external | Catalog only | — |
| 1D/01 | *NWSD | external | Catalog only | — |
| 0D/EF | *OCUR | internal | Catalog only | — |
| 0D/EE | *OHCUR | internal | Catalog only | — |
| 19/52 | *OIRS | internal | Evidence | — |
| 1E/51 | *OLBSF | internal | Catalog only | — |
| 06/A0 | *OPTBSS | internal | Catalog only | — |
| 1E/ED | *OPTSTMF | internal | Catalog only | — |
| 19/E4 | *OSSCB | internal | Catalog only | — |
| 0E/02 | *OUTQ | external | Identity | primer-1992 p.233 |
| 19/29 | *OVL | external | Catalog only | — |
| 0D/ED | *OWCUR | internal | Catalog only | — |
| 19/36 | *PAGDFN | external | Catalog only | — |
| 19/27 | *PAGSEG | external | Catalog only | — |
| 19/CC | *PCCR | internal | Catalog only | — |
| 0E/11 | *PDFMAP | external | Catalog only | — |
| 19/30 | *PDG | external | Catalog only | — |
| 19/C7 | *PDT | internal | Catalog only | — |
| 02/01 | *PGM | external | Identity | primer-1992 p.230,234,439; starter-2001 p.478,480,521,524; operations p.111 |
| 19/15 | *PNLGRP | external | Catalog only | — |
| 1E/B2 | *POBSF | internal | Catalog only | — |
| 19/33 | *PRDAVL | external | Catalog only | — |
| 0E/F1 | *PRDAVLI | internal | Catalog only | — |
| 19/1B | *PRDDFN | external | Catalog only | — |
| 19/1D | *PRDLOD | external | Catalog only | — |
| 19/A1 | *PRMGEN | internal | Catalog only | — |
| 19/DA | *PROCT | internal | Catalog only | — |
| 0E/CB | *PRODT | internal | Catalog only | — |
| 0E/C7 | *PRTQ | internal | Catalog only | — |
| 19/25 | *PSFCFG | external | Catalog only | — |
| 19/FC | *PTCSPC | internal | Catalog only | — |
| 01/90 | *QDAG | internal | Catalog only | — |
| 0B/90 | *QDDS | internal | Partial | — |
| 0C/90 | *QDDSI | internal | Partial | — |
| 0E/90 | *QDIDX | internal | Evidence | — |
| 1A/90 | *QDPCS | internal | Catalog only | — |
| 0A/90 | *QDQ | internal | Catalog only | — |
| 19/90 | *QDSP | internal | Catalog only | — |
| 0E/A3 | *QFSIDX | internal | Catalog only | — |
| 19/32 | *QMFORM | external | Catalog only | — |
| 19/31 | *QMQRY | external | Catalog only | — |
| 19/11 | *QRYDFN | external | Catalog only | — |
| 01/EF | *QTAG | internal | Catalog only | — |
| 0B/EF | *QTDS | internal | Catalog only | — |
| 0C/EF | *QTDSI | internal | Catalog only | — |
| 0E/EF | *QTIDX | internal | Catalog only | — |
| 1A/EF | *QTPCS | internal | Catalog only | — |
| 0A/EF | *QTQ | internal | Catalog only | — |
| 19/EF | *QTSP | internal | Catalog only | — |
| 0E/08 | *RCT | external | Catalog only | — |
| 19/A0 | *RCYAP | internal | Catalog only | — |
| 19/C5 | *RWCB | internal | Catalog only | — |
| 19/A3 | *RZHRIPD | internal | Catalog only | — |
| 19/19 | *S36 | external | Catalog only | — |
| 19/F1 | *S36BCH | internal | Catalog only | — |
| 19/EA | *S36EPT | internal | Catalog only | — |
| 0E/CE | *S36HLP | internal | Catalog only | — |
| 19/EC | *S36HST | internal | Catalog only | — |
| 0E/CC | *S36IDX | internal | Catalog only | — |
| 19/09 | *SBSD | external | Catalog only | — |
| 0E/07 | *SCHIDX | external | Catalog only | — |
| 19/DC | *SCO | internal | Catalog only | — |
| 19/DE | *SCPFSP | internal | Catalog only | — |
| 0E/C2 | *SDQ | internal | Catalog only | — |
| 0E/C3 | *SECOBJ | internal | Catalog only | — |
| 19/C3 | *SEPT | internal | Catalog only | — |
| 19/F8 | *SHRCV | internal | Catalog only | — |
| 0A/C2 | *SIQ | internal | Catalog only | — |
| 0E/C9 | *SLFSMS | internal | Catalog only | — |
| 1E/B1 | *SMBSF | internal | Catalog only | — |
| 0E/F2 | *SMIDX | internal | Catalog only | — |
| 0A/F1 | *SMQ | internal | Catalog only | — |
| 19/F9 | *SNMTBL | internal | Catalog only | — |
| 1E/03 | *SOCKET | external | Catalog only | — |
| 0E/A7 | *SORTSEQ | internal | Catalog only | — |
| 1C/01 | *SPADCT | external | Catalog only | — |
| 19/C2 | *SPLCB | internal | Catalog only | — |
| 02/02 | *SQLPKG | external | Catalog only | — |
| 19/1F | *SQLUDT | external | Catalog only | — |
| 19/49 | *SQLXSR | external | Catalog only | — |
| 19/CF | *SRAUTH | internal | Catalog only | — |
| 19/DB | *SRDS | internal | Catalog only | — |
| 0E/C8 | *SRMIDX | internal | Catalog only | — |
| 19/F3 | *SRMSPC | internal | Catalog only | — |
| 02/03 | *SRVPGM | external | Catalog only | — |
| 0E/05 | *SSND | external | Catalog only | — |
| 1E/01 | *STMF | external | Catalog only | — |
| 0E/D3 | *STPWIDX | internal | Catalog only | — |
| 85/A0 | *STREAM | internal | Catalog only | — |
| 19/D2 | *SVAL | internal | Catalog only | — |
| 19/17 | *SVRSTG | external | Catalog only | — |
| 19/54 | *SVRSTGD | internal | Catalog only | — |
| 0E/CD | *SWFL | internal | Catalog only | — |
| 19/F6 | *SYAUTS | internal | Catalog only | — |
| 1E/02 | *SYMLNK | external | Catalog only | — |
| 19/D3 | *SYSBC | internal | Catalog only | — |
| 19/D6 | *SYSPRTI | internal | Catalog only | — |
| 19/D8 | *SYSRPYL | internal | Catalog only | — |
| 19/06 | *TBL | external | Catalog only | — |
| 0A/C7 | *TCPIPQ | internal | Catalog only | — |
| 19/60 | *TDS | internal | Catalog only | — |
| 19/2F | *TIMZON | external | Catalog only | — |
| 0A/F2 | *TNIPLMQ | internal | Catalog only | — |
| 0E/A2 | *TOKTBL | internal | Catalog only | — |
| 19/FE | *UBPSPC | internal | Catalog only | — |
| 19/D9 | *UFCB | internal | Catalog only | — |
| 19/E7 | *UFO | internal | Catalog only | — |
| 0E/0A | *USRIDX | external | Catalog only | — |
| 08/01 | *USRPRF | external | Evidence | primer-1992 p.28,29,31,32; operations p.34 |
| 0A/02 | *USRQ | external | Catalog only | — |
| 19/34 | *USRSPC | external | Catalog only | — |
| 0E/10 | *VLDL | external | Catalog only | — |
| 19/D0 | *WCBT | internal | Catalog only | — |
| 19/DD | *WCBTRO | internal | Catalog only | — |
| 19/38 | *WSCST | external | Catalog only | — |
| 19/FA | *X40 | internal | Catalog only | — |
| 0E/F0 | *X4Q | internal | Catalog only | — |
| 0E/A1 | *ZMFINX | internal | Catalog only | — |
| 19/A2 | *ZMFSPC | internal | Catalog only | — |

## Next steps and safety

Run the script with --type-code 19/05 for full decoder evidence,
implementation links, associated commands/APIs and object links.
Use --format json to retrieve all 268 joined records.
The research/manual_sources.json manifest distinguishes catalogued
PDF filenames from specifically reviewed PDF pages.
See docs/MI_RESEARCH_ROADMAP.md for evidence-gated priorities.
Keep image bytes, manual pages and user-profile credentials out of Git.
