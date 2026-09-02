"""Replay committed histories against the current FlowRunWorkflow code.

This is the only test that catches non-determinism introduced by editing the
traversal loop. Regenerate the fixtures deliberately (and review the diff) when
a workflow change is intended to be incompatible with in-flight runs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Replayer

from adapters.temporal.sandbox import build_workflow_runner
from adapters.temporal.workflow import FlowRunWorkflow

HISTORIES = Path(__file__).parent / "histories"


@pytest.mark.parametrize("history_file", sorted(HISTORIES.glob("*.json")), ids=lambda p: p.stem)
@pytest.mark.asyncio
async def test_workflow_replays_committed_history(history_file: Path) -> None:
    history_json = json.loads(history_file.read_text())

    replayer = Replayer(
        workflows=[FlowRunWorkflow],
        workflow_runner=build_workflow_runner(),
        data_converter=pydantic_data_converter,
    )

    await replayer.replay_workflow(WorkflowHistory.from_json(history_file.stem, history_json))
