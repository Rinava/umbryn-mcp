"""The detection-engine seam.

:class:`Redactor` depends only on this :class:`DetectionEngine` protocol, never
on Presidio directly. That keeps three things easy:

* **Testing** — the fast invariant suite injects a trivial fake engine, so those
  tests exercise *orchestration* (fail-closed, round-trip, overlaps), not a heavy
  third-party library.
* **Swapping** — Presidio is one implementation; a future transformer- or
  cloud-free ruleset is another.
* **Embedding** — a proxy/gateway (see the roadmap) can reuse the core with any
  engine.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from phi_mcp.types import Entity


@runtime_checkable
class DetectionEngine(Protocol):
    """Anything that can find PHI/PII spans in text.

    Implementations MUST be deterministic for a given input and configuration,
    and MUST NOT perform any third-party network egress at detection time.
    """

    def detect(self, text: str) -> list[Entity]:
        """Return every candidate entity found in ``text``.

        Offsets are into ``text``. Implementations should return *candidates*
        (everything at or above a low detection floor) and leave the trust
        decision to the :class:`Redactor`, so that low-confidence hits can block
        rather than being silently dropped.
        """
        ...
