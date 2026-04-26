"""Runtime compatibility helpers for backend process startup."""

from __future__ import annotations

import os
import platform
from typing import Any


_PATCH_APPLIED = False


def apply_windows_torch_platform_patch(logger: Any | None = None) -> None:
    """Avoid Python 3.14 Windows WMI hangs triggered during torch import.

    Newer Python platform helpers may call WMI to resolve system metadata,
    which can stall indefinitely on some Windows systems. Torch import relies
    on platform.system()/platform.machine() during DLL initialization.
    This patch short-circuits those lookups to stable values.
    """
    global _PATCH_APPLIED
    if _PATCH_APPLIED:
        return

    if os.name != "nt":
        return

    arch = str(os.environ.get("PROCESSOR_ARCHITECTURE", "AMD64") or "AMD64").upper()

    def _safe_system() -> str:
        return "Windows"

    def _safe_machine() -> str:
        return arch

    platform.system = _safe_system  # type: ignore[assignment]
    platform.machine = _safe_machine  # type: ignore[assignment]
    _PATCH_APPLIED = True

    if logger is not None:
        try:
            logger.info("Applied Windows torch platform compatibility patch")
        except Exception:
            pass
