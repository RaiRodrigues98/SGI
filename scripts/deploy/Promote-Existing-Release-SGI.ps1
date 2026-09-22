param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d{8}-\d{6}$')]
    [string]$Release,

    [switch]$ValidarApenas,

    [string]$Servidor = "27.78.101.5",
    [string]$Usuario = "app-invent",
    [string]$BaseRemota = "/opt/apps/inventario"
)

$ErrorActionPreference = "Stop"

$Projeto = (Resolve-Path "$PSScriptRoot\..\..").Path
$PreDeploy = Join-Path $PSScriptRoot "PreDeploy-SGI.ps1"

Set-Location $Projeto

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "SGI - PROMOVER RELEASE EXISTENTE" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "Release: $Release"

Write-Host ""
Write-Host "[1/3] Validando repositorio local" -ForegroundColor Cyan

& $PreDeploy

if ($LASTEXITCODE -ne 0) {
    throw "Pre-deploy reprovado."
}

$ReleaseRemota = "$BaseRemota/_releases/$Release"
$ScriptRemoto = "$ReleaseRemota/scripts/deploy/Promote-Release-SGI.sh"

Write-Host ""
Write-Host "[2/3] Validando release no servidor" -ForegroundColor Cyan

$ComandoValidacao = @"
set -e
test -d '$ReleaseRemota'
test -f '$ReleaseRemota/docker-compose.yml'
test -f '$ReleaseRemota/.env.production'
test -f '$ScriptRemoto'
test -f '$BaseRemota/ACTIVE_RELEASE'

echo 'Release ativa atual:'
cat '$BaseRemota/ACTIVE_RELEASE'

echo ''
echo 'Release candidata:'
echo '$Release'
"@

& ssh.exe "$Usuario@$Servidor" $ComandoValidacao

if ($LASTEXITCODE -ne 0) {
    throw "Release remota nao encontrada ou incompleta: $Release"
}

Write-Host ""
Write-Host "[OK] Release remota validada" -ForegroundColor Green

if ($ValidarApenas) {
    Write-Host ""
    Write-Host "==============================================" -ForegroundColor Green
    Write-Host "PROMOCAO: VALIDACAO APROVADA" -ForegroundColor Green
    Write-Host "RELEASE: $Release" -ForegroundColor Green
    Write-Host "PRODUCAO NAO FOI ALTERADA" -ForegroundColor Green
    Write-Host "==============================================" -ForegroundColor Green
    exit 0
}

Write-Host ""
Write-Host "[3/3] Confirmacao de cutover" -ForegroundColor Yellow
Write-Host ""
Write-Host "Esta operacao alterara a producao na porta 3001." -ForegroundColor Yellow

$ConfirmacaoEsperada = "PROMOVER $Release"

Write-Host ""
Write-Host "Digite exatamente:" -ForegroundColor Yellow
Write-Host $ConfirmacaoEsperada -ForegroundColor White
Write-Host ""

$Confirmacao = Read-Host "Confirmacao"

if ($Confirmacao -ne $ConfirmacaoEsperada) {
    throw "Promocao cancelada."
}

Write-Host ""
Write-Host "Executando cutover controlado..." -ForegroundColor Cyan

$ComandoPromocao = "chmod +x '$ScriptRemoto' && '$ScriptRemoto' '$Release'"

& ssh.exe "$Usuario@$Servidor" $ComandoPromocao

if ($LASTEXITCODE -ne 0) {
    throw "Promocao remota falhou. Verifique o estado do rollback."
}

Write-Host ""
Write-Host "Validando registro da release ativa..." -ForegroundColor Cyan

$ComandoFinal = @"
set -e
echo 'ACTIVE_RELEASE:'
cat '$BaseRemota/ACTIVE_RELEASE'
echo ''
echo 'CURRENT:'
readlink -f '$BaseRemota/current'
"@

& ssh.exe "$Usuario@$Servidor" $ComandoFinal

if ($LASTEXITCODE -ne 0) {
    throw "Nao foi possivel validar o registro final da release."
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Green
Write-Host "PROMOCAO SGI: CONCLUIDA" -ForegroundColor Green
Write-Host "RELEASE ATIVA: $Release" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green