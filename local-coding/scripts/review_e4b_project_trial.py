"""Host review of a disposable project; tests run only after human/agent diff review."""
import argparse,difflib,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('project');p.add_argument('--run-tests',action='store_true');a=p.parse_args()
project=Path(a.project).resolve()
assert project.parent==ROOT/'data/e4b-project-trials','Only trial fixtures allowed'
baseline=json.loads(project.parent.joinpath(project.name+'-baseline.json').read_text())
report={'project':str(project),'changed':[],'protected_unchanged':True}
diffs=[]
for name,expected in baseline['hashes'].items():
 path=project/name
 digest=hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
 if digest!=expected:
  report['changed'].append(name)
  if not name.startswith('src/'): report['protected_unchanged']=False
  actual=path.read_text() if path.exists() else ''
  diffs.extend(difflib.unified_diff(baseline['files'][name].splitlines(True),actual.splitlines(True),fromfile='before/'+name,tofile='after/'+name))
extra=[str(p.relative_to(project)) for p in project.rglob('*') if p.is_file() and str(p.relative_to(project)).replace('\\','/') not in baseline['hashes'] and p.name!='baseline-test.log']
report['extra_files']=extra
folder=project.parent/(project.name+'-review');folder.mkdir(exist_ok=True)
(folder/'diff.patch').write_text(''.join(diffs),encoding='utf-8')
if a.run_tests:
 assert report['protected_unchanged'],'Protected files changed; reject trial'
 result=subprocess.run(['C:/Soft/nodejs/node.exe','--test','tests/checkout.test.cjs'],cwd=project,capture_output=True,text=True,timeout=30)
 report['test_exit']=result.returncode
 (folder/'test.log').write_text(result.stdout+result.stderr,encoding='utf-8')
 print((result.stdout+result.stderr)[-1400:])
(folder/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
if not a.run_tests: print(''.join(diffs))
