"""Test configuration and fixtures."""

import multiprocessing
import sys

if sys.platform == "darwin":
    multiprocessing.set_start_method("fork", force=True)


from unittest.mock import MagicMock

import pytest
import requests

from semantic_scholar_mcp.server import SemanticScholarServer


@pytest.fixture
def mock_api_key() -> str:
    """Mock API key for testing."""
    return "test-api-key"


@pytest.fixture
def server_without_api_key() -> SemanticScholarServer:
    """Create a server instance without API key."""
    return SemanticScholarServer()


@pytest.fixture
def server_with_api_key(mock_api_key: str) -> SemanticScholarServer:
    """Create a server instance with API key."""
    return SemanticScholarServer(api_key=mock_api_key)


@pytest.fixture
def mock_requests_get():
    """Mock requests.get for API calls."""
    with pytest.mock.patch("requests.get") as mock_get:  # type: ignore
        yield mock_get


@pytest.fixture
def sample_paper_response() -> dict:
    """Sample paper response from Semantic Scholar API."""
    return {
        "paperId": "649def34f8be52c8b66281af98ae884c09aef38b",
        "title": "Sample Paper Title",
        "abstract": "This is a sample abstract for testing purposes.",
        "authors": [
            {
                "authorId": "12345",
                "name": "John Doe",
                "affiliations": ["University of Example"],
            }
        ],
        "year": 2023,
        "citationCount": 42,
        "referenceCount": 15,
        "fieldsOfStudy": ["Computer Science"],
        "publicationTypes": ["JournalArticle"],
        "publicationDate": "2023-01-15",
        "journal": {"name": "Example Journal", "volume": "10", "pages": "1-10"},
        "openAccessPdf": {"url": "https://example.com/paper.pdf"},
    }


@pytest.fixture
def sample_search_response() -> dict:
    """Sample search response from Semantic Scholar API."""
    return {
        "total": 1,
        "offset": 0,
        "next": 1,
        "data": [
            {
                "paperId": "649def34f8be52c8b66281af98ae884c09aef38b",
                "title": "Sample Paper Title",
                "abstract": "This is a sample abstract for testing purposes.",
                "authors": [{"authorId": "12345", "name": "John Doe"}],
                "year": 2023,
                "citationCount": 42,
            }
        ],
    }


@pytest.fixture
def sample_authors_response() -> dict:
    """Sample authors response from Semantic Scholar API."""
    return {
        "data": [
            {
                "authorId": "12345",
                "name": "John Doe",
                "affiliations": ["University of Example"],
                "citationCount": 1000,
                "hIndex": 25,
            }
        ]
    }


@pytest.fixture
def sample_citation_response() -> dict:
    """Sample citation response from Semantic Scholar API."""
    return {
        "paperId": "649def34f8be52c8b66281af98ae884c09aef38b",
        "citationStyles": {
            "bibtex": "@article{doe2023sample,\n  title={Sample Paper Title},\n  author={Doe, John},\n  year={2023}\n}",
            "apa": "Doe, J. (2023). Sample Paper Title.",
        },
        "abstract": "This is a sample abstract for testing purposes.",
    }


@pytest.fixture
def mock_response_success():
    """Mock successful HTTP response."""
    mock_response = MagicMock(spec=requests.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    return mock_response


@pytest.fixture
def mock_response_404():
    """Mock 404 HTTP response."""
    mock_response = MagicMock(spec=requests.Response)
    mock_response.status_code = 404
    mock_response.text = "Not Found"
    return mock_response


@pytest.fixture
def mock_response_500():
    """Mock 500 HTTP response."""
    mock_response = MagicMock(spec=requests.Response)
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    return mock_response
