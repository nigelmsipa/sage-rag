# Benchmark methodology — 8GB-class model RAG ablation

Distilled from a deep-research pass. This is the spec the harness must implement
so the published numbers hold up. **Read before building the runner.**

## Why a specialized benchmark
Mainstream RAG benchmarks (RGB, CRAG, FreshQA, RAGTruth) target 70B+ cloud models
over Wikipedia. Nothing rigorously measures **8GB-VRAM-class models (1B–9B) on a
single specialized corpus**, where parametric memory is a *liability* (the model
must stick to local context, not hallucinate generic knowledge). That gap is the
contribution.

## 1. Ablation arms — expand 4 → **7**
| # | Arm | Purpose |
|---|---|---|
| 1 | Closed-book (zero-shot) | baseline capacity; detect contamination |
| 2 | Closed-book + CoT | isolate reasoning from raw recall |
| 3 | Curated corpus RAG | the standard local pipeline |
| 4 | Web RAG (**cached**) | synthesis over noisy external text |
| 5 | Curated + Web | reconcile conflicting / multi-hop |
| 6 | **Gold-context oracle** | upper bound — perfect chunk, bypass retriever. Failure here = reasoning/instruction deficit, NOT retrieval |
| 7 | **Distractor / counterfactual** | lower bound — similar-but-wrong context. Does the model refuse or hallucinate? |

## 2. Kill the confounds
- **Force uniform `num_ctx`** (e.g. 8192) for *every* model via API param or a temp
  Modelfile (`PARAMETER num_ctx 8192`). Ollama otherwise sizes context to VRAM and
  silently handicaps the bigger model → voids the comparison.
- **Model-specific chat templates.** Don't trust Ollama defaults — Qwen uses
  `<|im_start|>`, Llama uses `[INST]`/`<<SYS>>`. Use raw Jinja templates or strict
  API message arrays so the system prompt's semantic density is identical across
  models. Small models are disproportionately hurt by bad formatting.
- Record **exact quant** per model (Q4_K_M, Q6_K, …). "llama3.2:1b" alone is not
  reproducible — Q2 vs Q6 changes reasoning and context-override resistance.

## 3. Metrics — decouple retrieval from generation (use RAGAS / DeepEval)
Ternary PASS/PARTIAL/FAIL conflates IR failure with generation failure. Report both:

**Retrieval (judge the retriever, before the LLM):**
- Context Recall — are the gold answer's claims present in retrieved chunks?
- Context Precision@k — signal/noise + ranking quality (rank-1 weighted)
- MRR — rank of first relevant chunk

**Generation (judge the answer vs the provided context):**
- **Faithfulness** = supported claims / total claims (hallucination rate vs context)
- Answer Relevance (RAGAS reverse-question cosine method)
- Citation accuracy (flag confident citations to unsupported chunks)
- **Refusal / abstention rate** — measured on the distractor arm (good calibration
  = refuse rather than hallucinate)

## 4. LLM-as-judge rigor (gpt-oss:20b on the 64GB box)
- Force judge **CoT + strict JSON output** (Pydantic schema). Log invalid-JSON /
  "cannot assess" abstentions — abstention drift signals prompt instability.
- Mitigate biases: **style/verbosity** (strip markdown, judge on claim density,
  not length), **position** (swap order, run twice, disagreement = tie),
  **self-preference** (judge from a *different* family than candidates — the 20B
  OSS judge is distinct from Llama/Qwen/Gemma/Liquid candidates ✓).
- **Validate against humans** on a random N=100 sample. Report **Gwet's AC1**, NOT
  Cohen's κ — at high agreement / skewed marginals (e.g. 85% pass) κ collapses to
  ~0 (the "kappa paradox"). AC1 is paradox-resistant.

## 5. Statistics — don't publish naive percentages
- **Gold set must be ≥ ~200 Q&A.** To detect a 10% accuracy gap (paired, ~25%
  discordance, 80% power, α=.05) needs **N ≈ 194**. Under 100 → underpowered, only
  catches >20% gaps. **This is the key input we need from the corpus owner.**
- Paired comparisons → **McNemar's test** (not t-test/chi-square; same questions =
  paired data; test the discordant pairs).
- **N=3 runs per prompt/model/arm**, `temperature 0.1–0.2` + fixed seed. Report
  **mean + 95% CI via bootstrap** (1000 resamples).
- Many comparisons (5 models × 7 arms) inflate false positives → correct with
  **Holm-Bonferroni** or **Benjamini-Hochberg FDR** (plain Bonferroni kills power).

## 6. Web arm reproducibility
Live DuckDuckGo drifts → fatal confound. **Snapshot once** at init: run queries,
extract chunks, freeze to an immutable JSON cache. Eval runs **mock the call** and
serve frozen chunks so every model sees identical web text and others can reproduce.

## 7. Contamination check
If the produce manual leaked into a model's pretraining, closed-book scores are
inflated (memorization masquerading as reasoning). Run **CoDeC** (Contamination
Detection via Context): uncontaminated data gains confidence from few-shot
examples; memorized data *loses* confidence when its exact sequences are injected.
Flag any candidate with prior exposure.

## 8. Efficiency frontier (the point of edge-class)
Report a Pareto frontier, not just accuracy: **TTFT** (prefill cost of the RAG
context), **inter-token latency**, **throughput tok/s**, **peak VRAM**, **energy
(tokens/Joule)**. **Track and penalize CPU offload** — if the RAG context grows
the KV-cache past 8GB, llama.cpp/Ollama silently pages to RAM → >90% throughput
collapse. Flag models that breach the VRAM wall.

## 9. "Lost in the middle"
Small quantized models degrade U-shaped: good at prompt start/end, bad in the
middle, and effective context often dies after **4–8K tokens** despite advertised
32K+. **Stuffing the whole corpus loses to precise top-k=3.** Track the gold
chunk's token position in the prompt and plot accuracy vs position.

## Required publication artifacts
Gold Q&A key · curated corpus JSON · frozen web cache · full harness code
(eval.py/bakeoff.py + RAGAS/DeepEval, Gwet's AC1, McNemar) · exact prompt/Jinja
templates · temps, seeds, **quant levels** per model.
