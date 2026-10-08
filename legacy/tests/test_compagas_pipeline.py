import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compagas_pipeline import balance_patches, historical_split_2025, income_patches, reconciliation
from compagas_source import DATA


def record(year):
    return {"year": year, "facts": DATA[year]}


class CompagasPipelineTests(unittest.TestCase):
    def test_every_year_reconciles_to_published_totals(self):
        for year in (2023, 2024, 2025):
            with self.subTest(year=year):
                result = reconciliation(record(year))
                self.assertEqual(result["ebit_difference"], 0)
                self.assertEqual(result["pretax_difference"], 0)
                self.assertEqual(result["net_income_difference"], 0)
                self.assertEqual(result["assets_difference"], 0)
                self.assertEqual(result["asset_formula_difference"], 0)

    def test_confirmed_balance_formulas_are_retained(self):
        patches = balance_patches(record(2025), "M")
        self.assertEqual(patches["M26"], "=M27-M28")
        self.assertEqual(patches["M27"], "=M3-M4")
        self.assertEqual(patches["M28"], "=M11-M13")
        self.assertEqual(patches["M29"], "=M30-M31")

    def test_confirmed_income_formulas_are_retained(self):
        patches = income_patches(record(2025), "M")
        self.assertEqual(patches["M43"], "=M17+M18+M35")
        self.assertEqual(patches["M45"], "=M43+M44")
        self.assertEqual(patches["M46"], "=M47+M48")
        self.assertEqual(patches["M49"], "=M45+M46")
        self.assertEqual(patches["M50"], "=M51+M52")
        self.assertEqual(patches["M53"], "=M49+M50")

    def test_2025_pmso_split_uses_complete_historical_basis(self):
        split = historical_split_2025(record(2025))
        basis = split["basis"]
        self.assertEqual(basis["total"], basis["materials"] + basis["services"] + basis["other"])
        self.assertIn("*1753/67319", split["materials"])
        self.assertIn("*36268/67319", split["services"])
        self.assertEqual(split["other"].format(col="M"), "=-(39728)/1000-M23-M27")


if __name__ == "__main__":
    unittest.main()
