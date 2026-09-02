from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import random
import signal
import sys
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence
from uuid import UUID, uuid4

import httpx
from jose import jwt

DEMO_TENANT_ID = "00000000-0000-0000-0000-000000000100"
DEMO_FLOW_ID = "00000000-0000-0000-0000-000000000700"
DEMO_AGENT_ID = "00000000-0000-0000-0000-000000000600"

STRESS_SCOPES = (
    "execution:flow_run:create",
    "execution:flow_run:get",
    "execution:flow_run:resume",
    "execution:graph_state:get",
    "execution:node_runs:list",
    "execution:events:list",
    "execution:agent_run:create",
    "execution:agent_run:get",
    "execution:agent_run:cancel",
    "execution:agent_runs:list",
    "conversation:turn:create",
    "agents:card:get",
    "agents:a2a:send",
)

FLOW_PROMPTS = (
    "quanto gastei em comida no mes passado?",
    "preciso de ajuda com uma cobranca duplicada",
    "meu pedido ainda nao chegou, o que faco?",
    "quero cancelar minha assinatura",
    "como altero meu metodo de pagamento?",
)

AGENT_INSTRUCTIONS = (
    "resuma meus gastos do mes passado em uma frase",
    "diga ola em uma frase curta",
    "liste tres dicas de economia domestica",
    "explique o que e um estorno em uma frase",
)

BUCKET_GROWTH = 1.05
BUCKET_FLOOR_MS = 0.1
BUCKET_COUNT = 340


def now_ms() -> float:
    return time.perf_counter() * 1000.0


def new_trace_id() -> str:
    return uuid4().hex


def new_span_id() -> str:
    return uuid4().hex[:16]


def traceparent(trace_id: str, span_id: str) -> str:
    return f"00-{trace_id}-{span_id}-01"


class Latencies:
    __slots__ = ("buckets", "count", "total", "low", "high")

    def __init__(self) -> None:
        self.buckets = [0] * BUCKET_COUNT
        self.count = 0
        self.total = 0.0
        self.low = math.inf
        self.high = 0.0

    def record(self, ms: float) -> None:
        self.count += 1
        self.total += ms
        self.low = min(self.low, ms)
        self.high = max(self.high, ms)
        if ms <= BUCKET_FLOOR_MS:
            index = 0
        else:
            index = int(math.log(ms / BUCKET_FLOOR_MS) / math.log(BUCKET_GROWTH))
            index = min(max(index, 0), BUCKET_COUNT - 1)
        self.buckets[index] += 1

    def _value_at(self, index: int) -> float:
        return BUCKET_FLOOR_MS * (BUCKET_GROWTH ** index)

    def percentile(self, fraction: float) -> float:
        if self.count == 0:
            return 0.0
        target = fraction * self.count
        seen = 0
        for index, hits in enumerate(self.buckets):
            seen += hits
            if seen >= target:
                return round(self._value_at(index), 2)
        return round(self.high, 2)

    def summary(self) -> dict[str, Any]:
        if self.count == 0:
            return {"count": 0}
        return {
            "count": self.count,
            "mean_ms": round(self.total / self.count, 2),
            "min_ms": round(self.low, 2),
            "p50_ms": self.percentile(0.50),
            "p75_ms": self.percentile(0.75),
            "p90_ms": self.percentile(0.90),
            "p95_ms": self.percentile(0.95),
            "p99_ms": self.percentile(0.99),
            "max_ms": round(self.high, 2),
        }


@dataclass
class EndpointStats:
    key: str
    latencies: Latencies = field(default_factory=Latencies)
    statuses: Counter = field(default_factory=Counter)
    outcomes: Counter = field(default_factory=Counter)
    terminal: Counter = field(default_factory=Counter)
    errors: deque = field(default_factory=lambda: deque(maxlen=20))
    inflight: int = 0
    inflight_peak: int = 0

    def summary(self) -> dict[str, Any]:
        return {
            "endpoint": self.key,
            "latency": self.latencies.summary(),
            "status_codes": dict(sorted(self.statuses.items())),
            "outcomes": dict(sorted(self.outcomes.items())),
            "terminal_states": dict(sorted(self.terminal.items())),
            "inflight_peak": self.inflight_peak,
            "error_samples": list(self.errors),
        }


class Registry:
    def __init__(self) -> None:
        self.endpoints: dict[str, EndpointStats] = {}
        self.started_at = time.time()
        self.setup_defects: list[dict[str, Any]] = []

    def stats(self, key: str) -> EndpointStats:
        found = self.endpoints.get(key)
        if found is None:
            found = EndpointStats(key=key)
            self.endpoints[key] = found
        return found

    def enter(self, key: str) -> EndpointStats:
        stats = self.stats(key)
        stats.inflight += 1
        stats.inflight_peak = max(stats.inflight_peak, stats.inflight)
        return stats

    def total_requests(self) -> int:
        return sum(s.latencies.count for s in self.endpoints.values())

    def total_outcome(self, name: str) -> int:
        return sum(s.outcomes.get(name, 0) for s in self.endpoints.values())


SETUP_DEFECT_CODES = {
    "missing_idempotency_key",
    "access_policy_not_configured",
    "action_not_allowed",
    "rate_limit_policy_not_configured",
    "rate_limit_policy_not_published",
    "billing_policy_not_active",
    "auth_not_configured",
    "jwt_issuer_audience_not_configured",
}


@dataclass(frozen=True)
class Settings:
    base_url: str
    tenant_id: str
    flow_id: str
    agent_id: str
    duration_s: float
    concurrency_flow: int
    concurrency_conv: int
    concurrency_agent: int
    concurrency_a2a: int
    concurrency_read: int
    ramp_s: float
    think_ms: int
    poll_interval_ms: int
    poll_max_ms: int
    poll_timeout_s: float
    wait_flow: bool
    wait_agent: bool
    max_iterations: int
    report_interval_s: float
    json_report: str | None
    jwt_secret: str
    jwt_issuer: str
    jwt_audience: str
    jwt_algorithm: str
    jwt_ttl_s: int
    principal_type: str
    read_timeout_s: float
    seed: int
    unique_prompts: bool


def mint_token(settings: Settings, principal_id: str) -> str:
    issued = int(time.time())
    claims = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": issued,
        "exp": issued + settings.jwt_ttl_s,
        "tenant_id": settings.tenant_id,
        "principal_id": principal_id,
        "sub": principal_id,
        "principal_type": settings.principal_type,
        "scopes": list(STRESS_SCOPES),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


class Worker:
    def __init__(self, settings: Settings, index: int, plane: str) -> None:
        self.settings = settings
        self.index = index
        self.plane = plane
        self.principal_id = f"stress-{plane}-{index:03d}"
        self.user_id = f"stress-user-{plane}-{index:03d}"
        self.session_id = str(uuid4())
        self._token = mint_token(settings, self.principal_id)
        self._token_expires_at = time.time() + settings.jwt_ttl_s - 60

    def token(self) -> str:
        if time.time() >= self._token_expires_at:
            self._token = mint_token(self.settings, self.principal_id)
            self._token_expires_at = time.time() + self.settings.jwt_ttl_s - 60
        return self._token

    def headers(self, *, idempotent: bool, trace_id: str, stream: bool = False) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token()}",
            "Content-Type": "application/json",
            "traceparent": traceparent(trace_id, new_span_id()),
            "X-Trace-Id": trace_id,
            "X-Correlation-Id": str(uuid4()),
        }
        if idempotent:
            headers["Idempotency-Key"] = str(uuid4())
            headers["X-Request-Id"] = str(uuid4())
        if stream:
            headers["Accept"] = "text/event-stream"
        return headers


def classify(status: int, body: Any) -> tuple[str, str | None]:
    code = None
    if isinstance(body, dict):
        raw = body.get("code") or body.get("message")
        code = str(raw) if raw is not None else None
    if status in (200, 201):
        return "success", code
    if status == 202:
        return "pending", code
    if status == 409 and code and "idempotency_in_progress" in code:
        return "retry_pending", code
    if status == 429:
        return "throttled", code
    if code and any(defect in code for defect in SETUP_DEFECT_CODES):
        return "setup_defect", code
    if 400 <= status < 500:
        return "client_error", code
    if status >= 500:
        return "server_error", code
    return "other", code


def record(
    registry: Registry,
    stats: EndpointStats,
    *,
    elapsed_ms: float,
    status: int,
    body: Any,
    trace_id: str,
    terminal: str | None = None,
) -> str:
    stats.inflight -= 1
    stats.latencies.record(elapsed_ms)
    stats.statuses[str(status)] += 1
    outcome, code = classify(status, body)
    stats.outcomes[outcome] += 1
    if terminal:
        stats.terminal[terminal] += 1
    if outcome in ("client_error", "server_error", "setup_defect", "throttled"):
        sample = {
            "at": datetime.now(UTC).isoformat(),
            "status": status,
            "outcome": outcome,
            "code": code,
            "trace_id": trace_id,
            "body": json.dumps(body)[:512] if body is not None else None,
        }
        stats.errors.append(sample)
        if outcome == "setup_defect":
            registry.setup_defects.append({"endpoint": stats.key, **sample})
    return outcome


def record_transport_error(
    stats: EndpointStats, *, elapsed_ms: float, exc: BaseException, trace_id: str
) -> None:
    stats.inflight -= 1
    stats.latencies.record(elapsed_ms)
    stats.statuses["transport"] += 1
    stats.outcomes["transport_error"] += 1
    stats.errors.append(
        {
            "at": datetime.now(UTC).isoformat(),
            "status": "transport",
            "outcome": "transport_error",
            "code": type(exc).__name__,
            "trace_id": trace_id,
            "body": str(exc)[:512],
        }
    )


def make_prompt(settings: Settings, rng: random.Random, pool: Sequence[str]) -> str:
    base = rng.choice(pool)
    if not settings.unique_prompts:
        return base
    return f"{base} (ref {uuid4().hex[:12]})"


def parse_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {"_raw": response.text[:512]}


TERMINAL_RUN_STATES = {"COMPLETED", "FAILED", "CANCELLED", "ESCALATED"}
WAITING_RUN_STATES = {"WAITING", "WAITING_INPUT"}


async def drive_flow_plane(
    client: httpx.AsyncClient,
    worker: Worker,
    registry: Registry,
    settings: Settings,
    stop: asyncio.Event,
    rng: random.Random,
) -> None:
    create_key = "POST /core/v1/executions/flow-runs"
    get_key = "GET /core/v1/executions/flow-runs/{flow_run_id}"

    while not stop.is_set():
        trace_id = new_trace_id()
        payload = {
            "flow_id": settings.flow_id,
            "session_id": str(uuid4()),
            "user_id": worker.user_id,
            "input": {"user_input": make_prompt(settings, rng, FLOW_PROMPTS)},
            "metadata": {},
        }
        stats = registry.enter(create_key)
        started = now_ms()
        try:
            response = await client.post(
                "/core/v1/executions/flow-runs",
                params={"wait": str(settings.wait_flow).lower()},
                headers=worker.headers(idempotent=True, trace_id=trace_id),
                json=payload,
            )
        except Exception as exc:
            record_transport_error(stats, elapsed_ms=now_ms() - started, exc=exc, trace_id=trace_id)
            await sleep_or_stop(stop, settings.think_ms / 1000.0)
            continue

        body = parse_json(response)
        terminal = None
        if isinstance(body, dict):
            terminal = body.get("canonical_status") or body.get("status")
        outcome = record(
            registry,
            stats,
            elapsed_ms=now_ms() - started,
            status=response.status_code,
            body=body,
            trace_id=trace_id,
            terminal=terminal,
        )

        if outcome in ("success", "pending") and isinstance(body, dict) and body.get("id"):
            run_id = str(body["id"])
            state = str(body.get("canonical_status") or body.get("status") or "")
            if state not in TERMINAL_RUN_STATES:
                await poll_flow_run(client, worker, registry, settings, stop, run_id, get_key)

        await sleep_or_stop(stop, settings.think_ms / 1000.0)


async def poll_flow_run(
    client: httpx.AsyncClient,
    worker: Worker,
    registry: Registry,
    settings: Settings,
    stop: asyncio.Event,
    run_id: str,
    get_key: str,
) -> None:
    deadline = time.time() + settings.poll_timeout_s
    delay = settings.poll_interval_ms / 1000.0
    while time.time() < deadline and not stop.is_set():
        await sleep_or_stop(stop, delay)
        delay = min(delay * 2, settings.poll_max_ms / 1000.0)

        trace_id = new_trace_id()
        stats = registry.enter(get_key)
        started = now_ms()
        try:
            response = await client.get(
                f"/core/v1/executions/flow-runs/{run_id}",
                headers=worker.headers(idempotent=False, trace_id=trace_id),
            )
        except Exception as exc:
            record_transport_error(stats, elapsed_ms=now_ms() - started, exc=exc, trace_id=trace_id)
            return

        body = parse_json(response)
        state = ""
        if isinstance(body, dict):
            state = str(body.get("canonical_status") or body.get("status") or "")
        record(
            registry,
            stats,
            elapsed_ms=now_ms() - started,
            status=response.status_code,
            body=body,
            trace_id=trace_id,
            terminal=state or None,
        )
        if state in TERMINAL_RUN_STATES:
            return
        if state in WAITING_RUN_STATES:
            registry.stats(get_key).outcomes["waiting"] += 1
            return
    registry.stats(get_key).outcomes["unresolved"] += 1


async def drive_conversation_plane(
    client: httpx.AsyncClient,
    worker: Worker,
    registry: Registry,
    settings: Settings,
    stop: asyncio.Event,
    rng: random.Random,
) -> None:
    key = "POST /core/v1/conversations"

    while not stop.is_set():
        trace_id = new_trace_id()
        payload = {
            "agent_id": settings.agent_id,
            "session_id": worker.session_id,
            "user_id": worker.user_id,
            "user_input": make_prompt(settings, rng, FLOW_PROMPTS),
            "metadata": {},
        }
        stats = registry.enter(key)
        started = now_ms()
        ttfb_ms = None
        deltas = 0
        terminal_event = "no_terminal_event"
        error_code = None
        status = 0
        try:
            async with client.stream(
                "POST",
                "/core/v1/conversations",
                headers=worker.headers(idempotent=True, trace_id=trace_id, stream=True),
                json=payload,
            ) as response:
                status = response.status_code
                if status >= 400:
                    raw = await response.aread()
                    body = json.loads(raw) if raw else {}
                    record(
                        registry,
                        stats,
                        elapsed_ms=now_ms() - started,
                        status=status,
                        body=body,
                        trace_id=trace_id,
                        terminal="http_error",
                    )
                    await sleep_or_stop(stop, settings.think_ms / 1000.0)
                    continue

                async for event, data in iter_sse(response):
                    if ttfb_ms is None:
                        ttfb_ms = now_ms() - started
                    if event == "content_delta":
                        deltas += 1
                    elif event == "done":
                        terminal_event = "done"
                        break
                    elif event == "error":
                        code = data.get("error_code") or data.get("code")
                        if data.get("code") == "conversation_turn_failed":
                            terminal_event = "conversation_turn_failed"
                            error_code = code
                            break
                        registry.stats(key).outcomes["stream_error_event"] += 1
        except Exception as exc:
            record_transport_error(stats, elapsed_ms=now_ms() - started, exc=exc, trace_id=trace_id)
            await sleep_or_stop(stop, settings.think_ms / 1000.0)
            continue

        elapsed = now_ms() - started
        synthetic_status = status if terminal_event == "done" else 599
        body = None if terminal_event == "done" else {"code": error_code or terminal_event}
        record(
            registry,
            stats,
            elapsed_ms=elapsed,
            status=synthetic_status,
            body=body,
            trace_id=trace_id,
            terminal=terminal_event,
        )
        registry.stats("SSE /core/v1/conversations (ttfb)").latencies.record(ttfb_ms or elapsed)
        registry.stats(key).outcomes[f"deltas_{'some' if deltas else 'none'}"] += 1

        await sleep_or_stop(stop, settings.think_ms / 1000.0)


async def iter_sse(response: httpx.Response):
    event = "message"
    data_lines: list[str] = []
    async for line in response.aiter_lines():
        if line.startswith(":"):
            continue
        if line == "":
            if data_lines:
                raw = "\n".join(data_lines)
                try:
                    parsed = json.loads(raw)
                except ValueError:
                    parsed = {"_raw": raw}
                yield event, parsed if isinstance(parsed, dict) else {"value": parsed}
            event = "message"
            data_lines = []
            continue
        field, _, value = line.partition(":")
        value = value[1:] if value.startswith(" ") else value
        if field == "event":
            event = value
        elif field == "data":
            data_lines.append(value)


async def drive_agent_plane(
    client: httpx.AsyncClient,
    worker: Worker,
    registry: Registry,
    settings: Settings,
    stop: asyncio.Event,
    rng: random.Random,
) -> None:
    key = "POST /core/v1/executions/agent-runs"

    while not stop.is_set():
        trace_id = new_trace_id()
        payload = {
            "agent_id": settings.agent_id,
            "instruction": make_prompt(settings, rng, AGENT_INSTRUCTIONS),
            "payload": {},
            "context": [],
            "max_iterations": settings.max_iterations,
            "metadata": {},
        }
        stats = registry.enter(key)
        started = now_ms()
        try:
            response = await client.post(
                "/core/v1/executions/agent-runs",
                params={"wait": str(settings.wait_agent).lower()},
                headers=worker.headers(idempotent=True, trace_id=trace_id),
                json=payload,
            )
        except Exception as exc:
            record_transport_error(stats, elapsed_ms=now_ms() - started, exc=exc, trace_id=trace_id)
            await sleep_or_stop(stop, settings.think_ms / 1000.0)
            continue

        body = parse_json(response)
        terminal = body.get("canonical_status") if isinstance(body, dict) else None
        record(
            registry,
            stats,
            elapsed_ms=now_ms() - started,
            status=response.status_code,
            body=body,
            trace_id=trace_id,
            terminal=terminal,
        )
        await sleep_or_stop(stop, settings.think_ms / 1000.0)


async def drive_a2a_plane(
    client: httpx.AsyncClient,
    worker: Worker,
    registry: Registry,
    settings: Settings,
    stop: asyncio.Event,
    rng: random.Random,
) -> None:
    key = "POST /core/v1/agents/{agent_id}/a2a"

    while not stop.is_set():
        trace_id = new_trace_id()
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid4()),
            "method": "message/send",
            "params": {
                "message": {
                    "kind": "message",
                    "messageId": str(uuid4()),
                    "role": "user",
                    "parts": [{"kind": "text", "text": make_prompt(settings, rng, AGENT_INSTRUCTIONS)}],
                }
            },
        }
        stats = registry.enter(key)
        started = now_ms()
        try:
            response = await client.post(
                f"/core/v1/agents/{settings.agent_id}/a2a",
                headers=worker.headers(idempotent=False, trace_id=trace_id),
                json=payload,
            )
        except Exception as exc:
            record_transport_error(stats, elapsed_ms=now_ms() - started, exc=exc, trace_id=trace_id)
            await sleep_or_stop(stop, settings.think_ms / 1000.0)
            continue

        body = parse_json(response)
        rpc_error = body.get("error") if isinstance(body, dict) else None
        terminal = None
        if isinstance(body, dict) and isinstance(body.get("result"), dict):
            terminal = str((body["result"].get("status") or {}).get("state"))
        synthetic_status = response.status_code
        synthetic_body: Any = body
        if rpc_error:
            synthetic_status = 599
            synthetic_body = {"code": f"jsonrpc_{rpc_error.get('code')}"}
            terminal = f"jsonrpc_error_{rpc_error.get('code')}"
        record(
            registry,
            stats,
            elapsed_ms=now_ms() - started,
            status=synthetic_status,
            body=synthetic_body,
            trace_id=trace_id,
            terminal=terminal,
        )
        await sleep_or_stop(stop, settings.think_ms / 1000.0)


READ_ENDPOINTS: tuple[tuple[str, str, dict[str, Any]], ...] = (
    ("GET /core/v1/executions/agent-runs", "/core/v1/executions/agent-runs", {"limit": 20}),
    ("GET /core/v1/agents/{agent_id}/agent-card", "/core/v1/agents/{agent_id}/agent-card", {}),
    ("GET /health", "/health", {}),
)


async def drive_read_plane(
    client: httpx.AsyncClient,
    worker: Worker,
    registry: Registry,
    settings: Settings,
    stop: asyncio.Event,
    rng: random.Random,
) -> None:
    while not stop.is_set():
        key, path, params = rng.choice(READ_ENDPOINTS)
        url = path.replace("{agent_id}", settings.agent_id)
        trace_id = new_trace_id()
        stats = registry.enter(key)
        started = now_ms()
        try:
            response = await client.get(
                url,
                params=params,
                headers=worker.headers(idempotent=False, trace_id=trace_id),
            )
        except Exception as exc:
            record_transport_error(stats, elapsed_ms=now_ms() - started, exc=exc, trace_id=trace_id)
            await sleep_or_stop(stop, settings.think_ms / 1000.0)
            continue

        record(
            registry,
            stats,
            elapsed_ms=now_ms() - started,
            status=response.status_code,
            body=parse_json(response),
            trace_id=trace_id,
        )
        await sleep_or_stop(stop, settings.think_ms / 1000.0)


async def sleep_or_stop(stop: asyncio.Event, seconds: float) -> None:
    if seconds <= 0:
        return
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except (TimeoutError, asyncio.TimeoutError):
        return


PLANES = {
    "flow": drive_flow_plane,
    "conversation": drive_conversation_plane,
    "agent": drive_agent_plane,
    "a2a": drive_a2a_plane,
    "read": drive_read_plane,
}


def build_client(settings: Settings, connections: int) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.base_url,
        timeout=httpx.Timeout(
            connect=5.0, read=settings.read_timeout_s, write=10.0, pool=10.0
        ),
        limits=httpx.Limits(
            max_connections=max(connections, 4),
            max_keepalive_connections=max(connections, 4),
        ),
        follow_redirects=False,
    )


async def preflight(settings: Settings, registry: Registry, planes: dict[str, int]) -> bool:
    async with build_client(settings, 4) as client:
        try:
            response = await client.get("/health")
        except Exception as exc:
            print(f"preflight FAILED: cannot reach {settings.base_url}/health ({exc})")
            return False
        if response.status_code != 200:
            print(f"preflight FAILED: /health returned {response.status_code}")
            return False
        print(f"preflight: /health 200 {response.text.strip()[:80]}")

        worker = Worker(settings, 0, "preflight")
        checks: list[tuple[str, Any]] = []

        if planes.get("flow"):
            trace_id = new_trace_id()
            r = await client.post(
                "/core/v1/executions/flow-runs",
                params={"wait": "false"},
                headers=worker.headers(idempotent=True, trace_id=trace_id),
                json={
                    "flow_id": settings.flow_id,
                    "session_id": str(uuid4()),
                    "user_id": worker.user_id,
                    "input": {"user_input": FLOW_PROMPTS[0]},
                    "metadata": {},
                },
            )
            checks.append(("flow", r))
        if planes.get("agent"):
            trace_id = new_trace_id()
            r = await client.post(
                "/core/v1/executions/agent-runs",
                params={"wait": "true"},
                headers=worker.headers(idempotent=True, trace_id=trace_id),
                json={
                    "agent_id": settings.agent_id,
                    "instruction": AGENT_INSTRUCTIONS[1],
                    "payload": {},
                    "context": [],
                    "max_iterations": 2,
                    "metadata": {},
                },
            )
            checks.append(("agent", r))
        if planes.get("a2a"):
            trace_id = new_trace_id()
            r = await client.post(
                f"/core/v1/agents/{settings.agent_id}/a2a",
                headers=worker.headers(idempotent=False, trace_id=trace_id),
                json={
                    "jsonrpc": "2.0",
                    "id": str(uuid4()),
                    "method": "message/send",
                    "params": {
                        "message": {
                            "kind": "message",
                            "messageId": str(uuid4()),
                            "role": "user",
                            "parts": [{"kind": "text", "text": AGENT_INSTRUCTIONS[1]}],
                        }
                    },
                },
            )
            checks.append(("a2a", r))

        healthy = True
        for plane, response in checks:
            body = parse_json(response)
            outcome, code = classify(response.status_code, body)
            rpc_error = body.get("error") if isinstance(body, dict) else None
            if rpc_error:
                outcome, code = "server_error", f"jsonrpc_{rpc_error.get('code')}"
                if str(rpc_error.get("message")) in SETUP_DEFECT_CODES:
                    outcome, code = "setup_defect", str(rpc_error.get("message"))
            marker = "ok " if outcome in ("success", "pending") else "FAIL"
            print(f"preflight: {marker} {plane:12s} HTTP {response.status_code} {code or ''}")
            if outcome == "setup_defect":
                healthy = False
                registry.setup_defects.append(
                    {"endpoint": plane, "status": response.status_code, "code": code}
                )
        if planes.get("conversation"):
            print("preflight: ok  conversation (stream verified at run start)")
        return healthy


def render_live(registry: Registry, settings: Settings, elapsed: float) -> None:
    total = registry.total_requests()
    rate = total / elapsed if elapsed > 0 else 0.0
    print(
        f"\n[{elapsed:6.1f}s] requests={total} rate={rate:.2f}/s "
        f"success={registry.total_outcome('success')} "
        f"pending={registry.total_outcome('pending')} "
        f"throttled={registry.total_outcome('throttled')} "
        f"client_err={registry.total_outcome('client_error')} "
        f"server_err={registry.total_outcome('server_error')} "
        f"transport={registry.total_outcome('transport_error')}"
    )
    for key in sorted(registry.endpoints):
        stats = registry.endpoints[key]
        if stats.latencies.count == 0:
            continue
        summary = stats.latencies.summary()
        statuses = " ".join(f"{k}:{v}" for k, v in sorted(stats.statuses.items()))
        print(
            f"  {key:52s} n={summary['count']:5d} "
            f"p50={summary['p50_ms']:8.1f} p95={summary['p95_ms']:9.1f} "
            f"max={summary['max_ms']:9.1f}  [{statuses}]"
        )


async def reporter(registry: Registry, settings: Settings, stop: asyncio.Event) -> None:
    while not stop.is_set():
        await sleep_or_stop(stop, settings.report_interval_s)
        if stop.is_set():
            return
        render_live(registry, settings, time.time() - registry.started_at)


async def run(settings: Settings, planes: dict[str, int]) -> int:
    registry = Registry()
    print(f"target      : {settings.base_url}")
    print(f"tenant      : {settings.tenant_id}")
    print(f"planes      : " + ", ".join(f"{k}={v}" for k, v in planes.items() if v))
    print(f"duration    : {'until SIGINT' if settings.duration_s <= 0 else f'{settings.duration_s:.0f}s'}")
    print(f"prompts     : {'unique per request (real LLM calls)' if settings.unique_prompts else 'fixed pool (mostly semantic-cache hits)'}")
    print()

    if not await preflight(settings, registry, planes):
        print("\npreflight found setup defects; aborting before generating load.")
        for defect in registry.setup_defects:
            print(f"  {defect}")
        print(
            "\nHint: run resources/scripts/stress/prepare_stress_env.py to publish the governance "
            "policies the driver needs."
        )
        return 2

    print("\npreflight passed; starting load\n")
    registry.started_at = time.time()

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass

    clients: list[httpx.AsyncClient] = []
    tasks: list[asyncio.Task] = []

    async def spawn(plane: str, count: int) -> None:
        client = build_client(settings, count * 2)
        clients.append(client)
        for index in range(count):
            worker = Worker(settings, index, plane)
            rng = random.Random(settings.seed + hash(plane) % 10000 + index)
            delay = (settings.ramp_s / count) * index if count and settings.ramp_s else 0.0

            async def runner(
                fn=PLANES[plane], w=worker, c=client, r=rng, d=delay
            ) -> None:
                await sleep_or_stop(stop, d)
                if stop.is_set():
                    return
                await fn(c, w, registry, settings, stop, r)

            tasks.append(asyncio.create_task(runner(), name=f"{plane}-{index}"))

    for plane, count in planes.items():
        if count:
            await spawn(plane, count)

    tasks.append(asyncio.create_task(reporter(registry, settings, stop), name="reporter"))

    if settings.duration_s > 0:
        tasks.append(
            asyncio.create_task(deadline(stop, settings.duration_s), name="deadline")
        )

    try:
        await stop.wait()
    finally:
        stop.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for client in clients:
            await client.aclose()

    elapsed = time.time() - registry.started_at
    print("\n" + "=" * 100)
    print("FINAL REPORT")
    print("=" * 100)
    render_live(registry, settings, elapsed)

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "base_url": settings.base_url,
        "tenant_id": settings.tenant_id,
        "planes": {k: v for k, v in planes.items() if v},
        "duration_s": round(elapsed, 2),
        "total_requests": registry.total_requests(),
        "throughput_rps": round(registry.total_requests() / elapsed, 3) if elapsed else 0.0,
        "endpoints": [registry.endpoints[k].summary() for k in sorted(registry.endpoints)],
        "setup_defects": registry.setup_defects,
    }
    if settings.json_report:
        Path(settings.json_report).write_text(json.dumps(report, indent=2))
        print(f"\njson report written to {settings.json_report}")

    print("\nGrafana: http://localhost:3000   Tempo: http://localhost:3200   "
          "Prometheus: http://localhost:9090")
    print("Metrics lag ~45s behind the run (app 15s + spanmetrics 15s + scrape 15s).")

    return 1 if registry.total_outcome("server_error") else 0


async def deadline(stop: asyncio.Event, seconds: float) -> None:
    await sleep_or_stop(stop, seconds)
    stop.set()


def parse_duration(raw: str) -> float:
    raw = raw.strip().lower()
    if raw in ("0", ""):
        return 0.0
    if raw.endswith("ms"):
        return float(raw[:-2]) / 1000.0
    if raw.endswith("s"):
        return float(raw[:-1])
    if raw.endswith("m"):
        return float(raw[:-1]) * 60
    if raw.endswith("h"):
        return float(raw[:-1]) * 3600
    return float(raw)


def env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    env_file = Path(__file__).resolve().parents[3] / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return default


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="stress_driver",
        description="Continuous parallel load driver for agent-orchestration-core. Exercises flow "
        "runs, conversations (SSE), agent runs and A2A concurrently, emits W3C traceparent so every "
        "request is findable in Tempo, and reports latency percentiles and status distributions.",
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--duration", default="5m", help="e.g. 90s, 10m, 1h; 0 = until Ctrl-C")
    parser.add_argument("--flow", type=int, default=4, help="concurrent flow-run workers")
    parser.add_argument("--conversation", type=int, default=2, help="concurrent SSE workers")
    parser.add_argument("--agent", type=int, default=2, help="concurrent agent-run workers")
    parser.add_argument("--a2a", type=int, default=1, help="concurrent A2A workers")
    parser.add_argument("--read", type=int, default=2, help="concurrent read-load workers")
    parser.add_argument("--ramp", default="10s", help="linear ramp-up before steady state")
    parser.add_argument("--think-ms", type=int, default=250, help="pause between iterations")
    parser.add_argument("--tenant-id", default=DEMO_TENANT_ID)
    parser.add_argument("--flow-id", default=DEMO_FLOW_ID)
    parser.add_argument("--agent-id", default=DEMO_AGENT_ID)
    parser.add_argument("--principal-type", default="machine", choices=("machine", "human"))
    parser.add_argument("--wait-flow", action="store_true", help="pass ?wait=true on flow runs")
    parser.add_argument("--no-wait-agent", action="store_true", help="pass ?wait=false on agent runs")
    parser.add_argument("--max-iterations", type=int, default=2)
    parser.add_argument("--poll-interval-ms", type=int, default=400)
    parser.add_argument("--poll-max-ms", type=int, default=3000)
    parser.add_argument("--poll-timeout", default="120s")
    parser.add_argument("--read-timeout", default="300s", help="must exceed inline graph latency")
    parser.add_argument("--report-interval", default="10s")
    parser.add_argument("--json-report", default=None)
    parser.add_argument("--jwt-ttl", type=int, default=3600)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument(
        "--unique-prompts",
        action="store_true",
        help="append a nonce to every prompt so each request misses the semantic cache and hits the "
        "real LLM provider. Far more expensive; without it most load is served from cache.",
    )
    args = parser.parse_args(argv)

    secret = env("JWT_SECRET", "")
    if not secret:
        print("JWT_SECRET not found in environment or .env", file=sys.stderr)
        return 2

    settings = Settings(
        base_url=args.base_url.rstrip("/"),
        tenant_id=args.tenant_id,
        flow_id=args.flow_id,
        agent_id=args.agent_id,
        duration_s=parse_duration(args.duration),
        concurrency_flow=args.flow,
        concurrency_conv=args.conversation,
        concurrency_agent=args.agent,
        concurrency_a2a=args.a2a,
        concurrency_read=args.read,
        ramp_s=parse_duration(args.ramp),
        think_ms=args.think_ms,
        poll_interval_ms=args.poll_interval_ms,
        poll_max_ms=args.poll_max_ms,
        poll_timeout_s=parse_duration(args.poll_timeout),
        wait_flow=args.wait_flow,
        wait_agent=not args.no_wait_agent,
        max_iterations=args.max_iterations,
        report_interval_s=parse_duration(args.report_interval),
        json_report=args.json_report,
        jwt_secret=secret,
        jwt_issuer=env("JWT_ISSUER", "dev-issuer"),
        jwt_audience=env("JWT_AUDIENCE", "dev-audience"),
        jwt_algorithm=env("JWT_ALGORITHM", "HS256"),
        jwt_ttl_s=args.jwt_ttl,
        principal_type=args.principal_type,
        read_timeout_s=parse_duration(args.read_timeout),
        seed=args.seed,
        unique_prompts=args.unique_prompts,
    )

    planes = {
        "flow": args.flow,
        "conversation": args.conversation,
        "agent": args.agent,
        "a2a": args.a2a,
        "read": args.read,
    }

    try:
        return asyncio.run(run(settings, planes))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
