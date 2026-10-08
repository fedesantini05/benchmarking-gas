import unittest
from extractor import extract_one, statement
from control_planilla import arithmetic

class ReaderTests(unittest.TestCase):
    def test_sign_and_current_column(self):
        self.assertEqual(extract_one([(3,'Expense (1,234) 999 888')],'Expense')['value'],-1234)
    def test_change_is_read_not_memorized(self):
        self.assertEqual(extract_one([(9,'Revenue 765,432 1,000')],'Revenue')['value'],765432)
    def test_missing_is_not_zero(self):
        self.assertIsNone(extract_one([(3,'Different 10 20')],'Expense')['value'])
    def test_dash_is_disclosed_zero(self):
        self.assertEqual(extract_one([(3,'Expense — 20')],'Expense')['value'],0)
    def test_duplicate_is_review(self):
        self.assertEqual(extract_one([(3,'Expense 10 20'),(4,'Expense 30 40')],'Expense')['status'],'REVIEW')
    def test_wrong_entity_and_quarter_rejected(self):
        annual='Southwest Gas Corporation and Subsidiaries\nCONSOLIDATED STATEMENTS OF INCOME\n(In thousands)\nYear Ended December 31,\n2025 2024 2023\nRevenue 10 20 30'
        quarter=annual.replace('Year Ended December 31,','Three Months Ended March 31,')
        holding=annual.replace('Corporation and Subsidiaries','Holdings, Inc.')
        selected=statement([holding,quarter,annual],'Southwest Gas Corporation and Subsidiaries','CONSOLIDATED STATEMENTS OF INCOME',2025)
        self.assertEqual(selected[0][0],3)
        with self.assertRaises(ValueError): statement([annual],'Southwest Gas Corporation and Subsidiaries','CONSOLIDATED STATEMENTS OF INCOME',2024)
    def test_unsafe_formula_rejected(self):
        with self.assertRaises(ValueError): arithmetic('__import__("os")')

if __name__=='__main__': unittest.main()
