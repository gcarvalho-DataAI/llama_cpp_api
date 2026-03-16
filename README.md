# Local OpenAI-Compatible LLM API

Production-grade FastAPI proxy for local LLM serving, exposing OpenAI-compatible endpoints for chat, completions, and embeddings. The current default runtime is `vLLM` with `Qwen/Qwen2.5-7B-Instruct`, while `llama.cpp` remains available for GGUF-based operation.

## Why this project matters
This repository demonstrates practical AI backend engineering for real deployment scenarios, not just demos.

- Runs local LLM inference with OpenAI API compatibility (`/v1/*`)
- Adds reliability controls expected in production (timeouts, retries, rate limits)
- Improves operability with metrics, structured logs, and traceable request IDs
- Supports secure multi-client usage through API keys and per-client throttling
- Keeps integration simple for existing OpenAI-based applications

## LLM Engineer Snapshot
- Domain: LLM serving, inference reliability, and production API design
- Focus: latency/throughput tradeoffs, model runtime constraints, and endpoint compatibility
- Stack: Python, FastAPI, Pydantic, httpx, vLLM, llama.cpp, GGUF models, Prometheus-style metrics
- Value: enables cost-efficient local inference while preserving OpenAI-compatible integration

## What this demonstrates for LLM Engineer roles
- Inference serving architecture: wraps local inference backends (`vLLM` and `llama.cpp`) with a hardened API layer for real client workloads
- API contract engineering: keeps OpenAI request/response patterns for easy migration and interoperability
- Runtime reliability: retries, backoff, timeouts, and rate limits to handle unstable upstream behavior
- Observability for model serving: request IDs, structured logs, and metrics for incident triage and tuning
- Performance-oriented operations: CPU-first tuning knobs (`threads`, `batch`, `ctx`) and reproducible load checks

## Architecture

```text
OpenAI-compatible client/app
          |
          v
   FastAPI Proxy (this repo)
   - auth & per-client limits
   - schema validation
   - retries/timeouts
   - metrics/logging
          |
          v
   selected local backend
   - vLLM (HF models)
   - llama.cpp (GGUF models)
```

## Runtime modes

This repository supports two serving modes:

- `vLLM` mode
  - current default
  - best fit when you want a single high-quality local model behind one alias
  - current reference setup: `Qwen/Qwen2.5-7B-Instruct` served as `qwen-linkedin`
- `llama.cpp` mode
  - useful for GGUF models and CPU / hybrid GPU operation
  - supports one backend or multiple `llama-server` instances behind the proxy

Choose the runtime with:

```env
INFERENCE_BACKEND=vllm
```

or:

```env
INFERENCE_BACKEND=llama.cpp
```

## Endpoints
- `GET /health`
- `GET /metrics` (Prometheus text format)
- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/completions`
- `POST /v1/embeddings`

## Production features implemented
- OpenAI-style schema validation with Pydantic
- Streaming passthrough for `stream=true` (SSE)
- Retry with exponential backoff for transient upstream failures
- Route-specific timeouts
- API key auth with per-client keys (`OPENAI_API_KEYS`)
- Sliding-window rate limit per client
- Structured JSON logs with `x-request-id`
- CORS allowlist
- Smoke tests (`pytest`) and load test script

## Prerequisites
- Python 3.10+
- `vLLM` virtualenv in `./.venv-vllm` when using `INFERENCE_BACKEND=vllm`
- Built `llama.cpp` server binary (`llama-server`) when using `INFERENCE_BACKEND=llama.cpp`
- GGUF model file in `./models` for `llama.cpp` mode

## Quick start

1. Create virtualenv and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Configure:

```bash
cp .env.example .env
```

Then edit `.env` for the runtime you want.

### Recommended current setup: vLLM + Qwen 7B

Use this when you want the current default local model:

```env
INFERENCE_BACKEND=vllm
OPENAI_API_KEY=local
MODEL_UPSTREAMS=qwen-linkedin=http://127.0.0.1:8001
VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct
VLLM_SERVED_MODEL_NAME=qwen-linkedin
VLLM_PORT=8001
```

If the model is not already cached locally, `vLLM` will download it from Hugging Face. Set `HUGGING_FACE_TOKEN` in `.env` if needed.

Start everything:

```bash
./scripts/run_all.sh
```

This starts:
- `vLLM` on `127.0.0.1:8001`
- the proxy on `127.0.0.1:8000`

### Alternative setup: llama.cpp single-model mode

Use this when serving one GGUF model:

```env
INFERENCE_BACKEND=llama.cpp
LLAMA_CPP_BASE_URL=http://127.0.0.1:8080
LLAMA_MODEL=./models/your-model.gguf
MODEL_UPSTREAMS=llama=http://127.0.0.1:8080
```

Start backend:

```bash
./scripts/run_llama_server.sh
```

Start proxy:

```bash
./scripts/run_api.sh
```

### Alternative setup: llama.cpp multi-model mode

If you want model-aware routing from request payload (`"model": "..."`), configure multiple upstreams:

```env
MODEL_UPSTREAMS=llama-8b=http://127.0.0.1:8081,llama-70b-q4=http://127.0.0.1:8082,llama-70b-q5=http://127.0.0.1:8083
```

In this mode, the proxy routes each request to the upstream selected by the payload `model`.
Each `llama-server` process should load one model.

Also define local model files for the multi-launcher script:

```env
MODEL_PATHS=llama-8b=./models/Meta-Llama-3.1-8B-Instruct-Q5_K_M.gguf,llama-70b-q4=./models/Meta-Llama-3.1-70B-Instruct-Q4_K_M.gguf,llama-70b-q5=./models/Meta-Llama-3.1-70B-Instruct-Q5_K_M/Meta-Llama-3.1-70B-Instruct-Q5_K_M-00001-of-00002.gguf
ENABLED_MODELS=llama-8b
```

`ENABLED_MODELS` lets you start only a subset of models (recommended on limited RAM).

In this mode, start multiple backends:

```bash
./scripts/run_llama_servers_multi.sh
```

Then start proxy API:

```bash
./scripts/run_api.sh
```

To stop the multi-backend servers:

```bash
./scripts/stop_llama_servers_multi.sh
```

## Scripts

Operational scripts in `scripts/`:

- `run_all.sh`
  - main entrypoint
  - reads `.env`
  - starts either `vLLM` or `llama.cpp` based on `INFERENCE_BACKEND`
  - starts the FastAPI proxy
- `stop_all.sh`
  - stops the active backend and the proxy
- `run_vllm.sh`
  - starts the `vLLM` server
  - waits until `/health` and `/v1/models` are ready
- `stop_vllm.sh`
  - stops `vLLM` and associated worker processes
- `run_llama_server.sh`
  - starts one `llama.cpp` backend from `LLAMA_MODEL`
- `run_llama_servers_multi.sh`
  - starts one `llama.cpp` process per model in `MODEL_PATHS`
  - uses `ENABLED_MODELS` when defined
- `stop_llama_servers_multi.sh`
  - stops the multi-backend `llama.cpp` processes
- `run_api.sh`
  - starts only the FastAPI proxy
- `docker_up.sh` / `docker_down.sh`
  - containerized flow for the `llama.cpp` topology
- `load_test.py`
  - simple latency / throughput smoke benchmark

## Model configuration

### Public model alias

The proxy exposes model aliases defined in `MODEL_UPSTREAMS`. Clients should send those aliases in the OpenAI payload:

```json
{
  "model": "qwen-linkedin",
  "messages": [{"role": "user", "content": "..." }]
}
```

### vLLM model settings

For the current setup:

```env
VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct
VLLM_SERVED_MODEL_NAME=qwen-linkedin
VLLM_GPU_MEMORY_UTILIZATION=0.9
VLLM_MAX_MODEL_LEN=2048
VLLM_EXTRA_ARGS=--enforce-eager
```

Notes:
- `VLLM_MODEL` is the Hugging Face model id
- `VLLM_SERVED_MODEL_NAME` is the public alias returned by `/v1/models`
- `VLLM_EXTRA_ARGS=--enforce-eager` is the conservative default used here for stability
- if downloads are incomplete, `vLLM` may appear stuck during startup; complete the model cache first

### llama.cpp model settings

For GGUF mode:

```env
LLAMA_MODEL=./models/Meta-Llama-3.1-8B-Instruct-Q5_K_M.gguf
LLAMA_DEVICE=CUDA0
LLAMA_GPU_LAYERS=all
```

In multi-model mode, use:

```env
MODEL_PATHS=llama-8b=./models/Meta-Llama-3.1-8B-Instruct-Q5_K_M.gguf,llama-70b-q4=./models/Meta-Llama-3.1-70B-Instruct-Q4_K_M.gguf
ENABLED_MODELS=llama-8b
```

## Docker (single public port with model routing)
This setup uses one public API (`:8000`) and multiple internal `llama-server` containers.

Start lightweight mode (proxy + 8B only):

```bash
./scripts/docker_up.sh
```

Start full mode (proxy + 8B + 70B Q4 + 70B Q5):

```bash
./scripts/docker_up.sh full
```

Stop everything:

```bash
./scripts/docker_down.sh
```

By default, payload model aliases route to:
- `llama-8b` -> `llama_8b`
- `llama-70b-q4` -> `llama_70b_q4`
- `llama-70b-q5` -> `llama_70b_q5`

Call API on `http://127.0.0.1:8000` and send the desired model in the request body.

## Security and auth config
Use one key:

```env
OPENAI_API_KEY=local
```

Use multiple keys with client IDs:

```env
OPENAI_API_KEYS=key_a:team_a,key_b:team_b,key_c
```

`key_c` gets an autogenerated client id.

## Example requests

Chat completion:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer local" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-linkedin",
    "messages": [{"role": "user", "content": "hello"}],
    "temperature": 0.2
  }'
```

Streaming chat:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer local" \
  -H "Content-Type: application/json" \
  -N \
  -d '{
    "model": "qwen-linkedin",
    "messages": [{"role": "user", "content": "write one short poem"}],
    "stream": true
  }'
```

Embeddings:

```bash
curl http://127.0.0.1:8000/v1/embeddings \
  -H "Authorization: Bearer local" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-linkedin",
    "input": ["hello world"]
  }'
```

## llama.cpp tuning (i9 14900K baseline)
Suggested baseline in `.env`:

```env
LLAMA_THREADS=20
LLAMA_THREADS_BATCH=20
LLAMA_CTX=4096
LLAMA_N_BATCH=1024
LLAMA_EMBEDDINGS=1
```

Recommended quantization starting points:
- `8B Q5_K_M` for quality/latency balance
- `8B Q4_K_M` for lower latency

## Validation and tests
Run smoke tests:

```bash
source .venv/bin/activate
pytest -q
```

Run basic load test:

```bash
source .venv/bin/activate
python scripts/load_test.py --requests 40 --concurrency 8 --model llama --api-key local
```

## Integration with OpenAI-based apps
Point your existing app to this proxy:

```env
OPENAI_ENDPOINT=http://127.0.0.1:8000/v1
OPENAI_API_KEY=local
OPENAI_CHAT_MODEL=qwen-linkedin
```

For multi-model llama.cpp mode, set `OPENAI_CHAT_MODEL` dynamically in your client payload and make sure it matches keys in `MODEL_UPSTREAMS`.

## Suggested GitHub "About" text
LLM Engineer portfolio project: production-ready OpenAI-compatible API on top of llama.cpp, with streaming, validation, retries, rate limiting, and observability.
