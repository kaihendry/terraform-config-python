"""Unit tests for config transformation."""

import pytest

from infra_config.models import InfraConfig, DatabaseTier, StorageTier, Environment
from infra_config.transformers import TransformContext, DatabaseTransformer, StorageTransformer
from infra_config.transformers.base import UserRole


class TestDatabaseTransformer:
    """Tests for PostgreSQL database transformer."""

    def test_standard_tier_maps_to_correct_sku(self, transform_config):
        """Standard tier should map to GP_Standard_D2s_v3."""
        config = {
            "project": "myapp",
            "environment": "staging",
            "database": {"tier": "standard", "storage_gb": 64},
        }
        result = transform_config(config)

        assert result["postgresql"]["sku_name"] == "GP_Standard_D2s_v3"

    def test_starter_tier_maps_to_burstable_sku(self, transform_config):
        """Starter tier should map to B_Standard_B1ms."""
        config = {
            "project": "myapp",
            "environment": "dev",
            "database": {"tier": "starter", "storage_gb": 32},
        }
        result = transform_config(config)

        assert result["postgresql"]["sku_name"] == "B_Standard_B1ms"

    def test_premium_tier_maps_to_correct_sku(self, transform_config):
        """Premium tier should map to GP_Standard_D4s_v3."""
        config = {
            "project": "myapp",
            "environment": "production",
            "database": {"tier": "premium", "storage_gb": 128, "backup_retention_days": 14},
        }
        result = transform_config(config)

        assert result["postgresql"]["sku_name"] == "GP_Standard_D4s_v3"

    def test_enterprise_tier_maps_to_memory_optimized_sku(self, transform_config):
        """Enterprise tier should map to MO_Standard_E4s_v3."""
        config = {
            "project": "myapp",
            "environment": "production",
            "database": {"tier": "enterprise", "storage_gb": 256, "backup_retention_days": 14},
        }
        result = transform_config(config, role=UserRole.PLATFORM_ADMIN)

        assert result["postgresql"]["sku_name"] == "MO_Standard_E4s_v3"

    def test_production_enables_geo_redundant_backup(self, transform_config):
        """Production environment should enable geo-redundant backup."""
        config = {
            "project": "myapp",
            "environment": "production",
            "database": {"tier": "standard", "storage_gb": 64, "backup_retention_days": 14},
        }
        result = transform_config(config)

        assert result["postgresql"]["geo_redundant_backup_enabled"] is True

    def test_dev_disables_geo_redundant_backup(self, transform_config):
        """Dev environment should not enable geo-redundant backup."""
        config = {
            "project": "myapp",
            "environment": "dev",
            "database": {"tier": "standard", "storage_gb": 64},
        }
        result = transform_config(config)

        assert result["postgresql"]["geo_redundant_backup_enabled"] is False

    def test_high_availability_sets_zone_redundant_mode(self, transform_config):
        """High availability should set ZoneRedundant mode."""
        config = {
            "project": "myapp",
            "environment": "production",
            "database": {
                "tier": "standard",
                "storage_gb": 64,
                "high_availability": True,
                "backup_retention_days": 14,
            },
        }
        result = transform_config(config)

        assert result["postgresql"]["high_availability_mode"] == "ZoneRedundant"
        assert result["postgresql"]["zone"] == "1"

    def test_storage_gb_converted_to_mb(self, transform_config):
        """Storage should be converted from GB to MB."""
        config = {
            "project": "myapp",
            "environment": "dev",
            "database": {"tier": "starter", "storage_gb": 64},
        }
        result = transform_config(config)

        assert result["postgresql"]["storage_mb"] == 64 * 1024

    def test_resource_naming_convention(self, transform_config):
        """Resource names should follow convention."""
        config = {
            "project": "myapp",
            "environment": "staging",
            "database": {"tier": "standard"},
        }
        result = transform_config(config)

        assert result["postgresql"]["name"] == "psql-myapp-staging"
        assert result["postgresql"]["resource_group_name"] == "rg-myapp-staging"


class TestStorageTransformer:
    """Tests for Storage account transformer."""

    def test_standard_tier_production_uses_ragrs(self, transform_config):
        """Standard tier in production should use RAGRS replication."""
        config = {
            "project": "myapp",
            "environment": "production",
            "storage": {"tier": "standard"},
        }
        result = transform_config(config)

        assert result["storage"]["account_replication_type"] == "RAGRS"

    def test_standard_tier_dev_uses_lrs(self, transform_config):
        """Standard tier in dev should use LRS replication."""
        config = {
            "project": "myapp",
            "environment": "dev",
            "storage": {"tier": "standard"},
        }
        result = transform_config(config)

        assert result["storage"]["account_replication_type"] == "LRS"

    def test_basic_tier_uses_lrs(self, transform_config):
        """Basic tier should always use LRS."""
        for env in ["dev", "staging", "production"]:
            config = {
                "project": "myapp",
                "environment": env,
                "storage": {"tier": "basic"},
            }
            result = transform_config(config)
            assert result["storage"]["account_replication_type"] == "LRS"

    def test_premium_tier_uses_block_blob_storage(self, transform_config):
        """Premium tier should use BlockBlobStorage kind."""
        config = {
            "project": "myapp",
            "environment": "production",
            "storage": {"tier": "premium"},
        }
        result = transform_config(config, role=UserRole.PLATFORM_ADMIN)

        assert result["storage"]["account_kind"] == "BlockBlobStorage"

    def test_containers_transformed_correctly(self, transform_config):
        """Containers should be transformed with correct access types."""
        config = {
            "project": "myapp",
            "environment": "dev",
            "storage": {
                "tier": "standard",
                "containers": [
                    {"name": "uploads", "access": "private"},
                    {"name": "public-assets", "access": "blob"},
                ],
            },
        }
        result = transform_config(config)

        containers = result["storage"]["containers"]
        assert len(containers) == 2
        assert containers[0]["name"] == "uploads"
        assert containers[0]["container_access_type"] == "private"
        assert containers[1]["name"] == "public-assets"
        assert containers[1]["container_access_type"] == "blob"

    def test_storage_naming_no_hyphens(self, transform_config):
        """Storage account names should not contain hyphens."""
        config = {
            "project": "my-app",
            "environment": "production",
            "storage": {"tier": "standard"},
        }
        result = transform_config(config)

        assert "-" not in result["storage"]["name"]
        assert result["storage"]["name"] == "stmyappproduction"


class TestPolicyValidation:
    """Tests for policy validation."""

    def test_production_requires_standard_tier_for_database(self):
        """Production should reject starter tier for database."""
        config = InfraConfig.model_validate(
            {
                "project": "myapp",
                "environment": "production",
                "database": {"tier": "starter"},
            }
        )
        ctx = TransformContext(config=config, role=UserRole.DEVELOPER)
        transformer = DatabaseTransformer()

        errors = transformer.validate_policies(ctx)

        assert any("standard" in e.lower() for e in errors)

    def test_enterprise_tier_requires_elevated_role(self):
        """Enterprise tier should require team_lead or higher."""
        config = InfraConfig.model_validate(
            {
                "project": "myapp",
                "environment": "staging",
                "database": {"tier": "enterprise"},
            }
        )
        ctx = TransformContext(config=config, role=UserRole.DEVELOPER)
        transformer = DatabaseTransformer()

        errors = transformer.validate_policies(ctx)

        assert any("team_lead" in e.lower() or "platform_admin" in e.lower() for e in errors)

    def test_production_requires_minimum_backup_retention(self):
        """Production should require minimum 14 days backup retention."""
        config = InfraConfig.model_validate(
            {
                "project": "myapp",
                "environment": "production",
                "database": {"tier": "standard", "backup_retention_days": 7},
            }
        )
        ctx = TransformContext(config=config, role=UserRole.DEVELOPER)
        transformer = DatabaseTransformer()

        errors = transformer.validate_policies(ctx)

        assert any("14 days" in e for e in errors)


class TestTagging:
    """Tests for resource tagging."""

    def test_standard_tags_applied(self, transform_config):
        """Standard tags should be applied to all resources."""
        config = {
            "project": "myapp",
            "environment": "staging",
            "owner": "platform-team",
            "cost_center": "engineering",
            "database": {"tier": "standard"},
        }
        result = transform_config(config)

        tags = result["postgresql"]["tags"]
        assert tags["project"] == "myapp"
        assert tags["environment"] == "staging"
        assert tags["managed_by"] == "infra-config"
        assert tags["owner"] == "platform-team"
        assert tags["cost_center"] == "engineering"

    def test_custom_tags_merged(self, transform_config):
        """Custom tags should be merged with standard tags."""
        config = {
            "project": "myapp",
            "environment": "dev",
            "tags": {"service": "api", "team": "backend"},
            "storage": {"tier": "standard"},
        }
        result = transform_config(config)

        tags = result["storage"]["tags"]
        assert tags["service"] == "api"
        assert tags["team"] == "backend"
        assert tags["project"] == "myapp"  # Standard tag still present
