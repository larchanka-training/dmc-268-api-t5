variable "vps_host" {
  type        = string
  description = "Target VPS IP Address"
}

variable "vps_user" {
  type        = string
  description = "SSH User"
}

variable "vps_password" {
  type        = string
  description = "SSH Password"
  sensitive   = true
}

variable "app_domain" {
  type        = string
  default     = ""
  description = "Production domain (GitHub Variable APP_DOMAIN); staging lives on staging.<domain>. Empty means <ip-with-dashes>.sslip.io"
}
