"""One-shot Bonsai 2 tool probe against an already-running local server."""
import httpx, json
payload = {'model': 'bonsai2-partial',
    'messages': [{'role': 'user', 'content': 'Call read_file with path AGENTS.md now. Do not answer in prose.'}],
    'temperature': 0, 'max_tokens': 512,
    'tools': [{'type': 'function', 'function': {'name': 'read_file', 'description': 'r',
    'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}}, 'required': ['path']}}}]}
r = httpx.post('http://127.0.0.1:9131/v1/chat/completions', json=payload, timeout=httpx.Timeout(600.0, connect=10.0))
print(r.status_code)
body = r.json()
open('Z:/catts/local-coding/data/bonsai2-toolprobe-result.json', 'w').write(json.dumps(body, indent=2)[:8000])
msg = body['choices'][0]['message']
print('CONTENT:', str(msg.get('content'))[:500])
print('CALLS:', json.dumps(msg.get('tool_calls'))[:1000])
