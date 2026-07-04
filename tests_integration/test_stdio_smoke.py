"""End-to-end transport smoke test.

Launches the real ``phi-redact-mcp`` server as a subprocess and drives it through
a real MCP client over stdio: initialize, list tools, redact, restore. This is
the only test that exercises the actual wire protocol and process entry point, so
it lives in the slow suite, out of the fast red-green loop.

Run with:  pytest tests_integration
"""

from __future__ import annotations

import shutil

import anyio
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

pytestmark = pytest.mark.skipif(
    shutil.which("phi-redact-mcp") is None,
    reason="phi-redact-mcp console script not installed (pip install -e .)",
)

TEXT = "Contact john.doe@example.com; NPI 1234567893."


def _structured(result: object) -> dict:
    # CallToolResult exposes structuredContent for typed tool outputs.
    return getattr(result, "structuredContent", None) or {}


def test_stdio_roundtrip_over_real_transport() -> None:
    async def scenario() -> None:
        params = StdioServerParameters(
            command="phi-redact-mcp",
            env={"PHI_MCP_ENGINE": "regex"},  # pin the dependency-free engine
        )
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()

            tools = await session.list_tools()
            assert sorted(t.name for t in tools.tools) == ["detect", "redact", "restore"]

            redacted = await session.call_tool("redact", {"text": TEXT})
            assert redacted.isError is False
            data = _structured(redacted)
            assert "[EMAIL_ADDRESS_1]" in data["redacted_text"]
            assert "[NPI_1]" in data["redacted_text"]

            restored = await session.call_tool(
                "restore",
                {"redacted_text": data["redacted_text"], "token_map": data["token_map"]},
            )
            assert _structured(restored)["text"] == TEXT

    anyio.run(scenario)
