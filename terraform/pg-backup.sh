#!/bin/sh
# Ежедневный бэкап Postgres (ставит Terraform: terraform/pg-backup.sh -> /usr/local/bin/dmc-pg-backup).
# Дампит каждую БД dmc_* (pg_dump -Fc) и роли (pg_dumpall --globals-only), хранит KEEP_DAYS дней.
set -eu
umask 077

DIR=/var/backups/dmc-postgres
KEEP_DAYS=14

mkdir -p "$DIR"
CID=$(docker ps -q --filter label=com.docker.swarm.service.name=dmc-postgres | head -n 1)
[ -n "$CID" ] || { echo "$(date -Is) ОШИБКА: dmc-postgres не запущен" >&2; exit 1; }

TS=$(date +%Y%m%d-%H%M%S)
for DB in $(docker exec "$CID" psql -U postgres -tAc "SELECT datname FROM pg_database WHERE datname LIKE 'dmc\_%'"); do
  OUT="$DIR/${DB}-${TS}.dump"
  docker exec "$CID" pg_dump -U postgres -Fc "$DB" > "$OUT.tmp"
  mv "$OUT.tmp" "$OUT"
  echo "$(date -Is) $OUT ($(du -h "$OUT" | cut -f1))"
done
docker exec "$CID" pg_dumpall -U postgres --globals-only > "$DIR/globals-${TS}.sql"

find "$DIR" -type f -mtime +"$KEEP_DAYS" -delete
