param(
    [Parameter(Mandatory = $true)]
    [string]$Pacote,

    [Parameter(Mandatory = $true)]
    [string]$Manifesto,

    [string]$Servidor = "27.78.101.5",
    [string]$Usuario = "app-invent",
    [string]$BaseRemota = "/opt/apps/inventario"
)

$ErrorActionPreference = "Stop"

$Pacote = (Resolve-Path $Pacote).Path
$Manifesto = (Resolve-Path $Manifesto).Path

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "SGI - ENVIO DE RELEASE" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# ------------------------------------------------------------
# 1. VALIDACAO LOCAL
# ------------------------------------------------------------

Write-Host ""
Write-Host "[1/5] Validando pacote local" -ForegroundColor Cyan

$Dados = Get-Content $Manifesto -Raw | ConvertFrom-Json

$Release = $Dados.release
$HashEsperado = $Dados.sha256.ToUpperInvariant()

$HashAtual = (
    Get-FileHash -Algorithm SHA256 -LiteralPath $Pacote
).Hash.ToUpperInvariant()

if ($HashAtual -ne $HashEsperado) {
    throw "SHA256 local nao corresponde ao manifesto."
}

Write-Host "[OK] Release $Release validada" -ForegroundColor Green
Write-Host "SHA256: $HashAtual"


# ------------------------------------------------------------
# 2. DIRETORIOS REMOTOS
# ------------------------------------------------------------

Write-Host ""
Write-Host "[2/5] Preparando diretorios remotos" -ForegroundColor Cyan

$Incoming = "$BaseRemota/_incoming"
$Releases = "$BaseRemota/_releases"

& ssh.exe "$Usuario@$Servidor" "mkdir -p '$Incoming' '$Releases'"

if ($LASTEXITCODE -ne 0) {
    throw "Falha ao preparar diretorios remotos."
}

Write-Host "[OK] Diretorios remotos disponiveis" -ForegroundColor Green


# ------------------------------------------------------------
# 3. UPLOAD
# ------------------------------------------------------------

Write-Host ""
Write-Host "[3/5] Enviando pacote e manifesto" -ForegroundColor Cyan

$DestinoSCP = "${Usuario}@${Servidor}:$Incoming/"

& scp.exe $Pacote $Manifesto $DestinoSCP

if ($LASTEXITCODE -ne 0) {
    throw "Falha no upload da release."
}

Write-Host "[OK] Upload concluido" -ForegroundColor Green


# ------------------------------------------------------------
# 4. VALIDACAO E EXTRACAO REMOTA
# ------------------------------------------------------------

Write-Host ""
Write-Host "[4/5] Validando e extraindo no servidor" -ForegroundColor Cyan

$NomePacote = Split-Path $Pacote -Leaf
$NomeManifesto = Split-Path $Manifesto -Leaf

$PacoteRemoto = "$Incoming/$NomePacote"
$ManifestoRemoto = "$Incoming/$NomeManifesto"
$ReleaseDir = "$Releases/$Release"

$ComandoRemoto = @"
set -euo pipefail

PACKAGE='$PacoteRemoto'
MANIFEST='$ManifestoRemoto'
RELEASE_DIR='$ReleaseDir'
EXPECTED='$HashEsperado'

echo "Release destino: `$RELEASE_DIR"

ACTUAL=`$(sha256sum "`$PACKAGE" | awk '{print toupper(`$1)}')

if [ "`$ACTUAL" != "`$EXPECTED" ]; then
    echo "[ERRO] SHA256 remoto divergente"
    echo "Esperado: `$EXPECTED"
    echo "Atual:    `$ACTUAL"
    exit 20
fi

echo "[OK] SHA256 remoto validado"

if [ -e "`$RELEASE_DIR" ]; then
    echo "[ERRO] Diretorio da release ja existe: `$RELEASE_DIR"
    exit 21
fi

mkdir -p "`$RELEASE_DIR"

tar -xzf "`$PACKAGE" -C "`$RELEASE_DIR"

test -f "`$RELEASE_DIR/Dockerfile.backend"
test -f "`$RELEASE_DIR/docker-compose.yml"
test -f "`$RELEASE_DIR/deploy/nginx.conf"
test -f "`$RELEASE_DIR/requirements.txt"
test -f "`$RELEASE_DIR/frontend/Dockerfile"
test -f "`$RELEASE_DIR/frontend/package.json"
test -f "`$RELEASE_DIR/frontend/package-lock.json"

cp "`$MANIFEST" "`$RELEASE_DIR/DEPLOY-MANIFEST.json"

echo "[OK] Arquivos obrigatorios presentes"
echo "[OK] Release extraida"
du -sh "`$RELEASE_DIR"
"@

& ssh.exe "$Usuario@$Servidor" $ComandoRemoto

if ($LASTEXITCODE -ne 0) {
    throw "Validacao/extracao remota falhou."
}


# ------------------------------------------------------------
# 5. CONFIRMACAO
# ------------------------------------------------------------

Write-Host ""
Write-Host "[5/5] Confirmando preparo" -ForegroundColor Cyan

& ssh.exe "$Usuario@$Servidor" `
    "test -d '$ReleaseDir' && echo '[OK] $ReleaseDir'"

if ($LASTEXITCODE -ne 0) {
    throw "Release remota nao encontrada."
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Green
Write-Host "RELEASE REMOTA: PREPARADA" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Release : $Release"
Write-Host "Servidor: $Servidor"
Write-Host "Pasta   : $ReleaseDir"
Write-Host ""
Write-Host "PRODUCAO NAO FOI ALTERADA." -ForegroundColor Yellow
Write-Host ""
