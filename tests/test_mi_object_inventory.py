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
        self.assertEqual(28, sum(progress[k] for k, _ in STATUSES
                                 if k != "cataloged_only"))
        self.assertEqual(240, progress["cataloged_only"])
        self.assertEqual(2, progress["substantial_decoder"])
        self.assertEqual(7, progress["partial_decoder"])
        self.assertEqual(7, progress["evidence_only"])
        self.assertEqual(12, progress["identity_only"])
        found = {r["key"]: r for r in self.rows}
        self.assertEqual("substantial_decoder", found["0401"]["status"])
        self.assertEqual("evidence_only", found["1905"]["status"])
        self.assertEqual("identity_only", found["0201"]["status"])
        self.assertEqual("cataloged_only", found["19D4"]["status"])
        self.assertEqual("unreviewed", found["19D4"]["documentation"])

    def test_selected_manual_pages_are_verified_not_implied(self):
        sources = {s["id"]: s for s in self.manuals["sources"]}
        self.assertEqual(18, len(sources))
        self.assertEqual(4, sum(s["review_status"] == "selected_pages_reviewed"
                                for s in sources.values()))
        self.assertEqual(19, counts(self.rows)["manual_refs"])
        cmd = self.reviews["reviews"]["1905"]
        ref = next(r for r in cmd["manual_refs"]
                   if r["source"] == "primer-1992")
        self.assertEqual([230], ref["pdf_pages"])
        self.assertIn("command", ref["topic"].lower())
        self.assertTrue(all("source" in ref and "pdf_pages" in ref
                            for r in self.rows if r["review"]
                            for ref in r["review"]["manual_refs"]))

    def test_associations_distinguish_verified_logical_from_binary(self):
        cmd = self.reviews["reviews"]["1905"]
        target = next(t for t in cmd["relationships"]
                      if t["target"] == "0201")
        self.assertIn("on-disk pointer not decoded", target["basis"])
        user = self.reviews["reviews"]["0801"]
        self.assertTrue(any("credential" in line.lower()
                            for line in (user["scope"], user["next_step"])))
        self.assertTrue(all(t.get("basis") and t.get("relation")
                            for r in self.rows if r["review"]
                            for t in r["review"]["relationships"]))

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
