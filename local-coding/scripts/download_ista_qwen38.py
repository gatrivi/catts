"""Download and verify the selected official ISTA model exclusively on Z:."""
import hashlib
import json
import os
from pathlib import Path
import shutil

os.environ['HF_HOME']='Z:/models/.hf-home'
os.environ['HF_XET_CACHE']='Z:/models/.hf-xet-cache'
os.environ['HF_HUB_DISABLE_XET']='1'
from huggingface_hub import HfApi,hf_hub_download

REPO='ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF'
FILE='Qwen3.8-27B-GSQ-RCO-IQ2_XS-mtp.gguf'
EXPECTED='f3369f8d36968ab7dd12f5ff11452680aef9371aa19c9922d22ccd5e58c2d9c8'
DEST=Path('Z:/models/coding/Qwen3.8-27B-GSQ-RCO-IQ2_XS-MTP')

def main():
    info=HfApi().model_info(REPO,files_metadata=True)
    entry=next(f for f in info.siblings if f.rfilename==FILE)
    if entry.lfs.sha256!=EXPECTED:
        raise RuntimeError('Published checksum changed; inspect release before downloading')
    manifest={'repo':REPO,'revision':info.sha,'file':FILE,'bytes':entry.size,'sha256':EXPECTED}
    print(json.dumps(manifest),flush=True)
    if shutil.disk_usage('Z:/').free < entry.size*2+2*1024**3:
        raise RuntimeError('Insufficient free space on Z:; no deletion performed')
    DEST.mkdir(parents=True,exist_ok=True)
    (DEST/'download-manifest.json').write_text(json.dumps(manifest,indent=2))
    path=Path(hf_hub_download(REPO,FILE,revision=info.sha,local_dir=DEST))
    print('Verifying complete file SHA256...',flush=True)
    with path.open('rb') as stream:
        actual=hashlib.file_digest(stream,'sha256').hexdigest()
    if path.stat().st_size!=entry.size or actual!=EXPECTED:
        raise RuntimeError('Verification failed; model must not be launched')
    (DEST/'verified.json').write_text(json.dumps(manifest,indent=2))
    print('VERIFIED '+str(path),flush=True)

if __name__=='__main__':main()
