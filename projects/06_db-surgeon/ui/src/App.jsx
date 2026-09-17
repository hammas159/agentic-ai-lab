import { createSignal, For, Show } from "solid-js";

const SAMPLE_SCHEMA = `CREATE TABLE users (
    id       INTEGER PRIMARY KEY,
    email    TEXT NOT NULL,
    nickname TEXT,
    status   TEXT NOT NULL DEFAULT 'active'
);`;

const SAMPLE_SEED = `INSERT INTO users (id, email, nickname, status) VALUES
    (1, 'ann@example.com', 'ann', 'active'),
    (2, 'bob@example.com', 'bob', 'active'),
    (3, 'cat@example.com', NULL,  'disabled');`;

const SAMPLE_UP = `ALTER TABLE users DROP COLUMN nickname;`;
const SAMPLE_DOWN = `ALTER TABLE users ADD COLUMN nickname TEXT;`;

function Verdict(props) {
  const tone = () => {
    if (props.result.error) return "bad";
    if (props.result.safe) return "good";
    return props.result.data_restored ? "warn" : "bad";
  };
  return <span class={`verdict ${tone()}`}>{props.result.verdict}</span>;
}

/** The two checks side by side. The whole argument of the tool is that these
 *  can disagree, so they are never collapsed into one indicator. */
function Comparison(props) {
  const r = () => props.result;
  return (
    <div class="grid">
      <div class={`panel ${r().schema_equivalent ? "good" : "bad"}`}>
        <div class="k">Schema</div>
        <div class="v">{r().schema_equivalent ? "restored" : "not restored"}</div>
        <Show when={r().columns_reordered?.length}>
          <div class="note">
            columns came back in a different order: {r().columns_reordered.join(", ")}
          </div>
        </Show>
        <Show when={r().columns_lost?.length}>
          <div class="note">missing: {r().columns_lost.join(", ")}</div>
        </Show>
      </div>
      <div class={`panel ${r().data_restored ? "good" : "bad"}`}>
        <div class="k">Data</div>
        <div class="v">{r().data_restored ? "restored" : "lost"}</div>
        <Show when={!r().data_restored}>
          <div class="note">
            {r().rows_lost} row(s) lost. A review comparing only schemas would call
            this migration reversible.
          </div>
        </Show>
      </div>
    </div>
  );
}

export default function App() {
  const [schema, setSchema] = createSignal(SAMPLE_SCHEMA);
  const [seed, setSeed] = createSignal(SAMPLE_SEED);
  const [up, setUp] = createSignal(SAMPLE_UP);
  const [down, setDown] = createSignal(SAMPLE_DOWN);
  const [result, setResult] = createSignal(null);
  const [busy, setBusy] = createSignal(false);

  async function check() {
    setBusy(true);
    setResult(null);
    try {
      const response = await fetch("/api/check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          schema: schema(),
          seed: seed(),
          up: up(),
          down: down(),
        }),
      });
      setResult(await response.json());
    } catch (err) {
      setResult({ error: String(err), verdict: "could not reach the server" });
    } finally {
      setBusy(false);
    }
  }

  const field = (label, value, setter, rows) => (
    <label class="field">
      <span>{label}</span>
      <textarea rows={rows} value={value()} onInput={(e) => setter(e.currentTarget.value)} />
    </label>
  );

  return (
    <main>
      <header>
        <h1>db-surgeon</h1>
        <p>
          Runs <code>up</code> then <code>down</code> on a throwaway copy and compares
          both the schema and the rows. A rollback that restores the schema and loses
          the data is the case this exists to catch.
        </p>
      </header>

      <div class="editors">
        {field("Starting schema", schema, setSchema, 8)}
        {field("Starting rows", seed, setSeed, 8)}
        {field("up", up, setUp, 5)}
        {field("down", down, setDown, 5)}
      </div>

      <div class="actions">
        <button onClick={check} disabled={busy()}>
          {busy() ? "Running..." : "Run the round trip"}
        </button>
        <Show when={result()}>
          <Verdict result={result()} />
        </Show>
      </div>

      <Show when={result()?.error}>
        <pre class="error">{result().error}</pre>
      </Show>

      <Show when={result() && !result().error}>
        <Comparison result={result()} />

        <h2>What the static rules said</h2>
        <table>
          <thead>
            <tr>
              <th>Category</th>
              <th>Operation</th>
              <th>Target</th>
              <th>Why</th>
            </tr>
          </thead>
          <tbody>
            <For each={result().up}>
              {(op) => (
                <tr>
                  <td>
                    <span class={`pill ${op.category}`}>{op.category}</span>
                  </td>
                  <td class="mono">{op.kind}</td>
                  <td class="mono">{op.target}</td>
                  <td class="why">{op.reason}</td>
                </tr>
              )}
            </For>
          </tbody>
        </table>

        <Show when={result().disagreements?.length}>
          <div class="disagree">
            <strong>The static rules and the round trip disagree</strong>
            <For each={result().disagreements}>{(d) => <div>{d}</div>}</For>
            <div class="note">
              Where they differ the round trip is right, because it executed. A rule
              that mispredicts is a defect here, so it is shown rather than hidden.
            </div>
          </div>
        </Show>
      </Show>
    </main>
  );
}
