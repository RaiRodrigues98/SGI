from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from database import get_connection

from routers.snapshot import router as snapshot_router
from routers.rodadas import router as rodadas_router
from routers.contagens import router as contagens_router
from routers.escopo import router as escopo_router
from routers.analise import router as analise_router
from routers.gestor import router as gestor_router
from routers.finalizacao import router as finalizacao_router
from routers.resultado_final import router as resultado_final_router
from routers.consultas import router as consultas_router
from routers.encaminhamento_gestor import (
    router as encaminhamento_gestor_router,
)
from routers.usuarios import router as usuarios_router
from routers.auth import router as auth_router
from routers.inventarios import router as inventarios_router
from routers.rotativo import router as rotativo_router
from routers.configuracoes_operacionais import (
    router as configuracoes_operacionais_router,
)
from routers.indicadores import router as indicadores_router
from routers.historico import (
    router as historico_router,
)
from routers.risco import (
    router as risco_router,
)
from routers.rotativo_ciclos import (
    router as rotativo_ciclos_router,
)
from routers.rotativo_cobertura import (
    router as rotativo_cobertura_router,
)
from routers.rotativo_fluxo import (
    router as rotativo_fluxo_router,
)
from routers.rotativo_consulta import (
    router as rotativo_consulta_router,
)
from routers.rotativo_priorizacao import router as rotativo_priorizacao
# ============================================================
# APLICAÇÃO
# ============================================================

app = FastAPI(
    title="SGI - Alzarsilog",
    version="0.3.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ROUTERS
# ============================================================

app.include_router(
    contagens_router
)

app.include_router(
    escopo_router
)

app.include_router(
    analise_router
)

app.include_router(
    snapshot_router
)

app.include_router(
    rodadas_router
)

app.include_router(
    gestor_router
)

app.include_router(
    finalizacao_router
)

app.include_router(
    resultado_final_router
)

app.include_router(
    consultas_router
)

app.include_router(
    encaminhamento_gestor_router
)

app.include_router(
    configuracoes_operacionais_router
)

app.include_router(
    usuarios_router
)

app.include_router(
    auth_router
)

app.include_router(
    inventarios_router
)

app.include_router(
    rotativo_router
)

app.include_router(
    indicadores_router
)
app.include_router(
    historico_router
)
app.include_router(
    risco_router
)
app.include_router(
    rotativo_ciclos_router
)
app.include_router(
    rotativo_cobertura_router
)

app.include_router(
    rotativo_fluxo_router
)
app.include_router(
    rotativo_consulta_router
)
app.include_router(rotativo_priorizacao)