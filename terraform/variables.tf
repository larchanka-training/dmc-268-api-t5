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