import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / 'data/smol/probes/20260916-211401/16384-default/agent.jsonl'
SCRIPT = ROOT / 'scripts/minicpm_tool_probe.py'


class MiniCPMProbeEndToEndTests(unittest.TestCase):
    def test_original_log_through_actual_cli(self):
        original_hash = hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            case = Path(folder) / 'fresh-case'
            case.mkdir()
            copied = case / 'agent.jsonl'
            shutil.copyfile(ORIGINAL, copied)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), '--validate-case', str(case)],
                cwd=folder, capture_output=True, text=True, encoding='utf-8',
                errors='replace', timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout), {
                'raw_read_calls': 1,
                'tool_calls': ['read'],
                'saw_marker': True,
                'successful_reads': 1,
                'result': 'pass',
            })
            self.assertEqual(hashlib.sha256(copied.read_bytes()).hexdigest(), original_hash)
        self.assertEqual(hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(), original_hash)


if __name__ == '__main__':
    unittest.main()
