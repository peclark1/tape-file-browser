"""The manual scanner only produces unverified lexical page-hit candidates."""
import unittest

from as400_object_types import catalog
from tools.mi_manual_scan import mention_pattern, scan_pages


class ManualKeywordIndexTests(unittest.TestCase):
    def test_whole_object_tokens_no_prefixes(self):
        entries = catalog()
        pattern = mention_pattern(entries)
        text = "Command (*CMD), program *PGM and *MSGF; not *CMDS, *PGM2 or *LIBLIST."
        seen = [match.group().upper() for match in pattern.finditer(text)]
        self.assertEqual(["*CMD", "*PGM", "*MSGF"], seen)

    def test_page_numbers_are_one_based_and_lexical_not_verified(self):
        entries = catalog()
        rows = scan_pages(
            ["*CMD *PGM *CMD", "case insensitive: *cmd",
             "some other text", "use a *USRPRF profile"],
            entries,
            max_pages_per_type=2,
        )
        by_name = {row["object_type"]: row for row in rows}
        self.assertEqual(3, by_name["*CMD"]["hits"])
        self.assertEqual([1, 2], by_name["*CMD"]["pdf_pages_sample"])
        self.assertEqual([4], by_name["*USRPRF"]["pdf_pages_sample"])
        self.assertEqual("lexical_hit_unverified", by_name["*PGM"]["evidence"])
        self.assertFalse(any(item["object_type"] == "*MODD" for item in rows))

    def test_does_not_match_longer_ibm_parameter_literals(self):
        pattern = mention_pattern(catalog())
        text = "The values *PGMVAR, *MENUITEM and *FILEFIELD are not object types."
        self.assertEqual([], list(pattern.finditer(text)))


if __name__ == "__main__":
    unittest.main()
