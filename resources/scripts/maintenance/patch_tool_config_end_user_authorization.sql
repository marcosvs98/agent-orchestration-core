-- Merge Authorization header mapping for HTTP tools (app-platform end-user JWT via interaction_metadata).
-- Demo bootstrap: `resources/scripts/seeds/demo/seed_05_tool.py` already applies this to every
-- PUBLISHED tool_config for the demo tenant on each run (reconciliation pass). Use this SQL only
-- for non-demo tenants or one-off repairs.
-- Safe for PostgreSQL 16: set path '{headers,Authorization}' in one jsonb_set from {} is unreliable;
-- merge under config.headers instead.
--
-- Usage (docker):
--   docker exec -i router-postgres-dev psql -U postgres -d agent_router -v ON_ERROR_STOP=1 -f - < patch_tool_config_end_user_authorization.sql
-- Or from host with psql + connection string.

BEGIN;

UPDATE tool_config
SET
  config = jsonb_set(
    config,
    '{headers}',
    COALESCE(config->'headers', '{}'::jsonb)
      || '{"Authorization": {"interaction_metadata_key": "uora_end_user_authorization"}}'::jsonb,
    true
  ),
  updated_at = now()
WHERE status = 'PUBLISHED';

-- Optional: restrict to one row
-- AND tool_config_id = '00000000-0000-0000-0000-000000000501'::uuid;

COMMIT;

-- Verify
-- SELECT tool_config_id, config->'headers'->'Authorization' FROM tool_config WHERE status = 'PUBLISHED' LIMIT 5;
