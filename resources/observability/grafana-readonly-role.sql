DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'grafana_readonly') THEN
        CREATE ROLE grafana_readonly LOGIN PASSWORD 'grafana_readonly';
    END IF;
END
$$;

ALTER ROLE grafana_readonly SET statement_timeout = '20s';
ALTER ROLE grafana_readonly SET idle_in_transaction_session_timeout = '30s';
ALTER ROLE grafana_readonly SET default_transaction_read_only = on;

GRANT CONNECT ON DATABASE agent_router TO grafana_readonly;
GRANT USAGE ON SCHEMA public TO grafana_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO grafana_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO grafana_readonly;

REVOKE SELECT ON flow_run FROM grafana_readonly;
REVOKE SELECT ON node_run FROM grafana_readonly;

GRANT SELECT (
    flow_run_id, origin_flow_run_id, flow_version_id, session_id, user_id, interaction_id,
    status, canonical_status, correlation_id, started_at, finished_at,
    waiting_reason, waiting_deadline_at, flow_graph_snapshot_id, flow_snapshot_id,
    flow_deployment_id, execution_plan_hash, runtime_policy_hash, tool_catalog_hash,
    llm_provider_config_hash, trace_id, root_observation_id, temporal_workflow_id,
    temporal_run_id, turn_index, created_at, updated_at
) ON flow_run TO grafana_readonly;

GRANT SELECT (
    node_run_id, flow_run_id, node_id, status, canonical_status, correlation_id,
    started_at, finished_at, created_at, updated_at
) ON node_run TO grafana_readonly;

CREATE OR REPLACE VIEW grafana_flow_run AS
SELECT
    fr.flow_run_id,
    fr.session_id,
    fr.flow_version_id,
    fr.flow_graph_snapshot_id,
    fr.canonical_status,
    fr.status,
    fr.trace_id,
    fr.root_observation_id,
    fr.created_at,
    fr.started_at,
    fr.finished_at,
    fr.waiting_reason,
    fr.turn_index,
    fr.error ->> 'reason' AS failure_reason,
    fr.error ->> 'code' AS failure_code
FROM flow_run fr;

GRANT SELECT ON grafana_flow_run TO grafana_readonly;
