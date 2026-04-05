"""Semantic Scholar MCP Server implementation."""

import asyncio
from typing import Any

import requests
from mcp.server import Server
from mcp.types import Resource, TextContent, Tool

from .rate_limiter import RateLimiter

_rate_limit_to_thread = asyncio.to_thread


class SemanticScholarServer:
    """MCP server for Semantic Scholar operations."""

    def __init__(
        self,
        api_key: str | None = None,
        rate_limit_interval: float = 1.0,
        rate_limit_lock_path: str = "/tmp/.semantic-scholar-rate-lock",
    ) -> None:
        self.server = Server("semantic-scholar-mcp")
        self.api_key = api_key
        self.base_url = "https://api.semanticscholar.org/graph/v1"
        self._rate_limiter = RateLimiter(
            interval=rate_limit_interval,
            lock_path=rate_limit_lock_path,
        )
        self._setup_tools()
        self._setup_resources()
        self._setup_handlers()

    def _setup_tools(self) -> None:
        """Register available tools."""

        @self.server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            """List available tools."""
            return [
                Tool(
                    name="search_paper",
                    description="Search for papers using Semantic Scholar. Use 'fields' parameter to customize returned data",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": """A plain-text search query string.

- No special query syntax is supported
- Hyphenated query terms yield no matches (replace it with space to find matches).""",
                            },
                            "fields": {
                                "type": "string",
                                "description": """A comma-separated list of the fields to be returned. The paperId field is always returned. See the resource 'semantic-scholar://fields/paper' for available fields.

Examples:
- `title,url`
- `title,embedding.specter_v2`
- `title,authors,citations.title,citations.abstract`
                                """,
                                "default": self.search_paper_default_fields,
                            },
                            "publicationTypes": {
                                "type": "string",
                                "description": """A comma-separated list of publication types to include.

Available types: Review, JournalArticle, CaseReort, ClinicalTrial, Conference, Dataset, Editorial, LettersAndComments, MetaAnalysis, News, Study, Book, BookSection
Example: `Review,JournalArticle` will return papers with publication types Review and/or JournalArticle""",
                            },
                            "openAccessPdf": {
                                "type": "boolean",
                                "description": "Restricts results to only include papers with a public PDF.",
                                "default": False,
                            },
                            "minCitationCount": {
                                "type": "integer",
                                "description": "Restricts results to only include papers with the minimum number of citations.",
                                "default": 0,
                            },
                            "publicationDateOrYear": {
                                "type": "string",
                                "description": """Restricts results to the given range of publication dates or years (inclusive). Accepts the format `<startDate>:<endDate>` with each date in `YYYY-MM-DD` format.
Each term is optional, allowing for specific dates, fixed ranges, or open-ended ranges. In addition, prefixes are suported as a shorthand, e.g. `2020-06` matches all dates in June 2020.
Specific dates are not known for all papers, so some records returned with this filter will have a `null` value for publicationDate. `year`, however, will always be present. For records where a specific publication date is not known, they will be treated as if published on January 1st of their publication year.

Examples:

- `2019-03-05` on March 3rd, 2019
- `2019-03` during March 2019
- `2019` during 2019
- `2016-03-05:2020-06-06` as early as March 5th, 2016 or as late as June 6th, 2020
- `1981-08-25:` on or after August 25th, 1981
- `:2015-01` before or on January 31st, 2015
- `2015:2020` between January 1st, 2015 and December 31st, 2020
""",
                            },
                            "year": {
                                "type": "string",
                                "description": """Restricts results to the given publication year or range of years (inclusive).

Examples:

- `2019` in 2019
- `2016-2020` as early as 2016 or as late as 2020
- `2010-` during or after 2010
- `-2015` before or during 2015""",
                            },
                            "venue": {
                                "type": "string",
                                "description": """Restricts results to papers published in the given venues, formatted as a comma-separated list.

Input could also be an ISO4 abbreviation. Examples include:
- Nature
- New England Journal of Medicine
- Radiology
- N. Engl. J. Med.

Example: `Nature,Radiology` will return papers from venues Nature and/or Radiology.""",
                            },
                            "fieldsOfStudy": {
                                "type": "string",
                                "description": """A Comma-separated list of fields of study to include.

Available fields of study: Computer Science,Medicine,Chemistry,Biology,Materials Science,Physics,Geology,Psychology,Art,History,Geography,Sociology,Business,Political Science,Economics,Philosophy,Mathematics,Engineering,Environmental Science,Agricultural and Food Sciences,Education,Law,Linguistics
Example: `Physics,Mathematics` will return papers with either Physics or Mathematics in their list of fields-of-study.""",
                            },
                            "offset": {
                                "type": "integer",
                                "description": "Starting position in the list of results",
                                "default": 0,
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return (max: 100)",
                                "default": 10,
                            },
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="get_paper",
                    description="Get detailed information about a specific paper. Use 'fields' parameter to customize returned data.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "paper_id": {
                                "type": "string",
                                "description": """The following types of IDs are supported:
- `<sha>` - a Semantic Scholar ID, e.g. `649def34f8be52c8b66281af98ae884c09aef38b`
- `CorpusId:<id>` - a Semantic Scholar numerical ID, e.g. `CorpusId:215416146`
- `DOI:<doi>` - a Digital Object Identifier, e.g. `DOI:10.18653/v1/N18-3011`
- `ARXIV:<id>` - arXiv.rg, e.g. `ARXIV:2106.15928`
- `MAG:<id>` - Microsoft Academic Graph, e.g. `MAG:112218234`
- `ACL:<id>` - Association for Computational Linguistics, e.g. `ACL:W12-3903`
- `PMID:<id>` - PubMed/Medline, e.g. `PMID:19872477`
- `PMCID:<id>` - PubMed Central, e.g. `PMCID:2323736`
- `URL:<url>` - URL from one of the sites listed below, e.g. `URL:https://arxiv.org/abs/2106.15928v1`

URLs are recognized from the following sites:
- semanticscholar.org
- arxiv.org
- aclweb.org
- acm.org
- biorxiv.org""",
                            },
                            "fields": {
                                "type": "string",
                                "description": """A comma-separated list of the fields to be returned. The paperId field is always returned. See the resource 'semantic-scholar://fields/paper' for available fields.

Examples:
- `title,url`
- `title,embedding.specter_v2`
- `title,authors,citations.title,citations.abstract`
                                """,
                                "default": self.get_paper_default_fields,
                            },
                        },
                        "required": ["paper_id"],
                    },
                ),
                Tool(
                    name="get_authors",
                    description="Get authors information for a specific paper. Use 'fields' parameter to customize author data returned.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "paper_id": {
                                "type": "string",
                                "description": """The following types of IDs are supported:
- `<sha>` - a Semantic Scholar ID, e.g. `649def34f8be52c8b66281af98ae884c09aef38b`
- `CorpusId:<id>` - a Semantic Scholar numerical ID, e.g. `CorpusId:215416146`
- `DOI:<doi>` - a Digital Object Identifier, e.g. `DOI:10.18653/v1/N18-3011`
- `ARXIV:<id>` - arXiv.rg, e.g. `ARXIV:2106.15928`
- `MAG:<id>` - Microsoft Academic Graph, e.g. `MAG:112218234`
- `ACL:<id>` - Association for Computational Linguistics, e.g. `ACL:W12-3903`
- `PMID:<id>` - PubMed/Medline, e.g. `PMID:19872477`
- `PMCID:<id>` - PubMed Central, e.g. `PMCID:2323736`
- `URL:<url>` - URL from one of the sites listed below, e.g. `URL:https://arxiv.org/abs/2106.15928v1`

URLs are recognized from the following sites:
- semanticscholar.org
- arxiv.org
- aclweb.org
- acm.org
- biorxiv.org""",
                            },
                            "fields": {
                                "type": "string",
                                "description": """A comma-separated list of the fields to be returned. The authorId field is always returned. See the resource 'semantic-scholar://fields/author' for available fields.

Examples:
- `name,affiliations,papers`
- `url,papers.year,papers.authors`
                                """,
                                "default": "authorId,name,affiliations,citationCount,hIndex",
                            },
                            "offset": {
                                "type": "integer",
                                "description": "Used for pagination. When returning a list of results, start with the element at this position in the list.",
                                "default": 0,
                            },
                            "limit": {
                                "type": "integer",
                                "description": "The maximum number of results to return. Maximum is 1000.",
                                "default": 100,
                            },
                        },
                        "required": ["paper_id"],
                    },
                ),
                Tool(
                    name="get_citation",
                    description="Get citation information in various formats.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "paper_id": {
                                "type": "string",
                                "description": """The following types of IDs are supported:
- `<sha>` - a Semantic Scholar ID, e.g. `649def34f8be52c8b66281af98ae884c09aef38b`
- `CorpusId:<id>` - a Semantic Scholar numerical ID, e.g. `CorpusId:215416146`
- `DOI:<doi>` - a Digital Object Identifier, e.g. `DOI:10.18653/v1/N18-3011`
- `ARXIV:<id>` - arXiv.rg, e.g. `ARXIV:2106.15928`
- `MAG:<id>` - Microsoft Academic Graph, e.g. `MAG:112218234`
- `ACL:<id>` - Association for Computational Linguistics, e.g. `ACL:W12-3903`
- `PMID:<id>` - PubMed/Medline, e.g. `PMID:19872477`
- `PMCID:<id>` - PubMed Central, e.g. `PMCID:2323736`
- `URL:<url>` - URL from one of the sites listed below, e.g. `URL:https://arxiv.org/abs/2106.15928v1`

URLs are recognized from the following sites:
- semanticscholar.org
- arxiv.org
- aclweb.org
- acm.org
- biorxiv.org""",
                            },
                            "format": {
                                "type": "string",
                                "description": "Citation format: 'bibtex', 'apa', 'mla', or 'chicago'",
                                "default": "bibtex",
                            },
                        },
                        "required": ["paper_id"],
                    },
                ),
            ]

    def _setup_resources(self) -> None:
        """Register available resources."""

        @self.server.list_resources()
        async def handle_list_resources() -> list[Resource]:
            """List available resources."""
            return [
                Resource(
                    uri="semantic-scholar://fields/paper",  # type: ignore
                    name="Paper Fields Reference",
                    description="Complete list of available fields for paper-related tools",
                    mimeType="text/markdown",
                ),
                Resource(
                    uri="semantic-scholar://fields/author",  # type: ignore
                    name="Author Fields Reference",
                    description="Complete list of available fields for author-related tools",
                    mimeType="text/markdown",
                ),
            ]

        @self.server.read_resource()  # type: ignore
        async def handle_read_resource(uri: str) -> str:
            """Read resource content."""
            if uri == "semantic-scholar://fields/paper":
                return self._get_paper_fields_documentation()
            elif uri == "semantic-scholar://fields/author":
                return self._get_author_fields_documentation()
            else:
                raise ValueError(f"Unknown resource: {uri}")

    def _get_paper_fields_documentation(self) -> str:
        """Get paper fields documentation."""
        return """# Paper Fields Reference

## Basic Fields
- `paperId` - Unique paper identifier
- `title` - Paper title
- `abstract` - Paper abstract
- `year` - Publication year
- `publicationDate` - Full publication date (YYYY-MM-DD)

## Author Information
- `authors` - List of authors (returns authorId and name by default)
- `authors.authorId` - Author's unique identifier
- `authors.name` - Author's name
- `authors.affiliations` - Author's institutional affiliations
- `authors.citationCount` - Author's total citation count
- `authors.hIndex` - Author's h-index

## Citation and Reference Data
- `citationCount` - Number of times this paper has been cited
- `referenceCount` - Number of references in this paper
- `citations` - List of papers that cite this paper
- `references` - List of papers referenced by this paper

## Publication Details
- `journal` - Journal information (name, volume, pages, etc.)
- `venue` - Publication venue
- `publicationTypes` - Types of publication (e.g., JournalArticle, Conference)
- `fieldsOfStudy` - Academic fields (e.g., Computer Science, Medicine)
- `s2FieldsOfStudy` - Semantic Scholar's field classifications

## Additional Metadata
- `doi` - Digital Object Identifier
- `arxivId` - ArXiv identifier
- `url` - Paper URL
- `openAccessPdf` - Open access PDF information
- `embedding` - Paper embedding vectors (for similarity analysis)
"""

    def _get_author_fields_documentation(self) -> str:
        """Get author fields documentation."""
        return """# Author Fields Reference

## Available Fields
- `authorId` - Unique author identifier
- `name` - Author's name
- `affiliations` - Institutional affiliations (array)
- `citationCount` - Total citation count across all papers
- `hIndex` - h-index metric
- `paperCount` - Number of papers published
- `url` - Author's Semantic Scholar profile URL
"""

    def _setup_handlers(self) -> None:
        """Setup tool call handlers."""

        @self.server.call_tool()
        async def handle_call_tool(
            name: str, arguments: dict[str, Any]
        ) -> list[TextContent]:
            """Handle tool calls."""
            if name == "search_paper":
                return await self._handle_search_paper(arguments)
            elif name == "get_paper":
                return await self._handle_get_paper(arguments)
            elif name == "get_authors":
                return await self._handle_get_authors(arguments)
            elif name == "get_citation":
                return await self._handle_get_citation(arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")

    def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    search_paper_default_fields = "paperId,title,abstract,authors,year,citationCount"

    async def _handle_search_paper(
        self, arguments: dict[str, Any]
    ) -> list[TextContent]:
        """Handle paper search requests."""
        try:
            params = {
                "query": arguments["query"],
                "fields": arguments.get("fields", self.search_paper_default_fields),
                "offset": arguments.get("offset", 0),
                "limit": min(arguments.get("limit", 10), 100),
            }

            for queryParams in [
                "publicationTypes",
                "minCitationCount",
                "publicationDateOrYear",
                "year",
                "venue",
                "fieldsOfStudy",
            ]:
                if queryParams in arguments:
                    params[queryParams] = arguments[queryParams]
            if arguments.get("openAccessPdf"):
                params["openAccessPdf"] = ""

            await _rate_limit_to_thread(self._rate_limiter.acquire)
            response = await asyncio.to_thread(
                requests.get,
                f"{self.base_url}/paper/search",
                params=params,
                headers=self._get_headers(),
                timeout=30,
            )

            if response.status_code != 200:
                return [
                    TextContent(
                        type="text",
                        text=f"Error: API returned status {response.status_code}: {response.text}",
                    )
                ]

            res = response.json()

            return [TextContent(type="text", text=str(res))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error searching papers: {str(e)}")]

    get_paper_default_fields = "paperId,title,abstract,authors,year,citationCount,referenceCount,fieldsOfStudy,publicationTypes,publicationDate,journal,openAccessPdf"

    async def _handle_get_paper(self, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle get paper details requests."""
        try:
            paper_id = arguments["paper_id"]

            params = {"fields": arguments.get("fields", self.get_paper_default_fields)}

            await _rate_limit_to_thread(self._rate_limiter.acquire)
            response = await asyncio.to_thread(
                requests.get,
                f"{self.base_url}/paper/{paper_id}",
                params=params,
                headers=self._get_headers(),
                timeout=30,
            )

            if response.status_code == 404:
                return [TextContent(type="text", text=f"Paper not found: {paper_id}")]
            elif response.status_code != 200:
                return [
                    TextContent(
                        type="text",
                        text=f"Error: API returned status {response.status_code}: {response.text}",
                    )
                ]

            res = response.json()

            return [TextContent(type="text", text=str(res))]
        except Exception as e:
            return [
                TextContent(type="text", text=f"Error getting paper details: {str(e)}")
            ]

    get_authors_default_fields = "authorId,name,affiliations,citationCount,hIndex"

    async def _handle_get_authors(self, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle get paper authors requests."""
        try:
            paper_id = arguments["paper_id"]

            params = {
                "fields": arguments.get("fields", self.get_authors_default_fields),
                "offset": arguments.get("offset", 0),
                "limit": min(arguments.get("limit", 100), 1000),
            }

            await _rate_limit_to_thread(self._rate_limiter.acquire)
            response = await asyncio.to_thread(
                requests.get,
                f"{self.base_url}/paper/{paper_id}/authors",
                params=params,
                headers=self._get_headers(),
                timeout=30,
            )

            if response.status_code == 404:
                return [TextContent(type="text", text=f"Paper not found: {paper_id}")]
            elif response.status_code != 200:
                return [
                    TextContent(
                        type="text",
                        text=f"Error: API returned status {response.status_code}: {response.text}",
                    )
                ]

            res = response.json()

            return [TextContent(type="text", text=res)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error getting authors: {str(e)}")]

    async def _handle_get_citation(
        self, arguments: dict[str, Any]
    ) -> list[TextContent]:
        """Handle get citation requests."""
        try:
            paper_id = arguments["paper_id"]
            citation_format = arguments.get("format", "bibtex").lower()

            await _rate_limit_to_thread(self._rate_limiter.acquire)
            response = await asyncio.to_thread(
                requests.get,
                f"{self.base_url}/paper/{paper_id}",
                params={"fields": "citationStyles, abstract"},
                headers=self._get_headers(),
                timeout=30,
            )

            if response.status_code == 404:
                return [TextContent(type="text", text=f"Paper not found: {paper_id}")]
            elif response.status_code != 200:
                return [
                    TextContent(
                        type="text",
                        text=f"Error: API returned status {response.status_code}: {response.text}",
                    )
                ]

            data = response.json()

            if "citationStyles" not in data:
                return [
                    TextContent(
                        type="text", text="No citation styles available for this paper."
                    )
                ]
            if citation_format not in data["citationStyles"]:
                return [
                    TextContent(
                        type="text",
                        text=f"Citation format '{citation_format}' not available. Available formats for this paper: {', '.join(data['citationStyles'].keys())}",
                    )
                ]

            citation = data["citationStyles"][citation_format]
            abstract = data.get("abstract", "")

            result_text = add_abstract(citation, abstract, citation_format)
            return [TextContent(type="text", text=result_text)]
        except Exception as e:
            return [
                TextContent(type="text", text=f"Error generating citation: {str(e)}")
            ]


def add_abstract(citation: str, abstract: str, citation_format: str) -> str:
    return "TODO"
