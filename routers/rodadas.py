from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from domain.exceptions import ConflictError
from application.exceptions import TechnicalConfigurationError
from domain.exceptions import BusinessRuleViolation, NotFoundError

from infrastructure.database.unit_of_work import SqlServerUnitOfWork

from dependencies.auth import (
    exigir_permissao,
)

from services.comparativo_rodadas import (
    comparar_rodadas_oficial,
)

from services.rodadas.repositories.rodada_repository import (
    listar_rodadas_inventario,
)

from services.rodadas_service import (
    criar_proxima_rodada,
    sincronizar_localizacoes_recontagem,
    visualizar_proxima_rodada,
)

from services.analise_recontagem import (
    analisar_recontagem_oficial,
)

from services.analise_recontagem_rotativo import (
    analisar_recontagem_rotativo,
)

from services.analise_gestor import (
    analisar_inventario_gestor,
)


from services.notificacoes import (
    criar_por_permissao,
)


router = APIRouter(
    tags=["Rodadas"]
)


# ============================================================
# GERAR PRÓXIMA RODADA
#
# Permissão:
# RODADA_GERAR
# ============================================================

@router.post(
    "/inventarios/{id_inventario}/rodadas/proxima",
    dependencies=[
        Depends(
            exigir_permissao(
                "RODADA_GERAR"
            )
        )
    ]
)
def gerar_proxima_rodada(
    id_inventario: int
):

    if id_inventario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Inventário inválido."
        )

    uow = None
    cursor = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()
        cursor = uow.cursor

        # ====================================================
        # 1. INVENTÁRIO
        # ====================================================

        cursor.execute(
            """
            SELECT
                ID_Inventario,
                CodigoInventario,
                Tipo,
                ClienteId,
                RodadaAtual,
                Status

            FROM dbo.Inventarios

            WHERE ID_Inventario = ?
            """,
            id_inventario
        )

        inventario = cursor.fetchone()

        if not inventario:

            raise HTTPException(
                status_code=404,
                detail="Inventário não encontrado."
            )

        # ====================================================
        # 2. RODADA ATUAL
        # ====================================================

        cursor.execute(
            """
            SELECT
                ID_Rodada,
                ID_Inventario,
                NumeroRodada,
                Status

            FROM dbo.RodadasInventario

            WHERE
                ID_Inventario = ?
                AND NumeroRodada = ?
            """,
            (
                id_inventario,
                inventario.RodadaAtual
            )
        )

        rodada_atual = cursor.fetchone()

        if not rodada_atual:

            raise HTTPException(
                status_code=404,
                detail="Rodada atual não encontrada."
            )

        # ====================================================
        # 3. CRIA PRÓXIMA RODADA
        # ====================================================

        resultado = criar_proxima_rodada(
            cursor=cursor,
            inventario=inventario,
            rodada_atual=rodada_atual
        )

        # ====================================================
        # 4. COMMIT
        # ====================================================

        if isinstance(resultado, dict):
            numero_nova_rodada = int(
                resultado.get("numero_rodada")
                or resultado.get("rodada")
                or (
                    int(
                        rodada_atual.NumeroRodada
                    )
                    + 1
                )
            )
        else:
            numero_nova_rodada = (
                int(
                    rodada_atual.NumeroRodada
                )
                + 1
            )

        resumo_notificacoes = (
            criar_por_permissao(
                cursor=cursor,
                codigo_permissao=(
                    "CONTAGEM_EXECUTAR"
                ),
                id_usuario_ator=None,
                tipo="RECONTAGEM_GERADA",
                titulo=(
                    "Nova rodada dispon\u00edvel"
                ),
                mensagem=(
                    f"A rodada R"
                    f"{numero_nova_rodada} "
                    f"do invent\u00e1rio "
                    f"{inventario.CodigoInventario} "
                    f"est\u00e1 dispon\u00edvel "
                    f"para contagem."
                ),
                prioridade="ALTA",
                entidade_tipo="RODADA",
                entidade_id=None,
                id_inventario=id_inventario,
                url=(
                    f"/inventarios/"
                    f"{id_inventario}"
                ),
                chave_dedupe=(
                    "RECONTAGEM_GERADA:"
                    f"{id_inventario}:"
                    f"{numero_nova_rodada}"
                ),
                excluir_ator=False,
            )
        )

        if isinstance(resultado, dict):
            resultado["notificacoes"] = (
                resumo_notificacoes
            )

        uow.commit()

        return {
            "sucesso":
                True,

            "id_inventario":
                inventario.ID_Inventario,

            "codigo_inventario":
                inventario.CodigoInventario,

            "tipo_inventario":
                inventario.Tipo,

            "rodada_anterior":
                rodada_atual.NumeroRodada,

            "proxima_rodada":
                resultado
        }

    except BusinessRuleViolation as erro:
        if uow:
            uow.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(erro)
        )

    except NotFoundError as erro:
        if uow:
            uow.rollback()

        raise HTTPException(
            status_code=404,
            detail=str(erro)
        )

    except TechnicalConfigurationError as erro:
        if uow:
            uow.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )

    except ConflictError as erro:
        if uow:
            uow.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(erro)
        )

    except HTTPException:

        if uow:
            uow.rollback()

        raise

    except Exception as erro:

        if uow:
            uow.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )

    finally:

        if uow:
            uow.close()


# ============================================================
# COMPARATIVO DE RODADAS
#
# Permissão:
# ANALISE_VISUALIZAR
# ============================================================

@router.get(
    "/inventarios/{id_inventario}/comparativo-rodadas",
    dependencies=[
        Depends(
            exigir_permissao(
                "ANALISE_VISUALIZAR"
            )
        )
    ]
)
def comparativo_rodadas(
    id_inventario: int
):

    if id_inventario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Inventário inválido."
        )

    uow = None
    cursor = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()
        cursor = uow.cursor

        # ====================================================
        # 1. INVENTÁRIO
        # ====================================================

        cursor.execute(
            """
            SELECT
                ID_Inventario,
                CodigoInventario,
                Tipo,
                ClienteId,
                RodadaAtual,
                Status

            FROM dbo.Inventarios

            WHERE ID_Inventario = ?
            """,
            id_inventario
        )

        inventario = cursor.fetchone()

        if not inventario:

            raise HTTPException(
                status_code=404,
                detail="Inventário não encontrado."
            )

        if (
            str(inventario.Tipo)
            .strip()
            .upper()
            != "OFICIAL"
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "Comparativo de rodadas disponível "
                    "somente para inventário OFICIAL."
                )
            )

        # ====================================================
        # 2. COMPARATIVO
        # ====================================================

        resultado = comparar_rodadas_oficial(
            cursor=cursor,
            id_inventario=id_inventario
        )

        return {
            "id_inventario":
                inventario.ID_Inventario,

            "codigo_inventario":
                inventario.CodigoInventario,

            "tipo":
                inventario.Tipo,

            "cliente_id":
                inventario.ClienteId,

            "rodada_atual":
                inventario.RodadaAtual,

            "resumo": {
                "total_itens":
                    resultado["total_itens"],

                "rodada_1_ok":
                    resultado["rodada_1_ok"],

                "rodada_2_ok":
                    resultado["rodada_2_ok"],

                "candidatos_r3":
                    resultado["candidatos_r3"]
            },

            "itens":
                resultado["itens"]
        }

    except HTTPException:
        raise

    except Exception as erro:

        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )

    finally:

        if uow:
            uow.close()


# ============================================================
# SINCRONIZAR LOCALIZAÇÕES DA RECONTAGEM
#
# Permissão:
# RODADA_GERAR
# ============================================================

@router.post(
    "/inventarios/{id_inventario}"
    "/rodadas/{id_rodada}/sincronizar-localizacoes",
    dependencies=[
        Depends(
            exigir_permissao(
                "RODADA_GERAR"
            )
        )
    ]
)
def sincronizar_localizacoes_rodada(
    id_inventario: int,
    id_rodada: int
):

    if id_inventario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Inventário inválido."
        )

    if id_rodada <= 0:

        raise HTTPException(
            status_code=400,
            detail="Rodada inválida."
        )

    uow = None
    cursor = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()
        cursor = uow.cursor

        # ====================================================
        # 1. INVENTÁRIO
        # ====================================================

        cursor.execute(
            """
            SELECT
                ID_Inventario,
                CodigoInventario,
                Tipo,
                ClienteId,
                RodadaAtual,
                Status

            FROM dbo.Inventarios

            WHERE ID_Inventario = ?
            """,
            id_inventario
        )

        inventario = cursor.fetchone()

        if not inventario:

            raise HTTPException(
                status_code=404,
                detail="Inventário não encontrado."
            )

        # ====================================================
        # 2. RODADA
        # ====================================================

        cursor.execute(
            """
            SELECT
                ID_Rodada,
                ID_Inventario,
                NumeroRodada,
                Status

            FROM dbo.RodadasInventario

            WHERE
                ID_Rodada = ?
                AND ID_Inventario = ?
            """,
            (
                id_rodada,
                id_inventario
            )
        )

        rodada = cursor.fetchone()

        if not rodada:

            raise HTTPException(
                status_code=404,
                detail=(
                    "Rodada não encontrada "
                    "para este inventário."
                )
            )

        # ====================================================
        # 3. SOMENTE OFICIAL
        # ====================================================

        if (
            str(inventario.Tipo)
            .strip()
            .upper()
            != "OFICIAL"
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "Sincronização de localizações "
                    "disponível somente para "
                    "inventário OFICIAL."
                )
            )

        # ====================================================
        # 4. SINCRONIZA
        # ====================================================

        resultado = (
            sincronizar_localizacoes_recontagem(
                cursor=cursor,
                id_inventario=id_inventario,
                id_rodada=id_rodada
            )
        )

        # ====================================================
        # 5. COMMIT
        # ====================================================

        uow.commit()

        return {
            "sucesso":
                True,

            "id_inventario":
                inventario.ID_Inventario,

            "codigo_inventario":
                inventario.CodigoInventario,

            "id_rodada":
                rodada.ID_Rodada,

            "numero_rodada":
                rodada.NumeroRodada,

            "resultado":
                resultado
        }

    except HTTPException:

        if uow:
            uow.rollback()

        raise

    except Exception as erro:

        if uow:
            uow.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )

    finally:

        if uow:
            uow.close()


# ============================================================
# ANÁLISE DE RECONTAGEM - R3+
#
# Permissão:
# ANALISE_VISUALIZAR
# ============================================================

@router.get(
    "/inventarios/{id_inventario}"
    "/rodadas/{id_rodada}/analise-recontagem",
    dependencies=[
        Depends(
            exigir_permissao(
                "ANALISE_VISUALIZAR"
            )
        )
    ]
)
def analisar_rodada_recontagem(
    id_inventario: int,
    id_rodada: int
):

    if id_inventario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Inventário inválido."
        )

    if id_rodada <= 0:

        raise HTTPException(
            status_code=400,
            detail="Rodada inválida."
        )

    uow = None
    cursor = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()
        cursor = uow.cursor

        cursor.execute(
            """
            SELECT Tipo
            FROM dbo.Inventarios
            WHERE ID_Inventario = ?
            """,
            id_inventario
        )

        inventario = cursor.fetchone()

        if not inventario:

            raise NotFoundError(
                "Invent?rio n?o encontrado."
            )

        tipo_inventario = (
            str(inventario.Tipo or "")
            .strip()
            .upper()
        )

        if tipo_inventario == "ROTATIVO":

            resultado = analisar_recontagem_rotativo(
                cursor=cursor,
                id_inventario=id_inventario,
                id_rodada=id_rodada
            )

        elif tipo_inventario == "OFICIAL":

            resultado = analisar_recontagem_oficial(
                cursor=cursor,
                id_inventario=id_inventario,
                id_rodada=id_rodada
            )

        else:

            raise BusinessRuleViolation(
                "Tipo de invent?rio n?o suportado "
                "para an?lise de recontagem."
            )

        return resultado

    except BusinessRuleViolation as erro:
        raise HTTPException(
            status_code=400,
            detail=str(erro)
        )

    except NotFoundError as erro:
        raise HTTPException(
            status_code=404,
            detail=str(erro)
        )

    except HTTPException:
        raise

    except Exception as erro:

        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )

    finally:

        if uow:
            uow.close()


# ============================================================
# HIST?RICO DE RODADAS DO INVENT?RIO
#
# Permiss?o:
# ANALISE_VISUALIZAR
# ============================================================

@router.get(
    "/inventarios/{id_inventario}/rodadas",
    dependencies=[
        Depends(
            exigir_permissao(
                "ANALISE_VISUALIZAR"
            )
        )
    ]
)
def listar_rodadas_do_inventario(
    id_inventario: int
):

    if id_inventario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Invent?rio inv?lido."
        )

    uow = None
    cursor = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()
        cursor = uow.cursor

        cursor.execute(
            """
            SELECT
                ID_Inventario,
                CodigoInventario,
                Tipo,
                RodadaAtual,
                Status

            FROM dbo.Inventarios

            WHERE ID_Inventario = ?
            """,
            id_inventario
        )

        inventario = cursor.fetchone()

        if not inventario:

            raise HTTPException(
                status_code=404,
                detail="Invent?rio n?o encontrado."
            )

        rodadas = listar_rodadas_inventario(
            cursor=cursor,
            id_inventario=id_inventario
        )

        return {
            "id_inventario":
                inventario.ID_Inventario,

            "codigo_inventario":
                inventario.CodigoInventario,

            "tipo":
                inventario.Tipo,

            "rodada_atual":
                inventario.RodadaAtual,

            "status_inventario":
                inventario.Status,

            "total_rodadas":
                len(rodadas),

            "rodadas": [
                {
                    "id_rodada":
                        rodada.ID_Rodada,

                    "numero_rodada":
                        rodada.NumeroRodada,

                    "status":
                        rodada.Status
                }
                for rodada in rodadas
            ]
        }

    except HTTPException:
        raise

    except Exception as erro:

        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )

    finally:

        if uow:
            uow.close()


# ============================================================
# ANÁLISE GERENCIAL DO INVENTÁRIO OFICIAL
#
# Permissão:
# ANALISE_VISUALIZAR
# ============================================================

@router.get(
    "/inventarios/{id_inventario}/analise-gestor",
    dependencies=[
        Depends(
            exigir_permissao(
                "ANALISE_VISUALIZAR"
            )
        )
    ]
)
def consultar_analise_gestor(
    id_inventario: int
):

    if id_inventario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Inventário inválido."
        )

    uow = None
    cursor = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()
        cursor = uow.cursor

        resultado = analisar_inventario_gestor(
            cursor=cursor,
            id_inventario=id_inventario
        )

        return resultado

    except BusinessRuleViolation as erro:
        raise HTTPException(
            status_code=400,
            detail=str(erro)
        )

    except NotFoundError as erro:
        raise HTTPException(
            status_code=404,
            detail=str(erro)
        )

    except HTTPException:
        raise

    except Exception as erro:

        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )

    finally:

        if uow:
            uow.close()


# ============================================================
# PREVIEW DA PRÓXIMA RODADA
#
# Não grava dados.
#
# Permissão:
# ANALISE_VISUALIZAR
# ============================================================

@router.get(
    "/inventarios/{id_inventario}/rodadas/proxima-preview",
    dependencies=[
        Depends(
            exigir_permissao(
                "ANALISE_VISUALIZAR"
            )
        )
    ]
)
def preview_proxima_rodada(
    id_inventario: int
):

    if id_inventario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Inventário inválido."
        )

    uow = None
    cursor = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()
        cursor = uow.cursor

        # ====================================================
        # 1. INVENTÁRIO
        # ====================================================

        cursor.execute(
            """
            SELECT
                ID_Inventario,
                CodigoInventario,
                Tipo,
                ClienteId,
                RodadaAtual,
                Status

            FROM dbo.Inventarios

            WHERE ID_Inventario = ?
            """,
            id_inventario
        )

        inventario = cursor.fetchone()

        if not inventario:

            raise HTTPException(
                status_code=404,
                detail="Inventário não encontrado."
            )

        # ====================================================
        # 2. RODADA ATUAL
        # ====================================================

        cursor.execute(
            """
            SELECT TOP 1
                ID_Rodada,
                ID_Inventario,
                NumeroRodada,
                Status,
                DataHoraInicio

            FROM dbo.RodadasInventario

            WHERE
                ID_Inventario = ?
                AND NumeroRodada = ?

            ORDER BY
                ID_Rodada DESC
            """,
            (
                id_inventario,
                inventario.RodadaAtual
            )
        )

        rodada_atual = (
            cursor.fetchone()
        )

        if not rodada_atual:

            raise HTTPException(
                status_code=404,
                detail=(
                    "Rodada atual não encontrada."
                )
            )

        # ====================================================
        # 3. PREVIEW
        # ====================================================

        resultado = (
            visualizar_proxima_rodada(
                cursor=cursor,
                inventario=inventario,
                rodada_atual=rodada_atual
            )
        )

        return {
            "id_inventario":
                inventario.ID_Inventario,

            "codigo_inventario":
                inventario.CodigoInventario,

            "tipo_inventario":
                inventario.Tipo,

            "status_inventario":
                inventario.Status,

            "preview":
                resultado
        }

    except BusinessRuleViolation as erro:
        raise HTTPException(
            status_code=400,
            detail=str(erro)
        )

    except NotFoundError as erro:
        raise HTTPException(
            status_code=404,
            detail=str(erro)
        )

    except TechnicalConfigurationError as erro:
        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )

    except HTTPException:
        raise

    except Exception as erro:

        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )

    finally:

        if uow:
            uow.close()
