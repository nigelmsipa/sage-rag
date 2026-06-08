# Sage RAG — a private, domain-specific knowledge assistant

A local **Retrieval-Augmented Generation (RAG)** service that answers questions
from a *curated domain knowledge base* instead of the open internet — running
entirely on my own hardware, served to a native phone app over a private
network. No cloud, no subscription, no data leaving my machines.

This repo is the **brains**: the retrieval + answer service, an evaluation
harness that grades it against a gold answer key, and a benchmark that pits the
curated knowledge base against generic web search.

> The phone client (a native Sailfish OS app) lives in a companion repo:
> **harbour-sage**.

---

## The problem

General-purpose chatbots are confidently wrong about specialized domains. Ask a
generic model about produce-department storage and it repeats common myths
(e.g. "shock wilted greens in *ice-cold* water" — which is exactly backwards).

I wanted an assistant that answers from a **specific, trusted body of
knowledge** — a produce department's operational reference — and is *correct on
the details that matter* (exact storage temperatures, ethylene compatibility,
food-safety protocols).

## Architecture

```
 Phone app (Sage)
    │  question
    ▼
 Sage RAG service  (this repo, :11500 — speaks the Ollama API)
    │  1. embed the question        (mxbai-embed-large, 1024-dim)
    │  2. cosine-search the corpus   (top-k relevant chunks)
    │  3. build a grounded prompt
    ▼
 Ollama (:11434)  →  gpt-oss:20b writes the answer from the provided context
    │
    ▼  streamed back to the phone, with sources cited
```

Because the service **mimics the Ollama API**, the phone app needs zero changes
to switch between plain chat and knowledge mode — it just picks a different
"model" (`produce-rag`).

## Key design decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Embedding model | `mxbai-embed-large` (1024-dim) | Stronger retrieval than smaller 768-dim models |
| Answer model | `gpt-oss:20b` | Benchmarked head-to-head vs `qwen2.5:7b`; gpt-oss was meaningfully more accurate on domain specifics (worth the slower CPU inference) |
| Vector store | a single JSON file | The corpus is small (hundreds of chunks) — a database would be over-engineering |
| Multi-corpus | one server, many `knowledge-*.json` | Each corpus is its own isolated index + its own system prompt; switch by picking the model |
| Prompts | per-corpus `prompt-*.txt` | Produce-specific reasoning (ethylene compatibility) never leaks into other domains |

## Evaluation — how I know it works

I treat a hand-written **gold Q&A answer key** as a test suite. `eval.py`:

1. asks the RAG each question,
2. has a fast judge model grade the answer **PASS / PARTIAL / FAIL** against the
   gold answer,
3. streams a scorecard and saves full detail for drill-down.

This turns "I think it's good" into a measurable score, and surfaces *patterns*
of failure rather than one-off anecdotes.

### Case study: the "needle in a dense table" fix

The first eval run exposed a clear cluster: the RAG was strong on concepts but
**unreliable on precise per-commodity numbers** — e.g. it gave the cranberry
chilling threshold as `0°C` when the corpus clearly states `2°C (35°F)`.

**Root cause:** the source docs store each category as a markdown table (one row
per commodity). The original chunker lumped a whole table into one chunk, so a
single chunk held *six commodities' worth* of temperatures — and the model
grabbed a neighbor's number.

**Fix:** a table-aware chunker that emits **one self-contained chunk per row**,
with its column labels intact:

```
9. Berries — Cranberries
CI Threshold: 2°C (35°F)        ← isolated, unambiguous
```

One structural fix targeted an entire cluster of failures at once — the value of
evaluating for *patterns*, not patching individual answers.

## Benchmark: curated corpus vs. web search

To justify the effort of building a knowledge base (vs. just bolting web search
onto an LLM), I run the **same questions** through two arms with the **same**
answer model, varying only the source of facts:

- **Arm A** — this corpus RAG
- **Arm B** — a web-search RAG (live search → top results → same model)

Same gold answer key grades both. Hypothesis: the curated corpus wins decisively
on domain specifics and myth-busting cases. *(Results: in progress.)*

## Running it

```bash
# 1. Build the knowledge base from a folder of markdown docs
python3 ingest.py ~/corpora/produce produce      # -> knowledge-produce.json

# 2. Start the service (sits in front of a local Ollama)
python3 server.py                                # -> :11500

# 3. Evaluate against a gold Q&A file
python3 eval.py all                              # full graded scorecard
python3 eval.py path/to/qa.md 10                 # quick 10-question sample
```

Adding a new domain is just: drop a corpus folder, run `ingest.py`, optionally
add a `prompt-<name>.txt`, restart — and `<name>-rag` appears in the model list.

## Tech stack

Python (standard library + numpy) · Ollama · `mxbai-embed-large` · `gpt-oss:20b`
· cosine-similarity retrieval · Tailscale (private networking to the phone)

## What this demonstrates

- Building a RAG system end-to-end and **diagnosing** its failures with a real
  eval harness, not vibes
- Making **deliberate, tested** model/architecture trade-offs
- Turning a vague "is it good?" into measurable, presentable results
