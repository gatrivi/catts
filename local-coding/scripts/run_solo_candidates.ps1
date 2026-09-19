$ErrorActionPreference='Stop'
$root='Z:/catts/local-coding'
$python='E:/zengatrivi-drive-e/catts/.venv/Scripts/python.exe'
$eval=Join-Path $root 'scripts/eval_local_candidate.py'
$journal=Join-Path $root ('data/solo-sequence-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $journal | Out-Null
$existing=Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" | Where-Object { $_.CommandLine -like '*--port 8123*' }
if (@($existing).Count -ne 1 -or $existing.CommandLine -notlike '*qwen2.5-coder-7b-instruct-q4_k_m.gguf*') { throw 'Existing server changed; inspect before stopping' }
$existing | Select-Object ProcessId,ExecutablePath,CommandLine | ConvertTo-Json | Set-Content (Join-Path $journal 'prior-server.json')
$restoreArgs=@('-m','Z:/ai/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf','-ngl','99','-c','32768','--flash-attn','on','--cache-type-k','q8_0','--cache-type-v','q8_0','--device','Vulkan1','--host','127.0.0.1','--port','8123','--jinja')
$stopped=$false
try {
 Stop-Process -Id $existing.ProcessId
 $stopped=$true
 Start-Sleep -Seconds 3
 Write-Output 'Qwen2.5 paused. Starting solo trials.'
 & $python $eval --model "$root/data/models/gemma4-coder-q3/gemma4-coding-Q3_K_M.gguf" --label gemma12-solo
 & $python $eval --model "$root/data/models/bonsai27-q1/Bonsai-27B-Q1_0.gguf" --label bonsai27-solo
 & $python $eval --model "$root/data/models/gemma-e4b-qat/gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf" --label e4b-solo
 & $python $eval --model "$root/data/models/gemma-e4b-qat/gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf" --label e4b-mtp-solo --draft "$root/data/models/gemma-e4b-qat/mtp-gemma-4-E4B-it.gguf" --smoke-only
} finally {
 if ($stopped) {
  $restored=Start-Process -FilePath $existing.ExecutablePath -ArgumentList $restoreArgs -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $journal 'restored.stdout.log') -RedirectStandardError (Join-Path $journal 'restored.stderr.log')
  $restored.Id | Set-Content (Join-Path $journal 'restored.pid')
  $healthy=$false
  for ($i=0;$i -lt 90;$i++) {
   try { $health=Invoke-RestMethod 'http://127.0.0.1:8123/health' -TimeoutSec 2; if ($health.status -eq 'ok') {$healthy=$true;break} } catch {}
   Start-Sleep -Seconds 1
  }
  @{restored_pid=$restored.Id;healthy=$healthy} | ConvertTo-Json | Set-Content (Join-Path $journal 'restoration.json')
  Write-Output "Qwen2.5 restored: healthy=$healthy; journal=$journal"
 }
}
