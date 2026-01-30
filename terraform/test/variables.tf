# Common variables
variable "resource_group_name" {
  type    = string
  default = "rg-test"
}

variable "location" {
  type    = string
  default = "eastus"
}

variable "tags" {
  type    = map(string)
  default = {}
}

# PostgreSQL variables
variable "postgresql_enabled" {
  type    = bool
  default = false
}

variable "postgresql_name" {
  type    = string
  default = ""
}

variable "postgresql_sku_name" {
  type    = string
  default = "GP_Standard_D2s_v3"
}

variable "postgresql_storage_mb" {
  type    = number
  default = 65536
}

variable "postgresql_version" {
  type    = string
  default = "16"
}

variable "postgresql_administrator_login" {
  type    = string
  default = "pgadmin"
}

variable "postgresql_backup_retention_days" {
  type    = number
  default = 7
}

variable "postgresql_geo_redundant_backup_enabled" {
  type    = bool
  default = false
}

variable "postgresql_high_availability_mode" {
  type    = string
  default = "Disabled"
}

variable "postgresql_zone" {
  type    = string
  default = null
}

variable "postgresql_database_name" {
  type    = string
  default = "app"
}

# Storage variables
variable "storage_enabled" {
  type    = bool
  default = false
}

variable "storage_name" {
  type    = string
  default = ""
}

variable "storage_account_tier" {
  type    = string
  default = "Standard"
}

variable "storage_account_replication_type" {
  type    = string
  default = "LRS"
}

variable "storage_account_kind" {
  type    = string
  default = "StorageV2"
}

variable "storage_access_tier" {
  type    = string
  default = "Hot"
}

variable "storage_enable_https_traffic_only" {
  type    = bool
  default = true
}

variable "storage_min_tls_version" {
  type    = string
  default = "TLS1_2"
}

variable "storage_containers" {
  type = list(object({
    name                  = string
    container_access_type = string
  }))
  default = []
}
