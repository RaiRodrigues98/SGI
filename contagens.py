from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
)
from domain.exceptions import BusinessRuleViolation, NotFoundError

from infrastructure.database.unit_of_work import SqlServerUnitOfWork

from services.rotativo_fluxo import (
    resolver_localizacao_ciclo_operacional,
    iniciar_localizacao_rotativo,
)

from services.rotativo_cobertura import (
    registrar_conclusao_localizacao_rotativo,
    processar_inteligencia_conclusao_rotativo_background,
)

from dependencies.auth import (
    exigir_permissao,
    obter_usuario_atual,
)

from schemas.contagens import (
    ContagemEntrada,
    EncerrarSessaoEntrada,
    LocalizacaoEntrada,
)

from services.configuracoes_inventario import (
    obter_configuracao_por_inventario,
)


from services.notificacoes import (
    criar_por_permissao,
)

from services.rodadas_service import (
    visualizar_proxima_rodada,
)

from services.rodadas.lifecycle import (
    _finalizar_rodada_atual,
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

def _iniciar_ciclo_rotativo_da_localizacao(
    cursor,
    inventario,
    id_rodada: int,
    localizacao: str
):
    """
    Integra a abertura operacional da localiza??o
    com o ciclo ROTATIVO.

    OFICIAL n?o sofre nenhuma altera??o.

    N?o realiza commit/rollback.
    """

    tipo = _normalizar_upper(
        inventario.Tipo
    )

    if tipo != "ROTATIVO":
        return None

    ciclo_localizacao = (
        resolver_localizacao_ciclo_operacional(
            cursor=cursor,
            cliente_id=inventario.ClienteId,
            armazem=inventario.cArmazem,
            localizacao=localizacao
        )
    )

    return iniciar_localizacao_rotativo(
        cursor=cursor,
        id_ciclo_localizacao=(
            ciclo_localizacao.ID_CicloLocalizacao
        ),
        id_inventario=inventario.ID_Inventario,
        id_rodada=id_rodada,
        usuario=None
    )


@router.post(
    "/localizacoes/iniciar"
)
def iniciar_localizacao(
    dados: LocalizacaoEntrada,
    usuario_atual=Depends(
        exigir_permissao(
            "CONTAGEM_EXECUTAR"
        )
    )
):

    usuario_id = int(
        usuario_atual["id_usuario"]
    )

    usuario_login = str(
        usuario_atual["login"]
    ).strip()

    usuario_nome = str(
        usuario_atual.get("nome")
        or usuario_login
    ).strip()

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

    uow = None
    conn = None
    cursor = None

    try:
        uow = SqlServerUnitOfWork()
        uow.open()
        conn = uow.connection
        cursor = uow.cursor

        # 1. INVENTÁRIO
        cursor.execute(
            """
            SELECT
                ID_Inventario,
                CodigoInventario,
                Tipo,
                ClienteId,
                cArmazem,
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
                ValidaParaConsolidacao,
                ID_UsuarioAbertura,
                UsuarioAberturaLogin,
                UsuarioAberturaNome
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

                operador_id = (
                    int(existente.ID_UsuarioAbertura)
                    if existente.ID_UsuarioAbertura is not None
                    else None
                )

                operador_login = (
                    str(existente.UsuarioAberturaLogin).strip()
                    if existente.UsuarioAberturaLogin
                    else None
                )

                operador_nome = (
                    str(existente.UsuarioAberturaNome).strip()
                    if existente.UsuarioAberturaNome
                    else operador_login
                )

                mesma_pessoa = (
                    operador_id == usuario_id
                    if operador_id is not None
                    else (
                        operador_login is not None
                        and operador_login.casefold()
                        == usuario_login.casefold()
                    )
                )

                if not mesma_pessoa:
                    identificacao = (
                        operador_nome
                        or "outro usuário"
                    )

                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"A localização {localizacao} "
                            "já está em contagem por "
                            f"{identificacao}."
                        )
                    )

                # ====================================================
                # INTEGRACAO CICLO ROTATIVO - SESSAO EXISTENTE
                # ====================================================

                if (
                    tipo_inventario == "ROTATIVO"
                    and not rodada_recontagem
                ):

                    _iniciar_ciclo_rotativo_da_localizacao(
                        cursor=cursor,
                        inventario=inventario,
                        id_rodada=dados.id_rodada,
                        localizacao=localizacao
                    )

                    uow.commit()

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
                    ValidaParaConsolidacao,
                    ID_UsuarioAbertura,
                    UsuarioAberturaLogin,
                    UsuarioAberturaNome
                )
                OUTPUT
                    INSERTED.ID_Sessao,
                    INSERTED.DataHoraInicio
                VALUES
                (
                    ?, ?, ?,
                    'ABERTA',
                    0,
                    1,
                    ?, ?, ?
                )
                """,
                (
                    dados.id_inventario,
                    dados.id_rodada,
                    localizacao,
                    usuario_id,
                    usuario_login,
                    usuario_nome
                )
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

        # ========================================================
        # INTEGRACAO CICLO ROTATIVO - NOVA SESSAO
        # ========================================================

        if not rodada_recontagem:
            _iniciar_ciclo_rotativo_da_localizacao(
                cursor=cursor,
                inventario=inventario,
                id_rodada=dados.id_rodada,
                localizacao=localizacao
            )

        uow.commit()

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


# ============================================================
# ENCERRAR LOCALIZAÇÃO
#
# Permissão:
# CONTAGEM_EXECUTAR
# ============================================================

@router.post(
    "/localizacoes/encerrar"
)
def encerrar_localizacao(
    dados: EncerrarSessaoEntrada,
    background_tasks: BackgroundTasks,
    usuario_atual=Depends(
        exigir_permissao(
            "CONTAGEM_EXECUTAR"
        )
    )
):

    if dados.id_sessao <= 0:

        raise HTTPException(
            status_code=400,
            detail="Sessão inválida."
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

                R.NumeroRodada,

                I.Tipo AS TipoInventario

            FROM dbo.SessoesContagem S WITH (UPDLOCK, HOLDLOCK)

            INNER JOIN dbo.RodadasInventario R
                ON R.ID_Rodada =
                   S.ID_Rodada

            INNER JOIN dbo.Inventarios I
                ON I.ID_Inventario =
                   S.ID_Inventario

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

        # ========================================================
        # INTEGRACAO CICLO ROTATIVO - CONCLUSAO
        #
        # O service de cobertura utiliza a MESMA conexao.
        #
        # Na primeira conclusao da localizacao ROTATIVA,
        # o commit interno confirma atomicamente:
        #
        # - sessao ENCERRADA;
        # - RodadaLocalizacoes CONCLUIDA, quando aplicavel;
        # - cobertura do ciclo;
        # - historico rotativo.
        #
        # Em R2, se a localizacao ja estiver CONTADA no ciclo,
        # o service retorna de forma idempotente e o commit
        # abaixo confirma somente a operacao da R2.
        # ========================================================

        cobertura_rotativo = None

        if (
            _normalizar_upper(
                sessao.TipoInventario
            )
            == "ROTATIVO"
        ):

            cobertura_rotativo = (
                registrar_conclusao_localizacao_rotativo(
                    conn=conn,
                    cursor=cursor,
                    id_sessao=sessao.ID_Sessao,
                    usuario=None,
                    processar_inteligencia=False
                )
            )

        notificacoes_geradas = []

        # ====================================================
        # VERIFICA SE TODA A RODADA FOI CONCLUIDA
        # ====================================================

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM dbo.RodadaLocalizacoes
            WHERE
                ID_Inventario = ?
                AND ID_Rodada = ?
            """,
            (
                sessao.ID_Inventario,
                sessao.ID_Rodada,
            ),
        )

        total_planejadas = int(
            cursor.fetchone()[0]
        )

        if total_planejadas > 0:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM dbo.RodadaLocalizacoes
                WHERE
                    ID_Inventario = ?
                    AND ID_Rodada = ?
                    AND Status = 'CONCLUIDA'
                """,
                (
                    sessao.ID_Inventario,
                    sessao.ID_Rodada,
                ),
            )

            total_concluidas = int(
                cursor.fetchone()[0]
            )

        else:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM dbo.InventarioEscopoLocalizacoes
                WHERE
                    ID_Inventario = ?
                    AND Selecionado = 1
                """,
                sessao.ID_Inventario,
            )

            total_planejadas = int(
                cursor.fetchone()[0]
            )

            cursor.execute(
                """
                SELECT COUNT(*)

                FROM dbo.InventarioEscopoLocalizacoes E

                WHERE
                    E.ID_Inventario = ?
                    AND E.Selecionado = 1

                    AND EXISTS
                    (
                        SELECT 1

                        FROM dbo.SessoesContagem S

                        WHERE
                            S.ID_Inventario =
                                E.ID_Inventario

                            AND S.ID_Rodada = ?

                            AND S.ValidaParaConsolidacao = 1

                            AND S.Status = 'ENCERRADA'

                            AND UPPER(
                                LTRIM(
                                    RTRIM(S.Localizacao)
                                )
                            ) =
                            UPPER(
                                LTRIM(
                                    RTRIM(E.Localizacao)
                                )
                            )
                    )
                """,
                (
                    sessao.ID_Inventario,
                    sessao.ID_Rodada,
                ),
            )

            total_concluidas = int(
                cursor.fetchone()[0]
            )

        rodada_concluida = (
            total_planejadas > 0
            and
            total_concluidas >= total_planejadas
        )

        if rodada_concluida:
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
                sessao.ID_Inventario,
            )

            inventario_atual = cursor.fetchone()

            # ================================================
            # FECHAMENTO OPERACIONAL DA RODADA OFICIAL
            #
            # Quando todas as localizacoes planejadas foram
            # concluidas, a rodada deixa de estar ABERTA.
            #
            # A decisao sobre o proximo passo continua sendo
            # responsabilidade das regras aplicadas ao
            # inventario e do preview da proxima rodada.
            # ================================================

            if (
                inventario_atual
                and
                str(inventario_atual.Tipo)
                .strip()
                .upper()
                == "OFICIAL"
            ):
                _finalizar_rodada_atual(
                    cursor=cursor,
                    id_inventario=int(
                        sessao.ID_Inventario
                    ),
                    id_rodada=int(
                        sessao.ID_Rodada
                    ),
                )

            cursor.execute(
                """
                SELECT
                    ID_Rodada,
                    ID_Inventario,
                    NumeroRodada,
                    Status,
                    DataHoraInicio

                FROM dbo.RodadasInventario

                WHERE ID_Rodada = ?
                """,
                sessao.ID_Rodada,
            )

            rodada_atual = cursor.fetchone()

            numero_rodada = int(
                sessao.NumeroRodada
            )

            if numero_rodada > 1:
                tipo_evento = (
                    "RECONTAGEM_CONCLUIDA"
                )
                titulo_evento = (
                    "Recontagem conclu\u00edda"
                )
            else:
                tipo_evento = (
                    "RODADA_CONCLUIDA"
                )
                titulo_evento = (
                    "Rodada de contagem conclu\u00edda"
                )

            resumo_rodada = criar_por_permissao(
                cursor=cursor,
                codigo_permissao=(
                    "ANALISE_VISUALIZAR"
                ),
                id_usuario_ator=int(
                    usuario_atual["id_usuario"]
                ),
                tipo=tipo_evento,
                titulo=titulo_evento,
                mensagem=(
                    f"A rodada R{numero_rodada} "
                    f"do invent\u00e1rio "
                    f"{inventario_atual.CodigoInventario} "
                    f"foi conclu\u00edda e est\u00e1 "
                    f"pronta para an\u00e1lise."
                ),
                prioridade="ALTA",
                entidade_tipo="RODADA",
                entidade_id=int(
                    sessao.ID_Rodada
                ),
                id_inventario=int(
                    sessao.ID_Inventario
                ),
                url=(
                    f"/inventarios/"
                    f"{sessao.ID_Inventario}"
                ),
                chave_dedupe=(
                    f"{tipo_evento}:"
                    f"{sessao.ID_Inventario}:"
                    f"{sessao.ID_Rodada}"
                ),
                excluir_ator=False,
            )

            notificacoes_geradas.append(
                {
                    "tipo": tipo_evento,
                    **resumo_rodada,
                }
            )

            # ================================================
            # OFICIAL PRONTO PARA FINALIZAR
            # ================================================

            if (
                str(inventario_atual.Tipo)
                .strip()
                .upper()
                == "OFICIAL"
            ):
                preview = None

                try:
                    preview = visualizar_proxima_rodada(
                        cursor=cursor,
                        inventario=inventario_atual,
                        rodada_atual=rodada_atual,
                    )
                except (
                    BusinessRuleViolation,
                    NotFoundError,
                ):
                    preview = None

                if isinstance(preview, dict):
                    tipo_proxima = str(
                        preview.get(
                            "tipo_proxima_rodada"
                        )
                        or preview.get(
                            "proxima_acao"
                        )
                        or ""
                    ).strip().upper()

                    pronto_finalizar = bool(
                        preview.get(
                            "pode_finalizar",
                            False,
                        )
                    ) or tipo_proxima in {
                        "FINALIZADO",
                        "FINALIZAR",
                    }

                    if pronto_finalizar:
                        resumo_finalizar = (
                            criar_por_permissao(
                                cursor=cursor,
                                codigo_permissao=(
                                    "INVENTARIO_FINALIZAR"
                                ),
                                id_usuario_ator=int(
                                    usuario_atual[
                                        "id_usuario"
                                    ]
                                ),
                                tipo=(
                                    "INVENTARIO_PRONTO_FINALIZAR"
                                ),
                                titulo=(
                                    "Invent\u00e1rio pronto "
                                    "para finalizar"
                                ),
                                mensagem=(
                                    f"O invent\u00e1rio "
                                    f"{inventario_atual.CodigoInventario} "
                                    f"concluiu todas as "
                                    f"etapas necess\u00e1rias."
                                ),
                                prioridade="ALTA",
                                entidade_tipo=(
                                    "INVENTARIO"
                                ),
                                entidade_id=int(
                                    sessao.ID_Inventario
                                ),
                                id_inventario=int(
                                    sessao.ID_Inventario
                                ),
                                url=(
                                    f"/inventarios/"
                                    f"{sessao.ID_Inventario}"
                                ),
                                chave_dedupe=(
                                    "INVENTARIO_PRONTO_FINALIZAR:"
                                    f"{sessao.ID_Inventario}"
                                ),
                                excluir_ator=False,
                            )
                        )

                        notificacoes_geradas.append(
                            {
                                "tipo": (
                                    "INVENTARIO_PRONTO_FINALIZAR"
                                ),
                                **resumo_finalizar,
                            }
                        )

        uow.commit()

        # ====================================================
        # INTELIGENCIA ROTATIVA POS-RESPOSTA
        #
        # A cobertura operacional ja foi persistida.
        # A parte analitica utiliza uma nova conexao SQL
        # e nao bloqueia a resposta ao operador.
        #
        # Em R2, quando a localizacao ja estava CONTADA no
        # ciclo, o service retorna registrado=False e preserva
        # o comportamento idempotente existente.
        # ====================================================

        if (
            cobertura_rotativo
            and cobertura_rotativo.get("registrado") is True
        ):
            background_tasks.add_task(
                processar_inteligencia_conclusao_rotativo_background,
                id_sessao=sessao.ID_Sessao,
                usuario=None
            )

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

            "cobertura_rotativo":
                cobertura_rotativo,

            "rodada_concluida":
                rodada_concluida,

            "notificacoes":
                notificacoes_geradas,

            "mensagem":
                (
                    "Localização vazia confirmada "
                    "e encerrada com sucesso."
                    if dados.localizacao_vazia
                    else
                    "Localização encerrada com sucesso."
                )
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
    "/contagens"
)
def salvar_contagem(
    contagem: ContagemEntrada,
    usuario_atual=Depends(
        exigir_permissao(
            "CONTAGEM_EXECUTAR"
        )
    )
):

    # ========================================================
    # 1. NORMALIZAÇÃO
    # ========================================================

    criado_por = (
        str(
            usuario_atual["login"]
        )
        .strip()
    )

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

    uow = None
    conn = None
    cursor = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()
        conn = uow.connection
        cursor = uow.cursor

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
        # PROTEÇÃO R2 ROTATIVO - ITEM AUTORIZADO
        # ====================================================

        if (
            _normalizar_upper(
                sessao.TipoInventario
            ) == "ROTATIVO"
            and
            int(
                sessao.NumeroRodada
            ) >= 2
        ):

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM dbo.RodadaItens
                WHERE
                    ID_Inventario = ?
                    AND ID_Rodada = ?
                    AND LTRIM(RTRIM(Codigo)) = ?
                    AND ISNULL(
                        LTRIM(RTRIM(Lote)),
                        ''
                    ) = ?
                """,
                (
                    sessao.ID_Inventario,
                    sessao.ID_Rodada,
                    codigo,
                    lote or ""
                )
            )

            item_autorizado_na_r2 = (
                cursor.fetchone()[0] > 0
            )

            if not item_autorizado_na_r2:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Este item não pertence à "
                        "recontagem desta rodada."
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
                Status,
                CriadoPor
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
                'ATIVA',
                ?
            )
            """,
            (
                contagem.id_sessao,
                codigo,
                lote,
                contagem.quantidade,
                criado_por
            )
        )

        registro = (
            cursor.fetchone()
        )

        uow.commit()

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

    uow = None
    conn = None
    cursor = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()
        conn = uow.connection
        cursor = uow.cursor

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
# CANCELAR CONTAGEM
#
# Permissão:
# Qualquer usuario autenticado
# ============================================================

@router.patch(
    "/contagens/{id_contagem}/cancelar",
    dependencies=[
        Depends(
            obter_usuario_atual
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

    uow = None
    conn = None
    cursor = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()
        conn = uow.connection
        cursor = uow.cursor

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

        uow.commit()

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

    uow = None
    conn = None
    cursor = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()
        conn = uow.connection
        cursor = uow.cursor

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


        if uow:
            uow.close()
