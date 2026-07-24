import json
import re

import httpx

from .config import LLM_MODEL, OPENAI_API_KEY, OPENAI_BASE_URL


class LLMError(Exception):
    pass


def chat(system: str, user: str, temperature: float = 0.3) -> str:
    try:
        resp = httpx.post(
            f"{OPENAI_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "model": LLM_MODEL,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=180,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except httpx.HTTPError as exc:
        raise LLMError(f"LLM request failed: {exc}") from exc
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMError(f"Unexpected LLM response shape: {exc}") from exc


def chat_json(system: str, user: str) -> dict:
    """Chat and parse the first JSON object in the reply (models wrap JSON in
    prose or code fences more often than they honor response_format)."""
    text = chat(system, user, temperature=0.1)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise LLMError(f"No JSON object in LLM reply: {text[:200]!r}")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise LLMError(f"Invalid JSON from LLM: {exc}") from exc
