<h1 align="center">agentic-ai-llm</h1>
<p align="center"><i>Ten measurement tools for local coder models, each shipped as a running product — and eleven agent-infrastructure tools underneath them.</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="python">
  <img src="https://img.shields.io/badge/apps-10-e879f9" alt="apps">
  <img src="https://img.shields.io/badge/bus-Kafka-231f20" alt="kafka">
  <img src="https://img.shields.io/badge/state-Redis-dc382d" alt="redis">
  <img src="https://img.shields.io/badge/orchestration-LangGraph-1c3c3c" alt="langgraph">
  <img src="https://img.shields.io/badge/model-qwen2.5--coder-orange" alt="model">
</p>

---

Benchmark numbers are easy to quote and hard to act on. These ten apps each answer one
question that changes what you would build: whether the bigger model earns its VRAM, when to
stop a retry loop, whether generated tests catch anything, and how much of a published score
belongs to the prompt rather than the model.

Every one is a real web application with its own visual identity, backed by a Kafka job bus,
Redis state and a worker that owns the single GPU.

## The ten

| | App | Question | Theme |
|---|---|---|---|
| 🧭 | [**Localizer**](apps/01_localizer) | which file does this issue touch? | deep ocean |
| 🧫 | [**False Accepts**](apps/02_false_accepts) | how much wrong code do three asserts let through? | crimson lab |
| 🛡 | [**Vuln Baseline**](apps/03_vuln_baseline) | can a model beat answering "safe" every time? | amber terminal |
| 📐 | [**Size Curve**](apps/04_size_curve) | where does a 5× bigger model actually pay? | violet |
| 🌿 | [**Debug Ceiling**](apps/05_debug_ceiling) | how many rounds of self-debugging are worth it? | forest, light |
| 🎯 | [**Kill Rate**](apps/06_kill_rate) | do model-written tests catch anything? | magenta |
| 🔀 | [**Repair or Rewrite**](apps/07_repair_rewrite) | patch the failure, or start over? | slate & coral, light |
| 🖋 | [**Prompt Shapes**](apps/08_prompt_shapes) | how much of a score is the wording? | teal paper, light |
| 🌡 | [**Temperature Lab**](apps/09_temperature) | where do pass@1 and pass@k diverge? | heat |
| 📜 | [**Roundtrip**](apps/10_roundtrip) | what survives code → prose → code? | sepia, light |

Ten palettes, four light and six dark, with their own typeface pairings and corner radii —
opening two of them side by side should not feel like opening the same tool twice.

## What they found

Every app ships the result it was built from. These are measured numbers, not claims.

- **BM25 collapses from 74.5% to 8.4%** depending only on whether the issue quotes the file
  path. The same 14B model scores 55.8% on that hard half when naming files freely and
  **17.5% when restricted to reranking** — its advantage is knowing the repository, not
  reading the issue. It also invents one path in five.
- **A 14B coder model scores 50.0% on Devign against a 50.4% majority baseline** — below a
  classifier that reads nothing and always answers "safe".
- **17.6% of single-point mutants survive MBPP's three asserts**, and 442 of them are
  provably wrong. Hand-verification does not fix it: the sanitized split scores 16.0%.
- **Self-debug rounds 1–2 captured 100% of the gain**; rounds 3–5 added zero tasks for 60%
  of the compute. Independently: **93.3% of first-attempt failures survive both** repair and
  rewrite.
- **The 3B already handles 75.8%** of everything either size can solve.
- **Generated tests beat the benchmark's own** — 93.4% kill rate against 85.0% — but only
  when written from the implementation. From the task description, just 16% even agree with
  the reference.
- **Describing the reference code and reimplementing from that beats MBPP's own description
  by 32.5 points.** That is a leak, not better documentation.

## Architecture

```
browser  ──POST /run──▶  FastAPI (one per app, ports 8001-8010)
                          │
                          ├─▶ Kafka  jobs.requested    partitioned by app
                          │            │
                          │            ▼
                          │         worker.py  ──▶  Ollama, 8 requests in flight
                          │            │
                          │            ├─▶ Redis  generation cache, shared by all ten
                          │            ├─▶ Redis  job state + pub/sub
                          │            └─▶ Kafka  jobs.completed   kept for a year
                          ▼
browser  ◀──SSE────────  Redis pub/sub
```

**The web process never runs a measurement.** A submit publishes and returns a job id; the
worker consumes the partition and streams ticks back.

**Why a log and not a task queue.** `jobs.completed` is the durable record of every
measurement ever run here. Re-reading it from offset zero rebuilds the results without
re-running a single generation — which matters when a run costs an hour of GPU. The history
page in every app does exactly that.

**Why one worker.** One GPU means one job at a time. Making that explicit beats letting ten
web processes each start a run and discover the constraint by thrashing VRAM. Partitioning
by app keeps a long sweep from starving a short one.

**Redis is load-bearing, not decoration.** Several apps ask the model identical questions —
the first-attempt prompt in Repair-or-Rewrite is the same one Size Curve sends. Keyed on
`(model, prompt, temperature, seed)`, the second app pays nothing. That is the difference
between clicking through ten tools on one GPU and waiting for each.

**LangGraph where the shape fits.** Debug Ceiling runs its loop as a state graph —
`generate → execute → repair → execute` with a conditional edge on the test result and the
round cap as a recursion limit — because that is what a self-debug loop is. The conditional
reads a real assertion outcome, not a model's opinion of its own work.

Everything degrades. If Kafka is down the job runs in-process and the UI says so; if Redis
is down the apps still work without caching or live progress. A demo that only runs with the
full stack up is a demo nobody runs.

## Running it

```bash
docker compose up -d          # redis + kafka (KRaft, no zookeeper)
uv sync --all-groups
python worker.py              # consumes the bus; needs Ollama
sh serve_all.sh               # ten apps on 8001-8010
```

Needs Ollama with `qwen2.5-coder:14b`, plus `:3b` for Size Curve and `nomic-embed-text` for
Localizer. MBPP, HumanEval, Devign and SWE-bench Lite load from the local Hugging Face
cache; nothing downloads at runtime.

## The eleven agent-infrastructure tools

In [`projects/`](projects). Zero runtime dependencies and zero LLM calls — each one is
built around something that turned out to be wrong.

| # | Tool | What it does |
|---|---|---|
| 01 | [**repo-cartographer**](projects/01_repo-cartographer) | Map an unfamiliar Python codebase from its AST — no embeddings, no model |
| 02 | [**test-smith**](projects/02_test-smith) | Mutation testing from the standard library: does the suite catch the change, or merely run it? |
| 03 | [**review-bot**](projects/03_review-bot) | Propose findings, then try to disprove each one. Report only what survives |
| 04 | [**migration-pilot**](projects/04_migration-pilot) | Modernise Python where the rewrite is provably equivalent, and refuse where it would change behaviour |
| 05 | [**release-captain**](projects/05_release-captain) | Release readiness scored from diff statistics, not from opinion |
| 06 | [**db-surgeon**](projects/06_db-surgeon) | Prove a migration's rollback on a throwaway copy before trusting it |
| 07 | [**compliance-auditor**](projects/07_compliance-auditor) | Stated policy checked against collected evidence. No inferred compliance |
| 08 | [**csv-analyst**](projects/08_csv-analyst) | Profile a CSV, compute only what validates, and never narrate a number that was not computed |
| 09 | [**log-detective**](projects/09_log-detective) | Extract log templates, and report what the extraction destroyed |
| 10 | [**contract-reader**](projects/10_contract-reader) | Read a licence, and cite the character span behind every claim |
| 11 | [**study-tutor**](projects/11_study-tutor) | Spaced repetition where the scheduler is arithmetic and the model only writes questions |

## The twenty business agents

In [`products/`](products), on a ports-and-adapters platform with its own five-topic Kafka
convention. Each one is measured against real data — the full table with every finding is in
[`products/README.md`](products/README.md).

| | | | |
|---|---|---|---|
| [**revenue-desk**](products/01_revenue-desk) | [**ward-sync**](products/02_ward-sync) | [**one-desk**](products/03_one-desk) | [**ledger-brain**](products/04_ledger-brain) |
| [**comms-desk**](products/05_comms-desk) | [**oncall-mate**](products/06_oncall-mate) | [**hire-desk**](products/07_hire-desk) | [**bid-desk**](products/08_bid-desk) |
| [**hermes-home**](products/09_hermes-home) | [**kyc-floor**](products/10_kyc-floor) | [**watchtower**](products/11_watchtower) | [**powerguard**](products/12_powerguard) |
| [**swarm-lab**](products/13_swarm-lab) | [**graph-clinic**](products/14_graph-clinic) | [**claims-floor**](products/15_claims-floor) | [**shelf-ops**](products/16_shelf-ops) |
| [**fleet-desk**](products/17_fleet-desk) | [**campus-ops**](products/18_campus-ops) | [**agri-desk**](products/19_agri-desk) | [**driftwatch**](products/20_driftwatch) |

**The `products/` platform and the `apps/` platform are separate and currently duplicate
each other** — worth merging or explicitly splitting before either is presented as the house
architecture.

## Limits

- **One model family, one GPU.** Nothing here says how any of it scales.
- **MBPP is mostly short functions.** The self-debug ceiling in particular may look different
  where the first attempt is closer to right.
- **Sample sizes are 20–800** depending on the app, chosen so a run finishes while you watch
  it. Large enough to separate the effects reported; not large enough for small differences.
- **Localizer ranks file paths, not file contents.** Fetching every blob would be a clone by
  another name, so its numbers are a floor for what retrieval can do.
