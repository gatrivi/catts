"""Fetch one pinned Qwen3.5 9B Q4 model, with cache/output exclusively on Z:."""
import hashlib
import json
import os
from pathlib import Path
import shutil

os.environ['HF_HOME'] = 'Z:/models/.hf-home'
os.environ['HF_XET_CACHE'] = 'Z:/models/.hf-xet-cache'
os.environ['HF_HUB_DISABLE_XET'] = '1'
from huggingface_hub import HfApi, hf_hub_download

repo = 'unsloth/Qwen3.5-9B-GGUF'
filename = 'Qwen3.5-9B-Q4_K_M.gguf'
destination = Path('Z:/models/coding/Qwen3.5-9B')
info = HfApi().model_info(repo, files_metadata=True)
entry = next(f for f in info.siblings if f.rfilename == filename)
expected = entry.lfs.sha256
print(json.dumps({'repo':repo,'revision':info.sha,'file':filename,'bytes':entry.size,'sha256':expected}),flush=True)
if shutil.disk_usage('Z:/').free < entry.size * 2 + 2*1024**3:
    raise RuntimeError('Insufficient free space on Z:')
path = Path(hf_hub_download(repo, filename, revision=info.sha, local_dir=destination))
print('Verifying SHA256...',flush=True)
with path.open('rb') as stream:
    actual = hashlib.file_digest(stream, 'sha256').hexdigest()
if actual != expected:
    raise RuntimeError('Checksum mismatch; model will not be launched')
(destination / 'verified.json').write_text(json.dumps({'repo':repo,'revision':info.sha,
    'file':filename,'bytes':path.stat().st_size,'sha256':actual},indent=2),encoding='utf-8')
print(f'VERIFIED {path}',flush=True)
