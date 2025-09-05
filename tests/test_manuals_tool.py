"""Tests for :mod:`middleware.manuals_tool`."""

from __future__ import annotations

from unittest.mock import Mock, patch

from middleware.manuals_tool import ManualMarkdownTool


def _mock_blob_service_with_text(text: str) -> Mock:
    """Create a mocked BlobServiceClient returning *text* for any blob."""

    blob_client = Mock()
    download = Mock()
    download.content_as_text.return_value = text
    blob_client.download_blob.return_value = download

    container_client = Mock()
    container_client.get_blob_client.return_value = blob_client

    service_client = Mock()
    service_client.get_container_client.return_value = container_client

    return service_client


def test_appends_manual_text_when_present():
    service_client = _mock_blob_service_with_text("manual content")

    with patch("middleware.manuals_tool.BlobServiceClient") as blob_cls:
        blob_cls.from_connection_string.return_value = service_client
        tool = ManualMarkdownTool(connection_string="dummy")
        result = tool.run(machine_name="machine001", user_message="hello")

    assert "manual content" in result
    assert result.startswith("hello")
    service_client.get_container_client.assert_called_with("manuals-md")


def test_returns_original_message_when_manual_missing():
    blob_client = Mock()
    blob_client.download_blob.side_effect = Exception("not found")

    container_client = Mock()
    container_client.get_blob_client.return_value = blob_client

    service_client = Mock()
    service_client.get_container_client.return_value = container_client

    with patch("middleware.manuals_tool.BlobServiceClient") as blob_cls:
        blob_cls.from_connection_string.return_value = service_client
        tool = ManualMarkdownTool(connection_string="dummy")
        result = tool.run(machine_name="machine001", user_message="hello")

    assert result == "hello"

