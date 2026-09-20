# agentplatform

The shared platform the twenty products in [`../`](../) sit on.

**Nothing is required to import this package or to run its tests** — no broker, no
database, no model, no framework. FastAPI, LangGraph and ollama are optional extras behind
lazy imports.

```
PYTHONPATH=src python -m pytest -q      # 96 passed
```

## What is here

| Module | What it decides | Why it is not in a prompt |
|---|---|---|
| `topics` | the five topics per product, and which partition a key lands on | per-entity ordering is a correctness property, not a hint |
| `keys` | the six Redis keys and the TTL each must carry | a key without a TTL is a leak; a lock without one is an outage |
| `authority` | which agent may write which field | an agent that *can* write the record will eventually write something wrong |
| `gate` | which claims reach the user | a model cannot be asked to mark its own fabrications |
| `admission` | how many model workers this GPU can run | the bus has twelve partitions; the card has one model |
| `memory` | which facts are persisted | ungated writes are why long-lived agents rot |
| `ports` | the bus, store and cache as protocols, with in-memory implementations | a product must run end to end in a test |
| `models` | which model a product actually gets, and which one it was | nothing waits on a download |
| `llm` | the model interface, a fake, and the cache and budget wrappers | a test must not be able to reach a real model by accident |
| `graphs` | the graph runtime: five shapes, checkpointed interrupts | two measured findings are enforced, not suggested |
| `api` | the four things a person does with an agent product | — |

## The graph runtime, and LangGraph

A graph is declared as data — nodes, edges, and which node is an interrupt. It runs today on
`graphs.run()` with nothing installed, and `graphs.to_langgraph()` compiles the same
declaration onto LangGraph once the extra is present. A product describes its graph once
either way.

Two findings from `langgraph-lab` are enforced in the runtime rather than written in a
prompt:

- **A fan-out always hands the next node the branch status list.** A silently failed branch
  was disclosed 0% of the time by a default synthesis prompt, so `branch_status` and
  `branches_failed` are in the state and cannot be missed.
- **A resumed run restarts at the node *after* the interrupt.** A naive pause-and-reinvoke
  wastes exactly one generation per approval — a flat 50% overhead for identical output.
  There is a test asserting the drafting call happens once across a pause and a resume.

`graphs.loop()` caps revision at two iterations by default, with an **external** done
predicate, because doubling a critique-revise loop from three to six changed nothing on
every task measured and self-reported completion quit on the first draft every time.

## Nothing waits on a download

`models.resolve(role, installed)` hands back the best installed model for a capability and
records which one it was. A product asking for `general` gets `qwen2.5:7b-instruct` today
and `qwen2.5:14b-instruct` once that lands — and `Resolved.note` says which, so a later run
is a comparison row rather than an overwrite. `models.comparison_pending()` names the model
whose arrival would be worth re-running for.

## Three decisions worth the space

**Partitioning uses `zlib.crc32`, not the built-in `hash`.** Python salts `hash` per
process, so a consumer restarted tomorrow maps the same key to a different partition and
silently loses the per-entity ordering the whole design rests on. There is a test pinning
this.

**Authority is default-deny.** Anything not explicitly granted is `NEVER`, so a column added
to the schema next month is closed rather than open.

**The gate checks for invented receipts, not just missing ones.** A claim citing `src_z99`
when no such receipt was issued looks exactly like a real citation to a human reviewer.

And one more, in `llm.Recorded`: an unscripted prompt **raises**. A fake that answers
plausibly is how a test stops testing anything, and it is also how a test suite quietly
starts calling a real model.

## What it does NOT do

- **No Kafka, Redis or Postgres client.** `ports.py` defines the protocols; binding them is
  a deployment concern and the `infra` extra names the libraries.
- **No LLM call anywhere in the tests.** `llm.Ollama` is the only thing that would, and it
  is never constructed in one.
- **No async.** The runtime is synchronous. FastAPI's handlers are the only async surface
  and they do not need to be.
- **No retry, backoff or circuit breaking.** That is the client library's job.
- **No scheduler.** `Runtime.drain()` is one worker pass; what calls it in production is a
  supervisor, not this package.

## Problems hit while building this

- `hash()` was the obvious partitioner and is wrong in a way that only shows up under a
  rolling restart. Caught while writing the test for it, not while writing the code.
- The first `lock()` took any TTL. A ten-minute lock is not a longer lock, it is an outage,
  so the builder refuses one above five minutes and points at heartbeat renewal.
- Admission originally counted a refused request against the in-flight slots, so a tenant
  over budget also consumed capacity. There is an explicit test for that now.
- `Runtime.submit()` first ran the graph inline and returned the result, which was simpler
  and defeated the entire purpose of the bus. It publishes and returns; `drain()` runs it.

## Input / Output

No results yet — this is the platform, not a product. The number it owes is the measured
tokens/sec of a 14B on this card, which sets `kv_cache_mb_per_slot` and therefore
`Gpu.max_slots`. Until that is measured here, the 3000 MB in the tests is a placeholder and
is labelled as one.
