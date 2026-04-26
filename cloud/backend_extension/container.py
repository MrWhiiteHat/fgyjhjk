"""Dependency container for cloud platform services."""

from __future__ import annotations

from functools import lru_cache

from cloud.platform.api_gateway.api_keys import ApiKeyService
from cloud.platform.api_gateway.gateway import ApiGatewayService
from cloud.platform.api_gateway.idempotency import IdempotencyService
from cloud.platform.api_gateway.tenant_resolution import TenantResolver
from cloud.platform.config.settings import CloudSettings
from cloud.platform.enterprise.service import EnterpriseService
from cloud.platform.jobs.models import Job
from cloud.platform.jobs.queue import AsyncJobQueue
from cloud.platform.jobs.worker import JobWorker
from cloud.platform.metering.quota import QuotaService
from cloud.platform.metering.service import MeteringService
from cloud.platform.organizations.service import OrganizationWorkspaceService
from cloud.platform.reporting.service import ReportingService
from cloud.platform.storage.service import TenantStorageService
from cloud.platform.storage.signed_urls import SignedUrlService
from cloud.platform.tenancy.service import TenantService
from cloud.platform.authz.service import RbacService


class CloudPlatformContainer:
    """Centralized service registry for cloud module integration."""

    def __init__(self, settings: CloudSettings | None = None) -> None:
        self.settings = settings or CloudSettings.from_env()
        self.settings.ensure_directories()

        self.tenant_service = TenantService()
        self.organization_service = OrganizationWorkspaceService()
        self.rbac_service = RbacService()

        self.metering_service = MeteringService()
        self.quota_service = QuotaService(self.metering_service)

        self.job_queue = AsyncJobQueue()
        self.job_worker = JobWorker(
            queue=self.job_queue,
            handlers={"inference": self._inference_job_handler, "batch_report": self._batch_report_handler},
            poll_interval_seconds=self.settings.job_poll_interval_seconds,
        )

        signed_url_service = SignedUrlService(secret=self.settings.signed_url_secret)
        self.storage_service = TenantStorageService(storage_root=self.settings.storage_root, signed_url_service=signed_url_service)

        self.api_key_service = ApiKeyService(signing_secret=self.settings.webhook_signing_secret)
        self.tenant_resolver = TenantResolver(self.tenant_service, self.api_key_service)
        self.idempotency_service = IdempotencyService(ttl_seconds=self.settings.idempotency_ttl_seconds)
        self.gateway_service = ApiGatewayService(self.tenant_resolver, self.idempotency_service)

        self.enterprise_service = EnterpriseService()
        self.reporting_service = ReportingService(self.metering_service, self.job_queue)

    def start(self) -> None:
        """Start background worker resources."""

        self.job_worker.start()

    def stop(self) -> None:
        """Stop background worker resources."""

        self.job_worker.stop()

    @staticmethod
    def _inference_job_handler(job: Job) -> dict:
        payload = dict(job.payload)
        if payload.get("fail_once") and job.attempts == 1:
            raise RuntimeError("Simulated transient failure for retry validation")
        return {
            "job_id": job.job_id,
            "tenant_id": job.tenant_id,
            "status": "processed",
            "task": "inference",
            "input": payload,
        }

    @staticmethod
    def _batch_report_handler(job: Job) -> dict:
        return {
            "job_id": job.job_id,
            "tenant_id": job.tenant_id,
            "status": "processed",
            "task": "batch_report",
            "input": dict(job.payload),
        }


@lru_cache(maxsize=1)
def get_cloud_container() -> CloudPlatformContainer:
    """Return singleton cloud platform container."""

    container = CloudPlatformContainer()
    container.start()
    return container
