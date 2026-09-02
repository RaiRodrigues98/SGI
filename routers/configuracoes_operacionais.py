from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from domain.exceptions import BusinessRuleViolation, NotFoundError

from infrastructure.database.unit_of_work import SqlServerUnitOfWork

from dependencies.auth import (
    exigir_permissao,
)

from schemas.configuracoes_operacionais import (
    ConfiguracaoOperacionalEntrada,
)

from services.configuracoes_inventario import (
    obter_configuracao_completa,
)


router = APIRouter(
    tags=["Configurações"]
)


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def _normalizar_tipo(valor):

    if valor is None:
        return ""

    return (
        str(valor)
        .strip()
        .upper()
    )


# ============================================================
# CONSULTAR CONFIGURAÇÃO
#
# Permissão necessária:
# CONFIGURACAO_VISUALIZAR
# ============================================================

@router.get(
    "/configuracoes/inventario/{cliente_id}/{tipo}",
    dependencies=[
        Depends(
            exigir_permissao(
                "CONFIGURACAO_VISUALIZAR"
            )
        )
    ]
)
def consultar_configuracao(
    cliente_id: int,
    tipo: str
):

    if cliente_id <= 0:

        raise HTTPException(
            status_code=400,
            detail="Cliente inválido."
        )

    tipo_normalizado = (
        _normalizar_tipo(
            tipo
        )
    )

    if tipo_normalizado not in (
        "ROTATIVO",
        "OFICIAL"
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Tipo de inventário inválido. "
                "Utilize ROTATIVO ou OFICIAL."
            )
        )

    uow = None
    conn = None
    cursor = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()
        conn = uow.connection
        cursor = uow.cursor

        return obter_configuracao_completa(
            cursor=cursor,
            cliente_id=cliente_id,
            tipo_inventario=tipo_normalizado
        )

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
# ATUALIZAR CONFIGURAÇÃO
#
# Permissão necessária:
# CONFIGURACAO_EDITAR
#
# Atualiza:
# dbo.ConfiguracoesInventario
#
# As configurações das rodadas permanecem em:
# dbo.ConfiguracoesRodadasInventario
#
# Commit fica sob responsabilidade deste router.
# ============================================================

@router.put(
    "/configuracoes/inventario/{cliente_id}/{tipo}"
)
def atualizar_configuracao(
    cliente_id: int,
    tipo: str,
    dados: ConfiguracaoOperacionalEntrada,
    usuario_atual=Depends(
        exigir_permissao(
            "CONFIGURACAO_EDITAR"
        )
    )
):

    # ========================================================
    # 1. VALIDAÇÕES BÁSICAS
    # ========================================================

    if cliente_id <= 0:

        raise HTTPException(
            status_code=400,
            detail="Cliente inválido."
        )

    tipo_normalizado = (
        _normalizar_tipo(
            tipo
        )
    )

    if tipo_normalizado not in (
        "ROTATIVO",
        "OFICIAL"
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Tipo de inventário inválido. "
                "Utilize ROTATIVO ou OFICIAL."
            )
        )

    usuario = (
        str(usuario_atual["login"]).strip()
    )

    # ========================================================
    # 2. VALIDAÇÃO DAS QUANTIDADES
    # ========================================================

    if (
        dados.quantidade_minima
        >
        dados.quantidade_maxima
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Quantidade mínima não pode ser "
                "maior que a quantidade máxima."
            )
        )

    # ========================================================
    # 3. VALIDAÇÃO DAS RODADAS
    # ========================================================

    if (
        dados.rodadas_iniciais
        >
        dados.max_rodadas
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Rodadas iniciais não podem ser "
                "maiores que o máximo de rodadas."
            )
        )

    uow = None
    conn = None
    cursor = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()
        conn = uow.connection
        cursor = uow.cursor

        # ====================================================
        # 4. LOCALIZA CONFIGURAÇÃO
        # ====================================================

        cursor.execute(
            """
            SELECT TOP 1
                ID_Configuracao

            FROM dbo.ConfiguracoesInventario

            WHERE
                ClienteId = ?
                AND UPPER(
                    LTRIM(
                        RTRIM(TipoInventario)
                    )
                ) = ?
            """,
            (
                cliente_id,
                tipo_normalizado
            )
        )

        configuracao = (
            cursor.fetchone()
        )

        if not configuracao:

            raise HTTPException(
                status_code=404,
                detail=(
                    "Configuração não encontrada "
                    "para este cliente e tipo "
                    "de inventário."
                )
            )

        # ====================================================
        # 5. ATUALIZA CONFIGURAÇÃO
        # ====================================================

        cursor.execute(
            """
            UPDATE dbo.ConfiguracoesInventario

            SET
                ValidarLocalizacaoEscopo = ?,
                PermitirLocalizacaoVazia = ?,

                CodigoLivre = ?,
                PermitirCodigoNaoCadastrado = ?,
                PermitirItemForaLocalizacao = ?,

                LoteObrigatorioSeExistir = ?,
                ValidarLoteCodigo = ?,
                ValidarLoteLocalizacao = ?,

                QuantidadeMinima = ?,
                QuantidadeMaxima = ?,

                ContagemCega = ?,

                ConsideraLocalizacaoConciliacao = ?,

                RecontagemPorLocalizacao = ?,
                RodadasIniciais = ?,
                MaxRodadas = ?,

                PermitirGestorAntecipado = ?,
                LimiteItensGestorAntecipado = ?,

                DivergenciaBloqueiaFinalizacao = ?,

                Ativa = ?,

                AlteradoPor = ?,
                DataHoraAlteracao = SYSDATETIME()

            WHERE
                ID_Configuracao = ?
            """,
            (
                dados.validar_localizacao_escopo,
                dados.permitir_localizacao_vazia,

                dados.codigo_livre,
                dados.permitir_codigo_nao_cadastrado,
                dados.permitir_item_fora_localizacao,

                dados.lote_obrigatorio_se_existir,
                dados.validar_lote_codigo,
                dados.validar_lote_localizacao,

                dados.quantidade_minima,
                dados.quantidade_maxima,

                dados.contagem_cega,

                dados.considera_localizacao_conciliacao,

                dados.recontagem_por_localizacao,
                dados.rodadas_iniciais,
                dados.max_rodadas,

                dados.permitir_gestor_antecipado,
                dados.limite_itens_gestor_antecipado,

                dados.divergencia_bloqueia_finalizacao,

                dados.ativa,

                usuario,

                configuracao.ID_Configuracao
            )
        )

        if cursor.rowcount == 0:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Não foi possível atualizar "
                    "a configuração."
                )
            )

        # ====================================================
        # 6. COMMIT
        # ====================================================

        uow.commit()

        # ====================================================
        # 7. RETORNA CONFIGURAÇÃO ATUALIZADA
        # ====================================================

        resultado = (
            obter_configuracao_completa(
                cursor=cursor,
                cliente_id=cliente_id,
                tipo_inventario=tipo_normalizado
            )
        )

        return {
            "sucesso":
                True,

            "mensagem":
                "Configuração atualizada com sucesso.",

            "configuracao":
                resultado
        }

    except BusinessRuleViolation as erro:
        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(erro)
        )

    except NotFoundError as erro:
        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=404,
            detail=str(erro)
        )

    except HTTPException:

        if conn:
            uow.rollback()

        raise

    except Exception as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(erro)
        )

    finally:

        if uow:
            uow.close()