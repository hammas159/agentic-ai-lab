"""Async Ollama client, cached in Redis, with bounded concurrency.

Two things this does that a plain `httpx.post` does not.

**It keeps the GPU busy.** One request at a time leaves the card at about 9% utilisation:
it spends nearly all of its time waiting for the next HTTP round trip rather than decoding.
Eight in flight takes it to ~98%. That was measured on this machine and it roughly halves
every run in this repo, so the default is a bounded pool rather than a loop.

**It shares a cache across apps.** Several of these apps ask the model literally the same
questions - the first-attempt prompt in Repair-or-Rewrite is identical to the one in Size
Curve. Keyed on `(model, prompt, temperature, seed)` in Redis, the second app pays nothing,
which is what makes clicking through ten tools on one GPU tolerable.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable

import httpx

from . import cache

OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("MODEL", "qwen2.5-coder:14b")
CONCURRENCY = int(os.environ.get("GEN_CONCURRENCY", "8"))


async def generate(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.0,
    seed: int | None = None,
    num_predict: int = 512,
    timeout: float = 240.0,
    use_cache: bool = True,
) -> str | None:
    """One completion. None only if the model could not be reached."""
    if use_cache:
        hit = await cache.get_generation(model, prompt, temperature, seed)
        if hit is not None:
            return hit

    options: dict = {"temperature": temperature, "num_predict": num_predict}
    if seed is not None:
        options["seed"] = seed
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                f"{OLLAMA}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False, "options": options},
            )
            r.raise_for_status()
            text = r.json().get("response", "")
    except (httpx.HTTPError, ValueError):
        return None

    if use_cache:
        await cache.put_generation(model, prompt, temperature, seed, text)
    return text


async def generate_many(
    prompts: list[str],
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.0,
    seeds: list[int | None] | None = None,
    num_predict: int = 512,
    concurrency: int = CONCURRENCY,
    on_progress: Callable[[int, int], Awaitable[None]] | None = None,
) -> list[str | None]:
    """Many completions, in prompt order, `concurrency` in flight."""
    seeds = seeds or [None] * len(prompts)
    sem = asyncio.Semaphore(concurrency)
    done = 0
    lock = asyncio.Lock()

    async def one(i: int) -> str | None:
        nonlocal done
        async with sem:
            out = await generate(
                prompts[i],
                model=model,
                temperature=temperature,
                seed=seeds[i],
                num_predict=num_predict,
            )
        async with lock:
            done += 1
            current = done
        if on_progress and (current % 5 == 0 or current == len(prompts)):
            await on_progress(current, len(prompts))
        return out

    return list(await asyncio.gather(*(one(i) for i in range(len(prompts)))))


async def embed(texts: list[str], model: str = "nomic-embed-text") -> list[list[float]] | None:
    """Batched embeddings. The per-item endpoint is ~100x slower when a 14B holds VRAM."""
    out: list[list[float]] = []
    try:
        async with httpx.AsyncClient(timeout=240) as client:
            for i in range(0, len(texts), 256):
                r = await client.post(
                    f"{OLLAMA}/api/embed",
                    json={"model": model, "input": texts[i : i + 256], "keep_alive": "30m"},
                )
                r.raise_for_status()
                out.extend(r.json()["embeddings"])
    except (httpx.HTTPError, ValueError, KeyError):
        return None
    return out


async def available(model: str = DEFAULT_MODEL) -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{OLLAMA}/api/tags")
            return model.split(":")[0] in r.text
    except httpx.HTTPError:
        return False
