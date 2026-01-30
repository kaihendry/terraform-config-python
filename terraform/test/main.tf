terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

# Mock provider - skip actual Azure auth for planning
provider "azurerm" {
  features {}
  skip_provider_registration = true

  # These prevent actual Azure API calls during plan
  # Set to dummy values for testing
  subscription_id = "00000000-0000-0000-0000-000000000000"
  tenant_id       = "00000000-0000-0000-0000-000000000000"
}

# Resource group (would exist in real deployment)
data "azurerm_resource_group" "main" {
  count = 0  # Skip data source lookup in test
  name  = var.resource_group_name
}

# PostgreSQL module
module "postgresql" {
  count  = var.postgresql_enabled ? 1 : 0
  source = "../modules/postgresql"

  name                         = var.postgresql_name
  resource_group_name          = var.resource_group_name
  location                     = var.location
  sku_name                     = var.postgresql_sku_name
  storage_mb                   = var.postgresql_storage_mb
  postgresql_version           = var.postgresql_version
  administrator_login          = var.postgresql_administrator_login
  backup_retention_days        = var.postgresql_backup_retention_days
  geo_redundant_backup_enabled = var.postgresql_geo_redundant_backup_enabled
  high_availability_mode       = var.postgresql_high_availability_mode
  zone                         = var.postgresql_zone
  database_name                = var.postgresql_database_name
  tags                         = var.tags
}

# Storage module
module "storage" {
  count  = var.storage_enabled ? 1 : 0
  source = "../modules/storage"

  name                      = var.storage_name
  resource_group_name       = var.resource_group_name
  location                  = var.location
  account_tier              = var.storage_account_tier
  account_replication_type  = var.storage_account_replication_type
  account_kind              = var.storage_account_kind
  access_tier               = var.storage_access_tier
  enable_https_traffic_only = var.storage_enable_https_traffic_only
  min_tls_version           = var.storage_min_tls_version
  containers                = var.storage_containers
  tags                      = var.tags
}
