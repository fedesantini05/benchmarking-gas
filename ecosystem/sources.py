"""Bounded official-index discovery; document candidates are NEVER approvals."""
import hashlib
from html.parser import HTMLParser
import ipaddress
import re
import socket
from urllib.parse import urljoin,urlsplit,unquote
from urllib.request import Request,build_opener,HTTPRedirectHandler

from ecosystem.catalog import normalize


def check_url(url,hosts,resolve=True):
    p=urlsplit(url)
    if p.scheme!='https' or p.hostname not in hosts or p.username or p.password or p.port not in (None,443):
        raise ValueError('Fuente fuera de los dominios HTTPS autorizados')
    if resolve:
        addresses={entry[4][0] for entry in socket.getaddrinfo(p.hostname,443,type=socket.SOCK_STREAM)}
        if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
            raise ValueError('Fuente no pública')
    return url


class RedirectGuard(HTTPRedirectHandler):
    def __init__(self,hosts): self.hosts=hosts
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        check_url(newurl,self.hosts)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def fetch(url,hosts,limit=4*1024*1024):
    check_url(url,hosts)
    opener=build_opener(RedirectGuard(hosts))
    with opener.open(Request(url,headers={'User-Agent':'BenchmarkingGas-Pilot/1.0'}),timeout=20) as response:
        content=response.read(limit+1)
        if len(content)>limit: raise ValueError('Documento supera el límite de descarga')
        return content,response.geturl(),response.headers.get_content_charset() or 'utf-8'


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.context=''; self.active=None; self.links=[]; self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'): self.hidden+=1
        if tag=='a' and not self.hidden:
            self.active={'href':dict(attrs).get('href',''),'label':'','context':self.context[-220:]}
    def handle_data(self,text):
        if self.hidden: return
        self.context=(self.context+' '+text)[-500:]
        if self.active: self.active['label']+=' '+text
    def handle_endtag(self,tag):
        if tag in ('script','style') and self.hidden: self.hidden-=1
        if tag=='a' and self.active:
            self.links.append(self.active); self.active=None


def candidates(markup,page,source,years):
    parser=Links(); parser.feed(markup); result=[]; seen=set()
    for link in parser.links:
        url=urljoin(page,link['href'])
        if not urlsplit(url).path.lower().endswith('.pdf') or url in seen: continue
        try: check_url(url,source['hosts'],resolve=False)
        except ValueError: continue
        filename=unquote(urlsplit(url).path.rsplit('/',1)[-1])
        evidence=' '.join((link['context'],link['label'],filename))
        if not any(normalize(k) in normalize(evidence) for k in source['keywords']): continue
        # Publication directories and adjacent cards must not override an explicit title.
        observed=set(); year_basis=''
        for basis,text in [('link_label',link['label']),('filename',filename),('nearby_context',link['context'])]:
            observed=set(int(y) for y in re.findall(r'(?<!\d)(20\d{2})(?!\d)',text))
            if observed: year_basis=basis; break
        matches=sorted(observed & set(years))
        if not matches: continue
        seen.add(url)
        result.append({'url':url,'index_url':page,'label':link['label'].strip(),
                       'context':' '.join(link['context'].split()),'candidate_years':matches,'year_basis':year_basis,
                       'document_variant':'summary' if any(k in normalize(link['label']+' '+filename) for k in ('resumen','resumo')) else 'full_or_unknown',
                       'kind':source['kind'],'status':'DOCUMENT_REVIEW',
                       'entity_scope':'UNVERIFIED','period_in_document':'UNVERIFIED'})
    return result


def discover(company,years,fetcher=fetch):
    result=[]; errors=[]; pages=[]
    for source in company.get('sources',[]):
        try:
            raw,url,encoding=fetcher(source['url'],source['hosts'])
            pages.append({'url':url,'sha256':hashlib.sha256(raw).hexdigest()})
            result.extend(candidates(raw.decode(encoding,errors='replace'),url,source,years))
        except Exception as error: errors.append({'url':source['url'],'error':str(error)})
    return {'company':company['id'],'status':'SOURCE_NOT_CONFIGURED' if not company.get('sources') else
            'SOURCE_ERROR' if errors else 'CANDIDATES_FOUND' if result else 'NOT_FOUND',
            'candidates':result,'source_pages':pages,'errors':errors,
            'note':'Año del enlace/contexto es candidato; no confirma período, entidad ni estados individuales.'}


def safe_name(value):
    """Human-readable Windows component, never a path supplied by a document."""
    value=re.sub(r'[<>:"/\\|?*\x00-\x1f]','-',str(value))
    value=' '.join(value.split()).strip(' .')[:90].rstrip(' .') or 'Empresa'
    if value.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}:
        value='Empresa - '+value
    return value


def company_folder(company):
    return safe_name(company.get('alias') or company.get('id','Empresa').replace('_',' ').title())


def store_document(content,candidate,company,destination):
    """Reuse identical bytes; retain distinct revisions under numbered names."""
    if not content.startswith(b'%PDF-'): raise ValueError('La descarga no tiene cabecera PDF')
    destination=destination.resolve(); destination.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(content).hexdigest()
    kind='Resumen ejecutivo' if candidate.get('document_variant')=='summary' else (
        'Informe de gestion y sostenibilidad' if candidate.get('kind')=='management_report' else 'Informe contable')
    years=candidate.get('candidate_years',[])
    if any(type(year)!=int or not 1900<=year<=2100 for year in years): raise ValueError('Años candidatos inválidos')
    period='-'.join(str(y) for y in sorted(set(years))) or 'Periodo por confirmar'
    stem=f'{company_folder(company)} - {kind} - {period}'
    revision=1
    while True:
        filename=stem+(f' - version {revision}' if revision>1 else '')+'.pdf'
        path=destination/filename
        if not path.resolve().is_relative_to(destination): raise ValueError('Destino fuera de la carpeta de la empresa')
        if path.exists():
            with path.open('rb') as f: same=hashlib.file_digest(f,'sha256').hexdigest()==digest
            if same: break
            revision+=1; continue
        try:
            with path.open('xb') as f: f.write(content)
            break
        except FileExistsError: continue
    return {'sha256':digest,'filename':path.name,'local_path':str(path),'bytes':len(content)}


def download(candidate,company,destination,fetcher=fetch):
    hosts={h for source in company['sources'] for h in source['hosts']}
    content,url,_=fetcher(candidate['url'],hosts,limit=50*1024*1024)
    stored=store_document(content,candidate,company,destination)
    return dict(candidate,download_url=url,**stored,status='DOWNLOADED_PENDING_REVIEW')
