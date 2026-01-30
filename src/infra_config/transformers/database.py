"""Database transformer for PostgreSQL configuration."""

import re
from typing import Any

from ..models.config import DatabaseTier, Environment
from ..models.terraform import PostgreSQLTfVars
from .base import BaseTransformer, TransformContext, UserRole


# Tier to Azure PostgreSQL SKU mapping
TIER_TO_SKU: dict[DatabaseTier, str] = {
    DatabaseTier.STARTER: "B_Standard_B1ms",
    DatabaseTier.STANDARD: "GP_Standard_D2s_v3",
    DatabaseTier.PREMIUM: "GP_Standard_D4s_v3",
    DatabaseTier.ENTERPRISE: "MO_Standard_E4s_v3",
}


class DatabaseTransformer(BaseTransformer):
    """Transform database config to PostgreSQL Terraform variables."""

    def transform(self, ctx: TransformContext) -> dict[str, Any] | None:
        """Transform database config to Terraform variables."""
        db = ctx.config.database
        if db is None:
            return None

        # Map tier to SKU
        sku_name = TIER_TO_SKU[db.tier]

        # Environment-aware geo-backup (production gets geo-redundant by default)
        geo_redundant = ctx.is_production and db.tier != DatabaseTier.STARTER

        # High availability mode
        ha_mode = "ZoneRedundant" if db.high_availability else "Disabled"

        # Generate resource name (sanitized)
        name = self._generate_name(ctx.project, ctx.environment.value)

        tfvars = PostgreSQLTfVars(
            name=name,
            resource_group_name=ctx.resource_group_name,
            location=ctx.region,
            sku_name=sku_name,
            storage_mb=db.storage_gb * 1024,
            postgresql_version=db.version,
            backup_retention_days=db.backup_retention_days,
            geo_redundant_backup_enabled=geo_redundant,
            high_availability_mode=ha_mode,
            zone="1" if db.high_availability else None,
            tags=ctx.get_tags(),
        )

        return tfvars.model_dump()

    def validate_policies(self, ctx: TransformContext) -> list[str]:
        """Validate database policies."""
        errors: list[str] = []
        db = ctx.config.database

        if db is None:
            return errors

        # Production requires standard+ tier
        if ctx.is_production and db.tier == DatabaseTier.STARTER:
            errors.append("Production environment requires 'standard' tier or higher for database")

        # Enterprise tier requires elevated role
        if db.tier == DatabaseTier.ENTERPRISE and ctx.role == UserRole.DEVELOPER:
            errors.append("Enterprise tier requires 'team_lead' or 'platform_admin' role")

        # High availability requires standard+ tier
        if db.high_availability and db.tier == DatabaseTier.STARTER:
            errors.append("High availability requires 'standard' tier or higher")

        # Production should have minimum backup retention
        if ctx.is_production and db.backup_retention_days < 14:
            errors.append("Production environment requires minimum 14 days backup retention")

        return errors

    def _generate_name(self, project: str, environment: str) -> str:
        """Generate PostgreSQL server name.

        Azure PostgreSQL names must be:
        - 3-63 characters
        - Lowercase letters, numbers, and hyphens
        - Start with a letter
        """
        name = f"psql-{project}-{environment}"
        # Sanitize: lowercase, replace invalid chars with hyphen
        name = re.sub(r"[^a-z0-9-]", "-", name.lower())
        # Ensure starts with letter
        if not name[0].isalpha():
            name = "psql-" + name
        # Truncate to max length
        return name[:63]
