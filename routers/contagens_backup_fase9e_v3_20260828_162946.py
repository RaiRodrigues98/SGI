from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from database import get_connection

from dependencies.auth import (
    exigir_permissao,
)

from schemas.contagens import (
    ContagemEntrada,
    EncerrarSessaoEntrada,
    LocalizacaoEntrada,
)

from services.configuracoes_inventario import (
    obter_configuracao_por_inventario,
)


router = APIRouter(
    tags=["Contagens"]
)


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def _normalizar_texto(valor):

    if valor is None:
        return ""

    return str(valor).strip()


def _normalizar_upper(valor):

    return (
        _normalizar_texto(valor)
        .upper()
    )


# ============================================================
# INICIAR LOCALIZAÇÃO
#
# Permissão:
# CONTAGEM_EXECUTAR
#
# Fluxo:
#
# 1. operador bipa localização
# 2. valida inventário
# 3. carrega configuração
# 4. valida rodada
# 5. verifica se é recontagem
# 6. se ValidarLocalizacaoEscopo = TRUE:
#       valida escopo
#    se FALSE:
#       permite localização fora do escopo
# 7. recupera sessão aberta ou cria nova
#
# CONTAGEM CEGA:
# Nenhum saldo esperado é retornado.
# ============================================================

@router.post(
    "/localizacoes/iniciar",
    dependencies=[
        Depends(
            exigir_permissao(
                "CONTAGEM_EXECUTAR"
            )
        )
    ]
)
def iniciar_localizacao(
    dados: LocalizacaoEntrada
):

    localizacao = _normalizar_upper(dados.localizacao)

    if not localizacao:
        raise HTTPException(
            status_code=400,
            detail="Localização obrigatória."
        )

    if dados.id_inventario <= 0:
        raise HTTPException(
            status_code=400,
            detail="Inventário inválido."
        )

    if dados.id_rodada <= 0:
        raise HTTPException(
            status_code=400,
            detail="Rodada inválida."
        )

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # 1. INVENTÁRIO
        cursor.execute(
            """
            SELECT
                ID_Inventario,
                CodigoInventario,
                Tipo,
                ClienteId,
                RodadaAtual,
                Status
            FROM dbo.Inventarios WITH (UPDLOCK, HOLDLOCK)
            WHERE ID_Inventario = ?
            """,
            dados.id_inventario
        )

        inventario = cursor.fetchone()

        if not inventario:
            raise HTTPException(
                status_code=404,
                detail="Inventário não encontrado."
            )

        tipo_inventario = _normalizar_upper(inventario.Tipo)
        status_inventario = _normalizar_upper(inventario.Status)

        if status_inventario in ("FINALIZADO", "CANCELADO"):
            raise HTTPException(
                status_code=400,
                detail="O inventário não permite novas contagens."
            )

        # 2. CONFIGURAÇÃO
        configuracao = obter_configuracao_por_inventario(
            cursor=cursor,
            id_inventario=dados.id_inventario
        )

        validar_localizacao_escopo = bool(
            configuracao["validar_localizacao_escopo"]
        )
        contagem_cega = bool(
            configuracao["contagem_cega"]
        )
        permitir_reabertura_localizacao = bool(
            configuracao.get(
                "permitir_reabertura_localizacao",
                False
            )
        )

        # 3. RODADA
        cursor.execute(
            """
            SELECT
                ID_Rodada,
                ID_Inventario,
                NumeroRodada,
                Status
            FROM dbo.RodadasInventario WITH (UPDLOCK, HOLDLOCK)
            WHERE
                ID_Rodada = ?
                AND ID_Inventario = ?
            """,
            (dados.id_rodada, dados.id_inventario)
        )

        rodada = cursor.fetchone()

        if not rodada:
            raise HTTPException(
                status_code=404,
                detail="Rodada não encontrada para este inventário."
            )

        status_rodada = _normalizar_upper(rodada.Status)

        if status_rodada in ("FINALIZADA", "CANCELADA"):
            raise HTTPException(
                status_code=400,
                detail="A rodada não permite novas contagens."
            )

        # 4. IDENTIFICA RECONTAGEM
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM dbo.RodadaItens
            WHERE
                ID_Inventario = ?
                AND ID_Rodada = ?
            """,
            (dados.id_inventario, dados.id_rodada)
        )

        rodada_recontagem = int(cursor.fetchone()[0]) > 0

        # 5. VALIDAÇÃO DA LOCALIZAÇÃO
        if validar_localizacao_escopo:
            if rodada_recontagem:
                cursor.execute(
                    """
                    SELECT TOP 1
                        ID_RodadaLocalizacao,
                        Localizacao,
                        Status
                    FROM dbo.RodadaLocalizacoes
                    WHERE
                        ID_Inventario = ?
                        AND ID_Rodada = ?
                        AND UPPER(LTRIM(RTRIM(Localizacao))) = ?
                    """,
                    (dados.id_inventario, dados.id_rodada, localizacao)
                )

                rodada_localizacao = cursor.fetchone()

                if not rodada_localizacao:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Esta localização não pertence "
                            "à recontagem desta rodada."
                        )
                    )

                status_localizacao = _normalizar_upper(
                    rodada_localizacao.Status
                )

                if (
                    status_localizacao == "CONCLUIDA"
                    and not permitir_reabertura_localizacao
                ):
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Esta localização já foi concluída nesta rodada "
                            "e a configuração não permite reabertura."
                        )
                    )
            else:
                cursor.execute(
                    """
                    SELECT TOP 1
                        ID_EscopoLocalizacao,
                        Selecionado
                    FROM dbo.InventarioEscopoLocalizacoes
                    WHERE
                        ID_Inventario = ?
                        AND UPPER(LTRIM(RTRIM(Localizacao))) = ?
                    """,
                    (dados.id_inventario, localizacao)
                )

                escopo = cursor.fetchone()

                if not escopo:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Esta localização não pertence "
                            "ao escopo do inventário."
                        )
                    )

                if not bool(escopo.Selecionado):
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Esta localização não está ativa "
                            "no escopo do inventário."
                        )
                    )

        # 6. ÚLTIMA SESSÃO VÁLIDA
        cursor.execute(
            """
            SELECT TOP 1
                ID_Sessao,
                Status,
                DataHoraInicio,
                DataHoraFim,
                ValidaParaConsolidacao
            FROM dbo.SessoesContagem WITH (UPDLOCK, HOLDLOCK)
            WHERE
                ID_Inventario = ?
                AND ID_Rodada = ?
                AND UPPER(LTRIM(RTRIM(Localizacao))) = ?
                AND ValidaParaConsolidacao = 1
            ORDER BY ID_Sessao DESC
            """,
            (dados.id_inventario, dados.id_rodada, localizacao)
        )

        existente = cursor.fetchone()
        sessao_reaberta = False

        if existente:
            status_sessao_existente = _normalizar_upper(
                existente.Status
            )

            if status_sessao_existente == "ABERTA":
                return {
                    "sucesso": True,
                    "id_sessao": existente.ID_Sessao,
                    "id_inventario": dados.id_inventario,
                    "codigo_inventario": inventario.CodigoInventario,
                    "tipo_inventario": tipo_inventario,
                    "id_rodada": dados.id_rodada,
                    "numero_rodada": rodada.NumeroRodada,
                    "tipo_operacao": (
                        "RECONTAGEM" if rodada_recontagem else "COMPLETA"
                    ),
                    "localizacao": localizacao,
                    "status_sessao": "ABERTA",
                    "contagem_cega": contagem_cega,
                    "validar_localizacao_escopo": validar_localizacao_escopo,
                    "permitir_reabertura_localizacao": (
                        permitir_reabertura_localizacao
                    ),
                    "sessao_existente": True,
                    "sessao_reaberta": False,
                    "data_hora_inicio": existente.DataHoraInicio,
                    "mensagem": (
                        "Localização pronta para contagem. "
                        "Sessão aberta recuperada."
                    )
                }

            if status_sessao_existente == "ENCERRADA":
                if not permitir_reabertura_localizacao:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Esta localização já foi concluída nesta rodada "
                            "e a configuração não permite reabertura."
                        )
                    )

                cursor.execute(
    """
    UPDATE dbo.SessoesContagem

    SET
        ValidaParaConsolidacao = 0

    WHERE
        ID_Inventario = ?
        AND ID_Rodada = ?

        AND UPPER(
            LTRIM(
                RTRIM(Localizacao)
            )
        ) =
        UPPER(
            LTRIM(
                RTRIM(?)
            )
        )

        AND Status = 'ENCERRADA'
        AND ValidaParaConsolidacao = 1
    """,
    (
        dados.id_inventario,
        dados.id_rodada,
        localizacao
    )
)

        # 7. NOVA SESSÃO
        try:
            cursor.execute(
                """
                INSERT INTO dbo.SessoesContagem
                (
                    ID_Inventario,
                    ID_Rodada,
                    Localizacao,
                    Status,
                    LocalizacaoVazia,
                    ValidaParaConsolidacao
                )
                OUTPUT
                    INSERTED.ID_Sessao,
                    INSERTED.DataHoraInicio
                VALUES
                (?, ?, ?, 'ABERTA', 0, 1)
                """,
                (dados.id_inventario, dados.id_rodada, localizacao)
            )
            nova_sessao = cursor.fetchone()

        except Exception as erro_insert:
            mensagem_erro = str(erro_insert)
            if "2601" in mensagem_erro or "2627" in mensagem_erro:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Já existe uma sessão aberta para este inventário, "
                        "rodada e localização. Atualize a operação e tente "
                        "novamente."
                    )
                )
            raise

        # 8. ESTADO OPERACIONAL DA LOCALIZAÇÃO NA RECONTAGEM
        if rodada_recontagem:
            cursor.execute(
                """
                UPDATE dbo.RodadaLocalizacoes
                SET Status = 'EM_CONTAGEM'
                WHERE
                    ID_Inventario = ?
                    AND ID_Rodada = ?
                    AND UPPER(LTRIM(RTRIM(Localizacao))) = ?
                """,
                (dados.id_inventario, dados.id_rodada, localizacao)
            )

        conn.commit()

        return {
            "sucesso": True,
            "id_sessao": nova_sessao.ID_Sessao,
            "id_inventario": dados.id_inventario,
            "codigo_inventario": inventario.CodigoInventario,
            "tipo_inventario": tipo_inventario,
            "id_rodada": dados.id_rodada,
            "numero_rodada": rodada.NumeroRodada,
            "tipo_operacao": (
                "RECONTAGEM" if rodada_recontagem else "COMPLETA"
            ),
            "localizacao": localizacao,
            "status_sessao": "ABERTA",
            "contagem_cega": contagem_cega,
            "validar_localizacao_escopo": validar_localizacao_escopo,
            "permitir_reabertura_localizacao": (
                permitir_reabertura_localizacao
            ),
            "sessao_existente": False,
            "sessao_reaberta": sessao_reaberta,
            "data_hora_inicio": nova_sessao.DataHoraInicio,
            "mensagem": (
                "Localização reaberta para nova contagem."
                if sessao_reaberta
                else "Localização pronta para contagem."
            )
        }

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
# ENCERRAR LOCALIZAÇÃO
#
# Permissão:
# CONTAGEM_EXECUTAR
# ============================================================

@router.post(
    "/localizacoes/encerrar",
    dependencies=[
        Depends(
            exigir_permissao(
                "CONTAGEM_EXECUTAR"
            )
        )
    ]
)
def encerrar_localizacao(
    dados: EncerrarSessaoEntrada
):

    if dados.id_sessao <= 0:

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
        # 1. SESSÃO
        #
        # UPDLOCK + HOLDLOCK:
        # serializa o encerramento com o salvamento de contagens.
        # Enquanto esta transação estiver validando/encerrando,
        # outra transação não consegue alterar a mesma sessão.
        # ====================================================

        cursor.execute(
            """
            SELECT
                S.ID_Sessao,
                S.ID_Inventario,
                S.ID_Rodada,
                S.Localizacao,
                S.Status,
                S.LocalizacaoVazia,

                R.NumeroRodada

            FROM dbo.SessoesContagem S WITH (UPDLOCK, HOLDLOCK)

            INNER JOIN dbo.RodadasInventario R
                ON R.ID_Rodada =
                   S.ID_Rodada

            WHERE S.ID_Sessao = ?
            """,
            dados.id_sessao
        )

        sessao = (
            cursor.fetchone()
        )

        if not sessao:

            raise HTTPException(
                status_code=404,
                detail="Sessão não encontrada."
            )

        if (
            _normalizar_upper(
                sessao.Status
            )
            == "ENCERRADA"
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "Esta sessão já está encerrada."
                )
            )

        # ====================================================
        # 2. CONFIGURAÇÃO
        # ====================================================

        configuracao = (
            obter_configuracao_por_inventario(
                cursor=cursor,
                id_inventario=(
                    sessao.ID_Inventario
                )
            )
        )

        permitir_localizacao_vazia = bool(
            configuracao[
                "permitir_localizacao_vazia"
            ]
        )

        # ====================================================
        # 3. CONTAGENS ATIVAS DA SESSÃO
        # ====================================================

        cursor.execute(
            """
            SELECT COUNT(*)

            FROM dbo.Contagens

            WHERE
                ID_Sessao = ?
                AND Status = 'ATIVA'
            """,
            dados.id_sessao
        )

        total_contagens = int(
            cursor.fetchone()[0]
        )

        # ====================================================
        # 4. LOCALIZAÇÃO VAZIA
        # ====================================================

        if (
            total_contagens == 0
            and
            dados.localizacao_vazia
            and
            not permitir_localizacao_vazia
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "A configuração deste inventário "
                    "não permite confirmar "
                    "localização vazia."
                )
            )

        if (
            total_contagens == 0
            and
            not dados.localizacao_vazia
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "Nenhum item foi registrado nesta "
                    "localização. Se a posição estiver "
                    "fisicamente vazia, envie "
                    "localizacao_vazia=true para confirmar."
                )
            )

        if (
            total_contagens > 0
            and
            dados.localizacao_vazia
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "A localização possui itens contados "
                    "e não pode ser confirmada como vazia."
                )
            )

        # ====================================================
        # 5. ENCERRA SESSÃO
        # ====================================================

        cursor.execute(
            """
            UPDATE dbo.SessoesContagem

            SET
                Status = 'ENCERRADA',

                DataHoraFim =
                    SYSDATETIME(),

                LocalizacaoVazia = ?

            WHERE
                ID_Sessao = ?
                AND Status = 'ABERTA'
            """,
            (
                (
                    1
                    if dados.localizacao_vazia
                    else 0
                ),
                dados.id_sessao
            )
        )

        if cursor.rowcount == 0:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Não foi possível encerrar "
                    "a sessão."
                )
            )

        # ====================================================
        # 6. VERIFICA RodadaLocalizacoes
        # ====================================================

        cursor.execute(
            """
            SELECT TOP 1
                ID_RodadaLocalizacao,
                Status

            FROM dbo.RodadaLocalizacoes

            WHERE
                ID_Inventario = ?
                AND ID_Rodada = ?

                AND UPPER(
                    LTRIM(
                        RTRIM(Localizacao)
                    )
                ) =
                UPPER(
                    LTRIM(
                        RTRIM(?)
                    )
                )
            """,
            (
                sessao.ID_Inventario,
                sessao.ID_Rodada,
                sessao.Localizacao
            )
        )

        rodada_localizacao = (
            cursor.fetchone()
        )

        # ====================================================
        # 7. MARCA CONCLUÍDA
        # ====================================================

        if rodada_localizacao:

            cursor.execute(
                """
                UPDATE dbo.RodadaLocalizacoes

                SET
                    Status = 'CONCLUIDA'

                WHERE
                    ID_RodadaLocalizacao = ?
                """,
                (
                    rodada_localizacao
                    .ID_RodadaLocalizacao
                )
            )

        conn.commit()

        return {
            "sucesso":
                True,

            "id_sessao":
                sessao.ID_Sessao,

            "id_inventario":
                sessao.ID_Inventario,

            "id_rodada":
                sessao.ID_Rodada,

            "numero_rodada":
                sessao.NumeroRodada,

            "localizacao":
                sessao.Localizacao,

            "total_contagens":
                total_contagens,

            "localizacao_vazia":
                dados.localizacao_vazia,

            "status":
                "ENCERRADA",

            "status_localizacao_rodada":
                (
                    "CONCLUIDA"
                    if rodada_localizacao
                    else None
                ),

            "mensagem":
                (
                    "Localização vazia confirmada "
                    "e encerrada com sucesso."
                    if dados.localizacao_vazia
                    else
                    "Localização encerrada com sucesso."
                )
        }

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
# SALVAR CONTAGEM
#
# Permissão:
# CONTAGEM_EXECUTAR
#
# As regras de código, lote e quantidade que já estavam
# funcionando permanecem preservadas.
# ============================================================

@router.post(
    "/contagens",
    dependencies=[
        Depends(
            exigir_permissao(
                "CONTAGEM_EXECUTAR"
            )
        )
    ]
)
def salvar_contagem(
    contagem: ContagemEntrada
):

    # ========================================================
    # 1. NORMALIZAÇÃO
    # ========================================================

    codigo = (
        _normalizar_texto(
            contagem.codigo
        )
    )

    lote = (
        _normalizar_texto(
            contagem.lote
        )
        if contagem.lote
        else None
    )

    if contagem.id_sessao <= 0:

        raise HTTPException(
            status_code=400,
            detail="Sessão inválida."
        )

    if not codigo:

        raise HTTPException(
            status_code=400,
            detail="Código obrigatório."
        )

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        # ====================================================
        # 2. SESSÃO + INVENTÁRIO + RODADA
        #
        # UPDLOCK + HOLDLOCK:
        # mantém a linha da sessão protegida até COMMIT/ROLLBACK,
        # impedindo corrida entre salvar contagem e encerrar sessão.
        # ====================================================

        cursor.execute(
            """
            SELECT
                S.ID_Sessao,
                S.ID_Inventario,
                S.ID_Rodada,
                S.Localizacao,
                S.Status AS StatusSessao,

                I.Tipo AS TipoInventario,
                I.ClienteId,
                I.Status AS StatusInventario,

                R.NumeroRodada,
                R.Status AS StatusRodada

            FROM dbo.SessoesContagem S WITH (UPDLOCK, HOLDLOCK)

            INNER JOIN dbo.Inventarios I
                ON I.ID_Inventario =
                   S.ID_Inventario

            INNER JOIN dbo.RodadasInventario R
                ON R.ID_Rodada =
                   S.ID_Rodada

            WHERE S.ID_Sessao = ?
            """,
            contagem.id_sessao
        )

        sessao = (
            cursor.fetchone()
        )

        if not sessao:

            raise HTTPException(
                status_code=404,
                detail=(
                    "Sessão de contagem "
                    "não encontrada."
                )
            )

        # ====================================================
        # 3. STATUS OPERACIONAL
        # ====================================================

        if (
            _normalizar_upper(
                sessao.StatusSessao
            )
            != "ABERTA"
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "A sessão de contagem "
                    "não está aberta."
                )
            )

        if (
            _normalizar_upper(
                sessao.StatusInventario
            )
            in (
                "FINALIZADO",
                "CANCELADO"
            )
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "O inventário não permite "
                    "novas contagens."
                )
            )

        if (
            _normalizar_upper(
                sessao.StatusRodada
            )
            in (
                "FINALIZADA",
                "CANCELADA"
            )
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "A rodada não permite "
                    "novas contagens."
                )
            )

        # ====================================================
        # 4. CONFIGURAÇÃO
        # ====================================================

        configuracao = (
            obter_configuracao_por_inventario(
                cursor=cursor,
                id_inventario=(
                    sessao.ID_Inventario
                )
            )
        )

        # ====================================================
        # 5. QUANTIDADE
        # ====================================================

        quantidade = float(
            contagem.quantidade
        )

        quantidade_minima = float(
            configuracao[
                "quantidade_minima"
            ]
        )

        quantidade_maxima = float(
            configuracao[
                "quantidade_maxima"
            ]
        )

        if quantidade < quantidade_minima:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Quantidade abaixo do mínimo permitido. "
                    f"Mínimo: {quantidade_minima:g}."
                )
            )

        if quantidade > quantidade_maxima:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Quantidade acima do máximo permitido. "
                    f"Máximo: {quantidade_maxima:g}."
                )
            )

        # ====================================================
        # 6. VERIFICA CÓDIGO NO SNAPSHOT
        # ====================================================

        cursor.execute(
            """
            SELECT COUNT(*)

            FROM dbo.InventarioEstoqueSnapshot

            WHERE
                ID_Inventario = ?

                AND LTRIM(
                    RTRIM(Codigo)
                ) = ?
            """,
            (
                sessao.ID_Inventario,
                codigo
            )
        )

        codigo_existe = (
            cursor.fetchone()[0] > 0
        )

        # ====================================================
        # 7. REGRA DE CÓDIGO
        # ====================================================

        if (
            not codigo_existe
            and
            (
                not bool(
                    configuracao[
                        "codigo_livre"
                    ]
                )
                or
                not bool(
                    configuracao[
                        "permitir_codigo_nao_cadastrado"
                    ]
                )
            )
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "Código não cadastrado no estoque "
                    "deste inventário."
                )
            )

        # ====================================================
        # 8. VERIFICA SE CÓDIGO POSSUI LOTE
        # ====================================================

        codigo_possui_lote = False

        if codigo_existe:

            cursor.execute(
                """
                SELECT COUNT(*)

                FROM dbo.InventarioEstoqueSnapshot

                WHERE
                    ID_Inventario = ?

                    AND LTRIM(
                        RTRIM(Codigo)
                    ) = ?

                    AND NULLIF(
                        LTRIM(
                            RTRIM(Lote)
                        ),
                        ''
                    ) IS NOT NULL
                """,
                (
                    sessao.ID_Inventario,
                    codigo
                )
            )

            codigo_possui_lote = (
                cursor.fetchone()[0] > 0
            )

        # ====================================================
        # 9. LOTE OBRIGATÓRIO
        # ====================================================

        if (
            bool(
                configuracao[
                    "lote_obrigatorio_se_existir"
                ]
            )
            and
            codigo_possui_lote
            and
            not lote
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "Este código possui lote. "
                    "Bipe o lote antes de informar "
                    "a quantidade."
                )
            )

        # ====================================================
        # 10. VALIDA CÓDIGO + LOTE
        # ====================================================

        if (
            lote
            and
            codigo_existe
            and
            bool(
                configuracao[
                    "validar_lote_codigo"
                ]
            )
        ):

            cursor.execute(
                """
                SELECT COUNT(*)

                FROM dbo.InventarioEstoqueSnapshot

                WHERE
                    ID_Inventario = ?

                    AND LTRIM(
                        RTRIM(Codigo)
                    ) = ?

                    AND ISNULL(
                        LTRIM(
                            RTRIM(Lote)
                        ),
                        ''
                    ) = ?
                """,
                (
                    sessao.ID_Inventario,
                    codigo,
                    lote
                )
            )

            lote_codigo_valido = (
                cursor.fetchone()[0] > 0
            )

            if not lote_codigo_valido:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "O lote informado não pertence "
                        "ao código bipado."
                    )
                )

        # ====================================================
        # 11. VALIDA LOCALIZAÇÃO + CÓDIGO + LOTE
        #
        # Precedência das configurações:
        # - ValidarLoteLocalizacao = TRUE
        # - PermitirItemForaLocalizacao = FALSE
        #     => exige Localização + Código + Lote no snapshot.
        #
        # Se PermitirItemForaLocalizacao = TRUE, a divergência
        # física é registrada e a análise decide a classificação.
        # ====================================================

        if (
            codigo_existe
            and
            lote
            and
            bool(
                configuracao[
                    "validar_lote_localizacao"
                ]
            )
            and
            not bool(
                configuracao[
                    "permitir_item_fora_localizacao"
                ]
            )
        ):

            cursor.execute(
                """
                SELECT COUNT(*)

                FROM dbo.InventarioEstoqueSnapshot

                WHERE
                    ID_Inventario = ?

                    AND UPPER(
                        LTRIM(
                            RTRIM(Localizacao)
                        )
                    ) =
                    UPPER(
                        LTRIM(
                            RTRIM(?)
                        )
                    )

                    AND LTRIM(
                        RTRIM(Codigo)
                    ) = ?

                    AND ISNULL(
                        LTRIM(
                            RTRIM(Lote)
                        ),
                        ''
                    ) = ?
                """,
                (
                    sessao.ID_Inventario,
                    sessao.Localizacao,
                    codigo,
                    lote
                )
            )

            valido = (
                cursor.fetchone()[0] > 0
            )

            if not valido:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "O Código + Lote informado "
                        "não pertence à localização "
                        "que está sendo contada."
                    )
                )

        # ====================================================
        # 12. ITEM FORA DA LOCALIZAÇÃO
        # ====================================================

        if (
            codigo_existe
            and
            not bool(
                configuracao[
                    "permitir_item_fora_localizacao"
                ]
            )
        ):

            if lote:

                cursor.execute(
                    """
                    SELECT COUNT(*)

                    FROM dbo.InventarioEstoqueSnapshot

                    WHERE
                        ID_Inventario = ?

                        AND UPPER(
                            LTRIM(
                                RTRIM(Localizacao)
                            )
                        ) =
                        UPPER(
                            LTRIM(
                                RTRIM(?)
                            )
                        )

                        AND LTRIM(
                            RTRIM(Codigo)
                        ) = ?

                        AND ISNULL(
                            LTRIM(
                                RTRIM(Lote)
                            ),
                            ''
                        ) = ?
                    """,
                    (
                        sessao.ID_Inventario,
                        sessao.Localizacao,
                        codigo,
                        lote
                    )
                )

            else:

                cursor.execute(
                    """
                    SELECT COUNT(*)

                    FROM dbo.InventarioEstoqueSnapshot

                    WHERE
                        ID_Inventario = ?

                        AND UPPER(
                            LTRIM(
                                RTRIM(Localizacao)
                            )
                        ) =
                        UPPER(
                            LTRIM(
                                RTRIM(?)
                            )
                        )

                        AND LTRIM(
                            RTRIM(Codigo)
                        ) = ?
                    """,
                    (
                        sessao.ID_Inventario,
                        sessao.Localizacao,
                        codigo
                    )
                )

            item_na_localizacao = (
                cursor.fetchone()[0] > 0
            )

            if not item_na_localizacao:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Este item não pertence à "
                        "localização que está sendo contada."
                    )
                )

        # ====================================================
        # 13. SALVA CONTAGEM
        # ====================================================

        cursor.execute(
            """
            INSERT INTO dbo.Contagens
            (
                ID_Sessao,
                Codigo,
                Lote,
                Quantidade,
                Status
            )

            OUTPUT
                INSERTED.ID_Contagem,
                INSERTED.DataHora,
                INSERTED.Status

            VALUES
            (
                ?,
                ?,
                ?,
                ?,
                'ATIVA'
            )
            """,
            (
                contagem.id_sessao,
                codigo,
                lote,
                contagem.quantidade
            )
        )

        registro = (
            cursor.fetchone()
        )

        conn.commit()

        return {
            "sucesso":
                True,

            "id_contagem":
                registro.ID_Contagem,

            "id_sessao":
                sessao.ID_Sessao,

            "id_inventario":
                sessao.ID_Inventario,

            "id_rodada":
                sessao.ID_Rodada,

            "numero_rodada":
                sessao.NumeroRodada,

            "tipo_inventario":
                sessao.TipoInventario,

            "localizacao":
                sessao.Localizacao,

            "codigo":
                codigo,

            "lote":
                lote,

            "quantidade":
                quantidade,

            "status":
                registro.Status,

            "data_hora":
                registro.DataHora,

            "contagem_cega":
                bool(
                    configuracao[
                        "contagem_cega"
                    ]
                ),

            "mensagem":
                "Contagem salva com sucesso."
        }

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
# LISTAR CONTAGENS DA SESSÃO
#
# Permissão:
# CONTAGEM_EXECUTAR
#
# Necessário durante o fluxo operacional para o operador
# visualizar os registros realizados na sessão atual.
# ============================================================

@router.get(
    "/sessoes/{id_sessao}/contagens",
    dependencies=[
        Depends(
            exigir_permissao(
                "CONTAGEM_EXECUTAR"
            )
        )
    ]
)
def listar_contagens_sessao(
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
        # SESSÃO
        # ====================================================

        cursor.execute(
            """
            SELECT
                ID_Sessao,
                ID_Inventario,
                ID_Rodada,
                Localizacao,
                Status,
                LocalizacaoVazia

            FROM dbo.SessoesContagem

            WHERE ID_Sessao = ?
            """,
            id_sessao
        )

        sessao = (
            cursor.fetchone()
        )

        if not sessao:

            raise HTTPException(
                status_code=404,
                detail="Sessão não encontrada."
            )

        configuracao = (
            obter_configuracao_por_inventario(
                cursor=cursor,
                id_inventario=(
                    sessao.ID_Inventario
                )
            )
        )

        # ====================================================
        # CONTAGENS
        # ====================================================

        cursor.execute(
            """
            SELECT
                C.ID_Contagem,
                C.ID_Sessao,
                C.Codigo,
                C.Lote,
                C.Quantidade,
                C.Status,
                C.DataHora,

                MAX(
                    E.Descricao
                ) AS Produto,

                MAX(
                    E.Unidade
                ) AS Unidade,

                MAX(
                    E.Categoria
                ) AS Categoria

            FROM dbo.Contagens C

            LEFT JOIN dbo.InventarioEstoqueSnapshot E
                ON E.ID_Inventario = ?

               AND LTRIM(
                    RTRIM(E.Codigo)
               ) =
               LTRIM(
                    RTRIM(C.Codigo)
               )

               AND ISNULL(
                    LTRIM(
                        RTRIM(E.Lote)
                    ),
                    ''
               ) =
               ISNULL(
                    LTRIM(
                        RTRIM(C.Lote)
                    ),
                    ''
               )

            WHERE
                C.ID_Sessao = ?
                AND C.Status = 'ATIVA'

            GROUP BY
                C.ID_Contagem,
                C.ID_Sessao,
                C.Codigo,
                C.Lote,
                C.Quantidade,
                C.Status,
                C.DataHora

            ORDER BY
                C.ID_Contagem DESC
            """,
            (
                sessao.ID_Inventario,
                id_sessao
            )
        )

        linhas = (
            cursor.fetchall()
        )

        contagens = []

        for linha in linhas:

            contagens.append(
                {
                    "id_contagem":
                        linha.ID_Contagem,

                    "id_sessao":
                        linha.ID_Sessao,

                    "id_inventario":
                        sessao.ID_Inventario,

                    "id_rodada":
                        sessao.ID_Rodada,

                    "localizacao":
                        sessao.Localizacao,

                    "localizacao_vazia":
                        bool(
                            sessao.LocalizacaoVazia
                        ),

                    "codigo":
                        linha.Codigo,

                    "produto":
                        linha.Produto,

                    "lote":
                        linha.Lote,

                    "unidade":
                        linha.Unidade,

                    "categoria":
                        linha.Categoria,

                    "quantidade":
                        float(
                            linha.Quantidade
                        ),

                    "status":
                        linha.Status,

                    "data_hora":
                        linha.DataHora
                }
            )

        return {
            "id_sessao":
                sessao.ID_Sessao,

            "id_inventario":
                sessao.ID_Inventario,

            "id_rodada":
                sessao.ID_Rodada,

            "localizacao":
                sessao.Localizacao,

            "status_sessao":
                sessao.Status,

            "localizacao_vazia":
                bool(
                    sessao.LocalizacaoVazia
                ),

            "contagem_cega":
                bool(
                    configuracao[
                        "contagem_cega"
                    ]
                ),

            "total_registros":
                len(contagens),

            "contagens":
                contagens
        }

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
# CANCELAR CONTAGEM
#
# Permissão:
# CONTAGEM_CANCELAR
# ============================================================

@router.patch(
    "/contagens/{id_contagem}/cancelar",
    dependencies=[
        Depends(
            exigir_permissao(
                "CONTAGEM_CANCELAR"
            )
        )
    ]
)
def cancelar_contagem(
    id_contagem: int
):

    if id_contagem <= 0:

        raise HTTPException(
            status_code=400,
            detail="Contagem inválida."
        )

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                C.ID_Contagem,
                C.ID_Sessao,
                C.Status,

                S.Status AS StatusSessao

            FROM dbo.Contagens C

            INNER JOIN dbo.SessoesContagem S
                ON S.ID_Sessao =
                   C.ID_Sessao

            WHERE C.ID_Contagem = ?
            """,
            id_contagem
        )

        registro = (
            cursor.fetchone()
        )

        if not registro:

            raise HTTPException(
                status_code=404,
                detail="Contagem não encontrada."
            )

        if (
            _normalizar_upper(
                registro.Status
            )
            == "CANCELADA"
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "Esta contagem já está cancelada."
                )
            )

        if (
            _normalizar_upper(
                registro.StatusSessao
            )
            != "ABERTA"
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "Não é possível cancelar uma "
                    "contagem de uma localização "
                    "já encerrada."
                )
            )

        cursor.execute(
            """
            UPDATE dbo.Contagens

            SET
                Status = 'CANCELADA',
                DataHoraCancelamento =
                    SYSDATETIME()

            WHERE
                ID_Contagem = ?
                AND Status = 'ATIVA'
            """,
            id_contagem
        )

        if cursor.rowcount == 0:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Não foi possível cancelar "
                    "a contagem."
                )
            )

        conn.commit()

        return {
            "sucesso":
                True,

            "id_contagem":
                id_contagem,

            "status":
                "CANCELADA",

            "mensagem":
                "Contagem cancelada com sucesso."
        }

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
# LISTAR SESSÕES
#
# Permissão:
# ANALISE_VISUALIZAR
#
# Esta consulta possui visão global das sessões de contagem
# e não faz parte da operação básica de bipagem do operador.
# ============================================================

@router.get(
    "/sessoes",
    dependencies=[
        Depends(
            exigir_permissao(
                "ANALISE_VISUALIZAR"
            )
        )
    ]
)
def listar_sessoes():

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                S.ID_Sessao,
                S.ID_Inventario,
                S.ID_Rodada,
                S.Localizacao,
                S.Status,
                S.LocalizacaoVazia,
                S.DataHoraInicio,
                S.DataHoraFim,

                ISNULL(
                    SUM(
                        CASE
                            WHEN C.Status = 'ATIVA'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS ItensRegistrados,

                ISNULL(
                    SUM(
                        CASE
                            WHEN C.Status = 'ATIVA'
                            THEN C.Quantidade
                            ELSE 0
                        END
                    ),
                    0
                ) AS QuantidadeTotal

            FROM dbo.SessoesContagem S

            LEFT JOIN dbo.Contagens C
                ON C.ID_Sessao =
                   S.ID_Sessao

            GROUP BY
                S.ID_Sessao,
                S.ID_Inventario,
                S.ID_Rodada,
                S.Localizacao,
                S.Status,
                S.LocalizacaoVazia,
                S.DataHoraInicio,
                S.DataHoraFim

            ORDER BY
                S.ID_Sessao DESC
            """
        )

        linhas = (
            cursor.fetchall()
        )

        resultado = []

        for linha in linhas:

            resultado.append(
                {
                    "id_sessao":
                        linha.ID_Sessao,

                    "id_inventario":
                        linha.ID_Inventario,

                    "id_rodada":
                        linha.ID_Rodada,

                    "localizacao":
                        linha.Localizacao,

                    "status":
                        linha.Status,

                    "localizacao_vazia":
                        bool(
                            linha.LocalizacaoVazia
                        ),

                    "data_hora_inicio":
                        linha.DataHoraInicio,

                    "data_hora_fim":
                        linha.DataHoraFim,

                    "itens_registrados":
                        int(
                            linha.ItensRegistrados
                        ),

                    "quantidade_total":
                        float(
                            linha.QuantidadeTotal
                        )
                }
            )

        return resultado

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
