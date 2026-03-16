import asyncio
import orjson
import time
from collections.abc import Awaitable, Callable
from typing import Any, Dict, Optional

from llama_cpp import Llama, CreateChatCompletionResponse

from domain.llm.ports.llm_provider import LLMProviderPort
from domain.llm.schemas.llm import LLMRequest, LLMResult
from domain.llm.utils.model_path import resolve_slm_model_path
from domain.llm.exceptions.llm_exceptions import SLMInferenceTimeoutException
from exceptions.service_exceptions import DomainValidationException
from settings import SLM_INFERENCE_TIMEOUT_MS, SLM_MODEL_PATH


class SLMLocalProvider(LLMProviderPort):
    def __init__(
        self,
        *,
        credential_secret_ref: str | None = None,
        model_name: str | None = SLM_MODEL_PATH,
        timeout_s: int | None = SLM_INFERENCE_TIMEOUT_MS,
    ) -> None:
        self.credential_secret_ref = credential_secret_ref
        self._engine: Optional[Llama] = None
        self.model_name = model_name
        self.timeout_s = timeout_s
        self._engine_instance()

    def _engine_instance(self) -> Llama:
        if self._engine:
            return self._engine

        if not self.model_name:
            raise DomainValidationException("llm_provider_missing_model_path")

        resolved_path = resolve_slm_model_path(self.model_name)

        engine_config: Dict[str, Any] = {}
        if self.credential_secret_ref:
            try:
                engine_config = orjson.loads(self.credential_secret_ref)
            except orjson.JSONDecodeError as exc:
                raise DomainValidationException(
                    "llm_provider_invalid_credential_secret_ref",
                    errors=[str(exc)],
                ) from exc

        try:
            self._engine = Llama(
                model_path=resolved_path,
                n_ctx=engine_config.get("n_ctx", 2048),
                n_threads=engine_config.get("n_threads", 4),
                n_gpu_layers=engine_config.get("n_gpu_layers", 0),
                n_batch=engine_config.get("n_batch", 64),
                flash_attn=engine_config.get("flash_attn", False),
                offload_kqv=engine_config.get("offload_kqv", False),
                verbose=engine_config.get("verbose", False),
                embedding=engine_config.get("embedding", False),
                no_perf=engine_config.get("no_perf", True),
            )
        except ValueError as exc:
            raise DomainValidationException(
                "llm_provider_invalid_model_path",
                errors=[str(exc)],
            ) from exc

        return self._engine

    async def infer(
        self,
        request: LLMRequest,
        on_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> LLMResult:
        messages: list[dict[str, str]] = [
            message.model_dump(mode="json") for message in request.messages
        ]

        if not messages:
            # if request.system_prompt:
            #    messages.append({"role": "system", "content": request.system_prompt})
            # if request.system_context:
            #    messages.append({"role": "system", "content": request.system_context})
            if request.prompt:
                messages.append({"role": "system", "content": request.prompt})
            if request.user_message:
                messages.append({"role": "user", "content": request.user_message})

        schema_payload = request.json_schema or request.output_schema
        structured_expected = bool(schema_payload)

        temperature = (
            0.0
            if structured_expected
            else (request.temperature if request.temperature is not None else 0.2)
        )

        max_tokens = request.max_tokens if request.max_tokens else 256

        payload: Dict[str, Any] = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if structured_expected:
            if properties := schema_payload.get("properties"):
                result = properties.get("result")
                if result and result.get("type") == "array":
                    properties["result"]["maxItems"] = 2

            payload["response_format"] = {
                "type": "json_object",
                "schema": schema_payload,
            }

        loop = asyncio.get_running_loop()
        started = time.perf_counter()
        timeout_s = request.max_latency_ms  # / 1000.0

        inference_future = loop.run_in_executor(
            None,
            lambda: self._engine.create_chat_completion(**payload),
        )

        try:
            completion: CreateChatCompletionResponse = await asyncio.wait_for(
                asyncio.shield(inference_future),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError as e:
            raise SLMInferenceTimeoutException(message="slm_timeout_error") from e

        latency_ms = int((time.perf_counter() - started) * 1000)

        choice = completion["choices"][0]
        content_output: str = (choice.get("message", {}).get("content") or "").strip()
        try:
            output = orjson.loads(content_output)
        except orjson.JSONDecodeError as exc:
            raise DomainValidationException(
                "llm_invalid_json_output",
                input_data=content_output,
                errors=[str(exc)],
            ) from exc

        usage: Dict[str, int] = completion.get("usage", {})

        return LLMResult(
            output=output,
            token_usage={
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            cost_usd=0.0,
            latency_ms=latency_ms,
            model_alias=request.model_alias,
            raw_output=completion,
        )
