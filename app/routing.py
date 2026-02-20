from __future__ import annotations

from fastapi import HTTPException

from app.config import settings


class ModelRouter:
    def __init__(self) -> None:
        self._upstreams = settings.model_upstreams
        self._default = settings.llama_cpp_base_url

    @property
    def has_model_map(self) -> bool:
        return bool(self._upstreams)

    @property
    def configured_models(self) -> list[str]:
        return sorted(self._upstreams.keys())

    @property
    def configured_upstreams(self) -> list[tuple[str, str]]:
        return sorted(self._upstreams.items(), key=lambda item: item[0])

    def upstream_for_model(self, model: str) -> str:
        if not self._upstreams:
            return self._default

        upstream = self._upstreams.get(model)
        if not upstream:
            available = ", ".join(self.configured_models)
            raise HTTPException(
                status_code=400,
                detail=f"Unknown model '{model}'. Available models: {available}",
            )
        return upstream
