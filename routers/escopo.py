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
                (
                    E.qArmazenado
                    -
                    E.qReservado
                ) AS SaldoInventario,
                E.StatusEstoque,
                E.TipoLocalizacao

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
                "q_armazenado": float(
                    linha.qArmazenado
                ),
                "q_reservado": float(
                    linha.qReservado
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

        validas = []
        invalidas = []

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