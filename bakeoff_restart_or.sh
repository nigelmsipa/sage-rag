#!/bin/sh
# Restart the BAKEOFF sage-rag server for a specific OpenRouter model, on the
# dedicated bakeoff port (11501). Unlike bakeoff_restart.sh (which forces local
# Ollama), this routes RAG generation through OpenRouter so we can score cloud
# models (gpt-oss-120b, hermes, Claude/GPT/Gemini) on the same retrieval.
# Embeddings still run locally (mxbai) — only generation goes to the cloud.
#   ./bakeoff_restart_or.sh <openrouter-model-slug>
MODEL="$1"
[ -z "$MODEL" ] && echo "usage: bakeoff_restart_or.sh <openrouter-model-slug>" && exit 1
PORT=11501
PIDFILE=/tmp/sage-bakeoff.pid

# kill only our own previous bakeoff server (never the runit one)
[ -f "$PIDFILE" ] && kill "$(cat "$PIDFILE")" 2>/dev/null
for i in $(seq 1 20); do
  (ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null) | grep -q ":$PORT " || break
  sleep 0.5
done

export OLLAMA_HOST=http://localhost:11434
export SAGE_PORT=$PORT
# NB: do NOT set SAGE_FORCE_LOCAL — that would disable OpenRouter. The key at
# ~/.config/sage/openrouter.key must exist for cloud routing.
unset SAGE_FORCE_LOCAL
export SAGE_OPENROUTER_MODEL="$MODEL"
# Ollama fallback model: deliberately unpulled so an OpenRouter failure errors
# LOUDLY (empty answer in the dump) rather than silently scoring a local model.
export SAGE_GEN_MODEL="__no_local_fallback__"
export SAGE_TOP_K=3
export SAGE_NUM_CTX=8192
export SAGE_NUM_PREDICT=${SAGE_NUM_PREDICT:-512}
nohup python3 -u /home/nigel/sage-rag/server.py >/tmp/sage-bakeoff.log 2>&1 &
echo $! > "$PIDFILE"
for i in $(seq 1 30); do
  curl -s -m 2 http://localhost:$PORT/api/tags >/dev/null 2>&1 && break
  sleep 0.5
done
echo "bakeoff server up on :$PORT (pid $(cat $PIDFILE)) OPENROUTER_MODEL=$MODEL"
grep "RAG generation" /tmp/sage-bakeoff.log | tail -1
