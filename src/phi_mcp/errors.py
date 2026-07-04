"""Typed errors for the redaction boundary.

Every failure the server can raise is a :class:`PhiRedactionError` with a stable
machine-readable ``code``. The ``code`` is embedded in ``str(err)`` so it survives
transports (such as MCP) that flatten an exception down to its message string, and
downstream code can branch on it without string-matching prose.

The cardinal rule: **on any error, no redacted text is returned.** These errors
*are* the fail-closed guarantee — raising one blocks the request.
"""

from __future__ import annotations

from typing import Any


class PhiRedactionError(Exception):
    """Base class for every fail-closed error raised by the redaction boundary."""

    #: Stable, machine-readable error code. Overridden by subclasses.
    code: str = "PHI_REDACTION_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if code is not None:
            self.code = code
        self.details: dict[str, Any] = details or {}
        # Embed the code so a stringified error (e.g. through an MCP tool error)
        # still carries the typed signal: "[LOW_CONFIDENCE] ...".
        super().__init__(f"[{self.code}] {message}")
        self.message = message


class DetectionError(PhiRedactionError):
    """The detection engine raised or returned something malformed.

    We treat this as *unknown risk* and block, rather than passing the text
    through unredacted.
    """

    code = "DETECTION_ERROR"


class LowConfidenceError(PhiRedactionError):
    """At least one entity was detected below the trust threshold.

    This is the sharp edge of the thesis: an *uncertain* detection is not
    redacted-and-forgotten, it blocks the whole request. Uncertainty blocks.
    """

    code = "LOW_CONFIDENCE"


class InputTooLargeError(PhiRedactionError):
    """Input exceeded the configured size limit."""

    code = "INPUT_TOO_LARGE"


class InvalidInputError(PhiRedactionError):
    """Input was malformed (wrong type, invalid token map, etc.)."""

    code = "INVALID_INPUT"


class RestoreError(PhiRedactionError):
    """A token map could not be applied consistently during restore."""

    code = "RESTORE_ERROR"
