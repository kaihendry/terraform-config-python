"""Integration tests that verify terraform plan output.

These tests require Azure credentials to run terraform plan.
Without credentials, tests will be skipped.
"""

import pytest


@pytest.mark.integration
@pytest.mark.azure
class TestTerraformPlan:
    """Integration tests that run actual terraform plan.

    These tests require Azure credentials. Set ARM_CLIENT_ID, ARM_CLIENT_SECRET,
    ARM_SUBSCRIPTION_ID, and ARM_TENANT_ID environment variables, or login via
    `az login` to run these tests.
    """

    def test_postgresql_resources_in_plan(self, transform_config, terraform_plan):
        """Terraform plan should include PostgreSQL resources."""
        config = {
            "project": "testapp",
            "environment": "dev",
            "database": {"tier": "standard", "storage_gb": 64},
        }
        tfvars = transform_config(config)
        plan = terraform_plan(tfvars)

        # Extract planned resources
        resource_changes = plan.get("resource_changes", [])
        resource_types = [r["type"] for r in resource_changes if r["change"]["actions"] != ["no-op"]]

        assert "azurerm_postgresql_flexible_server" in resource_types
        assert "azurerm_postgresql_flexible_server_database" in resource_types
        assert "random_password" in resource_types

    def test_storage_resources_in_plan(self, transform_config, terraform_plan):
        """Terraform plan should include Storage resources."""
        config = {
            "project": "testapp",
            "environment": "dev",
            "storage": {
                "tier": "standard",
                "containers": [{"name": "uploads", "access": "private"}],
            },
        }
        tfvars = transform_config(config)
        plan = terraform_plan(tfvars)

        resource_changes = plan.get("resource_changes", [])
        resource_types = [r["type"] for r in resource_changes if r["change"]["actions"] != ["no-op"]]

        assert "azurerm_storage_account" in resource_types
        assert "azurerm_storage_container" in resource_types

    def test_postgresql_sku_in_plan(self, transform_config, terraform_plan):
        """Terraform plan should have correct SKU for PostgreSQL."""
        config = {
            "project": "testapp",
            "environment": "staging",
            "database": {"tier": "premium", "storage_gb": 128},
        }
        tfvars = transform_config(config)
        plan = terraform_plan(tfvars)

        # Find PostgreSQL server in plan
        pg_server = next(
            (r for r in plan.get("resource_changes", [])
             if r["type"] == "azurerm_postgresql_flexible_server"),
            None
        )

        assert pg_server is not None
        planned_values = pg_server["change"]["after"]
        assert planned_values["sku_name"] == "GP_Standard_D4s_v3"

    def test_storage_replication_in_plan(self, transform_config, terraform_plan):
        """Terraform plan should have correct replication for Storage."""
        config = {
            "project": "testapp",
            "environment": "production",
            "storage": {"tier": "standard"},
        }
        tfvars = transform_config(config)
        plan = terraform_plan(tfvars)

        # Find Storage account in plan
        storage = next(
            (r for r in plan.get("resource_changes", [])
             if r["type"] == "azurerm_storage_account"),
            None
        )

        assert storage is not None
        planned_values = storage["change"]["after"]
        assert planned_values["account_replication_type"] == "RAGRS"

    def test_full_stack_plan(self, transform_config, terraform_plan):
        """Terraform plan for full stack (database + storage)."""
        config = {
            "project": "fullapp",
            "environment": "production",
            "region": "westus2",
            "database": {
                "tier": "standard",
                "storage_gb": 128,
                "high_availability": True,
                "backup_retention_days": 14,
            },
            "storage": {
                "tier": "standard",
                "containers": [
                    {"name": "uploads", "access": "private"},
                ],
            },
            "owner": "backend-team",
        }
        tfvars = transform_config(config)
        plan = terraform_plan(tfvars)

        resource_changes = plan.get("resource_changes", [])
        resource_types = {r["type"] for r in resource_changes if r["change"]["actions"] != ["no-op"]}

        # Should have both PostgreSQL and Storage resources
        assert "azurerm_postgresql_flexible_server" in resource_types
        assert "azurerm_postgresql_flexible_server_database" in resource_types
        assert "azurerm_storage_account" in resource_types
        assert "azurerm_storage_container" in resource_types


@pytest.mark.integration
class TestTerraformValidate:
    """Tests that verify terraform configuration validity.

    These tests run terraform validate which doesn't require Azure credentials.
    """

    def test_terraform_modules_are_valid(self, terraform_validate, transform_config):
        """Terraform modules should pass validation."""
        config = {
            "project": "testapp",
            "environment": "dev",
            "database": {"tier": "standard", "storage_gb": 64},
            "storage": {
                "tier": "standard",
                "containers": [{"name": "uploads", "access": "private"}],
            },
        }
        tfvars = transform_config(config)
        valid, error = terraform_validate(tfvars)

        assert valid, f"Terraform validation failed: {error}"
