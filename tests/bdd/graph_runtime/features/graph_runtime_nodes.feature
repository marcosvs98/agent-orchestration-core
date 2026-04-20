# language: en
Feature: Graph runtime node behaviour (pure domain)
  Nodes implement deterministic execution contracts without HTTP or persistence.

  Scenario: Tool error handler schedules retries for retryable failures
    Given a tool error handler node
    And a failed tool operation below max retries
    When the node executes
    Then the result asks for a retry of that operation

  Scenario: IntentClassifier advertises selection task metadata
    Given the IntentClassifier node class
    Then its node type is IntentClassifier
