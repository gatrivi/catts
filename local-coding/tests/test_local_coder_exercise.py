import tempfile
import unittest
from pathlib import Path
from scripts.local_coder_exercise import CASES, run_tests, validate


class ExerciseTests(unittest.TestCase):
    def test_known_broken_and_correct_solutions(self):
        corrected = {
            'average': 'def average(xs):\n    if not xs: raise ValueError("empty")\n    return sum(xs) / len(xs)\n',
            'settings': 'def settings(text):\n    result = {}\n    for line in text.splitlines():\n        line = line.strip()\n        if not line or line.startswith("#"): continue\n        key, value = line.split("=", 1)\n        result[key.strip()] = value.strip()\n    return result\n',
            'unique': 'def unique(xs):\n    return list(dict.fromkeys(xs))\n',
        }
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/'solution.py'
            for name, (source, _, _) in CASES.items():
                path.write_text(source,encoding='utf-8')
                self.assertFalse(run_tests(name,path)['passed'])
                path.write_text(corrected[name],encoding='utf-8')
                self.assertTrue(run_tests(name,path)['passed'])

    def test_rejects_code_outside_exercise(self):
        for source in ['import os', 'def f():\n    return open("secret")',
                       'def f():\n    return (1).__class__', 'while True: pass']:
            with self.assertRaises(ValueError):
                validate(source)

    def test_partition_settings_solution(self):
        source = '''def settings(text):
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator:
            raise ValueError('Malformed line')
        result[key.strip()] = value.strip()
    return result
'''
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'solution.py'
            path.write_text(source, encoding='utf-8')
            self.assertTrue(run_tests('settings', path)['passed'])
