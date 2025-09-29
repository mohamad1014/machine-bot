"""Facilities for persisting user-centric data in Azure Cosmos DB."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from typing import Any, Callable, Sequence

from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError


DEFAULT_MAX_SUMMARIES = 50


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class UserConversationSummary:
    """Light-weight summary of a conversation stored on the user document."""

    conversation_id: str
    topic: str
    started_at: str
    last_interaction_at: str
    message_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "topic": self.topic,
            "started_at": self.started_at,
            "last_interaction_at": self.last_interaction_at,
            "message_count": self.message_count,
        }


@dataclass(slots=True)
class UserProfile:
    """Structured representation of the key data we track about a user."""

    user_id: str
    display_name: str | None = None
    email: str | None = None
    timezone: str | None = None
    locale: str | None = None
    role: str | None = None
    company: str | None = None
    phone_number: str | None = None
    preferences: dict[str, Any] = field(default_factory=dict)
    tags: Sequence[str] | None = None
    notes: str | None = None

    def profile_dict(self) -> dict[str, Any]:
        profile = {
            "display_name": self.display_name,
            "email": self.email,
            "timezone": self.timezone,
            "locale": self.locale,
            "role": self.role,
            "company": self.company,
            "phone_number": self.phone_number,
        }
        return {key: value for key, value in profile.items() if value is not None}


class UserDataStore:
    """Persist user metadata and conversation history in Cosmos DB."""

    def __init__(
        self,
        *,
        connection_string: str | None = None,
        database_name: str | None = None,
        user_container_name: str = "users",
        conversation_container_name: str = "conversations",
        max_summaries: int = DEFAULT_MAX_SUMMARIES,
        clock: Callable[[], datetime] | None = None,
        user_container=None,
        conversation_container=None,
        cosmos_client: CosmosClient | None = None,
    ) -> None:
        self._clock = clock or _default_clock
        self._max_summaries = max_summaries

        self._connection_string = connection_string or os.getenv("CosmosDbConnection")
        self._database_name = database_name or os.getenv("CosmosDatabase", "db")
        self._user_container_name = user_container_name
        self._conversation_container_name = conversation_container_name

        if user_container is not None and conversation_container is not None:
            self._user_container = user_container
            self._conversation_container = conversation_container
            self._client = cosmos_client
            return

        if not self._connection_string:
            raise ValueError(
                "A Cosmos DB connection string is required when container clients are not provided."
            )

        self._client = cosmos_client or CosmosClient.from_connection_string(self._connection_string)
        database = self._client.get_database_client(self._database_name)
        self._user_container = user_container or database.get_container_client(self._user_container_name)
        self._conversation_container = (
            conversation_container or database.get_container_client(self._conversation_container_name)
        )

    # public API -----------------------------------------------------------------
    def record_conversation(
        self,
        *,
        user_profile: UserProfile,
        conversation_id: str,
        topic: str,
        conversation_payload: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Persist the conversation transcript and update the user profile.

        Returns a tuple of ``(user_document, conversation_document)`` as they were
        submitted to Cosmos DB.
        """

        now = self._clock().isoformat()
        conversation_doc = self._build_conversation_document(
            user_profile.user_id, conversation_id, topic, conversation_payload, now
        )
        self._conversation_container.upsert_item(conversation_doc)

        user_doc = self._load_user_document(user_profile.user_id, now)
        updated_user_doc = self._update_user_document(
            user_doc, user_profile, conversation_doc, now
        )
        self._user_container.upsert_item(updated_user_doc)
        return updated_user_doc, conversation_doc

    # helpers --------------------------------------------------------------------
    def _build_conversation_document(
        self,
        user_id: str,
        conversation_id: str,
        topic: str,
        conversation_payload: dict[str, Any],
        now: str,
    ) -> dict[str, Any]:
        payload_copy = deepcopy(conversation_payload)
        messages = list(payload_copy.get("messages", []))
        created_at = payload_copy.get("created_at", now)
        payload_copy.update(
            {
                "id": conversation_id,
                "pk": conversation_id,
                "user_id": user_id,
                "topic": topic,
                "created_at": created_at,
                "updated_at": now,
                "message_count": len(messages),
            }
        )
        payload_copy["messages"] = messages
        payload_copy.setdefault("attachments", payload_copy.get("attachments", []))
        payload_copy.setdefault("metadata", payload_copy.get("metadata", {}))
        payload_copy.setdefault("channel", payload_copy.get("channel", "unknown"))
        payload_copy.setdefault("summary", payload_copy.get("summary"))
        return payload_copy

    def _load_user_document(self, user_id: str, now: str) -> dict[str, Any]:
        try:
            document = self._user_container.read_item(item=user_id, partition_key=user_id)
        except CosmosResourceNotFoundError:
            return self._create_base_user_document(user_id, now)
        return deepcopy(document)

    def _create_base_user_document(self, user_id: str, now: str) -> dict[str, Any]:
        return {
            "id": user_id,
            "pk": user_id,
            "created_at": now,
            "last_seen_at": now,
            "conversation_summaries": [],
            "stats": {
                "total_conversations": 0,
                "recent_topics": [],
            },
        }

    def _update_user_document(
        self,
        document: dict[str, Any],
        user_profile: UserProfile,
        conversation_doc: dict[str, Any],
        now: str,
    ) -> dict[str, Any]:
        document["last_seen_at"] = now

        profile_section = document.setdefault("profile", {})
        profile_section.setdefault("user_id", user_profile.user_id)
        profile_section.update(user_profile.profile_dict())

        preferences = document.setdefault("preferences", {})
        preferences.update(user_profile.preferences)

        if user_profile.tags is not None:
            existing_tags = set(document.get("tags", []))
            existing_tags.update(tag for tag in user_profile.tags if tag)
            document["tags"] = sorted(existing_tags)

        if user_profile.notes is not None:
            document["notes"] = user_profile.notes

        document.setdefault("alerts", {})
        document.setdefault("integrations", {})

        stats = document.setdefault("stats", {})
        stats.setdefault("total_conversations", 0)
        stats.setdefault("recent_topics", [])

        existing_summaries = document.get("conversation_summaries", [])
        had_existing_summary = any(
            summary.get("conversation_id") == conversation_doc["id"]
            for summary in existing_summaries
        )
        summaries = [
            summary
            for summary in existing_summaries
            if summary.get("conversation_id") != conversation_doc["id"]
        ]

        summary = UserConversationSummary(
            conversation_id=conversation_doc["id"],
            topic=conversation_doc.get("topic", ""),
            started_at=conversation_doc.get("created_at", now),
            last_interaction_at=now,
            message_count=conversation_doc.get("message_count", 0),
        )
        summaries.insert(0, summary.as_dict())
        document["conversation_summaries"] = summaries[: self._max_summaries]

        if not had_existing_summary:
            stats["total_conversations"] = int(stats.get("total_conversations", 0)) + 1
        else:
            stats["total_conversations"] = int(stats.get("total_conversations", 0))

        recent_topics = [entry.get("topic") for entry in document["conversation_summaries"] if entry.get("topic")]
        stats["recent_topics"] = recent_topics[:5]
        stats["last_conversation_id"] = conversation_doc["id"]
        stats["last_topic"] = conversation_doc.get("topic")
        stats["last_channel"] = conversation_doc.get("channel")
        stats["last_message_count"] = conversation_doc.get("message_count", 0)
        stats["last_interaction_at"] = now

        engagement = stats.get("engagement_score", 0)
        stats["engagement_score"] = min(100, engagement + 1)

        return document


__all__ = [
    "UserDataStore",
    "UserProfile",
    "UserConversationSummary",
]

