import unittest
from spanish_cases.reviewed_southern import AR, CL, NATURE, income_ar, income_cl, formula
from control_planilla import arithmetic


def number(expression):
    return arithmetic(expression[1:]) if expression is not None else 0


class SouthernPilotTests(unittest.TestCase):
    def test_exact_disclosed_operands_and_units(self):
        self.assertEqual(formula([25978152,5499264],-1),'=-(25978152+5499264)/1000')
        self.assertIsNone(formula([]))

    def test_ecogas_all_years_reconcile_without_plugs(self):
        for year,facts in AR.items():
            rows=income_ar(year,facts)
            inputs=[3,13,16,20,21,22,26,28,29,30,32,33,34,40,41,42,44,45,48,51,52,56]
            self.assertAlmostEqual(sum(number(rows.get(r)) for r in inputs),facts['net']/1000,places=6)
            self.assertTrue(all(number(rows[r])<=0 for r in [16,20,21,22,26,28,29,30,32,33,34,40,41,42,44,48,52,56]))

    def test_metrogas_financial_reversal_separate_from_expenses(self):
        for year,facts in CL.items():
            rows=income_cl(facts)
            self.assertAlmostEqual(sum(number(v) for v in rows.values()),facts['net']/1000,places=6)
            self.assertLess(number(rows[52]),0)
        self.assertIn('60941950',income_cl(CL[2024])[13])
        self.assertNotIn('60941950',income_cl(CL[2024])[52])

    def test_ecogas_capitalized_personnel_excluded(self):
        self.assertEqual(sum(NATURE[2025][0]),21015404)
        self.assertNotIn('318055',str(income_ar(2025,AR[2025])))


if __name__=='__main__':
    unittest.main()
