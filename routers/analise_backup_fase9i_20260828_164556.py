from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from dependencies.auth import (
    exigir_permissao,
)
from database import get_connection

from services.analise_rotativo import (
    analisar_inventario_rotativo,
    analisar_sessao_rotativo,
)

from services.analise_oficial import (
    analisar_sessao_oficial,
    analisar_rodada_oficial,
)


router = APIRouter(
    tags=["Análise"]
)


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def normalizar_tipo(tipo):

    if tipo is None:
        return ""

    return str(tipo).strip().upper()


def validar_snapshot(
    cursor,
    id_inventario: int
):

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM dbo.InventarioEstoqueSnapshot

        WHERE ID_Inventario = ?
        """,
        id_inventario
    )

    total = cursor.fetchone()[0]

    if total == 0:

        raise HTTPException(
            status_code=400,
            detail=(
                "O inventário ainda não possui "
                "snapshot de estoque."
            )
        )


# ============================================================
# ANÁLISE DA SESSÃO
#
# Neste momento:
#
# OFICIAL:
# possui análise individual de sessão.
#
# ROTATIVO:
# utiliza a análise consolidada do inventário,
# pois a conciliação é Localização + Código + Lote.
# ============================================================

@router.get(
    "/sessoes/{id_sessao}/analise"
)
def analisar_sessao(
    id_sessao: int
):

    if id_sessao <= 0:

        raise HTTPException(
            status_code=400,
            detail="Sessão inválida."
        )

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        # ====================================================
        # BUSCA SESSÃO + INVENTÁRIO
        # ====================================================

        cursor.execute(
            """
            SELECT
                S.ID_Sessao,
                S.ID_Inventario,
                S.ID_Rodada,
                S.Localizacao,
                S.Status,

                I.CodigoInventario,
                I.Tipo

            FROM dbo.SessoesContagem S

            LEFT JOIN dbo.Inventarios I
                ON I.ID_Inventario =
                   S.ID_Inventario

            WHERE S.ID_Sessao = ?
            """,
            id_sessao
        )

        sessao = cursor.fetchone()

        if not sessao:

            raise HTTPException(
                status_code=404,
                detail="Sessão não encontrada."
            )

        if sessao.ID_Inventario is None:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Sessão sem inventário vinculado."
                )
            )

        if sessao.ID_Rodada is None:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Sessão sem rodada vinculada."
                )
            )

        tipo = normalizar_tipo(
            sessao.Tipo
        )

        if tipo not in (
            "ROTATIVO",
            "OFICIAL"
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "Tipo de inventário inválido: "
                    f"{sessao.Tipo}"
                )
            )

        # ====================================================
        # SNAPSHOT
        # ====================================================

        validar_snapshot(
            cursor=cursor,
            id_inventario=(
                sessao.ID_Inventario
            )
        )

        # ====================================================
        # OFICIAL
        #
        # Continua utilizando análise individual da sessão.
        # ====================================================

        if tipo == "OFICIAL":

            return analisar_sessao_oficial(
                cursor=cursor,
                sessao=sessao
            )

        # ====================================================
        # ROTATIVO
        #
        # A análise da sessão deve considerar SOMENTE
        # as contagens vinculadas ao ID_Sessao solicitado.
        #
        # A análise consolidada do inventário/rodada continua
        # sendo responsabilidade de analisar_inventario_rotativo.
        # ====================================================

        return analisar_sessao_rotativo(
            cursor=cursor,
            sessao=sessao
        )

    except HTTPException:
        raise

    except Exception as erro:

        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# ANÁLISE CONSOLIDADA DA RODADA
# ============================================================

@router.get(
    "/inventarios/{id_inventario}"
    "/rodadas/{id_rodada}/analise",
    dependencies=[
        Depends(
            exigir_permissao(
                "ANALISE_VISUALIZAR"
            )
        )
    ]
)
def analisar_rodada(
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

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        # ====================================================
        # INVENTÁRIO
        # ====================================================

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
                detail="Inventário não encontrado."
            )

        tipo = normalizar_tipo(
            inventario.Tipo
        )

        if tipo not in (
            "ROTATIVO",
            "OFICIAL"
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "Tipo de inventário inválido: "
                    f"{inventario.Tipo}"
                )
            )

        # ====================================================
        # RODADA
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
        # SNAPSHOT
        # ====================================================

        validar_snapshot(
            cursor=cursor,
            id_inventario=id_inventario
        )

        # ====================================================
        # ROTATIVO
        #
        # Regra atual:
        # somente existe R1.
        # ====================================================

        if tipo == "ROTATIVO":

            if rodada.NumeroRodada != 1:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "O inventário ROTATIVO deste "
                        "cliente possui somente a Rodada 1."
                    )
                )

            return analisar_inventario_rotativo(
                cursor=cursor,
                id_inventario=id_inventario
            )

        # ====================================================
        # OFICIAL
        # ====================================================

        return analisar_rodada_oficial(
            cursor=cursor,
            inventario=inventario,
            rodada=rodada
        )

    except HTTPException:

        if conn:
            conn.rollback()

        raise

    except Exception as erro:

        if conn:
            conn.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# ANÁLISE ESPECÍFICA DO ROTATIVO
#
# Endpoint mais simples para o frontend.
# ============================================================

@router.get(
    "/inventarios/{id_inventario}/analise-rotativo"
)
def consultar_analise_rotativo(
    id_inventario: int
):

    if id_inventario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Inventário inválido."
        )

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        # ====================================================
        # INVENTÁRIO
        # ====================================================

        cursor.execute(
            """
            SELECT
                ID_Inventario,
                Tipo

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

        tipo = normalizar_tipo(
            inventario.Tipo
        )

        if tipo != "ROTATIVO":

            raise HTTPException(
                status_code=400,
                detail=(
                    "Este endpoint está disponível "
                    "somente para inventário ROTATIVO."
                )
            )

        # ====================================================
        # SNAPSHOT
        # ====================================================

        validar_snapshot(
            cursor=cursor,
            id_inventario=id_inventario
        )

        # ====================================================
        # ANÁLISE
        # ====================================================

        return analisar_inventario_rotativo(
            cursor=cursor,
            id_inventario=id_inventario
        )

    except HTTPException:
        raise

    except Exception as erro:

        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()