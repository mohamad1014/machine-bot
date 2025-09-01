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

## License

MIT

## Contributing

Pull requests are welcome. For major changes, please open an issue first.

## Contact
tbd
