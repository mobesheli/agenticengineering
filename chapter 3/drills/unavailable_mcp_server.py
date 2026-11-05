"""Failure drill three: the MCP server is not there.

    python -m drills.unavailable_mcp_server

Nothing is listening on port 8765, so entering the server's ``async with``
block fails before any agent exists and before any model call. The error names
the server, which is what you want to read at two in the morning. If you have
the finance evidence server running, stop it first, or the drill will connect.
"""

from __future__ import annotations

import asyncio

from agents.exceptions import UserError
from agents.mcp import MCPServerStreamableHttp

SERVER_URL = "http://127.0.0.1:8765/mcp"


async def main() -> None:
    model_calls = 0
    try:
        async with MCPServerStreamableHttp(
            name="finance-evidence",
            params={"url": SERVER_URL},
        ) as evidence_server:
            tools = await evidence_server.list_tools()
            print(f"unexpected: connected and found {len(tools)} tool(s); stop the server and rerun")
            return
    except UserError as exc:
        message = str(exc)
        server, _, reason = message.partition(": ")
        print(f"error  : {server}")
        print(f"reason : {reason or message} ({SERVER_URL})")
    print(f"model calls made: {model_calls}")


if __name__ == "__main__":
    asyncio.run(main())
