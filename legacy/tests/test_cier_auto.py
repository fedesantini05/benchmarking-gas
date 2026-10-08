import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("cier_auto", ROOT / "cier_auto.py")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CoreTests(unittest.TestCase):
    def test_amount_parser(self):
        self.assertEqual(MODULE.amount("(1,234)"), -1234)
        self.assertEqual(MODULE.amount("1,234"), 1234)
        self.assertIsNone(MODULE.amount("-"))

    def test_formula_preserves_source_arithmetic(self):
        self.assertEqual(MODULE.formula_negative_sum([100, 25], "K", 55), "=-(100 + 25)*K$55/1000")
        self.assertEqual(MODULE.formula_sum([100, 25], "K", 55), "=(100 + 25)*K$55/1000")

    def test_pair_parser_skips_note(self):
        text = "Gastos financieros 12.A (23,883) (26,233)"
        self.assertEqual(MODULE.extract_pair(text, "Gastos financieros", note=True), (-23883, -26233))

    def test_pmso_estimation_preserves_total(self):
        result = MODULE.estimate_missing_pmso(
            total=-100.0,
            disclosed={"personnel": -45.0, "services": -30.0},
            missing=["materials", "other"],
            historical_periods=[
                {"total": -100.0, "materials": -10.0, "other": -15.0},
                {"total": -120.0, "materials": -18.0, "other": -12.0},
            ],
        )
        self.assertEqual(result["status"], "ESTIMATED")
        self.assertAlmostEqual(sum(result["estimates"].values()) - 75.0, -100.0)
        self.assertGreater(abs(result["estimates"]["materials"]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
