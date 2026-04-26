"""Model version generation and navigation utilities."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True, order=True)
class SemanticVersion:
    """Comparable semantic version representation."""

    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


class VersionManager:
    """Manages model version allocation and ordering."""

    def __init__(self) -> None:
        self._versions: list[SemanticVersion] = []
        self._lock = RLock()

    def parse(self, version: str) -> SemanticVersion:
        """Parse semantic version string into structured representation."""

        raw = str(version).strip()
        parts = raw.split(".")
        if len(parts) != 3 or not all(item.isdigit() for item in parts):
            raise ValueError(f"Invalid semantic version: {version}")
        return SemanticVersion(int(parts[0]), int(parts[1]), int(parts[2]))

    def register_existing(self, version: str) -> None:
        """Record existing version in manager state."""

        parsed = self.parse(version)
        with self._lock:
            if parsed not in self._versions:
                self._versions.append(parsed)
                self._versions.sort()

    def next_version(self) -> str:
        """Generate next patch version from latest known version."""

        with self._lock:
            if not self._versions:
                candidate = SemanticVersion(1, 0, 0)
            else:
                latest = self._versions[-1]
                candidate = SemanticVersion(latest.major, latest.minor, latest.patch + 1)
            self._versions.append(candidate)
            self._versions.sort()
            return str(candidate)

    def latest_version(self) -> str | None:
        """Return latest known version string if available."""

        with self._lock:
            if not self._versions:
                return None
            return str(self._versions[-1])

    def previous_version(self, current_version: str) -> str | None:
        """Return previous version relative to current version."""

        target = self.parse(current_version)
        with self._lock:
            ordered = sorted(self._versions)
            try:
                idx = ordered.index(target)
            except ValueError:
                return None
            if idx <= 0:
                return None
            return str(ordered[idx - 1])
