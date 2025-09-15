"""Integration test for :mod:`middleware.manuals_tools` using real Azure Blob."""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

import pytest

from middleware.manuals_tools import ManualsTool, FetchManualsTool

def test_print_env_vars():
    """Debug visibility of env vars used by tests."""
    _hydrate_env_from_files()
    print("MANUALS_MD_CONNECTION_STRING:", os.environ.get("MANUALS_MD_CONNECTION_STRING"))
    print("AzureWebJobsStorage:", os.environ.get("AzureWebJobsStorage"))

def _load_connection_string() -> str | None:
    """Resolve a connection string for manuals.

    Priority order:
    - MANUALS_MD_CONNECTION_STRING env var
    - AzureWebJobsStorage env var
    - local.settings.json Values.MANUALS_MD_CONNECTION_STRING
    - local.settings.json Values.AzureWebJobsStorage
    When found, also set MANUALS_MD_CONNECTION_STRING in the environment
    for the tool to consume by default.
    """

    # First, hydrate env from common files so tests can run without manual export
    _hydrate_env_from_files()

    cs = os.environ.get("MANUALS_MD_CONNECTION_STRING") or os.environ.get(
        "AzureWebJobsStorage"
    )
    if cs:
        os.environ.setdefault("MANUALS_MD_CONNECTION_STRING", cs)
        return cs

    # Look into standard settings files
    for settings_path in (
        Path("local.settings.json"),
        Path("tests/local.settings.json"),
    ):
        if settings_path.exists():
            try:
                data = json.loads(settings_path.read_text(encoding="utf-8"))
                values = data.get("Values") or {}
                cs = values.get("MANUALS_MD_CONNECTION_STRING") or values.get(
                    "AzureWebJobsStorage"
                )
                if cs:
                    os.environ.setdefault("MANUALS_MD_CONNECTION_STRING", cs)
                    return cs
            except Exception:
                continue
    return None


def _hydrate_env_from_files() -> None:
    """Populate os.environ from .env and local.settings.json files.

    Precedence: existing env values are preserved; files only set missing keys.
    """
    _load_dotenv(Path(".env"))
    _load_dotenv(Path("tests/.env"))
    _load_local_settings(Path("local.settings.json"))
    _load_local_settings(Path("tests/local.settings.json"))


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)
    except Exception:
        # best-effort only
        pass


def _load_local_settings(path: Path) -> None:
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        values = data.get("Values") or {}
        for k, v in values.items():
            if isinstance(v, str):
                os.environ.setdefault(k, v)
    except Exception:
        # best-effort only
        pass
CONNECTION_STRING = _load_connection_string()
if CONNECTION_STRING is None:
    pytest.skip(
        "Azure storage connection string not configured", allow_module_level=True
    )
try:
    from azure.storage.blob import BlobServiceClient
    BlobServiceClient.from_connection_string(CONNECTION_STRING).get_service_properties()
except Exception:
    pytest.skip(
        "Azure storage not reachable", allow_module_level=True
    )


class TestManualsToolIntegration(unittest.TestCase):
    def test_azure_storage_available(self) -> None:
        """Assert Azure SDK import and connection produce a container client."""
        container_name = os.environ.get("MANUALS_MD_CONTAINER", "manuals-md")
        tool = ManualsTool(
            connection_string=CONNECTION_STRING,
            container_name=container_name,
            fallback_path="/__does_not_exist__",
        )
        self.assertIsNotNone(
            getattr(tool, "_container_client", None),
            "Azure SDK import or container client creation failed",
        )
    def test_connection_string_presence(self) -> None:
        """Test that a connection string is present."""
        assert CONNECTION_STRING

    def test_local_data_file_presence(self) -> None:
        """Test that the local data file exists."""
        data_path = Path(__file__).parent / "data" / "machine001.md"
        if not data_path.exists():
            self.fail(f"Missing local data file: {data_path}")

    def test_blob_existence(self) -> None:
        """Test that the blob exists in Azure Blob Storage."""
        container_name = os.environ.get("MANUALS_MD_CONTAINER", "manuals-md")
        blob_name = "machine001.md"
        tool = ManualsTool(
            connection_string=CONNECTION_STRING,
            container_name=container_name,
            fallback_path="/__does_not_exist__",
        )
        client = getattr(tool, "_container_client", None)
        if client is None:
            self.fail("Azure SDK import or container client creation failed")
        blob_client = client.get_blob_client(blob_name)
        try:
            exists = blob_client.exists()  # type: ignore[attr-defined]
        except Exception as exc:
            self.fail(f"Unable to access {container_name}/{blob_name}: {exc}")
        if not exists:
            self.fail(f"Blob not found: {container_name}/{blob_name}")

    def test_fetch_machine001_via_azure_blob(self) -> None:
        """Fetches manuals-md/machine001.md via real Azure Blob and compares output."""
        container_name = os.environ.get("MANUALS_MD_CONTAINER", "manuals-md")
        blob_name = "machine001.md"

        # Preflight: ensure the blob is reachable via the tool's client; otherwise fail.
        tool = ManualsTool(
            connection_string=CONNECTION_STRING,
            container_name=container_name,
            fallback_path="/__does_not_exist__",
        )
        client = getattr(tool, "_container_client", None)
        if client is None:
            self.fail("Azure SDK import or container client creation failed")
        blob_client = client.get_blob_client(blob_name)
        try:
            if not blob_client.exists():  # type: ignore[attr-defined]
                self.fail(f"Blob not found: {container_name}/{blob_name}")
        except Exception as exc:  # pragma: no cover - integration env dependent
            self.fail(f"Unable to access {container_name}/{blob_name}: {exc}")

        # Load expected content from local test data
        data_path = Path(__file__).parent / "data" / "machine001.md"
        if not data_path.exists():
            self.fail(f"Missing local data file: {data_path}")
        expected_text = data_path.read_text(encoding="utf-8")

        # Use the tool against the same resource (fallback disabled)
        tool = ManualsTool(
            connection_string=CONNECTION_STRING,
            container_name=container_name,
            fallback_path="/__does_not_exist__",
        )
        result = tool.run(machine_name="machine001")

        # Compare fetched blob text to local file text
        self.assertEqual(result, expected_text)

    def test_fetch_manuals_tool_lists_expected_files(self) -> None:
        """Test that FetchManualsTool returns the expected manual files."""
        
        container_name = os.environ.get("MANUALS_MD_CONTAINER", "manuals-md")
        
        # Load expected manual names from the test data file
        expected_manuals_path = Path(__file__).parent / "data" / "machine_manual_list.txt"
        if not expected_manuals_path.exists():
            self.fail(f"Missing expected manuals file: {expected_manuals_path}")
        
        expected_text = expected_manuals_path.read_text(encoding="utf-8").strip()
        try:
            expected_manuals = json.loads(expected_text)
        except json.JSONDecodeError as exc:
            self.fail(f"Invalid JSON in {expected_manuals_path}: {exc}")
        
        if not isinstance(expected_manuals, list):
            self.fail(f"Expected list in {expected_manuals_path}, got {type(expected_manuals)}")
        
        # Use FetchManualsTool to get the list of available manuals
        tool = FetchManualsTool(
            connection_string=CONNECTION_STRING,
            container_name=container_name,
            fallback_path="/__does_not_exist__",
        )
        
        result = tool._run()
        available_manuals = result.strip().split('\n') if result.strip() else []
        
        # Check that all expected manuals are present in the container
        for expected_manual in expected_manuals:
            self.assertIn(
                expected_manual, 
                available_manuals,
                f"Expected manual '{expected_manual}' not found in container. Available: {available_manuals}"
            )
        
        # Verify we got a non-empty list
        self.assertGreater(
            len(available_manuals), 
            0, 
            "FetchManualsTool returned no manuals"
        )
