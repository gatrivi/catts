"""Quick Bonsai 2 tool probe at 4K; prints one line and saves result."""
import httpx, json
payload = {'model': 'bonsai2-ngl60',
    'messages': [{'role': 'user', 'content': 'Call read_file with path AGENTS.md now. Do not answer in prose.'}],
    'temperature': 0, 'max_tokens': 256,
    'chat_template_kwargs': {'enable_thinking': False},
    'tools': [{'type': 'function', 'function': {'name': 'read_file', 'description': 'r',
    'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}}, 'required': ['path']}}}]}
r = httpx.post('http://127.0.0.1:9131/v1/chat/completions', json=payload, timeout=httpx.Timeout(600.0, connect=10.0))
print('STATUS', r.status_code)
body = r.json()
open('Z:/catts/local-coding/data/bonsai2-ngl60-probe.json', 'w').write(json.dumps(body)[:8000])
msg = body['choices'][0]['message']
print('CALLS', json.dumps(msg.get('tool_calls'))[:800])
print('CONTENT', str(msg.get('content'))[:300])
