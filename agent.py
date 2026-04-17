"""
agent.py — AI Agent module powered by DeepSeek API.

Exposes `process()` which returns a structured dict so the UI can render
granular feedback (success vs. specific error categories, token usage, latency).
"""

from __future__ import annotations

import os
import time
from typing import Any

from openai import (
    OpenAI,
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
    APIStatusError,
)
from dotenv import load_dotenv

load_dotenv()

# ── System prompts for each persona ──────────────────────────────────────────
PERSONAS: dict[str, str] = {
    "General Assistant": (
        "You are a helpful, concise AI assistant. "
        "Answer clearly and directly."
    ),
    "Research Analyst": (
        "You are a rigorous research analyst. "
        "Provide well-structured, evidence-based answers with key points highlighted. "
        "Use bullet points and clear sections when helpful."
    ),
    "Creative Writer": (
        "You are a creative and imaginative writing assistant. "
        "Produce engaging, vivid, and original responses."
    ),
    "Code Helper": (
        "You are an expert software engineer. "
        "Provide clean, well-commented code examples and clear technical explanations. "
        "Always mention edge cases or potential issues."
    ),
}

# ── Validation limits ────────────────────────────────────────────────────────
MIN_INPUT_CHARS = 3
MAX_INPUT_CHARS = 4000
REQUEST_TIMEOUT_S = 60.0
MAX_RETRIES = 2


def list_personas() -> list[str]:
    """Return available persona names."""
    return list(PERSONAS.keys())


def get_client() -> OpenAI:
    """Return an OpenAI-compatible client pointed at DeepSeek."""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "DEEPSEEK_API_KEY not found. Please add it to your .env file."
        )
    base_url = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com").rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=REQUEST_TIMEOUT_S,
        max_retries=MAX_RETRIES,
    )


def validate_input(user_input: str) -> tuple[bool, str]:
    """
    Server-side input validation. Returns (ok, message).
    Any issues the UI missed are caught here as a safety net.
    """
    if not isinstance(user_input, str):
        return False, "Input must be text."
    stripped = user_input.strip()
    if not stripped:
        return False, "Input is empty — please type a question."
    if len(stripped) < MIN_INPUT_CHARS:
        return False, f"Input is too short — at least {MIN_INPUT_CHARS} characters required."
    if len(stripped) > MAX_INPUT_CHARS:
        return False, f"Input is too long — please keep it under {MAX_INPUT_CHARS} characters."
    # Guard against control characters that often indicate copy/paste glitches
    if any(ord(c) < 9 or (13 < ord(c) < 32) for c in stripped):
        return False, "Input contains unsupported control characters — please retype your question."
    return True, "ok"


def _error_result(category: str, message: str, elapsed_s: float = 0.0) -> dict[str, Any]:
    return {
        "ok": False,
        "content": "",
        "error_category": category,
        "error": message,
        "tokens_prompt": 0,
        "tokens_completion": 0,
        "tokens_total": 0,
        "finish_reason": None,
        "elapsed_s": round(elapsed_s, 3),
    }


def process(
    user_input: str,
    *,
    persona: str = "General Assistant",
    temperature: float = 0.7,
    max_tokens: int = 1024,
    history: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Call the DeepSeek model and return a structured result dict.

    Returns keys:
        ok              : bool
        content         : str (model reply, empty on failure)
        error_category  : str (one of: validation, config, auth, rate_limit,
                                timeout, connection, bad_request, api, empty,
                                unknown)  — only set when ok=False
        error           : str (human-readable message)
        tokens_prompt   : int
        tokens_completion : int
        tokens_total    : int
        finish_reason   : str | None
        elapsed_s       : float (wall-clock seconds for the API call)
    """
    # ── 1. Input validation ──
    ok, msg = validate_input(user_input)
    if not ok:
        return _error_result("validation", msg)

    # ── 2. Parameter range clamping (safe defaults instead of crash) ──
    try:
        temperature = float(temperature)
    except (TypeError, ValueError):
        temperature = 0.7
    temperature = min(max(temperature, 0.0), 1.0)

    try:
        max_tokens = int(max_tokens)
    except (TypeError, ValueError):
        max_tokens = 1024
    max_tokens = min(max(max_tokens, 16), 4096)

    system_prompt = PERSONAS.get(persona, PERSONAS["General Assistant"])
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_input.strip()})

    start = time.perf_counter()
    try:
        client = get_client()
        model_name = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        elapsed = time.perf_counter() - start

        # Guard against empty / malformed responses
        if not response.choices:
            return _error_result("empty", "Model returned no choices.", elapsed)
        choice = response.choices[0]
        content = (choice.message.content or "").strip()
        if not content:
            return _error_result("empty", "Model returned an empty reply.", elapsed)

        usage = getattr(response, "usage", None)
        return {
            "ok": True,
            "content": content,
            "error_category": None,
            "error": "",
            "tokens_prompt": getattr(usage, "prompt_tokens", 0) or 0,
            "tokens_completion": getattr(usage, "completion_tokens", 0) or 0,
            "tokens_total": getattr(usage, "total_tokens", 0) or 0,
            "finish_reason": getattr(choice, "finish_reason", None),
            "elapsed_s": round(elapsed, 3),
        }

    except EnvironmentError as e:
        return _error_result("config", str(e), time.perf_counter() - start)
    except AuthenticationError as e:
        return _error_result(
            "auth",
            "Authentication failed. Check that DEEPSEEK_API_KEY in .env is correct and active.",
            time.perf_counter() - start,
        )
    except RateLimitError:
        return _error_result(
            "rate_limit",
            "Rate limit hit. Please wait a moment and try again.",
            time.perf_counter() - start,
        )
    except APITimeoutError:
        return _error_result(
            "timeout",
            f"Request timed out after {REQUEST_TIMEOUT_S:.0f}s. "
            "Try a shorter prompt or a smaller max-tokens value.",
            time.perf_counter() - start,
        )
    except APIConnectionError:
        return _error_result(
            "connection",
            "Could not reach the DeepSeek API. Check your internet connection and DEEPSEEK_API_BASE.",
            time.perf_counter() - start,
        )
    except BadRequestError as e:
        return _error_result(
            "bad_request",
            f"The API rejected the request: {e}. Try reducing max-tokens or clearing history.",
            time.perf_counter() - start,
        )
    except APIStatusError as e:
        return _error_result(
            "api",
            f"API returned HTTP {getattr(e, 'status_code', '?')}: {e}",
            time.perf_counter() - start,
        )
    except Exception as e:  # last-resort catch-all
        return _error_result(
            "unknown",
            f"Unexpected {type(e).__name__}: {e}",
            time.perf_counter() - start,
        )
