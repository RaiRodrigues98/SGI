from domain.exceptions import BusinessRuleViolation


# ============================================================
# UTILITARIOS
# ============================================================

def _txt(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def _normalizar_armazem(
    armazem: str
):
    armazem = (
        _txt(armazem)
        .upper()
    )

    if not armazem:
        raise BusinessRuleViolation(
            "Armaz?m ? obrigat?rio."
        )

    return armazem


# ============================================================
# CONSULTAR UNIVERSO ROTATIVO
# ============================================================

def consultar_universo_rotativo(
    cursor,
    cliente_id: int,
    armazem: str
):
    if not cliente_id or cliente_id <= 0:
        raise BusinessRuleViolation(
            "Cliente ? obrigat?rio."
        )

    armazem = (
        _normalizar_armazem(
            armazem
        )
    )

    # --------------------------------------------------------
    # ESTOQUE OPERACIONAL ATUAL
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT DISTINCT
            UPPER(
                LTRIM(
                    RTRIM(E.cLocalizacao)
                )
            ) AS Localizacao

        FROM AlzarsiLog.dbo.Estoque E

        WHERE
            E.ClienteId = ?
            AND UPPER(
                LTRIM(
                    RTRIM(E.cArmazem)
                )
            ) = ?
            AND E.cLocalizacao IS NOT NULL
            AND LTRIM(
                RTRIM(E.cLocalizacao)
            ) <> ''

        ORDER BY
            Localizacao
        """,
        (
            cliente_id,
            armazem,
        )
    )

    localizacoes_estoque = [
        _txt(
            linha.Localizacao
        ).upper()
        for linha in cursor.fetchall()
    ]

    # --------------------------------------------------------
    # CADASTRO MESTRE
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT
            ID_RotativoLocalizacao,
            UPPER(
                LTRIM(
                    RTRIM(Localizacao)
                )
            ) AS Localizacao,
            UPPER(
                LTRIM(
                    RTRIM(Status)
                )
            ) AS Status

        FROM dbo.RotativoLocalizacoes

        WHERE
            ClienteId = ?
            AND UPPER(
                LTRIM(
                    RTRIM(cArmazem)
                )
            ) = ?

        ORDER BY
            Localizacao
        """,
        (
            cliente_id,
            armazem,
        )
    )

    linhas_mestre = (
        cursor.fetchall()
    )

    mestre = {
        _txt(
            linha.Localizacao
        ).upper():
        {
            "id_rotativo_localizacao":
                linha.ID_RotativoLocalizacao,

            "status":
                _txt(
                    linha.Status
                ).upper(),
        }

        for linha in linhas_mestre
    }

    conjunto_estoque = set(
        localizacoes_estoque
    )

    conjunto_mestre = set(
        mestre.keys()
    )

    novas = sorted(
        conjunto_estoque
        -
        conjunto_mestre
    )

    fora_estoque = sorted(
        conjunto_mestre
        -
        conjunto_estoque
    )

    # --------------------------------------------------------
    # CICLO ABERTO
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT TOP 1
            ID_Ciclo,
            CodigoCiclo,
            Status

        FROM dbo.CiclosRotativo

        WHERE
            ClienteId = ?
            AND UPPER(
                LTRIM(
                    RTRIM(cArmazem)
                )
            ) = ?
            AND UPPER(
                LTRIM(
                    RTRIM(Status)
                )
            ) = 'ABERTO'

        ORDER BY
            ID_Ciclo DESC
        """,
        (
            cliente_id,
            armazem,
        )
    )

    ciclo = (
        cursor.fetchone()
    )

    ativos = sum(
        1
        for dados in mestre.values()
        if dados["status"] != "INATIVA"
    )

    inativos = (
        len(mestre)
        -
        ativos
    )

    return {
        "cliente_id":
            cliente_id,

        "armazem":
            armazem,

        "total_localizacoes_estoque":
            len(
                localizacoes_estoque
            ),

        "total_localizacoes_mestre":
            len(
                mestre
            ),

        "total_localizacoes_ativas":
            ativos,

        "total_localizacoes_inativas":
            inativos,

        "total_novas_localizacoes":
            len(
                novas
            ),

        "total_fora_estoque_atual":
            len(
                fora_estoque
            ),

        "configurado":
            len(mestre) > 0,

        "sincronizado":
            (
                len(novas) == 0
            ),

        "possui_ciclo_aberto":
            ciclo is not None,

        "ciclo_aberto":
            (
                {
                    "id_ciclo":
                        ciclo.ID_Ciclo,

                    "codigo_ciclo":
                        ciclo.CodigoCiclo,

                    "status":
                        ciclo.Status,
                }
                if ciclo
                else
                None
            ),

        "novas_localizacoes":
            novas,

        "localizacoes_fora_estoque_atual":
            [
                {
                    "localizacao":
                        localizacao,

                    "status":
                        mestre[
                            localizacao
                        ][
                            "status"
                        ],
                }
                for localizacao
                in fora_estoque
            ],
    }


# ============================================================
# CONFIGURAR / SINCRONIZAR UNIVERSO ROTATIVO
#
# REGRAS:
# - somente INSERT de localizacoes ausentes
# - nunca DELETE
# - nunca sobrescreve historico
# - nao altera localizacoes existentes
# - nao altera universo durante ciclo aberto
# ============================================================

def configurar_universo_rotativo(
    cursor,
    cliente_id: int,
    armazem: str
):
    if not cliente_id or cliente_id <= 0:
        raise BusinessRuleViolation(
            "Cliente ? obrigat?rio."
        )

    armazem = (
        _normalizar_armazem(
            armazem
        )
    )

    status_antes = (
        consultar_universo_rotativo(
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem,
        )
    )

    if (
        status_antes[
            "possui_ciclo_aberto"
        ]
    ):
        raise BusinessRuleViolation(
            "O universo rotativo n?o pode ser "
            "alterado enquanto existir ciclo "
            "rotativo aberto para este "
            "cliente/armaz?m."
        )

    if (
        status_antes[
            "total_localizacoes_estoque"
        ]
        == 0
    ):
        raise BusinessRuleViolation(
            "Nenhuma localiza??o operacional "
            "foi encontrada no estoque para "
            "este cliente/armaz?m."
        )

    novas = (
        status_antes[
            "novas_localizacoes"
        ]
    )

    inseridas = 0

    for localizacao in novas:

        cursor.execute(
            """
            INSERT INTO dbo.RotativoLocalizacoes (
                ClienteId,
                cArmazem,
                Localizacao,
                Status,
                Sugerida,
                DataHoraCriacao,
                DataHoraAtualizacao
            )

            SELECT
                ?,
                ?,
                ?,
                'PENDENTE',
                0,
                SYSDATETIME(),
                SYSDATETIME()

            WHERE NOT EXISTS (
                SELECT 1

                FROM dbo.RotativoLocalizacoes

                WHERE
                    ClienteId = ?
                    AND UPPER(
                        LTRIM(
                            RTRIM(cArmazem)
                        )
                    ) = ?
                    AND UPPER(
                        LTRIM(
                            RTRIM(Localizacao)
                        )
                    ) = ?
            )
            """,
            (
                cliente_id,
                armazem,
                localizacao,

                cliente_id,
                armazem,
                localizacao,
            )
        )

        if cursor.rowcount > 0:
            inseridas += 1

    status_depois = (
        consultar_universo_rotativo(
            cursor=cursor,
            cliente_id=cliente_id,
            armazem=armazem,
        )
    )

    return {
        "configurado":
            True,

        "motivo":
            (
                "UNIVERSO_CONFIGURADO"
                if inseridas > 0
                else
                "UNIVERSO_JA_CONFIGURADO"
            ),

        "localizacoes_inseridas":
            inseridas,

        "universo":
            status_depois,
    }
