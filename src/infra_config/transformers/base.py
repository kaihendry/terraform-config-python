"""Base transformer and context for config transformation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..models.config import Environment, InfraConfig


class UserRole(str, Enum):
    """User roles for policy enforcement."""

    DEVELOPER = "developer"
    TEAM_LEAD = "team_lead"
    PLATFORM_ADMIN = "platform_admin"


@dataclass
class TransformContext:
    """Context passed to transformers during transformation."""

    config: InfraConfig
    role: UserRole = UserRole.DEVELOPER

    @property
    def project(self) -> str:
        return self.config.project

    @property
    def environment(self) -> Environment:
        return self.config.environment

    @property
    def region(self) -> str:
        return self.config.region

    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    @property
    def resource_group_name(self) -> str:
        """Generate consistent resource group name."""
        return f"rg-{self.project}-{self.environment.value}"

    def get_tags(self) -> dict[str, str]:
        """Get merged tags with standard tags."""
        standard_tags = {
            "project": self.project,
            "environment": self.environment.value,
            "managed_by": "infra-config",
        }
        if self.config.owner:
            standard_tags["owner"] = self.config.owner
        if self.config.cost_center:
            standard_tags["cost_center"] = self.config.cost_center
        return {**standard_tags, **self.config.tags}


class BaseTransformer(ABC):
    """Base class for resource transformers."""

    @abstractmethod
    def transform(self, ctx: TransformContext) -> dict[str, Any] | None:
        """Transform user config to Terraform variables.

        Returns None if this resource type is not configured.
        """
        pass

    @abstractmethod
    def validate_policies(self, ctx: TransformContext) -> list[str]:
        """Validate policies and return list of error messages.

        Returns empty list if all policies pass.
        """
        pass
