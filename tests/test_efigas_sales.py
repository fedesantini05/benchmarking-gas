import unittest
from spanish_cases.efigas import sales_inputs, published_formula


class EfigasSalesTests(unittest.TestCase):
    def test_source_only_formulas_do_not_invent_a_breakdown(self):
        self.assertEqual(published_formula(530092,-1),'=-530092')
        self.assertEqual(published_formula(596889,-1),'=-596889')
        self.assertEqual(published_formula(100025),'=100025')
        with self.assertRaises(ValueError):
            published_formula(None)

    def test_one_total_and_blank_customer_detail(self):
        for column,income in [('K',680713),('L',723135),('M',801878)]:
            patch=sales_inputs(income,column)
            self.assertEqual(patch[f'{column}3'],income)
            for row in range(4,15):
                self.assertIsNone(patch[f'{column}{row}'])
            self.assertNotIn(f'{column}2',patch)
            self.assertNotIn(f'{column}15',patch)
            self.assertNotIn(f'{column}18',patch)


if __name__=='__main__':
    unittest.main()
