terraform {
  required_version = ">= 1.5.0"
  required_providers {
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

# Ресурс: подготовка Docker и подъем базового docker-контейнера на выданном VPS
resource "null_resource" "vps_bootstrap" {
  # Перезапускать триггер при смене IP
  triggers = {
    host = var.vps_host
  }

  connection {
    type     = "ssh"
    host     = var.vps_host
    user     = var.vps_user
    password = var.vps_password
    timeout  = "2m"
  }

  provisioner "remote-exec" {
    inline = [
      "echo '=== [Terraform] Проверка и установка базового окружения ==='",
      "if ! command -v docker > /dev/null 2>&1; then",
      "  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh",
      "  sh /tmp/get-docker.sh",
      "  systemctl enable --now docker",
      "fi",
      
      "echo '=== [Terraform] Создание базовой структуры каталогов ==='",
      "mkdir -p /opt/dmc-268/nginx",
      "chmod 755 /opt/dmc-268",

      "echo '=== [Terraform] Подъем базового docker-контейнера (DoD) ==='",
      "# Запуск базового reverse-proxy контейнера",
      "docker network inspect dmc-net >/dev/null 2>&1 || docker network create dmc-net",
      "docker stop dmc-base-bootstrap >/dev/null 2>&1 || true",
      "docker rm dmc-base-bootstrap >/dev/null 2>&1 || true",
      "docker run -d --name dmc-base-bootstrap --restart unless-stopped --network dmc-net -p 80:80 nginx:alpine",
      
      "echo '=== [Terraform] Базовый контейнер успешно запущен ==='",
      "docker ps --filter name=dmc-base-bootstrap"
    ]
  }
}