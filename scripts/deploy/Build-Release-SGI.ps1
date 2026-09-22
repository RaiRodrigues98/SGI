$ErrorActionPreference = "Stop"

$Projeto = (Resolve-Path "$PSScriptRoot\..\..").Path
$Frontend = Join-Path $Projeto "frontend"
$PreDeploy = Join-Path $PSScriptRoot "PreDeploy-SGI.ps1"

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "SGI - GERADOR DE RELEASE" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# ------------------------------------------------------------
# 1. PRE-DEPLOY
# ------------------------------------------------------------

Write-Host ""
Write-Host "[1/6] Validacao pre-deploy" -ForegroundColor Cyan

& $PreDeploy

if ($LASTEXITCODE -ne 0) {
    throw "Pre-deploy nao aprovado."
}

# ------------------------------------------------------------
# 2. IDENTIFICACAO
# ------------------------------------------------------------

Write-Host ""
Write-Host "[2/6] Identificando release" -ForegroundColor Cyan

$ReleaseId = Get-Date -Format "yyyyMMdd-HHmmss"
$CommitPrincipal = (git -C $Projeto rev-parse HEAD).Trim()
$CommitFrontend = (git -C $Frontend rev-parse HEAD).Trim()

$Saida = Split-Path $Projeto -Parent
$Pacote = Join-Path $Saida "SGI-deploy-$ReleaseId.tar.gz"
$Manifesto = Join-Path $Saida "SGI-deploy-$ReleaseId.manifest.json"

$TempBase = Join-Path $env:TEMP "sgi-release-$ReleaseId"
$ReleaseDir = Join-Path $TempBase "release"
$RootTar = Join-Path $TempBase "root.tar"
$FrontendTar = Join-Path $TempBase "frontend.tar"

New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null

Write-Host "Release   : $ReleaseId"
Write-Host "Principal : $($CommitPrincipal.Substring(0,7))"
Write-Host "Frontend  : $($CommitFrontend.Substring(0,7))"

# ------------------------------------------------------------
# 3. EXPORTACAO GIT
# ------------------------------------------------------------

Write-Host ""
Write-Host "[3/6] Exportando arquivos versionados" -ForegroundColor Cyan

git -C $Projeto archive `
    --format=tar `
    --output="$RootTar" `
    HEAD

if ($LASTEXITCODE -ne 0) {
    throw "Falha ao exportar repositorio principal."
}

tar.exe -xf $RootTar -C $ReleaseDir

if ($LASTEXITCODE -ne 0) {
    throw "Falha ao extrair repositorio principal."
}

$FrontendDestino = Join-Path $ReleaseDir "frontend"

if (-not (Test-Path $FrontendDestino)) {
    New-Item -ItemType Directory -Path $FrontendDestino -Force |
        Out-Null
}

git -C $Frontend archive `
    --format=tar `
    --output="$FrontendTar" `
    HEAD

if ($LASTEXITCODE -ne 0) {
    throw "Falha ao exportar frontend."
}

tar.exe -xf $FrontendTar -C $FrontendDestino

if ($LASTEXITCODE -ne 0) {
    throw "Falha ao extrair frontend."
}

Write-Host "[OK] Backend e frontend exportados diretamente do Git" -ForegroundColor Green

# ------------------------------------------------------------
# 4. SEGURANCA
# ------------------------------------------------------------

Write-Host ""
Write-Host "[4/6] Validando conteudo da release" -ForegroundColor Cyan

$Problemas = Get-ChildItem `
    -LiteralPath $ReleaseDir `
    -Recurse `
    -Force |
    Where-Object {
        $_.Name -eq ".git" -or
        $_.Name -eq "__pycache__" -or
        $_.Name -eq "node_modules" -or
        $_.Name -eq ".venv" -or
        $_.Name -eq "venv" -or
        $_.Name -eq ".output" -or
        $_.Name -eq "_backups" -or
        $_.Name -eq "backups" -or
        $_.Name -eq "_diagnosticos" -or
        $_.Name -eq "inventory-mapper-3d-main" -or
        $_.Name -like "*.pyc" -or
        (
            $_.Name -like ".env*" -and
            $_.Name -ne ".env.production.example"
        )
    }

if ($Problemas) {
    Write-Host "[ERRO] Conteudo proibido encontrado:" -ForegroundColor Red
    $Problemas |
        Select-Object FullName |
        Format-Table -AutoSize

    throw "Release bloqueada por arquivos proibidos."
}

$Obrigatorios = @(
    "Dockerfile.backend",
    "docker-compose.yml",
    "docker-compose.test.yml",
    "deploy\nginx.conf",
    "requirements.txt",
    "frontend\Dockerfile",
    "frontend\package.json",
    "frontend\package-lock.json"
)

foreach ($Arquivo in $Obrigatorios) {
    $Caminho = Join-Path $ReleaseDir $Arquivo

    if (-not (Test-Path $Caminho)) {
        throw "Arquivo obrigatorio ausente na release: $Arquivo"
    }
}

Write-Host "[OK] Release sem segredo, cache ou backup" -ForegroundColor Green

# ------------------------------------------------------------
# 5. PACOTE
# ------------------------------------------------------------

Write-Host ""
Write-Host "[5/6] Gerando pacote TAR.GZ" -ForegroundColor Cyan

if (Test-Path $Pacote) {
    Remove-Item $Pacote -Force
}

tar.exe -czf $Pacote -C $ReleaseDir .

if ($LASTEXITCODE -ne 0) {
    throw "Falha ao gerar TAR.GZ."
}

$Hash = (Get-FileHash `
    -Algorithm SHA256 `
    -LiteralPath $Pacote).Hash

$TamanhoMB = [Math]::Round(
    (Get-Item $Pacote).Length / 1MB,
    2
)

# ------------------------------------------------------------
# 6. MANIFESTO
# ------------------------------------------------------------

Write-Host ""
Write-Host "[6/6] Gerando manifesto" -ForegroundColor Cyan

$DadosManifesto = [ordered]@{
    sistema          = "SGI"
    release          = $ReleaseId
    gerado_em        = (Get-Date).ToString("o")
    commit_principal = $CommitPrincipal
    commit_frontend  = $CommitFrontend
    arquivo          = Split-Path $Pacote -Leaf
    sha256           = $Hash
    tamanho_mb       = $TamanhoMB
}

$DadosManifesto |
    ConvertTo-Json |
    Set-Content `
        -LiteralPath $Manifesto `
        -Encoding UTF8

Remove-Item $TempBase -Recurse -Force

Write-Host ""
Write-Host "==============================================" -ForegroundColor Green
Write-Host "PACOTE DE RELEASE: APROVADO" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Release   : $ReleaseId"
Write-Host "Principal : $($CommitPrincipal.Substring(0,7))"
Write-Host "Frontend  : $($CommitFrontend.Substring(0,7))"
Write-Host "Pacote    : $Pacote"
Write-Host "Manifesto : $Manifesto"
Write-Host "Tamanho   : $TamanhoMB MB"
Write-Host "SHA256    : $Hash"
Write-Host ""
