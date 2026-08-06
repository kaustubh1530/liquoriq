"""
services/advisor/openai_agent.py — the only place the advisor touches OpenAI.

Kept in its own module so `agent.py` — the loop, the memory, the tool
dispatch, all of the actual reasoning about how an agent should behave — has
no import of the SDK at all. That is what lets the whole loop be tested with a
three-line fake caller, with no API key and no network.

Returns a NORMALISED shape:

    {"content": str | None, "tool_calls": [{"id", "name", "arguments"}]}

so the loop never handles an OpenAI object. If the API shape changes, or the
model provider changes, this file changes and nothing else does.
"""

import json
import logging

from openai import RateLimitError

from app.config import get_settings
from app.services.openai_service import _client, _quota_message

logger = logging.getLogger(__name__)

# app.config exposes get_settings(), NOT a module-level `settings`. Importing
# the wrong name raised ImportError inside agent.ask()'s lazy import — which
# the agent's own "never raise" guard caught and turned into the fallback
# message. Every question failed before OpenAI was ever contacted.
settings = get_settings()


async def call_with_tools(messages: list[dict], tools: list[dict] | None) -> dict:
    """
    One turn against the model.

    `tools=None` means "no more lookups, give me your answer" — used to close
    out the loop when the round budget is spent.
    """
    kwargs = {
        "model": settings.openai_model,       # gpt-4o
        "messages": messages,
        # Low but not zero: business advice should be readable, not robotic,
        # and the figures come from tools rather than from sampling.
        "temperature": 0.3,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    logger.info(
        "OpenAI request · model=%s · messages=%d · tools=%s · approx_chars=%d",
        kwargs["model"], len(messages),
        len(tools) if tools else "none",
        sum(len(str(m.get("content") or "")) for m in messages),
    )

    try:
        response = await _client.chat.completions.create(**kwargs)
    except RateLimitError as exc:
        # THIS is the only error worth translating. The SDK raises
        # RateLimitError for both "going too fast" (retry works) and "out of
        # credits" (retry never works), and _quota_message tells them apart.
        logger.error("OpenAI rate limit / quota: %s", exc, exc_info=True)
        raise RuntimeError(_quota_message(exc)) from exc
    except Exception as exc:
        # EVERYTHING ELSE KEEPS ITS OWN IDENTITY.
        #
        # This block previously routed every exception through
        # _quota_message(), which returns "OpenAI is rate limiting us" for
        # anything it doesn't recognise. So an auth failure, a malformed tool
        # schema, a network timeout and a bad message shape all arrived at the
        # caller wearing the same disguise — and the real cause was destroyed
        # at the boundary before anyone could read it. Diagnosing that from the
        # outside is impossible, which is exactly what happened.
        logger.error("OpenAI call failed · %s: %s",
                     type(exc).__name__, exc, exc_info=True)
        raise

    message = response.choices[0].message
    logger.info(
        "OpenAI response · finish=%s · tool_calls=%d · content_chars=%d · usage=%s",
        response.choices[0].finish_reason,
        len(message.tool_calls or []),
        len(message.content or ""),
        getattr(response, "usage", None),
    )

    calls = []
    for call in (message.tool_calls or []):
        try:
            arguments = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError:
            logger.warning("Model sent unparseable arguments for %s: %s",
                           call.function.name, call.function.arguments)
            arguments = {}
        calls.append({"id": call.id, "name": call.function.name,
                      "arguments": arguments})

    return {"content": message.content, "tool_calls": calls}
