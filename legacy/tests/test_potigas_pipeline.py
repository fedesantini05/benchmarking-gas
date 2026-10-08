import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from potigas_pipeline import balance_patches, income_patches, reconciliation
from potigas_source import FACTS
from potigas_multiyear_source import FACTS_2024, FACTS_2025


RECORD = {"year": 2023, "facts": FACTS}


class PotigasPipelineTests(unittest.TestCase):
    def test_reconciles_every_published_control(self):
        result = reconciliation(RECORD)
        for key, value in result.items():
            if key.endswith("difference"):
                self.assertEqual(value, 0, key)

    def test_confirmed_income_formulas(self):
        patches = income_patches(RECORD)
        self.assertEqual(patches["K3"], "=SUM(K4:K12)")
        self.assertEqual(patches["K35"], "=SUM(K36:K42)")
        self.assertEqual(patches["K43"], "=K17+K18+K35")
        self.assertEqual(patches["K45"], "=K43+K44")
        self.assertEqual(patches["K46"], "=K47+K48")
        self.assertEqual(patches["K49"], "=K45+K46")
        self.assertEqual(patches["K50"], "=K51+K52")
        self.assertEqual(patches["K53"], "=K49+K50")

    def test_confirmed_balance_formulas(self):
        patches = balance_patches(RECORD)
        self.assertEqual(patches["K26"], "=K27-K28")
        self.assertEqual(patches["K27"], "=K3-K4")
        self.assertEqual(patches["K28"], "=K11-K13")
        self.assertEqual(patches["K29"], "=K30-K31")

    def test_all_years_reconcile(self):
        for year, facts in ((2023, FACTS), (2024, FACTS_2024), (2025, FACTS_2025)):
            result = reconciliation({"year": year, "facts": facts})
            for key, value in result.items():
                if key.endswith("difference"):
                    self.assertEqual(value, 0, f"{year} {key}")

    def test_2025_traceable_special_formulas(self):
        record = {"year": 2025, "facts": FACTS_2025}
        income = income_patches(record, "M")
        balance = balance_patches(record, "M")
        self.assertEqual(income["M35"], "=SUM(M36:M42)")
        self.assertEqual(income["M53"], "=M49+M50")
        self.assertEqual(balance["M26"], "=M27-M28")
        self.assertEqual(balance["M27"], "=M3-M4")
        self.assertEqual(balance["M28"], "=M11-M13")
        self.assertEqual(balance["M29"], "=M30-M31")
        self.assertEqual(balance["M25"], "=4245")


if __name__ == "__main__":
    unittest.main()
