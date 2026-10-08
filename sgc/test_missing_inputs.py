"""Explicit missing values must propagate; other errors must fail closed."""
import unittest
from lxml import etree as ET
from control_planilla import Book, MissingInput, NS


class MissingInputsTests(unittest.TestCase):
    def book(self,cells):
        result=Book.__new__(Book)
        result.sheets={'Test':{ref:ET.fromstring(xml) for ref,xml in cells.items()}}
        return result

    def test_na_propagates_to_nested_formula(self):
        ns=NS['m']
        book=self.book({'A1':f'<c xmlns="{ns}"><f>NA()</f></c>',
                        'A2':f'<c xmlns="{ns}"><v>42</v></c>',
                        'A3':f'<c xmlns="{ns}"><f>SUM(A1:A2)</f></c>'})
        with self.assertRaises(MissingInput):
            book.value('Test','A3')

    def test_cached_na_propagates(self):
        book=self.book({'A1':f'<c xmlns="{NS["m"]}" t="e"><v>#N/A</v></c>'})
        with self.assertRaises(MissingInput):
            book.value('Test','A1')

    def test_ref_error_is_not_allowed_missing(self):
        book=self.book({'A1':f'<c xmlns="{NS["m"]}" t="e"><v>#REF!</v></c>'})
        with self.assertRaises(ValueError) as context:
            book.value('Test','A1')
        self.assertNotIsInstance(context.exception,MissingInput)

    def test_guard_distinguishes_blank_from_zero(self):
        ns=NS['m']
        book=self.book({'A1':f'<c xmlns="{ns}"><v>0</v></c>',
                        'A2':f'<c xmlns="{ns}"/>',
                        'A3':f'<c xmlns="{ns}"><f>IF(COUNT(A1,A2)=2,A1-A2,"")</f></c>'})
        self.assertEqual(book.value('Test','A3'),'')
        book.sheets['Test']['A2']=ET.fromstring(f'<c xmlns="{ns}"><v>2</v></c>')
        self.assertEqual(book.value('Test','A3'),-2)

    def test_blank_result_propagates_through_guard(self):
        ns=NS['m']
        book=self.book({'A1':f'<c xmlns="{ns}"/>',
                        'A2':f'<c xmlns="{ns}"><f>IF(COUNT(A1)=1,A1,"")</f></c>',
                        'A3':f'<c xmlns="{ns}"><f>IF(COUNT(A2)=1,A2+1,"")</f></c>'})
        self.assertEqual(book.value('Test','A3'),'')


if __name__=='__main__':
    unittest.main()
