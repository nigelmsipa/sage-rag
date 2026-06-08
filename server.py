#!/usr/bin/env python3
"""
server.py — a RAG service that speaks Ollama's API and supports MANY corpora.

It sits in front of Ollama on port 11500 and is the only address the phone
app ever needs. Point Sage at it, then the model picker becomes a switcher:

    gpt-oss:20b     -> plain chat, passed straight through to Ollama
    produce-rag     -> answered from knowledge-produce.json
    <name>-rag      -> answered from knowledge-<name>.json

ADDING A NEW RAG is just:
    python3 ingest.py ~/corpora/theology theology   # -> knowledge-theology.json
    (restart this server)
...and "theology-rag" appears in the app's model list automatically.

    python3 server.py
"""

import os
import glob
import json
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

HERE        = os.path.expanduser("~/sage-rag")
OLLAMA      = "http://localhost:11434"
GEN_MODEL   = "gpt-oss:20b"        # the model that writes RAG answers (trusted; slower on CPU)
LISTEN      = ("0.0.0.0", 11500)
TOP_K       = 10        # more chunks -> better coverage for multi-fact questions
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


# ---- Load every knowledge-*.json into memory -------------------------------
def load_kbs():
    kbs = {}
    for path in sorted(glob.glob(os.path.join(HERE, "knowledge-*.json"))):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        name = data.get("name") or os.path.basename(path)[10:-5]  # strip knowledge-/.json
        chunks = data["chunks"]
        mat = np.array([c["vector"] for c in chunks], dtype=np.float32)
        mat /= (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-8)
        kbs[name] = {
            "name": name,
            "chunks": chunks,
            "mat": mat,
            "embed_model": data.get("model", "mxbai-embed-large"),
        }
        print(f"  loaded kb '{name}': {len(chunks)} chunks, {mat.shape[1]}-dim")
    return kbs


print("Loading knowledge bases...")
KBS = load_kbs()
if not KBS:
    print("  (none found — only plain chat passthrough will work)")


def embed(text, model):
    body = json.dumps({"model": model, "prompt": text}).encode()
    req = urllib.request.Request(OLLAMA + "/api/embeddings", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        v = np.array(json.loads(r.read())["embedding"], dtype=np.float32)
    return v / (np.linalg.norm(v) + 1e-8)


def retrieve(kb, question, k=TOP_K):
    qv = embed(QUERY_PREFIX + question, kb["embed_model"])
    scores = kb["mat"] @ qv
    top = np.argsort(-scores)[:k]
    return [kb["chunks"][i] for i in top]


def build_context(hits):
    blocks = []
    for c in hits:
        src = c["file"].replace(".md", "")
        head = f" / {c['heading']}" if c.get("heading") else ""
        blocks.append(f"[Source: {src}{head}]\n{c['text']}")
    return "\n\n---\n\n".join(blocks)


# Each knowledge base can have its OWN instructions in ~/sage-rag/prompt-<name>.txt
# (must contain a {context} placeholder). Corpora without a file use the generic
# default below — so produce's ethylene rules don't leak into, say, a theology RAG.
DEFAULT_TEMPLATE = (
    "You are Sage, a knowledgeable assistant. Answer the user's question using "
    "ONLY the context below. If the context doesn't contain the answer, say so "
    "plainly rather than guessing.\n\n"
    "RULES:\n"
    "- Quote exact figures, names, and quotes from the context VERBATIM. Never "
    "replace a specific value with a vague paraphrase.\n"
    "- Base every FACT on the context, but DO reason and combine multiple facts "
    "to reach a practical conclusion.\n"
    "- Be concise, and cite the sources you drew from.\n\n"
    "CONTEXT:\n{context}"
)


def load_prompts():
    """Read prompt-<name>.txt for each KB; fall back to the generic default."""
    prompts = {}
    for path in glob.glob(os.path.join(HERE, "prompt-*.txt")):
        name = os.path.basename(path)[7:-4]   # strip 'prompt-' and '.txt'
        with open(path, encoding="utf-8") as fh:
            tmpl = fh.read()
        if "{context}" in tmpl:
            prompts[name] = tmpl
            print(f"  loaded prompt for '{name}'")
        else:
            print(f"  ! prompt-{name}.txt has no {{context}} placeholder — ignored")
    return prompts


PROMPTS = load_prompts()


def prompt_for(kb_name):
    return PROMPTS.get(kb_name, DEFAULT_TEMPLATE)


def kb_for_model(model):
    """Map a requested model name to a knowledge base, or None for plain chat."""
    if not model:
        return None
    name = model[:-4] if model.endswith("-rag") else model
    return KBS.get(name)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/api/tags"):
            models = []
            # Real Ollama models (for plain chat)...
            try:
                with urllib.request.urlopen(OLLAMA + "/api/tags", timeout=10) as r:
                    models = json.loads(r.read()).get("models", [])
            except Exception:
                pass
            # ...plus one virtual "<name>-rag" per knowledge base.
            for name in KBS:
                models.insert(0, {"name": f"{name}-rag", "model": f"{name}-rag",
                                  "size": 0, "details": {"family": "rag"}})
            self._json(200, {"models": models})
        elif self.path.startswith("/api/version"):
            self._json(200, {"version": "sage-rag-0.2"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.startswith("/api/chat"):
            self._json(404, {"error": "only /api/chat is supported"})
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) or b"{}"
        req = json.loads(raw)
        kb = kb_for_model(req.get("model", ""))

        if kb is None:
            # Plain chat: forward the request to Ollama untouched.
            out_body = raw
        else:
            # RAG: retrieve, prepend a context system prompt, swap to GEN_MODEL.
            messages = req.get("messages", [])
            question = next((m.get("content", "") for m in reversed(messages)
                             if m.get("role") == "user"), "")
            hits = retrieve(kb, question) if question else []
            context = build_context(hits) if hits else "(no relevant context found)"
            system = {"role": "system",
                      "content": prompt_for(kb["name"]).format(context=context)}
            convo = [system] + [m for m in messages if m.get("role") != "system"]
            out_body = json.dumps({"model": GEN_MODEL, "messages": convo,
                                   "stream": True}).encode()

        ollama_req = urllib.request.Request(
            OLLAMA + "/api/chat", data=out_body,
            headers={"Content-Type": "application/json"})

        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        try:
            with urllib.request.urlopen(ollama_req, timeout=600) as resp:
                for line in resp:
                    self.wfile.write(line)
                    self.wfile.flush()
        except Exception as e:
            try:
                self.wfile.write(json.dumps({"error": str(e)}).encode() + b"\n")
            except Exception:
                pass


if __name__ == "__main__":
    print(f"Sage RAG on http://{LISTEN[0]}:{LISTEN[1]}  "
          f"(RAG answers via {GEN_MODEL}; plain models pass through)")
    ThreadingHTTPServer(LISTEN, Handler).serve_forever()
