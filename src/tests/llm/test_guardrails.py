import uuid

import pytest

from domain.execution.schemas.guardrails import GuardrailDecision, GuardrailDecisionType
from domain.execution.schemas.trace import TraceContext
from domain.execution.services.guardrails.guardrail_engine import GuardrailEngine
from domain.llm.schemas.llm import LLMRequest, LLMTaskType, LLMResult
from domain.llm.services.llm_executor import LLMExecutor
from domain.llm.services.provider_selector import LLMProviderSelection
from exceptions.service_exceptions import DomainValidationException


class _FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, dict] = {}
        self.counts: dict[str, int] = {}

    async def get(self, key: str):
        return self.data.get(key)

    async def set(self, key: str, data: dict, ttl: int = 0):
        self.data[key] = data

    async def delete(self, key: str):
        self.data.pop(key, None)

    async def incr_with_ttl(self, key: str, ttl: int):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]


class _FixedCostEngine:
    def __init__(self, cost: float) -> None:
        self.cost = cost

    async def compute_cost(self, *, provider: str, provider_model: str, token_usage: dict):
        return self.cost


@pytest.mark.asyncio
async def test_guardrail_blocks_on_flow_cost():
    engine = GuardrailEngine(_FakeRedis(), _FixedCostEngine(cost=10.0))
    request = LLMRequest(task_type=LLMTaskType.INTENT_SELECTION, model_alias="m")
    decision = await engine.check_and_reserve(
        tenant_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        request=request,
        policy_llm={"max_cost_usd_per_flow_run": 5.0},
        provider="OPENAI",
        provider_model="gpt-4o",
    )
    assert decision.decision == GuardrailDecisionType.BLOCK
    assert decision.reason_code == "COST_LIMIT_FLOW_RUN"


@pytest.mark.asyncio
async def test_guardrail_degrades_with_override():
    engine = GuardrailEngine(_FakeRedis(), _FixedCostEngine(cost=10.0))
    request = LLMRequest(task_type=LLMTaskType.INTENT_SELECTION, model_alias="m")
    decision = await engine.check_and_reserve(
        tenant_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        request=request,
        policy_llm={"max_cost_usd_per_flow_run": 5.0, "degrade_model_alias": "text-small"},
        provider="OPENAI",
        provider_model="gpt-4o",
    )
    assert decision.decision == GuardrailDecisionType.DEGRADE
    assert decision.overrides.get("model_alias") == "text-small"


@pytest.mark.asyncio
async def test_guardrail_blocks_on_rate_flow():
    engine = GuardrailEngine(_FakeRedis(), _FixedCostEngine(cost=0))
    request = LLMRequest(task_type=LLMTaskType.INTENT_SELECTION, model_alias="m")
    decision = await engine.check_and_reserve(
        tenant_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        request=request,
        policy_llm={"max_llm_calls_per_flow_run": 0},
        provider="OPENAI",
        provider_model="gpt-4o",
    )
    assert decision.decision == GuardrailDecisionType.BLOCK
    assert decision.reason_code == "RATE_LIMIT_FLOW_RUN"


class _GuardrailEngineStub:
    def __init__(self, decision: GuardrailDecision) -> None:
        self.decision = decision
        self.recorded_cost = None

    async def check_and_reserve(self, **_: dict):
        return self.decision

    async def record_post_call_cost(self, *, cost_usd, **kwargs):
        self.recorded_cost = cost_usd


class _Repo:
    def __init__(self) -> None:
        self.events = []

    async def append_execution_event(
        self,
        *,
        tenant_id,
        session_id,
        flow_run_id,
        event_type,
        payload,
        correlation_id,
        causation_id,
        schema_version,
        node_id=None,
        edge_id=None,
    ):
        self.events.append(event_type)


class _Provider:
    def __init__(self) -> None:
        self.calls = 0

    async def infer(self, request):
        self.calls += 1
        return LLMResult(output={"ok": True})


class _Selector:
    async def select(self, *, tenant_id, provider, model_alias):
        return LLMProviderSelection(
            provider=provider, provider_model=model_alias, base_url=None, credential_secret_ref=None
        )


class _ProviderFactory:
    def __init__(self, provider: _Provider) -> None:
        self.provider = provider

    def __call__(self, selection: LLMProviderSelection):
        return self.provider


@pytest.mark.asyncio
async def test_llm_executor_blocks_on_guardrail():
    repo = _Repo()
    provider = _Provider()
    guardrail = _GuardrailEngineStub(
        GuardrailDecision(
            decision=GuardrailDecisionType.BLOCK, reason_code="BLOCKED", applied_limits={}, overrides={}
        )
    )
    executor = LLMExecutor(
        repo,
        provider,
        guardrail_engine=guardrail,
    )
    request = LLMRequest(task_type=LLMTaskType.INTENT_SELECTION, model_alias="m")
    with pytest.raises(DomainValidationException):
        await executor.execute_llm(
            request=request,
            trace=TraceContext(
                trace_id=uuid.uuid4(),
                flow_run_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
            ),
            tenant_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            flow_run_id=uuid.uuid4(),
            correlation_id=uuid.uuid4(),
        )
    assert provider.calls == 0
    assert "GuardrailBlocked" in repo.events


@pytest.mark.asyncio
async def test_llm_executor_degrades_and_calls_provider():
    repo = _Repo()
    provider = _Provider()
    guardrail = _GuardrailEngineStub(
        GuardrailDecision(
            decision=GuardrailDecisionType.DEGRADE,
            reason_code="COST_LIMIT",
            applied_limits={},
            overrides={"model_alias": "text-small"},
        )
    )
    executor = LLMExecutor(
        repo,
        provider,
        guardrail_engine=guardrail,
        provider_selector=_Selector(),
        provider_factory=_ProviderFactory(provider),
    )
    request = LLMRequest(task_type=LLMTaskType.INTENT_SELECTION, model_alias="m")
    await executor.execute_llm(
        request=request,
        trace=TraceContext(
            trace_id=uuid.uuid4(),
            flow_run_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
        ),
        tenant_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
    )
    assert provider.calls == 1
    assert "GuardrailDegraded" in repo.events
