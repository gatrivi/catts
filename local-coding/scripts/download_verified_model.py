"""Pinned, resumable GGUF download with size and SHA256 verification."""
import argparse,hashlib,json,shutil,time
from pathlib import Path
import httpx
from huggingface_hub import HfApi
p=argparse.ArgumentParser(); p.add_argument('repo'); p.add_argument('file'); p.add_argument('folder'); a=p.parse_args()
root=Path(__file__).resolve().parents[1]/'data/models'/a.folder
assert Path(a.folder).name==a.folder
root.mkdir(parents=True,exist_ok=True)
info=HfApi().model_info(a.repo,files_metadata=True)
e=next(f for f in info.siblings if f.rfilename==a.file)
m=dict(repo=a.repo,revision=info.sha,file=a.file,bytes=e.size,sha256=e.lfs.sha256)
print(json.dumps(m),flush=True)
name=Path(a.file).name
manifest=root/(name+'.manifest.json')
partial=root/(name+'.partial')
if manifest.exists() and json.loads(manifest.read_text())!=m: raise RuntimeError('Manifest changed; preserve existing download')
manifest.write_text(json.dumps(m,indent=2))
if shutil.disk_usage(root).free<e.size+1024**3: raise RuntimeError('Insufficient disk space')
final=root/name
if final.exists(): partial=final
size=partial.stat().st_size if partial.exists() else 0
url='https://huggingface.co/'+a.repo+'/resolve/'+info.sha+'/'+a.file
with httpx.Client(follow_redirects=True,timeout=45) as client:
    while size<e.size:
        end=min(size+32*1024**2,e.size)-1
        for attempt in range(3):
            try:
                r=client.get(url,headers={'Range':f'bytes={size}-{end}'})
                r.raise_for_status()
                if r.status_code!=206 or len(r.content)!=end-size+1 or not r.headers.get('Content-Range','').startswith(f'bytes {size}-{end}/'): raise RuntimeError('Unexpected range response')
                break
            except httpx.HTTPError:
                if attempt==2: raise
                time.sleep(2)
        with partial.open('ab') as f: f.write(r.content)
        size=end+1
        if size%(512*1024**2)==0 or size==e.size: print(f'{a.folder}: {size}/{e.size}',flush=True)
print('Verifying '+name,flush=True)
with partial.open('rb') as f: actual=hashlib.file_digest(f,'sha256').hexdigest()
assert actual==m['sha256'] and partial.stat().st_size==e.size,'Verification failed'
if partial!=final: partial.rename(final)
(root/(name+'.verified.json')).write_text(json.dumps(m,indent=2))
print('VERIFIED '+str(final),flush=True)
