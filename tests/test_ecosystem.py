import json
from pathlib import Path
import tempfile
import unittest

from ecosystem.catalog import import_csv,import_roster,load,select
from ecosystem.jobs import execute
from ecosystem.sources import candidates,check_url,discover,download


SOURCE={'url':'https://example.com/reports','hosts':['example.com'],
        'keywords':['financial statements'],'kind':'financial_statements'}


class EcosystemTests(unittest.TestCase):
    def test_catalog_filters(self):
        catalog={'companies':[{'id':'one','name':'Compañía A','country':'BR','regulator':'R','vertical_integration':'NO'},
                              {'id':'two','name':'Empresa B','country':'AR','regulator':'S','vertical_integration':'SI'}]}
        self.assertEqual([c['id'] for c in select(catalog,country='br',query='compania',regulator='R',vertical='NO')],['one'])
        self.assertEqual(select(catalog,country='BR',vertical='SI'),[])

    def test_seed_only_five_reviewed_cases(self):
        path=Path(__file__).resolve().parents[1]/'config/catalog.json'
        catalog=load(path)
        self.assertEqual(len(catalog['companies']),5)
        self.assertEqual(sum(bool(c['sources']) for c in catalog['companies']),2)

    def test_csv_does_not_enable_generation(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'roster.csv'; path.write_text('nombre,pais\nUna empresa,AR\n',encoding='utf-8')
            company=import_csv(path)['companies'][0]
            self.assertEqual(company['reviewed_years'],[])
            self.assertEqual(company['sources'],[])
            self.assertEqual(company['status'],'IDENTITY_REVIEW')

    def test_csv_rejects_duplicate(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'roster.csv'; path.write_text('nombre\nEmpresa\nEmpresa\n')
            with self.assertRaises(ValueError): import_csv(path)

    def test_roster_preserves_names_without_autosources(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'roster.csv'
            path.write_text('Empresa,NombreCompleto,PaginaWeb,Regulador,IntegracionVertical,PaisDirecto\n'
                            'Una (p),Nombre exacto,www.example.com,R,NO,Brasil\n',encoding='utf-8')
            company=import_roster(path,{'companies':[]})['companies'][0]
            self.assertEqual(company['name'],'Nombre exacto')
            self.assertEqual(company['website'],'https://www.example.com')
            self.assertEqual(company['sources'],[])

    def test_candidates_not_approved_or_period_confirmed(self):
        result=candidates('<h2>Financial statements 2025</h2><a href="/df.pdf">Download</a>',SOURCE['url'],SOURCE,[2025])
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['candidate_years'],[2025])
        self.assertEqual(result[0]['status'],'DOCUMENT_REVIEW')
        self.assertEqual(result[0]['entity_scope'],'UNVERIFIED')

    def test_discovery_rejects_external_pdf(self):
        result=candidates('<h2>Financial statements 2025</h2><a href="https://other.example/x.pdf">Download</a>',SOURCE['url'],SOURCE,[2025])
        self.assertEqual(result,[])

    def test_discovery_does_not_use_wrong_year(self):
        result=candidates('<h2>Financial statements 2024</h2><a href="/df.pdf">Download</a>',SOURCE['url'],SOURCE,[2025])
        self.assertEqual(result,[])

    def test_publication_directory_not_reporting_year(self):
        result=candidates('<a href="/2025/03/financial-statements-2024.pdf">Financial statements 2024</a>',SOURCE['url'],SOURCE,[2025])
        self.assertEqual(result,[])

    def test_previous_title_does_not_override_label(self):
        result=candidates('<h2>Financial statements 2025</h2><a href="/2025/03/df.pdf">Financial statements 2024</a>',SOURCE['url'],SOURCE,[2024,2025])
        self.assertEqual(result[0]['candidate_years'],[2024])
        self.assertEqual(result[0]['year_basis'],'link_label')

    def test_filename_precedes_ambiguous_context(self):
        result=candidates('<h2>Financial statements 2024</h2><a href="/2024/df-2018.pdf">Download</a>',SOURCE['url'],SOURCE,[2024])
        self.assertEqual(result,[])

    def test_unsafe_urls_rejected(self):
        for url in ('http://example.com/a','https://user:password@example.com/a',
                    'https://example.com:8000/a','https://127.0.0.1/a','https://example.com.evil/a'):
            with self.assertRaises(ValueError): check_url(url,['example.com'],resolve=False)

    def test_source_unconfigured_not_zero(self):
        result=discover({'id':'one','sources':[]},[2025])
        self.assertEqual(result['status'],'SOURCE_NOT_CONFIGURED')
        self.assertEqual(result['candidates'],[])

    def test_download_checks_signature(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):
                download({'url':'https://example.com/a.pdf'},{'sources':[SOURCE]},Path(t),
                         fetcher=lambda *a,**kw:(b'<html>error</html>','https://example.com/a.pdf','utf-8'))
            self.assertEqual(list(Path(t).iterdir()),[])

    def test_new_year_does_not_call_generator(self):
        called=[]
        with tempfile.TemporaryDirectory() as t:
            result=execute({'companies':[{'id':'sgc','reviewed_years':[2025]}]},
                           {'companies':['sgc'],'years':[2026],'action':'generate'},Path(t),Path(t),
                           generator=lambda *a:called.append(a))
            self.assertEqual(result['cases'][0]['status'],'REVIEW_REQUIRED')
            self.assertEqual(called,[])
            self.assertTrue((Path(t)/result['id']/'job.json').is_file())

    def test_partial_remains_partial(self):
        with tempfile.TemporaryDirectory() as t:
            result=execute({'companies':[{'id':'efigas','reviewed_years':[2025]}]},
                {'companies':['efigas'],'years':[2025],'action':'generate'},Path(t),Path(t),
                generator=lambda *a:{'cases':[{'company':'efigas','status':'PASS','data_completeness':'PARTIAL'}]})
            self.assertEqual(result['cases'][0]['status'],'PARTIAL')
            self.assertEqual(result['status'],'REVIEW_REQUIRED')

    def test_batch_keeps_other_companies_on_failure(self):
        def finder(company,years):
            if company['id']=='one': raise ValueError('changed website')
            return {'company':'two','status':'NOT_FOUND','candidates':[]}
        with tempfile.TemporaryDirectory() as t:
            result=execute({'companies':[{'id':'one'},{'id':'two'}]},
                {'companies':['one','two'],'years':[2025],'action':'discover'},Path(t),discoverer=finder)
            self.assertEqual([c['status'] for c in result['cases']],['FAILED','NOT_FOUND'])

    def test_invalid_request_creates_no_files(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):
                execute({'companies':[]},{'companies':['unknown'],'years':[2025],'action':'discover'},Path(t))
            self.assertEqual(list(Path(t).iterdir()),[])


if __name__=='__main__': unittest.main()
