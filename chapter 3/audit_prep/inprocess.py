"""Run an ``mcp`` server application inside the host process.

The Agents SDK talks to MCP servers through an abstract ``MCPServer`` class.
This adapter implements it by calling an ``mcp.server.mcpserver.MCPServer``
application directly, with no transport in between. The tool definitions, the
argument validation, and the result shapes are the real ones; only the wire is
missing. It is what lets the audit-prep agent run end to end without a key and
without three terminals, and it is a reasonable way to unit test a server.
"""

from __future__ import annotations

from typing import Any

from agents import RunContextWrapper
from agents.agent import AgentBase
from agents.mcp import MCPServer
from mcp.server.mcpserver import MCPServer as MCPApp
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import (
    CallToolResult,
    GetPromptResult,
    ListPromptsResult,
    TextContent,
    Tool as MCPTool,
)


class InProcessMCPServer(MCPServer):
    """An SDK-facing MCP server backed by an in-process ``mcp`` application."""

    def __init__(self, app: MCPApp, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._app = app

    @property
    def name(self) -> str:
        return self._app.name

    async def connect(self) -> None:
        """Nothing to open; the application is already in memory."""

    async def cleanup(self) -> None:
        """Nothing to close."""

    async def __aenter__(self) -> InProcessMCPServer:
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.cleanup()

    async def list_tools(
        self,
        run_context: RunContextWrapper[Any] | None = None,
        agent: AgentBase | None = None,
    ) -> list[MCPTool]:
        return await self._app.list_tools()

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None,
        meta: dict[str, Any] | None = None,
    ) -> CallToolResult:
        try:
            result = await self._app.call_tool(tool_name, arguments or {})
        except ToolError as exc:
            return CallToolResult(
                content=[TextContent(type="text", text=str(exc))], is_error=True
            )
        if not isinstance(result, CallToolResult):
            raise TypeError(f"{tool_name} asked for client input, which this host does not support")
        return result

    async def list_prompts(self) -> ListPromptsResult:
        return ListPromptsResult(prompts=await self._app.list_prompts())

    async def get_prompt(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> GetPromptResult:
        result = await self._app.get_prompt(name, arguments)
        if not isinstance(result, GetPromptResult):
            raise TypeError(f"prompt {name} asked for client input, which this host does not support")
        return result
