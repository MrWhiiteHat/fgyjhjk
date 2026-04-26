"""Adapters for SSO and SCIM integration status reporting."""

from __future__ import annotations


class SsoConfigurationAdapter:
    """Documents SSO integration contract for enterprise environments."""

    @staticmethod
    def integration_status() -> dict[str, str | bool]:
        """Return current SSO implementation readiness."""

        return {
            "implemented": False,
            "status": "documented_not_implemented",
            "notes": "SAML/OIDC IdP wiring must be integrated with enterprise IAM.",
        }


class ScimProvisioningAdapter:
    """Documents SCIM provisioning integration contract."""

    @staticmethod
    def integration_status() -> dict[str, str | bool]:
        """Return current SCIM implementation readiness."""

        return {
            "implemented": False,
            "status": "documented_not_implemented",
            "notes": "SCIM 2.0 user/group provisioning endpoints are reserved for enterprise rollout.",
        }
