"""Contract tests for the MCP tool surface.

These drive the tools through ``FastMCP.call_tool`` with a fake engine, asserting
the wire shapes and that fail-closed errors surface as MCP tool errors (never a
partial/unredacted result).
"""

from __future__ import annotations

import json
from typing import Any

import anyio
import pytest
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from phi_mcp import Redactor
from phi_mcp.server import create_server
from tests.fakes import FakeEngine, make_entities

TEXT = "ping 555-867-5309 now"


def _call(server: FastMCP, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Call a tool and return its structured result as a dict."""

    async def run() -> Any:
        return await server.call_tool(name, args)

    result = anyio.run(run)
    # call_tool may return a content list or a (content, structured) tuple.
    if isinstance(result, tuple):
        content, structured = result
        if structured is not None:
            return structured
        result = content
    return json.loads(result[0].text)


def _server(entities: list | None = None, exc: Exception | None = None) -> FastMCP:
    redactor = Redactor(FakeEngine(entities or [], exc=exc), detection_floor=0.1)
    return create_server(redactor)


def test_redact_returns_redacted_text_and_token_map() -> None:
    entities = make_entities(TEXT, ("PHONE_NUMBER", 5, 17, 0.95))
    out = _call(_server(entities), "redact", {"text": TEXT})
    assert out["redacted_text"] == "ping [PHONE_NUMBER_1] now"
    assert out["token_map"] == {"[PHONE_NUMBER_1]": "555-867-5309"}
    assert out["entities"][0]["entity_type"] == "PHONE_NUMBER"


def test_restore_reverses_redaction() -> None:
    entities = make_entities(TEXT, ("PHONE_NUMBER", 5, 17, 0.95))
    server = _server(entities)
    red = _call(server, "redact", {"text": TEXT})
    restored = _call(
        server, "restore", {"redacted_text": red["redacted_text"], "token_map": red["token_map"]}
    )
    assert restored["text"] == TEXT


def test_detect_reports_without_mutating() -> None:
    entities = make_entities(TEXT, ("PHONE_NUMBER", 5, 17, 0.30))  # uncertain
    out = _call(_server(entities), "detect", {"text": TEXT})
    # detect surfaces the uncertain hit rather than blocking.
    assert out["count"] == 1
    assert out["entities"][0]["text"] == "555-867-5309"


def test_redact_fails_closed_on_engine_error() -> None:
    server = _server(exc=RuntimeError("kaboom"))
    with pytest.raises(ToolError) as excinfo:
        _call(server, "redact", {"text": TEXT})
    assert "[DETECTION_ERROR]" in str(excinfo.value)


def test_redact_fails_closed_on_low_confidence() -> None:
    entities = make_entities(TEXT, ("PHONE_NUMBER", 5, 17, 0.40))
    server = _server(entities)  # detection_floor=0.1, min_confidence default 0.5
    with pytest.raises(ToolError) as excinfo:
        _call(server, "redact", {"text": TEXT})
    assert "[LOW_CONFIDENCE]" in str(excinfo.value)


def test_server_exposes_three_tools() -> None:
    async def list_tools() -> list[str]:
        tools = await create_server(Redactor(FakeEngine([]))).list_tools()
        return sorted(t.name for t in tools)

    assert anyio.run(list_tools) == ["detect", "redact", "restore"]
