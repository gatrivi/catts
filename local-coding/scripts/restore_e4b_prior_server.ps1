param([Parameter(Mandatory=$true)][string]$Journal)
$ErrorActionPreference='Stop'
$spec=Get-Content -LiteralPath (Join-Path $Journal 'prior-server.json') -Raw | ConvertFrom-Json
$p=Start-Process -FilePath $spec.executable -ArgumentList $spec.argumentLine -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $Journal 'restored.stdout.log') -RedirectStandardError (Join-Path $Journal 'restored.stderr.log')
$healthy=$false
for ($i=0;$i -lt 150;$i++) {
 try { if ((Invoke-RestMethod 'http://127.0.0.1:8123/health' -TimeoutSec 2).status -eq 'ok') { $healthy=$true; break } } catch {}
 if ($p.HasExited) { break }
 Start-Sleep -Seconds 1
}
@{pid=$p.Id;healthy=$healthy} | ConvertTo-Json | Set-Content (Join-Path $Journal 'restoration.json')
if (-not $healthy) { throw "Qwen2.5 restoration failed. See $Journal" }
Write-Output "Qwen2.5 restaurado, puerto 8123, PID $($p.Id)."
