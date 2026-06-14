#!/bin/sh
# Cloud bakeoff sweep: each OpenRouter candidate through the produce RAG on :11501
# (top_k=3, num_ctx=8192). Retrieval is held constant; only the generation model
# varies. Dumps answers+timing to ~/sage-rag/bakeoff/<tag>.json for grading.
#   ./bakeoff_run_cloud.sh [sample_per_section]   (default 5)
SAMPLE="${1:-5}"
cd /home/nigel/sage-rag

# tag:openrouter-slug   (cheap/weak -> flagship)
set -- \
  "gptoss-120b:openai/gpt-oss-120b" \
  "hermes4-70b:nousresearch/hermes-4-70b" \
  "claude-haiku3:anthropic/claude-3-haiku" \
  "gpt5-nano:openai/gpt-5-nano" \
  "gemini25-flash-lite:google/gemini-2.5-flash-lite" \
  "claude-opus48:anthropic/claude-opus-4.8" \
  "gpt55-pro:openai/gpt-5.5-pro" \
  "gemini31-pro:google/gemini-3.1-pro-preview"

for entry in "$@"; do
  TAG="${entry%%:*}"
  MODEL="${entry#*:}"
  echo "============================================================"
  echo "### $TAG  ($MODEL)  sample=$SAMPLE/section"
  echo "============================================================"
  sh bakeoff_restart_or.sh "$MODEL" || { echo "restart failed for $MODEL"; continue; }
  python3 bakeoff_collect.py "$TAG" "$SAMPLE"
done
echo "#### CLOUD SWEEP COMPLETE ####"
