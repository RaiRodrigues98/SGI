from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from application.exceptions import TechnicalConfigurationError
from domain.exceptions import (
    BusinessRuleViolation,
    ConflictError,
    NotFoundError,
)

from infrastructure.database.unit_of_work import SqlServerUnitOfWork

from dependencies.auth import (
    exigir_permissao,
)

from schemas.configuracoes_operacionais import (
    AtualizarConfiguracaoInventarioAplicadaEntrada,
    ConfiguracaoOperacionalEntrada,
    ConfiguracoesRodadasEntrada,
    CriarConfiguracaoInventarioEntrada,
)

from services.configuracoes_inventario import (
    obter_configuracao_completa,
)


from services.configuracoes_inventario_aplicadas import (
    atualizar_configuracao_aplicada,
    listar_historico_configuracao_aplicada,
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


# ============================================================
# CRIAR CONFIGURACAO
#
# Permissao necessaria:
# CONFIGURACAO_EDITAR
#
# Cria de forma transacional:
# - dbo.ConfiguracoesInventario
# - dbo.ConfiguracoesRodadasInventario
#
# Nao altera configuracao existente.
# ============================================================

@router.post(
    "/configuracoes/inventario/{cliente_id}/{tipo}"
)
def criar_configuracao(
    cliente_id: int,
    tipo: str,
    dados: CriarConfiguracaoInventarioEntrada,
    usuario_atual=Depends(
        exigir_permissao(
            "CONFIGURACAO_EDITAR"
        )
    )
):

    # ========================================================
    # 1. VALIDACOES BASICAS
    # ========================================================

    if cliente_id <= 0:

        raise HTTPException(
            status_code=400,
            detail="Cliente invalido."
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
                "Tipo de inventario invalido. "
                "Utilize ROTATIVO ou OFICIAL."
            )
        )

    if not dados.ativa:

        raise HTTPException(
            status_code=400,
            detail=(
                "Uma nova configuracao deve "
                "ser criada ativa."
            )
        )

    if (
        dados.quantidade_minima
        >
        dados.quantidade_maxima
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Quantidade minima nao pode ser "
                "maior que a quantidade maxima."
            )
        )

    if (
        dados.rodadas_iniciais
        >
        dados.max_rodadas
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Rodadas iniciais nao podem ser "
                "maiores que o maximo de rodadas."
            )
        )

    if not dados.rodadas:

        raise HTTPException(
            status_code=400,
            detail=(
                "Informe pelo menos uma rodada."
            )
        )

    # ========================================================
    # 2. VALIDAR ESTRUTURA DAS RODADAS
    # ========================================================

    numeros = [
        rodada.numero_rodada
        for rodada in dados.rodadas
    ]

    if (
        len(numeros)
        !=
        len(set(numeros))
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Existem numeros de rodada "
                "duplicados."
            )
        )

    numeros_ordenados = sorted(
        numeros
    )

    sequencia_esperada = list(
        range(
            1,
            len(numeros_ordenados) + 1
        )
    )

    if (
        numeros_ordenados
        !=
        sequencia_esperada
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "As rodadas devem formar uma "
                "sequencia continua iniciando em 1."
            )
        )

    rodadas_ordenadas = sorted(
        dados.rodadas,
        key=lambda rodada:
            rodada.numero_rodada
    )

    if (
        len(rodadas_ordenadas)
        !=
        dados.max_rodadas
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "A quantidade de rodadas informada "
                "deve ser igual ao MaxRodadas."
            )
        )

    quantidade_gestor = sum(
        1
        for rodada in rodadas_ordenadas
        if rodada.tipo_rodada == "GESTOR"
    )

    if quantidade_gestor > 1:

        raise HTTPException(
            status_code=400,
            detail=(
                "Somente uma rodada GESTOR "
                "pode ser configurada."
            )
        )

    for rodada in rodadas_ordenadas:

        numero = (
            rodada.numero_rodada
        )

        tipo_rodada = (
            rodada.tipo_rodada
        )

        if (
            numero
            <=
            dados.rodadas_iniciais
            and
            tipo_rodada != "COMPLETA"
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    f"A rodada {numero} pertence "
                    "as rodadas iniciais e deve "
                    "ser do tipo COMPLETA."
                )
            )

        if (
            numero
            >
            dados.rodadas_iniciais
            and
            tipo_rodada == "COMPLETA"
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    f"A rodada {numero} nao pode "
                    "ser COMPLETA apos o limite "
                    "de rodadas iniciais."
                )
            )

        if (
            tipo_rodada == "GESTOR"
            and
            numero != dados.max_rodadas
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "A rodada GESTOR somente pode "
                    "ser configurada como ultima rodada."
                )
            )

    usuario = (
        str(
            usuario_atual["login"]
        )
        .strip()
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
        # 3. VALIDAR CLIENTE
        # ====================================================

        cursor.execute(
            """
            SELECT TOP 1
                Id,
                Nome

            FROM AlzarsiLog.dbo.Cliente

            WHERE Id = ?
            """,
            (
                cliente_id,
            )
        )

        cliente = (
            cursor.fetchone()
        )

        if not cliente:

            raise HTTPException(
                status_code=404,
                detail=(
                    "Cliente nao encontrado "
                    "no cadastro operacional."
                )
            )

        # ====================================================
        # 4. VERIFICAR CONFIGURACAO EXISTENTE
        # ====================================================

        cursor.execute(
            """
            SELECT TOP 1
                ID_Configuracao,
                Ativa

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

        existente = (
            cursor.fetchone()
        )

        if existente:

            if not bool(
                existente.Ativa
            ):

                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Ja existe uma configuracao "
                        "inativa para este cliente e tipo. "
                        "A chave ClienteId + TipoInventario "
                        "nao permite criar outra."
                    )
                )

            configuracao_existente = (
                obter_configuracao_completa(
                    cursor=cursor,
                    cliente_id=cliente_id,
                    tipo_inventario=(
                        tipo_normalizado
                    )
                )
            )

            return {
                "sucesso":
                    True,

                "criada":
                    False,

                "motivo":
                    "CONFIGURACAO_JA_EXISTE",

                "mensagem":
                    (
                        "A configuracao ativa "
                        "ja existe."
                    ),

                "configuracao":
                    configuracao_existente,
            }

        # ====================================================
        # 5. CRIAR CONFIGURACAO PRINCIPAL
        # ====================================================

        cursor.execute(
            """
            INSERT INTO dbo.ConfiguracoesInventario
            (
                ClienteId,
                TipoInventario,

                ValidarLocalizacaoEscopo,
                PermitirLocalizacaoVazia,

                CodigoLivre,
                PermitirCodigoNaoCadastrado,
                PermitirItemForaLocalizacao,

                LoteObrigatorioSeExistir,
                ValidarLoteCodigo,
                ValidarLoteLocalizacao,

                QuantidadeMinima,
                QuantidadeMaxima,

                ContagemCega,

                ConsideraLocalizacaoConciliacao,

                RecontagemPorLocalizacao,
                RodadasIniciais,
                MaxRodadas,

                PermitirGestorAntecipado,
                LimiteItensGestorAntecipado,

                DivergenciaBloqueiaFinalizacao,

                Ativa,

                CriadoPor,
                DataHoraCriacao,

                PermitirReaberturaLocalizacao,
                PermitirAlteracaoEscopoAposSnapshot
            )

            OUTPUT
                INSERTED.ID_Configuracao

            VALUES
            (
                ?,
                ?,

                ?,
                ?,

                ?,
                ?,
                ?,

                ?,
                ?,
                ?,

                ?,
                ?,

                ?,

                ?,

                ?,
                ?,
                ?,

                ?,
                ?,

                ?,

                1,

                ?,
                SYSDATETIME(),

                ?,
                ?
            )
            """,
            (
                cliente_id,
                tipo_normalizado,

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

                usuario,

                dados.permitir_reabertura_localizacao,
                dados.permitir_alteracao_escopo_apos_snapshot,
            )
        )

        linha_configuracao = (
            cursor.fetchone()
        )

        if not linha_configuracao:

            raise HTTPException(
                status_code=500,
                detail=(
                    "Nao foi possivel obter o ID "
                    "da configuracao criada."
                )
            )

        id_configuracao = int(
            linha_configuracao[0]
        )

        # ====================================================
        # 6. CRIAR CONFIGURACAO DAS RODADAS
        # ====================================================

        for rodada in rodadas_ordenadas:

            cursor.execute(
                """
                INSERT INTO dbo.ConfiguracoesRodadasInventario
                (
                    ID_Configuracao,
                    NumeroRodada,
                    TipoRodada,
                    Ativa
                )

                VALUES
                (
                    ?,
                    ?,
                    ?,
                    1
                )
                """,
                (
                    id_configuracao,
                    rodada.numero_rodada,
                    rodada.tipo_rodada,
                )
            )

        # ====================================================
        # 7. COMMIT
        # ====================================================

        uow.commit()

        # ====================================================
        # 8. RETORNO PELO SERVICO JA EXISTENTE
        # ====================================================

        resultado = (
            obter_configuracao_completa(
                cursor=cursor,
                cliente_id=cliente_id,
                tipo_inventario=(
                    tipo_normalizado
                )
            )
        )

        return {
            "sucesso":
                True,

            "criada":
                True,

            "motivo":
                "CONFIGURACAO_CRIADA",

            "mensagem":
                (
                    "Configuracao criada "
                    "com sucesso."
                ),

            "configuracao":
                resultado,
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

    except TechnicalConfigurationError as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=500,
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

    if not dados.ativa:
        raise HTTPException(
            status_code=400,
            detail=(
                "A desativacao da configuracao nao e permitida "
                "por este endpoint."
            )
        )

    usuario = (
        str(
            usuario_atual["login"]
        )
        .strip()
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
                ID_Configuracao,
                RodadasIniciais,
                MaxRodadas

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
        # ALTERACOES ESTRUTURAIS DE RODADAS
        #
        # RodadasIniciais e MaxRodadas sao administrados
        # exclusivamente pelo endpoint /rodadas.
        # ====================================================

        if (
            dados.rodadas_iniciais
            != int(configuracao.RodadasIniciais)
            or dados.max_rodadas
            != int(configuracao.MaxRodadas)
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "RodadasIniciais e MaxRodadas devem ser "
                    "alterados pelo endpoint de configuracao "
                    "das rodadas."
                )
            )

        # 5. ATUALIZA CONFIGURAÇÃO
        # ====================================================

        cursor.execute(
            """
            UPDATE dbo.ConfiguracoesInventario

            SET
                ValidarLocalizacaoEscopo = ?,
                PermitirLocalizacaoVazia = ?,
                PermitirReaberturaLocalizacao = ?,
                PermitirAlteracaoEscopoAposSnapshot = ?,

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
                dados.permitir_reabertura_localizacao,
                dados.permitir_alteracao_escopo_apos_snapshot,

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
            "sucesso": True,
            "mensagem":
                "Configuração atualizada com sucesso.",
            "configuracao": resultado
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

    except TechnicalConfigurationError as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=500,
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
# ATUALIZAR CONFIGURACAO DAS RODADAS
# ============================================================

@router.put(
    "/configuracoes/inventario/{cliente_id}/{tipo}/rodadas"
)
def atualizar_configuracao_rodadas(
    cliente_id: int,
    tipo: str,
    dados: ConfiguracoesRodadasEntrada,
    usuario_atual=Depends(
        exigir_permissao(
            "CONFIGURACAO_EDITAR"
        )
    )
):

    if cliente_id <= 0:
        raise HTTPException(
            status_code=400,
            detail="Cliente invalido."
        )

    tipo_normalizado = _normalizar_tipo(tipo)

    if tipo_normalizado not in (
        "ROTATIVO",
        "OFICIAL"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Tipo de inventario invalido. "
                "Utilize ROTATIVO ou OFICIAL."
            )
        )

    if dados.rodadas_iniciais > dados.max_rodadas:
        raise HTTPException(
            status_code=400,
            detail=(
                "Rodadas iniciais nao podem ser maiores "
                "que o maximo de rodadas."
            )
        )

    if not dados.rodadas:
        raise HTTPException(
            status_code=400,
            detail=(
                "Informe pelo menos uma rodada."
            )
        )

    numeros = [
        rodada.numero_rodada
        for rodada in dados.rodadas
    ]

    if len(numeros) != len(set(numeros)):
        raise HTTPException(
            status_code=400,
            detail=(
                "Existem numeros de rodada duplicados."
            )
        )

    numeros_ordenados = sorted(numeros)

    sequencia_esperada = list(
        range(
            1,
            len(numeros_ordenados) + 1
        )
    )

    if numeros_ordenados != sequencia_esperada:
        raise HTTPException(
            status_code=400,
            detail=(
                "As rodadas devem formar uma sequencia "
                "continua iniciando em 1."
            )
        )

    rodadas_ordenadas = sorted(
        dados.rodadas,
        key=lambda rodada: rodada.numero_rodada
    )

    usuario = (
        str(
            usuario_atual["login"]
        )
        .strip()
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
            SELECT TOP 1
                ID_Configuracao,
                RodadasIniciais,
                MaxRodadas

            FROM dbo.ConfiguracoesInventario

            WHERE
                ClienteId = ?
                AND UPPER(
                    LTRIM(
                        RTRIM(TipoInventario)
                    )
                ) = ?
                AND Ativa = 1
            """,
            (
                cliente_id,
                tipo_normalizado
            )
        )

        configuracao = cursor.fetchone()

        if not configuracao:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Configuracao ativa nao encontrada "
                    "para este cliente e tipo de inventario."
                )
            )

        id_configuracao = int(
            configuracao.ID_Configuracao
        )

        rodadas_iniciais = dados.rodadas_iniciais
        max_rodadas = dados.max_rodadas

        if len(rodadas_ordenadas) != max_rodadas:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"A configuracao exige exatamente "
                    f"{max_rodadas} rodadas."
                )
            )

        quantidade_gestor = sum(
            1
            for rodada in rodadas_ordenadas
            if rodada.tipo_rodada == "GESTOR"
        )

        if quantidade_gestor > 1:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Somente uma rodada GESTOR "
                    "pode ser configurada."
                )
            )

        for rodada in rodadas_ordenadas:

            numero = rodada.numero_rodada
            tipo_rodada = rodada.tipo_rodada

            if (
                numero <= rodadas_iniciais
                and tipo_rodada != "COMPLETA"
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"A rodada {numero} pertence "
                        "as rodadas iniciais e deve "
                        "ser do tipo COMPLETA."
                    )
                )

            if (
                numero > rodadas_iniciais
                and tipo_rodada == "COMPLETA"
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"A rodada {numero} nao pode "
                        "ser COMPLETA apos o limite "
                        "de rodadas iniciais."
                    )
                )

            if (
                tipo_rodada == "GESTOR"
                and numero != max_rodadas
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "A rodada GESTOR somente pode "
                        "ser configurada como ultima rodada."
                    )
                )

        # ====================================================
        # ATUALIZA ESTRUTURA PRINCIPAL
        # ====================================================

        cursor.execute(
            """
            UPDATE dbo.ConfiguracoesInventario

            SET
                RodadasIniciais = ?,
                MaxRodadas = ?,
                AlteradoPor = ?,
                DataHoraAlteracao = SYSDATETIME()

            WHERE
                ID_Configuracao = ?
                AND Ativa = 1
            """,
            (
                rodadas_iniciais,
                max_rodadas,
                usuario,
                id_configuracao
            )
        )

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Nao foi possivel atualizar a estrutura "
                    "da configuracao."
                )
            )

        # ====================================================
        # ATUALIZA CONFIGURACAO DAS RODADAS
        #
        # Preserva os IDs existentes e desativa rodadas
        # que nao fazem mais parte da configuracao atual.
        # ====================================================

        cursor.execute(
            """
            UPDATE dbo.ConfiguracoesRodadasInventario

            SET
                Ativa = 0

            WHERE
                ID_Configuracao = ?
            """,
            (
                id_configuracao,
            )
        )

        for rodada in rodadas_ordenadas:

            cursor.execute(
                """
                UPDATE dbo.ConfiguracoesRodadasInventario

                SET
                    TipoRodada = ?,
                    Ativa = 1

                WHERE
                    ID_Configuracao = ?
                    AND NumeroRodada = ?
                """,
                (
                    rodada.tipo_rodada,
                    id_configuracao,
                    rodada.numero_rodada
                )
            )

            if cursor.rowcount == 0:

                cursor.execute(
                    """
                    INSERT INTO dbo.ConfiguracoesRodadasInventario
                    (
                        ID_Configuracao,
                        NumeroRodada,
                        TipoRodada,
                        Ativa
                    )
                    VALUES
                    (
                        ?,
                        ?,
                        ?,
                        1
                    )
                    """,
                    (
                        id_configuracao,
                        rodada.numero_rodada,
                        rodada.tipo_rodada
                    )
                )

        uow.commit()

        resultado = obter_configuracao_completa(
            cursor=cursor,
            cliente_id=cliente_id,
            tipo_inventario=tipo_normalizado
        )

        return {
            "sucesso": True,
            "mensagem":
                "Configuracao das rodadas atualizada com sucesso.",
            "configuracao": resultado
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

    except TechnicalConfigurationError as erro:

        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=500,
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
# CONFIGURACAO ESPECIFICA DO INVENTARIO
# ============================================================

@router.put(
    "/inventarios/{id_inventario}/configuracao"
)
def atualizar_configuracao_do_inventario(
    id_inventario: int,
    dados: AtualizarConfiguracaoInventarioAplicadaEntrada,
    usuario_atual=Depends(
        exigir_permissao(
            "CONFIGURACAO_EDITAR"
        )
    )
):
    usuario = (
        str(
            usuario_atual["login"]
        )
        .strip()
    )

    uow = None
    conn = None

    try:
        uow = SqlServerUnitOfWork()
        uow.open()

        conn = uow.connection
        cursor = uow.cursor

        resultado = atualizar_configuracao_aplicada(
            cursor=cursor,
            id_inventario=id_inventario,
            dados=dados,
            usuario=usuario,
        )

        uow.commit()

        return resultado

    except ConflictError as erro:
        if conn:
            uow.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(erro)
        )

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


@router.get(
    "/inventarios/{id_inventario}/configuracao/historico"
)
def historico_configuracao_do_inventario(
    id_inventario: int,
    usuario_atual=Depends(
        exigir_permissao(
            "CONFIGURACAO_VISUALIZAR"
        )
    )
):
    uow = None

    try:
        uow = SqlServerUnitOfWork()
        uow.open()

        return listar_historico_configuracao_aplicada(
            cursor=uow.cursor,
            id_inventario=id_inventario,
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
