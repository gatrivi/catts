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
        patch('builtins.input',side_effect=['',str(root),'0']),patch.object(smol,'run') as run:
    smol.main()
   self.assertEqual(run.call_args.args[:4],('mini','project',root.resolve(),False))

 def test_explicit_chat_still_opens_without_project_prompt(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   with patch.object(smol,'DATA',root/'smol'),patch.object(smol,'RUNTIME',Path(__file__)), \
        patch.object(smol,'OMP',Path(__file__)),patch.object(sys,'argv',['smol','--model','mini','--mode','chat']), \
        patch('builtins.input',side_effect=AssertionError('Unexpected prompt')),patch.object(smol,'run') as run:
    smol.main()
   self.assertEqual(run.call_args.args[:2],('mini','chat'))

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
