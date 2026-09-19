import hashlib,json,subprocess
from pathlib import Path
root=Path('Z:/catts/local-coding/data/e4b-project-trials')
project=root/'20260906-184019'
base=json.loads((root/'20260906-184019-baseline.json').read_text())
out=root/'20260906-184019-review/host-tested'
out.mkdir(parents=True,exist_ok=False)
for name,content in base['files'].items():
 p=out/name;p.parent.mkdir(parents=True,exist_ok=True)
 if name.startswith('src/'): p.write_bytes((project/name).read_bytes())
 else: p.write_text(content,encoding='utf-8')
assert hashlib.sha256((out/'tests/checkout.test.cjs').read_bytes()).hexdigest()==base['hashes']['tests/checkout.test.cjs']
r=subprocess.run(['C:/Soft/nodejs/node.exe','--test','tests/checkout.test.cjs'],cwd=out,capture_output=True,text=True,timeout=30)
(out.parent/'original-tests.log').write_text(r.stdout+r.stderr,encoding='utf-8')
(out.parent/'original-tests-result.json').write_text(json.dumps({'test_exit':r.returncode,'original_tests_verified':True,'trial_rejected_for_protected_changes':True},indent=2))
print((r.stdout+r.stderr)[-1800:])
