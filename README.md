<h1 align="center">agentic-ai-lab (Python · NiceGUI · marimo · zero dependencies)</h1>
<p align="center"><i>Eleven agent-infrastructure tools, each built around something that turned out to be wrong</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="python">
  <img src="https://img.shields.io/badge/projects-11-brightgreen" alt="projects">
  <img src="https://img.shields.io/badge/tests-376-success" alt="tests">
  <img src="https://img.shields.io/badge/runtime%20deps-0-brightgreen" alt="zero dependencies">
  <img src="https://img.shields.io/badge/LLM%20calls-0-informational" alt="no llm">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="license"></a>
</p>

---

Eleven standalone tools for the parts of agent work that are not the agent: mapping an
unfamiliar codebase, proving a test suite would catch a bug, deciding whether a release
is safe, checking that a rollback actually rolls back.

Every one is built around a **finding** rather than a feature, and every number below was
produced on a machine, on real data, by the code in this repository.

## The eleven

| # | Project | What it found |
|---|---|---|
| **01** | [repo-cartographer](projects/01_repo-cartographer) | **99%** of a repo's internal calls resolve from the AST alone — median over 29 repos, 88,166 lines, no embeddings |
| **02** | [test-smith](projects/02_test-smith) | **62 deliberate bugs survived** on lines the suite had just executed. Suites check control flow (86% caught) and barely check values (31%) |
| **03** | [review-bot](projects/03_review-bot) | **24%** of findings it would have posted were wrong; for `bare-except` and `swallowed-exception`, **100%** were |
| **04** | [migration-pilot](projects/04_migration-pilot) | The documented fix for `datetime.utcnow()` **raises TypeError at runtime**. 12 behavioural edits against 7 mechanical across 1,675 files |
| **05** | [release-captain](projects/05_release-captain) | The largest commit changed **47,743 lines in 5 files**; the third largest, 5,442 lines in 693. No single metric ranks both correctly |
| **06** | [db-surgeon](projects/06_db-surgeon) | **3 of 10** migrations restore the schema exactly and still lose data. A schema-diff review passes all three |
| **07** | [compliance-auditor](projects/07_compliance-auditor) | The most confidently stated convention is the least followed: **9 of 33** repos (27%) |
| **08** | [csv-analyst](projects/08_csv-analyst) | 19,500 rows with a non-numeric invoice number are **100% cancellations**; a numeric cast overstates revenue by **8.68%** |
| **09** | [log-detective](projects/09_log-detective) | 1.1x → 3.7x compression **destroyed 655 of ~1,000** distinct messages. Templates seen once fell from 908 to 150 |
| **10** | [contract-reader](projects/10_contract-reader) | A keyword classifier reads the **Python licence as GPL**, because the PSF licence names the GPL in a choice-of-law clause |
| **11** | [study-tutor](projects/11_study-tutor) | One lapse sends an SM-2 card from a **238-day interval back to tomorrow**; FSRS resumes at 18 |

## Three things that are true of all eleven

**Zero runtime dependencies.** Every `pyproject.toml` says `dependencies = []`. Not a
constraint imposed up front — every project started with a planned dependency and
dropped it after trying it. tree-sitter lost to `ast`. mutmut and coverage.py lost to
`ast` + `sys.settrace`. sqlglot and Alembic lost to `sqlite3`. DuckDB, pandas and
matplotlib lost to `sqlite3`, `csv` and hand-written SVG. GitPython lost to
`git log --numstat`. ast-grep lost to text-slice edits.

**Zero LLM calls.** The original plan gave most of these a model. They shed it because
the deterministic version was better *and checkable*: `csv-analyst` narrates only
validated numbers, `review-bot` has no model precisely so it cannot confirm a finding it
never checked, `study-tutor` has a test asserting the same card schedules identically
twice — the property a model cannot offer.

**Real data, named.** 29 repositories and 88,166 lines of Python; 1.07M rows of UCI
Online Retail II; 1,005 log lines captured from real test runs on this machine; 75
licence files and 128 KB of legal text; 279 commits of real git history.

## The through-line: the denominator is usually the bug

Four of the eleven found the same shape of error, in four different fields.

- `repo-cartographer` reported **8%** call resolution until builtins were removed from
  the denominator. The real figure is **99%**.
- `test-smith` conflated "no test reaches this code" with "a test reaches it and does not
  check it". Only the second is about test quality.
- `review-bot`'s first run reported **96% retracted**, which was one badly scoped rule
  supplying 8,906 of 9,183 defeats. The honest number is **24%**.
- `release-captain`'s ranking-agreement table read 75–80% until it was compared against
  chance — with 8 commits and a top-5 list, chance alone gives **62%**.

Each is written up in its own README as the mistake it was, not quietly corrected.

## Running them

See **[RUNNING.md](RUNNING.md)**. Short version:

- **Nine of eleven need no UI.** They answer a question and print it.
- **Three serve a page from the standard library** with nothing installed —
  `release-captain` (:8090), `compliance-auditor` (:8100), `contract-reader` (:8115).
- Four have a UI needing `npm install` (Astro, SolidJS, Vue 3, Remix) and four need one
  Python extra (NiceGUI, Marimo, Reflex, Panel). All optional; the CLI is complete.

```bash
cd projects/01_repo-cartographer && uv run pytest -q
uv run cartographer compare D:\github
```

Each project is standalone: its own `pyproject.toml`, its own tests, its own README. They
share no code and no imports, deliberately.

## What this repository does NOT do

- **It is not an agent framework**, and nothing here competes with LangGraph or CrewAI.
  These are the deterministic tools an agent would call.
- **No model, anywhere.** If you were looking for prompt engineering, it is not here.
- **Python only**, and several projects say so more specifically — `db-surgeon` runs
  SQLite and is explicit that SQLite is not Postgres.
- **Findings are from one corpus.** Every number is real and every number came from this
  machine's repositories; a different codebase would produce different ones.
- **Nothing here is tuned.** FSRS uses published weights, `release-captain`'s risk
  weights are declared rather than fitted, and both READMEs say why: there is no labelled
  outcome data to tune against.

## Problems hit while building these

The per-project READMEs carry the full list. The ones worth reading first:

- **`compliance-auditor`** — three of its own bugs produced plausible-looking findings
  before being caught, including a regex whose `\s` spanned newlines and reported `sys`
  and `from` as imported modules.
- **`migration-pilot`** — a grep suggested dozens of files needed modernising and the
  scanner found nothing. The scanner was right; the files import the names and never
  subscript them.
- **`log-detective`** — the first corpus was 201 lines and showed a smooth curve with no
  cliff. A compression table over 201 lines proves nothing.
- **`contract-reader`** — fixing one misclassification took two changes, because there
  were two causes.

## Layout

```
projects/
  01_repo-cartographer   map a codebase from its AST
  02_test-smith          mutation testing from the standard library
  03_review-bot          propose, then try to disprove, then report
  04_migration-pilot     modernise what is equivalent, refuse what is not
  05_release-captain     release readiness from diff statistics
  06_db-surgeon          prove a rollback instead of reading it
  07_compliance-auditor  stated policy against collected evidence
  08_csv-analyst         refuse to coerce, and say what a cast would delete
  09_log-detective       report what template extraction destroyed
  10_contract-reader     cite the span, or drop the claim
  11_study-tutor         the scheduler is arithmetic, not a prompt
RUNNING.md               which need a UI, which run on localhost, which need npm
```
