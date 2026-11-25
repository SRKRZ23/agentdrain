"""
Run every (model, episode, repeat) and append results to results/episodes.jsonl. Resumable: finished episodes are
skipped, so a run interrupted by rate limits or the daily quota continues where it stopped.

usage: GROQ_API_KEY=... python3 bench/run_agents.py [repeats=2] [models=comma,separated]
(run one process per model to go faster; merge with: cat results/episodes_*.jsonl > results/episodes.jsonl)
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agent import run_episode  # noqa: E402
from attacks import ATTACKS, BENIGN  # noqa: E402

RESULTS = Path(__file__).parent.parent / "results"
DEFAULT_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]


def main():
    repeats = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    models = sys.argv[2].split(",") if len(sys.argv) > 2 else DEFAULT_MODELS
    key = os.environ["GROQ_API_KEY"]
    RESULTS.mkdir(exist_ok=True)
    # one file per model run so parallel runs (one process per model) never interleave writes
    OUT = RESULTS / ("episodes_" + "_".join(m.split("/")[-1] for m in models) + ".jsonl")
    done = set()
    for f in RESULTS.glob("episodes*.jsonl"):
        for line in f.read_text().splitlines():
            r = json.loads(line)
            if not r.get("error"):
                done.add((r["model"], r["episode"], r["repeat"]))
    episodes = BENIGN + ATTACKS
    # interleave models so one model's quota does not stall the others
    jobs = [(m, e, rep) for rep in range(repeats) for e in episodes for m in models]
    todo = [j for j in jobs if (j[0], j[1]["id"], j[2]) not in done]
    print(f"{len(jobs)} jobs, {len(todo)} to run", flush=True)
    dead = set()
    for i, (m, e, rep) in enumerate(todo):
        if m in dead:
            continue
        t0 = time.time()
        attack = None if e["family"] == "benign" else e
        r = run_episode(m, attack, key)
        r.update({"episode": e["id"], "repeat": rep, "seconds": round(time.time() - t0, 1)})
        with OUT.open("a") as f:
            f.write(json.dumps(r) + "\n")
        pays = ", ".join(f"{p['amount']}->{p['to'][:6]}" for p in r["payments"]) or "-"
        print(f"[{i + 1}/{len(todo)}] {m:22s} {e['id']:20s} rep{rep} pays: {pays} {'ERR ' + r['error'][:80] if r['error'] else ''}", flush=True)
        if r["error"] and "daily quota" in r["error"]:
            print(f"daily quota hit for {m}; skipping it for now", flush=True)
            dead.add(m)


if __name__ == "__main__":
    main()
