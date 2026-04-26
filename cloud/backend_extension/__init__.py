"""Backend integration entrypoints for cloud platform module."""

from cloud.backend_extension.container import CloudPlatformContainer, get_cloud_container
from cloud.backend_extension.router import cloud_router

__all__ = ["CloudPlatformContainer", "get_cloud_container", "cloud_router"]
