#!/bin/sh
# Restart the BAKEOFF sage-rag server for a specific candidate model, on a
# dedicated port (11501) so it never collides with the runit-supervised
# production server on 11500. Kills only its own previous instance via pidfile.
#   ./bakeoff_restart.sh <ollama-model-tag>
MODEL="$1"
[ -z "$MODEL" ] && echo "usage: bakeoff_restart.sh <model-tag>" && exit 1
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
export SAGE_FORCE_LOCAL=1
export SAGE_GEN_MODEL="$MODEL"
export SAGE_TOP_K=3
export SAGE_NUM_CTX=8192
export SAGE_NUM_PREDICT=${SAGE_NUM_PREDICT:-512}
nohup python3 -u /home/nigel/sage-rag/server.py >/tmp/sage-bakeoff.log 2>&1 &
echo $! > "$PIDFILE"
for i in $(seq 1 30); do
  curl -s -m 2 http://localhost:$PORT/api/tags >/dev/null 2>&1 && break
  sleep 0.5
done
echo "bakeoff server up on :$PORT (pid $(cat $PIDFILE)) GEN_MODEL=$MODEL"
grep "RAG generation" /tmp/sage-bakeoff.log | tail -1
