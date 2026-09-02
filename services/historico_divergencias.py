

# ============================================================
# NORMALIZAÇÃO
# ============================================================

def _txt(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def _loc(valor):
    return _txt(valor).upper()


def _num(valor):
    if valor is None:
        return 0.0
    return float(valor)


# ============================================================
# LOCALIZAÇÕES POSSÍVEIS NO SNAPSHOT
# ============================================================

def _localizacoes_snapshot_item(
    cursor,
    id_inventario: int,
    codigo: str,
    lote: str
):
    cursor.execute(
        """
        SELECT DISTINCT
            UPPER(LTRIM(RTRIM(Localizacao))) AS Localizacao

        FROM dbo.InventarioEstoqueSnapshot

        WHERE
            ID_Inventario = ?
            AND LTRIM(RTRIM(Codigo)) = ?
            AND ISNULL(LTRIM(RTRIM(Lote)), '') = ?
            AND NULLIF(LTRIM(RTRIM(Localizacao)), '') IS NOT NULL

        ORDER BY
            UPPER(LTRIM(RTRIM(Localizacao)))
        """,
        (
            id_inventario,
            codigo,
            lote
        )
    )

    return [
        _loc(linha.Localizacao)
        for linha in cursor.fetchall()
        if _loc(linha.Localizacao)
    ]


# ============================================================
# RESOLVER ARMAZÉM
#
# Prioridade:
# 1. Inventarios.cArmazem
# 2. Snapshot da mesma combinação
#
# Só infere pelo snapshot quando existe exatamente um armazém.
# ============================================================

def _resolver_armazem(
    cursor,
    id_inventario: int,
    armazem_inventario,
    localizacao: str,
    codigo: str,
    lote: str
):
    armazem = _txt(
        armazem_inventario
    ).upper()

    if armazem:
        return {
            "armazem": armazem,
            "origem": "INVENTARIO"
        }

    cursor.execute(
        """
        SELECT DISTINCT
            UPPER(
                LTRIM(
                    RTRIM(cArmazem)
                )
            ) AS Armazem

        FROM dbo.InventarioEstoqueSnapshot

        WHERE
            ID_Inventario = ?
            AND UPPER(
                LTRIM(
                    RTRIM(Localizacao)
                )
            ) = ?
            AND LTRIM(
                RTRIM(Codigo)
            ) = ?
            AND ISNULL(
                LTRIM(
                    RTRIM(Lote)
                ),
                ''
            ) = ?
            AND NULLIF(
                LTRIM(
                    RTRIM(cArmazem)
                ),
                ''
            ) IS NOT NULL

        ORDER BY
            UPPER(
                LTRIM(
                    RTRIM(cArmazem)
                )
            )
        """,
        (
            id_inventario,
            localizacao,
            codigo,
            lote
        )
    )

    armazens = [
        _txt(
            linha.Armazem
        ).upper()
        for linha in cursor.fetchall()
        if _txt(
            linha.Armazem
        )
    ]

    if len(armazens) == 1:
        return {
            "armazem": armazens[0],
            "origem": "INFERIDO_SNAPSHOT"
        }

    if len(armazens) > 1:
        return {
            "armazem": "",
            "origem": "AMBIGUO"
        }

    return {
        "armazem": "",
        "origem": "NAO_IDENTIFICADO"
    }


# ============================================================
# BASE DE RESULTADOS FINAIS
#
# IMPORTANTE:
# O filtro de armazém NÃO é aplicado diretamente em
# Inventarios.cArmazem, porque inventários antigos podem estar
# com cArmazem vazio e o armazém ser recuperável pelo snapshot.
# ============================================================

def _buscar_resultados_finais(
    cursor,
    cliente_id: int | None = None,
    codigo: str | None = None,
    lote: str | None = None,
    tipo_inventario: str | None = None,
    data_inicio=None,
    data_fim=None
):
    filtros = []
    parametros = []

    if cliente_id is not None:
        filtros.append(
            "I.ClienteId = ?"
        )
        parametros.append(
            cliente_id
        )

    if _txt(codigo):
        filtros.append(
            "LTRIM(RTRIM(RF.Codigo)) = ?"
        )
        parametros.append(
            _txt(codigo)
        )

    if lote is not None:
        filtros.append(
            "ISNULL(LTRIM(RTRIM(RF.Lote)), '') = ?"
        )
        parametros.append(
            _txt(lote)
        )

    if _txt(tipo_inventario):
        filtros.append(
            "UPPER(LTRIM(RTRIM(I.Tipo))) = ?"
        )
        parametros.append(
            _txt(tipo_inventario).upper()
        )

    if data_inicio is not None:
        filtros.append(
            "I.DataHoraInicio >= ?"
        )
        parametros.append(
            data_inicio
        )

    if data_fim is not None:
        filtros.append(
            """
            I.DataHoraInicio <
            DATEADD(
                DAY,
                1,
                CAST(? AS date)
            )
            """
        )
        parametros.append(
            data_fim
        )

    filtro_sql = ""

    if filtros:
        filtro_sql = (
            "WHERE "
            +
            " AND ".join(
                filtros
            )
        )

    cursor.execute(
        f"""
        SELECT
            RF.ID_ResultadoFinal,
            RF.ID_Inventario,
            RF.Codigo,
            ISNULL(RF.Lote, '') AS Lote,
            RF.Descricao,
            RF.Unidade,
            RF.Categoria,
            RF.QtdEstoque,
            RF.QuantidadeFinal,
            RF.DiferencaFinal,
            RF.StatusFinal,
            RF.OrigemQuantidade,
            RF.ID_DecisaoGestor,
            RF.RodadaFinal,
            RF.UsuarioFinalizacao,
            RF.DataHoraFinalizacao,
            RF.Localizacao,

            I.CodigoInventario,
            I.Tipo,
            I.Cliente,
            I.ClienteId,
            I.cArmazem,
            I.Status AS StatusInventario,
            I.DataHoraInicio,
            I.DataHoraFim

        FROM dbo.InventarioResultadoFinal RF

        INNER JOIN dbo.Inventarios I
            ON I.ID_Inventario = RF.ID_Inventario

        {filtro_sql}

        ORDER BY
            I.DataHoraFim,
            I.DataHoraInicio,
            RF.DataHoraFinalizacao,
            RF.ID_ResultadoFinal
        """,
        tuple(parametros)
    )

    return cursor.fetchall()


# ============================================================
# RESOLVER LOCALIZAÇÃO DO RESULTADO
#
# DIRETA:
# resultado final já possui localização.
#
# INFERIDA_SNAPSHOT:
# resultado sem localização, mas Código + Lote aparecem em
# exatamente uma localização no snapshot do inventário.
#
# AMBIGUA:
# item aparece em mais de uma localização.
#
# SEM_LOCALIZACAO:
# não existe localização recuperável pelo snapshot.
# ============================================================

def _resolver_localizacao_resultado(
    cursor,
    linha,
    cache
):
    registrada = _loc(
        linha.Localizacao
    )

    if registrada:
        return {
            "localizacao": registrada,
            "atribuicao": "DIRETA",
            "localizacoes_possiveis": [
                registrada
            ]
        }

    chave = (
        linha.ID_Inventario,
        _txt(
            linha.Codigo
        ),
        _txt(
            linha.Lote
        )
    )

    if chave not in cache:
        cache[chave] = (
            _localizacoes_snapshot_item(
                cursor=cursor,
                id_inventario=linha.ID_Inventario,
                codigo=_txt(
                    linha.Codigo
                ),
                lote=_txt(
                    linha.Lote
                )
            )
        )

    possiveis = cache[
        chave
    ]

    if len(possiveis) == 1:
        return {
            "localizacao":
                possiveis[0],

            "atribuicao":
                "INFERIDA_SNAPSHOT",

            "localizacoes_possiveis":
                possiveis
        }

    if len(possiveis) > 1:
        return {
            "localizacao": None,
            "atribuicao": "AMBIGUA",
            "localizacoes_possiveis":
                possiveis
        }

    return {
        "localizacao": None,
        "atribuicao": "SEM_LOCALIZACAO",
        "localizacoes_possiveis": []
    }


# ============================================================
# CLASSIFICAÇÃO DO RESULTADO
# ============================================================

def _status_resultado(
    status_final,
    diferenca
):
    status = (
        _txt(
            status_final
        ).upper()
    )

    diferenca = _num(
        diferenca
    )

    if (
        status == "OK"
        or
        abs(diferenca) <= 0.0001
    ):
        return "OK"

    if (
        status == "FALTA"
        or
        diferenca < 0
    ):
        return "FALTA"

    return "SOBRA"


# ============================================================
# PADRÃO DE RECORRÊNCIA
# ============================================================

def _classificar_padrao(
    faltas: int,
    sobras: int,
    divergencias_consecutivas: int
):
    if faltas >= 2 and sobras == 0:

        if divergencias_consecutivas >= 2:
            return "FALTA_PERSISTENTE"

        return "FALTA_RECORRENTE"

    if sobras >= 2 and faltas == 0:

        if divergencias_consecutivas >= 2:
            return "SOBRA_PERSISTENTE"

        return "SOBRA_RECORRENTE"

    if faltas > 0 and sobras > 0:
        return "DIVERGENCIA_OSCILANTE"

    if faltas + sobras == 1:
        return "DIVERGENCIA_ISOLADA"

    return "SEM_DIVERGENCIA"


# ============================================================
# CONSOLIDAR ORIGEM DO ARMAZÉM
# ============================================================

def _consolidar_origem_armazem(origens):
    origens = {
        origem
        for origem in origens
        if origem
    }

    if not origens:
        return "NAO_IDENTIFICADO"

    if len(origens) == 1:
        return next(
            iter(origens)
        )

    return "MISTA"


# ============================================================
# CONSULTAR HISTÓRICO DE DIVERGÊNCIAS E RECORRÊNCIA
# ============================================================

def consultar_historico_divergencias(
    cursor,
    cliente_id: int | None = None,
    armazem: str | None = None,
    localizacao: str | None = None,
    codigo: str | None = None,
    lote: str | None = None,
    tipo_inventario: str | None = None,
    data_inicio=None,
    data_fim=None,
    somente_recorrentes: bool = False
):
    localizacao_filtro = (
        _loc(
            localizacao
        )
        if localizacao
        else None
    )

    armazem_filtro = (
        _txt(
            armazem
        ).upper()
        if armazem
        else None
    )

    linhas = (
        _buscar_resultados_finais(
            cursor=cursor,
            cliente_id=cliente_id,
            codigo=codigo,
            lote=lote,
            tipo_inventario=tipo_inventario,
            data_inicio=data_inicio,
            data_fim=data_fim
        )
    )

    cache_localizacoes = {}
    cache_armazens = {}

    base = {}

    resultados_sem_localizacao = []
    resultados_sem_armazem = []

    total_resultados_validos = 0
    total_ok = 0
    total_faltas = 0
    total_sobras = 0

    quantidade_faltante_total = 0.0
    quantidade_sobrando_total = 0.0

    inventarios_validos = set()
    inventarios_com_divergencia = set()

    ultima_divergencia_global = None

    for linha in linhas:

        # ====================================================
        # RESOLVE LOCALIZAÇÃO
        # ====================================================

        resolucao_localizacao = (
            _resolver_localizacao_resultado(
                cursor=cursor,
                linha=linha,
                cache=cache_localizacoes
            )
        )

        loc_resolvida = (
            resolucao_localizacao[
                "localizacao"
            ]
        )

        if localizacao_filtro:
            if (
                loc_resolvida
                !=
                localizacao_filtro
            ):
                continue

        if not loc_resolvida:
            resultados_sem_localizacao.append(
                {
                    "id_resultado_final":
                        linha.ID_ResultadoFinal,

                    "id_inventario":
                        linha.ID_Inventario,

                    "codigo":
                        _txt(
                            linha.Codigo
                        ),

                    "lote":
                        _txt(
                            linha.Lote
                        ),

                    "atribuicao_localizacao":
                        resolucao_localizacao[
                            "atribuicao"
                        ],

                    "localizacoes_possiveis":
                        resolucao_localizacao[
                            "localizacoes_possiveis"
                        ]
                }
            )

            continue

        # ====================================================
        # RESOLVE ARMAZÉM
        # ====================================================

        chave_armazem_cache = (
            linha.ID_Inventario,
            loc_resolvida,
            _txt(
                linha.Codigo
            ),
            _txt(
                linha.Lote
            ),
            _txt(
                linha.cArmazem
            ).upper()
        )

        if (
            chave_armazem_cache
            not in cache_armazens
        ):
            cache_armazens[
                chave_armazem_cache
            ] = (
                _resolver_armazem(
                    cursor=cursor,
                    id_inventario=linha.ID_Inventario,
                    armazem_inventario=linha.cArmazem,
                    localizacao=loc_resolvida,
                    codigo=_txt(
                        linha.Codigo
                    ),
                    lote=_txt(
                        linha.Lote
                    )
                )
            )

        resolucao_armazem = (
            cache_armazens[
                chave_armazem_cache
            ]
        )

        armazem_resolvido = (
            resolucao_armazem[
                "armazem"
            ]
        )

        if armazem_filtro:
            if (
                armazem_resolvido
                !=
                armazem_filtro
            ):
                continue

        if not armazem_resolvido:
            resultados_sem_armazem.append(
                {
                    "id_resultado_final":
                        linha.ID_ResultadoFinal,

                    "id_inventario":
                        linha.ID_Inventario,

                    "localizacao":
                        loc_resolvida,

                    "codigo":
                        _txt(
                            linha.Codigo
                        ),

                    "lote":
                        _txt(
                            linha.Lote
                        ),

                    "origem_armazem":
                        resolucao_armazem[
                            "origem"
                        ]
                }
            )

        # ====================================================
        # RESULTADO VÁLIDO
        # ====================================================

        total_resultados_validos += 1

        inventarios_validos.add(
            linha.ID_Inventario
        )

        status = (
            _status_resultado(
                linha.StatusFinal,
                linha.DiferencaFinal
            )
        )

        diferenca = _num(
            linha.DiferencaFinal
        )

        if status == "OK":
            total_ok += 1

        elif status == "FALTA":
            total_faltas += 1

            quantidade_faltante_total += (
                abs(
                    diferenca
                )
            )

            inventarios_com_divergencia.add(
                linha.ID_Inventario
            )

        else:
            total_sobras += 1

            quantidade_sobrando_total += (
                abs(
                    diferenca
                )
            )

            inventarios_com_divergencia.add(
                linha.ID_Inventario
            )

        data_evento = (
            linha.DataHoraFinalizacao
            or
            linha.DataHoraFim
            or
            linha.DataHoraInicio
        )

        if (
            status != "OK"
            and
            data_evento is not None
            and
            (
                ultima_divergencia_global is None
                or
                data_evento
                >
                ultima_divergencia_global
            )
        ):
            ultima_divergencia_global = (
                data_evento
            )

        # ====================================================
        # CHAVE DA RECORRÊNCIA
        #
        # Cliente + Armazém resolvido + Localização +
        # Código + Lote
        # ====================================================

        chave = (
            linha.ClienteId,
            armazem_resolvido,
            loc_resolvida,
            _txt(
                linha.Codigo
            ),
            _txt(
                linha.Lote
            )
        )

        if chave not in base:
            base[chave] = {
                "cliente_id":
                    linha.ClienteId,

                "cliente":
                    linha.Cliente,

                "armazem":
                    armazem_resolvido,

                "origens_armazem":
                    set(),

                "localizacao":
                    loc_resolvida,

                "codigo":
                    _txt(
                        linha.Codigo
                    ),

                "lote":
                    _txt(
                        linha.Lote
                    ),

                "descricao":
                    linha.Descricao,

                "unidade":
                    linha.Unidade,

                "categoria":
                    linha.Categoria,

                "eventos": []
            }

        base[
            chave
        ][
            "origens_armazem"
        ].add(
            resolucao_armazem[
                "origem"
            ]
        )

        base[
            chave
        ]["eventos"].append(
            {
                "id_inventario":
                    linha.ID_Inventario,

                "codigo_inventario":
                    linha.CodigoInventario,

                "tipo_inventario":
                    linha.Tipo,

                "status_inventario":
                    linha.StatusInventario,

                "data_hora_inicio":
                    linha.DataHoraInicio,

                "data_hora_fim":
                    linha.DataHoraFim,

                "id_resultado_final":
                    linha.ID_ResultadoFinal,

                "data_hora_finalizacao":
                    linha.DataHoraFinalizacao,

                "status":
                    status,

                "qtd_estoque":
                    _num(
                        linha.QtdEstoque
                    ),

                "quantidade_final":
                    _num(
                        linha.QuantidadeFinal
                    ),

                "diferenca":
                    diferenca,

                "origem_quantidade":
                    linha.OrigemQuantidade,

                "rodada_final":
                    linha.RodadaFinal,

                "usuario_finalizacao":
                    linha.UsuarioFinalizacao,

                "atribuicao_localizacao":
                    resolucao_localizacao[
                        "atribuicao"
                    ],

                "armazem":
                    armazem_resolvido,

                "origem_armazem":
                    resolucao_armazem[
                        "origem"
                    ]
            }
        )

    # ========================================================
    # CONSOLIDA COMBINAÇÕES
    # ========================================================

    combinacoes = []

    for registro in base.values():

        eventos = sorted(
            registro["eventos"],
            key=lambda x: (
                x["data_hora_finalizacao"]
                or
                x["data_hora_fim"]
                or
                x["data_hora_inicio"]
            )
        )

        total = len(
            eventos
        )

        faltas = sum(
            1
            for evento in eventos
            if evento["status"] == "FALTA"
        )

        sobras = sum(
            1
            for evento in eventos
            if evento["status"] == "SOBRA"
        )

        ok = sum(
            1
            for evento in eventos
            if evento["status"] == "OK"
        )

        divergencias = (
            faltas
            +
            sobras
        )

        taxa = (
            round(
                (
                    divergencias
                    /
                    total
                )
                *
                100,
                2
            )
            if total > 0
            else 0
        )

        primeira_divergencia = None
        ultima_divergencia = None
        ultimo_ok = None

        for evento in eventos:

            data_evento = (
                evento[
                    "data_hora_finalizacao"
                ]
                or
                evento[
                    "data_hora_fim"
                ]
                or
                evento[
                    "data_hora_inicio"
                ]
            )

            if evento["status"] != "OK":

                if primeira_divergencia is None:
                    primeira_divergencia = (
                        data_evento
                    )

                ultima_divergencia = (
                    data_evento
                )

            else:
                ultimo_ok = (
                    data_evento
                )

        # Quantas divergências consecutivas existem a partir
        # do evento mais recente, até encontrar um OK.
        consecutivas = 0

        for evento in reversed(
            eventos
        ):

            if evento["status"] == "OK":
                break

            consecutivas += 1

        ultima_situacao = (
            eventos[-1]["status"]
            if eventos
            else None
        )

        direcao = "SEM_DIVERGENCIA"

        if faltas > sobras:
            direcao = "FALTA"

        elif sobras > faltas:
            direcao = "SOBRA"

        elif (
            faltas > 0
            and
            sobras > 0
        ):
            direcao = "MISTA"

        padrao = (
            _classificar_padrao(
                faltas=faltas,
                sobras=sobras,
                divergencias_consecutivas=(
                    consecutivas
                )
            )
        )

        recorrente = (
            divergencias >= 2
        )

        quantidade_falta = sum(
            abs(
                evento["diferenca"]
            )
            for evento in eventos
            if evento["status"] == "FALTA"
        )

        quantidade_sobra = sum(
            abs(
                evento["diferenca"]
            )
            for evento in eventos
            if evento["status"] == "SOBRA"
        )

        combinacoes.append(
            {
                "cliente_id":
                    registro[
                        "cliente_id"
                    ],

                "cliente":
                    registro[
                        "cliente"
                    ],

                "armazem":
                    registro[
                        "armazem"
                    ],

                "origem_armazem":
                    _consolidar_origem_armazem(
                        registro[
                            "origens_armazem"
                        ]
                    ),

                "localizacao":
                    registro[
                        "localizacao"
                    ],

                "codigo":
                    registro[
                        "codigo"
                    ],

                "lote":
                    registro[
                        "lote"
                    ],

                "descricao":
                    registro[
                        "descricao"
                    ],

                "unidade":
                    registro[
                        "unidade"
                    ],

                "categoria":
                    registro[
                        "categoria"
                    ],

                "historico": {
                    "inventarios_validos":
                        total,

                    "ok":
                        ok,

                    "faltas":
                        faltas,

                    "sobras":
                        sobras,

                    "divergencias":
                        divergencias,

                    "taxa_divergencia_percentual":
                        taxa,

                    "divergencias_consecutivas":
                        consecutivas,

                    "primeira_divergencia":
                        primeira_divergencia,

                    "ultima_divergencia":
                        ultima_divergencia,

                    "ultimo_ok":
                        ultimo_ok,

                    "ultima_situacao":
                        ultima_situacao,

                    "direcao_predominante":
                        direcao,

                    "padrao":
                        padrao,

                    "quantidade_faltante_total":
                        round(
                            quantidade_falta,
                            4
                        ),

                    "quantidade_sobrando_total":
                        round(
                            quantidade_sobra,
                            4
                        ),

                    "recorrente":
                        recorrente
                },

                "eventos":
                    eventos
            }
        )

    # ========================================================
    # FILTRO SOMENTE RECORRENTES
    # ========================================================

    if somente_recorrentes:
        combinacoes = [
            item
            for item in combinacoes
            if item[
                "historico"
            ][
                "recorrente"
            ]
        ]

    # ========================================================
    # ORDENAÇÃO
    # ========================================================

    combinacoes.sort(
        key=lambda item: (
            -item[
                "historico"
            ][
                "divergencias"
            ],
            -item[
                "historico"
            ][
                "divergencias_consecutivas"
            ],
            -item[
                "historico"
            ][
                "taxa_divergencia_percentual"
            ],
            item[
                "armazem"
            ],
            item[
                "localizacao"
            ],
            item[
                "codigo"
            ],
            item[
                "lote"
            ]
        )
    )

    combinacoes_com_divergencia = sum(
        1
        for item in combinacoes
        if item[
            "historico"
        ][
            "divergencias"
        ] > 0
    )

    combinacoes_recorrentes = sum(
        1
        for item in combinacoes
        if item[
            "historico"
        ][
            "recorrente"
        ]
    )

    taxa_recorrencia = (
        round(
            (
                combinacoes_recorrentes
                /
                len(
                    combinacoes
                )
            )
            *
            100,
            2
        )
        if combinacoes
        else 0
    )

    # ========================================================
    # RANKING DE RECORRÊNCIA
    # ========================================================

    ranking_itens = sorted(
        [
            {
                "codigo":
                    item[
                        "codigo"
                    ],

                "lote":
                    item[
                        "lote"
                    ],

                "armazem":
                    item[
                        "armazem"
                    ],

                "localizacao":
                    item[
                        "localizacao"
                    ],

                "divergencias":
                    item[
                        "historico"
                    ][
                        "divergencias"
                    ],

                "divergencias_consecutivas":
                    item[
                        "historico"
                    ][
                        "divergencias_consecutivas"
                    ],

                "taxa_divergencia_percentual":
                    item[
                        "historico"
                    ][
                        "taxa_divergencia_percentual"
                    ],

                "padrao":
                    item[
                        "historico"
                    ][
                        "padrao"
                    ]
            }
            for item in combinacoes
            if item[
                "historico"
            ][
                "divergencias"
            ] > 0
        ],
        key=lambda item: (
            -item[
                "divergencias"
            ],
            -item[
                "divergencias_consecutivas"
            ],
            -item[
                "taxa_divergencia_percentual"
            ]
        )
    )[:20]

    # ========================================================
    # RETORNO
    # ========================================================

    return {
        "tipo_consulta":
            "HISTORICO_DIVERGENCIAS_RECURRENCIA",

        "pesquisa": {
            "cliente_id":
                cliente_id,

            "armazem":
                armazem_filtro,

            "localizacao":
                localizacao_filtro,

            "codigo":
                codigo,

            "lote":
                lote,

            "tipo_inventario":
                tipo_inventario,

            "data_inicio":
                data_inicio,

            "data_fim":
                data_fim,

            "somente_recorrentes":
                somente_recorrentes
        },

        "resumo": {
            "inventarios_validos":
                len(
                    inventarios_validos
                ),

            "inventarios_com_divergencia":
                len(
                    inventarios_com_divergencia
                ),

            "resultados_item_validos":
                total_resultados_validos,

            "resultados_item_ok":
                total_ok,

            "resultados_item_falta":
                total_faltas,

            "resultados_item_sobra":
                total_sobras,

            "quantidade_faltante_total":
                round(
                    quantidade_faltante_total,
                    4
                ),

            "quantidade_sobrando_total":
                round(
                    quantidade_sobrando_total,
                    4
                ),

            "quantidade_divergencia_absoluta":
                round(
                    quantidade_faltante_total
                    +
                    quantidade_sobrando_total,
                    4
                ),

            "combinacoes_analisadas":
                len(
                    combinacoes
                ),

            "combinacoes_com_divergencia":
                combinacoes_com_divergencia,

            "combinacoes_recorrentes":
                combinacoes_recorrentes,

            "taxa_recorrencia_percentual":
                taxa_recorrencia,

            "ultima_divergencia":
                ultima_divergencia_global,

            "resultados_sem_localizacao_resolvida":
                len(
                    resultados_sem_localizacao
                ),

            "resultados_sem_armazem_resolvido":
                len(
                    resultados_sem_armazem
                )
        },

        "ranking_recorrencia":
            ranking_itens,

        "resultados_sem_localizacao_resolvida":
            resultados_sem_localizacao,

        "resultados_sem_armazem_resolvido":
            resultados_sem_armazem,

        "combinacoes":
            combinacoes
    }
