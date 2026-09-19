# ponytail: Bonsai client only — server must already be up (npm run bonsai)
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Text)
if (-not $Text) { $Text = @(Read-Host "prompt") }
$port = if ($env:BONSAI_PORT) { $env:BONSAI_PORT } else { 9099 }
$body = @{ model = "bonsai"; messages = @(@{ role = "user"; content = ($Text -join " ") }) } | ConvertTo-Json -Compress
(Invoke-RestMethod "http://127.0.0.1:$port/v1/chat/completions" -Method POST -ContentType "application/json" -Body $body).choices[0].message.content
