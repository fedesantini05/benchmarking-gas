import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from run_company import COMPANIES, validate_pilot_config
from spanish_cases.regression import compare_packages, assert_inputs, sha256
from spanish_cases.vocabulary import labels, efigas_label
from spanish_cases.reviewed_southern import AR, NATURE, income_ar, formula
from spanish_cases.efigas import ER_FORMULAS, BP_FORMULAS


class ApprovedCasesTests(unittest.TestCase):
    def test_scope(self):
        self.assertIn('ecogas_cuyo',COMPANIES)
        self.assertNotIn('metrogas_chile',COMPANIES)
        with self.assertRaises(ValueError):
            validate_pilot_config('ecogas_cuyo',{'reports':{'2026':'x'}})
        with self.assertRaises(ValueError):
            validate_pilot_config('efigas',{'reports':dict.fromkeys(['2023','2024','2025']),
                                           'missing_policy':'PRESERVE_FORMULAS_MARK_MISSING'})

    def test_confirmed_formula_map(self):
        self.assertEqual(ER_FORMULAS[31],'SUM({c}32:{c}34)')
        self.assertEqual(ER_FORMULAS[43],'{c}17+{c}18+{c}35')
        self.assertEqual(ER_FORMULAS[53],'{c}49+{c}50')
        self.assertEqual(BP_FORMULAS[26],'{c}27-{c}28')
        self.assertEqual(BP_FORMULAS[27],'{c}3-{c}4')
        self.assertEqual(BP_FORMULAS[28],'{c}11-{c}13')
        self.assertEqual(BP_FORMULAS[29],'{c}30-{c}31')

    def test_function_not_nature_controls_maintenance(self):
        rows=income_ar(2023,AR[2023])
        self.assertIn('2128129',rows[32])
        self.assertIn('811496',rows[34])
        self.assertNotIn('2128129',rows[34])

    def test_taxes_regulator_and_reversal_outside_pmso(self):
        for year,facts in AR.items():
            rows=income_ar(year,facts); n=NATURE[year]
            self.assertEqual(rows[41],formula([*n[13],n[14][2],facts['finance_tax']],-1))
            self.assertEqual(rows[42],formula(n[15],-1))
        rows=income_ar(2023,AR[2023])
        self.assertIn('254294',rows[13]); self.assertIsNone(rows[45])

    def test_glossary_is_scoped_not_learning(self):
        self.assertIn('Tasa ENARGAS',labels('Argentina','regulator_fee'))
        self.assertEqual(efigas_label('sale_cost',2025),'Costo de venta')
        with self.assertRaises(ValueError): efigas_label('income',2026)
        with self.assertRaises(KeyError): labels('Colombia','regulator_fee')

    def test_equal_totals_do_not_hide_changed_formula_or_style(self):
        with tempfile.TemporaryDirectory() as directory:
            before=Path(directory)/'before.xlsx'; after=Path(directory)/'after.xlsx'
            def pack(path,formula,style='same'):
                with ZipFile(path,'w') as z:
                    z.writestr('xl/worksheets/sheet1.xml',f'<c><f>{formula}</f><v>3</v></c>')
                    z.writestr('xl/styles.xml',style)
            pack(before,'1+2'); pack(after,'1+2')
            self.assertEqual(compare_packages(before,after)['status'],'PASS')
            pack(after,'3')
            self.assertEqual(compare_packages(before,after)['status'],'DIFFERENCE')
            pack(after,'1+2','changed')
            self.assertEqual(compare_packages(before,after)['different_parts'],['xl/styles.xml'])

    def test_changed_source_requires_review(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'source'; p.write_bytes(b'approved')
            config={'reference':str(p),'reference_sha256':sha256(p),
                    'template':str(p),'template_sha256':sha256(p),
                    'reports':{'2023':str(p)},'report_sha256':{'2023':sha256(p)}}
            assert_inputs(config)
            p.write_bytes(b'changed')
            with self.assertRaises(ValueError): assert_inputs(config)


if __name__=='__main__': unittest.main()
