# Emite el device Vulkan que hay que usar: Vulkan1 si existe (rig con iGPU + dGPU),
# si no el primer device disponible (p. ej. Vulkan0 cuando la dGPU no enumera).
# Los lanzadores ya no fijan 'Vulkan1' a mano: si la dGPU deja de aparecer, llama-server
# moria con "error while handling argument --device: invalid device: Vulkan1".
param([Parameter(Mandatory = $true)][string]$Exe)
if (-not (Test-Path -LiteralPath $Exe)) { throw "Missing llama-server: $Exe" }
$output = & $Exe --list-devices 2>&1 | Out-String
$devices = @([regex]::Matches($output, 'Vulkan\d+') | ForEach-Object { $_.Value } | Select-Object -Unique)
if ($devices -contains 'Vulkan1') { 'Vulkan1' }
elseif ($devices.Count -ge 1) { $devices[0] }
else { 'Vulkan0' }
