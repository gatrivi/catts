#!/usr/bin/env bash
# GPT-SoVITS fine-tune wrapper for CATTS worker.
set -euo pipefail
VOICE_ID="${1:?voice_id}"
SAMPLE="${2:?sample_path}"
OUT_DIR="${WORKER_VOICES_DIR:-/data/voices}/${VOICE_ID}"
mkdir -p "$OUT_DIR"
cp "$SAMPLE" "$OUT_DIR/reference.wav"
# Full training: integrate GPT-SoVITS WebUI scripts (slice, ASR, train GPT + SoVITS).
# Placeholder copies reference for inference until training hooks are wired.
echo "Training placeholder complete for $VOICE_ID"
