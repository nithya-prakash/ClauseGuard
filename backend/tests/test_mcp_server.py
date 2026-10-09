import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app import mcp_server as srv

BACKEND = Path(__file__).resolve().parents[1]


def test_search_returns_provenance_and_disclaimer():
    out = srv.search_legal_corpus("Haftung Vorsatz Ausschluss AGB", top_k=2)
    assert out["disclaimer"] and out["results"]
    assert all(r["source_url"].startswith("https://") and r["retrieved_at"] for r in out["results"])


def test_get_passage_known_and_unknown():
    assert srv.get_passage("BGB", "§ 307")["passage"]["section"] == "§ 307"
    assert "error" in srv.get_passage("BGB", "§ 99999")


def test_related_passages_uses_text_references():
    out = srv.related_passages("BGB", "§ 307")
    assert "§ 308" in {p["section"] for p in out["cites"]}
    assert "§ 307" in {p["section"] for p in srv.related_passages("BGB", "§ 310")["cites"]}


def test_stdio_protocol_lists_and_calls_tools():
    async def run():
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "app.mcp_server"], cwd=str(BACKEND)
        )
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            tools = {t.name for t in (await session.list_tools()).tools}
            result = await session.call_tool("get_passage", {"source": "BGB", "section": "§ 307"})
            return tools, result

    tools, result = asyncio.run(run())
    assert tools == {"get_scope", "search_legal_corpus", "get_passage", "related_passages"}
    assert not result.is_error and "§ 307" in str(result.content)
