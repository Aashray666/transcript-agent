"""LLM provider wrapper for the RiskMapper pipeline.

Wraps the NVIDIA NIM REST API (OpenAI-compatible) with retry logic, structured
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
from pydantic import BaseModel, ValidationError

from riskmapper.schemas import LLMCallError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_API_BASE = "https://integrate.api.nvidia.com/v1/chat/completions"
_MAX_RETRIES = 8
_RETRY_DELAYS = [5, 10, 20, 40, 60, 90, 120, 180]
_MIN_CALL_INTERVAL = 5.0
_VALIDATION_RETRIES = 2  # Extra retries specifically for validation errors


class LLMWrapper:
    """Thin wrapper around the NVIDIA NIM REST API for structured LLM calls."""

    _last_call_time: float = 0.0

    def __init__(
        self,
        model: str = "meta/llama-3.3-70b-instruct",
        api_key: str | None = None,
    ) -> None:
        load_dotenv(override=True)
        self.model = model
        self.api_key = api_key or os.environ.get("NVIDIA_API_KEY")
        if not self.api_key:
            raise EnvironmentError(
                "NVIDIA_API_KEY not found. Set it in the environment, "
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
        """Call the LLM API with JSON mode and structured output.

        Retries on: API errors (429, 5xx), validation errors (LLM returns
        wrong format). Returns a validated Pydantic model instance.
        """
        last_error: Exception | None = None
        start_time = time.time()

        # Outer loop: validation retries (re-prompt if LLM returns bad format)
        for val_attempt in range(_VALIDATION_RETRIES + 1):
            raw_json = self._call_api(prompt, response_model, temperature,
                                       step_name, system_prompt)

            try:
                result = response_model.model_validate(raw_json)
                return result
            except ValidationError as exc:
                last_error = exc
                if val_attempt < _VALIDATION_RETRIES:
                    logger.warning(
                        "Validation error on attempt %d/%d for %s: %s. "
                        "Retrying with simplified prompt.",
                        val_attempt + 1, _VALIDATION_RETRIES + 1,
                        step_name, str(exc)[:200],
                    )
                    # Retry with a stronger instruction
                    prompt = self._add_retry_instruction(prompt, exc)
                else:
                    raise

        raise LLMCallError(
            f"Validation failed after {_VALIDATION_RETRIES + 1} attempts "
            f"for step '{step_name}'"
        )

    def _call_api(
        self,
        prompt: str,
        response_model: type[BaseModel],
        temperature: float,
        step_name: str,
        system_prompt: str | None,
    ) -> dict:
        """Make the actual API call with retry logic for transient errors.

        Returns the parsed JSON dict (not yet validated against Pydantic).
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        body = self._build_request_body(
            prompt, response_model, temperature, system_prompt
        )

        start_time = time.time()

        for attempt in range(_MAX_RETRIES):
            try:
                elapsed = time.time() - LLMWrapper._last_call_time
                if elapsed < _MIN_CALL_INTERVAL:
                    time.sleep(_MIN_CALL_INTERVAL - elapsed)

                response = requests.post(
                    _API_BASE, headers=headers, json=body, timeout=120
                )

                if self._is_retryable(response.status_code):
                    logger.warning(
                        "Retryable error | status=%d | attempt=%d/%d | step=%s",
                        response.status_code, attempt + 1, _MAX_RETRIES, step_name,
                    )
                    if attempt < _MAX_RETRIES - 1:
                        time.sleep(_RETRY_DELAYS[attempt])
                    continue

                if response.status_code != 200:
                    raise LLMCallError(
                        f"LLM call failed with status {response.status_code} "
                        f"for step '{step_name}'"
                    )

                result_data = response.json()
                latency = time.time() - start_time

                usage = result_data.get("usage", {})
                logger.info(
                    "LLM call completed | model=%s | step=%s | "
                    "input_tokens=%d | output_tokens=%d | latency=%.2fs",
                    self.model, step_name,
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                    latency,
                )

                text_content = result_data["choices"][0]["message"]["content"]
                LLMWrapper._last_call_time = time.time()
                return json.loads(text_content)

            except requests.exceptions.ConnectionError as exc:
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_RETRY_DELAYS[attempt])
            except requests.exceptions.Timeout:
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_RETRY_DELAYS[attempt])

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
        """Build the API request body with simplified schema instruction."""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Build a SIMPLIFIED schema example instead of dumping the full JSON schema.
        # The full schema with "description", "type", "title" fields confuses the LLM
        # into echoing the schema metadata instead of filling in actual values.
        example = self._build_example_from_schema(response_model)

        schema_instruction = (
            f"\n\nRespond with a JSON object. Here is an example of the expected structure "
            f"(replace the example values with your actual assessment):\n"
            f"```json\n{json.dumps(example, indent=2)}\n```\n"
            f"Output ONLY the JSON object with your actual values. "
            f"Do NOT include schema descriptions or type annotations."
        )
        messages.append({"role": "user", "content": prompt + schema_instruction})

        return {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "max_tokens": 4000,
        }

    @staticmethod
    def _build_example_from_schema(model: type[BaseModel]) -> dict:
        """Build a concrete example dict from a Pydantic model.

        Recursively handles nested Pydantic models, producing a full
        example structure the LLM can follow.
        """
        import typing
        example = {}
        for field_name, field_info in model.model_fields.items():
            annotation = field_info.annotation
            example[field_name] = LLMWrapper._example_for_annotation(
                annotation, field_name
            )
        return example

    @staticmethod
    def _example_for_annotation(annotation, field_name: str = "field"):
        """Generate an example value for a given type annotation."""
        import typing

        if annotation is None or annotation is type(None):
            return None

        # Check for Literal
        origin = getattr(annotation, "__origin__", None)
        args = getattr(annotation, "__args__", None)

        if origin is typing.Literal:
            return args[0] if args else "value"

        # Basic types
        if annotation is str:
            return f"your {field_name.replace('_', ' ')} here"
        if annotation is int:
            return 3
        if annotation is float:
            return 3.0
        if annotation is bool:
            return True

        # Nested Pydantic model
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return LLMWrapper._build_example_from_schema(annotation)

        # List types
        if origin is list:
            if args:
                inner = LLMWrapper._example_for_annotation(args[0], "item")
                return [inner]
            return ["example"]

        # Dict types
        if origin is dict:
            return {"key": "value"}

        # Union / Optional
        if origin is typing.Union and args:
            non_none = [a for a in args if a is not type(None)]
            if non_none:
                return LLMWrapper._example_for_annotation(non_none[0], field_name)
            return None

        # Fallback: check for Literal args
        if args:
            return args[0]

        return f"your {field_name.replace('_', ' ')} here"

    @staticmethod
    def _add_retry_instruction(prompt: str, error: ValidationError) -> str:
        """Add a correction instruction when the LLM returned invalid format."""
        missing_fields = []
        for err in error.errors():
            if err["type"] == "missing":
                field = ".".join(str(loc) for loc in err["loc"])
                missing_fields.append(field)

        if missing_fields:
            correction = (
                f"\n\nIMPORTANT CORRECTION: Your previous response was missing "
                f"these required fields: {', '.join(missing_fields)}. "
                f"Please include ALL required fields with actual values, "
                f"not schema descriptions. Fill in real data based on your analysis."
            )
        else:
            correction = (
                "\n\nIMPORTANT CORRECTION: Your previous response had invalid format. "
                "Please respond with actual values, not schema descriptions or type annotations. "
                "Fill in real data based on your analysis."
            )

        return prompt + correction

    @staticmethod
    def _is_retryable(status_code: int) -> bool:
        return status_code == 429 or status_code >= 500
