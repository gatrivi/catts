"""Auto-context proxy for Bonsai-2 (:9103 -> :9106).

OpenAI-compatible pass-through that applies context_summarizer.truncate_context
to the rendered chat history before forwarding, so clients never overflow the
8K server window. Summarizes old turns via the model itself, falls back to
extractive truncation, and as a last resort hard-truncates to the keep_recent
budget so requests always fit.

Endpoints: POST /v1/chat/completions, GET /v1/models, GET /health
"""
import json
import logging
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

sys.path.insert(0, 'Z:/catts/local-coding/scripts')
from context_summarizer import _count_tokens, truncate_context

UPSTREAM = 'http://127.0.0.1:9103'
PORT = 9106
CTX = 8192
KEEP_RECENT = 4000
BUDGET = 6000  # leaves headroom for system prompt, template, and reply

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('bonsai2-proxy')


def render_history(messages):
    return '\n'.join(f"{m.get('role', 'user')}: {m.get('content') or ''}" for m in messages)


def _hard_truncate(messages, budget_tokens):
    """Last-resort: keep first system message + most recent messages within budget."""
    head = messages[:1] if messages and messages[0].get('role') == 'system' else []
    tail = []
    used = sum(_count_tokens(m.get('content') or '') for m in head)
    for m in reversed(messages[len(head):]):
        t = _count_tokens(m.get('content') or '')
        if used + t > budget_tokens:
            break
        tail.insert(0, m)
        used += t
    return head + tail


def compress_messages(messages):
    total = sum(_count_tokens(m.get('content') or '') for m in messages)
    if total <= BUDGET:
        return messages
    log.info('history ~%d tokens > budget %d; compressing', total, BUDGET)

    def summarize(prompt, temperature=0, max_tokens=512):
        r = httpx.post(f'{UPSTREAM}/v1/chat/completions', json={
            'model': 'bonsai2', 'temperature': temperature, 'max_tokens': max_tokens,
            'messages': [{'role': 'user', 'content': prompt}],
            'chat_template_kwargs': {'enable_thinking': False},
        }, timeout=300)
        return r.json()['choices'][0]['message']['content']

    compressed = truncate_context(render_history(messages), max_tokens=BUDGET,
                                  keep_recent=KEEP_RECENT, model=summarize,
                                  model_name='bonsai2-proxy')
    if _count_tokens(compressed) > BUDGET:
        log.warning('summarized history still over budget; hard-truncating')
        return _hard_truncate(messages, BUDGET)
    return [{'role': 'user', 'content': compressed}]


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path in ('/health', '/v1/models'):
            try:
                r = httpx.get(f'{UPSTREAM}{self.path}', timeout=5)
                self._send(r.status_code, r.json())
            except Exception as e:
                self._send(502, {'error': f'upstream: {e}'})
        else:
            self._send(404, {'error': 'not found'})

    def do_POST(self):
        if self.path != '/v1/chat/completions':
            self._send(404, {'error': 'not found'})
            return
        try:
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        except Exception as e:
            self._send(400, {'error': f'bad json: {e}'})
            return
        if isinstance(payload.get('messages'), list):
            payload['messages'] = compress_messages(payload['messages'])
        try:
            r = httpx.post(f'{UPSTREAM}/v1/chat/completions', json=payload, timeout=900)
            self._send(r.status_code, r.json())
        except Exception as e:
            self._send(502, {'error': f'upstream: {e}'})


if __name__ == '__main__':
    log.info('bonsai2-proxy :%d -> %s (budget %d/%d tokens)', PORT, UPSTREAM, BUDGET, CTX)
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
