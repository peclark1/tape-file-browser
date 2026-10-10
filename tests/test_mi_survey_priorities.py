"""Reproducible cross-evidence and ranking tests for the full MI survey."""
from collections import Counter
import contextlib
import io
import json
from pathlib import Path
import unittest

from tools.mi_object_inventory import ROOT, read_data
from tools.mi_survey_priorities import (
    main, markdown, summary, survey_rows,
)


class MISurveyPrioritiesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.images, cls.policy = survey_rows()
        cls.by_code = {r["key"]: r for r in cls.rows}
        cls.s = summary(cls.rows, cls.images)

    def test_catalog_completeness_and_exact_images(self):
        self.assertEqual(268, self.s["cataloged_types"])
        self.assertEqual(109, self.s["observed_distinct_raw_codes"])
        self.assertEqual(106, self.s["named_types_with_candidate_primary"])
        self.assertEqual(162, self.s["named_types_without_signature_match"])
        self.assertEqual(["0E00", "19C4", "19ED"],
                         self.s["unmapped_raw_codes"])
        self.assertEqual(19, self.s["with_verified_manual_pages"])
        self.assertEqual(86, self.s["with_unverified_lexical_hits"])
        self.assertEqual(
            20271, self.s["image_candidates"]["marks-v2r3"]["primary_candidates"])
        self.assertEqual(
            7570, self.s["image_candidates"]["petes-b10"]["primary_candidates"])
        self.assertEqual(1931265, self.s["image_candidates"]["marks-v2r3"]["physical_sectors"])
        self.assertEqual(616392, self.s["image_candidates"]["petes-b10"]["physical_sectors"])
        self.assertEqual(268, len({r["key"] for r in self.rows}))

    def test_all_268_have_transparent_scores_and_next_research_task(self):
        weights = self.policy["weights_percent"]
        self.assertEqual(100, sum(weights.values()))
        self.assertEqual(
            ["project_value", "shared_unlock", "evidence",
             "feasibility", "image_coverage"], list(weights))
        for row in self.rows:
            with self.subTest(code=row["code"]):
                factors = row["scores_out_of_5"]
                self.assertEqual(set(factors), set(weights))
                self.assertTrue(all(0 <= value <= 5 for value in factors.values()))
                calculated = round(
                    sum(factors[key] * weights[key] for key in weights) / 5, 1)
                self.assertEqual(calculated, row["priority_score_out_of_100"])
                self.assertTrue(row["next_research_step"])
                self.assertIn(row["physical_candidate_evidence"]["status"], (
                    "candidate_primaries_both",
                    "candidate_primaries_one",
                    "not_observed_by_signature"))
                self.assertTrue(row["tier"].startswith("Tier "))
        self.assertEqual(sorted(
            self.rows, key=lambda r: (-r["priority_score_out_of_100"],
                                     r["name"], r["key"])), self.rows)

    def test_priorities_highlight_shared_work_not_just_sector_frequency(self):
        self.assertEqual("*FILE", self.rows[0]["name"])
        self.assertLess(
            self.by_code["0201"]["scores_out_of_5"]["feasibility"], 3)
        self.assertGreater(
            self.by_code["1905"]["priority_score_out_of_100"],
            self.by_code["1926"]["priority_score_out_of_100"])
        self.assertGreater(
            self.by_code["0E03"]["scores_out_of_5"]["shared_unlock"], 3)
        # Lexical matches are explicitly unverified; never mistaken for
        # a verified historical manual page or binary offset.
        menu = self.by_code["1916"]
        self.assertEqual("initial_sources", menu["manual_review_status"])
        self.assertGreater(menu["pdf_lexical_evidence_unverified"]["mentions"], 0)
        self.assertEqual("partial_triage_basis",
                         self.by_code["19D4"]["confidence"])

    def test_zero_signature_count_is_not_absence_and_unknown_codes_survive(self):
        missing = next(r for r in self.rows
                       if r["physical_candidate_evidence"]["status"] ==
                          "not_observed_by_signature")
        self.assertEqual(0, missing["physical_candidate_evidence"]["total"])
        self.assertTrue(missing["next_research_step"])
        self.assertIn("does NOT mean", markdown(self.rows, self.images, self.policy))
        self.assertIn("0E/00, 19/C4, 19/ED",
                      markdown(self.rows, self.images, self.policy))
        # Four-family PGM census counted only tags 80/81/89; the broader
        # census includes newly observed 82/83/91 too.
        prog = self.by_code["0201"]["physical_candidate_evidence"]
        self.assertEqual((4346, 3102), (prog["marks_v2r3"], prog["petes_b10"]))
        self.assertEqual(30, prog["marks_group_tags"]["82"])

    def test_generated_markdown_is_identical_to_report(self):
        report = ROOT / "docs/MI_SURVEY_PRIORITIES.md"
        self.assertEqual(markdown(self.rows, self.images, self.policy),
                         report.read_text(encoding="utf-8"))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, main(["--check-report"]))

    def test_summary_and_json_output(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(0, main(["--format", "summary"]))
        self.assertEqual(268, json.loads(out.getvalue())["cataloged_types"])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(0, main(["--format", "json"]))
        decoded = json.loads(out.getvalue())
        self.assertEqual(268, len(decoded))
        self.assertEqual(self.rows[0]["code"], decoded[0]["code"])


if __name__ == "__main__":
    unittest.main()
