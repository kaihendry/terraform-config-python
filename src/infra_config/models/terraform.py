"""Terraform output models for Azure resources."""

from pydantic import BaseModel, Field


class PostgreSQLTfVars(BaseModel):
    """Terraform variables for Azure PostgreSQL Flexible Server."""

    name: str
    resource_group_name: str
    location: str
    sku_name: str
    storage_mb: int
    postgresql_version: str
    administrator_login: str = "pgadmin"
    backup_retention_days: int = Field(ge=7, le=35)
    geo_redundant_backup_enabled: bool = False
    high_availability_mode: str = "Disabled"
    zone: str | None = None
    database_name: str = "app"
    tags: dict[str, str] = Field(default_factory=dict)


class StorageContainerTfVars(BaseModel):
    """Terraform variables for a storage container."""

    name: str
    container_access_type: str  # "private", "blob", or "container"


class StorageAccountTfVars(BaseModel):
    """Terraform variables for Azure Storage Account."""

    name: str
    resource_group_name: str
    location: str
    account_tier: str  # "Standard" or "Premium"
    account_replication_type: str  # "LRS", "GRS", "RAGRS", "ZRS", "GZRS", "RAGZRS"
    account_kind: str = "StorageV2"
    access_tier: str = "Hot"  # "Hot" or "Cool"
    enable_https_traffic_only: bool = True
    min_tls_version: str = "TLS1_2"
    containers: list[StorageContainerTfVars] = Field(default_factory=list)
    tags: dict[str, str] = Field(default_factory=dict)
