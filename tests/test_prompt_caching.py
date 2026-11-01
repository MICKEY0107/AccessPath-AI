"""Token use and prompt-cache reporting for live planners."""

from __future__ import annotations

import io
import json
from types import SimpleNamespace

from engine.contracts import PlannerObservationV1
from engine.groq import GROQ_SYSTEM_PROMPT, GroqActionClient
from engine.provider_usage import TokenUsage


def test_openai_gemini_and_ollama_usage_shapes_are_counted() -> None:
    usage = TokenUsage()
    usage.add_openai(
        {
            "prompt_tokens": 1200,
            "completion_tokens": 40,
            "prompt_tokens_details": {"cached_tokens": 1024},
        }
    )
    usage.add_openai({"prompt_tokens": 800, "completion_tokens": 30})
    usage.add_gemini(
        SimpleNamespace(
            prompt_token_count=900, cached_content_token_count=512, candidates_token_count=20
        )
    )
    usage.add_ollama({"prompt_eval_count": 300, "eval_count": 10})
    usage.add_openai(None)
    data = usage.as_dict()
    assert data["calls"] == 4
    assert data["prompt_tokens"] == 3200 and data["cached_prompt_tokens"] == 1536
    assert data["completion_tokens"] == 100 and data["cached_share"] == 0.48


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_groq_sends_an_identical_prefix_and_records_cache_hits() -> None:
    sent = []

    def opener(request, timeout):
        sent.append(json.loads(request.data))
        body = {
            "model": "openai/gpt-oss-120b",
            "choices": [
                {"message": {"content": json.dumps({"action": "tab", "target_hint": "x"})}}
            ],
            "usage": {
                "prompt_tokens": 1500,
                "completion_tokens": 20,
                "prompt_tokens_details": {"cached_tokens": 1280 if sent[1:] else 0},
            },
        }
        return _Response(json.dumps(body).encode())

    client = GroqActionClient(api_key="k", timeout_seconds=5, min_interval_seconds=0, opener=opener)
    observation = PlannerObservationV1.model_validate(
        {"goal": "g", "url": "https://example.org/", "remaining_steps": 5}
    )
    for _ in range(2):
        client.generate_action(model="openai/gpt-oss-120b", observation=observation)
    assert sent[0]["messages"][0] == sent[1]["messages"][0]
    assert sent[0]["messages"][0]["content"] == GROQ_SYSTEM_PROMPT
    assert client.usage.as_dict()["cached_prompt_tokens"] == 1280
