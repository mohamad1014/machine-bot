"""Local Gradio UI for interacting with the Machine Bot conversation API."""

from __future__ import annotations

import json
import os
from typing import List, Tuple
from uuid import uuid4

import gradio as gr
import requests

DEFAULT_API_BASE = os.environ.get("MACHINE_BOT_API_BASE", "http://localhost:7071/api")
DEFAULT_API_KEY = os.environ.get("MACHINE_BOT_API_KEY", "")
RUN_ENDPOINT = os.environ.get("MACHINE_BOT_RUN_ENDPOINT", "conversationRun")
RESET_ENDPOINT = os.environ.get("MACHINE_BOT_RESET_ENDPOINT", "conversationReset")


def _normalize_base_url(base_url: str | None) -> str:
    """Normalize and sanitize the configured API base URL."""

    if not base_url:
        return DEFAULT_API_BASE.rstrip("/")
    cleaned = base_url.strip()
    if not cleaned:
        return DEFAULT_API_BASE.rstrip("/")
    return cleaned.rstrip("/")


def _post_json(
    url: str,
    payload: dict[str, object] | None = None,
    timeout: int = 60,
    api_key: str | None = None,
) -> dict[str, object]:
    """Send a JSON POST request and return the parsed response."""

    response = requests.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    try:
        return response.json()
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"Invalid JSON received from {url}") from exc


def handle_message(
    message: str,
    history: List[Tuple[str, str]],
    api_base: str,
    api_key: str,
    conversation_id: str,
) -> Tuple[List[Tuple[str, str]], str, str]:
    """Send the user's message to the API and append the response to history."""

    if not message.strip():
        return history, "", conversation_id

    base_url = _normalize_base_url(api_base)
    # If api_key is provided, append as ?code=... to the endpoint
    run_url = f"{base_url}/{RUN_ENDPOINT}"
    if api_key.strip():
        run_url += f"?code={api_key.strip()}"
    try:
        data = _post_json(
            run_url,
            {"input": message, "conversation_id": conversation_id},
        )
        bot_reply = str(data.get("output", ""))
        remote_conversation_id = data.get("conversation_id")
        if isinstance(remote_conversation_id, str) and remote_conversation_id.strip():
            conversation_id = remote_conversation_id.strip()
    except (requests.RequestException, ValueError) as exc:
        bot_reply = f"Error contacting API: {exc}"

    updated_history = history + [(message, bot_reply)]
    return updated_history, "", conversation_id


def reset_conversation(
    api_base: str, api_key: str, conversation_id: str
) -> Tuple[List[Tuple[str, str]], str, str]:
    """Clear both the UI history and the shared server-side memory."""

    base_url = _normalize_base_url(api_base)
    reset_url = f"{base_url}/{RESET_ENDPOINT}"
    if api_key.strip():
        reset_url += f"?code={api_key.strip()}"
    new_conversation_id = str(uuid4())
    try:
        _post_json(
            reset_url,
            payload={"conversation_id": conversation_id} if conversation_id else None,
            timeout=10,
        )
        gr.Info(f"Conversation reset. New session id: {new_conversation_id}")
    except (requests.RequestException, ValueError) as exc:
        gr.Warning(f"Unable to reset remote conversation: {exc}")

    return [], "", new_conversation_id


def update_api_base(new_base: str) -> str:
    """Normalize the API base URL whenever the user edits the textbox."""

    normalized = _normalize_base_url(new_base)
    if normalized != new_base:
        gr.Info(f"Using API base: {normalized}")
    return normalized


with gr.Blocks(title="Machine Bot Chat") as demo:
    gr.Markdown(
        """
        # Machine Bot Chat

        Connect to a locally running Azure Functions host or a deployed API to chat with the
        Machine Bot agents. Update the API base URL if you want to talk to a remote instance.
        """
    )

    api_base_input = gr.Textbox(
        value=DEFAULT_API_BASE,
        label="API base URL",
        info=(
            "For example: http://localhost:7071/api or "
            "https://<function-app>.azurewebsites.net/api"
        ),
    )

    function_key_input = gr.Textbox(
        value=DEFAULT_API_KEY,
        label="Function URL code (optional)",
        type="password",
        placeholder="Azure Functions ?code=... value",
    )

    chatbot = gr.Chatbot(label="Conversation", type="tuples")
    message_box = gr.Textbox(label="Message", placeholder="Ask about a machine...", lines=2)
    conversation_state = gr.State(str(uuid4()))

    with gr.Row():
        send_button = gr.Button("Send", variant="primary")
        new_session_button = gr.Button("Start new session")

    api_base_input.blur(fn=update_api_base, inputs=api_base_input, outputs=api_base_input)

    send_button.click(
        fn=handle_message,
        inputs=[message_box, chatbot, api_base_input, function_key_input, conversation_state],
        outputs=[chatbot, message_box, conversation_state],
    )
    message_box.submit(
        fn=handle_message,
        inputs=[message_box, chatbot, api_base_input, function_key_input, conversation_state],
        outputs=[chatbot, message_box, conversation_state],
    )

    new_session_button.click(
        fn=reset_conversation,
        inputs=[api_base_input, function_key_input, conversation_state],
        outputs=[chatbot, message_box, conversation_state],
    )


if __name__ == "__main__":
    demo.launch()
