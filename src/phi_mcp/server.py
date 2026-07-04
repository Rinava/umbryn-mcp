"""The MCP server: exposes redact / restore / detect over stdio.

This layer is deliberately thin. All the logic — and the fail-closed guarantee —
lives in :class:`~phi_mcp.redactor.Redactor`; the server just translates between
MCP tool calls and the core, mapping every :class:`~phi_mcp.errors.PhiRedactionError`
to an MCP tool error so the client sees ``isError`` and *never* a partial or
unredacted result.
"""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field

from phi_mcp.errors import PhiRedactionError
from phi_mcp.factory import build_redactor
from phi_mcp.redactor import Redactor
from phi_mcp.types import Entity

_INSTRUCTIONS = """\
phi-redact-mcp keeps PII/PHI out of anything downstream of this boundary.

- `redact` returns scrubbed text plus a `token_map`. Send only `redacted_text`
  to the model; keep `token_map` locally and NEVER pass it to the model — it
  contains the original sensitive values.
- `restore` rehydrates scrubbed text using that `token_map`.
- `detect` reports what would be found, without changing the text.

The boundary is fail-closed: if detection errors, or any detection lands below
the confidence threshold, the call returns an error instead of leaking data.
"""


class RedactedEntity(BaseModel):
    """Metadata about one redacted span (no raw value — that's in the token map)."""

    entity_type: str = Field(description="Canonical entity type, e.g. NPI or US_SSN")
    start: int = Field(description="Start offset in the original text")
    end: int = Field(description="End offset in the original text")
    score: float = Field(description="Detection confidence, 0-1")


class DetectedEntity(BaseModel):
    """One detected span, including the matched text (detect does not mutate)."""

    entity_type: str = Field(description="Canonical entity type, e.g. NPI or US_SSN")
    start: int
    end: int
    score: float = Field(description="Detection confidence, 0-1")
    text: str = Field(description="The matched substring")


class RedactResult(BaseModel):
    """Output of `redact`."""

    redacted_text: str = Field(description="Text with PHI/PII replaced by typed placeholders")
    token_map: dict[str, str] = Field(
        description="placeholder -> original value; keep local, do NOT send to the model"
    )
    entities: list[RedactedEntity] = Field(description="What was redacted, for auditing")


class DetectResult(BaseModel):
    """Output of `detect`."""

    entities: list[DetectedEntity]
    count: int = Field(description="Number of entities found")


class RestoreResult(BaseModel):
    """Output of `restore`."""

    text: str = Field(description="The rehydrated original text")


def _to_redacted(entity: Entity) -> RedactedEntity:
    return RedactedEntity(
        entity_type=entity.entity_type, start=entity.start, end=entity.end, score=entity.score
    )


def _to_detected(entity: Entity) -> DetectedEntity:
    return DetectedEntity(
        entity_type=entity.entity_type,
        start=entity.start,
        end=entity.end,
        score=entity.score,
        text=entity.text,
    )


def create_server(redactor: Redactor | None = None) -> FastMCP:
    """Build the FastMCP server. Inject a ``redactor`` in tests; otherwise one is
    built from the environment."""
    redactor = redactor or build_redactor()
    mcp = FastMCP("phi-redact", instructions=_INSTRUCTIONS)

    @mcp.tool(
        title="Redact PHI/PII",
        description="Replace PHI/PII in text with reversible typed placeholders.",
    )
    def redact(text: Annotated[str, Field(description="Text to scrub")]) -> RedactResult:
        try:
            result = redactor.redact(text)
        except PhiRedactionError as exc:
            raise ToolError(str(exc)) from exc
        return RedactResult(
            redacted_text=result.redacted_text,
            token_map=result.token_map,
            entities=[_to_redacted(e) for e in result.entities],
        )

    @mcp.tool(
        title="Restore redacted text",
        description="Reverse a redaction using its token map, recovering the original text.",
    )
    def restore(
        redacted_text: Annotated[str, Field(description="Text containing placeholders")],
        token_map: Annotated[dict[str, str], Field(description="placeholder -> original value")],
    ) -> RestoreResult:
        try:
            return RestoreResult(text=redactor.restore(redacted_text, token_map))
        except PhiRedactionError as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool(
        title="Detect PHI/PII",
        description="Report the PHI/PII entities found in text without modifying it.",
    )
    def detect(text: Annotated[str, Field(description="Text to inspect")]) -> DetectResult:
        try:
            result = redactor.detect(text)
        except PhiRedactionError as exc:
            raise ToolError(str(exc)) from exc
        return DetectResult(
            entities=[_to_detected(e) for e in result.entities],
            count=len(result.entities),
        )

    return mcp


def main() -> None:
    """Console-script entry point: run the server over stdio."""
    create_server().run()


if __name__ == "__main__":
    main()
