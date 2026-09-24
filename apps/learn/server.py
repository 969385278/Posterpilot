"""Loopback-only learning server; Python standard library, no model credentials."""
import argparse
import hashlib
import json
import os
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

from catalog import ROOT, catalog
from sources import source_for
from experiments import LABS, run_lab
from traces import SCENARIOS, make_trace

HERE = Path(__file__).resolve().parent
WEB = HERE / "web"
IDENTITY = hashlib.sha256(str(ROOT).encode()).hexdigest()[:16]


class Handler(BaseHTTPRequestHandler):
    server_version = "PosterPilotLearn/1.0"

    def log_message(self, format, *args):
        # Do not log request bodies or user input.
        print(format % args, flush=True)

    def allowed_host(self):
        host=self.headers.get("Host", "")
        return host in {f"127.0.0.1:{self.server.server_port}",f"localhost:{self.server.server_port}"}

    def write_headers(self, status, content_type, length):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'")
        self.end_headers()

    def send_json(self, value, status=200):
        data=json.dumps(value,ensure_ascii=False,allow_nan=False).encode("utf-8")
        self.write_headers(status,"application/json; charset=utf-8",len(data))
        self.wfile.write(data)

    def do_GET(self):
        if not self.allowed_host():
            return self.send_json({"error":"仅允许本地学习台地址"},403)
        parsed=urlparse(self.path)
        query=parse_qs(parsed.query)
        try:
            if parsed.path=="/api/health":
                return self.send_json({"service":"posterpilot-learn","identity":IDENTITY,"version":"1.0","pid":os.getpid()})
            if parsed.path=="/api/catalog":
                return self.send_json({**catalog(),"labs":LABS,"scenarios":SCENARIOS})
            if parsed.path=="/api/source":
                return self.send_json(source_for(query.get("id",[""])[0]))
            if parsed.path=="/api/trace":
                return self.send_json(make_trace(query.get("scenario",["normal"])[0],query.get("title",["春日摄影展"])[0]))
            if parsed.path.startswith("/api/"):
                return self.send_json({"error":"接口不存在"},404)
            relative=unquote(parsed.path).lstrip("/") or "index.html"
            path=(WEB/relative).resolve()
            if not path.is_relative_to(WEB) or not path.is_file() or path.suffix not in {".html",".css",".js",".svg",".png",".json"}:
                return self.send_json({"error":"文件不存在"},404)
            types={".html":"text/html; charset=utf-8",".css":"text/css; charset=utf-8",".js":"text/javascript; charset=utf-8",".svg":"image/svg+xml",".png":"image/png",".json":"application/json"}
            data=path.read_bytes()
            self.write_headers(200,types[path.suffix],len(data))
            self.wfile.write(data)
        except (ValueError,FileNotFoundError) as error:
            self.send_json({"error":str(error)},400)
        except Exception:
            traceback.print_exc()
            self.send_json({"error":"读取失败，请检查本地服务日志。"},500)

    def do_POST(self):
        origin=self.headers.get("Origin")
        allowed={f"http://127.0.0.1:{self.server.server_port}",f"http://localhost:{self.server.server_port}"}
        if not self.allowed_host() or (origin and origin not in allowed) or self.headers.get("Sec-Fetch-Site")=="cross-site":
            return self.send_json({"error":"拒绝跨站调用"},403)
        if self.path != "/api/lab":
            return self.send_json({"error":"接口不存在"},404)
        if self.headers.get_content_type()!="application/json":
            return self.send_json({"error":"需要 JSON 输入"},415)
        try:
            length=int(self.headers.get("Content-Length","0"))
            if not 0 < length <= 12000:
                return self.send_json({"error":"输入大小不合法"},413)
            payload=json.loads(self.rfile.read(length))
            if not isinstance(payload,dict):
                raise ValueError("需要 JSON 对象")
            result=run_lab(payload.get("id"),payload.get("values",{}))
            self.send_json(result)
        except (ValueError,TypeError) as error:
            self.send_json({"error":str(error)},400)
        except Exception:
            traceback.print_exc()
            self.send_json({"error":"实验执行失败；未调用模型，请查看本地服务日志。"},500)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=8879)
    parser.add_argument("--open",action="store_true")
    args=parser.parse_args()
    server=ThreadingHTTPServer(("127.0.0.1",args.port),Handler)
    runtime=HERE/".runtime"
    runtime.mkdir(exist_ok=True)
    (runtime/"server.json").write_text(json.dumps({"pid":os.getpid(),"port":server.server_port,"identity":IDENTITY}),encoding="utf-8")
    url=f"http://127.0.0.1:{server.server_port}"
    print("PosterPilot Learn: "+url,flush=True)
    if args.open:
        threading.Timer(0.4,lambda:webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__=="__main__":
    main()
