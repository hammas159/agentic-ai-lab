# Twenty products

Scaffolds for twenty complete multi-agent products. Each is a browser UI over a real API,
over a real event bus, over a real database, driven by a local instruct model under
LangGraph orchestration, with a named hallucination gate that can be measured.

Distinct from [`../projects`](../projects), which holds eleven finished single-purpose
tools. These are products: several agents, a bus, a store, an approval loop, a UI.

**Status.** The shared platform is built: ports, model resolution, the LLM interface, the
graph runtime and the HTTP surface. **`01_revenue-desk` runs end to end** — HTTP in, onto
the bus, drained by a worker, paused for approval, resumed without regenerating, HTTP out.
The other nineteen have their deterministic core written and tested and copy that wiring.
The full design for each — agent roster, topics, Redis keys, schema, UI, demo data — is in
its own README and in [`../../PRODUCT-PLAN.md`](../../PRODUCT-PLAN.md).

```
cd products/platform         && python -m pytest -q     # 97 passed
cd products/01_revenue-desk  && python -m pytest -q     # 21 passed
```

**340 tests, all passing, with no broker, no database, no model and no network.** That is
deliberate: the parts of these products that must be correct are the parts a model is not
allowed to touch, and those are testable offline today.

## The twenty

| # | Product | Domain | The number it exists to produce |
|---|---|---|---|
| [01](01_revenue-desk) | **revenue-desk** | CRM and lead engine | How often an agent update reverts a human's correction |
| [02](02_ward-sync) | **ward-sync** | Hospital operations | How often a discharge summary names a discontinued drug |
| [03](03_one-desk) | **one-desk** | Social presence | Token overlap between the four "per-platform" variants |
| [04](04_ledger-brain) | **ledger-brain** | SME back office | Matcher accuracy on the equal-amount subset |
| [05](05_comms-desk) | **comms-desk** | Email and meetings | Duplicate rate when one promise arrives twice |
| [06](06_oncall-mate) | **oncall-mate** | Incident command | Suspect accuracy against log-template compression ratio |
| [07](07_hire-desk) | **hire-desk** | Recruitment | Score delta, same CV identified versus redacted |
| [08](08_bid-desk) | **bid-desk** | Tenders | Mandatory-item recall, LLM versus regex and a rulebook |
| [09](09_hermes-home) | **hermes-home** | Personal agent | Hard-constraint survival at 50 turns, gated versus not |
| [10](10_kyc-floor) | **kyc-floor** | Onboarding and AML | Alias recall on the sanctions lists, and the FP load with it |
| [11](11_watchtower) | **watchtower** | Security posture | False-positive rate before and after the backport table |
| [12](12_powerguard) | **powerguard** | Machine custodian | Work lost per outage, before and after |
| [13](13_swarm-lab) | **swarm-lab** | Scaling study | The N beyond which more agents means less success |
| [14](14_graph-clinic) | **graph-clinic** | Clinical evidence | Graph traversal against a plain hybrid baseline |
| [15](15_claims-floor) | **claims-floor** | Insurance claims | How often retrieval returns a superseded policy wording |
| [16](16_shelf-ops) | **shelf-ops** | Marketplace ops | Realised margin, one price authority versus two agents |
| [17](17_fleet-desk) | **fleet-desk** | Dispatch | How much worse a model's route is than the solver's |
| [18](18_campus-ops) | **campus-ops** | Education admin | Clashes per published timetable, before and after |
| [19](19_agri-desk) | **agri-desk** | Crop advisory | False-alarm rate, variants collapsed versus not |
| [20](20_driftwatch) | **driftwatch** | Doc drift | Share of documentation claims a machine can settle |

## The shared platform

[`platform/`](platform) holds the eleven things every product needs, none of which needs a
model to be correct: the five-topic convention and stable partitioning, the six Redis keys
with their TTLs, default-deny write authority, the grounding gate, GPU admission control,
contradiction-gated memory, the bus/store/cache ports, model resolution, the LLM interface,
the graph runtime and the HTTP surface. Build on it rather than rebuilding it twenty times.

Four of its decisions are worth knowing before reading any product:

- **Partitioning uses `zlib.crc32`, not the built-in `hash`,** which Python salts per
  process. A consumer restarted tomorrow would otherwise map the same key to a different
  partition and silently lose per-entity ordering.
- **Authority is default-deny**, so a column added to a schema next month is closed rather
  than open.
- **The gate catches invented receipts, not just missing ones.** A claim citing `src_z99`
  when no such receipt was issued looks exactly like a real citation to a reviewer.
- **`llm.Recorded` raises on an unscripted prompt.** A fake that answers plausibly is how a
  test stops testing anything — and how a suite quietly starts calling a real model.

## LangChain, LangGraph and the API layer

A graph is declared as data — nodes, edges, and which node is an interrupt. It runs today on
`graphs.run()` with nothing installed, and `graphs.to_langgraph()` compiles the same
declaration onto LangGraph once that extra is present. A product describes its graph once
either way, so **LangGraph is a deployment choice rather than a rewrite**.

Two measured findings are enforced in the runtime rather than written into a prompt:

- **A fan-out always hands the next node the branch status list.** A silently failed branch
  was disclosed 0% of the time by a default synthesis prompt, so `branch_status` and
  `branches_failed` are in the state and cannot be missed.
- **A resumed run restarts at the node *after* the interrupt.** A naive pause-and-reinvoke
  wastes exactly one generation per approval — a flat 50% overhead for identical output.

`api.Runtime` is the worker and the write path; `api.create_app()` is FastAPI over it. Four
routes, because there are four things a person does with an agent product: start work, watch
it, approve what it paused on, read the audit trail. **`/intake` publishes and returns** —
it does not run the graph, which is the entire argument for the bus.

`01_revenue-desk` is the worked example: every graph shape appears in it exactly once, and
there is a test asserting that.

## Nothing waits on a download

`models.resolve(role, installed)` hands back the best installed model for a capability and
records which one it was. A product asking for `general` gets `qwen2.5:7b-instruct` today and
`qwen2.5:14b-instruct` once that lands, and `Resolved.note` says which — so a later run is a
comparison row rather than an overwrite.

## Running the infrastructure

`docker-compose.yml` brings up Postgres 16, Redis 7 and Redpanda (Kafka-compatible, one
binary, far lighter on this box). The model server is **not** in the compose file: ollama
runs on the host, because it needs the GPU.

```
docker compose up -d
```

None of the tests need any of it.

## Why the consumer group is smaller than the partition count

One card, 16 GB, one model instance. A six-agent workflow is six *sequential* generations,
so the topic can have twelve partitions while the consumer group that calls the model has
two. `platform/admission.py` computes that from VRAM rather than leaving it to a config
file someone will copy from a blog post.

This is also the whole reason the bus is load-bearing rather than decorative: it lets the
UI accept two hundred requests while the GPU serves them at its own pace, and it survives a
worker dying mid-generation.

## Standing constraints

- **Nothing here waits on a 14B.** Every product must be demonstrable on
  `qwen2.5:7b-instruct`, with a larger model added later as a comparison row — the pattern
  the model-comparison work already uses. A product whose demo cannot run today is not on
  the critical path.
- **Every README carries "what it does NOT do" and "problems hit while building this".**
- **Every README also says where Kafka is load-bearing and where it is not.** Bolting a bus
  onto something that does not need one is the commonest way this kind of product reads as
  unserious.
- **No number appears in a README that was not produced on a machine.** Every product's
  Input/Output section currently says it has produced none, because it has not.
- **Findings over features.** Each product names the number it exists to produce, and ships
  that number even when it contradicts the product.
