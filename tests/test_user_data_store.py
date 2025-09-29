from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from middleware.user_data_store import UserDataStore, UserProfile


def _not_found_error():
    response = MagicMock()
    response.status_code = 404
    response.headers = {}
    return CosmosResourceNotFoundError(response=response, message="Not Found")


def test_record_conversation_creates_new_user_document():
    user_container = MagicMock()
    user_container.read_item.side_effect = _not_found_error()
    conversation_container = MagicMock()

    fixed_now = datetime(2024, 1, 1, tzinfo=timezone.utc)

    store = UserDataStore(
        connection_string="AccountEndpoint=https://example/;AccountKey=abc==;",
        database_name="db",
        user_container=user_container,
        conversation_container=conversation_container,
        clock=lambda: fixed_now,
    )

    profile = UserProfile(
        user_id="user-123",
        display_name="Ada Lovelace",
        email="ada@example.com",
        timezone="UTC",
        locale="en-GB",
        role="Engineer",
        company="Analytical Engines Inc",
        preferences={"language": "en", "notify": True},
        tags=["beta", "vip"],
        notes="Interested in proactive maintenance reports.",
    )

    conversation_payload = {
        "messages": [
            {"role": "user", "content": "How is machine 42 doing?"},
            {"role": "assistant", "content": "Machine 42 is running smoothly."},
        ],
        "attachments": ["https://contoso.blob.core.windows.net/logs/machine42.csv"],
        "metadata": {"source": "telegram"},
        "channel": "telegram",
    }

    user_doc, conversation_doc = store.record_conversation(
        user_profile=profile,
        conversation_id="conv-001",
        topic="Machine status",
        conversation_payload=conversation_payload,
    )

    conversation_container.upsert_item.assert_called_once()
    saved_conversation = conversation_container.upsert_item.call_args.args[0]
    assert saved_conversation["id"] == "conv-001"
    assert saved_conversation["pk"] == "conv-001"
    assert saved_conversation["user_id"] == "user-123"
    assert saved_conversation["message_count"] == 2
    assert saved_conversation["messages"] == conversation_payload["messages"]
    assert saved_conversation["channel"] == "telegram"

    user_container.upsert_item.assert_called_once()
    saved_user = user_container.upsert_item.call_args.args[0]
    assert saved_user["id"] == "user-123"
    assert saved_user["pk"] == "user-123"
    assert saved_user["profile"]["display_name"] == "Ada Lovelace"
    assert saved_user["profile"]["email"] == "ada@example.com"
    assert saved_user["preferences"]["language"] == "en"
    assert saved_user["notes"].startswith("Interested")

    summaries = saved_user["conversation_summaries"]
    assert len(summaries) == 1
    assert summaries[0]["conversation_id"] == "conv-001"
    assert summaries[0]["topic"] == "Machine status"

    stats = saved_user["stats"]
    assert stats["total_conversations"] == 1
    assert stats["recent_topics"] == ["Machine status"]
    assert stats["engagement_score"] == 1

    assert set(saved_user["tags"]) == {"beta", "vip"}
    assert user_doc == saved_user
    assert conversation_doc == saved_conversation


def test_record_conversation_updates_existing_user_without_duplicate_counts():
    user_container = MagicMock()
    existing_user_document = {
        "id": "user-123",
        "pk": "user-123",
        "profile": {
            "display_name": "Ada Lovelace",
            "email": "ada@example.com",
        },
        "preferences": {"language": "en"},
        "tags": ["vip"],
        "conversation_summaries": [
            {
                "conversation_id": "conv-previous",
                "topic": "Diagnostics",
                "started_at": "2023-12-31T23:59:00+00:00",
                "last_interaction_at": "2023-12-31T23:59:00+00:00",
                "message_count": 3,
            }
        ],
        "stats": {
            "total_conversations": 2,
            "recent_topics": ["Diagnostics", "Calibration"],
            "engagement_score": 99,
        },
    }
    user_container.read_item.return_value = existing_user_document

    conversation_container = MagicMock()
    fixed_now = datetime(2024, 1, 2, 0, 5, tzinfo=timezone.utc)

    store = UserDataStore(
        connection_string="AccountEndpoint=https://example/;AccountKey=abc==;",
        database_name="db",
        user_container=user_container,
        conversation_container=conversation_container,
        clock=lambda: fixed_now,
    )

    profile = UserProfile(
        user_id="user-123",
        display_name="Ada Byron",
        timezone="UTC",
        locale="en-GB",
        preferences={"notify": False},
        tags=["vip", "urgent"],
        notes="Prefers succinct answers.",
    )

    conversation_payload = {
        "messages": [
            {"role": "user", "content": "Remind me about yesterday's diagnostics."},
            {"role": "assistant", "content": "Diagnostics completed successfully."},
        ],
        "metadata": {"source": "web"},
        "summary": "Follow-up on diagnostics",
    }

    user_doc, conversation_doc = store.record_conversation(
        user_profile=profile,
        conversation_id="conv-previous",
        topic="Diagnostics",
        conversation_payload=conversation_payload,
    )

    saved_user = user_container.upsert_item.call_args.args[0]
    stats = saved_user["stats"]
    assert stats["total_conversations"] == 2
    assert stats["engagement_score"] == 100
    assert stats["recent_topics"][0] == "Diagnostics"
    assert stats["last_channel"] == "unknown"

    summaries = saved_user["conversation_summaries"]
    assert summaries[0]["conversation_id"] == "conv-previous"
    assert summaries[0]["message_count"] == 2
    assert len(summaries) == 1

    assert saved_user["profile"]["display_name"] == "Ada Byron"
    assert saved_user["preferences"]["notify"] is False
    assert saved_user["notes"] == "Prefers succinct answers."
    assert saved_user["tags"] == ["urgent", "vip"]

    saved_conversation = conversation_container.upsert_item.call_args.args[0]
    assert saved_conversation["summary"] == "Follow-up on diagnostics"
    assert saved_conversation["message_count"] == 2
    assert saved_conversation["messages"][0]["role"] == "user"

    assert user_doc == saved_user
    assert conversation_doc == saved_conversation


def test_init_without_connection_string_raises_value_error(monkeypatch):
    monkeypatch.delenv("CosmosDbConnection", raising=False)
    with pytest.raises(ValueError):
        UserDataStore(database_name="db")

