"""A/B traffic assignment and experiment metrics helpers."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass
class ABAssignment:
    """A/B assignment result for an incoming request."""

    request_id: str
    bucket: str


class ABTesting:
    """Deterministic traffic splitter for control and candidate models."""

    def assign(self, *, request_id: str, control_ratio: float = 0.5) -> ABAssignment:
        """Assign request to control or candidate bucket deterministically."""

        control = min(max(float(control_ratio), 0.0), 1.0)
        digest = hashlib.sha256(str(request_id).encode("utf-8")).hexdigest()
        value = int(digest[:8], 16) / float(0xFFFFFFFF)
        bucket = "control" if value < control else "candidate"
        return ABAssignment(request_id=str(request_id), bucket=bucket)

    def summarize(self, assignments: list[ABAssignment]) -> dict[str, int]:
        """Summarize assignment counts by bucket."""

        summary = {"control": 0, "candidate": 0}
        for assignment in assignments:
            summary[assignment.bucket] = summary.get(assignment.bucket, 0) + 1
        return summary
