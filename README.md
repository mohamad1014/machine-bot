# Introduction

I am building this project to test the limits of "Vibe Coding" in multi-agent architecture. I will be using Codex and Github Copilot to create this project and will refrain from writing any code myself.
As we have already created something similar (but more complex and confidential) at work, I am curious to see how far we can get with this approach.

# Machine Bot

Machine Bot is a Python project designed to answer and solve questions related to specific machines in a manufacturing environment. It leverages modern AI frameworks and cloud services for robust, scalable, and interactive solutions.

## Features

- **LangChain**: Advanced language model orchestration for contextual question answering.
- **Azure Cloud Services**: Secure, scalable cloud infrastructure for data storage and processing.
- **Docling Research Index Tools**: Purpose-built utilities built on a shared Azure AI Search base class for composing queries and retrieving approved research content.
- **Telegram Integration**: Real-time communication with users via Telegram bot.
- **Gradio (Hugging Face Spaces)**: Interactive web interface for demonstrations and user interaction.
- **uv**: Fast Python package manager for efficient dependency management.

## Architecture

```
User (Telegram/Gradio) 
    |
   [Machine Bot]
    |
  [LangChain + Azure]
    |
  [Manufacturing Machine Data]
```

## Getting Started

### Prerequisites

- Python 3.12
- [uv](https://github.com/astral-sh/uv)
- Azure account & credentials
- Telegram bot token
- Hugging Face account (for Gradio Spaces)

### Installation

```bash
uv sync
```

### Configuration

1. Set up your Azure credentials.
2. Configure your Telegram bot token.
3. (Optional) Deploy to Hugging Face Spaces for Gradio UI.
4. Provide Azure AI Search settings for the document index:
   - `AZURE_SEARCH_ENDPOINT`
   - `AZURE_SEARCH_API_KEY`
   - `TESTING_AGENT_SEARCH_INDEX` (or reuse `AZURE_SEARCH_INDEX_NAME`)
   - (Optional) `AZURE_SEARCH_API_VERSION`

### Usage

- **Telegram**: Interact with the bot by sending questions about your machines.
- **Gradio**: Access the web UI for demonstrations and manual queries.
- **Local Gradio frontend**: Run `uv run python -m frontend.gradio_app` to launch a chat UI against your
  local Azure Functions host or a deployed API. Provide the API base URL and, if the endpoint is secured
  with a function key, enter it in the optional **API key** field (or set `MACHINE_BOT_API_KEY` to
  pre-populate the value). The UI now keeps a per-session `conversation_id` and includes it in all
  requests so that other integrations can correlate transcripts in the same way.

### Document research workflow

- Use the `docling_documents_search` tool when the agent needs to query the `docling-rag-documents-v422` index. Provide natural language queries plus optional tag, industry, application, or document type filters—the tool builds the JSON payload that is sent to Azure AI Search and returns only the `document_id`, `title`, and `abstract` fields.
- Call `docling_documents_content` in two steps:
  1. **Preview** – Invoke the tool with `confirm: false` (default) to list the requested document identifiers. Share that list with the user to verify the correct files.
  2. **Retrieve** – Re-run with `confirm: true` after user approval. The tool downloads the full `content` along with approved metadata fields for downstream analysis.
- The Testing Agent only uses these two tools and always follows the preview/confirm protocol before downloading any full document.

## Example

```python
# main.py
from langchain import SomeChain
from telegram import Bot
import gradio as gr

# Initialize services and start bot...
```

## Deployment
 
- Deploy backend services to Azure for scalability and security.
- Host Gradio UI on Hugging Face Spaces for public access.

## Azure Functions (Python v2)

- Entry point: `function_app.py` creates a shared `app` and imports modules under `functions/`.
- Samples included:
  - `functions/http_conversation.py` – HTTP trigger
  - `functions/timer_cleanup.py` – Timer trigger (5 minutes)
  - `functions/queue_worker.py` – Storage Queue trigger (`tasks`)
  - `functions/cosmos_listener.py` – Cosmos DB change feed trigger

### `POST /api/conversationRun`

Invoke the conversational model via an HTTP POST. The body must include an
`input` field containing the user's message. Provide a stable `conversation_id`
per client session to scope the shared conversation state; the Gradio frontend
initializes a UUID and reuses it until the session is reset.

Each invocation loads the full transcript for the provided `conversation_id` from
Cosmos DB, appends the new message, executes the agent graph, and persists the
updated transcript back to Cosmos. Reusing the same identifier maintains
conversation continuity, while using a different one isolates history.

```http
POST /api/conversationRun
Content-Type: application/json

{
  "input": "What is the status of machine 42?",
  "conversation_id": "2b6d1d22-5a02-4d8a-b17a-112233445566"
}
```

Example response (latest assistant reply):

```json
{
  "output": "Machine 42 is idle.",
  "conversation_id": "2b6d1d22-5a02-4d8a-b17a-112233445566"
}
```

### `POST /api/conversationReset`

Request a fresh `conversation_id`. Optionally include the previous identifier
if you want it echoed back in the response. The prior transcript is left in
Cosmos DB so that historical conversations remain available for auditing or
future retrieval.

```http
POST /api/conversationReset
Content-Type: application/json

{
  "conversation_id": "2b6d1d22-5a02-4d8a-b17a-112233445566"
}
```

Example response:

```json
{
  "status": "reset",
  "conversation_id": "c783b8ac-5e53-4af2-9bcb-73cf43c8ce19",
  "previous_conversation_id": null
}
```

### Local run

1) Install dependencies: `pip install -r requirements.txt`
2) Start the Functions host: `func start`

Configure local settings in `local.settings.json` (no secrets committed). Required keys:
- `AzureWebJobsStorage` (for local emulator or real storage)
- `CosmosDbConnection`, `CosmosDatabase`, `CosmosContainer` (for Cosmos trigger)
- `SqlConnectionString` (if using SQL access/bindings)

The Cosmos container now stores per-conversation transcripts keyed by the
`conversation_id` you pass to the HTTP API. Provision it with an `/id` partition
key (the default in `infra/main.bicep`) to align with the persistence model.

### Deployment

I recommend to deploy using the Azure CLI:
```
func azure functionapp publish <APP-NAME> --resource-group <RG>
```

Further deployments would be carried out using GitHub Actions. But for the first iterations I will do it manually.
### IaC (Bicep)

Infrastructure templates are in `infra/`. See `infra/README.md` for parameters and deployment steps using `az deployment group create`.

## License

MIT

## Contributing

Pull requests are welcome. For major changes, please open an issue first.

## Contact
ME
