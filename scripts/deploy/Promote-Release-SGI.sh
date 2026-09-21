#!/usr/bin/env bash
set -Eeuo pipefail

BASE="/opt/apps/inventario"
PORTA_PROD="3001"
PROJECT_PROD="sgi_prod"

if [ "$#" -ne 1 ]; then
    echo "Uso: $0 <release>"
    exit 2
fi

NEW_RELEASE="$1"
NEW_DIR="$BASE/_releases/$NEW_RELEASE"

if [ ! -f "$BASE/ACTIVE_RELEASE" ]; then
    echo "[ERRO] ACTIVE_RELEASE nao encontrado."
    exit 3
fi

OLD_RELEASE="$(tr -d '\r\n' < "$BASE/ACTIVE_RELEASE")"
OLD_DIR="$BASE/_releases/$OLD_RELEASE"

echo "=============================================="
echo "SGI - PROMOCAO DE RELEASE"
echo "=============================================="
echo "Atual : $OLD_RELEASE"
echo "Nova  : $NEW_RELEASE"
echo ""

if [ "$NEW_RELEASE" = "$OLD_RELEASE" ]; then
    echo "[ERRO] A release informada ja esta ativa."
    exit 4
fi

test -d "$OLD_DIR" || {
    echo "[ERRO] Release atual nao encontrada: $OLD_DIR"
    exit 5
}

test -d "$NEW_DIR" || {
    echo "[ERRO] Nova release nao encontrada: $NEW_DIR"
    exit 6
}

test -f "$OLD_DIR/.env.production" || {
    echo "[ERRO] .env.production da release atual nao encontrado."
    exit 7
}

if [ ! -f "$NEW_DIR/.env.production" ]; then
    cp "$OLD_DIR/.env.production" "$NEW_DIR/.env.production"
    chmod 600 "$NEW_DIR/.env.production"
    echo "[OK] .env.production preparado"
fi

echo ""
echo "[1/7] Validando producao atual"

HTTP_ATUAL="$(curl -sS -o /dev/null -w '%{http_code}' \
    "http://127.0.0.1:${PORTA_PROD}/" || true)"

if [ "$HTTP_ATUAL" != "200" ]; then
    echo "[ERRO] Producao atual respondeu HTTP $HTTP_ATUAL"
    exit 8
fi

echo "[OK] Producao atual HTTP 200"

echo ""
echo "[2/7] Construindo nova release"

cd "$NEW_DIR"

docker compose -p "$PROJECT_PROD" build

echo "[OK] Build concluido"

echo ""
echo "[3/7] Protegendo imagens atuais"

OLD_BACKEND_IMAGE="$(docker inspect -f '{{.Image}}' sgi_backend)"
OLD_FRONTEND_IMAGE="$(docker inspect -f '{{.Image}}' sgi_frontend)"

docker tag "$OLD_BACKEND_IMAGE" \
    "sgi-rollback-backend:${OLD_RELEASE}"

docker tag "$OLD_FRONTEND_IMAGE" \
    "sgi-rollback-frontend:${OLD_RELEASE}"

ROLLBACK_DIR="$BASE/_rollback/$OLD_RELEASE"
mkdir -p "$ROLLBACK_DIR"

cat > "$ROLLBACK_DIR/docker-compose.rollback.yml" <<EOF
services:
  backend:
    image: sgi-rollback-backend:${OLD_RELEASE}

  frontend:
    image: sgi-rollback-frontend:${OLD_RELEASE}
EOF

echo "[OK] Rollback armado"

rollback() {
    echo ""
    echo "=============================================="
    echo "ROLLBACK AUTOMATICO"
    echo "=============================================="

    docker rm -f \
        sgi_gateway \
        sgi_frontend \
        sgi_backend \
        >/dev/null 2>&1 || true

    cd "$OLD_DIR"

    docker compose \
        -p "$PROJECT_PROD" \
        -f docker-compose.yml \
        -f "$ROLLBACK_DIR/docker-compose.rollback.yml" \
        up -d --no-build

    sleep 8

    HTTP_ROLLBACK="$(curl -sS -o /dev/null -w '%{http_code}' \
        "http://127.0.0.1:${PORTA_PROD}/" || true)"

    if [ "$HTTP_ROLLBACK" = "200" ]; then
        echo "[OK] Rollback restaurado - HTTP 200"
    else
        echo "[CRITICO] Rollback respondeu HTTP $HTTP_ROLLBACK"
    fi

    exit 20
}

trap rollback ERR

echo ""
echo "[4/7] Substituindo containers de producao"

docker rm -f \
    sgi_gateway \
    sgi_frontend \
    sgi_backend

cd "$NEW_DIR"

docker compose \
    -p "$PROJECT_PROD" \
    up -d --no-build

sleep 8

echo "[OK] Nova release iniciada"

echo ""
echo "[5/7] Smoke test HTTP"

HTTP_FRONT="$(curl -sS -o /dev/null -w '%{http_code}' \
    "http://127.0.0.1:${PORTA_PROD}/")"

HTTP_API="$(curl -sS -o /dev/null -w '%{http_code}' \
    "http://127.0.0.1:${PORTA_PROD}/api/openapi.json")"

echo "Frontend: HTTP $HTTP_FRONT"
echo "API.....: HTTP $HTTP_API"

test "$HTTP_FRONT" = "200"
test "$HTTP_API" = "200"

echo ""
echo "[6/7] Smoke test SQL"

docker exec -i sgi_backend python - <<'PY'
import os
import pyodbc

server = os.environ["DB_SERVER"]
database = os.environ["DB_DATABASE"]
user = os.environ["DB_USER"]
password = os.environ["DB_PASSWORD"]
driver = os.environ.get(
    "DB_DRIVER",
    "ODBC Driver 18 for SQL Server"
)

conn_str = (
    f"DRIVER={{{driver}}};"
    f"SERVER={server};"
    f"DATABASE={database};"
    f"UID={user};"
    f"PWD={password};"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)

with pyodbc.connect(conn_str, timeout=10) as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT 1")
    valor = cursor.fetchone()[0]

print(f"[OK] SQL SELECT 1 = {valor}")
PY

echo ""
echo "[7/7] Registrando nova release"

printf '%s\n' "$OLD_RELEASE" > "$BASE/PREVIOUS_RELEASE"
printf '%s\n' "$NEW_RELEASE" > "$BASE/ACTIVE_RELEASE"

ln -sfn "$NEW_DIR" "$BASE/current"

trap - ERR

echo ""
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' |
    grep -E 'NAMES|sgi_gateway|sgi_backend|sgi_frontend|app_gestor_frota'

echo ""
echo "=============================================="
echo "PROMOCAO: APROVADA"
echo "RELEASE ATIVA: $NEW_RELEASE"
echo "RELEASE ANTERIOR: $OLD_RELEASE"
echo "=============================================="
