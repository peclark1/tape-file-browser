# AS/400 manual corpus — first full lexical scan

**Evidence class: AUTOMATED TEXT HITS ONLY — NOT VERIFIED CITATIONS.**

This is the first exact *OBJECTTYPE keyword pass over **all 18 supplied PDF
manuals**, using the text already embedded in the PDFs. The archive has
17 manuals; the separate SG24-5693 disk-storage Redbook is the 18th.
The procedure uses text-layer extraction, case-insensitive whole-token
IBM type-name matching, and 1-based PDF page numbers. No OCR or image
interpretation was performed.

## Overall results

- **18 manuals scanned**.
- **764 exact object-name mentions** over the text layers.
- **86 of the 268 modern IBM cataloged names** have at least one match.
- **182 of 268** have no exact name match in this archive's extracted text.
  This is NOT evidence the historical system lacked these objects, nor
  that the PDFs contain no relevant underlying concepts.
- Some IBM internal types (for example *QDDS, *QDDSI, *DOCBSS, *MEM)
  have **zero literal matches**; technical descriptions often use
  architectural names rather than IBM i external object labels.

| PDF manual | PDF pages | Different types matched | Literal mentions |
|---|---:|---:|---:|
| Understanding AS/400 System Operations | 818 | 34 | 331 |
| Starter Kit: IBM iSeries & AS/400 (2001) | 630 | 83 | 180 |
| AS/400 Primer (1992) | 464 | 26 | 136 |
| AS/400 Power Tips and Techniques | 414 | 11 | 48 |
| IBM Redbook SG24-5693 Disk Storage Topics and Tools | 252 | 13 | 44 |
| SC41-9878-00 Licensed Programs / New Release Installation, V2 | 192 | 5 | 13 |
| SY31-9066-3 9404 Installation Guide | 152 | 2 | 12 |
| Remaining 11 PDF files | various | 0 each | 0 total |

The 11 no-match documents primarily cover machine service, parts,
problem analysis, 2xx upgrades and the CISC System Builder. The fact
that both copies of the **CISC System Builder** yielded no exact
star-prefixed MI object-type names is a methodological limitation of the
lexical search, **not a judgment that they lack useful MI/LIC material**.

## Selected page leads for manual review

Pages below are **lexical candidates**, not yet approved manual_refs
in the audited type registry. These page numbers must be checked for
actual discussion (rather than merely a TOC or example list) before
being promoted to source evidence.

| Type | Candidates, 1-based PDF page numbers | Direct lexical mentions across archive |
|---|---|---:|
| *CMD | Primer p.230; Starter Kit p.478; Power Tips p.223,325,340 | 28 |
| *PGM | Operations p.111,112,113,114; Primer p.229,230,234 | 56 |
| *USRPRF | Operations p.363,379,381,382; Starter Kit p.59,68,71 | 87 |
| *DEVD | Operations p.189,192,202; Primer p.171,174,230 | 41 |
| *MODD | Starter Kit p.478 | 1 |
| *MSGF | Primer p.233,242; Starter Kit p.478,522 | 6 |
| *MSGQ | Primer p.233; Operations p.114,148,585 | 17 |
| *MENU | Primer p.233,414; Redbook p.173 | 8 |
| *FILE | Operations p.111,112,114; Redbook p.111,161,173 | 103 |
| *CTLD | Primer p.230; Operations p.114 | 5 |
| *LIND | Operations p.605,645,646; Starter Kit p.478,576 | 23 |
| *OUTQ | Operations p.101,102,114; Primer p.233 | 29 |
| *DTAQ | Starter Kit p.218,225,235,242; Primer p.231 | 18 |

Human review has **already** verified a narrower set of selected pages,
recorded in research/manual_sources.json and
research/mi_object_reviews.json. Those citations remain distinct
from this automated candidate list.

## What to study next

1. Inspect OS/400 operations and the 2001 Starter Kit for DSP/CRT/CHG
   command associations and any depicted parameter screens or program
   processing references. Record exact IBM terms and the actual section.
2. Investigate the *CMD/*PGM/*MSGF/*MENU relationships from Primer p.230
   and p.233 and the Starter Kit's command-definition example p.478.
3. Review *DEVD/*CTLD/*LIND/*MODD command chapters, not just star-prefixed
   references. The operations manual has substantial mode material
   that **does not contain a literal *MODD token**.
4. Review disk architecture and CISC System Builder using page headings,
   MI object pointers, space/index terminology and structural keywords.
   A type-label-only search cannot replace reading those documents.
5. Use the offline script tools/mi_manual_scan.py to repeat scans against
   the same local PDFs or additional period manuals. Never promote a
   lexical hit into a verified manual citation without inspecting it.

No disk image, manual excerpts, or proprietary user records were
committed. This report contains only page leads and aggregate counts.
