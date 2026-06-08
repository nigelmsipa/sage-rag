#!/usr/bin/env python3
"""
bakeoff.py — curated corpus RAG vs. web-search RAG, head to head.

Same question + same answer model (gpt-oss). The ONLY difference is where the
facts come from:
  - CORPUS arm: our knowledge base (via the running RAG service on :11500)
  - WEB arm:    live DuckDuckGo results fed to the same model

Prints GOLD / CORPUS / WEB for each question so we can compare directly.

    python3 bakeoff.py
"""
import json, urllib.request
from ddgs import DDGS

RAG_URL   = "http://localhost:11500/api/chat"   # corpus RAG (gpt-oss behind it)
OLLAMA    = "http://localhost:11434/api/chat"
GEN_MODEL = "gpt-oss:20b"
N_WEB     = 5

# Questions where domain specifics matter, with our gold answers.
QUESTIONS = [
    ("What is the correct water temperature for crisping wilted produce?",
     "95-100°F (35-38°C) warm water. Above 105°F cooks/damages the leaves; "
     "cold water constricts the tissue and fails to hydrate."),
    ("What is the chilling threshold for cranberries?",
     "Below 2°C (35°F) causes chilling injury."),
    ("At what temperature should sweet potatoes be stored?",
     "55-59°F (13-15°C). Refrigeration causes chilling injury (hard core, "
     "mahogany browning)."),
    ("Should I store apples next to leafy greens?",
     "No — apples emit ethylene and leafy greens are ethylene-sensitive, so "
     "they yellow/wilt prematurely."),
]


def _collect(req):
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


def corpus_answer(question):
    body = json.dumps({"model": "produce-rag",
                       "messages": [{"role": "user", "content": question}]}).encode()
    return _collect(urllib.request.Request(RAG_URL, data=body,
                    headers={"Content-Type": "application/json"}))


def web_answer(question):
    results = DDGS().text(question, max_results=N_WEB)
    blocks = [f"[{r['title']}] {r['body']} (source: {r['href']})" for r in results]
    context = "\n\n".join(blocks) or "(no results)"
    system = {"role": "system", "content":
              "Answer the user's question using ONLY these web search results. "
              "Be concise and cite which source you used.\n\nRESULTS:\n" + context}
    body = json.dumps({"model": GEN_MODEL,
                       "messages": [system, {"role": "user", "content": question}],
                       "stream": True}).encode()
    ans = _collect(urllib.request.Request(OLLAMA, data=body,
                   headers={"Content-Type": "application/json"}))
    top = results[0]["href"] if results else "(none)"
    return ans, top


def main():
    for i, (q, gold) in enumerate(QUESTIONS, 1):
        print(f"\n{'='*70}\nQ{i}: {q}\n{'='*70}", flush=True)
        print(f"GOLD:   {gold}\n", flush=True)
        corpus = corpus_answer(q)
        print(f"CORPUS: {corpus[:400]}\n", flush=True)
        web, top = web_answer(q)
        print(f"WEB:    {web[:400]}", flush=True)
        print(f"        (top result: {top})", flush=True)


if __name__ == "__main__":
    main()
