#!/usr/bin/env python3
"""Survey and provisionally rank all 268 IBM MI type/subtype names.

Inputs: modern IBM name catalog; existing audited decoder reviews; verified
manual page references; unverified lexical PDF hits; read-only, full-image
physical primary candidate signatures. No disk images or PDF files opened.

Scores are transparent PROJECT MANAGEMENT HEURISTICS, not empirically
measured decoding effort, verified binary relationships, or IBM facts.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.mi_object_inventory import read_data, inventory


def _load(root, filename):
    return json.loads((root / "research" / filename).read_text(encoding="utf-8"))


def survey_rows(root=ROOT):
    entries, reviews, _ = read_data(root)
    base = inventory(entries, reviews)
    image = _load(root, "mi_full_image_census.json")
    lexical = _load(root, "mi_lexical_type_coverage.json")
    policy = _load(root, "mi_survey_scoring.json")
    if image["schema_version"] != 2 or lexical["schema_version"] != 1:
        raise ValueError("Unexpected evidence schema")
    weights = policy["weights_percent"]
    if sum(weights.values()) != 100 or set(weights) != {
        "project_value", "shared_unlock", "evidence", "feasibility",
        "image_coverage",
    }:
        raise ValueError("Priority weights must sum to 100%")
    if lexical["total_exact_name_mentions"] != sum(
        x["exact_name_mentions"] for x in lexical["types"].values()
    ):
        raise ValueError("PDF lexical hit summary mismatch")
    for image_id, disk in image["images"].items():
        if disk["sector_bytes"] != 520:
            raise ValueError("Unexpected AS/400 sector size")
        if disk["accepted_candidates"] != sum(
            r["physical_primary_candidates"] for r in disk["by_type"].values()
        ):
            raise ValueError("Candidate primary count mismatch " + image_id)
        for key, item in disk["by_type"].items():
            if sum(item["segment_group_variants"].values()) != item["physical_primary_candidates"]:
                raise ValueError("Header variant count mismatch " + key)
    incoming = Counter()
    for review in reviews["reviews"].values():
        for item in review["relationships"]:
            incoming[item["target"]] += 1
    sources = image["images"]
    if set(sources) != {"marks-v2r3", "petes-b10"}:
        raise ValueError("Expected two independently identified images")
    domains = policy["domains"]
    rows = []
    for row in base:
        code = row["key"]
        name = row["name"]
        state = row["status"]
        audit = row["review"]
        mark = sources["marks-v2r3"]["by_type"].get(code)
        pete = sources["petes-b10"]["by_type"].get(code)
        m = mark["physical_primary_candidates"] if mark else 0
        p = pete["physical_primary_candidates"] if pete else 0
        total = m + p
        hits = lexical["types"].get(name, {})
        verified_pages = bool(audit and audit["manual_refs"])
        domain = next((group for group, keys in domains.items()
                       if code in keys), "Other / needs classification")

        value = 5 if code in policy["value_5"] else (
            4 if code in policy["value_4"] else (
                3 if code in policy["value_3"] else policy["default_value"]))
        leverage = policy["default_unlock"]
        if code in policy["shared_unlock_5"]:
            leverage = 5
        elif code in policy["shared_unlock_4"]:
            leverage = 4
        elif code in policy["shared_unlock_3"]:
            leverage = 3
        # Incoming reviewed logical relationships are weak evidence of
        # dependencies; they never imply verified persistent object pointers.
        if incoming[code] >= 5:
            leverage = max(leverage, 5)
        elif incoming[code] >= 3:
            leverage = max(leverage, 4)
        elif incoming[code] >= 1:
            leverage = max(leverage, 2)

        # 'Evidence' means available RESEARCH starting points, not proof
        # of a decoded binary field. Lexical hits contribute only 1 point.
        evidence = min(5, 1 + int(verified_pages)
                       + int(bool(hits.get("exact_name_mentions")))
                       + int(total > 0)
                       + int(state in ("evidence_only", "partial_decoder",
                                       "substantial_decoder")))
        feasibility = policy["feasibility_override"].get(
            code, {"substantial_decoder": 4, "partial_decoder": 4,
                   "evidence_only": 3, "identity_only": 2,
                   "cataloged_only": policy["default_feasibility"]}[state])
        # Capped/diminishing image abundance; no frequency == presence claim.
        coverage = (5 if m > 0 and p > 0 and total >= 200 else
                    4 if m > 0 and p > 0 and total >= 20 else
                    3 if m > 0 and p > 0 else
                    2 if total > 0 else 0)
        factors = {
            "project_value": value, "shared_unlock": leverage,
            "evidence": evidence, "feasibility": feasibility,
            "image_coverage": coverage,
        }
        score = round(sum(factors[k] * weights[k] for k in weights) / 5, 1)
        tier = ("Tier 1 — first research" if score >= 75 else
                "Tier 2 — near-term" if score >= 60 else
                "Tier 3 — exploratory" if score >= 45 else
                "Tier 4 — defer/presence check")
        observation = (
            "candidate_primaries_both" if m and p else
            "candidate_primaries_one" if total else
            "not_observed_by_signature"
        )
        rows.append({
            "code": row["code"], "key": code, "name": name,
            "category": row["category"], "description": row["description"],
            "domain": domain,
            "maturity": state,
            "manual_review_status": row["documentation"],
            "commands_and_apis": audit["interfaces"] if audit else [],
            "commands_reviewed": bool(audit),
            "relationship_count_reviewed": len(audit["relationships"]) if audit else 0,
            "incoming_documented_or_observed_links": incoming[code],
            "next_research_step": (
                audit["next_step"] if audit else
                "Review historical references and validate the object format "
                "before attempting type-specific field decoding."
            ),
            "physical_candidate_evidence": {
                "status": observation, "marks_v2r3": m, "petes_b10": p,
                "total": total,
                "marks_group_tags": mark["segment_group_variants"] if mark else {},
                "petes_group_tags": pete["segment_group_variants"] if pete else {},
            },
            "pdf_lexical_evidence_unverified": {
                "mentions": hits.get("exact_name_mentions", 0),
                "pdfs": hits.get("distinct_pdfs", 0),
            },
            "scores_out_of_5": factors,
            "priority_score_out_of_100": score,
            "tier": tier,
            "confidence": (
                "better_triage_basis" if verified_pages and m and p else
                "partial_triage_basis" if verified_pages or total else
                "catalog_only_uncertain"
            ),
        })
    rows.sort(key=lambda x: (-x["priority_score_out_of_100"], x["name"], x["key"]))
    return rows, image, policy


def summary(rows, image):
    observed = [r for r in rows if r["physical_candidate_evidence"]["total"]]
    total = len(rows)
    raw = {
        key for disk in image["images"].values()
        for key in disk["by_type"]
    }
    catalog = {r["key"] for r in rows}
    return {
        "cataloged_types": total,
        "named_types_with_candidate_primary": len(observed),
        "named_types_without_signature_match": total - len(observed),
        "unmapped_raw_codes": sorted(raw - catalog),
        "observed_distinct_raw_codes": len(raw),
        "with_verified_manual_pages": sum(r["manual_review_status"] == "initial_sources"
                                           for r in rows),
        "with_unverified_lexical_hits": sum(r["pdf_lexical_evidence_unverified"]["mentions"] > 0
                                            for r in rows),
        "by_tier": dict(Counter(r["tier"] for r in rows)),
        "image_candidates": {
            image_id: {
                "raw_codes": len(disk["by_type"]),
                "primary_candidates": disk["accepted_candidates"],
                "physical_sectors": disk["physical_sectors_scanned"],
            } for image_id, disk in image["images"].items()
        },
    }


def markdown(rows, image, policy):
    s = summary(rows, image)
    lines = [
        "# CISC AS/400 MI object survey — ranked research priorities", "",
        "Generated from the IBM 268-type catalog, audited decoder inventory,",
        "18-PDF unverified lexical index, selected reviewed manual pages, and",
        "complete physical-sector signature surveys of Mark V2R3 / Pete B10.",
        "",
        "**Scores are provisional research-planning judgments, NOT objective",
        "measurements of IBM object complexity, version availability,",
        "true live-object counts, or confirmed binary pointers.**", "",
        f"**{s['cataloged_types']}** IBM catalog types; **{s['named_types_with_candidate_primary']}**"
        " have physical primary candidates on at least one image;",
        f"**{s['named_types_without_signature_match']}** had no match with this heuristic.",
        "No signature match does NOT mean the type was absent from the",
        "machine, release, or an incomplete archival image.", "",
        "Three observed raw MI codes outside the later IBM catalog: "
        + ", ".join(x[:2] + "/" + x[2:] for x in s["unmapped_raw_codes"])
        + ". Their names remain unknown pending separate research.", "",
        "## Scoring", "",
        "Weights: " + ", ".join(f"{k.replace('_',' ')} {v}%"
                              for k, v in policy["weights_percent"].items()) + ".",
        "Each factor is 0–5; weighted score is 0–100. Value, leverage and",
        "feasibility are **curated hypotheses**; image coverage and",
        "lexical hits are measurements with explicit limitations. This",
        "ranking intentionally does not equate high counts with usefulness.",
        "The weights and curated overrides are editable in",
        "research/mi_survey_scoring.json.", "",
        "## Highest research priorities", "",
        "| Rank | Code | Type | Area | Score | V / U / E / F / C | Mark | Pete | Maturity |",
        "|---:|---|---|---|---:|---|---:|---:|---|",
    ]
    for index, r in enumerate(rows[:30], 1):
        f = r["scores_out_of_5"]
        sig = "/".join(str(f[k]) for k in (
            "project_value", "shared_unlock", "evidence",
            "feasibility", "image_coverage",
        ))
        d = r["physical_candidate_evidence"]
        lines.append(
            f"| {index} | {r['code']} | {r['name']} | {r['domain']} | "
            f"{r['priority_score_out_of_100']:.1f} | {sig} | "
            f"{d['marks_v2r3']} | {d['petes_b10']} | {r['maturity']} |"
        )
    lines.extend([
        "", "## Full 268-type ranking", "",
        "Each record retains its later-IBM type description; the survey JSON",
        "also retains original segment tag frequencies and audit/relationship",
        "metadata. Zero below means **no signature match**, not absence.", "",
        "| # | Type | Code | Domain | Priority | Score | Mark | Pete | Decoder | Manual |",
        "|---:|---|---|---|---|---:|---:|---:|---|---|",
    ])
    for rank, r in enumerate(rows, 1):
        d = r["physical_candidate_evidence"]
        lines.append(
            f"| {rank} | {r['name']} | {r['code']} | {r['domain']} | "
            f"{r['tier'].split(' — ')[0]} | {r['priority_score_out_of_100']:.1f} | "
            f"{d['marks_v2r3']} | {d['petes_b10']} | "
            f"{r['maturity']} | {r['manual_review_status']} |"
        )
    lines.extend([
        "", "## Development workstreams", "",
        "Top items should be treated as *linked milestones*, not isolated",
        "decoder implementations: resolve shared EPA/virtual extents and",
        "context directories first, then file/member/index structures;",
        "use message-file and command definitions to inform menu and",
        "5250 prompting; investigate device/controller/line relationships",
        "using period documentation; put program MI disassembly on a",
        "separate longer-term track.", "",
        "Investigate the three unmapped codes and zero-match caveats before",
        "assuming the modern catalog is complete for the CISC releases.", "",
        "## Reproduction and evidence integrity", "",
        "Run: python3 tools/mi_full_primary_survey.py /path/to/marks.hda.zip",
        "Run: python3 tools/mi_survey_priorities.py --format summary",
        "Run: python3 tools/mi_survey_priorities.py --format json",
        "Use --check-report after updating catalog, reviews, counts or weights.",
        "No raw source disk bytes, full manuals, names, secrets, or",
        "user-profile payloads are committed. The underlying prior MI",
        "research PRs remain independent of this survey.", "",
    ])
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--format", choices=("summary","json","markdown"), default="summary")
    p.add_argument("--check-report", action="store_true")
    args = p.parse_args(argv)
    rows, image, policy = survey_rows()
    if args.check_report:
        report = ROOT / "docs/MI_SURVEY_PRIORITIES.md"
        if not report.is_file() or report.read_text(encoding="utf-8") != markdown(rows,image,policy):
            print("Survey priority report needs regeneration", file=sys.stderr)
            return 1
        print("Survey priority report is synchronized")
        return 0
    if args.format == "summary":
        print(json.dumps(summary(rows,image), indent=2))
    elif args.format == "json":
        print(json.dumps(rows, indent=2))
    else:
        sys.stdout.write(markdown(rows,image,policy))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
