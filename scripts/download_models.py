#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path

from huggingface_hub import hf_hub_download


MODEL_SET = {
    "8b-q5": [
        ("bartowski/Meta-Llama-3.1-8B-Instruct-GGUF", "Meta-Llama-3.1-8B-Instruct-Q5_K_M.gguf"),
    ],
    "70b-q4": [
        ("bartowski/Meta-Llama-3.1-70B-Instruct-GGUF", "Meta-Llama-3.1-70B-Instruct-Q4_K_M.gguf"),
    ],
    "70b-q5": [
        (
            "bartowski/Meta-Llama-3.1-70B-Instruct-GGUF",
            "Meta-Llama-3.1-70B-Instruct-Q5_K_M/Meta-Llama-3.1-70B-Instruct-Q5_K_M-00001-of-00002.gguf",
        ),
        (
            "bartowski/Meta-Llama-3.1-70B-Instruct-GGUF",
            "Meta-Llama-3.1-70B-Instruct-Q5_K_M/Meta-Llama-3.1-70B-Instruct-Q5_K_M-00002-of-00002.gguf",
        ),
    ],
}


def read_token_from_env_file(env_file: Path) -> str | None:
    if not env_file.exists():
        return None
    with env_file.open("r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("HUGGING_FACE_TOKEN="):
                return line.strip().split("=", 1)[1]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Download GGUF model files for this workspace.")
    parser.add_argument(
        "--set",
        dest="model_sets",
        action="append",
        choices=sorted(MODEL_SET.keys()),
        help="Model set to download (repeatable). Default: all.",
    )
    parser.add_argument("--models-dir", default="models", help="Target directory for GGUF files.")
    parser.add_argument("--env-file", default=".env", help="Path to env file containing HUGGING_FACE_TOKEN.")
    args = parser.parse_args()

    requested_sets = args.model_sets or sorted(MODEL_SET.keys())

    token = os.getenv("HUGGING_FACE_TOKEN") or read_token_from_env_file(Path(args.env_file))
    if not token:
        raise SystemExit("Missing HUGGING_FACE_TOKEN (env var or .env file).")

    models_dir = Path(args.models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)

    for set_name in requested_sets:
        print(f"==> Downloading set: {set_name}")
        for repo_id, filename in MODEL_SET[set_name]:
            print(f"  - {repo_id}:{filename}")
            path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                repo_type="model",
                token=token,
                local_dir=str(models_dir),
            )
            print(f"    saved: {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
