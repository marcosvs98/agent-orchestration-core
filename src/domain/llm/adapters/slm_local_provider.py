import asyncio
import orjson
import time
from typing import Any, Dict, Optional

from llama_cpp import Llama

from adapters.observability.logging import get_logger
from domain.llm.ports.llm_provider import LLMProviderPort
from domain.llm.schemas.llm import LLMRequest, LLMResult
from domain.llm.utils.model_path import resolve_slm_model_path
from exceptions.service_exceptions import DomainValidationException
from settings import SLM_MODEL_PATH

logger = get_logger(__name__)


class SLMLocalProvider(LLMProviderPort):
    def __init__(
        self,
        *,
        credential_secret_ref: str | None = None,
    ) -> None:
        self.credential_secret_ref = credential_secret_ref
        self._engine: Optional[Llama] = None

    async def _engine_instance(self) -> Llama:
        if self._engine:
            return self._engine

        if not SLM_MODEL_PATH:
            raise DomainValidationException("llm_provider_missing_model_path")

        resolved_path = resolve_slm_model_path(SLM_MODEL_PATH)
        logger.info(
            "slm_local_provider model_path resolved",
            model_path_resolved=resolved_path,
            slm_model_path_config=SLM_MODEL_PATH,
        )

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
                flash_attn=False,
                offload_kqv=False,
                verbose=False,
                no_perf=True,
            )
        except ValueError as exc:
            raise DomainValidationException(
                "llm_provider_invalid_model_path",
                errors=[str(exc)],
            ) from exc

        return self._engine

    async def infer(self, request: LLMRequest) -> LLMResult:
        engine = await self._engine_instance()

        messages: list[dict[str, str]] = [
            message.model_dump(mode="json") for message in request.messages
        ]
        if not messages:
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            if request.prompt:
                messages.append({"role": "system", "content": request.prompt})
            if request.user_message:
                messages.append({"role": "user", "content": request.user_message})

        temperature = request.temperature if request.temperature is not None else 0.2
        max_tokens = request.max_tokens if request.max_tokens else 256

        completion_kwargs: Dict[str, Any] = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if request.json_schema or request.output_schema:
            completion_kwargs["response_format"] = {"type": "json_object"}

        logger.info(
            "slm_local_provider create_chat_completion payload",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=completion_kwargs.get("response_format"),
            task_type=getattr(request.task_type, "value", str(request.task_type)),
        )

        loop = asyncio.get_running_loop()
        started = time.perf_counter()
        try:
            completion: Dict[str, Any] = await loop.run_in_executor(
                None,
                lambda: engine.create_chat_completion(**completion_kwargs),
            )
        except Exception as exc:
            raise DomainValidationException(
                "llm_provider_error",
                input_data=completion_kwargs,
                errors=[str(exc)],
            ) from exc
        latency_ms = int((time.perf_counter() - started) * 1000)

        choice = completion["choices"][0]
        text_output: str = (choice.get("message", {}).get("content") or "").strip()

        output: Dict[str, Any]
        try:
            output = orjson.loads(text_output)
        except orjson.JSONDecodeError:
            output = {"content": text_output}

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
