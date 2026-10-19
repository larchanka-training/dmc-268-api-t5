output "status" {
  value = "Окружение развернуто на ${var.vps_host}"
}

output "production_url" {
  value = "https://${local.domain}"
}

output "staging_url" {
  value = "https://staging.${local.domain}"
}
