#!/usr/bin/env python3
"""
bakeoff_collect.py — run the gold Q&A through produce-rag for ONE candidate model
and record the answer + timing. No grading here (Claude grades the dumped JSON),
so generation (slow, local) is cleanly separated from judging (unbiased).

Assumes server.py is already running on :11500 with the desired GEN_MODEL
(set via SAGE_GEN_MODEL) and uniform SAGE_NUM_CTX=8192 / SAGE_TOP_K=3.

    python3 bakeoff_collect.py <model-tag> [sample_per_section]

Writes ~/sage-rag/bakeoff/<model-tag>.json
"""
import sys, json, os, glob, time, urllib.request

RAG_URL = f"http://localhost:{os.environ.get('BAKEOFF_PORT', '11501')}/api/chat"
RAG_MODEL = "produce-rag"
CORPUS = os.path.expanduser("~/corpora/produce")
OUTDIR = os.path.expanduser("~/sage-rag/bakeoff")


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


def ask_rag(question):
    body = json.dumps({"model": RAG_MODEL,
                       "messages": [{"role": "user", "content": question}]}).encode()
    req = urllib.request.Request(RAG_URL, data=body,
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
                        ("total_duration", "load_duration", "prompt_eval_count",
                         "prompt_eval_duration", "eval_count", "eval_duration")}
                break
    return out.strip(), meta


def main():
    model_tag = sys.argv[1]
    sample = int(sys.argv[2]) if len(sys.argv) > 2 else None
    os.makedirs(OUTDIR, exist_ok=True)

    files = sorted(glob.glob(os.path.join(CORPUS, "qa-*.md")))
    results = []
    t0 = time.time()
    n = 0
    for f in files:
        pairs = parse_pairs(open(f, encoding="utf-8").read())
        if sample and sample < len(pairs):
            step = len(pairs) / sample
            pairs = [pairs[int(i * step)] for i in range(sample)]
        section = os.path.basename(f).replace(".md", "")
        for q, gold in pairs:
            ans, meta = ask_rag(q)
            n += 1
            # tokens/sec from ollama's nanosecond durations
            def tps(cnt, dur): return round(cnt / (dur / 1e9), 1) if cnt and dur else None
            rec = {"section": section, "q": q, "gold": gold, "answer": ans,
                   "prefill_tok": meta.get("prompt_eval_count"),
                   "decode_tok": meta.get("eval_count"),
                   "prefill_tps": tps(meta.get("prompt_eval_count"), meta.get("prompt_eval_duration")),
                   "decode_tps": tps(meta.get("eval_count"), meta.get("eval_duration")),
                   "total_s": round((meta.get("total_duration") or 0) / 1e9, 2)}
            results.append(rec)
            print(f"[{n}] {section} | {rec['total_s']}s "
                  f"(prefill {rec['prefill_tps']} t/s, decode {rec['decode_tps']} t/s) "
                  f"| {q[:54]}", flush=True)

    out = os.path.join(OUTDIR, f"{model_tag}.json")
    summary = {
        "model": model_tag, "n": n, "wall_s": round(time.time() - t0, 1),
        "avg_total_s": round(sum(r["total_s"] for r in results) / n, 2),
        "avg_prefill_tps": round(sum(r["prefill_tps"] for r in results if r["prefill_tps"]) /
                                 max(1, sum(1 for r in results if r["prefill_tps"])), 1),
        "avg_decode_tps": round(sum(r["decode_tps"] for r in results if r["decode_tps"]) /
                                max(1, sum(1 for r in results if r["decode_tps"])), 1),
    }
    json.dump({"summary": summary, "results": results}, open(out, "w"), indent=1)
    print(f"\n== {model_tag}: {n} Q in {summary['wall_s']}s | "
          f"avg {summary['avg_total_s']}s/Q | decode {summary['avg_decode_tps']} t/s "
          f"| saved {out}", flush=True)


if __name__ == "__main__":
    main()
