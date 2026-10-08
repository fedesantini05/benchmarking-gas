import copy
import json
import unittest
from extractor import BASE
from generar_planilla import make_patches, ER, BP

class MappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records=[json.loads((BASE.parent/'tests'/'fixtures'/'sgc'/f'extraccion_{y}.json').read_text(encoding='utf-8')) for y in range(2020,2026)]
    def test_new_revenue_difference_blocks(self):
        records=copy.deepcopy(self.records)
        records[0]['facts']['residential']['value']+=1
        with self.assertRaises(ValueError): make_patches(records)
    def test_missing_required_amount_blocks(self):
        records=copy.deepcopy(self.records); records[0]['facts']['gas_cost']['value']=None
        with self.assertRaises(ValueError): make_patches(records)
    def test_change_to_balance_component_blocks(self):
        records=copy.deepcopy(self.records); records[0]['facts']['prepaid_other_current']['value']+=1
        with self.assertRaises(ValueError): make_patches(records)
    def test_formula_rules_and_expense_signs(self):
        patches,_=make_patches(self.records)
        for col in 'HIJKLM':
            self.assertEqual(patches[BP][col+'26'],f'={col}27-{col}28')
            self.assertEqual(patches[BP][col+'29'],f'={col}30-{col}31')
            self.assertEqual(patches[ER][col+'53'],f'={col}49+{col}50')
            self.assertTrue(patches[ER][col+'44'].startswith('=-('))

if __name__=='__main__': unittest.main()
