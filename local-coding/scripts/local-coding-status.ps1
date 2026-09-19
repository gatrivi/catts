$ErrorActionPreference = "Stop"
foreach ($target in @(
  @{ Name = "Bonsai-2 27B TQ2"; Port = 9103 },
  @{ Name = "Qwen3.8 27B (taller consultor)"; Port = 9101 },
  @{ Name = "Qwen3.5 9B (taller editor)"; Port = 9102 },
  @{ Name = "NeoHorse 4B"; Port = 9107 },
  @{ Name = "Spark-X2.5 4B"; Port = 9105 },
  @{ Name = "Smol (cualquier modelo)"; Port = 9104 },
  @{ Name = "Bonsai 4B (legacy)"; Port = 9099 },
  @{ Name = "Qwen2.5 Coder 7B (legacy)"; Port = 9100 }
)) {
  $listener = Get-NetTCPConnection -LocalPort $target.Port -State Listen -ErrorAction SilentlyContinue
  $status = if (-not $listener) {
    "down"
  } else {
    try { (Invoke-RestMethod -Uri "http://127.0.0.1:$($target.Port)/health" -TimeoutSec 3).status } catch { "loading" }
  }
  "{0} (: {1}) {2}" -f $target.Name, $target.Port, $status
}

