#!/usr/bin/env bash
# usage: serve.sh <e2b|e4b> <port> <reasoning_budget> <repeat_penalty> [log_verbosity]
# Flags copied from ~/run_goose.sh (-np 1, flash-attn, q8_0 KV cache, temp/top-p/top-k, repeat penalty, jinja, reasoning budget)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HERE/.run"
M=$1; PORT=$2; BUDGET=$3; RP=$4; LV=${5:-3}
case $M in
  e2b) MODEL=~/models/gemma_2/gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf; MMPROJ=~/models/gemma_2/mmproj-F16.gguf;;
  e4b) MODEL=~/models/gemma_4/gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf; MMPROJ=~/models/gemma_4/mmproj-F16.gguf;;
esac
LOG="$HERE/.run/server_${M}_${PORT}.log"
nohup llama serve -m "$MODEL" --mmproj "$MMPROJ" --host 127.0.0.1 --port "$PORT" -ngl 99 -c 16384 -np 1 -fa on \
  --cache-type-k q8_0 --cache-type-v q8_0 --temp 0.6 --top-p 0.95 --top-k 20 --repeat-penalty "$RP" --repeat-last-n 256 \
  -lv "$LV" --reasoning-budget "$BUDGET" --jinja --api-key critic-test-key --no-webui ${EXTRA_ARGS:-} > "$LOG" 2>&1 &
echo $! > "$HERE/.run/server_${PORT}.pid"
for i in $(seq 1 90); do
  if curl -s -H "Authorization: Bearer critic-test-key" "http://127.0.0.1:$PORT/health" | grep -q ok; then echo "ready ($M budget=$BUDGET rp=$RP) after $((i))s"; exit 0; fi
  sleep 1
done
echo "FAILED to start"; tail -20 "$LOG"; exit 1
