$ErrorActionPreference = "Stop"

$Projeto = (Resolve-Path "$PSScriptRoot\..\..").Path
$Frontend = Join-Path $Projeto "frontend"

Set-Location $Projeto

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "SGI - VALIDACAO PRE-DEPLOY" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# ------------------------------------------------------------
# 1. REPOSITORIO PRINCIPAL
# ------------------------------------------------------------

Write-Host ""
Write-Host "[1/6] Repositorio principal" -ForegroundColor Cyan

$BranchPrincipal = git branch --show-current

if ($BranchPrincipal -ne "main") {
    throw "Branch principal invalida: $BranchPrincipal. Esperado: main"
}

$StatusPrincipal = git status --porcelain

if ($StatusPrincipal) {
    Write-Host $StatusPrincipal
    throw "Repositorio principal possui alteracoes pendentes."
}

Write-Host "[OK] Principal limpo e em main" -ForegroundColor Green


# ------------------------------------------------------------
# 2. FRONTEND
# ------------------------------------------------------------

Write-Host ""
Write-Host "[2/6] Repositorio frontend" -ForegroundColor Cyan

$BranchFrontend = git -C $Frontend branch --show-current

if ($BranchFrontend -ne "main") {
    throw "Branch frontend invalida: $BranchFrontend. Esperado: main"
}

$StatusFrontend = git -C $Frontend status --porcelain

if ($StatusFrontend) {
    Write-Host $StatusFrontend
    throw "Frontend possui alteracoes pendentes."
}

Write-Host "[OK] Frontend limpo e em main" -ForegroundColor Green


# ------------------------------------------------------------
# 3. SINCRONIZACAO COM REMOTO
# ------------------------------------------------------------

Write-Host ""
Write-Host "[3/6] Sincronizacao remota" -ForegroundColor Cyan

git fetch origin --quiet
git -C $Frontend fetch origin --quiet

$PrincipalLocal = git rev-parse HEAD
$PrincipalRemoto = git rev-parse origin/main

if ($PrincipalLocal -ne $PrincipalRemoto) {
    throw "Repositorio principal nao esta sincronizado com origin/main."
}

$FrontendLocal = git -C $Frontend rev-parse HEAD
$FrontendRemoto = git -C $Frontend rev-parse origin/main

if ($FrontendLocal -ne $FrontendRemoto) {
    throw "Frontend nao esta sincronizado com origin/main."
}

Write-Host "[OK] Principal e frontend sincronizados" -ForegroundColor Green


# ------------------------------------------------------------
# 4. GITLINK DO FRONTEND
# ------------------------------------------------------------

Write-Host ""
Write-Host "[4/6] Referencia do frontend" -ForegroundColor Cyan

$FrontendRegistrado = (
    git ls-tree HEAD frontend
) -replace '^160000 commit ([0-9a-f]+).*$', '$1'

if ($FrontendRegistrado -ne $FrontendLocal) {
    Write-Host "Registrado na raiz: $FrontendRegistrado"
    Write-Host "Frontend atual:     $FrontendLocal"
    throw "Repositorio principal nao aponta para o commit atual do frontend."
}

Write-Host "[OK] Gitlink frontend consistente" -ForegroundColor Green


# ------------------------------------------------------------
# 5. ARQUIVOS OBRIGATORIOS
# ------------------------------------------------------------

Write-Host ""
Write-Host "[5/6] Infraestrutura de producao" -ForegroundColor Cyan

$Obrigatorios = @(
    "Dockerfile.backend",
    "docker-compose.yml",
    "docker-compose.test.yml",
    ".dockerignore",
    ".env.production.example",
    "deploy\nginx.conf",
    "requirements.txt",
    "frontend\Dockerfile",
    "frontend\.dockerignore",
    "frontend\package-lock.json"
)

foreach ($Arquivo in $Obrigatorios) {
    $Caminho = Join-Path $Projeto $Arquivo

    if (-not (Test-Path $Caminho)) {
        throw "Arquivo obrigatorio ausente: $Arquivo"
    }
}

Write-Host "[OK] Arquivos de infraestrutura presentes" -ForegroundColor Green


# ------------------------------------------------------------
# 6. SEGREDOS
# ------------------------------------------------------------

Write-Host ""
Write-Host "[6/6] Protecao de segredos" -ForegroundColor Cyan

$EnvRastreado = git ls-files ".env"

if ($EnvRastreado) {
    throw ".env voltou a ser rastreado pelo Git."
}

if (-not (Test-Path ".env")) {
    Write-Host "[INFO] .env local nao encontrado" -ForegroundColor Yellow
} else {
    Write-Host "[OK] .env local existe e nao esta versionado" -ForegroundColor Green
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Green
Write-Host "PRE-DEPLOY SGI: APROVADO" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green

Write-Host ""
Write-Host "Principal : $($PrincipalLocal.Substring(0,7))"
Write-Host "Frontend  : $($FrontendLocal.Substring(0,7))"
Write-Host ""
