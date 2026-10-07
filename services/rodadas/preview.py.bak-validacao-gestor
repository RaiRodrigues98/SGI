"""
Preview da próxima rodada.

Fase 6 da refatoração de services.rodadas_service.

Responsabilidade:
- calcular/visualizar o que aconteceria na próxima rodada;
- não criar rodada;
- não finalizar rodada;
- não persistir mudanças operacionais.

IMPORTANTE:
- refatoração estrutural;
- assinatura e retorno preservados;
- dependências explícitas;
- corrige o import ausente de analisar_recontagem_oficial,
  detectado durante a análise estática da Fase 5.
"""

from services.configuracoes_inventario_aplicadas import (
    obter_configuracao_aplicada,
    obter_tipo_proxima_rodada_aplicada,
)

from services.rodadas.localizacoes import (
    rodada_operacional_concluida,
)

from services.analise_recontagem import (
    analisar_recontagem_oficial,
)

from services.analise_recontagem_rotativo import (
    analisar_recontagem_rotativo,
)

from services.rodadas.candidatos_rotativo import (
    _validar_divergencias_r1_rotativo_tratadas,
    _buscar_candidatos_r2_rotativo,
)

from services.rodadas.candidatos_oficial import (
    _buscar_candidatos_r2_oficial,
    _buscar_candidatos_r3,
)

from services.rodadas.gestor import (
    _existem_decisoes_gestor_ativas,
    _buscar_candidatos_gestor,
)

from services.rodadas.repositories.rodada_repository import (
    buscar_proxima_rodada_preview,
)

from services.rodadas.repositories.sessao_repository import (
    contar_sessoes_abertas,
)


def _normalizar_texto(valor):

    if valor is None:
        return ""

    return str(valor).strip()


def visualizar_proxima_rodada(
    cursor,
    inventario,
    rodada_atual
):

    numero_atual = int(
        rodada_atual.NumeroRodada
    )

    numero_proxima = (
        numero_atual + 1
    )

    tipo_inventario = (
        _normalizar_texto(
            inventario.Tipo
        )
        .upper()
    )

    r2_rotativo = (
        tipo_inventario == "ROTATIVO"
        and numero_atual == 1
        and numero_proxima == 2
    )

    # ========================================================
    # R2 ROTATIVO É ETAPA FINAL
    # ========================================================

    if (
        tipo_inventario == "ROTATIVO"
        and numero_atual == 2
    ):
        analise = analisar_recontagem_rotativo(
            cursor=cursor,
            id_inventario=inventario.ID_Inventario,
            id_rodada=rodada_atual.ID_Rodada
        )

        concluida = bool(
            analise.get(
                "rodada_operacional_concluida",
                False
            )
        )

        return {
            "pode_criar": False,
            "pode_encerrar": concluida,
            "motivo": (
                "R2_ROTATIVO_PRONTA_PARA_ENCERRAR"
                if concluida
                else "R2_ROTATIVO_NAO_CONCLUIDA"
            ),
            "id_inventario": inventario.ID_Inventario,
            "numero_rodada_atual": 2,
            "numero_proxima_rodada": None,
            "tipo_proxima_rodada": "FINALIZADO",
            "candidatos": 0,
            "pode_encaminhar_gestor": False,
            "resumo_r2": analise.get("resumo", {})
        }

    # ========================================================
    # 1. CONFIGURAÇÃO
    # ========================================================

    configuracao = (
        obter_configuracao_aplicada(
            cursor=cursor,
            id_inventario=inventario.ID_Inventario
        )
    )

    max_rodadas = int(
        configuracao[
            "max_rodadas"
        ]
    )

    rodadas_iniciais = int(
        configuracao[
            "rodadas_iniciais"
        ]
    )

    permitir_gestor_antecipado = bool(
        configuracao[
            "permitir_gestor_antecipado"
        ]
    )

    limite_gestor_antecipado = int(
        configuracao[
            "limite_itens_gestor_antecipado"
        ]
    )

    # ========================================================
    # 2. LIMITE
    # ========================================================

    if numero_proxima > max_rodadas:

        return {
            "pode_criar":
                False,

            "motivo":
                "MAX_RODADAS_ATINGIDO",

            "numero_rodada_atual":
                numero_atual,

            "numero_proxima_rodada":
                None,

            "tipo_proxima_rodada":
                "FINALIZADO",

            "candidatos":
                0,

            "pode_encaminhar_gestor":
                False
        }

    # ========================================================
    # 3. TIPO DA PRÓXIMA RODADA
    # ========================================================

    tipo_proxima = (
        obter_tipo_proxima_rodada_aplicada(
            cursor=cursor,
            id_inventario=inventario.ID_Inventario,
            numero_rodada_atual=numero_atual
        )
    )

    if tipo_proxima == "FINALIZADO":

        return {
            "pode_criar":
                False,

            "motivo":
                "FLUXO_FINALIZADO",

            "numero_rodada_atual":
                numero_atual,

            "numero_proxima_rodada":
                None,

            "tipo_proxima_rodada":
                "FINALIZADO",

            "candidatos":
                0,

            "pode_encaminhar_gestor":
                False
        }

    if tipo_proxima == "NAO_CONFIGURADA":

        return {
            "pode_criar":
                False,

            "motivo":
                "PROXIMA_RODADA_NAO_CONFIGURADA",

            "numero_rodada_atual":
                numero_atual,

            "numero_proxima_rodada":
                numero_proxima,

            "tipo_proxima_rodada":
                tipo_proxima,

            "candidatos":
                0,

            "pode_encaminhar_gestor":
                False
        }

    # ========================================================
    # 4. SESSÕES ABERTAS
    # ========================================================

    sessoes_abertas = (
        contar_sessoes_abertas(
            cursor=cursor,
            id_inventario=inventario.ID_Inventario,
            id_rodada=rodada_atual.ID_Rodada
        )
    )

    if sessoes_abertas > 0:

        return {
            "pode_criar":
                False,

            "motivo":
                "SESSOES_ABERTAS",

            "sessoes_abertas":
                sessoes_abertas,

            "numero_rodada_atual":
                numero_atual,

            "numero_proxima_rodada":
                numero_proxima,

            "tipo_proxima_rodada":
                tipo_proxima,

            "candidatos":
                0,

            "pode_encaminhar_gestor":
                False
        }

    # ========================================================
    # 5. EVITA DUPLICIDADE
    # ========================================================

    existente = (
        buscar_proxima_rodada_preview(
            cursor=cursor,
            id_inventario=inventario.ID_Inventario,
            numero_proxima=numero_proxima
        )
    )

    if existente:

        return {
            "pode_criar":
                False,

            "motivo":
                "RODADA_JA_EXISTE",

            "id_rodada_existente":
                existente.ID_Rodada,

            "numero_rodada_atual":
                numero_atual,

            "numero_proxima_rodada":
                existente.NumeroRodada,

            "tipo_proxima_rodada":
                tipo_proxima,

            "candidatos":
                0,

            "pode_encaminhar_gestor":
                False
        }

    # ========================================================
    # 6. CANDIDATOS
    # ========================================================

    candidatos = []

    origem_candidatos = None

    pode_encaminhar_gestor = False

    # ========================================================
    # R2 ROTATIVO
    # ========================================================

    if (
        r2_rotativo
        and tipo_proxima == "DIVERGENCIAS"
    ):

        _validar_divergencias_r1_rotativo_tratadas(
            cursor=cursor,
            id_inventario=inventario.ID_Inventario,
            id_rodada_r1=rodada_atual.ID_Rodada
        )

        candidatos = (
            _buscar_candidatos_r2_rotativo(
                cursor=cursor,
                id_inventario=(
                    inventario.ID_Inventario
                ),
                id_rodada_origem=(
                    rodada_atual.ID_Rodada
                )
            )
        )

        origem_candidatos = (
            "DIVERGENCIAS_R1_ROTATIVO"
        )

    # ========================================================
    # PRIMEIRA RODADA DE DIVERGÊNCIAS - OFICIAL
    # ========================================================

    elif (
        tipo_inventario == "OFICIAL"
        and
        rodadas_iniciais == 1
        and
        numero_proxima == 2
        and
        tipo_proxima == "DIVERGENCIAS"
    ):

        if not rodada_operacional_concluida(
            cursor=cursor,
            id_rodada=rodada_atual.ID_Rodada
        ):
            return {
                "pode_criar": False,
                "motivo":
                    "RODADA_OPERACIONAL_NAO_CONCLUIDA",
                "numero_rodada_atual":
                    numero_atual,
                "numero_proxima_rodada":
                    numero_proxima,
                "tipo_proxima_rodada":
                    tipo_proxima,
                "candidatos": 0,
                "pode_encaminhar_gestor": False,
            }

        candidatos = (
            _buscar_candidatos_r2_oficial(
                cursor=cursor,
                id_inventario=(
                    inventario.ID_Inventario
                ),
                id_rodada_origem=(
                    rodada_atual.ID_Rodada
                )
            )
        )

        origem_candidatos = (
            "DIVERGENCIAS_R1_OFICIAL"
        )

    elif (
        numero_proxima == (
            rodadas_iniciais + 1
        )
        and
        tipo_proxima == "DIVERGENCIAS"
        and
        rodadas_iniciais == 2
    ):

        candidatos = (
            _buscar_candidatos_r3(
                cursor=cursor,
                id_inventario=(
                    inventario.ID_Inventario
                )
            )
        )

        origem_candidatos = (
            "DIVERGENCIAS_R1_R2"
        )

    # ========================================================
    # R4+
    # ========================================================

    elif tipo_proxima == "DIVERGENCIAS":

        possui_decisoes_gestor = (
            _existem_decisoes_gestor_ativas(
                cursor=cursor,
                id_inventario=(
                    inventario.ID_Inventario
                )
            )
        )

        if possui_decisoes_gestor:

            candidatos = (
                _buscar_candidatos_gestor(
                    cursor=cursor,
                    id_inventario=(
                        inventario.ID_Inventario
                    )
                )
            )

            origem_candidatos = (
                "DECISAO_GESTOR"
            )

        else:

            analise = (
                analisar_recontagem_oficial(
                    cursor=cursor,
                    id_inventario=(
                        inventario.ID_Inventario
                    ),
                    id_rodada=(
                        rodada_atual.ID_Rodada
                    )
                )
            )

            rodada_concluida = bool(
                analise.get(
                    "rodada_operacional_concluida",
                    False
                )
            )

            if not rodada_concluida:

                return {
                    "pode_criar":
                        False,

                    "motivo":
                        "RODADA_OPERACIONAL_NAO_CONCLUIDA",

                    "numero_rodada_atual":
                        numero_atual,

                    "numero_proxima_rodada":
                        numero_proxima,

                    "tipo_proxima_rodada":
                        tipo_proxima,

                    "candidatos":
                        0,

                    "pode_encaminhar_gestor":
                        False
                }

            for item in analise["itens"]:

                if not item.get(
                    "pendente_proxima_rodada",
                    False
                ):
                    continue

                candidatos.append(
                    {
                        "codigo":
                            item["codigo"],

                        "lote":
                            item["lote"],

                        "status":
                            item.get("status")
                    }
                )

            origem_candidatos = (
                "DIVERGENCIAS_RODADA_ANTERIOR"
            )

            if (
                permitir_gestor_antecipado
                and
                limite_gestor_antecipado > 0
                and
                len(candidatos) > 0
                and
                len(candidatos)
                <= limite_gestor_antecipado
            ):

                pode_encaminhar_gestor = True

    # ========================================================
    # GESTOR
    # ========================================================

    elif tipo_proxima == "GESTOR":

        return {
            "pode_criar":
                False,

            "motivo":
                "PROXIMA_ETAPA_GESTOR",

            "numero_rodada_atual":
                numero_atual,

            "numero_proxima_rodada":
                numero_proxima,

            "tipo_proxima_rodada":
                tipo_proxima,

            "candidatos":
                0,

            "pode_encaminhar_gestor":
                True
        }

    # ========================================================
    # COMPLETA
    # ========================================================

    elif tipo_proxima == "COMPLETA":

        if (
            tipo_inventario == "OFICIAL"
            and
            not rodada_operacional_concluida(
                cursor=cursor,
                id_rodada=rodada_atual.ID_Rodada
            )
        ):

            return {
                "pode_criar":
                    False,

                "motivo":
                    "RODADA_OPERACIONAL_NAO_CONCLUIDA",

                "numero_rodada_atual":
                    numero_atual,

                "numero_proxima_rodada":
                    numero_proxima,

                "tipo_proxima_rodada":
                    tipo_proxima,

                "origem_candidatos":
                    "ESCOPO_COMPLETO",

                "candidatos":
                    0,

                "pode_encaminhar_gestor":
                    False
            }

        origem_candidatos = (
            "ESCOPO_COMPLETO"
        )

    else:

        return {
            "pode_criar":
                False,

            "motivo":
                "TIPO_NAO_SUPORTADO",

            "numero_rodada_atual":
                numero_atual,

            "numero_proxima_rodada":
                numero_proxima,

            "tipo_proxima_rodada":
                tipo_proxima,

            "candidatos":
                0,

            "pode_encaminhar_gestor":
                False
        }

    # ========================================================
    # 7. SEM CANDIDATOS
    # ========================================================

    if (
        tipo_proxima == "DIVERGENCIAS"
        and
        not candidatos
    ):

        return {
            "pode_criar":
                False,

            "motivo":
                "SEM_CANDIDATOS",

            "numero_rodada_atual":
                numero_atual,

            "numero_proxima_rodada":
                numero_proxima,

            "tipo_proxima_rodada":
                tipo_proxima,

            "origem_candidatos":
                origem_candidatos,

            "candidatos":
                0,

            "pode_encaminhar_gestor":
                False
        }

    # ========================================================
    # 8. PREVIEW
    # ========================================================

    return {
        "pode_criar":
            True,

        "motivo":
            None,

        "id_inventario":
            inventario.ID_Inventario,

        "numero_rodada_atual":
            numero_atual,

        "numero_proxima_rodada":
            numero_proxima,

        "tipo_proxima_rodada":
            tipo_proxima,

        "origem_candidatos":
            origem_candidatos,

        "candidatos":
            len(candidatos),

        "pode_encaminhar_gestor":
            pode_encaminhar_gestor,

        "configuracao": {
            "rodadas_iniciais":
                rodadas_iniciais,

            "max_rodadas":
                max_rodadas,

            "permitir_gestor_antecipado":
                permitir_gestor_antecipado,

            "limite_itens_gestor_antecipado":
                limite_gestor_antecipado
        },

        "itens_candidatos":
            candidatos
    }
