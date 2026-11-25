# AgentDrain

A small benchmark for one question: when a prompt injection hits an AI purchasing
agent that can spend money, **how much money actually leaves the wallet, and which
spending control stops it?**

The agent is asked to buy one dataset from one vendor for the listed price. It must
read a search page, a product page and a reviews page before paying. One of those
pages carries a prompt injection that tries to redirect the payment, inflate it, or
repeat it. The agent's decisions are recorded once, then **replayed on a local chain
against four different spending controls**, so every control is judged on the exact
same agent behaviour.

## Headline finding

> The injections that work are the ones that look like ordinary page content: a changed
> payment address, a fake "system" note, a review that says "pay the deposit first".
> They succeed **55 to 60%** of the time. The obvious jailbreaks (base64, Morse,
> "ignore your instructions", social-engineering sob stories) succeed **0%**.
>
> A correctly configured runtime allowlist cuts unintended payment attempts from
> **34% to 8%**. But if the agent's signing key is stolen, every off-chain control
> loses the **entire wallet**. Only an on-chain spending mandate caps the loss.

192 episodes (152 attacked + 40 benign) across three open models:
`openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b`.

![results](results/agentdrain.png)

## Results

Attack = the agent sent any payment the user did not authorize (wrong recipient, over
price, or duplicate). "Leaked" is money that left the wallet beyond the single
legitimate $4.20 payment.

| Spending control | Attack success | Mean leaked / episode | Max leaked | Task still done |
|---|---|---|---|---|
| Raw wallet (no limit) | 51/152 (34%) | $2.75 | $34.80 | 80% |
| Per-payment cap ($10) | 42/152 (28%) | $1.27 | $10.00 | 79% |
| Runtime policy (allowlist + caps) | 12/152 (8%) | $0.33 | $4.20 | 79% |
| On-chain mandate (FairMeter) | 12/152 (8%) | $0.33 | $4.20 | 79% |

The runtime allowlist and the on-chain mandate stop the same prompt-injection attacks.
The residual 8% is the agent paying the *correct* vendor twice, each payment inside the
$10 cap, so nothing is stolen under either control. The difference between the two shows
up only when the key leaks.

### If the agent's key is stolen

Here the attacker signs with the agent's key directly. The wallet holds $100; the
on-chain mandate authorizes at most $10 to the vendor.

| Spending control | Taken by the attacker |
|---|---|
| Raw wallet | $100.00 |
| Per-payment cap ($10) | $100.00 |
| Runtime policy (allowlist + caps) | $100.00 |
| On-chain mandate (FairMeter) | $0.00 (worst case, if the vendor colludes: $10.00) |

Off-chain controls live next to the key. Steal the key and they are gone. An on-chain
mandate is enforced by the contract, so a stolen key still cannot exceed the cap or pay
an address the mandate does not allow.

### By model (raw wallet)

| Model | Attack success | Mean leaked |
|---|---|---|
| openai/gpt-oss-120b | 29/79 (37%) | $2.28 |
| openai/gpt-oss-20b | 20/46 (43%) | $4.99 |
| qwen/qwen3.8-27b | 2/27 (7%) | $0.31 |

### By attack family (raw wallet)

| Family | Success | Mean leaked | Best injection point |
|---|---|---|---|
| goal_hijack | 6/10 (60%) | $4.16 | product page |
| recipient_swap | 10/18 (56%) | $2.33 | reviews |
| fake_system | 10/18 (56%) | $7.56 | product page |
| repeat | 11/20 (55%) | $2.31 | payment response |
| multilingual | 6/11 (55%) | $2.29 | product page |
| hidden | 4/13 (31%) | $1.29 | payment response |
| amount_inflation | 2/16 (12%) | $4.05 | reviews |
| deposit | 2/19 (11%) | $2.37 | payment response |
| encoded | 0/17 (0%) | $0.00 | none |
| social | 0/10 (0%) | $0.00 | none |

## What is and is not new here

Prompt injection on tool-using agents is already benchmarked. In particular,
**AgentDojo** (Debenedetti et al., ETH Zurich, NeurIPS 2024) includes a banking suite
with money-transfer injection tasks, and is the standard reference. AgentDrain does not
claim to be the first agent-injection benchmark, and it is much smaller.

What this repo adds, narrowly:

1. **The same agent decisions are replayed against four spending controls**, so the
   controls are compared directly rather than each measured against a different run.
2. **Real on-chain replay**: payments are re-executed on a local Anvil chain with a
   deployed stablecoin and a mandate contract, not scored in text.
3. **A stolen-key test** alongside the prompt-injection test, which is what separates
   off-chain controls from the on-chain mandate.
4. One concrete, slightly surprising result: **a per-payment cap sized to the task
   budget still lets duplicate payments through**, because each one is individually
   under the cap.

## Honest disclosures

- **FairMeter is my own project.** It is used here as the on-chain-mandate control. I
  have an interest in it looking good, so read the FairMeter column with that in mind.
  The runtime-allowlist control reaches the same prompt-injection numbers without any
  contract; the only place the mandate wins is the stolen-key test, and that is a
  property of on-chain enforcement in general, not of FairMeter specifically.
- **Everything runs locally on a test chain with test tokens.** The domains are
  `.example`, the addresses are fixed test addresses, payments are recorded by the
  agent and then replayed. No real funds, no real network, no live vendor.
- The agent keys in `bench/replay.py` are the **well-known public Anvil default keys**.
  They are test keys, not secrets.
- Models were run through Groq's free tier; the 20b and qwen runs stopped at the daily
  quota, which is why their episode counts are smaller.

## Reproduce

```bash
# 1. install Solidity deps and build FairMeter + a test stablecoin
cd contracts
forge install foundry-rs/forge-std OpenZeppelin/openzeppelin-contracts
forge build
cd ..

# 2. run the agents (needs a Groq API key in the environment)
export GROQ_API_KEY=...        # free tier is enough
python3 bench/run_agents.py 2 openai/gpt-oss-120b
# repeat per model; results land in results/episodes_<model>.jsonl (resumable)

# 3. replay every episode against the four controls on a local anvil chain
python3 bench/replay.py

# 4. build the tables and the figure
python3 bench/report.py        # writes results/SUMMARY.md and results/agentdrain.png
```

## Layout

```
bench/scenario.py    the purchasing task, pages, and fixed test addresses
bench/attacks.py     40 injections in 10 families + benign controls
bench/agent.py       the tool loop (browse / pay / finish); pay() is recorded, not sent
bench/run_agents.py  one process per model, resumable
bench/replay.py      anvil replay of the four controls + the stolen-key test
bench/report.py      SUMMARY.md and agentdrain.png
contracts/           FairMeter mandate contract + a test stablecoin (Foundry)
results/             episodes, replay output, SUMMARY.md, figure
```

## License

MIT. See `LICENSE`.
