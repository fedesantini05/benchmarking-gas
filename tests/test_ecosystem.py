import json
import hashlib
from pathlib import Path
import tempfile
import unittest

from ecosystem.catalog import import_csv,import_roster,load,select
from ecosystem.jobs import execute
from ecosystem.bindings import bind_reports
from ecosystem.sources import candidates,check_url,discover,download,store_document,company_folder,safe_name


SOURCE={'url':'https://example.com/reports','hosts':['example.com'],
        'keywords':['financial statements'],'kind':'financial_statements'}


class EcosystemTests(unittest.TestCase):
    def binding_fixture(self,root):
        data=root/'data'; configs=data/'config/local'; configs.mkdir(parents=True)
        company={'id':'efigas','alias':'Efigas'}; folder=root/'outputs/Efigas'; folder.mkdir(parents=True)
        config={'report_sha256':{'2024':hashlib.sha256(b'%PDF-reviewed').hexdigest()}}
        (configs/'efigas.json').write_text(json.dumps(config))
        return data,company,folder

    def test_matching_download_binding(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); data,company,folder=self.binding_fixture(root)
            path=folder/'Efigas - Informe de gestion y sostenibilidad - 2024.pdf'; path.write_bytes(b'%PDF-reviewed')
            self.assertEqual(bind_reports(company,data,root/'outputs'),{'2024':str(path.resolve())})

    def test_changed_download_blocks_silent_fallback(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); data,company,folder=self.binding_fixture(root)
            (folder/'Efigas - Informe contable - 2024.pdf').write_bytes(b'%PDF-changed')
            with self.assertRaises(ValueError): bind_reports(company,data,root/'outputs')

    def test_summary_does_not_replace_full_report(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); data,company,folder=self.binding_fixture(root)
            (folder/'Efigas - Resumen ejecutivo - 2024.pdf').write_bytes(b'%PDF-summary')
            self.assertEqual(bind_reports(company,data,root/'outputs'),{})

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

    def test_readable_filename_and_deduplication(self):
        with tempfile.TemporaryDirectory() as t:
            candidate={'candidate_years':[2024],'kind':'management_report','document_variant':'full_or_unknown'}
            company={'id':'efigas','alias':'Efigas'}
            first=store_document(b'%PDF-first',candidate,company,Path(t))
            second=store_document(b'%PDF-first',candidate,company,Path(t))
            self.assertEqual(first['filename'],'Efigas - Informe de gestion y sostenibilidad - 2024.pdf')
            self.assertEqual(first,second)
            self.assertEqual(len(list(Path(t).iterdir())),1)

    def test_different_revision_never_overwrites(self):
        with tempfile.TemporaryDirectory() as t:
            candidate={'candidate_years':[2025],'document_variant':'summary'}
            company={'id':'efigas','alias':'Efigas'}
            first=store_document(b'%PDF-first',candidate,company,Path(t))
            second=store_document(b'%PDF-second',candidate,company,Path(t))
            self.assertTrue(second['filename'].endswith(' - version 2.pdf'))
            self.assertEqual(Path(first['local_path']).read_bytes(),b'%PDF-first')
            self.assertEqual(store_document(b'%PDF-second',candidate,company,Path(t)),second)

    def test_safe_folder_name(self):
        self.assertEqual(company_folder({'alias':'Efigas','id':'efigas'}),'Efigas')
        for value in ('../../Other','CON','a\\b','a/b','a:b','name. '):
            self.assertNotIn('/',safe_name(value)); self.assertNotIn('\\',safe_name(value))
            self.assertFalse(safe_name(value).endswith(('.', ' ')))

    def test_downloads_under_outputs_company_not_execution(self):
        with tempfile.TemporaryDirectory() as t:
            storage=Path(t)/'outputs/platform'
            company={'id':'efigas','alias':'Efigas'}
            received=[]
            def downloader(candidate,company,destination):
                received.append(destination); return {'status':'DOWNLOADED_PENDING_REVIEW'}
            execute({'companies':[company]},
                {'companies':['efigas'],'years':[2024],'action':'discover','download':True},storage,
                discoverer=lambda *args:{'company':'efigas','status':'CANDIDATES_FOUND','candidates':[{}]},downloader=downloader)
            self.assertEqual(received,[Path(t)/'outputs/Efigas'])

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
