terraform {
  required_version = ">= 1.5.0"
  required_providers {
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

locals {
  # Без своего домена используем sslip.io: 1-2-3-4.sslip.io резолвится в 1.2.3.4
  domain    = var.app_domain != "" ? var.app_domain : "${replace(var.vps_host, ".", "-")}.sslip.io"
  caddyfile = templatefile("${path.module}/Caddyfile.tftpl", { domain = local.domain })
}

# Ресурс: подготовка Docker, Redis, Swarm и reverse proxy (Caddy) на выданном VPS
resource "null_resource" "vps_bootstrap" {
  # Перезапускать при смене IP, домена или конфигурации Caddy
  triggers = {
    host      = var.vps_host
    caddyfile = sha256(local.caddyfile)
    pg_backup = filesha256("${path.module}/pg-backup.sh")
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
      "mkdir -p /opt/dmc-268/caddy",
      "chmod 755 /opt/dmc-268",
    ]
  }

  provisioner "file" {
    content     = local.caddyfile
    destination = "/opt/dmc-268/caddy/Caddyfile"
  }

  provisioner "file" {
    source      = "${path.module}/pg-backup.sh"
    destination = "/opt/dmc-268/pg-backup.sh"
  }

  provisioner "remote-exec" {
    inline = [
      "set -e",
      "echo '=== [Terraform] Ожидание освобождения apt/dpkg (свежий VPS ставит обновления) ==='",
      "for i in $(seq 1 120); do pgrep -x 'apt|apt-get|dpkg|unattended-upgr' >/dev/null || break; sleep 5; done",
      "echo '=== [Terraform] Проверка и установка базового окружения ==='",
      "if ! command -v docker > /dev/null 2>&1; then",
      "  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh",
      "  sh /tmp/get-docker.sh",
      "  systemctl enable --now docker",
      "fi",

      "echo '=== [Terraform] Firewall (ufw): входящие только SSH, 80, 443 ==='",
      "command -v ufw >/dev/null 2>&1 || { apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ufw; }",
      "SSH_PORT=$(sshd -T 2>/dev/null | awk '/^port /{print $2; exit}'); SSH_PORT=$${SSH_PORT:-22}",
      "# SSH разрешаем до включения ufw, иначе можно потерять доступ к серверу",
      "ufw allow \"$SSH_PORT/tcp\" comment 'ssh'",
      "[ \"$SSH_PORT\" = 22 ] || ufw allow 22/tcp comment 'ssh-default'",
      "ufw allow 80/tcp comment 'caddy http'",
      "ufw allow 443/tcp comment 'caddy https'",
      "ufw allow 443/udp comment 'caddy http3'",
      "ufw default deny incoming",
      "ufw default allow outgoing",
      "ufw --force enable",
      "ufw status verbose",

      "echo '=== [Terraform] Сеть dmc-net (Redis, UI, Caddy) ==='",
      "docker network inspect dmc-net >/dev/null 2>&1 || docker network create dmc-net",

      "echo '=== [Terraform] Swarm (один узел, только 127.0.0.1) и overlay-сеть для API/worker/Postgres ==='",
      "[ \"$(docker info --format '{{.Swarm.LocalNodeState}}')\" = active ] || docker swarm init --advertise-addr 127.0.0.1 --listen-addr 127.0.0.1:2377",
      "docker network inspect dmc-overlay >/dev/null 2>&1 || docker network create -d overlay --attachable dmc-overlay",

      "echo '=== [Terraform] Redis (общий для staging/prod, БД 0 и 1, наружу не публикуется) ==='",
      "docker volume inspect dmc-redisdata >/dev/null 2>&1 || docker volume create dmc-redisdata",
      "docker inspect dmc-redis >/dev/null 2>&1 || docker run -d --name dmc-redis --restart unless-stopped --network dmc-net -v dmc-redisdata:/data --health-cmd 'redis-cli ping' --health-interval 5s redis:7-alpine redis-server --appendonly yes",
      "docker start dmc-redis >/dev/null 2>&1 || true",
      "docker network connect dmc-overlay dmc-redis >/dev/null 2>&1 || true",

      "echo '=== [Terraform] Volume для Postgres (сервис создает deploy, пароль из swarm secret) ==='",
      "docker volume inspect dmc-pgdata >/dev/null 2>&1 || docker volume create dmc-pgdata",

      "echo '=== [Terraform] Бэкап Postgres: ежедневно в 03:30, /var/backups/dmc-postgres, 14 дней ==='",
      "install -m 0750 /opt/dmc-268/pg-backup.sh /usr/local/bin/dmc-pg-backup",
      "printf 'SHELL=/bin/sh\\nPATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\\n30 3 * * * root /usr/local/bin/dmc-pg-backup >> /var/log/dmc-pg-backup.log 2>&1\\n' > /etc/cron.d/dmc-pg-backup",
      "chmod 0644 /etc/cron.d/dmc-pg-backup",

      "echo '=== [Terraform] Caddy: reverse proxy и TLS (сертификаты Lets Encrypt) на 80/443 ==='",
      "docker rm -f dmc-base-bootstrap >/dev/null 2>&1 || true",
      "if docker inspect dmc-caddy >/dev/null 2>&1; then",
      "  docker start dmc-caddy >/dev/null 2>&1 || true",
      "  docker exec dmc-caddy caddy reload --config /etc/caddy/Caddyfile",
      "else",
      "  docker run -d --name dmc-caddy --restart unless-stopped --network dmc-net -p 80:80 -p 443:443 -p 443:443/udp -v /opt/dmc-268/caddy:/etc/caddy:ro -v dmc-caddydata:/data -v dmc-caddyconfig:/config caddy:2-alpine",
      "fi",
      "docker network connect dmc-overlay dmc-caddy >/dev/null 2>&1 || true",

      "echo '=== [Terraform] Проверка: порты docker -p обходят ufw, наружу публикует только Caddy ==='",
      "EXTRA=$(docker ps --format '{{.Names}} {{.Ports}}' | grep -v '^dmc-caddy ' | grep -- '->' || true)",
      "[ -z \"$EXTRA\" ] || { echo 'ВНИМАНИЕ: контейнеры публикуют порты в обход ufw (уберутся следующим деплоем API/UI):'; echo \"$EXTRA\"; }",

      "echo '=== [Terraform] Окружение готово ==='",
      "docker ps --filter name=dmc-"
    ]
  }
}
