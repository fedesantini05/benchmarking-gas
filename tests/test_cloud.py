import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from cloud.data_bundle import approved_member, unpack
from cloud.run_batch import run, select_companies


class CloudTests(unittest.TestCase):
    def archive(self, root, files, corrupt=False):
        path=root/'data.zip'
        manifest={name:hashlib.sha256(value).hexdigest() for name,value in files.items()}
        if corrupt: manifest[next(iter(manifest))]='0'*64
        with ZipFile(path,'w') as z:
            for name,value in files.items(): z.writestr(name,value)
            z.writestr('MANIFEST.json',json.dumps({'files':manifest}))
        return path,hashlib.sha256(path.read_bytes()).hexdigest()

    def test_company_selection(self):
        self.assertEqual(len(select_companies('todas')),5)
        self.assertEqual(select_companies('sgc, efigas'),['sgc','efigas'])
        for value in ('','otra','sgc,sgc','sgc;otra'):
            with self.assertRaises(ValueError): select_companies(value)

    def test_member_allowlist(self):
        self.assertTrue(approved_member('data/reports/sgc/2025.pdf'))
        for name in ('../data/templates/a.xlsx','data//templates/a.xlsx','data/templates/./a.xlsx',
                     'data/templates/CON.xlsx','data/templates/a.xlsx ',
                     'data/templates/a.xlsx:code','tools/run.py','config/local/a.py',
                     '/data/templates/a.xlsx','data\\templates\\a.xlsx'):
            self.assertFalse(approved_member(name),name)

    def test_valid_data_unpack(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            archive,digest=self.archive(root,{'config/local/sgc.json':b'{}'})
            unpack(archive,root/'inputs',digest)
            self.assertEqual((root/'inputs/config/local/sgc.json').read_bytes(),b'{}')
            with self.assertRaises(FileExistsError): unpack(archive,root/'inputs',digest)

    def test_wrong_archive_hash(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); archive,_=self.archive(root,{'config/local/sgc.json':b'{}'})
            with self.assertRaises(ValueError): unpack(archive,root/'inputs','0'*64)
            self.assertFalse((root/'inputs').exists())

    def test_no_code_in_data(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); archive,digest=self.archive(root,{'tools/run.py':b'pass'})
            with self.assertRaises(ValueError): unpack(archive,root/'inputs',digest)

    def test_altered_manifest(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); archive,digest=self.archive(root,{'config/local/sgc.json':b'{}'},corrupt=True)
            with self.assertRaises(ValueError): unpack(archive,root/'inputs',digest)
            self.assertFalse((root/'inputs').exists())

    def test_batch_continues_and_withholds_failed_excel(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); data=root/'data'; configs=data/'config/local'; configs.mkdir(parents=True)
            for company in ('sgc','efigas'):
                (configs/f'{company}.json').write_text(json.dumps({'template':'template.xlsx','reference':'reference.xlsx',
                    'reports':{'2025':'2025.pdf'}}))
            def generate(company,config,output):
                output.write_bytes(b'candidate')
                return {'checks':[]}
            with patch('cloud.run_batch.validate'),patch('cloud.run_batch.assert_inputs'), \
                 patch('cloud.run_batch.generate',side_effect=generate), \
                 patch('cloud.run_batch.compare_packages',side_effect=[{'status':'DIFFERENCE'},{'status':'PASS'}]):
                summary=run(['sgc','efigas'],data,root/'output','generar')
            self.assertEqual(summary['status'],'FAILED')
            self.assertEqual(len(summary['cases']),2)
            self.assertFalse((root/'output/sgc/sgc.xlsx').exists())
            self.assertTrue((root/'output/efigas/efigas.xlsx').exists())
            self.assertEqual(summary['cases'][1]['data_completeness'],'PARTIAL')

    def test_batch_existing_destination(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(FileExistsError): run(['sgc'],Path(t),Path(t),'generar')


if __name__=='__main__': unittest.main()
