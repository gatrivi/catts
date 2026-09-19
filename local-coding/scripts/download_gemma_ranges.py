import hashlib,json,time
from pathlib import Path
import httpx
root=Path('Z:/catts/local-coding/data/models/gemma4-coder-q3')
m=json.loads((root/'manifest.json').read_text())
p=root/(m['file']+'.partial')
u='https://huggingface.co/'+m['repo']+'/resolve/'+m['revision']+'/'+m['file']
size=p.stat().st_size if p.exists() else 0
with httpx.Client(follow_redirects=True,timeout=30) as client:
    while size<m['bytes']:
        end=min(size+32*1024**2,m['bytes'])-1
        r=client.get(u,headers={'Range':f'bytes={size}-{end}'})
        r.raise_for_status()
        if r.status_code!=206 or len(r.content)!=end-size+1: raise RuntimeError('Unexpected range response')
        with p.open('ab') as f: f.write(r.content)
        size=end+1
        if size%(256*1024**2)==0 or size==m['bytes']: print(f'{size}/{m["bytes"]} bytes',flush=True)
print('Verifying SHA256',flush=True)
with p.open('rb') as f: actual=hashlib.file_digest(f,'sha256').hexdigest()
assert actual==m['sha256'],'SHA256 mismatch'
p.rename(root/m['file'])
(root/'verified.json').write_text(json.dumps(m,indent=2))
print('VERIFIED',flush=True)
