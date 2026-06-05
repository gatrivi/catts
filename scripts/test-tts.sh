#!/usr/bin/env bash
# Smoke test: cold + warm latency for EN and ES (~20 words each).
set -euo pipefail

BASE_URL="${TTS_URL:-http://127.0.0.1:59125}"
OUT_DIR="${OUT_DIR:-/tmp/catts-tts-test}"
mkdir -p "$OUT_DIR"

EN_TEXT="The patient reports mild chest discomfort that started about two hours ago after lunch."
ES_TEXT="El paciente refiere molestia leve en el pecho que comenzó hace dos horas después del almuerzo."

echo "=== Health ==="
curl -sS "$BASE_URL/health" | python3 -m json.tool
echo

run_tts() {
  local lang="$1"
  local text="$2"
  local label="$3"
  local outfile="$OUT_DIR/${lang}-${label}.wav"

  echo "--- $lang ($label) ---"
  local start end elapsed http_code
  start=$(date +%s%3N)
  payload=$(python3 -c "import json,sys; print(json.dumps({'text': sys.argv[1], 'lang': sys.argv[2]}))" "$text" "$lang")
  http_code=$(curl -sS -o "$outfile" -w "%{http_code}" \
    -H "Content-Type: application/json" \
    -d "$payload" \
    "$BASE_URL/tts")
  end=$(date +%s%3N)
  elapsed=$((end - start))

  if [[ "$http_code" != "200" ]]; then
    echo "FAIL: HTTP $http_code"
    exit 1
  fi

  local bytes
  bytes=$(wc -c < "$outfile")
  echo "OK: ${bytes} bytes, wall ${elapsed}ms -> $outfile"
  file "$outfile" || true
  echo
}

# Restart server between cold/warm if you want true cold-start numbers.
run_tts en "$EN_TEXT" warm1
run_tts en "$EN_TEXT" warm2
run_tts es "$ES_TEXT" warm1
run_tts es "$ES_TEXT" warm2

echo "WAV files in $OUT_DIR"
echo "Play: ffplay -nodisp -autoexit $OUT_DIR/en-warm2.wav"
