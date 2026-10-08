"""Loopback-only pilot UI/API. Not a production server or corporate login."""
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import secrets
from urllib.parse import urlsplit

from ecosystem.catalog import load
from ecosystem.jobs import execute


def serve(catalog,storage,data_root,port):
    if not 1024<=port<=65535: raise ValueError('Puerto no admitido')
    token=secrets.token_hex(32); origin=f'http://127.0.0.1:{port}'
    pool=ThreadPoolExecutor(max_workers=1); tickets={}
    page=(Path(__file__).parent/'web/index.html').read_text(encoding='utf-8').replace('__TOKEN__',token)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def reply(self,code,value,kind='application/json; charset=utf-8'):
            content=value.encode('utf-8') if isinstance(value,str) else json.dumps(value,ensure_ascii=False).encode('utf-8')
            self.send_response(code); self.send_header('Content-Type',kind)
            self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',f"default-src 'self'; script-src 'nonce-{token}'; style-src 'nonce-{token}'; frame-ancestors 'none'")
            self.send_header('Content-Length',str(len(content))); self.end_headers(); self.wfile.write(content)
        def allowed(self):
            return self.headers.get('Host')==f'127.0.0.1:{port}'
        def do_GET(self):
            if not self.allowed(): self.reply(403,{'error':'Sólo acceso local'}); return
            route=urlsplit(self.path).path
            if route=='/': self.reply(200,page,'text/html; charset=utf-8')
            elif route=='/api/catalog': self.reply(200,load(catalog))
            elif route=='/api/health': self.reply(200,{'mode':'LOCAL_PILOT','sharepoint':False,'ai':False})
            elif route.startswith('/api/tickets/'):
                future=tickets.get(route.rsplit('/',1)[1])
                if future is None: self.reply(404,{'error':'Ejecución no encontrada'})
                elif not future.done(): self.reply(200,{'status':'RUNNING'})
                else:
                    try: self.reply(200,future.result())
                    except Exception as error: self.reply(200,{'status':'FAILED','error':str(error)})
            elif route=='/api/history':
                reports=sorted(Path(storage).glob('*/job.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:30]
                history=[]
                for path in reports:
                    try: history.append(json.loads(path.read_text(encoding='utf-8')))
                    except (OSError,json.JSONDecodeError): pass
                self.reply(200,history)
            else: self.reply(404,{'error':'Ruta no encontrada'})
        def do_POST(self):
            if not self.allowed() or self.headers.get('Origin')!=origin or self.headers.get('X-Request-Token')!=token:
                self.reply(403,{'error':'Solicitud local no autorizada'}); return
            if self.path!='/api/jobs': self.reply(404,{'error':'Ruta no encontrada'}); return
            if any(not f.done() for f in tickets.values()): self.reply(409,{'error':'Esperá que termine la ejecución actual'}); return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=8192: raise ValueError('Solicitud demasiado grande o vacía')
                request=json.loads(self.rfile.read(length))
                if not isinstance(request,dict): raise ValueError('Solicitud inválida')
                identity=secrets.token_hex(16)
                tickets[identity]=pool.submit(execute,load(catalog),request,storage,data_root)
                self.reply(202,{'ticket':identity})
            except (ValueError,TypeError) as error: self.reply(400,{'error':str(error)})

    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'Piloto local: {origin} — no expuesto a Internet',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close(); pool.shutdown(wait=True)
