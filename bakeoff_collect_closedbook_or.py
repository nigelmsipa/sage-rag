#!/usr/bin/env python3
"""
bakeoff_collect_closedbook_or.py — the closed-book (no-RAG) arm for CLOUD models.

Same idea as bakeoff_collect_closedbook.py, but instead of hitting local Ollama
it goes straight to OpenRouter with the model slug. No retrieval, no grounding —
the question is answered from the model's parametric knowledge alone, with the
same neutral expert SYSTEM prompt the local closed-book arm uses (so the RAG-vs-
closed-book delta is apples-to-apples across local and cloud).

    python3 bakeoff_collect_closedbook_or.py <openrouter-slug> <out-tag> [sample]

Writes ~/sage-rag/bakeoff/closedbook/<out-tag>.json
"""
import sys, json, os, glob, time, urllib.request

OR_URL  = "https://openrouter.ai/api/v1/chat/completions"
KEYFILE = os.path.expanduser("~/.config/sage/openrouter.key")
CORPUS  = os.path.expanduser("~/corpora/produce")
OUTDIR  = os.path.expanduser("~/sage-rag/bakeoff/closedbook")

# Identical to the local closed-book arm — fair shot, explicit "I don't know".
SYSTEM = ("You are a knowledgeable retail-produce and grocery operations expert. "
          "Answer the question concisely and specifically from your own knowledge. "
          "If you do not actually know a specific figure or fact, say so plainly "
          "rather than guessing.")


def parse_pairs(text):
    pairs, q, a, mode = [], None, [], None
    for line in text.splitlines():
        if line.startswith("Q:"):
            if q is not None:
                pairs.append((q.strip(), " ".join(a).strip()))
            q, a, mode = line[2:], [], "q"
        elif line.startswith("A:"):
            a, mode = [line[2:]], "a"
        else:
            if mode == "a":
                a.append(line)
            elif mode == "q":
                q += " " + line
    if q is not None:
        pairs.append((q.strip(), " ".join(a).strip()))
    return pairs


def ask(key, model, question):
    # Cap max_tokens — otherwise pricey reasoning models (gpt-5.5-pro) reserve
    # their full default output and 402 on a modest balance.
    body = json.dumps({"model": model,
                       "messages": [{"role": "system", "content": SYSTEM},
                                    {"role": "user", "content": question}],
                       "max_tokens": int(os.environ.get("CB_MAX_TOKENS", "8000"))}).encode()
    req = urllib.request.Request(OR_URL, data=body, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/nigelmsipa/sage-rag",
        "X-Title": "Sage RAG closed-book bakeoff",
    })
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.loads(r.read())
    ans = d["choices"][0]["message"]["content"].strip()
    usage = d.get("usage", {}) or {}
    return ans, usage


def main():
    model, tag = sys.argv[1], sys.argv[2]
    sample = int(sys.argv[3]) if len(sys.argv) > 3 else None
    with open(KEYFILE) as fh:
        key = fh.read().strip()
    os.makedirs(OUTDIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(CORPUS, "qa-*.md")))
    results, n = [], 0
    for f in files:
        pairs = parse_pairs(open(f, encoding="utf-8").read())
        if sample and sample < len(pairs):
            step = len(pairs) / sample
            pairs = [pairs[int(i * step)] for i in range(sample)]
        section = os.path.basename(f).replace(".md", "")
        for q, gold in pairs:
            t = time.time()
            try:
                ans, usage = ask(key, model, q)
            except Exception as e:
                ans, usage = f"[ERROR: {e}]", {}
            wall = round(time.time() - t, 2)
            n += 1
            results.append({"section": section, "q": q, "gold": gold, "answer": ans,
                            "prompt_tok": usage.get("prompt_tokens"),
                            "completion_tok": usage.get("completion_tokens"),
                            "total_s": wall})
            print(f"[{n}] {section} | {wall}s | {q[:55]}", flush=True)
    out = os.path.join(OUTDIR, f"{tag}.json")
    json.dump({"model": tag, "arm": "closed-book", "backend": "openrouter",
               "slug": model, "n": n, "results": results}, open(out, "w"), indent=1)
    print(f"\n== {tag} (closed-book, cloud): {n} Q | saved {out}", flush=True)


if __name__ == "__main__":
    main()
