# HANDOFF — sage-rag on-device (Xperia 10 III)

## Status: WORKING ✅ (2026-06-11)

The produce RAG runs **fully on-device** on the Xperia 10 III. Verified end to end:
a `produce-rag` query embeds → retrieves 3 chunks from the 905-chunk index →
generates with the local 1.2B model. No cloud, no OpenRouter.

Example: *"What temperature should cranberries be stored at?"* →
**"Cranberries should be stored at 35–41°F (2–5°C)."** (grounded, correct)

## Access
- **Phone IP:** `192.168.1.192`
- **SSH:** `ssh defaultuser@192.168.1.192` — password `yxx95kkma`
- **RAG endpoint:** `http://192.168.1.192:11500` (or `http://localhost:11500` on-device)
- **Ollama:** `http://localhost:11434`, binary `/home/defaultuser/bin/ollama`

## On the phone
- **Models pulled (CPU):**
  - `LiquidAI/lfm2.5-1.2b-instruct:latest` — answer model (~730 MB, Q4)
  - `mxbai-embed-large:latest` — embeddings, 1024-dim (~669 MB)
- **sage-rag:** `/home/defaultuser/sage-rag` (git clone of `nigelmsipa/sage-rag`)
- **Index:** `knowledge-produce.json` — 905 chunks, mxbai-embed-large 1024-dim
- **Launcher:** `/home/defaultuser/start-sage.sh` (NOT in the repo — phone-local)

## What was wrong, and the fix (commit `80086fc`)
`server.py` was hardcoded for the GPU box: `GEN_MODEL=lfm2.5:8b` (not pulled on
the phone) and `TOP_K=10`. Two failure modes:
1. **Wrong model name** → server returned `HTTP/0.9` / empty bodies.
2. **Prefill blowup** → the phone CPU prefills at **~19 tok/s**. 10 chunks ≈ 2265
   prompt tokens ≈ **113s** just to process the prompt before the first token, so
   every query timed out. The server never crashed — it was grinding prefill.

Fix: `server.py` generation params are now **env-overridable** (GPU defaults
unchanged on `main`):

| env var            | default      | phone value                              |
|--------------------|--------------|------------------------------------------|
| `SAGE_GEN_MODEL`   | `lfm2.5:8b`  | `LiquidAI/lfm2.5-1.2b-instruct:latest`   |
| `SAGE_TOP_K`       | `10`         | `3`                                      |
| `SAGE_NUM_CTX`     | `8192`       | `2048`                                   |
| `SAGE_NUM_PREDICT` | `512`        | `320`                                    |

The phone's `start-sage.sh` exports the phone column. Result: ~55s/query,
3-chunk prompt (~1009 tok). It IS just slow — prefill-bound on the CPU. That's
the hardware ceiling, not a bug.

## How to run / restart on the phone
```sh
ssh defaultuser@192.168.1.192
sh /home/defaultuser/start-sage.sh      # starts ollama serve + server.py with phone env
tail -f /tmp/sage-rag.log               # logs
```
Test:
```sh
curl -s http://localhost:11500/api/chat -H "Content-Type: application/json" \
  -d '{"model":"produce-rag","messages":[{"role":"user","content":"What temp for cranberries?"}],"stream":false}'
```

## Point the app at it
In harbour-sage, set the server address to `http://localhost:11500` (on-device)
or `http://192.168.1.192:11500` (from another device on the LAN). `produce-rag`
appears automatically in the model list (`/api/tags`).

## TODO (next, for Windsurf)
1. **Auto-start on boot.** `start-sage.sh` is manual right now. Add a systemd
   user service or a `~/.config/autostart/` entry that runs it on login. Confirm
   ollama + server.py come up after a reboot.
2. **Speed (optional).** ~55s/query is prefill-bound. Options if it needs to be
   faster: `SAGE_TOP_K=2` (~37s, less coverage); trim `prompt-produce.txt` (the
   system prompt is re-prefilled every query); or a smaller/faster answer model.
   Generation itself is fine (~10 tok/s) — only prefill is the cost.
3. **More corpora.** `python3 ingest.py ~/corpora/<name> <name>` →
   `knowledge-<name>.json`, restart, and `<name>-rag` shows up automatically.

## Git
Repo: `https://github.com/nigelmsipa/sage-rag`. Working tree on the dev box:
`/home/nigel/sage-rag` (this is where `gh` is authed — the phone has no GitHub
credentials, so push from here, not from the phone). Latest on `main`: `80086fc`.
