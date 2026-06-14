#!/usr/bin/env python3
"""
judge.py — grade a bakeoff dump (RAG or closed-book) against the gold answers
with a neutral LLM judge over OpenRouter. Separates judging from generation, and
labels REFUSAL distinctly from FAIL so we can see calibration (honest "I don't
know" vs confident-wrong) — the key closed-book signal.

    python3 judge.py <dump.json> [--out grades/<name>.json]

Grades per question: PASS | PARTIAL | FAIL | REFUSAL.
"""
import sys, json, os, time, urllib.request

OR_URL  = "https://openrouter.ai/api/v1/chat/completions"
KEYFILE = os.path.expanduser("~/.config/sage/openrouter.key")
JUDGE   = os.environ.get("JUDGE_MODEL", "google/gemini-2.5-flash")

RUBRIC = """You are grading a produce-operations Q&A answer against a GOLD reference.
Judge ONLY factual correctness on the specifics that matter (exact temperatures,
percentages, names, figures, food-safety facts). Style/length don't matter.

Return EXACTLY one word:
- PASS    : the answer states the gold's key fact(s)/figure(s) correctly.
- PARTIAL : partially correct, or correct-but-vague (misses the specific figure), or mixes a correct fact with a minor wrong one.
- FAIL    : confidently states a WRONG fact/figure, or contradicts the gold, or is off-topic.
- REFUSAL : the model declined / said it does not know / has no specific data (no fabricated specifics).

Output only the one word."""


def judge_one(key, question, gold, answer):
    if not answer.strip() or answer.startswith("[ERROR"):
        return "REFUSAL"  # empty/blank → treat as non-answer (kept separate from FAIL)
    user = f"QUESTION:\n{question}\n\nGOLD:\n{gold}\n\nMODEL ANSWER:\n{answer}\n\nGrade:"
    body = json.dumps({"model": JUDGE,
                       "messages": [{"role": "system", "content": RUBRIC},
                                    {"role": "user", "content": user}],
                       "max_tokens": 8}).encode()
    req = urllib.request.Request(OR_URL, data=body, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "X-Title": "Sage RAG judge"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                txt = json.loads(r.read())["choices"][0]["message"]["content"].upper()
            for label in ("PARTIAL", "REFUSAL", "PASS", "FAIL"):
                if label in txt:
                    return label
            return "PARTIAL"
        except Exception as e:
            if attempt == 2:
                return f"ERR:{e}"
            time.sleep(2)


def main():
    dump = sys.argv[1]
    out = None
    if "--out" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1]
    key = open(KEYFILE).read().strip()
    d = json.load(open(dump))
    results = d["results"]
    tag = d.get("model", os.path.basename(dump)[:-5])
    arm = d.get("arm", "rag")
    counts = {"PASS": 0, "PARTIAL": 0, "FAIL": 0, "REFUSAL": 0}
    graded = []
    for i, r in enumerate(results, 1):
        g = judge_one(key, r["q"], r["gold"], r["answer"])
        if g.startswith("ERR:"):
            g = "PARTIAL"
        counts[g] = counts.get(g, 0) + 1
        graded.append({"section": r["section"], "q": r["q"], "grade": g,
                       "gold": r["gold"], "answer": r["answer"][:600]})
        print(f"[{i:>2}/{len(results)}] {g:8s} {r['q'][:60]}", flush=True)
    n = len(results)
    pass_rate = round(100 * counts["PASS"] / n, 1)
    soft_rate = round(100 * (counts["PASS"] + 0.5 * counts["PARTIAL"]) / n, 1)
    summary = {"model": tag, "arm": arm, "judge": JUDGE, "n": n,
               "counts": counts, "pass_rate_pct": pass_rate,
               "soft_rate_pct": soft_rate}
    if out:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        json.dump({"summary": summary, "graded": graded}, open(out, "w"), indent=1)
    print(f"\n== {tag} [{arm}] PASS {pass_rate}%  soft {soft_rate}%  "
          f"{counts}  judge={JUDGE}", flush=True)


if __name__ == "__main__":
    main()
