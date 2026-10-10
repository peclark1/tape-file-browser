#!/usr/bin/env python3
"""Audit MI type decoding against IBM catalog, reviewed code and manual citations.

Never reads an AS/400 image. The modern IBM catalogs label types but do not
establish that an object existed in OS/400 V2R3 or is fully decoded.
"""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from as400_object_types import catalog, lookup

STATUSES = (
    ("cataloged_only", "Catalog only"),
    ("identity_only", "Identity"),
    ("evidence_only", "Evidence"),
    ("partial_decoder", "Partial"),
    ("substantial_decoder", "Substantial"),
)
LABELS = dict(STATUSES)


def read_data(root=ROOT):
    reviews = json.loads((root / "research/mi_object_reviews.json").read_text())
    manuals = json.loads((root / "research/manual_sources.json").read_text())
    if reviews.get("schema_version") != 1 or manuals.get("schema_version") != 1:
        raise ValueError("Unsupported inventory schema")
    source_ids = {s["id"]: s for s in manuals["sources"]}
    if len(source_ids) != len(manuals["sources"]):
        raise ValueError("Duplicate manual ID")
    entries = catalog()
    if len(entries) != 268:
        raise ValueError("Unexpected type catalog size")
    for code, review in reviews["reviews"].items():
        if not re.fullmatch("[0-9A-F]{4}", code) or code not in entries:
            raise ValueError("Unknown reviewed MI code: " + code)
        if review["status"] not in LABELS or review["status"] == "cataloged_only":
            raise ValueError("Invalid reviewed state: " + code)
        if not review["scope"].strip() or not review["next_step"].strip():
            raise ValueError("Incomplete decoder review: " + code)
        for spec in review["implementation"]:
            file, colon, symbol = spec.partition(":")
            path = root / file
            if not colon or not symbol or not path.is_file():
                raise ValueError("Unknown implementation: " + code + " " + spec)
            if symbol not in path.read_text():
                raise ValueError("Missing implementation symbol: " + spec)
        for ref in review["manual_refs"]:
            doc = source_ids.get(ref["source"])
            if not doc or doc["review_status"] != "selected_pages_reviewed":
                raise ValueError("Unreviewed manual reference for " + code)
            known = {p for item in doc["verified_sections"]
                     for p in item["pdf_pages"]}
            if not ref["pdf_pages"] or not set(ref["pdf_pages"]).issubset(known):
                raise ValueError("Unverified manual page for " + code)
        for link in review["relationships"]:
            if link["target"] not in entries:
                raise ValueError("Unknown relationship target for " + code)
            if not link["relation"].strip() or not link["basis"].strip():
                raise ValueError("Relationship lacks evidence for " + code)
    return entries, reviews, manuals


def inventory(entries, reviews):
    rows = []
    for code, entry in entries.items():
        audit = reviews["reviews"].get(code)
        rows.append({
            "key": code, "code": entry.display_code, "name": entry.name,
            "category": entry.category, "description": entry.description,
            "status": audit["status"] if audit else "cataloged_only",
            "documentation": "initial_sources" if audit and audit["manual_refs"]
                             else "unreviewed",
            "review": audit,
        })
    return sorted(rows, key=lambda r: (r["name"], r["key"]))


def counts(rows):
    return {
        "types": len(rows),
        "external": sum(r["category"] == "external" for r in rows),
        "internal": sum(r["category"] == "internal" for r in rows),
        "manual_refs": sum(r["documentation"] == "initial_sources" for r in rows),
        "by_status": {key: sum(r["status"] == key for r in rows)
                      for key, _ in STATUSES},
    }


def markdown(rows):
    info = counts(rows)
    audited = info["types"] - info["by_status"]["cataloged_only"]
    lines = [
        "# AS/400 MI object decoding inventory", "",
        "Generated from the two IBM type TSV catalogs and the audited",
        "research/mi_object_reviews.json registry. Rebuild with the",
        "tools/mi_object_inventory.py command-line script.", "",
        "**Cataloged is NOT decoded or confirmed present in OS/400 V2R3.**",
        "IBM object names come from later published tables; research states",
        "describe the audited capabilities in this repository only.", "",
        f"**{info['types']} types**: {info['external']} external; "
        f"{info['internal']} internal. **{audited} reviewed types**, "
        f"**{info['manual_refs']} with indexed historical manual pages**.",
        "", "## Decoder maturity", "",
        "| Status | Count |", "|---|---:|",
    ]
    lines.extend(f"| {label} | {info['by_status'][key]} |"
                 for key, label in STATUSES)
    lines.extend([
        "", "## Full IBM type inventory", "",
        "| MI | IBM type | Category | Decoder | Historical manual pages |",
        "|---|---|---|---|---|",
    ])
    for row in rows:
        refs = row["review"]["manual_refs"] if row["review"] else []
        pages = "; ".join(
            ref["source"] + " p." + ",".join(str(n) for n in ref["pdf_pages"])
            for ref in refs
        ) or "—"
        lines.append(
            f"| {row['code']} | {row['name']} | {row['category']} | "
            f"{LABELS[row['status']]} | {pages} |"
        )
    lines.extend([
        "", "## Next steps and safety", "",
        "Run the script with --type-code 19/05 for full decoder evidence,",
        "implementation links, associated commands/APIs and object links.",
        "Use --format json to retrieve all 268 joined records.",
        "The research/manual_sources.json manifest distinguishes catalogued",
        "PDF filenames from specifically reviewed PDF pages.",
        "See docs/MI_RESEARCH_ROADMAP.md for evidence-gated priorities.",
        "Keep image bytes, manual pages and user-profile credentials out of Git.",
        "",
    ])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("summary", "json", "markdown"),
                        default="summary")
    parser.add_argument("--type-code", help="MI type as XX/YY")
    parser.add_argument("--check-report", action="store_true")
    args = parser.parse_args(argv)
    entries, reviews, _ = read_data()
    rows = inventory(entries, reviews)
    if args.check_report:
        dest = ROOT / "docs/MI_OBJECT_INVENTORY.md"
        if not dest.is_file() or dest.read_text() != markdown(rows):
            print("Generated inventory report is out of sync", file=sys.stderr)
            return 1
        print("Generated inventory report is synchronized")
        return 0
    if args.type_code:
        item = lookup(args.type_code)
        if not item:
            print("Unknown MI object type: " + args.type_code, file=sys.stderr)
            return 2
        selected = next(r for r in rows if r["key"] == item.code)
        print(json.dumps(selected, indent=2, ensure_ascii=False))
    elif args.format == "json":
        print(json.dumps(rows, indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        sys.stdout.write(markdown(rows))
    else:
        print(json.dumps(counts(rows), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
