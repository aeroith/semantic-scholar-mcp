"""CLI interface for the Semantic Scholar MCP Server."""

import anyio
import click
import uvicorn
from mcp.server.stdio import stdio_server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.routing import Mount

from .server import SemanticScholarServer


@click.group()
@click.version_option()
def cli() -> None:
    """Semantic Scholar MCP Server - A Model Context Protocol server for Semantic Scholar.

    This CLI provides commands to interact with Semantic Scholar API,
    including search, paper details, author info, and citation operations.
    """
    pass


@cli.command()
@click.argument("transport", type=click.Choice(["stdio", "http"]), default="stdio")
@click.option(
    "--port",
    type=int,
    default=8000,
    help="Port to bind the HTTP server to (default: 8000, only used with 'http' transport)",
)
@click.option(
    "--host",
    default="127.0.0.1",
    help="Host to bind the HTTP server to (default: 127.0.0.1, only used with 'http' transport)",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug mode with additional logging",
)
@click.option(
    "--api-key",
    envvar="SEMANTIC_SCHOLAR_API_KEY",
    help="Semantic Scholar API key (can also be set via SEMANTIC_SCHOLAR_API_KEY environment variable)",
)
def serve(
    transport: str,
    port: int,
    host: str,
    debug: bool,
    api_key: str | None,
) -> None:
    """Start the MCP server with specified transport.

    TRANSPORT: Choose between 'stdio' (default, MCP standard) or 'http' (Streamable HTTP)

    - stdio: Standard MCP communication via stdin/stdout
    - http: HTTP server with Streamable HTTP for web-based clients
    """
    import sys

    log = sys.stderr if transport == "stdio" else sys.stdout

    if debug:
        click.echo("Debug mode enabled", file=log)

    if api_key:
        click.echo("✓ Semantic Scholar API key configured", file=log)
    else:
        click.echo(
            "⚠️  No Semantic Scholar API key found (set SEMANTIC_SCHOLAR_API_KEY environment variable for higher rate limits)",
            file=log,
        )

    server_instance = SemanticScholarServer(api_key=api_key)

    click.echo("\nAvailable tools:", file=log)
    click.echo("  • search_paper - Search for papers using Semantic Scholar", file=log)
    click.echo("  • get_paper - Get detailed information about a specific paper", file=log)
    click.echo("  • get_authors - Get authors information for a specific paper", file=log)
    click.echo("  • get_citation - Get citation information in various formats", file=log)

    if transport == "http":
        click.echo(f"\nStarting HTTP server on http://{host}:{port}")
        click.echo("Available endpoints:")
        click.echo(f"  • HTTP  http://{host}:{port}/mcp - MCP over HTTP endpoint")

        session_manager = StreamableHTTPSessionManager(
            app=server_instance.server,
            event_store=None,
            json_response=True,
            stateless=True,
        )

        async def handle_streamable_http(scope, receive, send):
            await session_manager.handle_request(scope, receive, send)

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def lifespan(app: Starlette):
            async with session_manager.run():
                yield

        starlette_app = Starlette(
            debug=debug,
            lifespan=lifespan,
            routes=[
                Mount("/mcp", app=handle_streamable_http),
            ],
        )

        uvicorn.run(starlette_app, host=host, port=port)
    else:  # stdio
        click.echo("\nStarting Semantic Scholar MCP Server...", file=log)
        click.echo("Server will communicate via stdio (MCP standard)", file=log)
        click.echo("Server ready. Waiting for MCP client connection...", file=log)

        async def async_main() -> None:
            async with stdio_server() as (read_stream, write_stream):
                await server_instance.server.run(
                    read_stream,
                    write_stream,
                    server_instance.server.create_initialization_options(),
                )

        anyio.run(async_main)


@click.group()
@click.option(
    "--api-key",
    envvar="SEMANTIC_SCHOLAR_API_KEY",
    help="Semantic Scholar API key (can also be set via SEMANTIC_SCHOLAR_API_KEY environment variable)",
)
@click.pass_context
def tools(ctx: click.Context, api_key: str | None) -> None:
    """MCP tools for interacting with Semantic Scholar."""
    ctx.ensure_object(dict)
    ctx.obj["api_key"] = api_key


@tools.command("list")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "table"]),
    default="table",
    help="Output format (default: table)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed information about each tool including schemas and examples",
)
def list_tools(output_format: str, verbose: bool) -> None:
    """List all available MCP tools provided by the server."""

    tools_data = [
        {
            "name": "search_paper",
            "description": "Search for papers using Semantic Scholar",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Plain-text search query string",
                    },
                    "fields": {
                        "type": "string",
                        "description": "Comma-separated list of fields to return",
                        "default": "paperId,title,abstract,authors,year,citationCount",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (max: 100)",
                        "default": 10,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Starting position in the list of results",
                        "default": 0,
                    },
                    "year": {
                        "type": "string",
                        "description": "Publication year or range (e.g., '2019', '2016-2020')",
                    },
                    "fieldsOfStudy": {
                        "type": "string",
                        "description": "Comma-separated list of fields of study",
                    },
                    "openAccessPdf": {
                        "type": "boolean",
                        "description": "Filter to only include papers with open access PDFs",
                        "default": False,
                    },
                },
                "required": ["query"],
            },
            "examples": [
                {
                    "description": "Search for machine learning papers",
                    "input": {"query": "machine learning"},
                    "usage": "Find papers about machine learning",
                },
                {
                    "description": "Search with filters",
                    "input": {
                        "query": "neural networks",
                        "year": "2020-2023",
                        "fieldsOfStudy": "Computer Science",
                        "limit": 5,
                    },
                    "usage": "Find recent neural network papers in Computer Science",
                },
            ],
        },
        {
            "name": "get_paper",
            "description": "Get detailed information about a specific paper",
            "input_schema": {
                "type": "object",
                "properties": {
                    "paper_id": {
                        "type": "string",
                        "description": "Paper ID (supports S2, DOI, ArXiv, MAG, ACL, PubMed, Corpus ID)",
                    },
                    "fields": {
                        "type": "string",
                        "description": "Comma-separated list of fields to return",
                        "default": "paperId,title,abstract,authors,year,citationCount,referenceCount,fieldsOfStudy,publicationTypes,publicationDate,journal,openAccessPdf",
                    },
                },
                "required": ["paper_id"],
            },
            "examples": [
                {
                    "description": "Get paper by DOI",
                    "input": {"paper_id": "10.1038/nature12373"},
                    "usage": "Get details for a paper using its DOI",
                },
                {
                    "description": "Get paper by ArXiv ID",
                    "input": {"paper_id": "arXiv:2106.15928"},
                    "usage": "Get details for a paper using its ArXiv ID",
                },
            ],
        },
        {
            "name": "get_authors",
            "description": "Get authors information for a specific paper",
            "input_schema": {
                "type": "object",
                "properties": {
                    "paper_id": {
                        "type": "string",
                        "description": "Paper ID to get authors for",
                    },
                    "fields": {
                        "type": "string",
                        "description": "Comma-separated list of author fields to return",
                        "default": "authorId,name,affiliations,citationCount,hIndex",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of authors to return",
                        "default": 100,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Starting position in the list of authors",
                        "default": 0,
                    },
                },
                "required": ["paper_id"],
            },
            "examples": [
                {
                    "description": "Get authors for a paper",
                    "input": {"paper_id": "649def34f8be52c8b66281af98ae884c09aef38b"},
                    "usage": "Get all authors and their details for a specific paper",
                },
            ],
        },
        {
            "name": "get_citation",
            "description": "Get citation information in various formats including BibTeX",
            "input_schema": {
                "type": "object",
                "properties": {
                    "paper_id": {
                        "type": "string",
                        "description": "Paper ID to get citation for",
                    },
                    "format": {
                        "type": "string",
                        "description": "Citation format: 'bibtex', 'apa', 'mla', or 'chicago'",
                        "default": "bibtex",
                    },
                },
                "required": ["paper_id"],
            },
            "examples": [
                {
                    "description": "Get BibTeX citation",
                    "input": {"paper_id": "649def34f8be52c8b66281af98ae884c09aef38b"},
                    "usage": "Generate BibTeX citation for the paper",
                },
                {
                    "description": "Get APA citation",
                    "input": {
                        "paper_id": "649def34f8be52c8b66281af98ae884c09aef38b",
                        "format": "apa",
                    },
                    "usage": "Generate APA format citation for the paper",
                },
            ],
        },
    ]

    if output_format == "json":
        import json

        click.echo(json.dumps(tools_data, indent=2))
    elif output_format == "table":
        click.echo("Available MCP Tools")
        click.echo("=" * 80)
        click.echo()

        for tool in tools_data:
            click.echo(f"🔧 {tool['name']}")
            click.echo(f"   {tool['description']}")
            click.echo()

            if verbose:
                # Input Schema
                click.echo("   📥 Input Schema:")
                props = tool["input_schema"].get("properties", {})
                required = tool["input_schema"].get("required", [])

                if props:
                    for param_name, param_info in props.items():
                        required_mark = (
                            " (required)" if param_name in required else " (optional)"
                        )
                        param_type = param_info.get("type", "unknown")
                        param_desc = param_info.get("description", "No description")
                        default = param_info.get("default")
                        default_text = (
                            f" [default: {default}]" if default is not None else ""
                        )

                        click.echo(
                            f"     • {param_name} ({param_type}){required_mark}: {param_desc}{default_text}"
                        )
                else:
                    click.echo("     No parameters required")
                click.echo()

                # Examples
                if "examples" in tool:
                    click.echo("   💡 Usage Examples:")
                    for i, example in enumerate(tool["examples"], 1):
                        click.echo(f"     {i}. {example['description']}")
                        click.echo(f"        Input: {example['input']}")
                        click.echo(f"        Usage: {example['usage']}")
                        if i < len(tool["examples"]):
                            click.echo()
                    click.echo()

            click.echo("-" * 80)
            click.echo()
    else:  # text format
        click.echo("Available MCP Tools:")
        click.echo()

        for tool in tools_data:
            click.echo(f"• {tool['name']}: {tool['description']}")

            if verbose:
                # Parameters
                props = tool["input_schema"].get("properties", {})
                required = tool["input_schema"].get("required", [])
                if props:
                    click.echo("  Parameters:")
                    for param_name, param_info in props.items():
                        required_mark = (
                            " (required)" if param_name in required else " (optional)"
                        )
                        param_desc = param_info.get("description", "No description")
                        default = param_info.get("default")
                        default_text = (
                            f" [default: {default}]" if default is not None else ""
                        )
                        click.echo(
                            f"    - {param_name}{required_mark}: {param_desc}{default_text}"
                        )

                # Examples
                if "examples" in tool:
                    click.echo("  Examples:")
                    for example in tool["examples"]:
                        click.echo(
                            f"    - {example['description']}: {example['usage']}"
                        )
                        click.echo(f"      Input: {example['input']}")

            click.echo()


def _get_server_instance(api_key: str | None = None) -> SemanticScholarServer:
    """Get a server instance for tool testing."""
    return SemanticScholarServer(api_key=api_key)


@tools.command("search_paper")
@click.argument("query", required=True)
@click.option(
    "--fields",
    default="paperId,title,abstract,authors,year,citationCount",
    help="Comma-separated list of fields to return",
)
@click.option(
    "--limit",
    type=int,
    default=10,
    help="Maximum number of results to return (max: 100)",
)
@click.option(
    "--offset",
    type=int,
    default=0,
    help="Starting position in the list of results",
)
@click.option(
    "--year",
    help="Publication year or range (e.g., '2019', '2016-2020')",
)
@click.option(
    "--fields-of-study",
    help="Comma-separated list of fields of study to filter by",
)
@click.option(
    "--open-access-pdf",
    is_flag=True,
    help="Filter to only include papers with open access PDFs",
)
@click.pass_context
def search_paper(
    ctx: click.Context,
    query: str,
    fields: str,
    limit: int,
    offset: int,
    year: str | None,
    fields_of_study: str | None,
    open_access_pdf: bool,
) -> None:
    """Search for papers using Semantic Scholar.

    QUERY: The search query string.
    """

    async def run_search() -> None:
        api_key = ctx.obj.get("api_key")
        server = _get_server_instance(api_key=api_key)
        args = {
            "query": query,
            "fields": fields,
            "limit": limit,
            "offset": offset,
        }
        if year:
            args["year"] = year
        if fields_of_study:
            args["fieldsOfStudy"] = fields_of_study
        if open_access_pdf:
            args["openAccessPdf"] = True

        results = await server._handle_search_paper(args)

        for result in results:
            click.echo(result.text)

    anyio.run(run_search)


@tools.command("get_paper")
@click.argument("paper_id", required=True)
@click.option(
    "--fields",
    default="paperId,title,abstract,authors,year,citationCount,referenceCount,fieldsOfStudy,publicationTypes,publicationDate,journal,openAccessPdf",
    help="Comma-separated list of fields to return",
)
@click.pass_context
def get_paper(ctx: click.Context, paper_id: str, fields: str) -> None:
    """Get detailed information about a specific paper.

    PAPER_ID: Paper ID (supports S2, DOI, ArXiv, MAG, ACL, PubMed, Corpus ID).
    """

    async def run_get_paper() -> None:
        api_key = ctx.obj.get("api_key")
        server = _get_server_instance(api_key=api_key)
        results = await server._handle_get_paper(
            {"paper_id": paper_id, "fields": fields}
        )

        for result in results:
            click.echo(result.text)

    anyio.run(run_get_paper)


@tools.command("get_authors")
@click.argument("paper_id", required=True)
@click.option(
    "--fields",
    default="authorId,name,affiliations,citationCount,hIndex",
    help="Comma-separated list of author fields to return",
)
@click.option(
    "--limit",
    type=int,
    default=100,
    help="Maximum number of authors to return",
)
@click.option(
    "--offset",
    type=int,
    default=0,
    help="Starting position in the list of authors",
)
@click.pass_context
def get_authors(
    ctx: click.Context, paper_id: str, fields: str, limit: int, offset: int
) -> None:
    """Get authors information for a specific paper.

    PAPER_ID: Paper ID to get authors for.
    """

    async def run_get_authors() -> None:
        api_key = ctx.obj.get("api_key")
        server = _get_server_instance(api_key=api_key)
        results = await server._handle_get_authors(
            {"paper_id": paper_id, "fields": fields, "limit": limit, "offset": offset}
        )

        for result in results:
            click.echo(result.text)

    anyio.run(run_get_authors)


@tools.command("get_citation")
@click.argument("paper_id", required=True)
@click.option(
    "--format",
    "citation_format",
    type=click.Choice(["bibtex", "apa", "mla", "chicago"]),
    default="bibtex",
    help="Citation format (default: bibtex)",
)
@click.pass_context
def get_citation(ctx: click.Context, paper_id: str, citation_format: str) -> None:
    """Get citation information in various formats.

    PAPER_ID: Paper ID to get citation for.
    """

    async def run_get_citation() -> None:
        api_key = ctx.obj.get("api_key")
        server = _get_server_instance(api_key=api_key)
        results = await server._handle_get_citation(
            {"paper_id": paper_id, "format": citation_format}
        )

        for result in results:
            click.echo(result.text)

    anyio.run(run_get_citation)


# Add the tools group to the main CLI
cli.add_command(tools)


def main() -> None:
    """Entry point for the CLI application."""
    cli()


if __name__ == "__main__":
    main()
