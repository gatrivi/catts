import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import contextmanager

from scripts import local_task as task


class LocalTaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / 'project'
        self.project.mkdir()
        (self.project / 'Button.jsx').write_text('export const Button = () => <button />;\n', encoding='utf-8')
        (self.project / 'package.json').write_text(json.dumps({'scripts': {'test': 'node verify.cjs'}}))
        (self.project / 'AGENTS.md').write_text('Preserve existing behavior.')
        self.folder = self.root / 'evidence'
        self.folder.mkdir()

    def test_discovery_excludes_private_and_dependencies(self):
        (self.project / '.env').write_text('SECRET=hidden')
        (self.project / 'node_modules').mkdir()
        (self.project / 'node_modules/Other.jsx').write_text('secret')
        packet = task.discover(self.project, 'Fix Button')
        self.assertEqual(list(packet['files']), ['Button.jsx'])
        self.assertIn('AGENTS.md', packet['instructions'])
        for name in ['../outside.jsx', '.env', 'node_modules/Other.jsx']:
            with self.assertRaises(ValueError):
                task.safe_path(self.project, name)

    def test_invalid_batch_does_not_write_and_protects_tests(self):
        original = task.read(self.project, 'Button.jsx')
        with self.assertRaises(ValueError):
            task.prepare_edits(self.project, ['Button.jsx'], {'edits': [
                {'path': 'Button.jsx', 'before': '<button />', 'after': '<button type="button" />'},
                {'path': 'Button.jsx', 'before': 'MISSING', 'after': ''}]})
        self.assertEqual(task.read(self.project, 'Button.jsx'), original)
        self.assertFalse(task.editable('src/Button.test.jsx'))
        self.assertFalse(task.editable('tests/Button.jsx'))

    def test_journal_resume_is_idempotent_and_preserves_concurrent_change(self):
        changes = task.prepare_edits(self.project, ['Button.jsx'], {'edits': [
            {'path': 'Button.jsx', 'before': '<button />', 'after': '<button type="button" />'}]})
        task.apply_pending(self.project, changes)
        task.apply_pending(self.project, changes)
        (self.project / 'Button.jsx').write_text('user edit')
        with self.assertRaises(ValueError):
            task.apply_pending(self.project, changes)
        self.assertEqual(task.read(self.project, 'Button.jsx'), 'user edit')

    def test_plan_rejects_unknown_files_and_ambiguity(self):
        packet = task.discover(self.project, 'Button')
        for plan in [
            {'question': 'Which behavior?'},
            {'acceptance': ['works'], 'steps': [{'instruction': 'fix', 'files': ['Unknown.jsx']}]},
        ]:
            with self.assertRaises(ValueError):
                task.validate_plan(plan, packet)

    def test_edit_preserves_windows_line_endings(self):
        path = self.project / 'Button.jsx'
        path.write_bytes(b'const a = 1;\r\nconst b = 2;\r\n')
        changes = task.prepare_edits(self.project, ['Button.jsx'], {'edits': [
            {'path': 'Button.jsx', 'before': 'a = 1', 'after': 'a = 3'}]})
        task.apply_pending(self.project, changes)
        self.assertEqual(path.read_bytes(), b'const a = 3;\r\nconst b = 2;\r\n')

    def test_resume_rejects_changed_source(self):
        state = {'hashes': {'Button.jsx': task.digest(task.read(self.project, 'Button.jsx'))},
                 'test_command': task.test_command(self.project)}
        task.verify_snapshot(self.project, state)
        (self.project / 'Button.jsx').write_text('user change')
        with self.assertRaises(ValueError):
            task.verify_snapshot(self.project, state)

    def test_fenced_model_response_is_supported_but_truncation_is_rejected(self):
        body = {'choices': [{'finish_reason': 'stop', 'message': {
            'content': '<think>\n</think>\nExplanation.\n```json\n{"approved": true}\n```'}}]}
        self.assertEqual(task.structured_reply(body), {'approved': True})
        body['choices'][0]['finish_reason'] = 'length'
        with self.assertRaises(ValueError):
            task.structured_reply(body)
        body['choices'][0]['finish_reason'] = 'stop'
        body['choices'][0]['message']['content'] += '\n```json\n{}\n```'
        with self.assertRaises(ValueError):
            task.structured_reply(body)

    def test_reasoning_envelope_allows_plain_json_without_mutating_evidence(self):
        content = '<think>\n\n</think>\n{"approved": true}'
        body = {'choices': [{'finish_reason': 'stop', 'message': {'content': content}}]}
        self.assertEqual(task.structured_reply(body), {'approved': True})
        self.assertEqual(body['choices'][0]['message']['content'], content)
        for invalid in ['<think>{"approved":true}', '<think></think>{"approved":true,}',
                        '<think></think>{}{}', '<think></think>{} trailing text']:
            body['choices'][0]['message']['content'] = invalid
            with self.assertRaises(ValueError):
                task.structured_reply(body)
        body['choices'][0]['message']['content'] = content
        body['choices'][0]['finish_reason'] = 'length'
        with self.assertRaises(ValueError):
            task.structured_reply(body)

    def test_reasoning_envelope_does_not_bypass_plan_limits(self):
        plan = {'acceptance': ['works'], 'steps': [
            {'instruction': 'Fix button', 'files': ['Button.jsx']} for _ in range(4)]}
        body = {'choices': [{'finish_reason': 'stop', 'message': {
            'content': '<think></think>' + json.dumps(plan)}}]}
        with self.assertRaises(ValueError):
            task.validate_plan(task.structured_reply(body), task.discover(self.project, 'Button'))

    def test_cycle_orders_models_and_cannot_pass_failed_tests(self):
        packet = task.discover(self.project, 'Button')
        baseline = {name: task.read(self.project, name) for name in packet['files']}
        state = {'goal': 'Fix Button', 'packet': packet, 'baseline': baseline,
                 'hashes': {n: task.digest(c) for n, c in baseline.items()},
                 'test_command': task.test_command(self.project), 'stage': 'plan', 'attempt': 0}
        events = []
        @contextmanager
        def fake_model(expert, folder):
            events.append(('start', expert))
            yield None
            events.append(('stop', expert))
        replies = [
            {'acceptance': ['No form submit'], 'steps': [{'instruction': 'Fix type', 'files': ['Button.jsx']}]},
            {'edits': [{'path': 'Button.jsx', 'before': '<button />', 'after': '<button type="button" />'}]},
            {'approved': True, 'reason': 'Looks good', 'repair': ''},
        ]
        def fake_test(*args):
            events.append(('test', None))
            return {'code': 1, 'tail': 'Assertion failed'}
        with patch.object(task, 'model', fake_model), patch.object(task, 'ask', side_effect=replies), patch.object(task, 'run_tests', fake_test):
            self.assertEqual(task.run(self.project, self.folder, state), 2)
        self.assertEqual(state['stage'], 'needs_attention')
        self.assertEqual(events, [('test', None), ('start', True), ('stop', True),
                         ('start', False), ('stop', False), ('test', None), ('start', True), ('stop', True)])

    def test_review_repair_is_bounded_and_can_complete(self):
        packet = task.discover(self.project, 'Button')
        baseline = {name: task.read(self.project, name) for name in packet['files']}
        state = {'goal': 'Fix Button', 'packet': packet, 'baseline': baseline,
                 'hashes': {n: task.digest(c) for n, c in baseline.items()},
                 'test_command': task.test_command(self.project), 'stage': 'review', 'attempt': 0,
                 'tests': {'code': 1, 'tail': 'Wrong type'}, 'baseline_tests': {'code': 1},
                 'plan': {'acceptance': ['No form submit'], 'steps': [
                     {'instruction': 'Fix type', 'files': ['Button.jsx']}]}}
        @contextmanager
        def fake_model(*args):
            yield None
        replies = [
            {'approved': False, 'reason': 'Wrong type', 'repair': 'Set button type', 'repair_files': ['Button.jsx']},
            {'edits': [{'path': 'Button.jsx', 'before': '<button />', 'after': '<button type="button" />'}]},
            {'approved': True, 'reason': 'Tests pass and diff fixes the type', 'repair': ''},
        ]
        with patch.object(task, 'model', fake_model), patch.object(task, 'ask', side_effect=replies), patch.object(task, 'run_tests', return_value={'code': 0, 'tail': 'PASS'}):
            self.assertEqual(task.run(self.project, self.folder, state), 0)
        self.assertEqual(state['attempt'], 1)
        self.assertEqual(state['stage'], 'complete')
        self.assertIn('original_plan', state)
        self.assertIn('type="button"', (self.folder / 'latest.diff').read_text())

    def test_resume_pending_final_step_skips_executor_reload(self):
        packet = task.discover(self.project, 'Button')
        baseline = {name: task.read(self.project, name) for name in packet['files']}
        pending = task.prepare_edits(self.project, ['Button.jsx'], {'edits': [
            {'path': 'Button.jsx', 'before': '<button />', 'after': '<button type="button" />'}]})
        state = {'goal': 'Fix Button', 'packet': packet, 'baseline': baseline,
                 'hashes': {n: task.digest(c) for n, c in baseline.items()},
                 'test_command': task.test_command(self.project), 'stage': 'execute', 'attempt': 0,
                 'step': 0, 'pending': pending, 'baseline_tests': {'code': 1},
                 'plan': {'acceptance': ['No form submit'], 'steps': [
                     {'instruction': 'Fix type', 'files': ['Button.jsx']}]}}
        started = []
        @contextmanager
        def fake_model(expert, folder):
            started.append(expert)
            yield None
        with patch.object(task, 'model', fake_model), patch.object(task, 'ask', return_value={
                'approved': True, 'reason': 'Tested', 'repair': ''}), patch.object(task, 'run_tests', return_value={'code': 0, 'tail': 'PASS'}):
            self.assertEqual(task.run(self.project, self.folder, state), 0)
        self.assertEqual(started, [True])
        self.assertIsNone(state['pending'])

    def test_executor_retries_invalid_batch_once_without_writing(self):
        original = task.read(self.project, 'Button.jsx')
        payload = {'step': {'files': ['Button.jsx']}}
        valid = {'edits': [{'path': 'Button.jsx', 'before': '<button />', 'after': '<button type="button" />'}]}
        with patch.object(task, 'ask', side_effect=[ValueError('Malformed JSON'), valid]) as ask:
            result = task.executor_edits(None, payload, self.project, self.folder, 'retry')
        self.assertEqual(ask.call_count, 2)
        self.assertEqual(ask.call_args.args[2]['format_error'], 'Malformed JSON')
        self.assertIn('type="button"', result['Button.jsx']['after'])
        self.assertEqual(task.read(self.project, 'Button.jsx'), original)
        with patch.object(task, 'ask', side_effect=ValueError('Malformed JSON')) as ask:
            with self.assertRaises(ValueError):
                task.executor_edits(None, payload, self.project, self.folder, 'retry')
        self.assertEqual(ask.call_count, 2)

    def test_handoff_records_blocker_without_claiming_edits_are_verified(self):
        state = {'goal': 'Fix Button', 'stage': 'execute', 'attempt': 0, 'worker': 'bonsai', 'step': 1,
                 'plan': {'acceptance': ['No form submit'], 'steps': [
                     {'instruction': 'Fix type', 'files': ['Button.jsx']}]}}
        task.write_handoff(self.folder, state, 'Model stopped')
        note = (self.folder / 'HANDOFF.md').read_text(encoding='utf-8')
        for expected in ['Worker: bonsai', 'Paused because: Model stopped', '[edited]',
                         'Do not treat edited steps as verified', 'state.json', '--resume']:
            self.assertIn(expected, note)


if __name__ == '__main__':
    unittest.main()
