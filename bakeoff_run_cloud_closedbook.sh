#!/bin/sh
# Closed-book (no-RAG) cloud sweep: same 8 OpenRouter models as the RAG arm,
# answered from parametric knowledge only (direct to OpenRouter, no retrieval).
# The gap vs the RAG dump is what the produce corpus buys for each model.
#   ./bakeoff_run_cloud_closedbook.sh [sample_per_section]   (default 5)
SAMPLE="${1:-5}"
cd /home/nigel/sage-rag

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
  echo "### closed-book: $TAG  ($MODEL)  sample=$SAMPLE/section"
  echo "============================================================"
  python3 bakeoff_collect_closedbook_or.py "$MODEL" "$TAG" "$SAMPLE"
done
echo "#### CLOUD CLOSED-BOOK SWEEP COMPLETE ####"
