"""Storage transformer for Azure Storage Account configuration."""

import re
from typing import Any

from ..models.config import ContainerAccess, Environment, StorageTier
from ..models.terraform import StorageAccountTfVars, StorageContainerTfVars
from .base import BaseTransformer, TransformContext, UserRole


# Tier mappings
TIER_TO_ACCOUNT_TIER: dict[StorageTier, str] = {
    StorageTier.BASIC: "Standard",
    StorageTier.STANDARD: "Standard",
    StorageTier.PREMIUM: "Premium",
}

TIER_TO_REPLICATION: dict[StorageTier, dict[Environment, str]] = {
    StorageTier.BASIC: {
        Environment.DEV: "LRS",
        Environment.STAGING: "LRS",
        Environment.PRODUCTION: "LRS",
    },
    StorageTier.STANDARD: {
        Environment.DEV: "LRS",
        Environment.STAGING: "GRS",
        Environment.PRODUCTION: "RAGRS",
    },
    StorageTier.PREMIUM: {
        Environment.DEV: "LRS",
        Environment.STAGING: "ZRS",
        Environment.PRODUCTION: "ZRS",
    },
}

ACCESS_TO_TERRAFORM: dict[ContainerAccess, str] = {
    ContainerAccess.PRIVATE: "private",
    ContainerAccess.BLOB: "blob",
    ContainerAccess.CONTAINER: "container",
}


class StorageTransformer(BaseTransformer):
    """Transform storage config to Azure Storage Account Terraform variables."""

    def transform(self, ctx: TransformContext) -> dict[str, Any] | None:
        """Transform storage config to Terraform variables."""
        storage = ctx.config.storage
        if storage is None:
            return None

        # Map tier to account tier and replication
        account_tier = TIER_TO_ACCOUNT_TIER[storage.tier]
        replication = TIER_TO_REPLICATION[storage.tier][ctx.environment]

        # Premium tier uses BlockBlobStorage kind
        account_kind = "BlockBlobStorage" if storage.tier == StorageTier.PREMIUM else "StorageV2"

        # Generate resource name (sanitized, no hyphens for storage accounts)
        name = self._generate_name(ctx.project, ctx.environment.value)

        # Transform containers
        containers = [
            StorageContainerTfVars(
                name=c.name,
                container_access_type=ACCESS_TO_TERRAFORM[c.access],
            )
            for c in storage.containers
        ]

        tfvars = StorageAccountTfVars(
            name=name,
            resource_group_name=ctx.resource_group_name,
            location=ctx.region,
            account_tier=account_tier,
            account_replication_type=replication,
            account_kind=account_kind,
            containers=[c.model_dump() for c in containers],
            tags=ctx.get_tags(),
        )

        return tfvars.model_dump()

    def validate_policies(self, ctx: TransformContext) -> list[str]:
        """Validate storage policies."""
        errors: list[str] = []
        storage = ctx.config.storage

        if storage is None:
            return errors

        # Production should use standard+ tier
        if ctx.is_production and storage.tier == StorageTier.BASIC:
            errors.append("Production environment recommends 'standard' tier or higher for storage")

        # Premium tier requires elevated role
        if storage.tier == StorageTier.PREMIUM and ctx.role == UserRole.DEVELOPER:
            errors.append("Premium storage tier requires 'team_lead' or 'platform_admin' role")

        # Public containers in production require team_lead+
        if ctx.is_production:
            for container in storage.containers:
                if container.access != ContainerAccess.PRIVATE and ctx.role == UserRole.DEVELOPER:
                    errors.append(
                        f"Public container '{container.name}' in production requires "
                        "'team_lead' or 'platform_admin' role"
                    )

        return errors

    def _generate_name(self, project: str, environment: str) -> str:
        """Generate storage account name.

        Azure Storage Account names must be:
        - 3-24 characters
        - Lowercase letters and numbers only (no hyphens!)
        - Globally unique
        """
        # Remove hyphens and special chars, lowercase only
        clean_project = re.sub(r"[^a-z0-9]", "", project.lower())
        clean_env = re.sub(r"[^a-z0-9]", "", environment.lower())

        # Prefix with 'st' for storage
        name = f"st{clean_project}{clean_env}"

        # Truncate to max length
        return name[:24]
