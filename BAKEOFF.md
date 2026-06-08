# Bake-off: curated knowledge base vs. web search

**Question:** is it worth building and maintaining a domain knowledge base, or
could you get the same answers by just bolting web search onto an LLM?

I tested it instead of guessing.

## Method

A controlled comparison — the **only** variable is the source of facts:

- **Same questions** for both arms
- **Same answer model** (`gpt-oss:20b`) for both arms
- **Arm A (Corpus):** retrieves from my curated produce knowledge base
- **Arm B (Web):** retrieves live DuckDuckGo results, fed to the same model

Both arms are graded against a hand-written gold answer key.
Reproducible via [`bakeoff.py`](./bakeoff.py).

## Results

| Question | Curated corpus | Web search | Winner |
|----------|----------------|------------|--------|
| Crisping water temperature | **95–100°F** ✅ | "cold water — colder is better" ❌ | **Corpus** |
| Cranberry chilling threshold | **2°C (35°F)** ✅ | cranberry-*farming* dormancy hours ❌ (wrong topic) | **Corpus** |
| Sweet potato storage temp | 55–59°F ✅ | 55–59°F ✅ | Tie |
| Apples next to leafy greens | No — ethylene ✅ (+ 3-ft rule) | No — ethylene ✅ | Tie |

## What the failures reveal

The web didn't just lose — it lost in *instructive* ways:

1. **It served the exact myth the corpus debunks.** For crisping wilted greens,
   the top web result said "soak in **cold** water." A different search returned
   "**120°F hot** water." The open web gives **contradictory, confidently wrong**
   advice; the corpus gives one authoritative answer (95–100°F, and explicitly
   warns >105°F damages the produce).

2. **It couldn't tell the domain from an adjacent one.** Asked for the cranberry
   *retail-storage* chilling threshold, the web answered about cranberry
   *farming* (dormancy chill hours) — a completely different question.

Where the web *did* tie, it was on **common, well-documented facts** (sweet
potato temperature, apple/ethylene). Those are exactly the cases where a
knowledge base adds little.

## Conclusion

> A curated knowledge base earns its keep precisely where generic web search is
> **unreliable**: domain-specific operational knowledge, myth-prone topics, and
> disambiguating *your* context from adjacent ones. For commodity facts the web
> is fine — but you can't tell in advance *which* answer you're getting, so the
> corpus wins on **trustworthiness**, which is the whole point of a reference
> tool.

The value of the knowledge base isn't that it knows *more* than the web — it's
that it's **right when being wrong would cost you**, and you can trust it without
second-guessing every answer.
