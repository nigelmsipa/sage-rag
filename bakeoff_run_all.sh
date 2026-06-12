#!/bin/sh
# L1 bakeoff sweep: each candidate model, smallest -> biggest, through the produce
# RAG on :11501 (forced local, top_k=3, num_ctx=8192). Dumps answers+timing to
# ~/sage-rag/bakeoff/<tag>.json for Claude to grade. Retrieval is held constant;
# only GEN_MODEL varies.
#   ./bakeoff_run_all.sh [sample_per_section]   (default 5)
SAMPLE="${1:-5}"
cd /home/nigel/sage-rag

# tag:ollama-model   (smallest -> biggest by disk footprint)
set -- \
  "lfm-instruct:LiquidAI/lfm2.5-1.2b-instruct:latest" \
  "lfm-thinking:lfm2.5-thinking:latest" \
  "gemma2b:gemma:2b" \
  "llama3.2-3b:llama3.2:latest" \
  "qwen2.5-7b:qwen2.5:7b" \
  "gemma4-e2b:gemma4:e2b" \
  "gemma4-e4b:gemma4:e4b" \
  "gptoss-20b:gpt-oss:20b"

for entry in "$@"; do
  TAG="${entry%%:*}"
  MODEL="${entry#*:}"
  echo "============================================================"
  echo "### $TAG  ($MODEL)  sample=$SAMPLE/section"
  echo "============================================================"
  sh bakeoff_restart.sh "$MODEL" || { echo "restart failed for $MODEL"; continue; }
  python3 bakeoff_collect.py "$TAG" "$SAMPLE"
done
echo "#### SWEEP COMPLETE ####"
