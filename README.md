# Introduction

I am building this project to test the limits of "Vibe Coding" in multi-agent architecture. I will be using Codex and Github Copilot to create this project and will refrain from writing any code myself.
As we have already created something similar (but more complex and confidential) at work, I am curious to see how far we can get with this approach.

# Machine Bot

Machine Bot is a Python project designed to answer and solve questions related to specific machines in a manufacturing environment. It leverages modern AI frameworks and cloud services for robust, scalable, and interactive solutions.

## Features

- **LangChain**: Advanced language model orchestration for contextual question answering.
- **Azure Cloud Services**: Secure, scalable cloud infrastructure for data storage and processing.
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

### Usage

- **Telegram**: Interact with the bot by sending questions about your machines.
- **Gradio**: Access the web UI for demonstrations and manual queries.

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

Invoke the conversational model via an HTTP POST. The endpoint accepts either
pure text messages or mixed text+image content and returns the model's
response.

**Required environment variables**

- `AZURE_OPENAI_ENDPOINT` – endpoint URL for your Azure OpenAI deployment
- `AZURE_OPENAI_API_KEY` – API key for the Azure OpenAI resource
- `AzureWebJobsStorage` – Azure Storage connection string used by the function

#### Text request

```http
POST /api/conversationRun
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "What is the status of machine 42?"}
  ]
}
```

Example response:

```json
{
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "Machine 42 is idle."
      }
    }
  ]
}
```

#### Image request

```http
POST /api/conversationRun
Content-Type: application/json

{
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "Inspect this component"},
        {"type": "image_url", "image_url": {"url": "https://example.com/photo.jpg"}}
      ]
    }
  ]
}
```

Example response:

```json
{
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "The component shows signs of wear on the belt."
      }
    }
  ]
}
```

### Local run

1) Install dependencies: `pip install -r requirements.txt`
2) Start the Functions host: `func start`

Configure local settings in `local.settings.json` (no secrets committed). Required keys:
- `AzureWebJobsStorage` (for local emulator or real storage)
- `CosmosDbConnection`, `CosmosDatabase`, `CosmosContainer` (for Cosmos trigger)
- `SqlConnectionString` (if using SQL access/bindings)

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
