import asyncio
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def list_tools_over_stdio():
    launcher = Path(__file__).parents[1] / "run.sh"
    params = StdioServerParameters(command=str(launcher), args=[])

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            response = await session.list_tools()
            return [tool.name for tool in response.tools]


def test_stdio_server_registers_brave_search_tool():
    assert asyncio.run(list_tools_over_stdio()) == ["brave_search"]
