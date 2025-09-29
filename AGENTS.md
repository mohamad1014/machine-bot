# AGENTS.md

## Project summary
Machine Bot is an Azure Functions (Python) application that orchestrates LangChain agents to answer questions about manufacturing machines.  The app exposes HTTP, timer, queue, and Cosmos DB triggers under `functions/`, while shared business logic for agents, tools, and middleware lives under dedicated packages in the repo root.

## Key directories
- `function_app.py`: Azure Functions entry point that wires triggers to the shared FastAPI-style app object.
- `functions/`: Individual function triggers (HTTP, queue, timer, Cosmos DB).  Tests mock these functions directly.
- `agents/`: Agent implementations built on LangChain / LangGraph.
- `middleware/`: Reusable middleware and routing helpers for orchestrating the agent graph.
- `infra/`: Bicep templates and deployment assets.
- `tests/`: Pytest suite covering the Azure Functions and agent behaviors.  Test data fixtures are under `tests/data/`.

## Environment setup
1. Install Python 3.12.
2. Prefer [`uv`](https://github.com/astral-sh/uv) for dependency management:
   ```bash
   uv sync
   ```
   Alternatively you can fall back to `pip install -r requirements.txt`.
3. Activate the virtual environment that `uv` creates (`.venv/`) or ensure your interpreter points at the synced environment.
4. Populate the following environment variables when running live against Azure services:
   - `AZURE_OPENAI_ENDPOINT`
   - `AZURE_OPENAI_API_KEY`
   - `AzureWebJobsStorage`
   - `CosmosDbConnection`, `CosmosDatabase`, `CosmosContainer`
   - `SqlConnectionString` (if SQL bindings are used)
   Local tests typically mock these values, so they are not required for `pytest`.

## Common commands
- Run the full test suite:
  ```bash
  uv run pytest
  ```
- Run a single test module:
  ```bash
  uv run pytest tests/test_http_conversation.py
  ```
- Lint and type-check the project:
  ```bash
  uv run ruff check .
  uv run mypy .
  ```
- Start the local Azure Functions host after installing requirements:
  ```bash
  func start
  ```

## Coding guidelines
- Follow standard Python typing practices; the project targets Python 3.12 with `from __future__ import annotations` where useful.
- Keep Azure Function handlers stateless.  Use helpers in `agents/` and `middleware/` for shared state.
- Prefer small, pure functions for agent tools and include docstrings describing tool contracts.
- Update or add pytest coverage when modifying behavior.  Tests should not depend on real Azure resources; use fixtures or monkeypatching.

## Pull request & CI expectations
- Ensure `uv run pytest`, `uv run ruff check .`, and `uv run mypy .` complete without errors before submitting a PR.
- Follow conventional commit-style messages when possible (e.g., `feat:`, `fix:`, `chore:`) to keep history readable.
- Describe any required environment variables or infra changes in the PR body if they are relevant to reviewers.
