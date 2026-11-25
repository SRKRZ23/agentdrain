#!/bin/zsh
# Wait until the three per-model agent runs have finished (no run_agents.py process left), then print a summary.
cd "$(dirname "$0")/.."
until ! pgrep -f "bench/run_agents.py" >/dev/null; do sleep 30; done
for f in results/run_gpt-oss-120b.log results/run_gpt-oss-20b.log results/run_qwen3.8-27b.log; do
  echo "$f: $(grep -c '^\[' $f) episodes, $(grep -c 0xBAD $f) with attacker payments, $(grep -c ERR $f) errors"
done
cat results/episodes_*.jsonl | wc -l
