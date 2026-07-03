#!/usr/bin/env bash
# Optional: start SGLang Unlimited-OCR before worker (GPU host).
set -euo pipefail
if [ "${START_SGLANG:-0}" = "1" ]; then
  python3 -m sglang.launch_server \
    --model baidu/Unlimited-OCR \
    --served-model-name Unlimited-OCR \
    --attention-backend fa3 \
    --page-size 1 \
    --mem-fraction-static 0.8 \
    --context-length 32768 \
    --enable-custom-logit-processor \
    --disable-overlap-schedule \
    --skip-server-warmup \
    --host 0.0.0.0 \
    --port 10000 &
fi
exec python3 -m worker.main
