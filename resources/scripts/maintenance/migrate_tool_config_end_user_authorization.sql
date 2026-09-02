-- Rename the end-user credential metadata key on existing HTTP tool_config rows.
--
-- The engine no longer carries a client-specific key name. Producers write
-- `end_user_authorization` (src/domain/common/interaction_metadata.py); consumers still accept the
-- legacy `uora_end_user_authorization` spelling so this migration can run after deploy rather than
-- during it. Run it once, then the legacy alias can be dropped from the accepted set.
--
-- Usage (docker):
--   docker exec -i router-postgres-dev psql -U postgres -d agent_router -v ON_ERROR_STOP=1 \
--     -f - < migrate_tool_config_end_user_authorization.sql

BEGIN;

UPDATE tool_config
SET
  config = jsonb_set(
    config,
    '{headers,Authorization,interaction_metadata_key}',
    '"end_user_authorization"'::jsonb,
    true
  ),
  updated_at = now()
WHERE config->'headers'->'Authorization'->>'interaction_metadata_key'
      = 'uora_end_user_authorization';

COMMIT;

-- Verify: this should return no rows.
-- SELECT tool_config_id
-- FROM tool_config
-- WHERE config->'headers'->'Authorization'->>'interaction_metadata_key'
--       = 'uora_end_user_authorization';
