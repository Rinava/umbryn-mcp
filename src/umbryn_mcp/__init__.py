"""umbryn-mcp — a fail-closed PHI/PII redaction MCP server.

The public surface is intentionally small and free of any MCP or Presidio
imports so the detection core can be embedded anywhere (a proxy, a batch job,
another server). See :class:`umbryn_mcp.redactor.Redactor`.
"""

from __future__ import annotations

from umbryn_mcp.errors import (
    DetectionError,
    InputTooLargeError,
    InvalidInputError,
    LowConfidenceError,
    PhiRedactionError,
    RestoreError,
)
from umbryn_mcp.redactor import Redactor
from umbryn_mcp.types import DetectionResult, Entity, RedactionResult

__all__ = [
    "DetectionError",
    "DetectionResult",
    "Entity",
    "InputTooLargeError",
    "InvalidInputError",
    "LowConfidenceError",
    "PhiRedactionError",
    "RedactionResult",
    "Redactor",
    "RestoreError",
]

__version__ = "0.2.0"
