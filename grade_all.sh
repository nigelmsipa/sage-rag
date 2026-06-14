#!/bin/sh
# Grade all 12 new models x 2 arms with the LLM judge, in parallel (6 at a time).
# RAG grades  -> bakeoff/grades/<tag>.json
# closed-book -> bakeoff/grades/closedbook-<tag>.json   (matches prior naming)
cd /home/nigel/sage-rag
mkdir -p bakeoff/grades

TAGS="gptoss-120b hermes4-70b claude-haiku3 gpt5-nano gemini25-flash-lite claude-opus48 gpt55-pro gemini31-pro gemma3-12b qwen36-35b-a3b gemma4-31b gemma4-26b-a4b"

# build the job list: "dump|outfile"
JOBS=""
for t in $TAGS; do
  JOBS="$JOBS bakeoff/$t.json|bakeoff/grades/$t.json"
  JOBS="$JOBS bakeoff/closedbook/$t.json|bakeoff/grades/closedbook-$t.json"
done

printf '%s\n' $JOBS | xargs -P 6 -I {} sh -c '
  d=$(echo "{}" | cut -d"|" -f1); o=$(echo "{}" | cut -d"|" -f2)
  [ -f "$d" ] && python3 judge.py "$d" --out "$o" >/dev/null 2>&1 && echo "graded $o" || echo "SKIP/ERR $d"
'
echo "#### GRADING COMPLETE ####"
