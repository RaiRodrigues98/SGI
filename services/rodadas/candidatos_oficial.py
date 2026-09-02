"""
Seleção de candidatos para rodadas de divergência do inventário OFICIAL.

Fase 3 da refatoração de services.rodadas_service.

Escopo:
- candidatos da R3 a partir da comparação R1 x R2;
- candidatos das recontagens OFICIAL posteriores.

IMPORTANTE:
- refatoração exclusivamente estrutural;
- nenhuma regra de negócio alterada;
- assinaturas preservadas;
- fluxo ROTATIVO não pertence a este módulo.
"""

from domain.exceptions import BusinessRuleViolation

from services.comparativo_rodadas import (
    comparar_rodadas_oficial,
)

from services.analise_recontagem import (
    analisar_recontagem_oficial,
)


def _buscar_candidatos_r3(
    cursor,
    id_inventario: int
):

    comparativo = (
        comparar_rodadas_oficial(
            cursor=cursor,
            id_inventario=id_inventario
        )
    )

    candidatos = []

    for item in comparativo["itens"]:

        if not item.get(
            "vai_para_r3",
            False
        ):
            continue

        status_r1 = (
            item["rodada_1"]["status"]
        )

        status_r2 = (
            item["rodada_2"]["status"]
        )

        if (
            status_r1 != "OK"
            and
            status_r2 != "OK"
        ):

            motivo = (
                "DIVERGENCIA_R1_R2"
            )

        elif status_r1 != "OK":

            motivo = (
                "DIVERGENCIA_R1"
            )

        else:

            motivo = (
                "DIVERGENCIA_R2"
            )

        candidatos.append(
            {
                "codigo":
                    item["codigo"],

                "lote":
                    item["lote"],

                "motivo":
                    motivo
            }
        )

    return candidatos

def _buscar_candidatos_recontagem_anterior(
    cursor,
    id_inventario: int,
    id_rodada_origem: int
):

    analise = (
        analisar_recontagem_oficial(
            cursor=cursor,
            id_inventario=id_inventario,
            id_rodada=id_rodada_origem
        )
    )

    if not analise.get(
        "rodada_operacional_concluida",
        False
    ):

        raise BusinessRuleViolation(
            "A rodada atual ainda não foi "
                "concluída operacionalmente."
        )

    candidatos = []

    for item in analise["itens"]:

        if not item.get(
            "pendente_proxima_rodada",
            False
        ):
            continue

        status = (
            item.get(
                "status"
            )
            or
            "DIVERGÊNCIA"
        )

        numero_rodada = (
            analise["numero_rodada"]
        )

        if status == "FALTA":

            motivo = (
                f"FALTA_R{numero_rodada}"
            )

        elif status == "SOBRA":

            motivo = (
                f"SOBRA_R{numero_rodada}"
            )

        else:

            motivo = (
                f"DIVERGENCIA_R{numero_rodada}"
            )

        candidatos.append(
            {
                "codigo":
                    item["codigo"],

                "lote":
                    item["lote"],

                "motivo":
                    motivo
            }
        )

    return candidatos
