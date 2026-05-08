from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

for _repo in Path(__file__).resolve().parents:
    if (_repo / "pyproject.toml").exists():
        sys.path.insert(0, str(_repo / "src"))
        sys.path.insert(0, str(_repo / "resources" / "scripts"))
        sys.path.insert(0, str(_repo))
        break
else:
    raise SystemExit("repository root not found")

from exceptions.service_exceptions import DomainValidationException

from wait_for_db import wait_for_db
from seeds.demo.seed_01_tenant import seed_tenant
from seeds.demo.seed_03_model import seed_model
from seeds.demo.seed_04_policy import seed_policy
from seeds.demo.seed_05_tool import seed_tool
from seeds.demo.seed_06_agent import seed_agent
from seeds.demo.seed_07_flow import seed_flow
from seeds.demo.seed_08_nodes import seed_nodes
from seeds.demo.seed_09_prompts import seed_prompts
from seeds.demo.seed_10_bindings import seed_bindings
from seeds.demo.seed_11_graph import seed_graph
from seeds.demo.seed_12_runtime_policy import seed_runtime_policy
from seeds.demo.seed_13_llm_provider_config import seed_llm_provider_config
from seeds.demo.seed_14_llm_model_mapping import seed_llm_model_mapping
from seeds.demo.seed_15_node_ai_execution_policy_binding import (
    seed_node_ai_execution_policy_binding,
)
from seeds.demo.seed_16_router import seed_router
from seeds.demo.seed_17_llm_pricing import seed_llm_pricing
from seeds.demo.seed_18_access_policy import seed_access_policy
from seeds.demo.seed_19_rate_limit_policy import seed_rate_limit_policy
from seeds.demo.seed_20_billing_policy import seed_billing_policy
from seeds.demo.seed_21_rag import seed_rag
from seeds.demo.seed_22_tool_catalog_rag import seed_tool_catalog_rag
from seeds.demo.seed_22_memory_policy import seed_memory_policy
from seeds.demo.seed_23_rag_policy import seed_rag_policy
from seeds.demo.seed_24_user_prompt import seed_user_prompt
from seeds.demo.seed_25_mcp_server import seed_mcp_server
from seeds.demo.seed_26_flow_snapshot_deployment import seed_flow_snapshot_deployment
from seeds.demo.seed_27_tenant_mcp_credential import seed_tenant_mcp_credential


async def main() -> None:
    try:
        if not os.getenv("DATABASE_URL"):
            print("DATABASE_URL environment variable is not set", file=sys.stderr)
            sys.exit(1)
        await wait_for_db()

        seeds = [
            ("Tenant", seed_tenant),
            ("Model", seed_model),
            ("Policy", seed_policy),
            ("Tool", seed_tool),
            ("RAG", seed_rag),
            ("Tool Catalog RAG", seed_tool_catalog_rag),
            ("Agent", seed_agent),
            ("Flow", seed_flow),
            ("Prompts", seed_prompts),
            ("Nodes", seed_nodes),
            ("User prompt", seed_user_prompt),
            ("Bindings", seed_bindings),
            ("Graph", seed_graph),
            ("Runtime Policy", seed_runtime_policy),
            ("LLM Provider Config", seed_llm_provider_config),
            ("LLM Model Mapping", seed_llm_model_mapping),
            ("Node AI Execution Policy Binding", seed_node_ai_execution_policy_binding),
            ("Router", seed_router),
            ("LLM Pricing", seed_llm_pricing),
            ("Access Policy", seed_access_policy),
            ("Rate Limit Policy", seed_rate_limit_policy),
            ("Billing Policy", seed_billing_policy),
            ("Memory Policy", seed_memory_policy),
            ("RAG Policy", seed_rag_policy),
            ("Flow Snapshot Deployment", seed_flow_snapshot_deployment),
            ("MCP server", seed_mcp_server),
            ("Tenant MCP credential", seed_tenant_mcp_credential),
        ]

        try:
            for name, seed_func in seeds:
                await seed_func()
        except DomainValidationException as exc:
            print(
                {
                    "code": exc.name,
                    "message": exc.message,
                    "correlation_id": None,
                    "details": {
                        "service": exc.service,
                        "resource": 'resources.scripts.seeds.demo.run.py',
                        "errors": exc.errors(),
                    },
                    "input_data": exc.input_data
                }
            )
            raise exc from exc

        print("Bootstrap completed successfully", file=sys.stdout)
        sys.exit(0)
    except Exception as e:
        print(f"Error during bootstrap: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
