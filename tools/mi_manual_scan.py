#!/usr/bin/env python3
"""Find *candidate* IBM object-type mentions in a local AS/400 PDF corpus.

This is a lexical index, NOT evidence of a decoded object, a parameter layout,
or a reviewed manual citation. No manual text is copied to the result. PDFs
must be locally available. No OCR, network access, or disk-image access.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from as400_object_types import catalog


def mention_pattern(entries):
    names = sorted({entry.name for entry in entries.values()},
                   key=lambda name: (-len(name), name))
    # Avoid partial matches such as *LIB within *LIBLIST; matching is case
    # insensitive for historical OCR'd/text-layer typography.
    return re.compile(
        r"(?<![A-Z0-9#$@_])(?:"
        + "|".join(re.escape(name) for name in names)
        + r")(?![A-Z0-9#$@_])",
        re.IGNORECASE,
    )


def scan_pages(page_text, entries, *, max_pages_per_type=20):
    pattern = mention_pattern(entries)
    by_name = {entry.name: entry for entry in entries.values()}
    count = defaultdict(int)
    pages = defaultdict(list)
    for number, content in enumerate(page_text, 1):
        for matched in pattern.finditer(content):
            name = matched.group().upper()
            info = by_name[name]
            code = info.code
            count[code] += 1
            if number not in pages[code] and len(pages[code]) < max_pages_per_type:
                pages[code].append(number)
    return [
        {"code": code[:2] + "/" + code[2:],
         "object_type": entries[code].name,
         "hits": count[code],
         "pdf_pages_sample": pages[code],
         "evidence": "lexical_hit_unverified"}
        for code in sorted(count)
    ]


def extract_pdf_pages(path):
    try:
        proc = subprocess.run(
            ["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("pdftotext is required; install poppler-utils") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Failed to extract PDF text: {path}") from exc
    text = proc.stdout.decode("utf-8", errors="replace")
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def scan_pdf_member(zfile, member, entries):
    # Extract temporarily; no PDF content is retained or uploaded.
    with tempfile.TemporaryDirectory(prefix="mi-pdf-") as folder:
        dest = Path(folder) / "source.pdf"
        with zfile.open(member) as stream, dest.open("wb") as out:
            while True:
                block = stream.read(1024 * 1024)
                if not block:
                    break
                out.write(block)
        pages = extract_pdf_pages(dest)
    return {
        "scanned_pages": len(pages),
        "text_characters": sum(len(page) for page in pages),
        "matches": scan_pages(pages, entries),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, help="Local as400 manuals.zip")
    p.add_argument("--redbook", type=Path, help="Local disk-storage Redbook PDF")
    p.add_argument("--only-source", help="Optional manual ID from source manifest")
    p.add_argument("--output", type=Path, help="Write JSON candidate index here")
    args = p.parse_args(argv)
    if not args.archive and not args.redbook:
        p.error("Provide --archive and/or --redbook")
    sources = json.loads((ROOT / "research/manual_sources.json").read_text())
    all_entries = catalog()
    results = []
    for source in sources["sources"]:
        if args.only_source and args.only_source != source["id"]:
            continue
        if source["location"] == "as400 manuals.zip":
            if args.archive is None:
                continue
            with zipfile.ZipFile(args.archive) as zf:
                record = scan_pdf_member(zf, source["archive_member"], all_entries)
        elif args.redbook is not None:
            pages = extract_pdf_pages(args.redbook)
            record = {
                "scanned_pages": len(pages),
                "text_characters": sum(len(page) for page in pages),
                "matches": scan_pages(pages, all_entries),
            }
        else:
            continue
        results.append({"source_id": source["id"], **record})
    if args.only_source and not results:
        raise ValueError("Manual not found, or corresponding PDF input missing")
    result = {
        "method": "pdftotext text-layer exact lexical matches; no OCR",
        "review_status": "automatic_unverified_not_a_citation",
        "caution": "Verify PDF pages and actual context manually before adding manual_refs.",
        "documents": results,
    }
    data = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(data, encoding="utf-8")
        print(f"Indexed {len(results)} PDF(s); lexical hits require verification")
    else:
        sys.stdout.write(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
