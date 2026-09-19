import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import smol

class SmolTests(unittest.TestCase):
 def test_enter_opens_mini_project_with_folder_prompt(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   with patch.object(smol,'DATA',root/'smol'),patch.object(smol,'RUNTIME',Path(__file__)), \
        patch.object(smol,'OMP',Path(__file__)),patch.object(sys,'argv',['smol']), \
        patch.object(smol,'handle_foreign'), \
        patch('builtins.input',side_effect=['',str(root),'0']),patch.object(smol,'run') as run:
    smol.main()
   self.assertEqual(run.call_args.args[:4],('mini','project',root.resolve(),False))

 def test_explicit_chat_still_opens_without_project_prompt(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   with patch.object(smol,'DATA',root/'smol'),patch.object(smol,'RUNTIME',Path(__file__)), \
        patch.object(smol,'OMP',Path(__file__)),patch.object(sys,'argv',['smol','--model','mini','--mode','chat']), \
        patch.object(smol,'handle_foreign'), \
        patch('builtins.input',side_effect=AssertionError('Unexpected prompt')),patch.object(smol,'run') as run:
    smol.main()
   self.assertEqual(run.call_args.args[:2],('mini','chat'))

 def test_main_gates_foreign_servers_before_menu(self):
  with tempfile.TemporaryDirectory() as tmp, \
       patch.object(smol,'DATA',Path(tmp)),patch.object(smol,'RUNTIME',Path(__file__)), \
       patch.object(smol,'OMP',Path(__file__)),patch.object(sys,'argv',['smol']), \
       patch('builtins.input',side_effect=['0']),patch.object(smol,'handle_foreign') as gate:
   smol.main()
  self.assertEqual(gate.call_count,1)

 def test_chat_has_no_tools_or_trial_deadline(self):
  args=smol.agent_args('mini',Path('C:/example'),'chat',False)
  self.assertIn('--no-tools',args)
  self.assertNotIn('--max-time',args)
  self.assertNotIn('--auto-approve',args)

 def test_project_tools_require_write_approval(self):
  args=smol.agent_args('mini',Path('C:/project with spaces'),'project',False,True)
  self.assertEqual(args[args.index('--approval-mode')+1],'always-ask')
  self.assertIn('bash',args[args.index('--tools')+1].split(','))
  self.assertIn('--continue',args)
  self.assertIn('C:\\project with spaces',args)
  self.assertNotIn('--auto-approve',args)

 def test_profile_preserves_sessions_and_reasoning(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(smol,'DATA',Path(tmp)):
   p=smol.profile('nanbeige',True)
   (p/'sessions').mkdir();(p/'sessions/keep').write_text('saved')
   (p/'config.yml').write_text('user settings')
   smol.profile('nanbeige',False)
   self.assertEqual((p/'sessions/keep').read_text(),'saved')
   self.assertEqual((p/'config.yml').read_text(),'user settings')
   cfg=json.loads((p/'models.yml').read_text())['providers']['smol']
   self.assertEqual(cfg['compat']['extraBody']['max_tokens'],-1)
   self.assertTrue(cfg['compat']['extraBody']['chat_template_kwargs']['preserve_thinking'])
   self.assertFalse(cfg['compat']['extraBody']['chat_template_kwargs']['enable_thinking'])

 def test_unknown_server_is_not_stopped(self):
  class Process:
   info={'name':'llama-server.exe','exe':'C:/other/llama-server.exe','cmdline':['other'],'pid':123}
  with patch.object(smol.psutil,'process_iter',return_value=[Process()]):
   with self.assertRaises(RuntimeError):smol.find_prior()

 def test_unreadable_cmdline_residue_is_ignored_when_ports_free(self):
  class Process:
   info={'name':'llama-server.exe','exe':'Z:/models/runtime/llama-vulkan/llama-server.exe','cmdline':None,'pid':7824}
  with patch.object(smol.psutil,'process_iter',return_value=[Process()]):
   self.assertIsNone(smol.find_prior())

 def test_handle_foreign_stops_and_logs(self):
  foreign={'pid':555,'port':9103,'key':'bonsai2','model':'Z:/models/bonsai2.gguf','cmdline':['x','--port','9103']}
  with tempfile.TemporaryDirectory() as tmp, \
       patch.object(smol,'DATA',Path(tmp)), \
       patch('hub.find_servers',return_value=[foreign]) as find, \
       patch('hub.stop_pid',return_value='detenido') as stop_pid, \
       patch('builtins.input',return_value='1'):
   smol.handle_foreign()
   find.assert_called_once()
   stop_pid.assert_called_once_with(555,expect_model=True)
   log=(Path(tmp)/'stopped-foreign.log').read_text(encoding='utf-8')
   self.assertIn('pid=555',log); self.assertIn('9103',log)

 def test_handle_foreign_cancel_exits_without_stopping(self):
  foreign={'pid':555,'port':9103,'key':None,'model':'Z:/models/bonsai2.gguf','cmdline':['x','--port','9103']}
  with tempfile.TemporaryDirectory() as tmp, \
       patch.object(smol,'DATA',Path(tmp)), \
       patch('hub.find_servers',return_value=[foreign]), \
       patch('hub.stop_pid',side_effect=AssertionError('must not stop')), \
       patch('builtins.input',return_value='2'):
   with self.assertRaises(SystemExit): smol.handle_foreign()

 def test_handle_foreign_ignores_qwen_prior_and_residue(self):
  qwen={'pid':100,'port':8123,'key':None,'model':'Z:/m/qwen2.5-coder-7b-instruct-q4_k_m.gguf',
        'cmdline':['x','--port','8123','Z:/m/qwen2.5-coder-7b-instruct-q4_k_m.gguf']}
  residue={'pid':200,'port':None,'key':None,'model':None,'cmdline':[]}
  with patch.object(smol,'DATA',Path(tempfile.gettempdir())), \
       patch('hub.find_servers',return_value=[qwen,residue]), \
       patch('builtins.input',side_effect=AssertionError('Unexpected prompt')):
   smol.handle_foreign()

 @unittest.skipUnless(sys.platform=='win32','Windows job objects')
 def test_job_closure_stops_owned_child(self):
  job=smol.RuntimeJob()
  child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],creationflags=subprocess.CREATE_NO_WINDOW)
  try:
   job.assign(child)
   job.close()
   child.wait(timeout=5)
   self.assertIsNotNone(child.returncode)
  finally:
   smol.stop(child);job.close()

if __name__=='__main__':unittest.main()
