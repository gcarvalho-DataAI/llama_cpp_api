from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import respx
from fastapi.testclient import TestClient
from httpx import Response

import app.main as main


def _reset_state() -> None:
    main.auth._keys.clear()  # type: ignore[attr-defined]
    main.auth._keys["test-key"] = "test-client"  # type: ignore[attr-defined]
    main.rate_limiter.limit_per_minute = 120
    main.rate_limiter._buckets.clear()  # type: ignore[attr-defined]

    main.metrics.requests_total.clear()
    main.metrics.request_latency_sum.clear()
    main.metrics.request_latency_count.clear()
    main.metrics.upstream_retries_total.clear()
    main.metrics.upstream_latency_sum.clear()
    main.metrics.upstream_latency_count.clear()
    main.metrics.upstream_errors_total.clear()
    main.metrics.rate_limited_total = 0
    main.model_router._upstreams = {}  # type: ignore[attr-defined]


client = TestClient(main.app)


def setup_function() -> None:
    _reset_state()


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_auth_required_for_v1_routes() -> None:
    response = client.get("/v1/models")
    assert response.status_code == 401


@respx.mock
def test_chat_completion_success() -> None:
    route = respx.post(f"{main.settings.llama_cpp_base_url}/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={"id": "chatcmpl-1", "choices": [{"message": {"role": "assistant", "content": "ok"}}]},
        )
    )

    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-key"},
        json={
            "model": "llama",
            "messages": [{"role": "user", "content": "hello"}],
            "temperature": 0.2,
        },
    )

    assert route.called
    assert response.status_code == 200
    assert response.headers.get("x-request-id")
    assert response.json()["choices"][0]["message"]["content"] == "ok"


@respx.mock
def test_retry_then_success() -> None:
    route = respx.get(f"{main.settings.llama_cpp_base_url}/v1/models").mock(
        side_effect=[Response(503, json={"error": "busy"}), Response(200, json={"data": []})]
    )

    response = client.get("/v1/models", headers={"Authorization": "Bearer test-key"})

    assert route.call_count == 2
    assert response.status_code == 200


@respx.mock
def test_rate_limit() -> None:
    main.rate_limiter.limit_per_minute = 1
    respx.post(f"{main.settings.llama_cpp_base_url}/v1/embeddings").mock(
        return_value=Response(200, json={"data": [{"embedding": [0.1, 0.2], "index": 0}]})
    )

    payload = {"model": "llama", "input": ["one"]}
    ok = client.post("/v1/embeddings", headers={"Authorization": "Bearer test-key"}, json=payload)
    blocked = client.post("/v1/embeddings", headers={"Authorization": "Bearer test-key"}, json=payload)

    assert ok.status_code == 200
    assert blocked.status_code == 429
    assert blocked.headers.get("retry-after")


def test_validation_error() -> None:
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-key"},
        json={"model": "llama"},
    )
    assert response.status_code == 422


def test_metrics() -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    text = response.text
    assert "proxy_requests_total" in text
    assert "proxy_rate_limited_total" in text
