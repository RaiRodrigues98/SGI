from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from infrastructure.database.unit_of_work import SqlServerUnitOfWork

from dependencies.auth import (
    exigir_permissao,
)

from schemas.escopo import (
    EscopoLocalizacoesEntrada,
)


router = APIRouter(
    tags=["Escopo do Inventário"]
)


# ============================================================
# ESTOQUE CANDIDATO
#
# Permissão:
# ANALISE_VISUALIZAR
# ============================================================

@router.get(
    "/inventarios/{id_inventario}/estoque-candidatos",
    dependencies=[
        Depends(
            exigir_permissao(
                "ANALISE_VISUALIZAR"
            )
        )
    ]
)
def listar_estoque_candidatos(
    id_inventario: int,
    localizacao: str | None = None,
    item: str | None = None,
    lote: str | None = None,
    categoria: str | None = None,
    tipo_localizacao: str | None = None,
    somente_com_saldo: bool = True,
):

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
                ID_Inventario,
                CodigoInventario,
                Tipo,
                Cliente,
                ClienteId,
                cArmazem,
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

        sql = """
            SELECT
                E.Id,
                E.cArmazem,
                E.cLocalizacao,
                E.cItem,
                E.cLote,
                E.ClienteId,
                E.dItem,
                E.cUnidade,
                E.cCategoria,
                E.Validade,
                E.qArmazenado,
                E.qReservado,
                E.qBloqueado,
                E.qEstimado,

                Preco.ValorUnitario,

                CASE
                    WHEN Preco.ValorUnitario IS NULL
                    THEN NULL
                    ELSE
                        Preco.ValorUnitario
                        *
                        E.qArmazenado
                END AS ValorTotalEstoque,

                (
                    E.qArmazenado
                    -
                    E.qReservado
                ) AS SaldoInventario,

                E.StatusEstoque,
                E.TipoLocalizacao

            FROM AlzarsiLog.dbo.Estoque E

            INNER JOIN AlzarsiLog.dbo.Cliente C
                ON C.Id = E.ClienteId

            OUTER APPLY (
                SELECT TOP 1
                    RI.ValorUnitario

                FROM AlzarsiLog.dbo.RecebimentoItem RI

                INNER JOIN AlzarsiLog.dbo.Recebimento R
                    ON R.Id = RI.RecebimentoId

                WHERE
                    R.CnpjCliente = C.Cnpj

                    AND RI.CodigoItem = E.cItem

                    AND ISNULL(
                        LTRIM(RTRIM(RI.CodigoLote)),
                        ''
                    ) = ISNULL(
                        LTRIM(RTRIM(E.cLote)),
                        ''
                    )

                    AND RI.ValorUnitario IS NOT NULL

                ORDER BY
                    R.DataCriacao DESC,
                    RI.Id DESC
            ) Preco

            WHERE E.ClienteId = ?
              AND E.cArmazem = ?
        """

        parametros = [
            inventario.ClienteId,
            inventario.cArmazem
        ]

        if somente_com_saldo:
            sql += """
                AND (
                    E.qArmazenado
                    -
                    E.qReservado
                ) <> 0
            """

        if localizacao:
            sql += " AND E.cLocalizacao LIKE ?"
            parametros.append(
                f"%{localizacao.strip()}%"
            )

        if item:
            sql += " AND E.cItem LIKE ?"
            parametros.append(
                f"%{item.strip()}%"
            )

        if lote:
            sql += " AND E.cLote LIKE ?"
            parametros.append(
                f"%{lote.strip()}%"
            )

        if categoria:
            sql += " AND E.cCategoria LIKE ?"
            parametros.append(
                f"%{categoria.strip()}%"
            )

        if tipo_localizacao:
            sql += " AND E.TipoLocalizacao LIKE ?"
            parametros.append(
                f"%{tipo_localizacao.strip()}%"
            )

        sql += """
            ORDER BY
                E.cLocalizacao,
                E.cItem,
                E.cLote
        """

        cursor.execute(
            sql,
            tuple(parametros)
        )

        linhas = cursor.fetchall()

        itens = []

        for linha in linhas:
            itens.append({
                "id_origem": linha.Id,
                "c_armazem": linha.cArmazem,
                "localizacao": linha.cLocalizacao,
                "codigo": linha.cItem,
                "lote": linha.cLote,
                "cliente_id": linha.ClienteId,
                "descricao": linha.dItem,
                "unidade": linha.cUnidade,
                "categoria": linha.cCategoria,
                "validade": linha.Validade,
                "valor_unitario": (
                    float(linha.ValorUnitario)
                    if linha.ValorUnitario is not None
                    else None
                ),

                "valor_total": (
                    float(linha.ValorTotalEstoque)
                    if linha.ValorTotalEstoque is not None
                    else None
                ),

                "q_armazenado": float(
                    linha.qArmazenado
                ),

                "q_reservado": float(
                    linha.qReservado
                ),

                "q_separando": float(
                    linha.qReservado
                ),

                "q_bloqueado": float(
                    linha.qBloqueado
                ),

                "q_recebimento": float(
                    linha.qEstimado
                ),

                "saldo_inventario": float(
                    linha.SaldoInventario
                ),
                "status_estoque":
                    linha.StatusEstoque,
                "tipo_localizacao":
                    linha.TipoLocalizacao
            })

        return {
            "id_inventario":
                id_inventario,

            "codigo_inventario":
                inventario.CodigoInventario,

            "tipo":
                inventario.Tipo,

            "cliente":
                inventario.Cliente,

            "cliente_id":
                inventario.ClienteId,

            "c_armazem":
                inventario.cArmazem,

            "total":
                len(itens),

            "itens":
                itens
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
# LOCALIZAÇÕES CANDIDATAS
#
# Permissão:
# ANALISE_VISUALIZAR
# ============================================================

@router.get(
    "/inventarios/{id_inventario}/localizacoes-candidatas",
    dependencies=[
        Depends(
            exigir_permissao(
                "ANALISE_VISUALIZAR"
            )
        )
    ]
)
def listar_localizacoes_candidatas(
    id_inventario: int,
    localizacao: str | None = None,
    item: str | None = None,
    lote: str | None = None,
    categoria: str | None = None,
    tipo_localizacao: str | None = None,
    somente_com_saldo: bool = True,
):

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
                ID_Inventario,
                CodigoInventario,
                Tipo,
                Cliente,
                ClienteId,
                cArmazem,
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

        sql = """
            SELECT
                E.cLocalizacao,

                COUNT(*) AS Registros,

                COUNT(
                    DISTINCT E.cItem
                ) AS ItensDistintos,

                COUNT(
                    DISTINCT E.cLote
                ) AS LotesDistintos,

                SUM(
                    E.qArmazenado
                    -
                    E.qReservado
                ) AS QuantidadeTotal

            FROM AlzarsiLog.dbo.Estoque E

            WHERE E.ClienteId = ?
              AND E.cArmazem = ?
        """

        parametros = [
            inventario.ClienteId,
            inventario.cArmazem
        ]

        if somente_com_saldo:
            sql += """
                AND (
                    E.qArmazenado
                    -
                    E.qReservado
                ) <> 0
            """

        if localizacao:
            sql += " AND E.cLocalizacao LIKE ?"
            parametros.append(
                f"%{localizacao.strip()}%"
            )

        if item:
            sql += " AND E.cItem LIKE ?"
            parametros.append(
                f"%{item.strip()}%"
            )

        if lote:
            sql += " AND E.cLote LIKE ?"
            parametros.append(
                f"%{lote.strip()}%"
            )

        if categoria:
            sql += " AND E.cCategoria LIKE ?"
            parametros.append(
                f"%{categoria.strip()}%"
            )

        if tipo_localizacao:
            sql += " AND E.TipoLocalizacao LIKE ?"
            parametros.append(
                f"%{tipo_localizacao.strip()}%"
            )

        sql += """
            GROUP BY
                E.cLocalizacao

            ORDER BY
                E.cLocalizacao
        """

        cursor.execute(
            sql,
            tuple(parametros)
        )

        linhas = cursor.fetchall()

        localizacoes = []

        for linha in linhas:
            localizacoes.append({
                "localizacao":
                    linha.cLocalizacao,

                "registros":
                    linha.Registros,

                "itens_distintos":
                    linha.ItensDistintos,

                "lotes_distintos":
                    linha.LotesDistintos,

                "quantidade_total":
                    float(
                        linha.QuantidadeTotal or 0
                    )
            })

        return {
            "id_inventario":
                id_inventario,

            "codigo_inventario":
                inventario.CodigoInventario,

            "tipo":
                inventario.Tipo,

            "cliente":
                inventario.Cliente,

            "cliente_id":
                inventario.ClienteId,

            "c_armazem":
                inventario.cArmazem,

            "total_localizacoes":
                len(localizacoes),

            "localizacoes":
                localizacoes
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
# ADICIONAR LOCALIZAÇÕES AO ESCOPO
#
# Permissão:
# RODADA_GERAR
# ============================================================

@router.post(
    "/inventarios/{id_inventario}/escopo/localizacoes",
    dependencies=[
        Depends(
            exigir_permissao(
                "RODADA_GERAR"
            )
        )
    ]
)
def adicionar_localizacoes_escopo(
    id_inventario: int,
    dados: EscopoLocalizacoesEntrada
):

    localizacoes = list(
        dict.fromkeys(
            localizacao.strip().upper()
            for localizacao in dados.localizacoes
            if localizacao
            and localizacao.strip()
        )
    )

    if not localizacoes:
        raise HTTPException(
            status_code=400,
            detail=(
                "Informe pelo menos "
                "uma localização."
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

        cursor.execute(
            """
            SELECT
                ID_Inventario,
                CodigoInventario,
                Tipo,
                ClienteId,
                cArmazem,
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
        # ALTERACAO DO ESCOPO APOS SNAPSHOT
        #
        # Regra:
        #
        # - sem snapshot: permite normalmente;
        # - com snapshot + configuracao desativada: bloqueia;
        # - com snapshot + configuracao ativada:
        #     somente permite antes da primeira sessao;
        # - se o escopo realmente mudar, o snapshot antigo
        #   sera invalidado antes do commit.
        # ====================================================

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM dbo.InventarioEstoqueSnapshot
            WHERE ID_Inventario = ?
            """,
            id_inventario
        )

        total_snapshot = int(
            cursor.fetchone()[0]
        )

        permitir_alteracao_apos_snapshot = False

        if total_snapshot > 0:

            cursor.execute(
                """
                SELECT TOP 1
                    PermitirAlteracaoEscopoAposSnapshot

                FROM dbo.ConfiguracoesInventario

                WHERE
                    ClienteId = ?
                    AND UPPER(
                        LTRIM(
                            RTRIM(TipoInventario)
                        )
                    ) =
                    UPPER(
                        LTRIM(
                            RTRIM(?)
                        )
                    )
                    AND Ativa = 1

                ORDER BY ID_Configuracao DESC
                """,
                (
                    inventario.ClienteId,
                    inventario.Tipo
                )
            )

            configuracao_escopo = cursor.fetchone()

            permitir_alteracao_apos_snapshot = bool(
                configuracao_escopo
                and configuracao_escopo
                    .PermitirAlteracaoEscopoAposSnapshot
            )

            if not permitir_alteracao_apos_snapshot:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "O escopo não pode ser alterado "
                        "após a geração do snapshot."
                    )
                )

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM dbo.SessoesContagem
                WHERE ID_Inventario = ?
                """,
                id_inventario
            )

            total_sessoes = int(
                cursor.fetchone()[0]
            )

            if total_sessoes > 0:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "O escopo não pode ser alterado "
                        "após o início da contagem."
                    )
                )

        validas = []
        invalidas = []
        escopo_alterado = False

        for localizacao in localizacoes:

            cursor.execute(
                """
                SELECT TOP 1
                    E.cLocalizacao

                FROM AlzarsiLog.dbo.Estoque E

                WHERE E.ClienteId = ?
                  AND E.cArmazem = ?

                  AND UPPER(
                        LTRIM(
                            RTRIM(
                                E.cLocalizacao
                            )
                        )
                      ) = ?

                  AND (
                        E.qArmazenado
                        -
                        E.qReservado
                      ) <> 0
                """,
                (
                    inventario.ClienteId,
                    inventario.cArmazem,
                    localizacao
                )
            )

            if cursor.fetchone():
                validas.append(
                    localizacao
                )
            else:
                invalidas.append(
                    localizacao
                )

        if invalidas:
            raise HTTPException(
                status_code=400,
                detail={
                    "mensagem":
                        (
                            "Existem localizações "
                            "inválidas para este "
                            "inventário."
                        ),

                    "localizacoes_invalidas":
                        invalidas
                }
            )

        adicionadas = []
        ja_existentes = []
        reativadas = []

        for localizacao in validas:

            cursor.execute(
                """
                SELECT
                    ID_EscopoLocalizacao,
                    Selecionado

                FROM dbo.InventarioEscopoLocalizacoes

                WHERE ID_Inventario = ?
                  AND Localizacao = ?
                """,
                (
                    id_inventario,
                    localizacao
                )
            )

            existente = cursor.fetchone()

            if existente:

                if existente.Selecionado:
                    ja_existentes.append(
                        localizacao
                    )

                else:
                    cursor.execute(
                        """
                        UPDATE
                            dbo.InventarioEscopoLocalizacoes

                        SET
                            Selecionado = 1,
                            MotivoExclusao = NULL,
                            DataHoraAlteracao =
                                SYSDATETIME(),
                            AlteradoPor = ?

                        WHERE
                            ID_EscopoLocalizacao = ?
                        """,
                        (
                            dados.criado_por,
                            existente.ID_EscopoLocalizacao
                        )
                    )

                    reativadas.append(
                        localizacao
                    )

                    escopo_alterado = True

            else:

                cursor.execute(
                    """
                    INSERT INTO
                        dbo.InventarioEscopoLocalizacoes
                    (
                        ID_Inventario,
                        Localizacao,
                        Selecionado,
                        CriadoPor
                    )

                    VALUES
                    (
                        ?,
                        ?,
                        1,
                        ?
                    )
                    """,
                    (
                        id_inventario,
                        localizacao,
                        dados.criado_por
                    )
                )

                adicionadas.append(
                    localizacao
                )

                escopo_alterado = True

        if (
            total_snapshot > 0
            and permitir_alteracao_apos_snapshot
            and escopo_alterado
        ):
            cursor.execute(
                """
                DELETE FROM dbo.InventarioEstoqueSnapshot
                WHERE ID_Inventario = ?
                """,
                id_inventario
            )

        uow.commit()

        return {
            "sucesso":
                True,

            "id_inventario":
                id_inventario,

            "codigo_inventario":
                inventario.CodigoInventario,

            "localizacoes_recebidas":
                len(localizacoes),

            "adicionadas":
                adicionadas,

            "reativadas":
                reativadas,

            "ja_existentes":
                ja_existentes,

            "mensagem":
                (
                    "Escopo do inventário "
                    "atualizado com sucesso."
                )
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
# CONSULTAR ESCOPO
#
# Permissão:
# ANALISE_VISUALIZAR
# ============================================================


# ============================================================
# STATUS OPERACIONAL DO ESCOPO
#
# Permissao:
# ANALISE_VISUALIZAR
#
# Regra:
# - Contagem iniciada: sempre bloqueia.
# - Snapshot + configuracao desativada: bloqueia.
# - Demais casos: permite alteracao.
# ============================================================

@router.get(
    "/inventarios/{id_inventario}/escopo/status",
    dependencies=[
        Depends(
            exigir_permissao(
                "ANALISE_VISUALIZAR"
            )
        )
    ]
)
def consultar_status_escopo_inventario(
    id_inventario: int
):

    if id_inventario <= 0:
        raise HTTPException(
            status_code=400,
            detail="Invent\u00e1rio inv\u00e1lido."
        )

    uow = None
    cursor = None

    try:

        uow = SqlServerUnitOfWork()
        uow.open()
        cursor = uow.cursor

        # ----------------------------------------------------
        # INVENTARIO
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                ID_Inventario,
                ClienteId,
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
                detail="Invent\u00e1rio n\u00e3o encontrado."
            )

        # ----------------------------------------------------
        # SNAPSHOT
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM dbo.InventarioEstoqueSnapshot
            WHERE ID_Inventario = ?
            """,
            id_inventario
        )

        total_snapshot = int(
            cursor.fetchone()[0]
        )

        snapshot_gerado = (
            total_snapshot > 0
        )

        # ----------------------------------------------------
        # CONFIGURACAO
        # Mesma consulta utilizada na gravacao do escopo.
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT TOP 1
                PermitirAlteracaoEscopoAposSnapshot

            FROM dbo.ConfiguracoesInventario

            WHERE
                ClienteId = ?
                AND UPPER(
                    LTRIM(
                        RTRIM(TipoInventario)
                    )
                ) =
                UPPER(
                    LTRIM(
                        RTRIM(?)
                    )
                )
                AND Ativa = 1

            ORDER BY ID_Configuracao DESC
            """,
            (
                inventario.ClienteId,
                inventario.Tipo
            )
        )

        configuracao_escopo = (
            cursor.fetchone()
        )

        permitir_alteracao_apos_snapshot = bool(
            configuracao_escopo
            and configuracao_escopo
                .PermitirAlteracaoEscopoAposSnapshot
        )

        # ----------------------------------------------------
        # CONTAGEM INICIADA
        # Mesmo criterio utilizado na gravacao do escopo.
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM dbo.SessoesContagem
            WHERE ID_Inventario = ?
            """,
            id_inventario
        )

        total_sessoes = int(
            cursor.fetchone()[0]
        )

        contagem_iniciada = (
            total_sessoes > 0
        )

        # ----------------------------------------------------
        # REGRA EFETIVA
        # ----------------------------------------------------

        if contagem_iniciada:

            pode_alterar_escopo = False
            motivo_bloqueio = (
                "CONTAGEM_INICIADA"
            )

        elif (
            snapshot_gerado
            and not permitir_alteracao_apos_snapshot
        ):

            pode_alterar_escopo = False
            motivo_bloqueio = (
                "SNAPSHOT_GERADO"
            )

        else:

            pode_alterar_escopo = True
            motivo_bloqueio = None

        return {
            "id_inventario":
                id_inventario,

            "snapshot_gerado":
                snapshot_gerado,

            "registros_snapshot":
                total_snapshot,

            "permitir_alteracao_apos_snapshot":
                permitir_alteracao_apos_snapshot,

            "contagem_iniciada":
                contagem_iniciada,

            "total_sessoes_contagem":
                total_sessoes,

            "pode_alterar_escopo":
                pode_alterar_escopo,

            "motivo_bloqueio":
                motivo_bloqueio,
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


@router.get(
    "/inventarios/{id_inventario}/escopo",
    dependencies=[
        Depends(
            exigir_permissao(
                "ANALISE_VISUALIZAR"
            )
        )
    ]
)
def consultar_escopo_inventario(
    id_inventario: int,
    somente_selecionados: bool = False
):

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
                ID_Inventario,
                CodigoInventario,
                Tipo,
                Cliente,
                ClienteId,
                cArmazem,
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

        sql = """
            SELECT
                ID_EscopoLocalizacao,
                Localizacao,
                Selecionado,
                MotivoExclusao,
                DataHoraInclusao,
                DataHoraAlteracao,
                CriadoPor,
                AlteradoPor

            FROM dbo.InventarioEscopoLocalizacoes

            WHERE ID_Inventario = ?
        """

        if somente_selecionados:
            sql += (
                " AND Selecionado = 1"
            )

        sql += (
            " ORDER BY Localizacao"
        )

        cursor.execute(
            sql,
            id_inventario
        )

        linhas = cursor.fetchall()

        localizacoes = []

        for linha in linhas:
            localizacoes.append({
                "id_escopo_localizacao":
                    linha.ID_EscopoLocalizacao,

                "localizacao":
                    linha.Localizacao,

                "selecionado":
                    bool(
                        linha.Selecionado
                    ),

                "motivo_exclusao":
                    linha.MotivoExclusao,

                "data_hora_inclusao":
                    linha.DataHoraInclusao,

                "data_hora_alteracao":
                    linha.DataHoraAlteracao,

                "criado_por":
                    linha.CriadoPor,

                "alterado_por":
                    linha.AlteradoPor
            })

        cursor.execute(
            """
            SELECT
                COUNT(*) AS Total,

                SUM(
                    CASE
                        WHEN Selecionado = 1
                        THEN 1
                        ELSE 0
                    END
                ) AS Selecionadas,

                SUM(
                    CASE
                        WHEN Selecionado = 0
                        THEN 1
                        ELSE 0
                    END
                ) AS Excluidas

            FROM dbo.InventarioEscopoLocalizacoes

            WHERE ID_Inventario = ?
            """,
            id_inventario
        )

        totais = cursor.fetchone()

        return {
            "id_inventario":
                id_inventario,

            "codigo_inventario":
                inventario.CodigoInventario,

            "tipo":
                inventario.Tipo,

            "cliente":
                inventario.Cliente,

            "cliente_id":
                inventario.ClienteId,

            "c_armazem":
                inventario.cArmazem,

            "status":
                inventario.Status,

            "resumo": {
                "total_localizacoes":
                    int(
                        totais.Total or 0
                    ),

                "selecionadas":
                    int(
                        totais.Selecionadas or 0
                    ),

                "excluidas":
                    int(
                        totais.Excluidas or 0
                    )
            },

            "localizacoes":
                localizacoes
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
# ESTOQUE ATUAL DO ARMAZEM
# ============================================================
#
# Consulta operacional independente de inventario.
#
# Diferente de /inventarios/{id}/estoque-candidatos:
# - nao depende de ID_Inventario
# - nao limita pelo cliente do inventario
# - pode retornar todos os clientes do armazem
# - usa qArmazenado como estoque fisico atual
#
# Permissao:
# ANALISE_VISUALIZAR
# ============================================================

@router.get(
    "/estoque/atual",
    dependencies=[
        Depends(
            exigir_permissao(
                "ANALISE_VISUALIZAR"
            )
        )
    ]
)
def listar_estoque_atual(
    armazem: str,
    cliente_id: int | None = None,
    localizacao: str | None = None,
    somente_com_estoque: bool = True,
):
    armazem = armazem.strip()

    if not armazem:
        raise HTTPException(
            status_code=400,
            detail="Armazem obrigatorio."
        )

    uow = None

    try:
        uow = SqlServerUnitOfWork()
        uow.open()

        cursor = uow.cursor

        sql = """
            SELECT
                E.Id AS id,
                E.cArmazem AS armazem,
                E.cLocalizacao AS localizacao,
                E.cItem AS codigo,
                E.cLote AS lote,
                E.ClienteId AS cliente_id,
                C.Nome AS cliente,
                E.dItem AS descricao,
                E.cUnidade AS unidade,
                E.cCategoria AS categoria,
                E.Validade AS validade,

                E.qArmazenado AS q_armazenado,
                E.qReservado AS q_reservado,
                E.qBloqueado AS q_bloqueado,
                E.qEstimado AS q_estimado,

                (
                    ISNULL(E.qArmazenado, 0)
                    -
                    ISNULL(E.qReservado, 0)
                ) AS saldo_disponivel,

                E.StatusEstoque AS status_estoque,
                E.TipoLocalizacao AS tipo_localizacao

            FROM AlzarsiLog.dbo.Estoque E

            INNER JOIN AlzarsiLog.dbo.Cliente C
                ON C.Id = E.ClienteId

            WHERE
                E.cArmazem = ?
        """

        parametros = [
            armazem
        ]

        if cliente_id is not None:
            sql += """
                AND E.ClienteId = ?
            """

            parametros.append(
                cliente_id
            )

        if localizacao and localizacao.strip():
            sql += """
                AND E.cLocalizacao = ?
            """

            parametros.append(
                localizacao.strip()
            )

        if somente_com_estoque:
            sql += """
                AND ISNULL(
                    E.qArmazenado,
                    0
                ) <> 0
            """

        sql += """
            ORDER BY
                E.cLocalizacao,
                E.ClienteId,
                E.cItem,
                E.cLote
        """

        cursor.execute(
            sql,
            *parametros
        )

        colunas = [
            coluna[0]
            for coluna
            in cursor.description
        ]

        itens = [
            dict(
                zip(
                    colunas,
                    linha
                )
            )
            for linha
            in cursor.fetchall()
        ]

        return {
            "armazem": armazem,
            "cliente_id": cliente_id,
            "localizacao": (
                localizacao.strip()
                if localizacao
                else None
            ),
            "somente_com_estoque": (
                somente_com_estoque
            ),
            "total": len(itens),
            "itens": itens,
        }

    except HTTPException:
        raise

    except Exception as erro:
        raise HTTPException(
            status_code=500,
            detail=(
                "Erro ao consultar "
                f"estoque atual: {erro}"
            )
        )

    finally:
        if uow is not None:
            uow.close()
