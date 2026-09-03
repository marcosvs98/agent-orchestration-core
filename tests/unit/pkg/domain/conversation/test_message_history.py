import pytest

from domain.conversation.utils.message_history import parse_message_history


def test_parse_message_history_returns_user_and_assistant_messages() -> None:
    history = parse_message_history(
        {
            "message_history": [
                {"role": "user", "content": "Cartão e fatura"},
                {"role": "assistant", "content": "Qual cartão?"},
                {"role": "system", "content": "ignored"},
                {"role": "user", "content": "  "},
            ]
        }
    )

    assert history == [
        {"role": "user", "content": "Cartão e fatura"},
        {"role": "assistant", "content": "Qual cartão?"},
    ]


def test_parse_message_history_returns_empty_for_missing_metadata() -> None:
    assert parse_message_history(None) == []
    assert parse_message_history({}) == []


def test_parse_message_history_ignores_non_list_history() -> None:
    assert parse_message_history({"message_history": "not-a-list"}) == []


def test_parse_message_history_skips_non_dict_items() -> None:
    history = parse_message_history(
        {
            "message_history": [
                "not-a-dict",
                {"role": "user", "content": "ok"},
            ]
        }
    )
    assert history == [{"role": "user", "content": "ok"}]


def test_parse_message_history_rejects_forbidden_metadata() -> None:
    with pytest.raises(ValueError, match="forbidden_metadata_key:end_user_authorization"):
        parse_message_history({"end_user_authorization": "Bearer forged"})


def test_parse_message_history_limits_items_and_content() -> None:
    history = parse_message_history(
        {
            "message_history": [
                {"role": "user", "content": "x" * 17000},
                *[{"role": "assistant", "content": f"msg-{index}"} for index in range(70)],
            ]
        }
    )
    assert len(history) == 50
    assert len(history[0]["content"]) == 16000
