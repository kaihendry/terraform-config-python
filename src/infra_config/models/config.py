"""User-facing Pydantic models for infrastructure configuration."""

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


class Environment(str, Enum):
    """Deployment environment."""

    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"


class DatabaseTier(str, Enum):
    """Database performance tier."""

    STARTER = "starter"
    STANDARD = "standard"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class StorageTier(str, Enum):
    """Storage performance tier."""

    BASIC = "basic"
    STANDARD = "standard"
    PREMIUM = "premium"


class ContainerAccess(str, Enum):
    """Storage container access level."""

    PRIVATE = "private"
    BLOB = "blob"
    CONTAINER = "container"


class ContainerConfig(BaseModel):
    """Configuration for a storage container."""

    name: Annotated[str, Field(min_length=3, max_length=63, pattern=r"^[a-z0-9-]+$")]
    access: ContainerAccess = ContainerAccess.PRIVATE


class DatabaseConfig(BaseModel):
    """Database configuration."""

    tier: DatabaseTier = DatabaseTier.STANDARD
    storage_gb: Annotated[int, Field(ge=32, le=16384)] = 64
    version: Annotated[str, Field(pattern=r"^(11|12|13|14|15|16)$")] = "16"
    high_availability: bool = False
    backup_retention_days: Annotated[int, Field(ge=7, le=35)] = 7


class StorageConfig(BaseModel):
    """Storage configuration."""

    tier: StorageTier = StorageTier.STANDARD
    containers: list[ContainerConfig] = Field(default_factory=list)


class InfraConfig(BaseModel):
    """Root infrastructure configuration model."""

    project: Annotated[str, Field(min_length=1, max_length=20, pattern=r"^[a-z][a-z0-9-]*$")]
    environment: Environment
    region: str = "eastus"

    database: DatabaseConfig | None = None
    storage: StorageConfig | None = None

    owner: str | None = None
    cost_center: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)

    @field_validator("region")
    @classmethod
    def validate_region(cls, v: str) -> str:
        """Validate Azure region."""
        valid_regions = {
            "eastus",
            "eastus2",
            "westus",
            "westus2",
            "westus3",
            "centralus",
            "northeurope",
            "westeurope",
            "uksouth",
            "ukwest",
            "southeastasia",
            "eastasia",
            "australiaeast",
            "australiasoutheast",
        }
        if v.lower() not in valid_regions:
            raise ValueError(f"Invalid region: {v}. Valid regions: {sorted(valid_regions)}")
        return v.lower()
