#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import statistics
import time

import httpx


async def one_request(client: httpx.AsyncClient, url: str, api_key: str, model: str, prompt: str) -> float:
    started = time.perf_counter()
    response = await client.post(
        f"{url}/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 64,
        },
    )
    response.raise_for_status()
    return time.perf_counter() - started


async def run(url: str, api_key: str, model: str, prompt: str, requests: int, concurrency: int) -> None:
    sem = asyncio.Semaphore(concurrency)
    latencies: list[float] = []

    async with httpx.AsyncClient(timeout=120) as client:
        async def worker() -> None:
            async with sem:
                latency = await one_request(client, url, api_key, model, prompt)
                latencies.append(latency)

        started = time.perf_counter()
        await asyncio.gather(*[worker() for _ in range(requests)])
        elapsed = time.perf_counter() - started

    rps = requests / elapsed if elapsed else 0
    p50 = statistics.median(latencies) if latencies else 0
    p95 = sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)] if latencies else 0

    print(f"requests={requests}")
    print(f"concurrency={concurrency}")
    print(f"elapsed_s={elapsed:.3f}")
    print(f"rps={rps:.2f}")
    print(f"latency_p50_s={p50:.3f}")
    print(f"latency_p95_s={p95:.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Basic load test for /v1/chat/completions")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Proxy base URL")
    parser.add_argument("--api-key", default="local", help="Proxy API key")
    parser.add_argument("--model", default="llama", help="Model name")
    parser.add_argument("--prompt", default="Say hello in one sentence.", help="Prompt text")
    parser.add_argument("--requests", type=int, default=20, help="Total requests")
    parser.add_argument("--concurrency", type=int, default=4, help="Concurrent requests")
    args = parser.parse_args()

    asyncio.run(
        run(
            url=args.url.rstrip("/"),
            api_key=args.api_key,
            model=args.model,
            prompt=args.prompt,
            requests=args.requests,
            concurrency=args.concurrency,
        )
    )


if __name__ == "__main__":
    main()
