import hashlib,json,os,shutil
from pathlib import Path
root=Path('Z:/catts/local-coding/data')
os.environ['HF_HOME']=str(root/'hf-home')
os.environ['HF_HUB_DISABLE_XET']='1'
from huggingface_hub import HfApi,hf_hub_download
repo='yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF'
name='gemma4-coding-Q3_K_M.gguf'
info=HfApi().model_info(repo,files_metadata=True)
e=next(f for f in info.siblings if f.rfilename==name)
m=dict(repo=repo,revision=info.sha,file=name,bytes=e.size,sha256=e.lfs.sha256)
print(json.dumps(m),flush=True)
if shutil.disk_usage('Z:/').free<e.size*2+2*1024**3: raise RuntimeError('Insufficient disk space')
dest=root/'models/gemma4-coder-q3'
dest.mkdir(parents=True,exist_ok=True)
(dest/'manifest.json').write_text(json.dumps(m,indent=2))
p=Path(hf_hub_download(repo,name,revision=info.sha,local_dir=dest))
with p.open('rb') as f: actual=hashlib.file_digest(f,'sha256').hexdigest()
assert actual==m['sha256'] and p.stat().st_size==e.size,'Verification failed'
(dest/'verified.json').write_text(json.dumps(m,indent=2))
print('VERIFIED '+str(p),flush=True)
