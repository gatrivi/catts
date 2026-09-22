import json
import tempfile
import unittest
from unittest import mock

import scripts.gpu_sweep as gs


class FakeSrv:
    def __init__(self, exit_code=None):
        self.exit_code = exit_code
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.exit_code

    def terminate(self):
        self.terminated = True

    def wait(self, t):
        return 0

    def kill(self):
        self.killed = True


class SweepMatrixTests(unittest.TestCase):
    def test_matrix_count_and_compatibility(self):
        runs = gs.build_runs(['mini'], [(256, 128), (512, 256)], ['q8_0', 'q4_0'])
        self.assertEqual(len(runs), 8)  # 2 runtimes x 2 ubs x 2 kvs
        self.assertEqual({r['runtime'] for r in runs}, {'default', 'b10964'})

    def test_bonsai2_only_prism(self):
        runs = gs.build_runs(['bonsai2'], [(256, 128)], ['q8_0'])
        self.assertEqual([r['runtime'] for r in runs], ['prism'])

    def test_argv_flags(self):
        run = {'model': 'qwen35', 'runtime': 'default', 'b': 512, 'ub': 256, 'kv': 'q4_0'}
        argv = gs.server_argv(run, 9151, 'Vulkan0')
        self.assertEqual(argv[0], gs.RUNTIMES['default'])
        self.assertEqual(argv[argv.index('--device') + 1], 'Vulkan0')
        self.assertIn('--no-mmap', argv)
        self.assertIn('9151', argv)
        self.assertEqual(argv[argv.index('-b') + 1], '512')
        self.assertEqual(argv[argv.index('-ub') + 1], '256')
        self.assertEqual(argv[argv.index('-ctk') + 1], 'q4_0')
        self.assertEqual(argv[argv.index('-ctv') + 1], 'q4_0')
        self.assertEqual(argv[argv.index('-ngl') + 1], '999')

    def test_detect_device_prefers_vulkan1(self):
        out = '  Vulkan0 = 0x0000\n  Vulkan1 = 0x0001'
        with mock.patch('scripts.gpu_sweep.subprocess.run',
                        return_value=mock.Mock(stdout=out)):
            self.assertEqual(gs.detect_device('x.exe'), 'Vulkan1')

    def test_detect_device_falls_back_to_only_device(self):
        with mock.patch('scripts.gpu_sweep.subprocess.run',
                        return_value=mock.Mock(stdout='  Vulkan0 = 0x0000')):
            self.assertEqual(gs.detect_device('x.exe'), 'Vulkan0')
        with mock.patch('scripts.gpu_sweep.subprocess.run', side_effect=OSError):
            self.assertEqual(gs.detect_device('x.exe'), 'Vulkan1')


class RunOneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log_dir = gs.Path(self.tmp.name)
        self.run = {'model': 'mini', 'runtime': 'default', 'b': 256, 'ub': 128, 'kv': 'q8_0'}
        patcher = mock.patch.object(gs, 'free_ram_mb', return_value=8000)
        patcher.start()
        self.addCleanup(patcher.stop)
        sleep_p = mock.patch('scripts.gpu_sweep.time.sleep', lambda s: None)
        sleep_p.start()
        self.addCleanup(sleep_p.stop)

    def test_ok_path_measures_and_stops_server(self):
        stats = {'pp_n': 2200, 'pp_tps': 350.0, 'tg_n': 640, 'tg_tps': 31.2, 'wall_s': 20.0}
        with mock.patch.object(gs, 'wait_health', return_value=1.5), \
             mock.patch.object(gs, 'chat', return_value=(stats, 20.0)), \
             mock.patch('scripts.gpu_sweep.subprocess.Popen', return_value=FakeSrv()):
            res = gs.run_one(self.run, 9151, 2500, 600, self.log_dir, 'Vulkan1')
        self.assertEqual(res['status'], 'ok')
        self.assertEqual(res['decode']['tg_tps'], 31.2)
        self.assertEqual(res['pp']['pp_tps'], 350.0)
        self.assertEqual(res['load_s'], 1.5)

    def test_load_failed_records_tail_and_still_stops(self):
        srv = FakeSrv(exit_code=1)
        with mock.patch.object(gs, 'wait_health', return_value=None), \
             mock.patch('scripts.gpu_sweep.subprocess.Popen', return_value=srv):
            res = gs.run_one(self.run, 9151, 2500, 600, self.log_dir, 'Vulkan1')
        self.assertEqual(res['status'], 'load_failed')
        self.assertIn('error_tail', res)
        self.assertTrue(srv.terminated)

    def test_ram_floor_skips_launch(self):
        with mock.patch.object(gs, 'free_ram_mb', return_value=100), \
             mock.patch('scripts.gpu_sweep.subprocess.Popen') as popen:
            res = gs.run_one(self.run, 9151, 2500, 600, self.log_dir, 'Vulkan1')
        self.assertEqual(res['status'], 'ram_floor')
        popen.assert_not_called()

    def test_port_busy_skips_launch(self):
        import socket
        blocker = socket.socket()
        blocker.bind(('127.0.0.1', 9151))
        blocker.listen(1)
        self.addCleanup(blocker.close)
        with mock.patch('scripts.gpu_sweep.subprocess.Popen') as popen:
            res = gs.run_one(self.run, 9151, 2500, 600, self.log_dir, 'Vulkan1')
        self.assertEqual(res['status'], 'port_busy')
        popen.assert_not_called()


class VerdictTests(unittest.TestCase):
    def test_best_by_picks_max(self):
        runs = [
            {'model': 'mini', 'runtime': 'default', 'status': 'ok', 'decode': {'tg_tps': 40.0}, 'pp': {'pp_tps': 100.0}},
            {'model': 'mini', 'runtime': 'b10964', 'status': 'ok', 'decode': {'tg_tps': 45.0}, 'pp': {'pp_tps': 90.0}},
            {'model': 'mini', 'runtime': 'prism', 'status': 'load_failed', 'decode': None, 'pp': None},
        ]
        self.assertEqual(gs.best_by(runs, 'tg_tps', 'decode')['runtime'], 'b10964')
        self.assertEqual(gs.best_by(runs, 'pp_tps', 'pp')['runtime'], 'default')
        self.assertIsNone(gs.best_by([], 'tg_tps', 'decode'))

    def test_fmt_contains_verdict_fields(self):
        rec = {'model': 'mini', 'runtime': 'default', 'b': 256, 'ub': 128, 'kv': 'q8_0',
               'decode': {'tg_tps': 40.0}, 'pp': {'pp_tps': 100.0}}
        s = gs.fmt(rec)
        self.assertIn('-ub 128', s)
        self.assertIn('tg 40.0', s)
        self.assertIn('pp 100.0', s)
        self.assertEqual(gs.fmt(None), 'n/a')


class GuardTests(unittest.TestCase):
    def test_gpu_busy_aborts_main(self):
        argv = ['gpu_sweep.py', '--models', 'mini']
        with mock.patch.object(gs, 'gpu_busy', return_value=True), \
             mock.patch('sys.argv', argv):
            with self.assertRaises(SystemExit):
                gs.main()

    def test_unknown_model_rejected(self):
        with mock.patch('sys.argv', ['gpu_sweep.py', '--models', 'nope']), \
             mock.patch.object(gs, 'gpu_busy', return_value=False):
            with self.assertRaises(SystemExit):
                gs.main()

    def test_gpu_busy_parses_tasklist(self):
        with mock.patch('scripts.gpu_sweep.subprocess.run') as run:
            run.return_value = mock.Mock(stdout='llama-server.exe    1234 Console')
            self.assertTrue(gs.gpu_busy())
            run.return_value = mock.Mock(stdout='INFO: No tasks are running')
            self.assertFalse(gs.gpu_busy())


if __name__ == '__main__':
    unittest.main()
