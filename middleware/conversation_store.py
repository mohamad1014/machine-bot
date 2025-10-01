from __future__ import annotations

"""Cosmos-backed persistence for conversation transcripts."""

import os
from typing import Iterable

from azure.cosmos import CosmosClient, exceptions
from langchain_core.messages import BaseMessage, messages_from_dict, messages_to_dict


class ConversationStore:
    """Persist and retrieve serialized LangChain message transcripts."""

    def __init__(
        self,
        *,
        connection_string: str | None = None,
        database_name: str | None = None,
        container_name: str | None = None,
        container=None,
    ) -> None:
        self._connection_string = connection_string or os.getenv("CosmosDbConnection")
        self._database_name = database_name or os.getenv("CosmosDatabase")
        self._container_name = container_name or os.getenv("CosmosContainer")
        self._container = container
        self._client: CosmosClient | None = None

    def _get_container(self):
        if self._container is not None:
            return self._container
        if not self._connection_string:
            raise RuntimeError("CosmosDbConnection must be configured for ConversationStore")
        if not self._database_name:
            raise RuntimeError("CosmosDatabase must be configured for ConversationStore")
        if not self._container_name:
            raise RuntimeError("CosmosContainer must be configured for ConversationStore")
        if self._client is None:
            self._client = CosmosClient.from_connection_string(self._connection_string)
        database = self._client.get_database_client(self._database_name)
        self._container = database.get_container_client(self._container_name)
        return self._container

    def load_messages(self, conversation_id: str) -> list[BaseMessage]:
        """Return the stored transcript for ``conversation_id`` if present."""

        if not conversation_id:
            return []
        container = self._get_container()
        try:
            record = container.read_item(item=conversation_id, partition_key=conversation_id)
        except exceptions.CosmosResourceNotFoundError:
            return []
        messages_data = record.get("messages", [])
        if not messages_data:
            return []
        return list(messages_from_dict(messages_data))

    def save_messages(self, conversation_id: str, messages: Iterable[BaseMessage]) -> None:
        """Persist ``messages`` under ``conversation_id``."""

        container = self._get_container()
        serialized = messages_to_dict(list(messages))
        container.upsert_item({"id": conversation_id, "messages": serialized})

    def delete(self, conversation_id: str) -> None:
        """Remove the stored transcript, ignoring missing records."""

        if not conversation_id:
            return
        container = self._get_container()
        try:
            container.delete_item(item=conversation_id, partition_key=conversation_id)
        except exceptions.CosmosResourceNotFoundError:
            return
