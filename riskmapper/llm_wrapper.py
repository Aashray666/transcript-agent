"""LLM provider wrapper for the RiskMapper pipeline.

Wraps the Groq REST API (OpenAI-compatible) with retry logic, structured
JSON output, and observability logging. Uses only the `requests` library.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import TypeVar

import requests
from dotenv import load_dotenv
from pydantic import BaseModel

from riskmapper.schemas import LLMCallError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_GROQ_API_BASE = "https://api.groq.com/openai/v1/chat/completions"
_MAX_RETRIES = 5
_RETRY_DELAYS = [5, 10, 20, 30, 60]  # backoff for Groq free tier
_MIN_CALL_INTERVAL = 15.0  # seconds between calls — 12K TPM / ~2.5K per call = ~4 calls/min


class LLMWrapper:
    """Thin wrapper around the Groq REST API for structured LLM calls."""

    # Class-level timestamp for rate limiting across instances
    _last_call_time: float = 0.0

    def __init__(
        self,
        model: str = "llama-3.3-70b-versatile",
        api_key: str | None = None,
    ) -> None:
        load_dotenv(override=True)
        self.model = model
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise EnvironmentError(
                "GROQ_API_KEY not found. Set it in the environment, "
                "in a .env file, or pass it directly."
            )

    def call(
        self,
        prompt: str,
        response_model: type[T],
        temperature: float = 0.0,
        step_name: str = "",
        system_prompt: str | None = None,
    ) -> T:
        """Call the Groq API with JSON mode and structured output.

        Retries up to 3 times with exponential backoff on transient errors.
        Returns a validated Pydantic model instance.
        Raises LLMCallError if all retries are exhausted.
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        body = self._build_request_body(
            prompt, response_model, temperature, system_prompt
        )

        last_error: Exception | None = None
        start_time = time.time()

        for attempt in range(_MAX_RETRIES):
            try:
                # Rate limiting: ensure minimum interval between calls
                elapsed = time.time() - LLMWrapper._last_call_time
                if elapsed < _MIN_CALL_INTERVAL:
                    wait = _MIN_CALL_INTERVAL - elapsed
                    logger.debug("Rate limit pause: %.1fs", wait)
                    time.sleep(wait)

                response = requests.post(
                    _GROQ_API_BASE, headers=headers, json=body, timeout=120
                )

                if self._is_retryable(response.status_code):
                    logger.warning(
                        "Retryable error | status=%d | attempt=%d/%d | step=%s",
                        response.status_code, attempt + 1, _MAX_RETRIES, step_name,
                    )
                    last_error = Exception(
                        f"API returned status {response.status_code}"
                    )
                    if attempt < _MAX_RETRIES - 1:
                        time.sleep(_RETRY_DELAYS[attempt])
                    continue

                if response.status_code != 200:
                    logger.error(
                        "LLM call failed | model=%s | step=%s | status=%d",
                        self.model, step_name, response.status_code,
                    )
                    raise LLMCallError(
                        f"LLM call failed with status {response.status_code} "
                        f"for step '{step_name}'"
                    )

                result_data = response.json()
                latency = time.time() - start_time

                # Extract token counts from Groq response
                usage = result_data.get("usage", {})
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)

                logger.info(
                    "LLM call completed | model=%s | step=%s | "
                    "input_tokens=%d | output_tokens=%d | latency=%.2fs",
                    self.model, step_name,
                    input_tokens, output_tokens, latency,
                )

                # Parse the response content
                text_content = result_data["choices"][0]["message"]["content"]
                parsed = json.loads(text_content)

                # Validate against the Pydantic model
                LLMWrapper._last_call_time = time.time()
                return response_model.model_validate(parsed)

            except requests.exceptions.ConnectionError as exc:
                last_error = exc
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_RETRY_DELAYS[attempt])
            except requests.exceptions.Timeout as exc:
                last_error = exc
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_RETRY_DELAYS[attempt])

        # All retries exhausted
        latency = time.time() - start_time
        logger.error(
            "LLM call failed after %d retries | model=%s | step=%s | latency=%.2fs",
            _MAX_RETRIES, self.model, step_name, latency,
        )
        raise LLMCallError(
            f"LLM call failed after {_MAX_RETRIES} retries for step '{step_name}'"
        )

    def _build_request_body(
        self,
        prompt: str,
        response_model: type[BaseModel],
        temperature: float,
        system_prompt: str | None,
    ) -> dict:
        """Build the Groq API request body (OpenAI-compatible format)."""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Include JSON schema instructions in the user prompt
        schema = response_model.model_json_schema()
        schema_instruction = (
            f"\n\nYou must respond with valid JSON matching this exact schema:\n"
            f"{json.dumps(schema, indent=2)}\n"
            f"Output ONLY the JSON object, no other text."
        )
        messages.append({"role": "user", "content": prompt + schema_instruction})

        return {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "max_tokens": 8000,
        }

    @staticmethod
    def _is_retryable(status_code: int) -> bool:
        """Determine if an HTTP status code warrants a retry."""
        return status_code == 429 or status_code >= 500
