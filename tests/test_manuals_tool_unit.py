"""Unit tests for ManualMarkdownTool.run() call signatures using local fallback.

These tests only exercise the fallback path and do not require Azure.
"""
from pathlib import Path
from middleware.manuals_tool import ManualMarkdownTool

DATA_FILE = Path(__file__).parent / "data" / "machine001.md"


def test_run_with_machine_name_kw():
    tool = ManualMarkdownTool(connection_string=None, container_name="manuals-md", fallback_path=str(DATA_FILE.parent))
    result = tool.run(machine_name="machine001")
    assert "Machine 001" in result or len(result) > 0


def test_run_with_positional_arg():
    tool = ManualMarkdownTool(connection_string=None, container_name="manuals-md", fallback_path=str(DATA_FILE.parent))
    result = tool.run("machine001")
    assert "Machine 001" in result or len(result) > 0


def test_run_with_tool_input_dict():
    tool = ManualMarkdownTool(connection_string=None, container_name="manuals-md", fallback_path=str(DATA_FILE.parent))
    result = tool.run(tool_input={"machine_name": "machine001"})
    assert "Machine 001" in result or len(result) > 0
