"""
Encerramentos terminais do inventário ROTATIVO.

Fase 5 da refatoração de services.rodadas_service.

Responsabilidades:
- encerrar ROTATIVO diretamente pela R1 quando não há recontagem;
- encerrar ROTATIVO após a conclusão da R2;
- consolidar o resultado final correspondente.

IMPORTANTE:
- refatoração exclusivamente estrutural;
- nenhuma regra de negócio alterada;
- SQL, retornos e assinaturas preservados;
- não contém regras do inventário OFICIAL.
"""

from fastapi import HTTPException
from domain.exceptions import BusinessRuleViolation

from services.analise_recontagem_rotativo import (
    analisar_recontagem_rotativo,
)

from services.finalizacao_rotativo import (
    consolidar_resultado_final_rotativo,
    consolidar_resultado_final_rotativo_r1,
)

from services.rodadas.lifecycle import (
    _finalizar_rodada_atual,
)

from services.rodadas.repositories.rodada_repository import (
    buscar_r1,
)

from services.rodadas.repositories.sessao_repository import (
    contar_sessoes_abertas,
)

from services.rodadas.repositories.inventario_repository import (
    finalizar_rotativo_pela_r1,
    finalizar_rotativo_pela_r2,
)


def _encerrar_inventario_rotativo_apos_r1_sem_recontagem(
    cursor,
    inventario,
    rodada_atual
):

    # ========================================================
    # 1. VALIDA QUE É R1
    # ========================================================

    numero_rodada = int(
        rodada_atual.NumeroRodada
    )

    if numero_rodada != 1:

        raise HTTPException(
            status_code=400,
            detail=(
                "Encerramento ROTATIVO pela R1 disponível "
                "somente para a primeira rodada."
            )
        )

    # ========================================================
    # 2. NÃO PERMITE SESSÕES ABERTAS
    # ========================================================

    sessoes_abertas = (
        contar_sessoes_abertas(
            cursor=cursor,
            id_inventario=inventario.ID_Inventario,
            id_rodada=rodada_atual.ID_Rodada
        )
    )

    if sessoes_abertas > 0:

        raise HTTPException(
            status_code=400,
            detail=(
                "Existem sessões abertas na R1. "
                "Encerre todas antes de finalizar "
                "o inventário ROTATIVO."
            )
        )

    # ========================================================
    # 3. GARANTE QUE NÃO EXISTE RECONTAR ATIVO
    # ========================================================

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM dbo.DecisoesRotativo

        WHERE
            ID_Inventario = ?
            AND ID_Rodada = ?
            AND Decisao = 'RECONTAR'
            AND Status = 'ATIVA'
        """,
        (
            inventario.ID_Inventario,
            rodada_atual.ID_Rodada
        )
    )

    total_recontar = int(
        cursor.fetchone()[0]
    )

    if total_recontar > 0:

        raise HTTPException(
            status_code=400,
            detail=(
                "Existem decisões RECONTAR ativas. "
                "O inventário deve seguir para R2."
            )
        )

    # ========================================================
    # 4. GARANTE QUE NÃO EXISTEM DIVERGÊNCIAS SEM DECISÃO
    #
    # Toda ocorrência da R1 precisa estar:
    # - JUSTIFICADA; ou
    # - resolvida por alguma regra válida.
    #
    # PENDENTE não permite encerramento.
    # EM_RECONTAGEM também não permite, pois exigiria R2.
    # ========================================================

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM dbo.OcorrenciasDivergencia

        WHERE
            ID_Inventario = ?
            AND ID_Rodada = ?
            AND StatusResolucao IN
            (
                'PENDENTE',
                'EM_RECONTAGEM'
            )
        """,
        (
            inventario.ID_Inventario,
            rodada_atual.ID_Rodada
        )
    )

    divergencias_pendentes = int(
        cursor.fetchone()[0]
    )

    if divergencias_pendentes > 0:

        raise HTTPException(
            status_code=400,
            detail=(
                "Ainda existem divergências da R1 "
                "sem tratamento concluído."
            )
        )

    # ========================================================
    # 5. CONSOLIDA RESULTADO FINAL PELA R1
    # ========================================================

    resultado_final = (
        consolidar_resultado_final_rotativo_r1(
            cursor=cursor,
            id_inventario=inventario.ID_Inventario,
            id_rodada_r1=rodada_atual.ID_Rodada,
            usuario="sistema"
        )
    )

    # ========================================================
    # 6. FINALIZA R1
    # ========================================================

    _finalizar_rodada_atual(
        cursor=cursor,
        id_inventario=inventario.ID_Inventario,
        id_rodada=rodada_atual.ID_Rodada
    )

    # ========================================================
    # 7. FINALIZA INVENTÁRIO
    #
    # Não houve R2.
    # Portanto RodadaAtual = 1.
    # ========================================================

    linhas_afetadas = (
        finalizar_rotativo_pela_r1(
            cursor=cursor,
            id_inventario=inventario.ID_Inventario
        )
    )

    if linhas_afetadas == 0:

        raise HTTPException(
            status_code=400,
            detail=(
                "Não foi possível finalizar "
                "o inventário ROTATIVO pela R1."
            )
        )

    # ========================================================
    # 8. RETORNO
    # ========================================================

    return {
        "encerrado":
            True,

        "criada":
            False,

        "id_inventario":
            inventario.ID_Inventario,

        "id_rodada":
            rodada_atual.ID_Rodada,

        "numero_rodada":
            1,

        "status_inventario":
            "FINALIZADO",

        "status_rodada":
            "FINALIZADA",

        "tipo_inventario":
            "ROTATIVO",

        "motivo":
            "R1_ROTATIVO_SEM_RECONTAGEM",

        "mensagem": (
            "R1 concluída sem necessidade de recontagem. "
            "Resultado final consolidado e inventário "
            "ROTATIVO encerrado sem geração de R2."
        ),

        "resultado_final":
            resultado_final
    }

def _encerrar_inventario_rotativo_apos_r2(
    cursor,
    inventario,
    rodada_atual
):

    # ========================================================
    # 1. ANALISA R2
    # ========================================================

    analise = analisar_recontagem_rotativo(
        cursor=cursor,
        id_inventario=inventario.ID_Inventario,
        id_rodada=rodada_atual.ID_Rodada
    )

    if not analise.get(
        "rodada_operacional_concluida",
        False
    ):

        raise BusinessRuleViolation(
            "A R2 do inventário ROTATIVO ainda não foi "
                "concluída operacionalmente. Encerre todas as "
                "sessões e conclua todas as localizações previstas."
        )

    # ========================================================
    # 2. LOCALIZA R1
    # ========================================================

    r1 = (
        buscar_r1(
            cursor=cursor,
            id_inventario=inventario.ID_Inventario
        )
    )

    if not r1:

        raise HTTPException(
            status_code=400,
            detail=(
                "Não foi possível localizar a R1 "
                "do inventário ROTATIVO."
            )
        )

    # ========================================================
    # 3. CONSOLIDA RESULTADO FINAL
    # ========================================================

    resultado_final = (
        consolidar_resultado_final_rotativo(
            cursor=cursor,
            id_inventario=inventario.ID_Inventario,
            id_rodada_r1=r1.ID_Rodada,
            id_rodada_r2=rodada_atual.ID_Rodada,
            usuario="sistema"
        )
    )

    # ========================================================
    # 4. FINALIZA R2
    # ========================================================

    _finalizar_rodada_atual(
        cursor=cursor,
        id_inventario=inventario.ID_Inventario,
        id_rodada=rodada_atual.ID_Rodada
    )

    # ========================================================
    # 5. FINALIZA INVENTÁRIO
    # ========================================================

    linhas_afetadas = (
        finalizar_rotativo_pela_r2(
            cursor=cursor,
            id_inventario=inventario.ID_Inventario
        )
    )

    if linhas_afetadas == 0:

        raise HTTPException(
            status_code=400,
            detail=(
                "Não foi possível finalizar "
                "o inventário ROTATIVO."
            )
        )

    # ========================================================
    # 6. RETORNO
    # ========================================================

    return {
        "encerrado":
            True,

        "criada":
            False,

        "id_inventario":
            inventario.ID_Inventario,

        "id_rodada":
            rodada_atual.ID_Rodada,

        "numero_rodada":
            2,

        "status_inventario":
            "FINALIZADO",

        "status_rodada":
            "FINALIZADA",

        "tipo_inventario":
            "ROTATIVO",

        "motivo":
            "R2_ROTATIVO_CONCLUIDA",

        "mensagem": (
            "R2 concluída, resultado final consolidado "
            "e inventário ROTATIVO encerrado sem geração de R3."
        ),

        "resumo_r2":
            analise.get(
                "resumo",
                {}
            ),

        "resultado_final":
            resultado_final,

        "itens":
            analise.get(
                "itens",
                []
            )
    }
