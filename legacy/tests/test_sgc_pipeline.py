import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sgc_pipeline import balance_patches, income_patches, reconciliation
from sgc_source import FACTS


RECORD = {"year": 2020, "facts": FACTS[2020]}


class SouthwestGasPipelineTests(unittest.TestCase):
    def test_reconciles_published_controls(self):
        result = reconciliation(RECORD)
        for key, value in result.items():
            if key.endswith("difference"):
                self.assertEqual(value, 0, key)

    def test_income_formulas(self):
        p = income_patches(RECORD, "H")
        self.assertEqual(p["H18"], "=-(406382)/1000")
        self.assertEqual(p["H35"], "=SUM(H36:H42)")
        self.assertEqual(p["H43"], "=H17+H18+H35")
        self.assertEqual(p["H45"], "=H43+H44")
        self.assertEqual(p["H46"], "=H47+H48")
        self.assertEqual(p["H49"], "=H45+H46")
        self.assertEqual(p["H50"], "=H51+H52")
        self.assertEqual(p["H53"], "=H49+H50")

    def test_balance_formulas(self):
        p = balance_patches(RECORD, "H")
        self.assertEqual(p["H25"], "=47482")
        self.assertEqual(p["H26"], "=H27-H28")
        self.assertEqual(p["H27"], "=H3-H4")
        self.assertEqual(p["H28"], "=H11-H13")
        self.assertEqual(p["H29"], "=H30-H31")


if __name__ == "__main__":
    unittest.main()
