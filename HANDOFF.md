# Handoff — sage-rag on-device (Xperia 10 III)

## Goal
Get `produce-rag` working fully on-device on the Xperia 10 III Sailfish phone
via the local sage-rag server, so harbour-sage can query it at `http://192.168.1.192:11500`.

## Current state
Everything is installed and partially working:

- **Phone IP:** `192.168.1.192`
- **SSH:** `ssh defaultuser@192.168.1.192` password: `yxx95kkma`
- **Ollama binary:** `/home/defaultuser/bin/ollama`
- **Ollama models pulled:**
  - `LiquidAI/lfm2.5-1.2b-instruct:latest` (the answer model, 697MB Q4)
  - `mxbai-embed-large` (the embedding model, 669MB)
- **sage-rag cloned:** `/home/defaultuser/sage-rag`
- **Produce index:** `/home/defaultuser/sage-rag/knowledge-produce.json` (905 chunks, mxbai-embed-large 1024-dim)
- **startup script:** `/home/defaultuser/start-sage.sh`

## The problem
`server.py` starts (PID visible) but returns `HTTP/0.9` responses to chat requests,
meaning it crashes before sending proper HTTP headers. The log at `/tmp/sage-rag.log`
is empty — stdout/stderr not captured.

### Steps to diagnose
1. SSH into phone
2. Kill anything on port 11500: `fuser -k 11500/tcp`
3. Start server in foreground to see actual error:
```bash
OLLAMA_HOST=http://localhost:11434 python3 -u /home/defaultuser/sage-rag/server.py
```
4. In another terminal, send a test query:
```bash
curl -s http://localhost:11500/api/chat \
  -H "Content-Type: application/json" \
  -d '{"model":"produce-rag","messages":[{"role":"user","content":"What temp for cranberries?"}],"stream":false}'
```
5. Read the traceback in the first terminal.

## Likely culprits
- **GEN_MODEL mismatch:** `server.py` has `GEN_MODEL = "lfm2.5:8b"` but the phone
  only has `LiquidAI/lfm2.5-1.2b-instruct:latest`. The model name needs to match
  exactly what `ollama list` shows. Fix in `server.py`:
  ```python
  GEN_MODEL = "LiquidAI/lfm2.5-1.2b-instruct:latest"
  ```
- **embed endpoint:** Already fixed (`/api/embed` with `input` key) — this was the
  previous bug, should be fine now.

## Fix and push
After diagnosing, fix `server.py`, commit, push to `nigelmsipa/sage-rag`, done.

## Once working
Point harbour-sage server address at `http://localhost:11500` (or `http://192.168.1.192:11500`
from the phone's own browser) and it should work fully offline.

## Auto-start on boot (after it's working)
Create a systemd user service or add to `/home/defaultuser/.config/autostart/`.
