import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from spanish_cases.regression import compare_packages, efigas_source_updates, sha256


class SourceComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.before=Path(self.temp.name)/'before.xlsx'
        self.after=Path(self.temp.name)/'after.xlsx'
        self.part='xl/worksheets/sheet2.xml'
        self.original='<worksheet><row><c r="K3"><f>1+2</f><v>3</v></c><c r="O3" s="7" t="inlineStr"><is><t>old.pdf; p. 23; COP</t></is></c><c r="O4" t="inlineStr"><is><t>other</t></is></c></row></worksheet>'
        self.updated=self.original.replace('old.pdf','new.pdf')
        self.rules={self.part:{'O3':{'before':'old.pdf; p. 23; COP','after':'new.pdf; p. 23; COP'}}}

    def compare(self,updated,rules=True,style='unchanged'):
        for path,xml,styles in ((self.before,self.original,'unchanged'),(self.after,updated,style)):
            with ZipFile(path,'w') as archive:
                archive.writestr(self.part,xml)
                archive.writestr('xl/styles.xml',styles)
        return compare_packages(self.before,self.after,self.rules if rules else None)

    def test_exact_filename_change_only(self):
        result=self.compare(self.updated)
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(len(result['accepted_source_updates']),1)

    def test_default_remains_strict(self):
        self.assertEqual(self.compare(self.updated,False)['status'],'DIFFERENCE')

    def test_page_unit_other_source_and_style_changes_block(self):
        for updated in (self.updated.replace('p. 23','p. 24'),self.updated.replace('COP','USD'),
                        self.updated.replace('>other<','>altered<'),self.updated.replace('s="7"','s="8"')):
            with self.subTest(updated=updated):
                self.assertEqual(self.compare(updated)['status'],'DIFFERENCE')

    def test_formula_value_and_other_part_changes_block(self):
        for updated in (self.updated.replace('1+2','3'),self.updated.replace('<v>3','<v>4'),
                        self.updated.replace('<row>','<row hidden="1">')):
            with self.subTest(updated=updated):
                self.assertEqual(self.compare(updated)['status'],'DIFFERENCE')
        self.assertEqual(self.compare(self.updated,style='changed')['different_parts'],['xl/styles.xml'])

    def test_wrong_expected_text_and_non_source_cell_rejected(self):
        self.rules[self.part]['O3']['before']='different approval'
        self.assertEqual(self.compare(self.updated)['status'],'DIFFERENCE')
        self.rules={self.part:{'K3':{'before':'1+2','after':'3'}}}
        with self.assertRaises(ValueError): self.compare(self.updated)

    def test_changed_pdf_content_cannot_create_exception(self):
        old=Path(self.temp.name)/'old.pdf'; new=Path(self.temp.name)/'new.pdf'
        old.write_bytes(b'approved'); new.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            efigas_source_updates(self.before,{'2024':str(old)},{'2024':str(new)},
                                  {'2024':sha256(old)},[])


if __name__=='__main__': unittest.main()
