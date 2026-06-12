# Tasks — handoff between machines

## Request from the GPU box (RX 6600 / lynx) — need the produce corpus

**Context:** I've set up this repo to run on the GPU box. Findings:

- Answer model chosen: **`lfm2.5:8b`** (LiquidAI LFM2.5-8B-A1B, Q4) — benchmarked
  at **~116 tok/s** on the RX 6600, 5.3GB VRAM, 100% GPU. Far faster than
  qwen2.5:7b (40) and gemma4:e2b (74), with 8B-class quality (~1B active).
  Plan: set `GEN_MODEL = "lfm2.5:8b"` in `server.py`.
- `mxbai-embed-large` is being pulled here (needed to embed live queries).
- `lfm2.5:8b` + `mxbai-embed-large` ≈ 6.5GB, both fit resident in 8GB at once.
  GPU does embedding + generation; CPU does the (trivial) cosine search.

**The blocker:** this box has `server.py`, `ingest.py`, `prompt-produce.txt`,
but **no corpus** — and `.gitignore` excludes both `knowledge-*.json` (the built
index) and `corpora/` (the private source docs). So I can't run RAG here yet.

**What I need from you (the Void box, where the corpus lives) — pick one:**

### Option A (fastest — just the prebuilt index)
Force-add the built index past the gitignore and push. It's a few MB of vectors;
fine for git. The source docs stay private.

```bash
cd ~/sage-rag
git add -f knowledge-produce.json
git commit -m "Add prebuilt produce index for GPU box"
git push
```

Then I pull, start `server.py`, and `produce-rag` works immediately — no
re-ingest. **Confirm the index was built with `mxbai-embed-large` (1024-dim)** so
it matches the embedder I'm loading here. (server.py reads the embed model from
the JSON, so as long as that field says `mxbai-embed-large` we're aligned.)

### Option B (if you'd rather I rebuild here)
Force-add the source produce markdown docs (or tell me how to fetch them), and
confirm `ingest.py`'s settings. I'll run `ingest.py` here to build the index
fresh on the GPU. Only do this if you don't want the prebuilt JSON in git.

```bash
cd ~/sage-rag
git add -f corpora/produce        # or wherever the source docs live
git commit -m "Add produce source docs for GPU box to ingest"
git push
```

**Default ask: Option A.** One file, I'm live in minutes. Ping me here (this file)
once it's pushed.
