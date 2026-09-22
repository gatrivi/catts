import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import scripts.kaggle_bench as kb


class QuotaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = Path(self.tmp.name) / 'quota_ledger.json'
        patch = mock.patch.object(kb, 'LEDGER', self.ledger)
        patch.start()
        self.addCleanup(patch.stop)

    def test_fresh_ledger_allows_and_logs(self):
        ok, used, budget = kb.quota_check(5.0)
        self.assertTrue(ok)
        self.assertEqual((used, budget), (0.0, kb.DEFAULT_BUDGET_H))
        total = kb.quota_log(5.0)
        self.assertEqual(total, 5.0)
        self.assertEqual(kb.read_ledger()['weeks'][kb.week_key()], 5.0)

    def test_refuses_when_over_budget(self):
        kb.quota_log(28.0)
        ok, used, budget = kb.quota_check(5.0)
        self.assertFalse(ok)
        self.assertEqual(used, 28.0)

    def test_exactly_budget_allowed(self):
        kb.quota_log(28.0)
        ok, _, _ = kb.quota_check(2.0)
        self.assertTrue(ok)


class CandidatesTests(unittest.TestCase):
    def test_filters_incomplete_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / 'c.json'
            f.write_text(json.dumps({'items': [
                {'name': 'ok', 'repo': 'a/b', 'file': 'm.gguf'},
                {'name': 'no-repo', 'repo': '', 'file': 'm.gguf'},
                {'name': 'no-file', 'repo': 'a/b'},
            ]}), encoding='utf-8')
            items = kb.load_candidates(str(f))
            self.assertEqual([i['name'] for i in items], ['ok'])

    def test_rejects_when_nothing_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / 'c.json'
            f.write_text(json.dumps({'items': [{'name': 'x', 'repo': '', 'file': ''}]}), encoding='utf-8')
            with self.assertRaises(SystemExit):
                kb.load_candidates(str(f))


class KernelGenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        conf = mock.patch.object(kb, 'kaggle_conf', return_value={'username': 'tester', 'key': 'k'})
        conf.start()
        self.addCleanup(conf.stop)

    def test_generates_kernel_with_inlined_candidates_and_metadata(self):
        items = [{'name': 'm', 'repo': 'a/b', 'file': 'm.gguf', 'ctx': 16384}]
        user, workdir = kb.generate_kernel(items, self.tmp.name)
        self.assertEqual(user, 'tester')
        kb.write_metadata(workdir, user, 'slug-x')
        src = (workdir / 'bench_kernel.py').read_text(encoding='utf-8')
        self.assertNotIn('CANDIDATES = __CANDIDATES__', src)
        self.assertIn("'m.gguf'", src)
        meta = json.loads((workdir / 'kernel-metadata.json').read_text(encoding='utf-8'))
        self.assertTrue(meta['enable_gpu'])
        self.assertTrue(meta['enable_internet'])
        self.assertEqual(meta['id'], 'tester/slug-x')
        self.assertEqual(meta['kernel_type'], 'script')

    def test_write_metadata_uses_slug(self):
        meta = kb.write_metadata(self.tmp.name, 'tester', 'bench-20260920')
        self.assertEqual(meta['id'], 'tester/bench-20260920')

    def test_template_missing_marker_fails(self):
        with mock.patch.object(kb, 'TEMPLATE', Path(self.tmp.name) / 'nope.py'):
            with self.assertRaises(SystemExit):
                kb.generate_kernel([{'repo': 'a/b', 'file': 'x'}], self.tmp.name)


class ParseStatusTests(unittest.TestCase):
    def test_parses_quoted_and_plain(self):
        self.assertEqual(kb.parse_status('"x/y" has status "complete"'), 'complete')
        self.assertEqual(kb.parse_status('has status running'), 'running')
        self.assertIsNone(kb.parse_status('nada'))


class VerbTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for target, val in (('LEDGER', Path(self.tmp.name) / 'q.json'),):
            p = mock.patch.object(kb, target, val)
            p.start()
            self.addCleanup(p.stop)
        root = mock.patch.object(kb, 'ROOT', Path(self.tmp.name))
        root.start()
        self.addCleanup(root.stop)
        # TEMPLATE real se usa solo si existe el marcador; usamos una mini-plantilla
        tpl = Path(self.tmp.name) / 'bench_kernel.py'
        tpl.write_text('CANDIDATES = __CANDIDATES__\n', encoding='utf-8')
        tplt = mock.patch.object(kb, 'TEMPLATE', tpl)
        tplt.start()
        self.addCleanup(tplt.stop)

    def test_push_dry_run_creates_files_without_cli_or_quota(self):
        cand = Path(self.tmp.name) / 'c.json'
        cand.write_text(json.dumps({'items': [{'name': 'm', 'repo': 'a/b', 'file': 'm.gguf'}]}), encoding='utf-8')
        with mock.patch.object(kb, 'kaggle_conf', return_value={'username': 'tester', 'key': 'k'}), \
             mock.patch.object(kb, 'run') as run_mock:
            rc = kb.cmd_push(argparse.Namespace(
                candidates=str(cand), slug='dry1', estimate_hours=None, dry_run=True, force=False))
        self.assertEqual(rc, 0)
        run_mock.assert_not_called()
        workdir = Path(self.tmp.name) / 'data' / 'kaggle' / 'push-dry1'
        self.assertTrue((workdir / 'kernel-metadata.json').is_file())
        self.assertFalse((Path(self.tmp.name) / 'q.json').exists())  # dry-run no toca cuota

    def test_push_success_logs_quota(self):
        cand = Path(self.tmp.name) / 'c.json'
        cand.write_text(json.dumps({'items': [{'name': 'm', 'repo': 'a/b', 'file': 'm.gguf'}]}), encoding='utf-8')
        with mock.patch.object(kb, 'kaggle_conf', return_value={'username': 'tester', 'key': 'k'}), \
             mock.patch.object(kb, 'run', return_value=mock.Mock(returncode=0, stdout='pushed', stderr='')):
            rc = kb.cmd_push(argparse.Namespace(
                candidates=str(cand), slug='live1', estimate_hours=1.0, dry_run=False, force=False))
        self.assertEqual(rc, 0)
        led = json.loads((Path(self.tmp.name) / 'q.json').read_text(encoding='utf-8'))
        self.assertEqual(led['weeks'][kb.week_key()], 1.0)

    def test_push_refuses_over_quota_without_force(self):
        kb.quota_log(29.9)
        cand = Path(self.tmp.name) / 'c.json'
        cand.write_text(json.dumps({'items': [{'name': 'm', 'repo': 'a/b', 'file': 'm.gguf'}]}), encoding='utf-8')
        with mock.patch.object(kb, 'run') as run_mock:
            with self.assertRaises(SystemExit):
                kb.cmd_push(argparse.Namespace(
                    candidates=str(cand), slug='over', estimate_hours=None, dry_run=False, force=False))
        run_mock.assert_not_called()

    def test_status_complete_hints_pull(self):
        with mock.patch.object(kb, 'kaggle_conf', return_value={'username': 'tester', 'key': 'k'}), \
             mock.patch.object(kb, 'run', return_value=mock.Mock(
                 returncode=0, stdout='"tester/s1" has status "complete"', stderr='')) as run_mock:
            kb.cmd_status(argparse.Namespace(slug='s1'))
        self.assertIn('kernels', run_mock.call_args[0][0])

    def test_pull_reads_results(self):
        dest = Path(self.tmp.name) / 'data' / 'kaggle_runs' / 's2'
        dest.mkdir(parents=True)
        (dest / 'results.json').write_text(json.dumps([
            {'name': 'm1', 'status': 'ok', 'decode': {'tg_tps': 20.0}, 'pp': {'pp_tps': 200.0}},
            {'name': 'm2', 'status': 'load_failed'},
        ]), encoding='utf-8')
        # pull crea el dir y sobreescribe: simulamos descarga previa parcheando run
        def fake_run(cmd, timeout=600):
            # el output ya esta en destino (como si kaggle lo hubiera bajado)
            return mock.Mock(returncode=0, stdout='ok', stderr='')
        with mock.patch.object(kb, 'kaggle_conf', return_value={'username': 'tester', 'key': 'k'}), \
             mock.patch.object(kb, 'run', side_effect=fake_run):
            rc = kb.cmd_pull(argparse.Namespace(slug='s2'))
        self.assertEqual(rc, 0)


class GoldenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for target, val in (('LEDGER', Path(self.tmp.name) / 'q.json'),
                            ('ROOT', Path(self.tmp.name)),
                            ('TEMPLATE', Path(self.tmp.name) / 'bench_kernel.py'),
                            ('GOLDEN_TEMPLATE', Path(self.tmp.name) / 'golden_kernel.py'),
                            ('GOLDEN_PROMPTS', Path(self.tmp.name) / 'golden_prompts.json')):
            p = mock.patch.object(kb, target, val)
            p.start()
            self.addCleanup(p.stop)
        (Path(self.tmp.name) / 'bench_kernel.py').write_text('CANDIDATES = __CANDIDATES__\n', encoding='utf-8')
        (Path(self.tmp.name) / 'golden_kernel.py').write_text(
            'CANDIDATES = __CANDIDATES__\nPROMPTS = __PROMPTS__\n', encoding='utf-8')
        (Path(self.tmp.name) / 'golden_prompts.json').write_text(
            json.dumps({'sampling': {'temperature': 0}, 'prompts': [{'id': 'x'}]}), encoding='utf-8')

    def _cand(self):
        f = Path(self.tmp.name) / 'c.json'
        f.write_text(json.dumps({'items': [{'name': 'm', 'repo': 'a/b', 'file': 'm.gguf', 'golden': True}]}), encoding='utf-8')
        return f

    def test_generate_golden_kernel_inlines_both_markers(self):
        with mock.patch.object(kb, 'kaggle_conf', return_value={'username': 'tester', 'key': 'k'}):
            user, workdir = kb.generate_golden_kernel([{'name': 'm', 'repo': 'a/b', 'file': 'm.gguf', 'golden': True}],
                                                      str(Path(self.tmp.name) / 'gk'))
        self.assertEqual(user, 'tester')
        src = (workdir / 'golden_kernel.py').read_text(encoding='utf-8')
        self.assertNotIn('__CANDIDATES__', src)
        self.assertNotIn('__PROMPTS__', src)
        self.assertIn("'m.gguf'", src)
        self.assertIn("'temperature'", src)
        self.assertIn('True', src)  # bools python-validos, no true/false json

    def test_push_golden_dry_run(self):
        with mock.patch.object(kb, 'kaggle_conf', return_value={'username': 'tester', 'key': 'k'}), \
             mock.patch.object(kb, 'run') as run_mock:
            rc = kb.cmd_push(argparse.Namespace(
                candidates=str(self._cand()), slug='g1', estimate_hours=None,
                golden=True, dry_run=True, force=False))
        self.assertEqual(rc, 0)
        run_mock.assert_not_called()
        meta = json.loads((Path(self.tmp.name) / 'data' / 'kaggle' / 'push-g1' / 'kernel-metadata.json')
                          .read_text(encoding='utf-8'))
        self.assertEqual(meta['code_file'], 'golden_kernel.py')
        self.assertEqual(meta['id'], 'tester/g1')
        self.assertTrue(meta['enable_gpu'])
        self.assertFalse((Path(self.tmp.name) / 'q.json').exists())  # dry-run no toca cuota

    def test_pull_prints_golden_summary(self):
        dest = Path(self.tmp.name) / 'data' / 'kaggle_runs' / 'g2'
        dest.mkdir(parents=True)
        (dest / 'golden.json').write_text(json.dumps({
            'spec_hash': 'abc123', 'models': [
                {'name': 'm', 'status': 'ok', 'logprobs_mode': 'top',
                 'prompts': [{'id': 'p1', 'n': 10}, {'id': 'p2', 'n': 20}]}]}), encoding='utf-8')
        with mock.patch.object(kb, 'kaggle_conf', return_value={'username': 'tester', 'key': 'k'}), \
             mock.patch.object(kb, 'run', return_value=mock.Mock(returncode=0, stdout='ok', stderr='')):
            rc = kb.cmd_pull(argparse.Namespace(slug='g2'))
        self.assertEqual(rc, 0)


if __name__ == '__main__':
    unittest.main()
