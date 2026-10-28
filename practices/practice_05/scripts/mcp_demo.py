"""Реальный вызов MCP diff-guard по stdio: корректный diff и ошибочный вход."""

import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

GOOD = ('--- a/app/settings.py\n+++ b/app/settings.py\n@@ -1,2 +1,3 @@\n import os\n'
        '+API_KEY = "sk-live-0123456789abcdef"\n DEBUG = False\n')
CASES = [("корректный diff с секретом", GOOD),
         ("пустой diff", ""),
         ("не diff", "просто текст"),
         ("слишком большой", "+++ b/x\n@@ -1 +1 @@\n" + "+" * 20_001)]


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server.diff_guard"])
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        print("tools:", [t.name for t in tools.tools])
        for title, diff in CASES:
            result = await session.call_tool("inspect_diff", {"diff": diff})
            text = result.content[0].text if result.content else ""
            if not result.is_error:
                data = json.loads(text)
                text = json.dumps({k: data[k] for k in ("chars", "files", "secrets")},
                                  ensure_ascii=False)
            print(f"\n== {title}: isError={result.is_error}\n{text}")


if __name__ == "__main__":
    asyncio.run(main())
