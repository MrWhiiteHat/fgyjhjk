"""Emergency disable and rollback helper controls."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EmergencyState:
    """Runtime emergency disable state snapshot."""

    explainability_disabled: bool = False
    video_endpoint_disabled: bool = False
    bulk_inference_disabled: bool = False
    blocked_model_versions: set[str] = field(default_factory=set)


class EmergencyDisableController:
    """Provides immediate feature/model disable controls for incident response."""

    def __init__(self) -> None:
        self._state = EmergencyState()

    def disable_explainability(self) -> EmergencyState:
        """Disable explainability endpoint output."""

        self._state.explainability_disabled = True
        return self.snapshot()

    def disable_video_endpoint(self) -> EmergencyState:
        """Disable video inference endpoint."""

        self._state.video_endpoint_disabled = True
        return self.snapshot()

    def disable_bulk_inference(self) -> EmergencyState:
        """Disable bulk inference endpoint."""

        self._state.bulk_inference_disabled = True
        return self.snapshot()

    def block_model_version(self, model_version: str) -> EmergencyState:
        """Block a suspect model version immediately."""

        self._state.blocked_model_versions.add(str(model_version).strip())
        return self.snapshot()

    def clear(self) -> EmergencyState:
        """Reset emergency disable state."""

        self._state = EmergencyState()
        return self.snapshot()

    def snapshot(self) -> EmergencyState:
        """Return copy-like state snapshot."""

        return EmergencyState(
            explainability_disabled=self._state.explainability_disabled,
            video_endpoint_disabled=self._state.video_endpoint_disabled,
            bulk_inference_disabled=self._state.bulk_inference_disabled,
            blocked_model_versions=set(self._state.blocked_model_versions),
        )
