param(
    [switch]$ValidarApenas,
    [switch]$Promover,

    [string]$Servidor = "27.78.101.5",
    [string]$Usuario = "app-invent",
    [string]$BaseRemota = "/opt/apps/inventario"
)

$ErrorActionPreference = "Stop"

$Projeto = (Resolve-Path "$PSScriptRoot\..\..").Path
$PreDeploy = Join-Path $PSScriptRoot "PreDeploy-SGI.ps1"
$BuildRelease = Join-Path $PSScriptRoot "Build-Release-SGI.ps1"
$UploadRelease = Join-Path $PSScriptRoot "Upload-Release-SGI.ps1"

Set-Location $Projeto

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "SGI - DEPLOY CONTROLADO" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# ------------------------------------------------------------
# 1. VALIDACAO
# ------------------------------------------------------------

Write-Host ""
Write-Host "[1/4] Pre-deploy" -ForegroundColor Cyan

& $PreDeploy

if ($LASTEXITCODE -ne 0) {
    throw "Pre-deploy reprovado."
}

if ($ValidarApenas) {
    Write-Host ""
    Write-Host "==============================================" -ForegroundColor Green
    Write-Host "DEPLOY: VALIDACAO APROVADA" -ForegroundColor Green
    Write-Host "Nenhuma release foi criada ou enviada." -ForegroundColor Green
    Write-Host "==============================================" -ForegroundColor Green
    exit 0
}

# ------------------------------------------------------------
# 2. GERAR RELEASE
# ------------------------------------------------------------

Write-Host ""
Write-Host "[2/4] Gerando release" -ForegroundColor Cyan

$Inicio = Get-Date

& $BuildRelease

if ($LASTEXITCODE -ne 0) {
    throw "Falha ao gerar release."
}

$DiretorioSaida = Split-Path $Projeto -Parent

$Manifesto = Get-ChildItem `
    -LiteralPath $DiretorioSaida `
    -Filter 'SGI-deploy-*.manifest.json' `
    -File |
    Where-Object {
        $_.LastWriteTime -ge $Inicio.AddSeconds(-5)
    } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $Manifesto) {
    throw "Manifesto da nova release nao localizado."
}

$Dados = Get-Content $Manifesto.FullName -Raw |
    ConvertFrom-Json

$Release = $Dados.release
$Pacote = Join-Path $DiretorioSaida $Dados.arquivo

if (-not (Test-Path $Pacote)) {
    throw "Pacote da release nao localizado: $Pacote"
}

Write-Host ""
Write-Host "[OK] Release gerada: $Release" -ForegroundColor Green

# ------------------------------------------------------------
# 3. ENVIAR / PREPARAR NO SERVIDOR
# ------------------------------------------------------------

Write-Host ""
Write-Host "[3/4] Enviando release ao servidor" -ForegroundColor Cyan

& $UploadRelease `
    -Pacote $Pacote `
    -Manifesto $Manifesto.FullName `
    -Servidor $Servidor `
    -Usuario $Usuario `
    -BaseRemota $BaseRemota

if ($LASTEXITCODE -ne 0) {
    throw "Falha ao preparar release remota."
}

Write-Host ""
Write-Host "[OK] Release preparada no servidor" -ForegroundColor Green

# ------------------------------------------------------------
# 4. PROMOCAO OPCIONAL
# ------------------------------------------------------------

Write-Host ""
Write-Host "[4/4] Promocao" -ForegroundColor Cyan

if (-not $Promover) {
    Write-Host ""
    Write-Host "==============================================" -ForegroundColor Yellow
    Write-Host "RELEASE PREPARADA - SEM CUTOVER" -ForegroundColor Yellow
    Write-Host "==============================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Release   : $Release"
    Write-Host "Pacote    : $Pacote"
    Write-Host "Manifesto : $($Manifesto.FullName)"
    Write-Host ""
    Write-Host "A producao NAO foi alterada."
    Write-Host ""
    Write-Host "Para promover futuramente:"
    Write-Host ".\scripts\deploy\Deploy-SGI.ps1 -Promover"
    exit 0
}

$ConfirmacaoEsperada = "PROMOVER $Release"

Write-Host ""
Write-Host "ATENCAO: esta etapa substituira a release ativa na porta 3001." -ForegroundColor Yellow
Write-Host ""
Write-Host "Digite exatamente:" -ForegroundColor Yellow
Write-Host $ConfirmacaoEsperada -ForegroundColor White
Write-Host ""

$Confirmacao = Read-Host "Confirmacao"

if ($Confirmacao -ne $ConfirmacaoEsperada) {
    throw "Promocao cancelada pelo usuario."
}

$ScriptRemoto = "$BaseRemota/_releases/$Release/scripts/deploy/Promote-Release-SGI.sh"

Write-Host ""
Write-Host "Executando promocao no servidor..." -ForegroundColor Cyan

& ssh.exe "$Usuario@$Servidor" `
    "chmod +x '$ScriptRemoto' && '$ScriptRemoto' '$Release'"

if ($LASTEXITCODE -ne 0) {
    throw "Promocao remota falhou. Verifique o rollback no servidor."
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Green
Write-Host "DEPLOY SGI: CONCLUIDO" -ForegroundColor Green
Write-Host "RELEASE ATIVA: $Release" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green
