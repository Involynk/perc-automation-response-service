#!/usr/bin/env python3
"""Local smoke test for Ollama + Qwen3 connectivity.

This script performs non-destructive checks only:
- verifies `OLLAMA_BASE_URL` is reachable
- verifies the configured model exists and equals `qwen3:8b`
- sends a single minimal probe through `OllamaLLMClient`

It intentionally avoids printing secrets or sensitive environment values.
Exit codes: 0 = success, 1 = failure
"""
import sys
import json

from app.core.config import settings
from app.agent.providers.ollama_client import OllamaLLMClient, OllamaError


def safe_print(*parts):
    print(" ".join(str(p) for p in parts))


def main() -> int:
    # Basic configuration checks
    base_url = settings.OLLAMA_BASE_URL
    model = settings.OLLAMA_MODEL

    if not base_url:
        safe_print("FAIL: OLLAMA_BASE_URL is not configured")
        return 1

    safe_print("OLLAMA_BASE_URL:", base_url)

    if not model:
        safe_print("FAIL: OLLAMA_MODEL is not configured")
        return 1

    safe_print("Configured Ollama model:", model)

    # Confirm expected configured model
    expected = "qwen3:8b"
    if model != expected:
        safe_print("FAIL: configured model is not the expected qwen3:8b")
        return 1

    # Construct client
    try:
        client = OllamaLLMClient()
    except Exception as exc:
        safe_print("FAIL: could not construct OllamaLLMClient:", exc)
        return 1

    # Health check + model verification
    safe_print("Checking Ollama health and model list...")
    ok = client.health_check(verify_model=True)
    if not ok:
        safe_print("FAIL: Ollama health check or model verification failed")
        return 1
    safe_print("OK: Ollama reachable and model present")

    # Send a minimal probe. Do not print the probe prompt or any sensitive prompt text.
    probe_prompt = (
        'Return a minimal JSON object with keys primary_intent and confidence. '
        'Example: {"primary_intent":"C1_COURSE_DISCOVERY","confidence":0.9} '
        'Respond with JSON only.'
    )

    try:
        resp_text = client.generate(probe_prompt)
    except OllamaError as exc:
        safe_print("FAIL: Ollama generate() failed:", exc)
        return 1
    except Exception as exc:
        safe_print("FAIL: unexpected error from generate():", exc)
        return 1

    # Diagnostic: check if the response is parseable JSON and list keys (safe)
    try:
        obj = json.loads(resp_text)
        if isinstance(obj, dict):
            safe_print("OK: probe returned JSON object with keys:", ",".join(sorted(obj.keys())))
        else:
            safe_print("WARN: probe returned JSON that is not an object (type:", type(obj), ")")
    except Exception:
        safe_print("WARN: probe did not return JSON. Response length:", len(resp_text or ""))

    safe_print("Smoke test completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
