from __future__ import annotations

import json
import logging
import time
import uuid
import asyncio
from typing import AsyncIterable

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse

from app.auth import ApiKeyAuth
from app.config import settings
from app.metrics import MetricsRegistry
from app.rate_limit import SlidingWindowRateLimiter
from app.routing import ModelRouter
from app.schemas import ChatCompletionRequest, CompletionRequest, EmbeddingsRequest

app = FastAPI(title="llama.cpp OpenAI-compatible proxy", version="0.2.0")

if settings.cors_allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger("llama_cpp_proxy")

auth = ApiKeyAuth()
rate_limiter = SlidingWindowRateLimiter(settings.rate_limit_rpm)
metrics = MetricsRegistry()
model_router = ModelRouter()

RETRIABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _timeout(read_s: float) -> httpx.Timeout:
    return httpx.Timeout(
        connect=settings.connect_timeout_s,
        read=read_s,
        write=read_s,
        pool=settings.connect_timeout_s,
    )


def _request_id(request: Request) -> str:
    existing = request.headers.get("x-request-id")
    if existing and existing.strip():
        return existing.strip()
    return uuid.uuid4().hex


def _client_ip(request: Request) -> str:
    client = request.client
    return client.host if client else "unknown"


def _log_event(event: str, **kwargs: object) -> None:
    payload = {"event": event, **kwargs}
    logger.info(json.dumps(payload, ensure_ascii=True))


def _proxy_headers(request_id: str) -> dict[str, str]:
    return {"x-request-id": request_id}


def _retry_wait(attempt: int) -> float:
    return settings.retry_backoff_s * (2**attempt)


async def _post_json_with_retry(
    *,
    base_url: str,
    path: str,
    payload: dict,
    timeout: httpx.Timeout,
    request_id: str,
) -> tuple[int, bytes, str]:
    target_url = f"{base_url}{path}"

    for attempt in range(settings.max_retries + 1):
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                upstream = await client.post(
                    target_url,
                    json=payload,
                    headers=_proxy_headers(request_id),
                )
            latency = time.monotonic() - started
            metrics.record_upstream_latency(path, latency)

            if upstream.status_code in RETRIABLE_STATUS_CODES and attempt < settings.max_retries:
                metrics.record_upstream_retry(path)
                await _sleep_retry(attempt)
                continue

            content_type = upstream.headers.get("content-type", "application/json")
            return upstream.status_code, upstream.content, content_type
        except httpx.TimeoutException as exc:
            metrics.record_upstream_error(path)
            if attempt < settings.max_retries:
                metrics.record_upstream_retry(path)
                await _sleep_retry(attempt)
                continue
            raise HTTPException(status_code=504, detail=f"Upstream timeout on {path}") from exc
        except httpx.RequestError as exc:
            metrics.record_upstream_error(path)
            if attempt < settings.max_retries:
                metrics.record_upstream_retry(path)
                await _sleep_retry(attempt)
                continue
            raise HTTPException(status_code=502, detail=f"Upstream request failed on {path}") from exc

    raise HTTPException(status_code=502, detail=f"Failed to reach upstream on {path}")


async def _post_stream_with_retry(
    *,
    base_url: str,
    path: str,
    payload: dict,
    timeout: httpx.Timeout,
    request_id: str,
) -> tuple[httpx.AsyncClient, httpx.Response]:
    target_url = f"{base_url}{path}"

    for attempt in range(settings.max_retries + 1):
        started = time.monotonic()
        client = httpx.AsyncClient(timeout=timeout)
        try:
            req = client.build_request(
                "POST",
                target_url,
                json=payload,
                headers=_proxy_headers(request_id),
            )
            upstream = await client.send(req, stream=True)
            metrics.record_upstream_latency(path, time.monotonic() - started)

            if upstream.status_code in RETRIABLE_STATUS_CODES and attempt < settings.max_retries:
                metrics.record_upstream_retry(path)
                await upstream.aclose()
                await client.aclose()
                await _sleep_retry(attempt)
                continue

            return client, upstream
        except httpx.TimeoutException as exc:
            metrics.record_upstream_error(path)
            await client.aclose()
            if attempt < settings.max_retries:
                metrics.record_upstream_retry(path)
                await _sleep_retry(attempt)
                continue
            raise HTTPException(status_code=504, detail=f"Upstream timeout on {path}") from exc
        except httpx.RequestError as exc:
            metrics.record_upstream_error(path)
            await client.aclose()
            if attempt < settings.max_retries:
                metrics.record_upstream_retry(path)
                await _sleep_retry(attempt)
                continue
            raise HTTPException(status_code=502, detail=f"Upstream request failed on {path}") from exc

    raise HTTPException(status_code=502, detail=f"Failed to reach upstream on {path}")


async def _get_with_retry(
    *,
    base_url: str,
    path: str,
    timeout: httpx.Timeout,
    request_id: str,
) -> tuple[int, bytes, str]:
    target_url = f"{base_url}{path}"

    for attempt in range(settings.max_retries + 1):
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                upstream = await client.get(target_url, headers=_proxy_headers(request_id))
            metrics.record_upstream_latency(path, time.monotonic() - started)

            if upstream.status_code in RETRIABLE_STATUS_CODES and attempt < settings.max_retries:
                metrics.record_upstream_retry(path)
                await _sleep_retry(attempt)
                continue

            content_type = upstream.headers.get("content-type", "application/json")
            return upstream.status_code, upstream.content, content_type
        except httpx.TimeoutException as exc:
            metrics.record_upstream_error(path)
            if attempt < settings.max_retries:
                metrics.record_upstream_retry(path)
                await _sleep_retry(attempt)
                continue
            raise HTTPException(status_code=504, detail=f"Upstream timeout on {path}") from exc
        except httpx.RequestError as exc:
            metrics.record_upstream_error(path)
            if attempt < settings.max_retries:
                metrics.record_upstream_retry(path)
                await _sleep_retry(attempt)
                continue
            raise HTTPException(status_code=502, detail=f"Upstream request failed on {path}") from exc

    raise HTTPException(status_code=502, detail=f"Failed to reach upstream on {path}")


async def _sleep_retry(attempt: int) -> None:
    await asyncio.sleep(_retry_wait(attempt))


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    started = time.monotonic()
    route = request.url.path
    method = request.method
    request_id = _request_id(request)
    request.state.request_id = request_id
    client_ip = _client_ip(request)
    client_id = client_ip
    status_code = 500
    rate_remaining = settings.rate_limit_rpm

    try:
        if route.startswith("/v1/") and method != "OPTIONS":
            identity = auth.authenticate(request.headers.get("authorization"))
            client_id = identity.client_id if auth.enabled else client_ip

            decision = rate_limiter.check(client_id)
            if not decision.allowed:
                metrics.record_rate_limited()
                response = JSONResponse(
                    status_code=429,
                    content={"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}},
                    headers={
                        "retry-after": str(decision.retry_after_s),
                        "x-ratelimit-limit": str(settings.rate_limit_rpm),
                        "x-ratelimit-remaining": "0",
                    },
                )
                response.headers["x-request-id"] = request_id
                metrics.record_request(route, method, response.status_code, time.monotonic() - started)
                _log_event(
                    "request_completed",
                    request_id=request_id,
                    client_id=client_id,
                    method=method,
                    route=route,
                    status=response.status_code,
                    latency_ms=round((time.monotonic() - started) * 1000, 2),
                )
                return response
            rate_remaining = decision.remaining

        response = await call_next(request)
        status_code = response.status_code
    except HTTPException as exc:
        status_code = exc.status_code
        response = JSONResponse(status_code=exc.status_code, content={"error": {"message": exc.detail}})
    except Exception as exc:  # pragma: no cover
        metrics.record_upstream_error(route)
        status_code = 500
        response = JSONResponse(status_code=500, content={"error": {"message": "Internal server error"}})
        _log_event(
            "request_failed",
            request_id=request_id,
            method=method,
            route=route,
            error=str(exc),
        )

    latency_s = time.monotonic() - started
    response.headers["x-request-id"] = request_id
    if route.startswith("/v1/") and method != "OPTIONS":
        response.headers["x-ratelimit-limit"] = str(settings.rate_limit_rpm)
        response.headers["x-ratelimit-remaining"] = str(max(0, rate_remaining))

    metrics.record_request(route, method, status_code, latency_s)
    _log_event(
        "request_completed",
        request_id=request_id,
        client_id=client_id,
        method=method,
        route=route,
        status=status_code,
        latency_ms=round(latency_s * 1000, 2),
    )
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics_endpoint() -> Response:
    return Response(metrics.render_prometheus(), media_type="text/plain; version=0.0.4; charset=utf-8")


@app.get("/v1/models")
async def list_models(request: Request) -> Response:
    if not model_router.has_model_map:
        status, content, content_type = await _get_with_retry(
            base_url=settings.llama_cpp_base_url,
            path="/v1/models",
            timeout=_timeout(settings.timeout_models_s),
            request_id=request.state.request_id,
        )
        return Response(content=content, status_code=status, media_type=content_type)

    data: list[dict[str, object]] = []
    for model, base_url in model_router.configured_upstreams:
        try:
            status, content, _ = await _get_with_retry(
                base_url=base_url,
                path="/v1/models",
                timeout=_timeout(settings.timeout_models_s),
                request_id=request.state.request_id,
            )
            if status >= 400:
                continue
            body = json.loads(content.decode("utf-8"))
            entries = body.get("data")
            if isinstance(entries, list) and entries:
                for entry in entries:
                    if isinstance(entry, dict):
                        entry = dict(entry)
                        entry["upstream_model_id"] = entry.get("id", "")
                        entry["id"] = model
                        data.append(entry)
            else:
                data.append(
                    {
                        "id": model,
                        "object": "model",
                        "owned_by": "llamacpp",
                        "meta": {"upstream": base_url},
                    }
                )
        except Exception:
            continue

    # Keep deterministic output and avoid duplicated IDs.
    seen: set[str] = set()
    unique_data: list[dict[str, object]] = []
    for item in data:
        model_id = str(item.get("id", ""))
        if model_id and model_id not in seen:
            seen.add(model_id)
            unique_data.append(item)

    return JSONResponse({"object": "list", "data": unique_data, "models": unique_data})


@app.post("/v1/chat/completions")
async def chat_completions(body: ChatCompletionRequest, request: Request) -> Response:
    payload = body.model_dump(exclude_none=True)
    request_id = request.state.request_id
    base_url = model_router.upstream_for_model(body.model)

    if body.stream:
        client, upstream = await _post_stream_with_retry(
            base_url=base_url,
            path="/v1/chat/completions",
            payload=payload,
            timeout=_timeout(settings.timeout_chat_s),
            request_id=request_id,
        )

        content_type = upstream.headers.get("content-type", "text/event-stream")

        async def event_stream() -> AsyncIterable[bytes]:
            try:
                async for chunk in upstream.aiter_raw():
                    yield chunk
            finally:
                await upstream.aclose()
                await client.aclose()

        return StreamingResponse(event_stream(), status_code=upstream.status_code, media_type=content_type)

    status, content, content_type = await _post_json_with_retry(
        base_url=base_url,
        path="/v1/chat/completions",
        payload=payload,
        timeout=_timeout(settings.timeout_chat_s),
        request_id=request_id,
    )
    return Response(content=content, status_code=status, media_type=content_type)


@app.post("/v1/embeddings")
async def embeddings(body: EmbeddingsRequest, request: Request) -> Response:
    base_url = model_router.upstream_for_model(body.model)
    status, content, content_type = await _post_json_with_retry(
        base_url=base_url,
        path="/v1/embeddings",
        payload=body.model_dump(exclude_none=True),
        timeout=_timeout(settings.timeout_embeddings_s),
        request_id=request.state.request_id,
    )
    return Response(content=content, status_code=status, media_type=content_type)


@app.post("/v1/completions")
async def completions(body: CompletionRequest, request: Request) -> Response:
    payload = body.model_dump(exclude_none=True)
    request_id = request.state.request_id
    base_url = model_router.upstream_for_model(body.model)

    if body.stream:
        client, upstream = await _post_stream_with_retry(
            base_url=base_url,
            path="/v1/completions",
            payload=payload,
            timeout=_timeout(settings.timeout_completions_s),
            request_id=request_id,
        )

        content_type = upstream.headers.get("content-type", "text/event-stream")

        async def event_stream() -> AsyncIterable[bytes]:
            try:
                async for chunk in upstream.aiter_raw():
                    yield chunk
            finally:
                await upstream.aclose()
                await client.aclose()

        return StreamingResponse(event_stream(), status_code=upstream.status_code, media_type=content_type)

    status, content, content_type = await _post_json_with_retry(
        base_url=base_url,
        path="/v1/completions",
        payload=payload,
        timeout=_timeout(settings.timeout_completions_s),
        request_id=request_id,
    )
    return Response(content=content, status_code=status, media_type=content_type)
