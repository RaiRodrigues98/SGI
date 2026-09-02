from fastapi import HTTPException

from services.configuracoes_inventario import (
    obter_configuracao_inventario,
    obter_tipo_proxima_rodada_configurada,
)
from services.analise_gestor import (
    analisar_inventario_gestor,
)


from services.rodadas import (
    _inserir_rodada_item,
    _buscar_localizacoes_snapshot_item,
    _buscar_localizacoes_contagem_item,
    _buscar_localizacoes_para_item,
    _inserir_rodada_localizacao,
    sincronizar_localizacoes_recontagem,
)

from services.rodadas.candidatos_rotativo import (
    _validar_divergencias_r1_rotativo_tratadas,
    _buscar_colunas_tabela,
    _resolver_coluna_quantidade_rotativo,
    _buscar_candidatos_r2_rotativo,
)

from services.rodadas.candidatos_oficial import (
    _buscar_candidatos_r3,
    _buscar_candidatos_recontagem_anterior,
)

from services.rodadas.gestor import (
    _buscar_itens_nova_recontagem_gestor,
    _existem_decisoes_gestor_ativas,
    _buscar_candidatos_gestor,
)

from services.rodadas.lifecycle import (
    _finalizar_rodada_atual,
)

from services.rodadas.finalizacao_rotativo import (
    _encerrar_inventario_rotativo_apos_r1_sem_recontagem,
    _encerrar_inventario_rotativo_apos_r2,
)

from services.rodadas.preview import (
    visualizar_proxima_rodada,
)

# ============================================================
# NORMALIZAÇÃO
# ============================================================

def _normalizar_texto(valor):

    if valor is None:
        return ""

    return str(valor).strip()


def _normalizar_lote(valor):

    return _normalizar_texto(valor)


def _normalizar_localizacao(valor):

    return (
        _normalizar_texto(valor)
        .upper()
    )


# ============================================================
# FINALIZAR RODADA ATUAL
#
# Usado quando a próxima rodada será criada.
#
# Regras:
# - é idempotente: se já estiver FINALIZADA, não altera;
# - não permite avançar uma rodada CANCELADA;
# - preenche DataHoraFim automaticamente;
# - o commit continua sendo responsabilidade do router.
# ============================================================



# ============================================================
# BUSCAR DECISÕES ATIVAS DO GESTOR
#
# Retorna somente itens marcados:
#
# NOVA_RECONTAGEM
# ============================================================



# ============================================================
# VERIFICA SE EXISTEM DECISÕES GERENCIAIS ATIVAS
# ============================================================



# ============================================================
# BUSCAR LOCALIZAÇÕES DO SNAPSHOT
# ============================================================



# ============================================================
# BUSCAR LOCALIZAÇÕES HISTÓRICAS
# ============================================================



# ============================================================
# BUSCAR LOCALIZAÇÕES PARA RECONTAGEM
# ============================================================



# ============================================================
# INSERIR ITEM NA RODADA
# ============================================================



# ============================================================
# INSERIR LOCALIZAÇÃO NA RODADA
# ============================================================



# ============================================================
# SINCRONIZAR LOCALIZAÇÕES DE RECONTAGEM
# ============================================================





# ============================================================
# VALIDAR TRATAMENTO DAS DIVERGÊNCIAS DA R1 - ROTATIVO
# ============================================================



# ============================================================
# CANDIDATOS R2 - INVENTÁRIO ROTATIVO
#
# Regra:
# - compara a R1 contra o snapshot pela chave
#   Localização + Código + Lote;
# - envia para a R2 somente chaves divergentes;
# - preserva as localizações efetivamente divergentes, sem
#   ampliar o escopo para todas as localizações do item;
# - não utiliza nenhuma rotina de análise do inventário OFICIAL.
# ============================================================






# ============================================================
# CANDIDATOS R3
#
# R1 ou R2 divergente
# ============================================================



# ============================================================
# CANDIDATOS DA RODADA ANTERIOR
# ============================================================



# ============================================================
# CANDIDATOS DEFINIDOS PELO GESTOR
#
# Apenas NOVA_RECONTAGEM
# ============================================================



# ============================================================
# ENCERRAR INVENTÁRIO ROTATIVO APÓS R2
#
# Regra de negócio:
# - R2 é a última rodada física do ROTATIVO;
# - não cria R3;
# - exige conclusão operacional da R2;
# - divergências permanecem registradas para auditoria/relatório;
# - o commit continua sendo responsabilidade do router.
# ============================================================
# ============================================================
# ENCERRAR INVENTÁRIO ROTATIVO APÓS R1 SEM RECONTAGEM
#
# Regra:
# - R1 foi concluída;
# - não existem candidatos RECONTAR;
# - divergências existentes já foram justificadas;
# - não cria R2;
# - consolida resultado final diretamente pela R1;
# - RodadaAtual permanece 1;
# - commit continua responsabilidade do router.
# ============================================================

# ============================================================
# ENCERRAR INVENTÁRIO ROTATIVO APÓS R2
#
# Regras:
# - R2 é a última rodada física do ROTATIVO;
# - não cria R3;
# - exige conclusão operacional da R2;
# - consolida resultado final antes de finalizar;
# - commit continua sendo responsabilidade do router.
# ============================================================

# ============================================================
# CRIAR PRÓXIMA RODADA
# ============================================================

def criar_proxima_rodada(
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
    # ENCERRAMENTO DO ROTATIVO APÓS R2
    #
    # R2 é terminal para inventário ROTATIVO. Não consultar
    # configuração de R3 e não reutilizar fluxo do OFICIAL.
    # ========================================================

    if (
        tipo_inventario == "ROTATIVO"
        and numero_atual == 2
    ):
        return _encerrar_inventario_rotativo_apos_r2(
            cursor=cursor,
            inventario=inventario,
            rodada_atual=rodada_atual
        )

    # ========================================================
    # 1. CARREGA CONFIGURAÇÃO DO CLIENTE
    # ========================================================

    configuracao = (
        obter_configuracao_inventario(
            cursor=cursor,
            cliente_id=inventario.ClienteId,
            tipo_inventario=inventario.Tipo
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

    recontagem_por_localizacao = bool(
        configuracao[
            "recontagem_por_localizacao"
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
    # 2. LIMITE DE RODADAS
    # ========================================================

    if numero_proxima > max_rodadas:

        raise HTTPException(
            status_code=400,
            detail=(
                "O inventário atingiu o número máximo "
                f"de rodadas configurado ({max_rodadas})."
            )
        )

    # ========================================================
    # 3. TIPO DA PRÓXIMA RODADA
    # ========================================================

    tipo_proxima = (
        obter_tipo_proxima_rodada_configurada(
            cursor=cursor,
            cliente_id=inventario.ClienteId,
            tipo_inventario=inventario.Tipo,
            numero_rodada_atual=numero_atual
        )
    )

    if tipo_proxima == "FINALIZADO":

        raise HTTPException(
            status_code=400,
            detail=(
                "Não existe próxima rodada configurada. "
                "O inventário atingiu o fim do fluxo "
                "de rodadas."
            )
        )

    if tipo_proxima == "NAO_CONFIGURADA":

        raise HTTPException(
            status_code=400,
            detail=(
                "A próxima rodada não está configurada "
                "para este cliente e tipo de inventário."
            )
        )

    # ========================================================
    # 4. NÃO PERMITE SESSÕES ABERTAS
    # ========================================================

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM dbo.SessoesContagem

        WHERE
            ID_Inventario = ?
            AND ID_Rodada = ?
            AND Status = 'ABERTA'
        """,
        (
            inventario.ID_Inventario,
            rodada_atual.ID_Rodada
        )
    )

    sessoes_abertas = (
        cursor.fetchone()[0]
    )

    if sessoes_abertas > 0:

        raise HTTPException(
            status_code=400,
            detail=(
                "Existem sessões abertas na rodada atual. "
                "Encerre todas antes de criar "
                "a próxima rodada."
            )
        )

    # ========================================================
    # 5. SERIALIZA CRIAÇÃO DA R2 ROTATIVO
    #
    # Duas requisições simultâneas podem passar pelo SELECT de
    # existência antes que qualquer uma tenha inserido a R2.
    # A constraint UQ_RodadasInventario protege o banco, mas sem
    # serialização a segunda requisição recebe erro 2627/HTTP 500.
    #
    # O application lock é transacional e restrito somente à
    # criação R1 -> R2 do ROTATIVO, preservando o fluxo OFICIAL.
    # A segunda requisição aguarda o commit da primeira e, então,
    # cai naturalmente no bloco idempotente "existente".
    # ========================================================

    if r2_rotativo:

        recurso_lock = (
            "SGI:ROTATIVO:PROXIMA_RODADA:"
            f"{inventario.ID_Inventario}:"
            f"{numero_proxima}"
        )

        cursor.execute(
            """
            DECLARE @resultado_lock INT;

            EXEC @resultado_lock = sys.sp_getapplock
                @Resource = ?,
                @LockMode = 'Exclusive',
                @LockOwner = 'Transaction',
                @LockTimeout = 10000;

            SELECT @resultado_lock AS ResultadoLock;
            """,
            recurso_lock
        )

        resultado_lock = int(
            cursor.fetchone()[0]
        )

        if resultado_lock < 0:

            raise HTTPException(
                status_code=409,
                detail=(
                    "Não foi possível obter exclusividade para "
                    "criar a R2 do inventário ROTATIVO. "
                    "Tente novamente."
                )
            )

    # ========================================================
    # 6. EVITA DUPLICIDADE
    #
    # Para ROTATIVO R2 este SELECT ocorre após o application
    # lock. Portanto, se outra requisição acabou de criar a R2,
    # ela será recuperada aqui com criada=False.
    # ========================================================

    cursor.execute(
        """
        SELECT
            ID_Rodada,
            NumeroRodada,
            Status,
            DataHoraInicio

        FROM dbo.RodadasInventario

        WHERE
            ID_Inventario = ?
            AND NumeroRodada = ?
        """,
        (
            inventario.ID_Inventario,
            numero_proxima
        )
    )

    existente = cursor.fetchone()

    if existente:

        _finalizar_rodada_atual(
            cursor=cursor,
            id_inventario=(
                inventario.ID_Inventario
            ),
            id_rodada=(
                rodada_atual.ID_Rodada
            )
        )

        return {
            "criada":
                False,

            "id_rodada":
                existente.ID_Rodada,

            "numero_rodada":
                existente.NumeroRodada,

            "status":
                existente.Status,

            "data_hora_inicio":
                existente.DataHoraInicio,

            "tipo_rodada":
                tipo_proxima,

            "rodada_origem":
                numero_atual,

            "mensagem":
                "A próxima rodada já existe."
        }

    # ========================================================
    # 7. DEFINE CANDIDATOS
    # ========================================================

    candidatos = []

    origem_candidatos = None

    pode_encaminhar_gestor = False

    # ========================================================
    # R2 ROTATIVO
    #
    # A R2 rotativa recebe somente as divergências da R1 pela
    # chave Localização + Código + Lote. O fluxo OFICIAL abaixo
    # permanece independente.
    # ========================================================

    if (
        r2_rotativo
        and
        tipo_proxima == "DIVERGENCIAS"
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
    # R3 OFICIAL
    #
    # Primeira rodada de divergências após R1/R2.
    # ========================================================

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
    # DIVERGÊNCIAS R4+
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

        # ====================================================
        # FLUXO GERENCIAL
        # ====================================================

        if possui_decisoes_gestor:

            analise_gestor = (
                analisar_inventario_gestor(
                    cursor=cursor,
                    id_inventario=(
                        inventario.ID_Inventario
                    )
                )
            )

            resumo_gestor = (
                analise_gestor.get(
                    "resumo",
                    {}
                )
            )

            itens_sem_decisao = int(
                resumo_gestor.get(
                    "itens_sem_decisao",
                    0
                )
            )

            total_nova_recontagem = int(
                resumo_gestor.get(
                    "nova_recontagem",
                    0
                )
            )

            pode_finalizar = bool(
                analise_gestor.get(
                    "pode_finalizar_inventario",
                    False
                )
            )

            if itens_sem_decisao > 0:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Ainda existem "
                        f"{itens_sem_decisao} item(ns) "
                        "divergente(s) sem decisão do gestor."
                    )
                )

            if total_nova_recontagem == 0:

                if pode_finalizar:

                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Todas as divergências foram "
                            "tratadas pelo gestor. "
                            "O inventário está apto "
                            "para finalização."
                        )
                    )

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Nenhum item foi marcado como "
                        "NOVA_RECONTAGEM."
                    )
                )

            candidatos = (
                _buscar_candidatos_gestor(
                    cursor=cursor,
                    id_inventario=(
                        inventario.ID_Inventario
                    )
                )
            )

            if not candidatos:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "A análise gerencial indica itens "
                        "para nova recontagem, porém nenhum "
                        "registro NOVA_RECONTAGEM foi "
                        "localizado."
                    )
                )

            if (
                len(candidatos)
                != total_nova_recontagem
            ):

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Inconsistência entre a análise "
                        "gerencial e as decisões de "
                        "NOVA_RECONTAGEM."
                    )
                )

            origem_candidatos = (
                "DECISAO_GESTOR"
            )

        # ====================================================
        # FLUXO AUTOMÁTICO
        # ====================================================

        else:

            candidatos = (
                _buscar_candidatos_recontagem_anterior(
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
                "DIVERGENCIAS_RODADA_ANTERIOR"
            )

            # ================================================
            # GESTOR ANTECIPADO
            #
            # Apenas sinaliza.
            # Não altera o fluxo automaticamente.
            # ================================================

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
    #
    # Não é rodada física.
    # ========================================================

    elif tipo_proxima == "GESTOR":

        raise HTTPException(
            status_code=400,
            detail=(
                "A próxima etapa configurada é GESTOR. "
                "Não deve ser criada como rodada "
                "operacional. Utilize a análise gerencial."
            )
        )

    # ========================================================
    # RODADA COMPLETA
    # ========================================================

    elif tipo_proxima == "COMPLETA":

        candidatos = []

        origem_candidatos = (
            "ESCOPO_COMPLETO"
        )

    else:

        raise HTTPException(
            status_code=400,
            detail=(
                "Tipo de próxima rodada não suportado: "
                f"{tipo_proxima}"
            )
        )
    # ========================================================
    # 8. DIVERGÊNCIA SEM CANDIDATOS
    # ========================================================

    if (
        tipo_proxima == "DIVERGENCIAS"
        and
        not candidatos
    ):

        if r2_rotativo:

            return (
                _encerrar_inventario_rotativo_apos_r1_sem_recontagem(
                    cursor=cursor,
                    inventario=inventario,
                    rodada_atual=rodada_atual
                )
            )

        raise HTTPException(
            status_code=400,
            detail=(
                "Não existem itens pendentes "
                "para gerar uma nova rodada."
            )
        )

    # ========================================================
    # 9. FINALIZA RODADA ATUAL
    #
    # Só chegamos aqui depois de:
    # - validar sessões abertas;
    # - validar configuração;
    # - montar candidatos;
    # - confirmar que existe motivo para criar a próxima.
    #
    # Assim evitamos deixar a rodada atual FINALIZADA caso a
    # criação da próxima rodada seja rejeitada por alguma regra.
    # ========================================================

    rodada_anterior_finalizada = (
        _finalizar_rodada_atual(
            cursor=cursor,
            id_inventario=(
                inventario.ID_Inventario
            ),
            id_rodada=(
                rodada_atual.ID_Rodada
            )
        )
    )

    # ========================================================
    # 10. CRIA NOVA RODADA
    # ========================================================

    cursor.execute(
        """
        INSERT INTO dbo.RodadasInventario
        (
            ID_Inventario,
            NumeroRodada,
            Status,
            DataHoraInicio
        )

        OUTPUT
            INSERTED.ID_Rodada,
            INSERTED.NumeroRodada,
            INSERTED.Status,
            INSERTED.DataHoraInicio

        VALUES
        (
            ?,
            ?,
            'ABERTA',
            SYSDATETIME()
        )
        """,
        (
            inventario.ID_Inventario,
            numero_proxima
        )
    )

    nova = cursor.fetchone()

    # ========================================================
    # 11. GERA RodadaItens
    # ========================================================

    itens_gerados = 0

    if tipo_proxima == "DIVERGENCIAS":

        for item in candidatos:

            _inserir_rodada_item(
                cursor=cursor,
                id_inventario=(
                    inventario.ID_Inventario
                ),
                id_rodada=(
                    nova.ID_Rodada
                ),
                codigo=(
                    item["codigo"]
                ),
                lote=(
                    item["lote"]
                ),
                motivo=(
                    item["motivo"]
                )
            )

            itens_gerados += 1

    # ========================================================
    # 12. GERA LOCALIZAÇÕES DA RECONTAGEM
    #
    # Agora respeita configuração.
    # ========================================================

    localizacoes_geradas = 0
    localizacoes = []

    if (
        tipo_proxima == "DIVERGENCIAS"
        and
        recontagem_por_localizacao
    ):

        if r2_rotativo:

            localizacoes_rotativo = set()

            for item in candidatos:

                for localizacao in item.get(
                    "localizacoes",
                    []
                ):

                    localizacoes_rotativo.add(
                        _normalizar_localizacao(
                            localizacao
                        )
                    )

            localizacoes = sorted(
                localizacao
                for localizacao in localizacoes_rotativo
                if localizacao
            )

            for localizacao in localizacoes:

                _inserir_rodada_localizacao(
                    cursor=cursor,
                    id_inventario=(
                        inventario.ID_Inventario
                    ),
                    id_rodada=(
                        nova.ID_Rodada
                    ),
                    localizacao=localizacao
                )

            localizacoes_geradas = len(
                localizacoes
            )

        else:

            sincronizacao = (
                sincronizar_localizacoes_recontagem(
                    cursor=cursor,
                    id_inventario=(
                        inventario.ID_Inventario
                    ),
                    id_rodada=(
                        nova.ID_Rodada
                    )
                )
            )

            localizacoes_geradas = (
                sincronizacao[
                    "localizacoes_geradas"
                ]
            )

            localizacoes = (
                sincronizacao[
                    "localizacoes"
                ]
            )

        if (
            itens_gerados > 0
            and
            localizacoes_geradas == 0
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "Foram encontrados itens para "
                    "recontagem, porém nenhuma localização "
                    "foi encontrada no snapshot ou "
                    "no histórico de contagens."
                )
            )

    # ========================================================
    # 13. ATUALIZA RODADA ATUAL DO INVENTÁRIO
    # ========================================================

    cursor.execute(
        """
        UPDATE dbo.Inventarios

        SET
            RodadaAtual = ?

        WHERE
            ID_Inventario = ?
        """,
        (
            numero_proxima,
            inventario.ID_Inventario
        )
    )
    # ========================================================
    # 14. RETORNO
    #
    # Commit continua responsabilidade do router.
    # ========================================================

    return {
        "criada":
            True,

        "id_rodada":
            nova.ID_Rodada,

        "numero_rodada":
            nova.NumeroRodada,

        "status":
            nova.Status,

        "data_hora_inicio":
            nova.DataHoraInicio,

        "tipo_rodada":
            tipo_proxima,

        "rodada_origem":
            numero_atual,

        "rodada_anterior_finalizada":
            True,

        "origem_candidatos":
            origem_candidatos,

        "itens_gerados":
            itens_gerados,

        "localizacoes_geradas":
            localizacoes_geradas,

        "localizacoes":
            localizacoes,

        "candidatos":
            len(candidatos),

        "configuracao": {
            "rodadas_iniciais":
                rodadas_iniciais,

            "max_rodadas":
                max_rodadas,

            "recontagem_por_localizacao":
                recontagem_por_localizacao,

            "permitir_gestor_antecipado":
                permitir_gestor_antecipado,

            "limite_itens_gestor_antecipado":
                limite_gestor_antecipado
        },

        "pode_encaminhar_gestor":
            pode_encaminhar_gestor
    }


