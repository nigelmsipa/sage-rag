# Sage RAG — Model Bakeoff L2 (cloud sweep + closed-book)

**Date:** 2026-06-14 · **Corpus:** produce (905 chunks, mxbai-embed-large) ·
**Sample:** 5 Q/section × 13 sections = **65 Q** · **Retrieval held constant**
(top_k=3, num_ctx=8192) — only the generation model varies.
**Judge:** `google/gemini-2.5-flash` (neutral LLM judge, PASS/PARTIAL/FAIL/REFUSAL).

This extends the L1 bakeoff (8 local models). Here: 11 cloud models (+ gemma-3-12b
bonus), each run **with RAG** and **closed-book** (no retrieval). All via OpenRouter
at provider precision (note: local Q4 copies may score slightly lower).

## Scorecard (sorted by RAG strict pass-rate)

| Model | RAG % | RAG soft | Closed-book % | Δ RAG−CB | CB refusals* |
|---|---:|---:|---:|---:|---:|
| gemini-2.5-flash-lite | **93.8** | 96.2 | 21.5 | +72.3 | 4 |
| gpt-oss-120b | 92.3 | 95.4 | 33.8 | +58.5 | 3 |
| gemma-3-12b | 89.2 | 93.1 | 16.9 | +72.3 | 0 |
| qwen3.6-35b-a3b | 89.2 | 93.8 | 29.2 | +60.0 | 3 |
| gemma-4-26b-a4b | 89.2 | 93.8 | 26.2 | +63.0 | 3 |
| gpt-5-nano | 87.7 | 92.3 | 23.1 | +64.6 | 8 |
| gemini-3.1-pro | 87.7 | 92.3 | 41.5 | +46.2 | 2 |
| gemma-4-31b | 87.7 | 93.1 | 32.3 | +55.4 | 1 |
| hermes-4-70b | 86.2 | 92.3 | 24.6 | +61.6 | 8 |
| claude-3-haiku | 86.2 | 90.8 | 16.9 | +69.3 | **23** |
| claude-opus-4.8 | 84.6 | 90.8 | **47.7** | +36.9 | 8 |
| gpt-5.5-pro | **81.5** | 88.5 | 43.1 | +38.4 | 2 |

\* *CB refusals = honest "I don't know" closed-book (higher = better calibrated).*
*soft = PASS + 0.5·PARTIAL.*

## Findings

1. **With RAG, model power is irrelevant — and the pricey reasoning models are
   *worst*.** Whole field sits in an 82–94% band; the cheapest/smallest models
   lead. **gpt-5.5-pro (last, 81.5%) and claude-opus-4.8 (84.6%) sit at the
   bottom** — reasoning models over-hedge and second-guess the provided context
   (marked PARTIAL). The RAG ceiling (~94%) is set by **retrieval, not the model**
   (consistent with L1).

2. **Closed-book rewards size — but it doesn't matter.** opus-4.8 (47.7%) and
   gpt-5.5-pro (43.1%) know the most produce facts cold, yet the **worst RAG score
   (81.5%) beats the best closed-book score (47.7%) by 34 points.** RAG buys
   **+37 to +72 points**. The corpus is the whole game.

3. **Weak models gain most from RAG.** Biggest Δ: gemini-2.5-flash-lite +72.3,
   gemma-3-12b +72.3, claude-3-haiku +69.3. Smallest Δ: opus-4.8 +36.9,
   gpt-5.5-pro +38.4 — strong models already knew more, so RAG adds less.

4. **Calibration prize: claude-3-haiku** — 23 honest closed-book refusals instead
   of fabricating. **gemma-3-12b is the opposite** — 0 refusals, invents specifics
   (and is the only self-hostable with a RAG FAIL).

## Confident-wrong highlights (closed-book hallucinations the corpus fixes)

- **"International Federation for Everything (IFRA)"** manages PLU codes
  (gemma-4-26b-a4b) — gold: IFPS.
- **PAL = "Polyphenol Oxidase (PPO)"** (claude-3-haiku, gemma-4-26b-a4b) — gold:
  Phenylalanine ammonia-lyase. Recurring error.
- **Crisping water = "32–40°F cold"** (claude-3-haiku) — gold: **95–100°F warm**.
  Same backwards-myth as L1.
- Salmonella red-onion outbreak **"158 people"** (gemma-4-26b-a4b) — gold: 1,100+.
- Shiitake PLU **4692** (claude-3-haiku) — gold: 4651.
- Cilantro/parsley soak **"15–30 min"** (gemma-3-12b) — gold: 1–3 min.

## Decision: what to self-host

Three self-hostable open models **tie at 89.2% RAG**: **qwen3.6-35b-a3b,
gemma-4-26b-a4b, gemma-3-12b**. For the RX 6600 box, **gemma-4-26b-a4b** (MoE, 4B
active) is the sweet spot — top-tier accuracy at MoE speed — with
**qwen3.6-35b-a3b** essentially equal. gpt-oss-120b (92.3%) leads if going bigger,
but only +3 over the 26B. **No reason to pay for a strong cloud model.**

## Cost footnote

gpt-5.5-pro cost **~$18** across its two arms (reasoning tokens at $180/M out) —
and finished **last** on RAG. The whole rest of the sweep was ~$2.

## Repro

```sh
sh bakeoff_run_cloud.sh 5              # RAG arm (8) ; bakeoff_restart_or.sh for extras
sh bakeoff_run_cloud_closedbook.sh 5  # closed-book arm
sh grade_all.sh                       # LLM-judge all dumps -> bakeoff/grades/
```
