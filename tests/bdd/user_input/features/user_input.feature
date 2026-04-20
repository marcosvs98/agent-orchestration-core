Feature: User input normalization for flow runs
  Multimodal parts are composed into a single canonical user_input string.

  @m1 @smoke
  Scenario: Text-only legacy path
    Given a tenant id
    When we normalize with user_input "hello world" and no input parts
    Then the composed user_input is "hello world"

  @m1
  Scenario: Empty input parts and empty user_input
    Given a tenant id
    When we normalize with user_input "" and no input parts
    Then the composed user_input is empty
