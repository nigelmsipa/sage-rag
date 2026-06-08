#!/usr/bin/env python3
"""
eval.py — grade the RAG against your gold Q&A answer key.

gpt-oss (via the RAG server) writes each answer; a fast judge model grades it
PASS / PARTIAL / FAIL against your gold answer. Streams a scorecard live and
saves full details to eval-results.json for drill-down.

    python3 eval.py all                 # every qa-*.md section
    python3 eval.py <file.md>           # one section
    python3 eval.py all 10              # sample 10 questions per section
"""
import sys, json, os, glob, urllib.request

RAG_URL     = "http://localhost:11500/api/chat"   # gpt-oss via RAG server
OLLAMA      = "http://localhost:11434/api/chat"    # direct, for the judge
RAG_MODEL   = "produce-rag"
JUDGE_MODEL = "qwen2.5:7b"
CORPUS      = os.path.expanduser("~/corpora/produce")
RESULTS     = os.path.expanduser("~/sage-rag/eval-results.json")


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
    out = ""
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
                break
    return out.strip()


def judge(question, gold, candidate):
    prompt = (
        "Grade a CANDIDATE answer against the official GOLD answer. Judge ONLY "
        "factual agreement:\n"
        "- PASS: the candidate includes the gold's key facts/numbers and "
        "contradicts none. Extra correct detail, more thoroughness, and "
        "different wording are FINE and must NOT lower the grade.\n"
        "- PARTIAL: gets the main idea but misses a key fact the question asks "
        "for, or is vague where the gold gives a specific value.\n"
        "- FAIL: contradicts the gold (e.g. a different number/temperature) or "
        "misses the core answer.\n"
        "Never penalize the candidate for adding extra correct information.\n\n"
        f"QUESTION: {question}\nGOLD: {gold}\nCANDIDATE: {candidate}\n\n"
        "Reply with exactly one word — PASS, PARTIAL, or FAIL — then ' | ' and "
        "a one-line reason."
    )
    body = json.dumps({"model": JUDGE_MODEL,
                       "messages": [{"role": "user", "content": prompt}],
                       "stream": False,
                       "options": {"temperature": 0}}).encode()
    req = urllib.request.Request(OLLAMA, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        txt = json.loads(r.read())["message"]["content"].strip()
    up = txt.upper()
    verdict = next((k for k in ("PARTIAL", "PASS", "FAIL") if k in up), "?")
    return verdict, txt


def main():
    arg = sys.argv[1]
    if arg == "all":
        files = sorted(glob.glob(os.path.join(CORPUS, "qa-*.md")))
    else:
        files = [os.path.expanduser(arg)]
    sample = int(sys.argv[2]) if len(sys.argv) > 2 else None

    results = []
    grand = {"PASS": 0, "PARTIAL": 0, "FAIL": 0, "?": 0}

    for f in files:
        pairs = parse_pairs(open(f, encoding="utf-8").read())
        if sample and sample < len(pairs):
            step = len(pairs) / sample
            pairs = [pairs[int(i * step)] for i in range(sample)]
        section = os.path.basename(f).replace(".md", "")
        counts = {"PASS": 0, "PARTIAL": 0, "FAIL": 0, "?": 0}
        print(f"\n===== {section}: {len(pairs)} questions =====", flush=True)

        for i, (q, gold) in enumerate(pairs, 1):
            rag = ask_rag(q)
            verdict, reason = judge(q, gold, rag)
            counts[verdict] += 1
            grand[verdict] += 1
            mark = {"PASS": "  ok", "PARTIAL": "WARN", "FAIL": "FAIL", "?": " ???"}[verdict]
            print(f"[{mark}] Q{i}: {q[:72]}", flush=True)
            if verdict != "PASS":
                print(f"        -> {reason[:160]}", flush=True)
            results.append({"section": section, "q": q, "gold": gold,
                            "rag": rag, "verdict": verdict, "reason": reason})

        print(f"----- {section}: {counts['PASS']} pass / "
              f"{counts['PARTIAL']} partial / {counts['FAIL']} fail -----", flush=True)
        # save progress after every section
        json.dump(results, open(RESULTS, "w"))

    print(f"\n===== TOTAL: {grand['PASS']} pass / {grand['PARTIAL']} partial / "
          f"{grand['FAIL']} fail / {grand['?']} ungraded =====", flush=True)


if __name__ == "__main__":
    main()
