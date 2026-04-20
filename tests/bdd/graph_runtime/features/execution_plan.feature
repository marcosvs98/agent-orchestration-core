# language: en
Feature: Execution plan model
  ExecutionPlan is an immutable value object describing compiled graph structure.

  Scenario: Plan round-trips through JSON mode
    Given a minimal execution plan fixture
    When the plan is serialized with model_dump mode json
    Then the start node id is preserved in the payload
