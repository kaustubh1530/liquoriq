"""
services/openai_service.py — Async GPT-4o wrapper for LiquorIQ

Single responsibility: take a text prompt, call OpenAI, return a validated
Python dict. All retry logic and JSON parsing lives here so strategy_service.py
stays clean.

Key decisions:
  - response_format={"type": "json_object"} forces the model to emit valid JSON
    (no need to strip markdown fences or parse manually)
  - temperature=0.7 gives creative but grounded output
  - We pass model and api_key from settings so they can be changed in .env
    without touching code
"""

import json
import logging

from openai import AsyncOpenAI
from openai import APIConnectionError, RateLimitError, APIStatusError

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Module-level client — created once, reused across all requests
# (AsyncOpenAI manages its own httpx connection pool internally)
_client = AsyncOpenAI(api_key=settings.openai_api_key)


async def generate_json_response(system_prompt: str, user_prompt: str) -> dict:
    """
    Call GPT-4o with JSON mode and return a parsed dict.

    Raises:
        ValueError  — if the response is not valid JSON (shouldn't happen with
                      json_object mode, but guards against empty responses)
        RuntimeError — for OpenAI API errors (connection, rate limit, status)
    """
    try:
        response = await _client.chat.completions.create(
            model=settings.openai_model,         # "gpt-4o" from config
            response_format={"type": "json_object"},
            temperature=0.7,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        )
    except APIConnectionError as e:
        logger.error("OpenAI connection error: %s", e)
        raise RuntimeError(f"Could not connect to OpenAI: {e}") from e
    except RateLimitError as e:
        logger.error("OpenAI rate limit hit: %s", e)
        raise RuntimeError("OpenAI rate limit reached. Try again in a moment.") from e
    except APIStatusError as e:
        logger.error("OpenAI API error %s: %s", e.status_code, e.message)
        raise RuntimeError(f"OpenAI API error {e.status_code}: {e.message}") from e

    raw_content = response.choices[0].message.content or ""

    try:
        return json.loads(raw_content)
    except json.JSONDecodeError as e:
        logger.error("OpenAI returned non-JSON content: %s", raw_content[:200])
        raise ValueError(f"OpenAI response was not valid JSON: {e}") from e