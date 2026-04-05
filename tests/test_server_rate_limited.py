"""Tests that the server gates every API call through the rate limiter."""

import time
from unittest.mock import MagicMock, patch

import pytest
from mcp.types import TextContent

from semantic_scholar_mcp.server import SemanticScholarServer


@pytest.fixture
def server(tmp_path):
    return SemanticScholarServer(
        api_key="test-key",
        rate_limit_interval=0.3,
        rate_limit_lock_path=str(tmp_path / "lock"),
    )


def _mock_api_response(data: dict, status: int = 200):
    mock = MagicMock()
    mock.status_code = status
    mock.json.return_value = data
    mock.text = ""
    return mock


class TestServerRateLimited:
    @pytest.mark.anyio
    async def test_two_searches_are_spaced(self, server: SemanticScholarServer):
        with patch("asyncio.to_thread") as mock_to_thread:
            mock_to_thread.return_value = _mock_api_response(
                {"total": 0, "data": []}
            )

            await server._handle_search_paper({"query": "a"})
            start = time.monotonic()
            await server._handle_search_paper({"query": "b"})
            elapsed = time.monotonic() - start

            assert elapsed >= 0.25

    @pytest.mark.anyio
    async def test_get_paper_is_rate_limited(self, server: SemanticScholarServer):
        with patch("asyncio.to_thread") as mock_to_thread:
            mock_to_thread.return_value = _mock_api_response(
                {"paperId": "abc", "title": "T"}
            )

            await server._handle_get_paper({"paper_id": "abc"})
            start = time.monotonic()
            await server._handle_get_paper({"paper_id": "def"})
            elapsed = time.monotonic() - start

            assert elapsed >= 0.25

    @pytest.mark.anyio
    async def test_get_authors_is_rate_limited(self, server: SemanticScholarServer):
        with patch("asyncio.to_thread") as mock_to_thread:
            mock_to_thread.return_value = _mock_api_response({"data": []})

            await server._handle_get_authors({"paper_id": "abc"})
            start = time.monotonic()
            await server._handle_get_authors({"paper_id": "def"})
            elapsed = time.monotonic() - start

            assert elapsed >= 0.25

    @pytest.mark.anyio
    async def test_get_citation_is_rate_limited(self, server: SemanticScholarServer):
        with patch("asyncio.to_thread") as mock_to_thread:
            mock_to_thread.return_value = _mock_api_response(
                {
                    "paperId": "abc",
                    "citationStyles": {"bibtex": "@article{...}"},
                    "abstract": "x",
                }
            )

            await server._handle_get_citation(
                {"paper_id": "abc", "format": "bibtex"}
            )
            start = time.monotonic()
            await server._handle_get_citation(
                {"paper_id": "def", "format": "bibtex"}
            )
            elapsed = time.monotonic() - start

            assert elapsed >= 0.25

    @pytest.mark.anyio
    async def test_default_server_has_rate_limiter(self):
        """Default constructor creates a rate limiter with 1s interval."""
        server = SemanticScholarServer()
        assert server._rate_limiter is not None
        assert server._rate_limiter._interval == 1.0
