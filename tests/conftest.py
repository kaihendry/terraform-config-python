"""Pytest configuration and fixtures."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from infra_config.models import InfraConfig
from infra_config.transformers import (
    DatabaseTransformer,
    StorageTransformer,
    TransformContext,
)
from infra_config.transformers.base import UserRole


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: marks tests requiring terraform")
    config.addinivalue_line("markers", "azure: marks tests requiring Azure credentials")


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def terraform_test_dir(project_root: Path) -> Path:
    """Return the terraform test directory."""
    return project_root / "terraform" / "test"


@pytest.fixture
def transform_config():
    """Factory fixture to transform a config dict to tfvars."""

    def _transform(config_dict: dict, role: UserRole = UserRole.TEAM_LEAD) -> dict:
        config = InfraConfig.model_validate(config_dict)
        ctx = TransformContext(config=config, role=role)

        result = {}
        if config.database:
            db_transformer = DatabaseTransformer()
            result["postgresql"] = db_transformer.transform(ctx)
        if config.storage:
            storage_transformer = StorageTransformer()
            result["storage"] = storage_transformer.transform(ctx)

        return result

    return _transform


@pytest.fixture
def terraform_validate(terraform_test_dir: Path):
    """Factory fixture to run terraform validate and return success/errors."""

    def _validate(tfvars: dict) -> tuple[bool, str]:
        # Initialize terraform if needed
        init_result = subprocess.run(
            ["terraform", "init", "-backend=false", "-input=false"],
            cwd=terraform_test_dir,
            capture_output=True,
            text=True,
        )
        if init_result.returncode != 0:
            return False, init_result.stderr

        # Convert our tfvars format to test module format
        test_tfvars = _convert_to_test_tfvars(tfvars)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tfvars.json", delete=False
        ) as f:
            json.dump(test_tfvars, f)
            tfvars_file = f.name

        try:
            # Run terraform validate
            result = subprocess.run(
                ["terraform", "validate", "-json"],
                cwd=terraform_test_dir,
                capture_output=True,
                text=True,
                env={**os.environ, "TF_VAR_FILE": tfvars_file},
            )

            output = json.loads(result.stdout) if result.stdout else {}
            valid = output.get("valid", False)
            error_msg = ""
            if not valid:
                diagnostics = output.get("diagnostics", [])
                error_msg = "\n".join(d.get("summary", "") for d in diagnostics)

            return valid, error_msg
        finally:
            Path(tfvars_file).unlink(missing_ok=True)

    return _validate


def has_azure_credentials() -> bool:
    """Check if Azure credentials are available for terraform plan tests.

    Requires explicit opt-in via RUN_AZURE_TESTS=1 environment variable
    plus valid Azure credentials (ARM_* vars or az login).
    """
    # Require explicit opt-in
    if not os.environ.get("RUN_AZURE_TESTS"):
        return False

    # Check for service principal credentials
    if os.environ.get("ARM_CLIENT_ID") and os.environ.get("ARM_SUBSCRIPTION_ID"):
        return True

    # Check if az cli is logged in
    if subprocess.run(["which", "az"], capture_output=True).returncode == 0:
        result = subprocess.run(["az", "account", "show"], capture_output=True)
        return result.returncode == 0

    return False


@pytest.fixture
def terraform_plan(terraform_test_dir: Path):
    """Factory fixture to run terraform plan and return parsed JSON output.

    Requires Azure credentials to be configured.
    """

    def _plan(tfvars: dict) -> dict:
        if not has_azure_credentials():
            pytest.skip("Azure credentials not configured")

        # Initialize terraform if needed
        subprocess.run(
            ["terraform", "init", "-backend=false", "-input=false"],
            cwd=terraform_test_dir,
            capture_output=True,
            check=True,
        )

        # Convert our tfvars format to test module format
        test_tfvars = _convert_to_test_tfvars(tfvars)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tfvars.json", delete=False
        ) as f:
            json.dump(test_tfvars, f)
            tfvars_file = f.name

        try:
            # Run terraform plan with JSON output
            result = subprocess.run(
                [
                    "terraform",
                    "plan",
                    f"-var-file={tfvars_file}",
                    "-out=tfplan",
                    "-input=false",
                ],
                cwd=terraform_test_dir,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                pytest.fail(f"Terraform plan failed: {result.stderr}")

            # Get JSON representation of the plan
            show_result = subprocess.run(
                ["terraform", "show", "-json", "tfplan"],
                cwd=terraform_test_dir,
                capture_output=True,
                text=True,
                check=True,
            )

            return json.loads(show_result.stdout)
        finally:
            Path(tfvars_file).unlink(missing_ok=True)
            (terraform_test_dir / "tfplan").unlink(missing_ok=True)

    return _plan


def _convert_to_test_tfvars(tfvars: dict) -> dict:
    """Convert our generated tfvars to test module variable format."""
    result = {}

    if "postgresql" in tfvars and tfvars["postgresql"]:
        pg = tfvars["postgresql"]
        result.update(
            {
                "postgresql_enabled": True,
                "resource_group_name": pg["resource_group_name"],
                "location": pg["location"],
                "postgresql_name": pg["name"],
                "postgresql_sku_name": pg["sku_name"],
                "postgresql_storage_mb": pg["storage_mb"],
                "postgresql_version": pg["postgresql_version"],
                "postgresql_administrator_login": pg["administrator_login"],
                "postgresql_backup_retention_days": pg["backup_retention_days"],
                "postgresql_geo_redundant_backup_enabled": pg["geo_redundant_backup_enabled"],
                "postgresql_high_availability_mode": pg["high_availability_mode"],
                "postgresql_zone": pg["zone"],
                "postgresql_database_name": pg["database_name"],
                "tags": pg["tags"],
            }
        )

    if "storage" in tfvars and tfvars["storage"]:
        st = tfvars["storage"]
        result.update(
            {
                "storage_enabled": True,
                "resource_group_name": st["resource_group_name"],
                "location": st["location"],
                "storage_name": st["name"],
                "storage_account_tier": st["account_tier"],
                "storage_account_replication_type": st["account_replication_type"],
                "storage_account_kind": st["account_kind"],
                "storage_access_tier": st["access_tier"],
                "storage_enable_https_traffic_only": st["enable_https_traffic_only"],
                "storage_min_tls_version": st["min_tls_version"],
                "storage_containers": st["containers"],
                "tags": st["tags"],
            }
        )

    return result
