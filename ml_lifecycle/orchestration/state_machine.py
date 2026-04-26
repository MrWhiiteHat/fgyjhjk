"""Lifecycle state machine for closed-loop ML operations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LifecycleStateMachine:
    """Enforces allowed transitions across lifecycle states."""

    state: str = "idle"

    _allowed_transitions = {
        "idle": {"monitoring"},
        "monitoring": {"drift_detected", "production"},
        "drift_detected": {"retraining", "monitoring"},
        "retraining": {"validation", "monitoring"},
        "validation": {"rollout", "monitoring"},
        "rollout": {"production", "monitoring"},
        "production": {"monitoring"},
    }

    def transition(self, next_state: str) -> str:
        """Transition to next state if allowed."""

        target = str(next_state).strip()
        allowed = self._allowed_transitions.get(self.state, set())
        if target not in allowed:
            raise ValueError(f"Invalid transition: {self.state} -> {target}")
        self.state = target
        return self.state
