from pathlib import Path
from datetime import datetime
import shutil

ROOT = Path.cwd()

SERVICE = ROOT / "services" / "indicadores_operacionais.py"
ROUTER = ROOT / "routers" / "indicadores.py"

timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backup_dir = ROOT / "backups" / f"movimentacao-12-meses-{timestamp}"
backup_dir.mkdir(parents=True, exist_ok=True)

shutil.copy2(SERVICE, backup_dir / SERVICE.name)
shutil.copy2(ROUTER, backup_dir / ROUTER.name)

print(f"[OK] Backup: {backup_dir}")

# ============================================================
# SERVICE
# ============================================================

service_text = SERVICE.read_text(encoding="utf-8")

marker_service = "# MOVIMENTACAO_12_MESES_V1"

if marker_service not in service_text:

    service_block = r'''

# ============================================================
# MOVIMENTACAO DOS ULTIMOS 12 MESES
# MOVIMENTACAO_12_MESES_V1
# ============================================================

_ARMAZEM_ESTABELECIMENTO_CNPJ = {
    "ML007": "63590553000161",
}


def _subtrair_um_ano(data: datetime) -> datetime:
    """
    Retorna exatamente um ano antes da data informada.

    Trata 29/02 convertendo para 28/02 quando o ano anterior
    nao for bissexto.
    """

    try:
        return data.replace(
            year=data.year - 1
        )
    except ValueError:
        return data.replace(
            year=data.year - 1,
            day=28
        )


def obter_movimentacao_12_meses(
    cursor,
    id_inventario: int
):
    """
    Retorna recebimentos e expedicoes efetivamente movimentados
    nos 12 meses anteriores a finalizacao de um inventario OFICIAL.

    Regras:

    Recebimento:
    - documento nao cancelado;
    - item conferido;
    - DataConferido preenchida;
    - qArmazenada > 0;
    - quantidade = qArmazenada;
    - valor = qArmazenada * ValorUnitario.

    Expedicao:
    - documento nao cancelado;
    - DataExpedicao preenchida;
    - linha local nao cancelada;
    - cArmazem igual ao inventario;
    - qExpedida > 0;
    - quantidade = qExpedida;
    - valor = qExpedida * ValorUnitario.

    Periodo:
    - fim = DataHoraFinalizacao do inventario;
    - inicio = exatamente 1 ano antes.
    """

    # --------------------------------------------------------
    # INVENTARIO + DATA FINAL
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT
            I.ID_Inventario,
            I.CodigoInventario,
            I.Tipo,
            I.ClienteId,
            I.Cliente,
            LTRIM(RTRIM(I.cArmazem)) AS Armazem,
            MAX(RF.DataHoraFinalizacao) AS DataHoraFinalizacao

        FROM dbo.Inventarios I

        LEFT JOIN dbo.InventarioResultadoFinal RF
            ON RF.ID_Inventario = I.ID_Inventario

        WHERE
            I.ID_Inventario = ?

        GROUP BY
            I.ID_Inventario,
            I.CodigoInventario,
            I.Tipo,
            I.ClienteId,
            I.Cliente,
            I.cArmazem
        """,
        (
            id_inventario,
        )
    )

    inventario = cursor.fetchone()

    if not inventario:
        raise NotFoundError(
            "Inventário não encontrado."
        )

    tipo = _normalizar_texto(
        inventario[2]
    ).upper()

    if tipo != "OFICIAL":
        raise NotFoundError(
            "Movimentação de 12 meses disponível somente "
            "para inventário oficial."
        )

    cliente_id = inventario[3]

    cliente = _normalizar_texto(
        inventario[4]
    )

    armazem = _normalizar_texto(
        inventario[5]
    ).upper()

    data_fim = inventario[6]

    if data_fim is None:
        raise NotFoundError(
            "Inventário oficial ainda não possui "
            "resultado final."
        )

    data_inicio = _subtrair_um_ano(
        data_fim
    )

    # --------------------------------------------------------
    # CNPJ CLIENTE
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT
            C.Cnpj
        FROM AlzarsiLog.dbo.Cliente C
        WHERE
            C.Id = ?
        """,
        (
            cliente_id,
        )
    )

    linha_cliente = cursor.fetchone()

    if (
        not linha_cliente
        or
        linha_cliente[0] is None
    ):
        raise NotFoundError(
            "Cliente não encontrado no AlzarsiLog."
        )

    cnpj_cliente = _normalizar_texto(
        linha_cliente[0]
    )

    # --------------------------------------------------------
    # ESTABELECIMENTO
    # --------------------------------------------------------

    cnpj_estabelecimento = (
        _ARMAZEM_ESTABELECIMENTO_CNPJ.get(
            armazem
        )
    )

    if not cnpj_estabelecimento:
        raise NotFoundError(
            f"Armazém {armazem} sem CNPJ de "
            "estabelecimento configurado."
        )

    # --------------------------------------------------------
    # MOVIMENTACOES
    # --------------------------------------------------------

    cursor.execute(
        """
        SET NOCOUNT ON;

        DECLARE @CnpjCliente VARCHAR(30) = ?;
        DECLARE @CnpjEstabelecimento VARCHAR(30) = ?;
        DECLARE @Armazem VARCHAR(50) = ?;
        DECLARE @DataInicio DATETIME2 = ?;
        DECLARE @DataFim DATETIME2 = ?;

        ;WITH Recebimentos AS
        (
            SELECT
                R.Id AS DocumentoId,
                RI.Id AS LinhaId,
                RI.CodigoItem,

                CAST(
                    ISNULL(
                        RI.qArmazenada,
                        0
                    )
                    AS DECIMAL(19,4)
                ) AS Quantidade,

                CAST(
                    RI.ValorUnitario
                    AS DECIMAL(19,6)
                ) AS ValorUnitario

            FROM AlzarsiLog.dbo.Recebimento R

            INNER JOIN
                AlzarsiLog.dbo.RecebimentoItem RI
                ON RI.RecebimentoId = R.Id

            WHERE
                R.CnpjCliente = @CnpjCliente

                AND R.CnpjEstabelecimento =
                    @CnpjEstabelecimento

                AND R.DataCancelado IS NULL

                AND RI.Conferido = 1

                AND RI.DataConferido IS NOT NULL

                AND ISNULL(
                    RI.qArmazenada,
                    0
                ) > 0

                AND RI.DataConferido >=
                    @DataInicio

                AND RI.DataConferido <=
                    @DataFim
        ),

        ResumoRecebimentos AS
        (
            SELECT
                COUNT(
                    DISTINCT DocumentoId
                ) AS Documentos,

                COUNT(*) AS Linhas,

                COUNT(
                    DISTINCT CodigoItem
                ) AS SKUs,

                ISNULL(
                    SUM(Quantidade),
                    0
                ) AS Quantidade,

                ISNULL(
                    SUM(
                        CASE
                            WHEN ValorUnitario IS NULL
                                THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS LinhasSemValor,

                ISNULL(
                    SUM(
                        CASE
                            WHEN ValorUnitario IS NOT NULL
                                THEN
                                    Quantidade
                                    *
                                    ValorUnitario
                            ELSE 0
                        END
                    ),
                    0
                ) AS ValorConhecido

            FROM Recebimentos
        ),

        Expedicoes AS
        (
            SELECT
                E.Id AS DocumentoId,
                EILL.Id AS LinhaId,
                EI.CodigoItem,

                CAST(
                    ISNULL(
                        EILL.qExpedida,
                        0
                    )
                    AS DECIMAL(19,4)
                ) AS Quantidade,

                CAST(
                    EI.ValorUnitario
                    AS DECIMAL(19,6)
                ) AS ValorUnitario

            FROM AlzarsiLog.dbo.Expedicao E

            INNER JOIN
                AlzarsiLog.dbo.ExpedicaoItem EI
                ON EI.ExpedicaoId = E.Id

            INNER JOIN
                AlzarsiLog.dbo.ExpedicaoItemLinhaLocal EILL
                ON EILL.ExpedicaoItemId = EI.Id

            WHERE
                E.CnpjCliente = @CnpjCliente

                AND E.CnpjEstabelecimento =
                    @CnpjEstabelecimento

                AND E.DataCancelado IS NULL

                AND E.DataExpedicao IS NOT NULL

                AND EILL.DataCancelamento IS NULL

                AND LTRIM(
                    RTRIM(EILL.cArmazem)
                ) = @Armazem

                AND ISNULL(
                    EILL.qExpedida,
                    0
                ) > 0

                AND E.DataExpedicao >=
                    @DataInicio

                AND E.DataExpedicao <=
                    @DataFim
        ),

        ResumoExpedicoes AS
        (
            SELECT
                COUNT(
                    DISTINCT DocumentoId
                ) AS Documentos,

                COUNT(*) AS Linhas,

                COUNT(
                    DISTINCT CodigoItem
                ) AS SKUs,

                ISNULL(
                    SUM(Quantidade),
                    0
                ) AS Quantidade,

                ISNULL(
                    SUM(
                        CASE
                            WHEN ValorUnitario IS NULL
                                THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS LinhasSemValor,

                ISNULL(
                    SUM(
                        CASE
                            WHEN ValorUnitario IS NOT NULL
                                THEN
                                    Quantidade
                                    *
                                    ValorUnitario
                            ELSE 0
                        END
                    ),
                    0
                ) AS ValorConhecido

            FROM Expedicoes
        )

        SELECT
            R.Documentos,
            R.Linhas,
            R.SKUs,
            R.Quantidade,
            R.LinhasSemValor,
            R.ValorConhecido,

            E.Documentos,
            E.Linhas,
            E.SKUs,
            E.Quantidade,
            E.LinhasSemValor,
            E.ValorConhecido

        FROM ResumoRecebimentos R
        CROSS JOIN ResumoExpedicoes E;
        """,
        (
            cnpj_cliente,
            cnpj_estabelecimento,
            armazem,
            data_inicio,
            data_fim
        )
    )

    resumo = cursor.fetchone()

    if not resumo:
        raise NotFoundError(
            "Não foi possível calcular a movimentação."
        )

    recebimentos_documentos = int(
        resumo[0] or 0
    )
    recebimentos_linhas = int(
        resumo[1] or 0
    )
    recebimentos_skus = int(
        resumo[2] or 0
    )
    recebimentos_quantidade = float(
        resumo[3] or 0
    )
    recebimentos_sem_valor = int(
        resumo[4] or 0
    )
    recebimentos_valor_conhecido = float(
        resumo[5] or 0
    )

    expedicoes_documentos = int(
        resumo[6] or 0
    )
    expedicoes_linhas = int(
        resumo[7] or 0
    )
    expedicoes_skus = int(
        resumo[8] or 0
    )
    expedicoes_quantidade = float(
        resumo[9] or 0
    )
    expedicoes_sem_valor = int(
        resumo[10] or 0
    )
    expedicoes_valor_conhecido = float(
        resumo[11] or 0
    )

    recebimentos_valor = (
        None
        if recebimentos_sem_valor > 0
        else recebimentos_valor_conhecido
    )

    expedicoes_valor = (
        None
        if expedicoes_sem_valor > 0
        else expedicoes_valor_conhecido
    )

    valor_total = (
        None
        if (
            recebimentos_valor is None
            or
            expedicoes_valor is None
        )
        else
        recebimentos_valor
        +
        expedicoes_valor
    )

    return {
        "id_inventario": int(
            inventario[0]
        ),
        "codigo_inventario": _normalizar_texto(
            inventario[1]
        ),
        "cliente_id": int(
            cliente_id
        ),
        "cliente": cliente,
        "armazem": armazem,

        "periodo": {
            "inicio": data_inicio,
            "fim": data_fim,
            "dias": (
                data_fim
                -
                data_inicio
            ).days,
        },

        "recebimentos": {
            "documentos":
                recebimentos_documentos,

            "linhas":
                recebimentos_linhas,

            "skus":
                recebimentos_skus,

            "quantidade":
                recebimentos_quantidade,

            "valor":
                recebimentos_valor,

            "linhas_sem_valor":
                recebimentos_sem_valor,
        },

        "expedicoes": {
            "documentos":
                expedicoes_documentos,

            "linhas":
                expedicoes_linhas,

            "skus":
                expedicoes_skus,

            "quantidade":
                expedicoes_quantidade,

            "valor":
                expedicoes_valor,

            "linhas_sem_valor":
                expedicoes_sem_valor,
        },

        "total": {
            "documentos":
                recebimentos_documentos
                +
                expedicoes_documentos,

            "linhas":
                recebimentos_linhas
                +
                expedicoes_linhas,

            "quantidade":
                recebimentos_quantidade
                +
                expedicoes_quantidade,

            "valor_movimentado":
                valor_total,
        },
    }
'''

    SERVICE.write_text(
        service_text.rstrip()
        + service_block
        + "\n",
        encoding="utf-8"
    )

    print("[OK] Service atualizado.")

else:
    print("[SKIP] Service já contém MOVIMENTACAO_12_MESES_V1.")


# ============================================================
# ROUTER
# ============================================================

router_text = ROUTER.read_text(
    encoding="utf-8"
)

marker_router = "# MOVIMENTACAO_12_MESES_V1"

if marker_router not in router_text:

    antigo = '''from services.indicadores_operacionais import (
    obter_acompanhamento_inventario,
    obter_acompanhamento_localizacoes,
    obter_produtividade_inventario,
)'''

    novo = '''from services.indicadores_operacionais import (
    obter_acompanhamento_inventario,
    obter_acompanhamento_localizacoes,
    obter_produtividade_inventario,
    obter_movimentacao_12_meses,
)'''

    if antigo not in router_text:
        raise SystemExit(
            "[ERRO] Bloco de import esperado não encontrado "
            "em routers/indicadores.py. Nenhuma alteração no router."
        )

    router_text = router_text.replace(
        antigo,
        novo,
        1
    )

    route_block = r'''

# ============================================================
# MOVIMENTACAO DOS ULTIMOS 12 MESES
# MOVIMENTACAO_12_MESES_V1
# ============================================================

@router.get(
    "/{id_inventario}/indicadores/movimentacao-12-meses"
)
def consultar_movimentacao_12_meses(
    id_inventario: int
):

    conn = None
    cursor = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        return obter_movimentacao_12_meses(
            cursor=cursor,
            id_inventario=id_inventario
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

        if cursor:
            cursor.close()

        if conn:
            conn.close()
'''

    ROUTER.write_text(
        router_text.rstrip()
        + route_block
        + "\n",
        encoding="utf-8"
    )

    print("[OK] Router atualizado.")

else:
    print("[SKIP] Router já contém MOVIMENTACAO_12_MESES_V1.")

print("")
print("==============================================")
print("PATCH BACKEND CONCLUIDO")
print("==============================================")
print(f"Backup: {backup_dir}")
