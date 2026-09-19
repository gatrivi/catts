"""Voice gateway: browser/phone -> local llama-server, no cloud LLM in the loop.

Stdlib only (no new deps). Reverse-proxies the OpenAI-compatible endpoint
that smol.py already runs (default http://127.0.0.1:9104) with CORS added,
so a page on the tailnet (PC browser, phone over Tailscale) can POST chat
directly to the local model. STT stays where it is (Deepgram in
challenge-zero); this gateway never re-transcribes.

Routes:
  GET  /health                 -> {"live": bool, "upstream": ...} (never 500)
  POST /v1/chat/completions    -> streamed passthrough (SSE or JSON)

Run (model must already be up via SMOL.cmd; this loads nothing itself):
  python scripts/voice_gateway.py --port 9110
  python scripts/voice_gateway.py --host 100.x.y.z --port 9110  # phone path
  python scripts/voice_gateway.py --check                       # no servers

Security: no auth. Bind 127.0.0.1 for PC-only, or the Tailscale IP for the
phone path (tailnet-only). Never 0.0.0.0 on untrusted networks.
"""
import argparse, json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

UPSTREAM = 'http://127.0.0.1:9104'
TIMEOUT = 15


def probe(upstream):
    try:
        with urlrequest.urlopen(upstream + '/health', timeout=TIMEOUT) as r:
            return r.status == 200
    except Exception:
        return False


class Handler(BaseHTTPRequestHandler):
    upstream = UPSTREAM
    server_version = 'VoiceGateway/1'

    def log_message(self, *a):
        pass

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path.rstrip('/') in ('/health', '/api/health'):
            body = json.dumps(
                {'live': probe(self.upstream), 'upstream': self.upstream}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self._cors()
            self.end_headers()

    def do_POST(self):
        if self.path.rstrip('/') != '/v1/chat/completions':
            self.send_response(404)
            self._cors()
            self.end_headers()
            return
        length = int(self.headers.get('Content-Length') or 0)
        payload = self.rfile.read(length) if length else b'{}'
        try:
            req = urlrequest.Request(
                self.upstream + '/v1/chat/completions', data=payload,
                headers={'Content-Type': 'application/json'}, method='POST')
            upstream_res = urlrequest.urlopen(req, timeout=None)
        except HTTPError as e:
            detail = e.read()[:4096]
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(detail)))
            self._cors()
            self.end_headers()
            self.wfile.write(detail)
            return
        except (URLError, OSError):
            body = json.dumps(
                {'error': 'upstream unreachable: start a model with SMOL.cmd first'}
            ).encode()
            self.send_response(502)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)
            return
        ctype = upstream_res.headers.get('Content-Type', 'text/event-stream')
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self._cors()
        self.end_headers()
        try:
            while True:
                chunk = upstream_res.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
        except (ConnectionAbortedError, BrokenPipeError):
            pass


def main():
    ap = argparse.ArgumentParser(description='Browser/phone -> local model gateway')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=9110)
    ap.add_argument('--upstream', default=UPSTREAM)
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    if args.check:
        print('upstream:', args.upstream, 'live:', probe(args.upstream))
        print('OK voice_gateway (nothing loaded, nothing started)')
        return
    Handler.upstream = args.upstream.rstrip('/')
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f'voice_gateway on http://{args.host}:{args.port} -> {Handler.upstream}')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
