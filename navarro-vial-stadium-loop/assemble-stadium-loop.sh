#!/usr/bin/env bash
# Assemble navarro-vial-stadium-loop from frames + sequence.json
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

FORWARD="${FORWARD_SEC:-6}"
REVERSE="${REVERSE_SEC:-6}"
TOTAL=$((FORWARD + REVERSE))
FRAMES=(
  frame-01-terreno.png
  frame-02-nivelacion.png
  frame-03-fundaciones.png
  frame-04-gradas-bajas.png
  frame-05-estructura.png
  frame-06-techo.png
  frame-07-finales.png
  frame-08-estadio.png
)
ORDER=(1 2 3 4 5 6 7 8 7 6 5 4 3 2 1)
COUNT=${#ORDER[@]}
DUR=$(awk "BEGIN {printf \"%.4f\", $TOTAL / $COUNT}")

CONCAT="$DIR/_concat.txt"
rm -f "$CONCAT"
for idx in "${ORDER[@]}"; do
  f="${FRAMES[$((idx - 1))]}"
  echo "file '$f'" >> "$CONCAT"
  echo "duration $DUR" >> "$CONCAT"
done
# concat demuxer requires last file repeated without duration
echo "file '${FRAMES[7]}'" >> "$CONCAT"

OUT_DIR="${OUT_DIR:-$DIR/export}"
mkdir -p "$OUT_DIR"

MASTER="$OUT_DIR/hero-navarro-vial-stadium-loop.mp4"
WEB="$OUT_DIR/hero-navarro-vial-stadium-loop-web.mp4"

VF="scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p"

ffmpeg -y -f concat -safe 0 -i "$CONCAT" \
  -vf "$VF" -an -r 30 \
  -c:v libx264 -pix_fmt yuv420p -crf 18 -preset medium \
  "$MASTER"

# ~6 Mbps target for web (~9MB @12s); tune with WEB_CRF
WEB_CRF="${WEB_CRF:-23}"
ffmpeg -y -f concat -safe 0 -i "$CONCAT" \
  -vf "$VF" -an -r 30 \
  -c:v libx264 -pix_fmt yuv420p -crf "$WEB_CRF" -preset medium \
  -maxrate 6M -bufsize 12M \
  "$WEB"

rm -f "$CONCAT"
echo "Master: $MASTER"
echo "Web:    $WEB"
ls -lh "$MASTER" "$WEB"
