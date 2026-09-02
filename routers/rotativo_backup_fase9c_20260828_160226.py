from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from database import get_connection

from dependencies.auth import (
    exigir_permissao,
)

from schemas.rotativo import (
    DecisaoRotativoEntrada,
)

from services.decisoes_rotativo import (
    registrar_decisao_rotativo,
)

from services.rotativo_orquestrador import (
    executar_orquestracao_rotativo,
)


router = APIRouter(
    tags=["Rotativo"]
)
# ============================================================
# REGISTRAR DECISÃO DO INVENTÁRIO ROTATIVO
# ============================================================

@router.post(
    "/inventarios/{id_inventario}/decisoes-rotativo"
)
def registrar_decisao_rotativo_endpoint(
    id_inventario: int,
    dados: DecisaoRotativoEntrada,
    usuario_atual=Depends(
        exigir_permissao(
            "INVENTARIO_ROTATIVO_DECIDIR"
        )
    )
):

    if id_inventario <= 0:

        raise HTTPException(
            status_code=400,
            detail="Inventário inválido."
        )

    usuario = (
        str(
            usuario_atual["login"]
        )
        .strip()
    )

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        resultado = (
            registrar_decisao_rotativo(
                cursor=cursor,
                id_inventario=id_inventario,
                id_rodada=dados.id_rodada,
                localizacao=dados.localizacao,
                codigo=dados.codigo,
                lote=dados.lote or "",
                decisao=dados.decisao,
                justificativa=dados.justificativa,
                usuario=usuario
            )
        )

        # ====================================================
        # COMMIT DA OPERAÇÃO PRINCIPAL
        # ====================================================

        conn.commit()

        # ====================================================
        # INTELIGÊNCIA PÓS-JUSTIFICATIVA
        #
        # O orquestrador deve rodar somente depois do commit.
        # Falha analítica não pode desfazer a decisão já gravada.
        # ====================================================

        decisao_normalizada = (
            str(
                dados.decisao
            )
            .strip()
            .upper()
        )

        if (
            decisao_normalizada
            ==
            "JUSTIFICAR_DIVERGENCIA"
        ):

            try:

                inteligencia = (
                    executar_orquestracao_rotativo(
                        conn=conn,
                        cursor=cursor,
                        cliente_id=(
                            resultado[
                                "cliente_id"
                            ]
                        ),
                        armazem=(
                            resultado[
                                "armazem"
                            ]
                        ),
                        origem_evento=(
                            "JUSTIFICATIVA_DIVERGENCIA"
                        ),
                        localizacao=(
                            resultado[
                                "localizacao"
                            ]
                        ),
                        id_ocorrencia=(
                            resultado.get(
                                "id_ocorrencia"
                            )
                        ),
                        id_inventario=(
                            id_inventario
                        ),
                        id_rodada=(
                            dados.id_rodada
                        ),
                        usuario=usuario,
                        limite_score_sugestao=50.0,
                        quantidade_sugestoes=20,
                        retornar_painel=True,
                    )
                )

                resultado[
                    "inteligencia"
                ] = {
                    "executada":
                        bool(
                            inteligencia
                            and
                            inteligencia.get(
                                "orquestrado"
                            )
                        ),

                    "motivo":
                        (
                            inteligencia.get(
                                "motivo"
                            )
                            if inteligencia
                            else None
                        ),

                    "resultado":
                        inteligencia,

                    "erro":
                        None,
                }

            except Exception as erro_inteligencia:

                resultado[
                    "inteligencia"
                ] = {
                    "executada":
                        False,

                    "motivo":
                        "FALHA_ATUALIZACAO_INTELIGENCIA",

                    "resultado":
                        None,

                    "erro":
                        str(
                            erro_inteligencia
                        ),

                    "mensagem":
                        (
                            "A decisão foi registrada com sucesso, "
                            "mas houve falha ao atualizar a "
                            "inteligência do inventário rotativo."
                        ),
                }

        else:

            resultado[
                "inteligencia"
            ] = {
                "executada":
                    False,

                "motivo":
                    "EVENTO_NAO_APLICAVEL",

                "resultado":
                    None,

                "erro":
                    None,

                "mensagem":
                    (
                        "A decisão foi registrada. O recálculo "
                        "automático da inteligência é executado "
                        "neste endpoint apenas para "
                        "JUSTIFICAR_DIVERGENCIA."
                    ),
            }

        return resultado

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