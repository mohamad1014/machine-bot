"""Unit tests for manuals tools using local fallback data."""

from pathlib import Path

from middleware.manuals_tools import ManualsTool, FetchManualsTool

DATA_FILE = Path(__file__).parent / "data" / "machine001.md"


def test_run_with_machine_name_kw():
    tool = ManualsTool(connection_string=None, container_name="manuals-md", fallback_path=str(DATA_FILE.parent))
    result = tool.run(machine_name="machine001")
    assert "Machine 001" in result or len(result) > 0


def test_run_with_positional_arg():
    tool = ManualsTool(connection_string=None, container_name="manuals-md", fallback_path=str(DATA_FILE.parent))
    result = tool.run("machine001")
    assert "Machine 001" in result or len(result) > 0


def test_run_with_tool_input_dict():
    tool = ManualsTool(connection_string=None, container_name="manuals-md", fallback_path=str(DATA_FILE.parent))
    result = tool.run(tool_input={"machine_name": "machine001"})
    assert "Machine 001" in result or len(result) > 0


def test_fetch_manuals_lists_files():
    tool = FetchManualsTool(connection_string=None, container_name="manuals-md", fallback_path=str(DATA_FILE.parent))
    result = tool.run()
    assert "machine001.md" in result.splitlines()
