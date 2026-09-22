import json
import tempfile
import unittest
from pathlib import Path

import scripts.golden_check as gc


def dump(texts=None, tokens=None, status='ok', name='m1', spec_hash='h1', prompts_ids=('p1',)):
    prompts = []
    for pid in prompts_ids:
        e = {'id': pid, 'text': (texts or {}).get(pid, 'abc'), 'n': 3}
        if tokens and pid in tokens:
            e['tokens'] = tokens[pid]
        prompts.append(e)
    return {'spec_hash': spec_hash, 'models': [{'name': name, 'status': status, 'prompts': prompts}]}


class CompareTests(unittest.TestCase):
    def test_identical_ok(self):
        s = gc.compare_golds(dump(), dump())
        self.assertEqual(s['prompts_compared'], 1)
        self.assertEqual(s['prompts_diverged'], 0)
        self.assertTrue(s['spec_match'])
        self.assertEqual(gc.verdict(s), 0)

    def test_text_divergence_reports_first_diff_and_exit_1(self):
        s = gc.compare_golds(dump(texts={'p1': 'hello world'}),
                             dump(texts={'p1': 'hello wxrld'}))
        self.assertEqual(s['prompts_diverged'], 1)
        pm = s['models'][0]['prompts'][0]
        self.assertEqual(pm['first_diff_char'], 7)
        self.assertEqual(gc.verdict(s), 1)

    def test_token_and_logprob_metrics(self):
        ta = [{'t': 'a', 'lp': -0.1}, {'t': 'b', 'lp': -0.2}]
        tb = [{'t': 'a', 'lp': -0.4}, {'t': 'b', 'lp': -0.2}]
        s = gc.compare_golds(dump(texts={'p1': 'ab'}, tokens={'p1': ta}),
                             dump(texts={'p1': 'ab'}, tokens={'p1': tb}))
        self.assertEqual(s['prompts_diverged'], 0)
        pm = s['models'][0]['prompts'][0]
        self.assertIsNone(pm['first_diff_token'])
        self.assertAlmostEqual(pm['lp_max_d'], 0.3, places=4)
        self.assertAlmostEqual(pm['lp_mean_d'], 0.15, places=4)

    def test_missing_model_is_structural_when_nothing_comparable(self):
        s = gc.compare_golds(dump(name='m1'), dump(name='OTRO'))
        self.assertIsNotNone(s['structural_error'])
        self.assertEqual(gc.verdict(s), 2)

    def test_missing_prompt_counts_as_diverged(self):
        s = gc.compare_golds(dump(prompts_ids=('p1', 'p2')), dump(prompts_ids=('p1',)))
        self.assertEqual(s['prompts_compared'], 1)
        self.assertEqual(s['prompts_diverged'], 1)
        self.assertEqual(gc.verdict(s), 1)

    def test_error_prompt_counts(self):
        b = dump()
        b['models'][0]['prompts'][0]['status'] = 'error'
        s = gc.compare_golds(dump(), b)
        self.assertEqual(s['prompts_diverged'], 1)

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            fa = Path(tmp) / 'a.json'
            fb = Path(tmp) / 'b.json'
            fa.write_text(json.dumps(dump()), encoding='utf-8')
            fb.write_text(json.dumps(dump(texts={'p1': 'zzz'})), encoding='utf-8')
            self.assertEqual(gc.main([str(fa), str(fb)]), 1)
            self.assertEqual(gc.main([str(fa), str(fa)]), 0)


if __name__ == '__main__':
    unittest.main()
