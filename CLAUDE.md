# Development Guidelines

## Architecture

### Rate Limiter (`rate_limiter.py`)

Cross-process FIFO rate limiter using `fcntl.flock`. All MCP server instances coordinate through a shared lock file at `/tmp/.semantic-scholar-rate-lock`. The `acquire()` method is blocking and runs in a thread via `asyncio.to_thread`.

### Server (`server.py`)

Every `_handle_*` method calls `await _rate_limit_to_thread(self._rate_limiter.acquire)` before making the HTTP request. Constructor accepts `rate_limit_interval` (default 1.0s) and `rate_limit_lock_path` for testing with isolated lock files and faster intervals.

### CLI (`cli.py`)

In `stdio` transport mode, all diagnostic messages go to stderr to avoid corrupting MCP JSON-RPC framing.

## Commands

```bash
uv run pytest tests/              # Run tests
uv run ruff format .              # Format
uv run ruff check . --fix         # Lint
uv run ty check                   # Type check
```

## Rules

- Use uv, never pip
- Type hints required for all code
- Line length: 88 chars max
- New features require tests, bug fixes require regression tests
- Async testing: use anyio, not asyncio
