# Assemble navarro-vial-stadium-loop (Windows) — requires ffmpeg in PATH
$ErrorActionPreference = "Stop"
$Dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Dir

$Forward = if ($env:FORWARD_SEC) { [double]$env:FORWARD_SEC } else { 6 }
$Reverse = if ($env:REVERSE_SEC) { [double]$env:REVERSE_SEC } else { 6 }
$Total = $Forward + $Reverse

$Frames = @(
  "frame-01-terreno.png",
  "frame-02-nivelacion.png",
  "frame-03-fundaciones.png",
  "frame-04-gradas-bajas.png",
  "frame-05-estructura.png",
  "frame-06-techo.png",
  "frame-07-finales.png",
  "frame-08-estadio.png"
)
$Order = @(1,2,3,4,5,6,7,8,7,6,5,4,3,2,1)
$Dur = "{0:N4}" -f ($Total / $Order.Count)

$Concat = Join-Path $Dir "_concat.txt"
Remove-Item $Concat -ErrorAction SilentlyContinue
foreach ($idx in $Order) {
  $f = $Frames[$idx - 1]
  Add-Content $Concat "file '$f'"
  Add-Content $Concat "duration $Dur"
}
Add-Content $Concat "file '$($Frames[7])'"

$OutDir = if ($env:OUT_DIR) { $env:OUT_DIR } else { Join-Path $Dir "export" }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$Master = Join-Path $OutDir "hero-navarro-vial-stadium-loop.mp4"
$Web = Join-Path $OutDir "hero-navarro-vial-stadium-loop-web.mp4"
$VF = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p"

ffmpeg -y -f concat -safe 0 -i $Concat -vf $VF -an -r 30 `
  -c:v libx264 -pix_fmt yuv420p -crf 18 -preset medium $Master

$WebCrf = if ($env:WEB_CRF) { $env:WEB_CRF } else { "23" }
ffmpeg -y -f concat -safe 0 -i $Concat -vf $VF -an -r 30 `
  -c:v libx264 -pix_fmt yuv420p -crf $WebCrf -preset medium -maxrate 6M -bufsize 12M $Web

Remove-Item $Concat -ErrorAction SilentlyContinue
Get-Item $Master, $Web | Format-Table Name, Length
