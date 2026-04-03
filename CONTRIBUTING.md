# Contributing Guidelines

## Local development

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) tool.
2. Install project dependencies using `uv sync` command.

## Code style

Check code style:

```bash
uv run ruff check
```


## Code formatting

Format code:

```bash
uv run ruff format
```

## Testing

Run all tests:

```bash
uv run pytest
```

Run a single test:

```bash
uv run pytest tests/test_services.py
```
