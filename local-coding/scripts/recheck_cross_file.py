"""Recheck recorded cross-file answers after only removing JSON fences."""
import ast,json,subprocess,sys,textwrap
from pathlib import Path
source=Path(__file__).with_name('eval_local_candidate.py').read_text(encoding='utf-8-sig')
start=source.index('        try:\n            files=json.loads(answer)')
end=source.index('        save(); print(',start)
validation=textwrap.dedent(source[start:end])
for arg in sys.argv[1:]:
    path=Path(arg)
    original_report=json.loads(path.read_text(encoding='utf-8-sig'))
    recorded=original_report['results']['cross_file']
    answer=recorded['response']['choices'][0]['message'].get('content') or ''
    stripped=answer.strip()
    normalized=False
    if stripped.startswith('```json\n') and stripped.endswith('\n```'):
        answer=stripped[len('```json\n'):-len('\n```')]; normalized=True
    elif stripped.startswith('```\n') and stripped.endswith('\n```'):
        answer=stripped[4:-4]; normalized=True
    out=path.parent/'normalized-cross-file'; out.mkdir(exist_ok=True)
    original={'units.py':'','receipt.py':''}
    report={'results':{'cross_file':{}}}
    exec(compile(validation,'trusted-host-cross-file-validator','exec'))
    result=report['results']['cross_file']; result['removed_markdown_fences']=normalized
    result['source_report']=str(path)
    (out/'validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(path.parent.name,json.dumps(result),flush=True)

