"""Model registry with versioning, promotion, rollback, and audit trail."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from threading import RLock

from ml_lifecycle.registry.artifact_store import ArtifactStore
from ml_lifecycle.registry.version_manager import VersionManager


@dataclass
class ModelRecord:
    """Registered model version metadata."""

    model_version: str
    training_dataset_id: str
    metrics: dict[str, float]
    created_at: str
    status: str
    artifact_uri: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class RegistryEvent:
    """Audit event for model lifecycle actions."""

    action: str
    model_version: str
    timestamp: str
    details: dict[str, str] = field(default_factory=dict)


class ModelRegistry:
    """In-memory registry with artifact-backed metadata persistence."""

    STATUS_STAGING = "staging"
    STATUS_PRODUCTION = "production"
    STATUS_ARCHIVED = "archived"

    def __init__(self, artifact_store: ArtifactStore | None = None, version_manager: VersionManager | None = None) -> None:
        self._artifact_store = artifact_store or ArtifactStore()
        self._version_manager = version_manager or VersionManager()
        self._records: dict[str, ModelRecord] = {}
        self._production_version: str | None = None
        self._events: list[RegistryEvent] = []
        self._lock = RLock()

    def register_model(
        self,
        *,
        training_dataset_id: str,
        metrics: dict[str, float],
        created_at: str,
        payload: bytes,
        metadata: dict[str, str] | None = None,
        model_version: str | None = None,
    ) -> ModelRecord:
        """Register model metadata and artifact under staging status."""

        with self._lock:
            version = str(model_version).strip() if model_version else self._version_manager.next_version()
            if version in self._records:
                raise ValueError(f"Model version already exists: {version}")
            self._version_manager.register_existing(version)

            artifact_uri = self._artifact_store.put_artifact(
                model_version=version,
                payload=payload,
                metadata={"training_dataset_id": training_dataset_id},
            )
            record = ModelRecord(
                model_version=version,
                training_dataset_id=str(training_dataset_id),
                metrics={k: float(v) for k, v in metrics.items()},
                created_at=str(created_at),
                status=self.STATUS_STAGING,
                artifact_uri=artifact_uri,
                metadata=dict(metadata or {}),
            )
            self._records[version] = record
            self._events.append(
                RegistryEvent(
                    action="register",
                    model_version=version,
                    timestamp=created_at,
                    details={"status": self.STATUS_STAGING},
                )
            )
            return record

    def promote_model(self, *, model_version: str, promoted_at: str, validation_passed: bool) -> ModelRecord:
        """Promote validated staging model to production."""

        if not validation_passed:
            raise ValueError("Cannot promote unvalidated model")

        with self._lock:
            record = self._get_record_or_raise(model_version)
            if record.status == self.STATUS_ARCHIVED:
                raise ValueError("Archived model cannot be promoted")

            previous_production = self._production_version
            if previous_production and previous_production != model_version:
                previous_record = self._records[previous_production]
                self._records[previous_production] = ModelRecord(**{**asdict(previous_record), "status": self.STATUS_ARCHIVED})
                self._events.append(
                    RegistryEvent(
                        action="archive",
                        model_version=previous_production,
                        timestamp=promoted_at,
                        details={"reason": "promoted_new_model"},
                    )
                )

            updated = ModelRecord(**{**asdict(record), "status": self.STATUS_PRODUCTION})
            self._records[model_version] = updated
            self._production_version = model_version
            self._events.append(
                RegistryEvent(
                    action="promote",
                    model_version=model_version,
                    timestamp=promoted_at,
                    details={"previous_production": previous_production or "none"},
                )
            )
            return updated

    def rollback_model(self, *, rollback_at: str, target_version: str | None = None) -> ModelRecord:
        """Rollback production pointer to previous stable or explicit target model version."""

        with self._lock:
            if not self._records:
                raise ValueError("No models available for rollback")

            if target_version is None:
                if not self._production_version:
                    raise ValueError("No production model set")
                candidate = self._version_manager.previous_version(self._production_version)
                if not candidate:
                    raise ValueError("No previous model version available for rollback")
                target_version = candidate

            target = self._get_record_or_raise(target_version)
            if target.status == self.STATUS_ARCHIVED:
                target = ModelRecord(**{**asdict(target), "status": self.STATUS_STAGING})
                self._records[target_version] = target

            previous_production = self._production_version
            if previous_production and previous_production in self._records and previous_production != target_version:
                previous = self._records[previous_production]
                self._records[previous_production] = ModelRecord(**{**asdict(previous), "status": self.STATUS_ARCHIVED})

            self._records[target_version] = ModelRecord(**{**asdict(target), "status": self.STATUS_PRODUCTION})
            self._production_version = target_version

            self._events.append(
                RegistryEvent(
                    action="rollback",
                    model_version=target_version,
                    timestamp=rollback_at,
                    details={"from_version": previous_production or "none"},
                )
            )
            return self._records[target_version]

    def get_model(self, model_version: str) -> ModelRecord:
        """Get model metadata by version."""

        with self._lock:
            return self._get_record_or_raise(model_version)

    def get_production_model(self) -> ModelRecord | None:
        """Return current production model if available."""

        with self._lock:
            if not self._production_version:
                return None
            return self._records[self._production_version]

    def list_models(self) -> list[ModelRecord]:
        """List all model records ordered by semantic version."""

        with self._lock:
            versions = sorted(self._records.keys(), key=self._version_manager.parse)
            return [self._records[version] for version in versions]

    def audit_log(self) -> list[RegistryEvent]:
        """Return immutable audit event snapshot."""

        with self._lock:
            return list(self._events)

    def _get_record_or_raise(self, model_version: str) -> ModelRecord:
        version = str(model_version).strip()
        if version not in self._records:
            raise KeyError(f"Unknown model version: {version}")
        return self._records[version]
