"""Vuln Baseline — can a coder model beat answering "safe" every time?

Devign is a standard C vulnerability-detection benchmark and published accuracies cluster
around 62%. The number almost never printed beside them is the majority baseline: the test
split is 1477 safe to 1255 vulnerable, so a classifier that reads no code and always answers
SAFE scores **54.1%**. That leaves eight points of headroom, which is a narrow target.

Measured here on 800 rows: `qwen2.5-coder:14b` scores **50.0%**, which is 0.4 points *below*
the constant. It answered VULNERABLE 437 times out of 800 against a true rate of 50.4% and
was right at about the rate a coin would be. That is not detecting vulnerabilities badly -
it is not detecting them.

The second column removes the rows this dataset is known to duplicate with conflicting
labels. It moves accuracy by a tenth of a point, which settles the convenient excuse: the
label noise is real and far too rare to explain anybody's number.
"""

from __future__ import annotations

import glob
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from apps._platform import model  # noqa: E402
from apps._platform.base import Field, create_app  # noqa: E402

HERE = Path(__file__).resolve().parent
SLUG = "vuln-baseline"

PROMPT = """You are auditing C code for security vulnerabilities.

```c
{code}
```

Does this function contain a security vulnerability?

Answer with exactly one word: VULNERABLE or SAFE.
"""

_WORD = re.compile(r"\b(VULNERABLE|SAFE)\b", re.IGNORECASE)


def _load_devign(split: str = "test"):
    import pandas as pd

    roots = [
        os.environ.get("HF_HUB_CACHE"),
        (os.environ.get("HF_HOME") or "") + "/hub",
        str(Path.home() / ".cache" / "huggingface" / "hub"),
    ]
    for root in roots:
        if not root:
            continue
        hits = sorted(
            glob.glob(
                f"{root}/datasets--google--code_x_glue_cc_defect_detection"
                f"/snapshots/*/data/{split}-*.parquet"
            )
        )
        if hits:
            return pd.read_parquet(hits[0])
    raise FileNotFoundError("Devign not in the local Hugging Face cache")


def _score(pairs: list[tuple[bool, bool]]) -> dict:
    tp = sum(1 for p, a in pairs if p and a)
    tn = sum(1 for p, a in pairs if not p and not a)
    fp = sum(1 for p, a in pairs if p and not a)
    fn = sum(1 for p, a in pairs if not p and a)
    n = len(pairs) or 1
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    majority = max(sum(1 for _, a in pairs if a), sum(1 for _, a in pairs if not a)) / n
    return {
        "n": len(pairs), "accuracy": (tp + tn) / n, "majority": majority,
        "precision": prec, "recall": rec,
        "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "said_vulnerable": tp + fp,
    }


async def runner(params: dict, emit) -> dict:
    limit = int(params.get("limit", 120))
    frame = _load_devign("test")
    take = min(limit, len(frame))
    await emit(0, take, f"{len(frame)} rows in the Devign test split, classifying {take}")

    codes = [frame["func"].iloc[i][:6000] for i in range(take)]
    labels = [bool(frame["target"].iloc[i]) for i in range(take)]

    async def progress(done: int, total: int) -> None:
        await emit(done, total, f"{done}/{total} classified")

    raws = await model.generate_many(
        [PROMPT.format(code=c) for c in codes],
        num_predict=8,
        on_progress=progress,
    )

    pairs: list[tuple[bool, bool]] = []
    unparsed = 0
    for raw, actual in zip(raws, labels, strict=True):
        m = _WORD.search(raw or "")
        if not m:
            unparsed += 1
            continue
        pairs.append((m.group(1).upper() == "VULNERABLE", actual))

    if not pairs:
        raise ValueError("no parsable answers from the model")

    full = _score(pairs)
    return {
        "rows": take,
        "unparsed": unparsed,
        "full": full,
        "beats_baseline": full["accuracy"] - full["majority"],
        "said_vulnerable_rate": full["said_vulnerable"] / full["n"],
        "true_vulnerable_rate": sum(1 for _, a in pairs if a) / full["n"],
    }


ABOUT = """
<p>One C function per prompt, temperature 0, answer forced to a single word.</p>
<p>The point is the column nobody prints: <b>Devign's majority baseline is 54.1%</b> on the
full test split. Published accuracies cluster near 62%, so the entire headroom of this
benchmark is about eight points.</p>
<p>On 800 rows a 14B coder model scored <b>50.0%</b> — 0.4 points below answering SAFE every
time — while saying VULNERABLE 55% of the time against a true rate of 50.4%.</p>
<p>This does not say a fine-tuned classifier cannot beat the baseline; published ones do,
narrowly. It says a general-purpose coder model prompted for the task performs at chance,
and that a benchmark this tight deserves a baseline printed next to every reported gain.</p>
"""

app = create_app(
    slug="vuln-baseline",
    icon="🛡",
    runner=runner,
    fields=[
        Field("limit", "Functions to classify", default=120, min=20, max=800,
              hint="from the Devign test split; one model call each"),
    ],
    result_template="result.html",
    about=ABOUT,
    templates_dir=HERE / "templates",
)
