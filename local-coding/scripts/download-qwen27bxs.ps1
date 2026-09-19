# Downloads the exact Q3-DOWN-XS GGUF directly to Z: and resumes an interrupted transfer.
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repo = 'guideboardlabs/Qwen3.8-27B-Q3-DOWN-XS-GGUF'
$file = 'Qwen3.8-27B-Q3-DOWN-XS.gguf'
$dir = 'Z:\models\coding\Qwen3.8-27B-Q3-DOWN-XS'
$destination = Join-Path $dir $file
$expectedBytes = 8491269152
$expectedSha256 = 'f1e75d0145ee32c3f216b336c2efa4ac8b2ff9249449159b1414187f966cc9cd'

New-Item -ItemType Directory -Force -Path $dir | Out-Null
if ((Test-Path -LiteralPath $destination) -and ((Get-Item -LiteralPath $destination).Length -eq $expectedBytes)) {
  $existingHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $destination).Hash.ToLowerInvariant()
  if ($existingHash -eq $expectedSha256) {
    Write-Host "Verified model already present: $destination" -ForegroundColor Green
    exit 0
  }
  throw "Existing completed-size file fails the expected SHA-256. Rename or remove it before retrying."
}

Write-Host "Downloading $repo/$file to Z: (resume-safe)..." -ForegroundColor Cyan
# Xet transfer is resumable; both cache and output remain on Z:.
$env:HF_HOME = 'Z:\models\.hf-home'
$env:HF_XET_CACHE = 'Z:\models\.hf-xet-cache'
$env:HF_XET_HIGH_PERFORMANCE = '1'
& hf download $repo $file --local-dir $dir --max-workers 16
if ($LASTEXITCODE -ne 0) { throw "Hugging Face download failed (exit $LASTEXITCODE). Re-run this command to resume." }

$size = (Get-Item -LiteralPath $destination).Length
if ($size -ne $expectedBytes) { throw "Downloaded file has $size bytes; expected $expectedBytes. Re-run to resume." }
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $destination).Hash.ToLowerInvariant()
if ($hash -ne $expectedSha256) { throw "SHA-256 mismatch: $hash" }
Write-Host ("Download complete and verified: {0:N2} GiB" -f ($size / 1GB)) -ForegroundColor Green
