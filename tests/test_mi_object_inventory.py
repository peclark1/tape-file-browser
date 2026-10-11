"""Regression tests for the auditable 268-type MI decoding research registry."""
import contextlib
import io
import json
from pathlib import Path
import unittest

from tools.mi_object_inventory import (
    ROOT, STATUSES, counts, inventory, main, markdown, read_data,
)


class MIResearchInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries, cls.reviews, cls.manuals = read_data()
        cls.rows = inventory(cls.entries, cls.reviews)

    def test_full_ibm_catalog_accounted_for(self):
        total = counts(self.rows)
        self.assertEqual((268, 102, 166), (
            total["types"], total["external"], total["internal"]))
        self.assertEqual(total["types"], sum(total["by_status"].values()))
        self.assertEqual(len(self.rows), len({r["key"] for r in self.rows}))
        self.assertEqual(len(self.rows), len({r["code"] for r in self.rows}))

    def test_reviewed_vs_catalog_only_is_explicit(self):
        progress = counts(self.rows)["by_status"]
        self.assertEqual(34, sum(progress[k] for k, _ in STATUSES
                                 if k != "cataloged_only"))
        self.assertEqual(234, progress["cataloged_only"])
        self.assertEqual(2, progress["substantial_decoder"])
        self.assertEqual(19, progress["partial_decoder"])
        self.assertEqual(8, progress["evidence_only"])
        self.assertEqual(5, progress["identity_only"])
        found = {r["key"]: r for r in self.rows}
        self.assertEqual("substantial_decoder", found["0401"]["status"])
        self.assertEqual("partial_decoder", found["1905"]["status"])
        self.assertEqual("evidence_only", found["0201"]["status"])
        self.assertEqual("cataloged_only", found["19D4"]["status"])
        self.assertEqual("unreviewed", found["19D4"]["documentation"])

    def test_selected_manual_pages_are_verified_not_implied(self):
        sources = {s["id"]: s for s in self.manuals["sources"]}
        self.assertEqual(18, len(sources))
        self.assertEqual(5, sum(s["review_status"] == "selected_pages_reviewed"
                                for s in sources.values()))
        self.assertEqual(20, counts(self.rows)["manual_refs"])
        scan = self.manuals["lexical_scan_summary"]
        self.assertEqual(18, scan["manuals_scanned"])
        self.assertEqual(764, scan["total_type_mentions"])
        self.assertEqual(86, scan["distinct_ibm_type_names_across_corpus"])
        self.assertEqual(
            764, sum(source["lexical_scan"]["exact_token_mentions"]
                     for source in sources.values()))
        self.assertTrue(all(source["lexical_scan"]["status"]
                            == "automated_unverified_text_layer"
                            for source in sources.values()))
        cmd = self.reviews["reviews"]["1905"]
        ref = next(r for r in cmd["manual_refs"]
                   if r["source"] == "primer-1992")
        self.assertEqual([230, 438, 439], ref["pdf_pages"])
        self.assertIn("command", ref["topic"].lower())
        self.assertTrue(all("source" in ref and "pdf_pages" in ref
                            for r in self.rows if r["review"]
                            for ref in r["review"]["manual_refs"]))

    def test_associations_distinguish_verified_logical_from_binary(self):
        cmd = self.reviews["reviews"]["1905"]
        target = next(t for t in cmd["relationships"]
                      if t["target"] == "0201")
        self.assertIn("on-disk pointers are not decoded", target["basis"])
        user = self.reviews["reviews"]["0801"]
        self.assertTrue(any("credential" in line.lower()
                            for line in (user["scope"], user["next_step"])))
        self.assertTrue(all(t.get("basis") and t.get("relation")
                            for r in self.rows if r["review"]
                            for t in r["review"]["relationships"]))

    def test_four_type_historical_examples_keep_program_and_message_links_grounded(self):
        reviews = self.reviews["reviews"]
        cmd = reviews["1905"]
        msgf = reviews["0E03"]
        pgm = reviews["0201"]
        menu = reviews["1916"]
        self.assertIn("PR", cmd["manual_refs"][1]["topic"].upper())
        self.assertIn("ADDMSGD", msgf["interfaces"])
        self.assertTrue(any(
            link["target"] == "1901" and "unverified" in link["basis"]
            for link in msgf["relationships"]
        ))
        self.assertTrue(any(
            link["target"] == "1905" and "no compiled pointer" in link["basis"]
            for link in pgm["relationships"]
        ))
        self.assertEqual(
            {"1901", "0E03", "0201"},
            {link["target"] for link in menu["relationships"]}
        )
        self.assertEqual("partial_decoder", msgf["status"])
        self.assertEqual("evidence_only", pgm["status"])
        self.assertEqual("partial_decoder", menu["status"])
        self.assertEqual("partial_decoder", cmd["status"])

    def test_partial_image_presence_preserves_unscanned_distinction(self):
        by_code = {row["key"]: row for row in self.rows}
        self.assertEqual(
            "not_scanned", by_code["19D4"]["image_evidence"]["status"])
        self.assertEqual(
            "scanned_physical_primary_candidates",
            by_code["0E03"]["image_evidence"]["status"])
        expected = {
            "1905": (3129, 1117), "0E03": (56, 38),
            "1916": (574, 223), "0201": (4286, 3081),
        }
        for code, (marks, petes) in expected.items():
            with self.subTest(code=code):
                sample = by_code[code]["image_evidence"]["images"]
                self.assertEqual(
                    marks, sample["marks-v2r3"]["primary_candidates"])
                self.assertEqual(
                    petes, sample["petes-b10"]["primary_candidates"])
        self.assertEqual(
            264, sum(row["image_evidence"]["status"] == "not_scanned"
                     for row in self.rows))
        self.assertIn("not scanned", markdown(self.rows))

    def test_generated_markdown_is_in_sync(self):
        path = ROOT / "docs/MI_OBJECT_INVENTORY.md"
        self.assertEqual(markdown(self.rows), path.read_text(encoding="utf-8"))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, main(["--check-report"]))

    def test_full_json_and_type_lookup(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, main(["--type-code", "19/05"]))
        command = json.loads(output.getvalue())
        self.assertEqual("*CMD", command["name"])
        self.assertIn("QCDRCMDI", command["review"]["interfaces"])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, main(["--format", "json"]))
        rows = json.loads(output.getvalue())
        self.assertEqual(268, len(rows))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(2, main(["--type-code", "FF/FF"]))


if __name__ == "__main__":
    unittest.main()
