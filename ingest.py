#!/usr/bin/env python3
"""
ingest.py — turn the produce corpus into a searchable knowledge base.

What it does:
  1. Reads every .md file in CORPUS_DIR.
  2. Splits each into chunks (by heading, then by size with overlap).
  3. Asks Ollama to embed each chunk into a 1024-dim vector (mxbai-embed-large).
  4. Saves everything to knowledge.json (text + vector + source metadata).

Run once (and re-run whenever the corpus changes):
    python3 ingest.py
"""

import os
import re
import json
import sys
import time
import urllib.request

# Usage: python3 ingest.py [corpus_dir] [name]
#   corpus_dir : folder of .md files (default ~/corpora/produce)
#   name       : knowledge-base name -> knowledge-<name>.json (default: folder name)
CORPUS_DIR   = os.path.expanduser(sys.argv[1]) if len(sys.argv) > 1 \
               else os.path.expanduser("~/corpora/produce")
KB_NAME      = sys.argv[2] if len(sys.argv) > 2 \
               else os.path.basename(CORPUS_DIR.rstrip("/")) or "knowledge"
OUT_PATH     = os.path.expanduser(f"~/sage-rag/knowledge-{KB_NAME}.json")
OLLAMA       = "http://localhost:11434"
EMBED_MODEL  = "mxbai-embed-large"      # 1024-dim, strong retrieval model

# Chunking targets (in words). Big enough to hold an idea, small enough to be
# precise. Overlap keeps context from being cut mid-thought.
CHUNK_WORDS   = 280
CHUNK_OVERLAP = 50


def embed(text, retries=4):
    """Get one embedding vector from Ollama, retrying transient failures.
    Returns None if it ultimately fails."""
    body = json.dumps({"model": EMBED_MODEL, "prompt": text}).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                OLLAMA + "/api/embeddings", data=body,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                emb = json.loads(r.read()).get("embedding")
            if emb:
                return emb
        except Exception as e:
            if attempt == retries - 1:
                print(f"\n  ! embed failed after {retries} tries: {e}",
                      file=sys.stderr)
                return None
            time.sleep(1.5 * (attempt + 1))   # back off and retry
    return None


def _clean(s):
    """Strip markdown noise from a cell/heading."""
    s = s.strip().replace("\\", "")     # drop escapes like \-0.5
    return s.strip("*").strip()         # drop bold markers


def _split_row(row):
    return [_clean(c) for c in row.strip().strip("|").split("|")]


def _table_chunks(heading, table_lines):
    """One chunk per table ROW (per commodity), so each commodity's numbers
    stay together and don't blur with its neighbours' in the same chunk."""
    if len(table_lines) < 2:
        yield from _window_chunks(heading, table_lines)
        return
    header = _split_row(table_lines[0])
    for row in table_lines[1:]:
        if re.match(r'^[\s|:\-]+$', row):       # separator row (|:---|---|)
            continue
        cells = _split_row(row)
        if len(cells) != len(header) or not cells[0]:
            continue
        name = cells[0]
        parts = [f"{heading} — {name}"]
        for h, c in zip(header, cells):
            if c:
                parts.append(f"{h}: {c}")
        text = "\n".join(parts)
        if len(text) > 40:
            yield f"{heading} / {name}", text


def _window_chunks(heading, lines):
    """Slide a CHUNK_WORDS window over prose (non-table) text."""
    words = " ".join(lines).split()
    if not words:
        return
    step = CHUNK_WORDS - CHUNK_OVERLAP
    for start in range(0, len(words), step):
        piece = " ".join(words[start:start + CHUNK_WORDS]).strip()
        if len(piece) > 40:
            yield heading, piece
        if start + CHUNK_WORDS >= len(words):
            break


def split_into_chunks(text):
    """Split markdown into heading-aware chunks. Tables become one chunk per
    row (per commodity); prose is windowed. Yields (heading, chunk_text)."""
    # Break the doc into sections at markdown headings.
    sections = []
    current_heading = ""
    current_lines = []
    for line in text.splitlines():
        if re.match(r'^#{1,6}\s', line):
            if current_lines:
                sections.append((current_heading, current_lines))
                current_lines = []
            current_heading = _clean(line.lstrip("#"))
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_heading, current_lines))

    # Within each section, peel out table blocks and chunk them per-row;
    # everything else is windowed prose.
    for heading, lines in sections:
        i, prose = 0, []
        while i < len(lines):
            if lines[i].lstrip().startswith("|"):
                block = []
                while i < len(lines) and lines[i].lstrip().startswith("|"):
                    block.append(lines[i])
                    i += 1
                yield from _window_chunks(heading, prose)
                prose = []
                yield from _table_chunks(heading, block)
            else:
                prose.append(lines[i])
                i += 1
        yield from _window_chunks(heading, prose)


def main():
    files = sorted(f for f in os.listdir(CORPUS_DIR) if f.endswith(".md"))
    if not files:
        print(f"No .md files in {CORPUS_DIR}", file=sys.stderr)
        sys.exit(1)

    records = []
    chunk_id = 0
    for fname in files:
        path = os.path.join(CORPUS_DIR, fname)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        n_before = chunk_id
        for heading, chunk in split_into_chunks(text):
            vec = embed(chunk)
            if vec is None:
                continue        # skip this chunk, keep going
            records.append({
                "id": chunk_id,
                "file": fname,
                "heading": heading,
                "text": chunk,
                "vector": vec,
            })
            chunk_id += 1
            print(f"\r  {fname}: {chunk_id - n_before} chunks  "
                  f"(total {chunk_id})", end="", flush=True)
        print()

    with open(OUT_PATH, "w", encoding="utf-8") as out:
        json.dump({"name": KB_NAME, "model": EMBED_MODEL,
                   "dim": len(records[0]["vector"]), "chunks": records}, out)
    print(f"\nWrote {len(records)} chunks -> {OUT_PATH} "
          f"({len(records[0]['vector'])}-dim vectors)  kb='{KB_NAME}'")


if __name__ == "__main__":
    main()
