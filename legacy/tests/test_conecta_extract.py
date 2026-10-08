import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conecta_extract import LABELS, parse_revenue_page
from conecta_source import amount, norm


class RevenueTests(unittest.TestCase):
    def page(self):
        return "Dic-23 Dic-22\n" + "\n".join(f"{label} (1.234) 9.876" for label in LABELS)

    def test_current_not_comparative(self):
        result = parse_revenue_page(self.page(), 2023)
        self.assertEqual(result["Venta de gas"]["value_source_units"], -1234)

    def test_wrong_year_rejected(self):
        with self.assertRaises(ValueError):
            parse_revenue_page(self.page(), 2024)

    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            parse_revenue_page(self.page() + "\nVenta de gas 1.234 9.876", 2023)

    def test_missing_rejected(self):
        with self.assertRaises(ValueError):
            parse_revenue_page(self.page().replace("Venta de gas", "Otra etiqueta"), 2023)

    def test_dash_not_silently_zero(self):
        with self.assertRaises(ValueError):
            parse_revenue_page(self.page().replace("(1.234)", "-"), 2023)

    def test_source_amount_and_normalization(self):
        self.assertEqual(amount("(1.234)"), -1234)
        self.assertEqual(amount("-"), 0)
        self.assertEqual(norm("Regulación MIEM"), "regulacionmiem")
