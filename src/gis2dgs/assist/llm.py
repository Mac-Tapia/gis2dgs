from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


def refine_mapping_with_llm(schema: dict[str, Any], seed: dict[str, Any]) -> dict[str, Any] | None:
    """Optional OpenAI-compatible refinement. Never writes DGS; only mapping YAML."""

    url = os.environ.get("GIS2DGS_LLM_URL", "").strip()
    key = os.environ.get("GIS2DGS_LLM_API_KEY", "").strip()
    model = os.environ.get("GIS2DGS_LLM_MODEL", "gpt-4o-mini").strip()
    if not url or not key:
        return None
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Propose GIS2DGS mapping YAML as JSON with keys buses, lines, "
                    "loads, sources, transformers, switches, generators, substations. "
                    "Each value is {source, fields}. Do not invent impedances. "
                    "Do not emit DGS."
                ),
            },
            {
                "role": "user",
                "content": json.dumps({"schema": schema, "seed": seed}, ensure_ascii=False),
            },
        ],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    try:
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None
