"""Conflict resolution policies for edge/backend sync reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Strategy = Literal["client_wins", "server_wins", "latest_timestamp"]


@dataclass(frozen=True)
class ConflictDecision:
    """Decision output for one conflict pair."""

    winner: Literal["client", "server"]
    strategy: Strategy
    reason: str


def resolve_conflict(
    client_payload: dict[str, Any],
    server_payload: dict[str, Any],
    strategy: Strategy = "latest_timestamp",
) -> ConflictDecision:
    """Resolve record conflict according to selected strategy."""
    if strategy == "client_wins":
        return ConflictDecision(winner="client", strategy=strategy, reason="configured_client_wins")

    if strategy == "server_wins":
        return ConflictDecision(winner="server", strategy=strategy, reason="configured_server_wins")

    client_updated = str(client_payload.get("updated_at", client_payload.get("created_at", "")))
    server_updated = str(server_payload.get("updated_at", server_payload.get("created_at", "")))

    if client_updated >= server_updated:
        return ConflictDecision(winner="client", strategy=strategy, reason="client_is_latest")
    return ConflictDecision(winner="server", strategy=strategy, reason="server_is_latest")
