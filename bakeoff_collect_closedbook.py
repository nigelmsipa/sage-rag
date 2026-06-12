#!/usr/bin/env python3
"""
bakeoff_collect_closedbook.py — the "wild west" arm. Run the gold Q&A against a
model with NO retrieval: question straight to Ollama, parametric knowledge only.
The gap between this and the RAG score IS the value the corpus adds. Also exposes
hallucination (confident wrong specifics) and contamination (suspiciously-right
specifics) when the model is ungrounded.

    python3 bakeoff_collect_closedbook.py <ollama-model-tag> <out-tag> [sample]

Writes ~/sage-rag/bakeoff/closedbook/<out-tag>.json
"""
import sys, json, os, glob, urllib.request

OLLAMA = "http://localhost:11434/api/chat"
CORPUS = os.path.expanduser("~/corpora/produce")
OUTDIR = os.path.expanduser("~/sage-rag/bakeoff/closedbook")

# Neutral expert prompt: give it a fair shot, and explicitly allow "I don't know"
# so we can tell refusal (good) from confident hallucination (bad) in the wild.
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


def ask(model, question):
    body = json.dumps({"model": model,
                       "messages": [{"role": "system", "content": SYSTEM},
                                    {"role": "user", "content": question}],
                       "stream": True,
                       "options": {"num_ctx": 8192,
                                   "num_predict": int(os.environ.get("CB_NUM_PREDICT", "512"))}}).encode()
    req = urllib.request.Request(OLLAMA, data=body,
                                 headers={"Content-Type": "application/json"})
    out, meta = "", {}
    with urllib.request.urlopen(req, timeout=600) as r:
        for line in r:
            line = line.decode().strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            out += d.get("message", {}).get("content", "")
            if d.get("done"):
                meta = {k: d.get(k) for k in
                        ("total_duration", "prompt_eval_count", "eval_count")}
                break
    return out.strip(), meta


def main():
    model, tag = sys.argv[1], sys.argv[2]
    sample = int(sys.argv[3]) if len(sys.argv) > 3 else None
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
            ans, meta = ask(model, q)
            n += 1
            tot = round((meta.get("total_duration") or 0) / 1e9, 2)
            results.append({"section": section, "q": q, "gold": gold, "answer": ans,
                            "total_s": tot})
            print(f"[{n}] {section} | {tot}s | {q[:55]}", flush=True)
    out = os.path.join(OUTDIR, f"{tag}.json")
    json.dump({"model": tag, "arm": "closed-book", "n": n, "results": results},
              open(out, "w"), indent=1)
    print(f"\n== {tag} (closed-book): {n} Q | saved {out}", flush=True)


if __name__ == "__main__":
    main()
