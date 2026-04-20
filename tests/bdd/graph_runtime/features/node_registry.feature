# language: en
Feature: Node registry resolution
  The registry returns concrete node classes with dependencies injected from the runtime container.

  Background:
    Given a runtime tracer stub

  Scenario: ToolResolver requires LLM and catalog dependencies
    Given a node registry without LLM executor
    When resolving "ToolResolver"
    Then resolution raises because required dependencies are missing

  Scenario: ContentModeration requires moderation provider
    Given a node registry without moderation provider
    When resolving "ContentModeration"
    Then resolution raises because required dependencies are missing

  Scenario: ResponseBuilder resolves when LLM stack is present
    Given a node registry with LLM stack mocks
    When resolving "ResponseBuilder"
    Then the resolved class can be instantiated
