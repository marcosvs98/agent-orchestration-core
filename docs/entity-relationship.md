```mermaid
classDiagram
direction BT
class access_policy {
   uuid tenant_id
   varchar(128) name
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid access_policy_id
}
class access_policy_version {
   uuid access_policy_id
   varchar(16) status
   integer version_major
   integer version_minor
   integer version_patch
   varchar(128) config_hash
   jsonb rules
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid access_policy_version_id
}
class active_agent_version {
   uuid agent_version_id
   timestamp with time zone activated_at
   varchar(128) activated_by_principal_id
   varchar(512) justification
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid agent_id
}
class active_billing_policy_version {
   uuid billing_policy_version_id
   timestamp with time zone activated_at
   varchar(128) activated_by_principal_id
   varchar(512) justification
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid tenant_id
}
class active_flow_version {
   uuid flow_version_id
   uuid flow_graph_snapshot_id
   timestamp with time zone activated_at
   varchar(128) activated_by_principal_id
   varchar(512) justification
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid flow_id
}
class active_memory_policy_version {
   uuid memory_policy_version_id
   varchar(128) activated_by_principal_id
   varchar(512) justification
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid tenant_id
}
class active_rag_policy_version {
   uuid rag_policy_version_id
   varchar(128) activated_by_principal_id
   varchar(512) justification
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid tenant_id
}
class agent {
   uuid tenant_id
   varchar(255) name
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid agent_id
}
class agent_run {
   uuid ai_task_id
   uuid node_run_id
   uuid agent_version_id
   uuid ai_execution_policy_version_id
   varchar(128) model
   integer input_tokens
   integer output_tokens
   numeric(18,6) estimated_cost
   uuid billing_policy_version_id
   varchar(32) status
   varchar(32) canonical_status
   uuid correlation_id
   timestamp with time zone started_at
   timestamp with time zone finished_at
   jsonb input
   jsonb output
   jsonb error
   varchar(64) system_prompt_hash
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid agent_run_id
}
class agent_version {
   uuid agent_id
   uuid ai_execution_policy_version_id
   uuid rag_config_id
   varchar(16) status
   integer version_major
   integer version_minor
   integer version_patch
   varchar(128) config_hash
   text description
   integer supported_tool_schema_version
   varchar(128) supported_tool_config_hash_prefix
   jsonb persona_config
   uuid system_prompt_template_id
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid agent_version_id
}
class agent_version_tool_binding {
   uuid agent_version_id
   uuid tool_config_id
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid agent_version_tool_binding_id
}
class ai_execution_policy {
   uuid tenant_id
   text description
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid ai_execution_policy_id
}
class ai_execution_policy_version {
   uuid ai_execution_policy_id
   uuid model_id
   varchar(16) status
   integer version_major
   integer version_minor
   integer version_patch
   varchar(128) config_hash
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid ai_execution_policy_version_id
}
class ai_task {
   varchar(255) name
   boolean allow_rag_tenant
   boolean allow_user_memory
   boolean allow_session_context
   boolean allow_memory_write
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid ai_task_id
}
class alembic_version {
   varchar(32) version_num
}
class authoring_event {
   uuid tenant_id
   varchar(64) resource_type
   uuid resource_id
   uuid version_id
   varchar(64) event_type
   varchar(64) change_type
   varchar(128) principal_id
   varchar(512) justification
   timestamp with time zone occurred_at
   integer schema_version
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid authoring_event_id
}
class billing_policy {
   uuid tenant_id
   varchar(128) name
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid billing_policy_id
}
class billing_policy_version {
   uuid billing_policy_id
   varchar(32) status
   integer version_major
   integer version_minor
   integer version_patch
   varchar(128) config_hash
   jsonb rules
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid billing_policy_version_id
}
class condition_expression {
   text expression
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid condition_expression_id
}
class end_user {
   uuid tenant_id
   varchar(255) user_id
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid end_user_id
}
class escalation {
   uuid flow_run_id
   uuid escalation_policy_id
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid escalation_id
}
class escalation_policy {
   uuid condition_expression_id
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid escalation_policy_id
}
class execution_event {
   uuid tenant_id
   varchar(255) user_id
   uuid session_id
   uuid flow_run_id
   uuid correlation_id
   uuid causation_id
   timestamp with time zone occurred_at
   bigint event_sequence
   integer schema_version
   varchar(64) type
   jsonb payload
   uuid node_id
   varchar(128) edge_id
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid execution_event_id
}
class execution_limit_policy {
   uuid tenant_id
   varchar(128) name
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid execution_limit_policy_id
}
class execution_limit_policy_version {
   uuid execution_limit_policy_id
   varchar(16) status
   integer version_major
   integer version_minor
   integer version_patch
   varchar(128) config_hash
   integer max_nodes_per_flow_run
   integer max_node_runs_per_flow_run
   integer max_agent_runs_per_interaction
   integer max_tool_runs_per_flow_run
   integer max_tokens_per_agent_run
   integer max_total_runtime_seconds
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid execution_limit_policy_version_id
}
class flow {
   uuid tenant_id
   varchar(255) name
   text description
   character varying[] tags
   varchar(128) created_by
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid flow_id
}
class flow_graph {
   uuid flow_version_id
   jsonb definition
   timestamp with time zone created_at
   varchar(128) created_by
   timestamp with time zone updated_at
   uuid flow_graph_id
}
class flow_graph_draft {
   uuid flow_version_id
   jsonb definition
   varchar(32) status
   timestamp with time zone created_at
   varchar(128) created_by
   timestamp with time zone validated_at
   varchar(128) validated_by
   timestamp with time zone updated_at
   uuid flow_graph_draft_id
}
class flow_graph_snapshot {
   uuid flow_version_id
   varchar(128) graph_hash
   jsonb snapshot
   timestamp with time zone compiled_at
   varchar(128) compiled_by
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid flow_graph_snapshot_id
}
class flow_run {
   uuid origin_flow_run_id
   uuid flow_version_id
   uuid session_id
   varchar(255) user_id
   uuid interaction_id
   varchar(32) status
   varchar(32) canonical_status
   uuid correlation_id
   timestamp with time zone started_at
   timestamp with time zone finished_at
   varchar(255) waiting_reason
   timestamp with time zone waiting_deadline_at
   jsonb input
   jsonb output
   jsonb error
   uuid flow_graph_snapshot_id
   varchar(128) execution_plan_hash
   varchar(128) runtime_policy_hash
   varchar(128) tool_catalog_hash
   varchar(128) llm_provider_config_hash
   uuid trace_id
   varchar(128) root_observation_id
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid flow_run_id
}
class flow_run_lock {
   timestamp with time zone locked_at
   varchar(128) owner
   uuid correlation_id
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid flow_run_id
}
class flow_version {
   uuid flow_id
   varchar(16) status
   integer version_major
   integer version_minor
   integer version_patch
   varchar(128) config_hash
   integer min_agent_version_major
   integer min_agent_version_minor
   integer min_agent_version_patch
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid flow_version_id
}
class graph_state {
   uuid flow_run_id
   uuid last_node_run_id
   jsonb state
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid graph_state_id
}
class interaction {
   uuid session_id
   uuid flow_run_id
   uuid result_node_run_id
   varchar(64) channel
   jsonb payload
   jsonb output
   jsonb headers
   jsonb interaction_metadata
   varchar(128) external_message_id
   varchar(128) request_id
   varchar(128) trace_id
   timestamp with time zone received_at
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid interaction_id
}
class llm_model_mapping {
   uuid tenant_id
   varchar(32) provider
   varchar(64) model_alias
   varchar(128) provider_model
   varchar(16) status
   timestamp with time zone created_at
   varchar(128) created_by
   timestamp with time zone updated_at
   uuid llm_model_mapping_id
}
class llm_pricing {
   varchar(32) provider
   varchar(128) provider_model
   varchar(16) unit
   numeric(18,6) input_cost_per_1k
   numeric(18,6) output_cost_per_1k
   varchar(8) currency
   varchar(16) status
   timestamp with time zone created_at
   varchar(128) created_by
   timestamp with time zone updated_at
   uuid llm_pricing_id
}
class llm_provider_config {
   uuid tenant_id
   varchar(32) provider
   varchar(16) status
   varchar(255) base_url
   varchar(255) credential_secret_ref
   timestamp with time zone created_at
   varchar(128) created_by
   timestamp with time zone updated_at
   uuid llm_provider_config_id
}
class memory_policy {
   uuid tenant_id
   varchar(128) name
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid memory_policy_id
}
class memory_policy_version {
   uuid memory_policy_id
   varchar(16) status
   integer version_major
   integer version_minor
   integer version_patch
   varchar(128) config_hash
   integer retention_ttl_seconds
   jsonb consent_definition
   jsonb allowed_sources
   jsonb allowed_schemas
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid memory_policy_version_id
}
class model {
   varchar(255) name
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid model_id
}
class node {
   uuid flow_version_id
   uuid ai_task_id
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid node_id
}
class node_agent_binding {
   uuid node_id
   uuid agent_version_id
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid node_agent_binding_id
}
class node_ai_execution_policy_binding {
   uuid node_id
   uuid ai_execution_policy_version_id
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid node_ai_execution_policy_binding_id
}
class node_prompt {
   varchar(64) node_type
   text template_text
   varchar(128) input_schema_id
   varchar(128) output_schema_id
   integer version
   varchar(64) frozen_hash
   boolean is_active
   text description
   varchar(128) created_by
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid prompt_id
}
class node_run {
   uuid flow_run_id
   uuid node_id
   varchar(32) status
   varchar(32) canonical_status
   uuid correlation_id
   timestamp with time zone started_at
   timestamp with time zone finished_at
   jsonb input
   jsonb output
   jsonb error
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid node_run_id
}
class onboarding {
   uuid tenant_id
   varchar(255) name
   varchar(128) created_by
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid onboarding_id
}
class onboarding_run {
   uuid onboarding_version_id
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid onboarding_run_id
}
class onboarding_step {
   uuid onboarding_version_id
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid onboarding_step_id
}
class onboarding_version {
   uuid onboarding_id
   varchar(16) status
   integer version_major
   integer version_minor
   integer version_patch
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid onboarding_version_id
}
class rag_chunk {
   uuid document_id
   integer chunk_index
   text content
   varchar(128) content_hash
   integer token_count
   vector(1536) embedding
   varchar(128) embedding_model
   integer embedding_dimension
   jsonb metadata
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid chunk_id
}
class rag_config {
   uuid tenant_id
   uuid vector_store_id
   varchar(16) status
   integer version_major
   integer version_minor
   integer version_patch
   varchar(128) config_hash
   jsonb options
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid rag_config_id
}
class rag_document {
   uuid tenant_id
   varchar(255) source
   varchar(128) doc_type
   varchar(128) content_hash
   text content
   varchar(64) version
   varchar(32) embedding_status
   integer embedding_attempts
   varchar(128) last_embedding_error_code
   timestamp with time zone embedding_started_at
   timestamp with time zone embedding_completed_at
   jsonb metadata
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid document_id
}
class rag_policy {
   uuid tenant_id
   varchar(128) name
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid rag_policy_id
}
class rag_policy_version {
   uuid rag_policy_id
   varchar(16) status
   integer version_major
   integer version_minor
   integer version_patch
   varchar(128) config_hash
   jsonb policy_definition
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid rag_policy_version_id
}
class rag_query_cache {
   uuid tenant_id
   varchar(128) query_hash
   vector(1536) embedding
   varchar(128) embedding_model
   integer embedding_dimension
   integer use_count
   timestamp with time zone last_used_at
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid query_cache_id
}
class rate_limit_policy {
   uuid tenant_id
   varchar(128) name
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid rate_limit_policy_id
}
class rate_limit_policy_version {
   uuid rate_limit_policy_id
   varchar(16) status
   integer version_major
   integer version_minor
   integer version_patch
   varchar(128) config_hash
   varchar(128) action
   varchar(16) principal_type
   integer limit
   integer window_seconds
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid rate_limit_policy_version_id
}
class response_artifact {
   uuid interaction_id
   uuid flow_run_id
   jsonb payload
   integer schema_version
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid response_artifact_id
}
class router {
   uuid node_id
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid router_id
}
class routing_rule {
   uuid router_id
   uuid condition_expression_id
   uuid from_node_id
   uuid to_node_id
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid routing_rule_id
}
class run_failure {
   uuid flow_run_id
   uuid node_run_id
   uuid agent_run_id
   uuid tool_run_id
   varchar(64) error_type
   jsonb error
   uuid correlation_id
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid run_failure_id
}
class runtime_policy {
   uuid tenant_id
   varchar(16) scope
   uuid flow_id
   varchar(16) version
   varchar(16) status
   jsonb policy_definition
   timestamp with time zone created_at
   varchar(128) created_by
   timestamp with time zone updated_at
   uuid runtime_policy_id
}
class session {
   uuid tenant_id
   varchar(255) user_id
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid session_id
}
class step_run {
   uuid onboarding_step_id
   uuid onboarding_run_id
   varchar(255) name
   varchar(32) status
   jsonb input_payload
   jsonb output_payload
   uuid schema_id
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid step_run_id
}
class system_prompt_template {
   varchar(255) name
   text template_text
   jsonb allowed_placeholders
   integer version
   varchar(32) status
   text description
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid template_id
}
class tenant {
   uuid external_id
   varchar(255) name
   text description
   varchar(64) timezone
   boolean is_active
   varchar(3) currency
   varchar(10) language
   varchar(255) contact_name
   varchar(50) contact_phone
   jsonb settings
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid tenant_id
}
class tool {
   varchar(255) name
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid tool_id
}
class tool_config {
   uuid tool_id
   uuid tenant_id
   varchar(16) status
   integer version_major
   integer version_minor
   integer version_patch
   varchar(128) config_hash
   integer schema_version
   jsonb config
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid tool_config_id
}
class tool_run {
   uuid agent_run_id
   uuid node_run_id
   uuid tool_config_id
   varchar(32) status
   varchar(32) canonical_status
   uuid correlation_id
   timestamp with time zone started_at
   timestamp with time zone finished_at
   jsonb input
   jsonb output
   jsonb error
   varchar(255) idempotency_key
   boolean has_side_effect
   numeric(18,6) estimated_cost
   uuid billing_policy_version_id
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid tool_run_id
}
class user_memory_profile {
   uuid tenant_id
   varchar(255) user_id
   jsonb profile
   integer profile_version
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid user_memory_profile_id
}
class user_preference {
   uuid tenant_id
   varchar(255) user_id
   varchar(128) preference_key
   jsonb preference_value
   varchar(32) source
   integer version
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid user_preference_id
}
class vector_store {
   varchar(255) name
   timestamp with time zone created_at
   timestamp with time zone updated_at
   uuid vector_store_id
}

access_policy  -->  tenant : tenant_id
access_policy_version  -->  access_policy : access_policy_id
active_agent_version  -->  agent : agent_id
active_agent_version  -->  agent_version : agent_version_id
active_billing_policy_version  -->  billing_policy_version : billing_policy_version_id
active_billing_policy_version  -->  tenant : tenant_id
active_flow_version  -->  flow : flow_id
active_flow_version  -->  flow_graph_snapshot : flow_graph_snapshot_id
active_flow_version  -->  flow_version : flow_version_id
active_memory_policy_version  -->  memory_policy_version : memory_policy_version_id
active_memory_policy_version  -->  tenant : tenant_id
active_rag_policy_version  -->  rag_policy_version : rag_policy_version_id
active_rag_policy_version  -->  tenant : tenant_id
agent  -->  tenant : tenant_id
agent_run  -->  agent_version : agent_version_id
agent_run  -->  ai_execution_policy_version : ai_execution_policy_version_id
agent_run  -->  ai_task : ai_task_id
agent_run  -->  billing_policy_version : billing_policy_version_id
agent_run  -->  node_run : node_run_id
agent_version  -->  agent : agent_id
agent_version  -->  ai_execution_policy_version : ai_execution_policy_version_id
agent_version  -->  rag_config : rag_config_id
agent_version  -->  system_prompt_template : system_prompt_template_id:template_id
agent_version_tool_binding  -->  agent_version : agent_version_id
agent_version_tool_binding  -->  tool_config : tool_config_id
ai_execution_policy  -->  tenant : tenant_id
ai_execution_policy_version  -->  ai_execution_policy : ai_execution_policy_id
ai_execution_policy_version  -->  model : model_id
authoring_event  -->  tenant : tenant_id
billing_policy  -->  tenant : tenant_id
billing_policy_version  -->  billing_policy : billing_policy_id
end_user  -->  tenant : tenant_id
escalation  -->  escalation_policy : escalation_policy_id
escalation  -->  flow_run : flow_run_id
escalation_policy  -->  condition_expression : condition_expression_id
execution_event  -->  flow_run : flow_run_id
execution_event  -->  session : session_id
execution_event  -->  tenant : tenant_id
execution_limit_policy  -->  tenant : tenant_id
execution_limit_policy_version  -->  execution_limit_policy : execution_limit_policy_id
flow  -->  tenant : tenant_id
flow_graph  -->  flow_version : flow_version_id
flow_graph_draft  -->  flow_version : flow_version_id
flow_graph_snapshot  -->  flow_version : flow_version_id
flow_run  -->  flow_graph_snapshot : flow_graph_snapshot_id
flow_run  -->  flow_run : origin_flow_run_id:flow_run_id
flow_run  -->  flow_version : flow_version_id
flow_run  -->  interaction : interaction_id
flow_run  -->  session : session_id
flow_run_lock  -->  flow_run : flow_run_id
flow_version  -->  flow : flow_id
graph_state  -->  flow_run : flow_run_id
graph_state  -->  node_run : last_node_run_id:node_run_id
interaction  -->  flow_run : flow_run_id
interaction  -->  node_run : result_node_run_id:node_run_id
interaction  -->  session : session_id
llm_model_mapping  -->  tenant : tenant_id
llm_provider_config  -->  tenant : tenant_id
memory_policy  -->  tenant : tenant_id
memory_policy_version  -->  memory_policy : memory_policy_id
node  -->  ai_task : ai_task_id
node  -->  flow_version : flow_version_id
node_agent_binding  -->  agent_version : agent_version_id
node_agent_binding  -->  node : node_id
node_ai_execution_policy_binding  -->  ai_execution_policy_version : ai_execution_policy_version_id
node_ai_execution_policy_binding  -->  node : node_id
node_run  -->  flow_run : flow_run_id
node_run  -->  node : node_id
onboarding  -->  tenant : tenant_id
onboarding_run  -->  onboarding_version : onboarding_version_id
onboarding_step  -->  onboarding_version : onboarding_version_id
onboarding_version  -->  onboarding : onboarding_id
rag_chunk  -->  rag_document : document_id
rag_config  -->  tenant : tenant_id
rag_config  -->  vector_store : vector_store_id
rag_document  -->  tenant : tenant_id
rag_policy  -->  tenant : tenant_id
rag_policy_version  -->  rag_policy : rag_policy_id
rag_query_cache  -->  tenant : tenant_id
rate_limit_policy  -->  tenant : tenant_id
rate_limit_policy_version  -->  rate_limit_policy : rate_limit_policy_id
response_artifact  -->  flow_run : flow_run_id
response_artifact  -->  interaction : interaction_id
router  -->  node : node_id
routing_rule  -->  condition_expression : condition_expression_id
routing_rule  -->  node : from_node_id:node_id
routing_rule  -->  node : to_node_id:node_id
routing_rule  -->  router : router_id
run_failure  -->  agent_run : agent_run_id
run_failure  -->  flow_run : flow_run_id
run_failure  -->  node_run : node_run_id
run_failure  -->  tool_run : tool_run_id
runtime_policy  -->  flow : flow_id
runtime_policy  -->  tenant : tenant_id
session  -->  end_user : tenant_id, user_id
session  -->  tenant : tenant_id
step_run  -->  onboarding_run : onboarding_run_id
step_run  -->  onboarding_step : onboarding_step_id
tool_config  -->  tenant : tenant_id
tool_config  -->  tool : tool_id
tool_run  -->  agent_run : agent_run_id
tool_run  -->  billing_policy_version : billing_policy_version_id
tool_run  -->  node_run : node_run_id
tool_run  -->  tool_config : tool_config_id
user_memory_profile  -->  end_user : tenant_id, user_id
user_preference  -->  end_user : tenant_id, user_id
```