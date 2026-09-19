import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import chores_api


class ChoresApiSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1] / 'data' / 'chores' / 'test-root'
        cls.root.mkdir(parents=True, exist_ok=True)
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), chores_api.Handler)
        cls.server.api_token = 't' * 40
        cls.server.allowed_origins = frozenset({'https://good.example'})
        cls.server.project_roots = frozenset({cls.root})
        cls.server.allow_writes = False
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def request(self, method, path, body=None, auth=True, origin=None):
        headers = {'Content-Type': 'application/json'}
        if auth:
            token = auth if isinstance(auth, str) else 't' * 40
            headers['Authorization'] = 'Bearer ' + token
        if origin:
            headers['Origin'] = origin
        r = urllib.request.Request(
            f'http://127.0.0.1:{self.port}{path}', method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers)
        try:
            with urllib.request.urlopen(r, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode())

    def test_auth_required(self):
        self.assertEqual(self.request('GET', '/health', auth=False)[0], 401)

    def test_bad_token_rejected(self):
        status, _ = self.request('GET', '/health', auth='wrong')
        self.assertEqual(status, 401)

    def test_health_and_models_authorized(self):
        self.assertEqual(self.request('GET', '/health')[0], 200)
        self.assertEqual(self.request('GET', '/models')[0], 200)

    def test_caller_approval_is_rejected(self):
        status, _ = self.request('POST', '/agent/turn', {'prompt': 'x', 'approval': 'yolo'})
        self.assertEqual(status, 400)

    def test_project_outside_roots_rejected(self):
        status, _ = self.request('POST', '/agent/turn', {'prompt': 'x', 'project': 'C:/Windows'})
        self.assertEqual(status, 403)

    def test_turn_without_model_is_502(self):
        status, _ = self.request('POST', '/agent/turn', {'prompt': 'inspect', 'project': str(self.root)})
        self.assertEqual(status, 502)

    def test_non_object_body_rejected(self):
        status, _ = self.request('POST', '/agent/turn', [1, 2])
        self.assertEqual(status, 400)


if __name__ == '__main__':
    unittest.main()
