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

OLD_RELEASE="$(cat "$BASE/ACTIVE_RELEASE")"
OLD_DIR="$BASE/_releases/$OLD_RELEASE"
CURRENT_DIR="$(readlink -f "$BASE/current")"

ROLLBACK_DIR="$BASE/_rollback/$OLD_RELEASE"
ROLLBACK_COMPOSE="$ROLLBACK_DIR/docker-compose.rollback.yml"
ROLLBACK_BACKEND="sgi-rollback-backend:${OLD_RELEASE}"
ROLLBACK_FRONTEND="sgi-rollback-frontend:${OLD_RELEASE}"

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

if [ "$CURRENT_DIR" != "$OLD_DIR" ]; then
    echo "[ERRO] current nao aponta para a release ativa."
    echo "ACTIVE_RELEASE: $OLD_DIR"
    echo "current.......: $CURRENT_DIR"
    exit 7
fi

test -f "$OLD_DIR/.env.production" || {
    echo "[ERRO] .env.production da release atual nao encontrado."
    exit 8
}

if [ ! -f "$NEW_DIR/.env.production" ]; then
    cp "$OLD_DIR/.env.production" "$NEW_DIR/.env.production"
    chmod 600 "$NEW_DIR/.env.production"
    echo "[OK] .env.production preparado"
fi

wait_http() {
    local label="$1"
    local url="$2"
    local tentativa
    local codigo

    for tentativa in $(seq 1 30); do
        codigo="$(curl -sS -o /dev/null -w '%{http_code}' \
            "$url" || true)"

        if [ "$codigo" = "200" ]; then
            echo "[OK] $label HTTP 200"
            return 0
        fi

        sleep 2
    done

    echo "[ERRO] $label respondeu HTTP $codigo"
    return 1
}

proteger_imagem() {
    local imagem_atual="$1"
    local imagem_rollback="$2"
    local componente="$3"

    if docker image inspect "$imagem_atual" >/dev/null 2>&1; then
        docker tag "$imagem_atual" "$imagem_rollback"
        echo "[OK] $componente protegido a partir do container atual"
    elif docker image inspect "$imagem_rollback" >/dev/null 2>&1; then
        echo "[AVISO] Imagem atual de $componente sem metadados locais"
        echo "[OK] Rollback existente preservado: $imagem_rollback"
    else
        echo "[ERRO] Nao foi possivel proteger $componente"
        echo "[ERRO] Imagem atual indisponivel: $imagem_atual"
        echo "[ERRO] Rollback indisponivel: $imagem_rollback"
        return 1
    fi

    docker image inspect "$imagem_rollback" >/dev/null
}

echo ""
echo "[1/7] Validando producao atual"

for container in sgi_gateway sgi_frontend sgi_backend; do
    docker inspect "$container" >/dev/null
    test "$(docker inspect -f '{{.State.Running}}' "$container")" = "true"
done

wait_http \
    "Frontend atual" \
    "http://127.0.0.1:${PORTA_PROD}/"

wait_http \
    "API atual" \
    "http://127.0.0.1:${PORTA_PROD}/api/openapi.json"

cd "$OLD_DIR"
docker compose -p "$PROJECT_PROD" config -q

cd "$NEW_DIR"
docker compose -p "$PROJECT_PROD" config -q

echo "[OK] Producao e arquivos Compose validados"

echo ""
echo "[2/7] Protegendo imagens atuais"

OLD_BACKEND_IMAGE="$(docker inspect -f '{{.Image}}' sgi_backend)"
OLD_FRONTEND_IMAGE="$(docker inspect -f '{{.Image}}' sgi_frontend)"

mkdir -p "$ROLLBACK_DIR"

proteger_imagem \
    "$OLD_BACKEND_IMAGE" \
    "$ROLLBACK_BACKEND" \
    "backend"

proteger_imagem \
    "$OLD_FRONTEND_IMAGE" \
    "$ROLLBACK_FRONTEND" \
    "frontend"

cat > "$ROLLBACK_COMPOSE" <<EOF
services:
  backend:
    image: ${ROLLBACK_BACKEND}

  frontend:
    image: ${ROLLBACK_FRONTEND}
EOF

chmod 600 "$ROLLBACK_COMPOSE"

docker image inspect "$ROLLBACK_BACKEND" >/dev/null
docker image inspect "$ROLLBACK_FRONTEND" >/dev/null
docker compose \
    -p "$PROJECT_PROD" \
    -f "$OLD_DIR/docker-compose.yml" \
    -f "$ROLLBACK_COMPOSE" \
    config -q

echo "[OK] Rollback armado e validado antes do build"

echo ""
echo "[3/7] Construindo nova release"

cd "$NEW_DIR"

docker compose \
    -p "$PROJECT_PROD" \
    build backend frontend

docker image inspect sgi_prod-backend:latest >/dev/null
docker image inspect sgi_prod-frontend:latest >/dev/null

echo "[OK] Build concluido e imagens novas validadas"

rollback() {
    trap - ERR
    set +e

    echo ""
    echo "=============================================="
    echo "ROLLBACK AUTOMATICO"
    echo "=============================================="

    docker rm -f \
        sgi_gateway \
        sgi_frontend \
        sgi_backend \
        >/dev/null 2>&1 || true

    cd "$OLD_DIR" || exit 21

    docker compose \
        -p "$PROJECT_PROD" \
        -f docker-compose.yml \
        -f "$ROLLBACK_COMPOSE" \
        up -d --no-build

    printf '%s\n' "$OLD_RELEASE" > "$BASE/ACTIVE_RELEASE"
    ln -sfn "$OLD_DIR" "$BASE/current"

    ROLLBACK_OK="true"

    wait_http \
        "Frontend restaurado" \
        "http://127.0.0.1:${PORTA_PROD}/" ||
        ROLLBACK_OK="false"

    wait_http \
        "API restaurada" \
        "http://127.0.0.1:${PORTA_PROD}/api/openapi.json" ||
        ROLLBACK_OK="false"

    if [ "$ROLLBACK_OK" = "true" ]; then
        echo "[OK] Rollback restaurado"
    else
        echo "[CRITICO] Rollback iniciou, mas os testes HTTP falharam"
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

echo "[OK] Nova release iniciada"

echo ""
echo "[5/7] Smoke test HTTP"

wait_http \
    "Frontend" \
    "http://127.0.0.1:${PORTA_PROD}/"

wait_http \
    "API" \
    "http://127.0.0.1:${PORTA_PROD}/api/openapi.json"

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

test "$(cat "$BASE/ACTIVE_RELEASE")" = "$NEW_RELEASE"
test "$(cat "$BASE/PREVIOUS_RELEASE")" = "$OLD_RELEASE"
test "$(readlink -f "$BASE/current")" = "$NEW_DIR"

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
