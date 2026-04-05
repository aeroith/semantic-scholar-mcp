# Semantic Scholar MCP Server

A Model Context Protocol (MCP) server for the [Semantic Scholar API](https://www.semanticscholar.org/product/api) with built-in cross-process rate limiting.

Fork of [FujishigeTemma/semantic-scholar-mcp](https://github.com/FujishigeTemma/semantic-scholar-mcp) with a key addition: a **cross-process FIFO rate limiter** that enforces 1 request per second across all MCP server instances. This is critical when using tools like Claude Code that spawn parallel agents — each agent gets its own MCP server process, and without coordination they will blow past the API rate limit.

## Features

- **Paper Search**: Search for academic papers with filters for year, fields of study, and open access
- **Paper Details**: Get comprehensive information about specific papers including abstracts, authors, and citation counts
- **Author Information**: Retrieve detailed author data including affiliations, h-index, and citation metrics
- **Citation Export**: Generate citations in multiple formats (BibTeX, APA, MLA, Chicago)
- **Cross-Process Rate Limiting**: All server instances coordinate through a shared lock file to enforce 1 RPS with FIFO fairness

## Why This Fork?

The Semantic Scholar API enforces strict rate limits (1 req/s with an API key). The upstream MCP server has no rate limiting, which works fine for a single client. But when you use Claude Code (or similar tools) that launch **parallel agents**, each agent spawns its own MCP server process. With 3-5 agents running simultaneously, they each fire requests independently and quickly trigger 429 rate limit errors.

This fork adds a kernel-level file lock (`fcntl.flock`) that serializes API requests across all processes:

1. Before each HTTP request, the server acquires an exclusive lock on a shared file
2. It reads the timestamp of the last request from the file
3. If less than 1 second has passed, it sleeps for the remainder
4. It writes the new timestamp and releases the lock

The kernel's flock wait queue provides FIFO ordering, so requests are served fairly in the order they arrive.

## Setup

### Get API Key

While the Semantic Scholar API can be used without authentication, having an API key provides higher rate limits:

1. Visit [Semantic Scholar API](https://www.semanticscholar.org/product/api)
2. Request an API key

### Install from local clone

```bash
git clone https://github.com/aeroith/semantic-scholar-mcp ~/repos/semantic-scholar-mcp
```

### Add to Claude Code (global)

Add to `~/.claude/settings.json` under `mcpServers`:

```json
{
  "mcpServers": {
    "semantic-scholar-mcp": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/path/to/semantic-scholar-mcp",
        "semantic-scholar-mcp",
        "serve",
        "stdio"
      ],
      "env": {
        "SEMANTIC_SCHOLAR_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

### Add to Claude Code (project)

Add to `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "semantic-scholar-mcp": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/path/to/semantic-scholar-mcp",
        "semantic-scholar-mcp",
        "serve",
        "stdio"
      ],
      "env": {
        "SEMANTIC_SCHOLAR_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

### HTTP Transport

For web-based MCP clients:

```bash
cd /path/to/semantic-scholar-mcp
SEMANTIC_SCHOLAR_API_KEY=your-key uv run semantic-scholar-mcp serve http --port 8000
```

## Available Tools

1. **search_paper** - Search for papers
   - Required: `query` (search terms)
   - Optional: `fields`, `limit`, `offset`, `year`, `fieldsOfStudy`, `openAccessPdf`

2. **get_paper** - Get detailed paper information
   - Required: `paper_id` (supports multiple ID types: DOI, ArXiv ID, S2 Paper ID, etc.)
   - Optional: `fields` (customize returned data, see [Field Customization](#field-customization))

3. **get_authors** - Get author information for a paper
   - Required: `paper_id`
   - Optional: `fields`, `limit`, `offset`

4. **get_citation** - Generate formatted citations
   - Required: `paper_id`
   - Optional: `format` (bibtex, apa, mla, chicago)

## CLI Examples

```bash
# Search for papers
semantic-scholar-mcp tools search_paper "machine learning" --limit 5 --year "2020-2023"

# Get paper details
semantic-scholar-mcp tools get_paper "10.1038/nature12373"

# Get authors for a paper
semantic-scholar-mcp tools get_authors "649def34f8be52c8b66281af98ae884c09aef38b"

# Generate BibTeX citation
semantic-scholar-mcp tools get_citation "649def34f8be52c8b66281af98ae884c09aef38b" --format bibtex
```

## Field Customization

All tools support a `fields` parameter to customize the returned data.

### Paper Fields

| Category | Fields |
|----------|--------|
| Basic | `paperId`, `title`, `abstract`, `year`, `publicationDate` |
| Authors | `authors`, `authors.authorId`, `authors.name`, `authors.affiliations`, `authors.citationCount`, `authors.hIndex` |
| Citations | `citationCount`, `referenceCount`, `citations`, `references` |
| Publication | `journal`, `venue`, `publicationTypes`, `fieldsOfStudy`, `s2FieldsOfStudy` |
| Metadata | `doi`, `arxivId`, `url`, `openAccessPdf`, `embedding` |

### Author Fields

`authorId`, `name`, `affiliations`, `citationCount`, `hIndex`, `paperCount`, `url`

## Rate Limiting

The rate limiter coordinates across processes via a shared lock file at `/tmp/.semantic-scholar-rate-lock`. Both the interval and lock path are configurable:

```python
from semantic_scholar_mcp.server import SemanticScholarServer

server = SemanticScholarServer(
    api_key="your-key",
    rate_limit_interval=1.0,                          # seconds between requests
    rate_limit_lock_path="/tmp/.my-custom-lock-file",  # shared lock file path
)
```

### API Rate Limits

- Without API key: 100 requests per 5 minutes
- With API key: 1 request per second

## Supported Paper ID Types

- Semantic Scholar ID (e.g., `649def34f8be52c8b66281af98ae884c09aef38b`)
- DOI (e.g., `DOI:10.1038/nature12373`)
- ArXiv (e.g., `ARXIV:2106.15928`)
- MAG, ACL, PubMed, PubMed Central, Corpus ID

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest tests/

# Format and lint
uv run ruff format .
uv run ruff check . --fix

# Type check
uv run ty check
```

### Project Structure

```
semantic-scholar-mcp/
  src/semantic_scholar_mcp/
    __init__.py
    server.py          # MCP server with rate-limited API handlers
    rate_limiter.py    # Cross-process FIFO rate limiter (fcntl.flock)
    cli.py             # CLI interface (stdio + HTTP transports)
  tests/
    test_rate_limiter.py         # Unit + cross-process rate limiter tests
    test_server_rate_limited.py  # Integration tests (server + rate limiter)
    test_server.py               # Core server tests
    test_integration.py          # Edge case and API handling tests
    test_cli.py                  # CLI tests
```

## License

MIT License

## Acknowledgments

- Upstream: [FujishigeTemma/semantic-scholar-mcp](https://github.com/FujishigeTemma/semantic-scholar-mcp)
- [Semantic Scholar API](https://www.semanticscholar.org/product/api)
