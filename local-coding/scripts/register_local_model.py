"""Registra un GGUF ya descargado: escribe <archivo>.verified.json con bytes y sha256 locales.

Uso: python scripts/register_local_model.py RUTA.gguf [RUTA2.gguf ...]
El hash es local (integridad de aqui en adelante), no prueba procedencia de HF.
"""
import hashlib, json, sys
from pathlib import Path

for arg in sys.argv[1:]:
 path = Path(arg)
 if not path.is_file(): raise SystemExit('No existe: ' + str(path))
 with path.open('rb') as f: digest = hashlib.file_digest(f, 'sha256').hexdigest()
 manifest = {'repo': None, 'revision': None, 'file': path.name, 'bytes': path.stat().st_size,
  'sha256': digest, 'source': 'local-hash'}
 path.with_name(path.name + '.verified.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
 print('OK', path.name, manifest['bytes'], digest[:12])
