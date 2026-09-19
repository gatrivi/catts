# Measures endpoint load state plus 8K and 16K real-chat behavior. Server must already be running.
[CmdletBinding()]
param(
  [int]$Port = 9101,
  [ValidateRange(1, 1000)][int]$MaxTokens = 128
)

$ErrorActionPreference = 'Stop'
$base = "http://127.0.0.1:$Port"
try { $health = Invoke-RestMethod -Uri "$base/health" -TimeoutSec 10 } catch { throw "Qwen27 endpoint is not ready at $base. Start it with: npm run qwen27" }
if ($health.status -ne 'ok') { throw "Endpoint status is $($health.status), not ok." }

$outDir = 'Z:\models\coding\Qwen3.8-27B-Q3-DOWN-XS\benchmarks'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$server = Get-Process llama-server -ErrorAction SilentlyContinue | Sort-Object StartTime | Select-Object -Last 1
function Get-WorkingSetMiB {
  if (-not $server) { return $null }
  $proc = Get-Process -Id $server.Id -ErrorAction SilentlyContinue
  if (-not $proc) { return $null }
  return [math]::Round($proc.WorkingSet64 / 1MB, 1)
}
function Get-GpuLocalUsageMiB {
  if (-not $server) { return $null }
  try {
    $value = (Get-Counter '\GPU Process Memory(*)\Local Usage' -ErrorAction Stop).CounterSamples |
      Where-Object { $_.InstanceName -like "*$($server.Id)*" } |
      Measure-Object -Property CookedValue -Sum
    if ($null -ne $value.Sum) { return [math]::Round($value.Sum / 1MB, 1) }
  } catch { }
  return $null
}

$results = @()
foreach ($targetTokens in @(8192, 16384)) {
  # Repetition produces approximately the requested token load with Qwen's tokenizer while keeping the test deterministic.
  $seed = 'Review this CATTS code requirement and identify one concrete correctness risk: preserve API compatibility, avoid secret exposure, and make the smallest safe change. '
  $prompt = ($seed * [math]::Ceiling($targetTokens / 28))
  $body = @{ model = 'Qwen3.8-27B-Q3-DOWN-XS'; messages = @(@{ role = 'user'; content = $prompt }); max_tokens = $MaxTokens; temperature = 0 } | ConvertTo-Json -Depth 5
  $ramBefore = Get-WorkingSetMiB
  $vramBefore = Get-GpuLocalUsageMiB
  $watch = [Diagnostics.Stopwatch]::StartNew()
  try {
    $response = Invoke-RestMethod -Method Post -Uri "$base/v1/chat/completions" -ContentType 'application/json' -Body $body -TimeoutSec 900
    $watch.Stop()
    $usage = $response.usage
    $tokens = if ($usage.completion_tokens) { $usage.completion_tokens } else { 64 }
    $results += [pscustomobject]@{
      context_target = $targetTokens
      prompt_tokens = $usage.prompt_tokens
      completion_tokens = $tokens
      elapsed_seconds = [math]::Round($watch.Elapsed.TotalSeconds, 2)
      end_to_end_tokens_per_second = [math]::Round($tokens / $watch.Elapsed.TotalSeconds, 2)
      process_ram_mib_before = $ramBefore
      process_ram_mib_after = Get-WorkingSetMiB
      process_vram_mib_before = $vramBefore
      process_vram_mib_after = Get-GpuLocalUsageMiB
      response_preview = $response.choices[0].message.content.Substring(0, [math]::Min(200, $response.choices[0].message.content.Length))
    }
  } catch {
    $watch.Stop()
    $results += [pscustomobject]@{ context_target = $targetTokens; prompt_tokens = $null; completion_tokens = $null; elapsed_seconds = [math]::Round($watch.Elapsed.TotalSeconds, 2); end_to_end_tokens_per_second = $null; response_preview = "FAILED: $($_.Exception.Message)" }
  }
}
# Real coding review from the checked-out CATTS source: no synthetic benchmark replaces this.
$sourcePath = 'E:\zengatrivi-drive-e\catts\services\tts_runtime.py'
if (Test-Path -LiteralPath $sourcePath) {
  $source = Get-Content -LiteralPath $sourcePath -Raw
  $reviewBody = @{ model = 'Qwen3.8-27B-Q3-DOWN-XS'; messages = @(@{ role = 'system'; content = 'You are a careful coding reviewer. Be concise and cite exact code evidence.' }, @{ role = 'user'; content = "Review this real CATTS source for one correctness bug or operational risk. Propose the smallest safe fix. FILE: services/tts_runtime.py`n`n$source" }); max_tokens = $MaxTokens; temperature = 0 } | ConvertTo-Json -Depth 5
  $watch = [Diagnostics.Stopwatch]::StartNew()
  try {
    $review = Invoke-RestMethod -Method Post -Uri "$base/v1/chat/completions" -ContentType 'application/json' -Body $reviewBody -TimeoutSec 900
    $watch.Stop()
    $results += [pscustomobject]@{ context_target = 'real_repo_review'; prompt_tokens = $review.usage.prompt_tokens; completion_tokens = $review.usage.completion_tokens; elapsed_seconds = [math]::Round($watch.Elapsed.TotalSeconds, 2); end_to_end_tokens_per_second = [math]::Round($review.usage.completion_tokens / $watch.Elapsed.TotalSeconds, 2); process_ram_mib_before = $null; process_ram_mib_after = Get-WorkingSetMiB; process_vram_mib_before = $null; process_vram_mib_after = Get-GpuLocalUsageMiB; response_preview = $review.choices[0].message.content }
  } catch {
    $watch.Stop()
    $results += [pscustomobject]@{ context_target = 'real_repo_review'; prompt_tokens = $null; completion_tokens = $null; elapsed_seconds = [math]::Round($watch.Elapsed.TotalSeconds, 2); end_to_end_tokens_per_second = $null; process_ram_mib_before = $null; process_ram_mib_after = Get-WorkingSetMiB; process_vram_mib_before = $null; process_vram_mib_after = Get-GpuLocalUsageMiB; response_preview = "FAILED: $($_.Exception.Message)" }
  }
}
$path = Join-Path $outDir "benchmark-$stamp.json"
$results | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $path -Encoding utf8
$results | Format-Table -AutoSize
Write-Host "Saved $path" -ForegroundColor Green
