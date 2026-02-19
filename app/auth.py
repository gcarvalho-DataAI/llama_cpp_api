from __future__ import annotations

import hashlib
from dataclasses import dataclass

from fastapi import HTTPException

from app.config import settings


@dataclass(frozen=True)
class ClientIdentity:
    client_id: str
    key: str


class ApiKeyAuth:
    def __init__(self) -> None:
        key_specs = settings.openai_api_keys.copy()
        if settings.fallback_openai_api_key:
            key_specs.append(settings.fallback_openai_api_key)

        self._keys: dict[str, str] = {}
        for spec in key_specs:
            if ":" in spec:
                key, client_id = spec.split(":", 1)
                key = key.strip()
                client_id = client_id.strip()
                if key:
                    self._keys[key] = client_id or self._default_client_id(key)
            elif spec:
                self._keys[spec] = self._default_client_id(spec)

    @staticmethod
    def _default_client_id(key: str) -> str:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
        return f"client-{digest}"

    @property
    def enabled(self) -> bool:
        return bool(self._keys)

    def authenticate(self, authorization: str | None) -> ClientIdentity:
        if not self.enabled:
            return ClientIdentity(client_id="anonymous", key="")

        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

        token = authorization.split(" ", 1)[1].strip()
        client_id = self._keys.get(token)
        if not client_id:
            raise HTTPException(status_code=401, detail="Invalid API key")

        return ClientIdentity(client_id=client_id, key=token)
