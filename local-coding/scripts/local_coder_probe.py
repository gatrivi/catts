"""Small repeatable local model/tool smoke check; never executes model code."""
import argparse
import json
from pathlib import Path
import time
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:9100')
    parser.add_argument('--out', default='data/local-coder-probe.json')
    args = parser.parse_args()
    results = []
    with httpx.Client(base_url=args.url, timeout=120) as client:
        client.get('/health').raise_for_status()
        model = client.get('/v1/models').json()['data'][0]['id']
        messages = [{'role': 'system', 'content': 'You are a coding assistant. Use the supplied tools with the tool call format, not markdown code blocks. Never invent file contents. After receiving tool results, answer with JSON.'},
            {'role': 'user', 'content': 'Use read_file to read fixture.json, then calculate the sum of its numbers. Your final answer should be {"sum": number}.'}]
        tool = {'type': 'function', 'function': {'name': 'read_file', 'description': 'Read a test fixture.',
            'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}}, 'required': ['path']}}}
        start = time.monotonic()
        response = client.post('/v1/chat/completions', json={'model': model, 'messages': messages,
            'tools': [tool], 'temperature': 0, 'max_tokens': 256})
        response.raise_for_status()
        message = response.json()['choices'][0]['message']
        calls = message.get('tool_calls', [])
        if len(calls) != 1 or calls[0]['function']['name'] != 'read_file':
            results.append({'test': 'automatic_tool_selection', 'passed': False, 'answer': message})
            response = client.post('/v1/chat/completions', json={'model':model,'messages':messages,
                'tools':[tool], 'tool_choice':'required','temperature':0,'max_tokens':256})
            response.raise_for_status()
            message = response.json()['choices'][0]['message']
            calls = message.get('tool_calls', [])
            if len(calls) != 1 or calls[0]['function']['name'] != 'read_file':
                results.append({'test':'constrained_tool_call','passed':False,'answer':message,
                    'timings':response.json().get('timings')})
                destination = Path(args.out)
                destination.parent.mkdir(parents=True,exist_ok=True)
                destination.write_text(json.dumps({'model':model,'results':results},indent=2),encoding='utf-8')
                print(f'FAIL: automatic and constrained tool calls. Report: {destination}')
                return 2
        else:
            results.append({'test':'automatic_tool_selection','passed':True})
        if json.loads(calls[0]['function']['arguments']).get('path') != 'fixture.json':
            raise RuntimeError('Wrong tool arguments')
        # This is the actual tool execution, restricted to a fixed test fixture.
        fixture = Path(__file__).resolve().parents[1] / 'fixtures' / 'local-coder' / 'fixture.json'
        data = fixture.read_text(encoding='utf-8')
        messages += [message, {'role': 'tool', 'tool_call_id': calls[0]['id'], 'content': data}]
        response = client.post('/v1/chat/completions', json={'model': model, 'messages': messages,
            'tools': [tool], 'temperature': 0, 'max_tokens': 256})
        response.raise_for_status()
        body = response.json()
        content = body['choices'][0]['message']['content']
        results.append({'test': 'tool_round_trip', 'passed': json.loads(content) == {'sum': sum(json.loads(data)['numbers'])},
            'seconds': round(time.monotonic()-start, 2), 'answer': content, 'usage': body.get('usage'), 'timings': body.get('timings')})
        prompt = 'Python bug: def average(xs): return sum(xs) // len(xs). Required behavior: mean([1,2]) must be 1.5; empty input must raise ValueError. Return only JSON {"division_operator": "...", "empty_exception": "..."} describing the correction.'
        start = time.monotonic()
        response = client.post('/v1/chat/completions', json={'model':model,'messages':[{'role':'user','content':prompt}], 'temperature':0,'max_tokens':256})
        response.raise_for_status()
        body = response.json()
        content = body['choices'][0]['message']['content']
        results.append({'test':'bug_review','passed':json.loads(content)=={'division_operator':'/','empty_exception':'ValueError'},
            'seconds':round(time.monotonic()-start,2),'answer':content,'timings':body.get('timings')})
    output = {'model':model,'results':results}
    destination = Path(args.out)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(json.dumps(output,indent=2))
    return 0 if all(r['passed'] for r in results) else 2


if __name__ == '__main__':
    raise SystemExit(main())
