import pytest


manual_agent = pytest.importorskip("agents.manual_agent")
langchain = pytest.importorskip("langchain")
pytest.importorskip("langchain_openai")

from langchain_core.messages import AIMessage, ToolCall
from langchain_core.chat_models.fake import FakeListChatModel


def _build_fake_tool_call_model():
    responses = [
        AIMessage(
            content="",
            tool_calls=[
                ToolCall(
                    name="manual_markdown_lookup",
                    args={
                        "machine_name": "machine001",
                        "user_message": "How do I use it?",
                    },
                    id="call_1",
                )
            ],
        ),
        AIMessage(content="Manual consulted"),
    ]
    return FakeListChatModel(responses=responses)


def _build_fake_final_model():
    responses = [AIMessage(content="saw image")]
    return FakeListChatModel(responses=responses)


@pytest.fixture
def manual_file(tmp_path):
    manuals = tmp_path / "manuals-md"
    manuals.mkdir()
    (manuals / "machine001.md").write_text("Step 1")
    return manuals


def test_agent_invokes_manual_tool(monkeypatch, manual_file):
    fake_model = _build_fake_tool_call_model()
    monkeypatch.setattr(
        manual_agent, "AzureChatOpenAI", lambda **_: fake_model
    )
    agent = manual_agent.create_manual_agent(fallback_path=str(manual_file))
    result = agent.invoke({"input": "How do I use it?", "machine_name": "machine001"})
    assert "Step 1" in result["output"]


def test_agent_accepts_image_input(monkeypatch, manual_file):
    fake_model = _build_fake_final_model()
    monkeypatch.setattr(
        manual_agent, "AzureChatOpenAI", lambda **_: fake_model
    )
    agent = manual_agent.create_manual_agent(fallback_path=str(manual_file))
    img_input = [
        {"type": "text", "text": "What is shown?"},
        {"type": "image_url", "image_url": {"url": "http://example.com"}},
    ]
    result = agent.invoke({"input": img_input, "machine_name": "machine001"})
    assert result["output"] == "saw image"
