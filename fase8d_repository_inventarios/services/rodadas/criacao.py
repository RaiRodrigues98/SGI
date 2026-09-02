"""
Criação/orquestração da próxima rodada.

Fase 7 da refatoração de services.rodadas_service.

Objetivo:
- transformar criar_proxima_rodada() em um orquestrador pequeno;
- separar validações, concorrência, candidatos e persistência;
- preservar integralmente o comportamento validado nas regressões.

IMPORTANTE:
- nenhuma regra de negócio foi redesenhada;
- SQL preserva a mesma ordem operacional;
- commit/rollback continuam fora deste módulo;
- sp_getapplock permanece restrito à criação R1 -> R2 ROTATIVO.
"""

from fastapi import HTTPException

from services.configuracoes_inventario import (
    obter_configuracao_inventario,
    obter_tipo_proxima_rodada_configurada,
)

from services.analise_gestor import (
    analisar_inventario_gestor,
)

from services.rodadas.itens import (
    _inserir_rodada_item,
)

from services.rodadas.localizacoes import (
    _inserir_rodada_localizacao,
    sincronizar_localizacoes_recontagem,
)

from services.rodadas.candidatos_rotativo import (
    _validar_divergencias_r1_rotativo_tratadas,
    _buscar_candidatos_r2_rotativo,
)

from services.rodadas.candidatos_oficial import (
    _buscar_candidatos_r3,
    _buscar_candidatos_recontagem_anterior,
)

from services.rodadas.gestor import (
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

from services.rodadas.repositories.rodada_repository import (
    buscar_proxima_rodada_existente,
    inserir_rodada_aberta,
)

from services.rodadas.repositories.sessao_repository import (
    contar_sessoes_abertas,
)

from services.rodadas.repositories.inventario_repository import (
    atualizar_rodada_atual,
)


def _normalizar_texto(valor):

    if valor is None:
        return ""

    return str(valor).strip()


def _normalizar_localizacao(valor):

    return (
        _normalizar_texto(valor)
        .upper()
    )


def _montar_contexto_basico(
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

    return {
        "numero_atual":
            numero_atual,

        "numero_proxima":
            numero_proxima,

        "tipo_inventario":
            tipo_inventario,

        "r2_rotativo":
            r2_rotativo,
    }


def _carregar_configuracao_criacao(
    cursor,
    inventario,
    numero_atual: int,
    numero_proxima: int
):

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

    if numero_proxima > max_rodadas:

        raise HTTPException(
            status_code=400,
            detail=(
                "O inventário atingiu o número máximo "
                f"de rodadas configurado ({max_rodadas})."
            )
        )

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

    return {
        "max_rodadas":
            max_rodadas,

        "rodadas_iniciais":
            rodadas_iniciais,

        "recontagem_por_localizacao":
            recontagem_por_localizacao,

        "permitir_gestor_antecipado":
            permitir_gestor_antecipado,

        "limite_gestor_antecipado":
            limite_gestor_antecipado,

        "tipo_proxima":
            tipo_proxima,
    }


def _validar_sem_sessoes_abertas(
    cursor,
    inventario,
    rodada_atual
):

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
                "Existem sessões abertas na rodada atual. "
                "Encerre todas antes de criar "
                "a próxima rodada."
            )
        )


def _serializar_criacao_r2_rotativo(
    cursor,
    inventario,
    numero_proxima: int,
    r2_rotativo: bool
):

    if not r2_rotativo:
        return

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


def _buscar_proxima_rodada_existente(
    cursor,
    id_inventario: int,
    numero_proxima: int
):

    return buscar_proxima_rodada_existente(
        cursor=cursor,
        id_inventario=id_inventario,
        numero_proxima=numero_proxima
    )


def _retornar_rodada_existente(
    cursor,
    inventario,
    rodada_atual,
    existente,
    tipo_proxima: str,
    numero_atual: int
):

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


def _selecionar_candidatos(
    cursor,
    inventario,
    rodada_atual,
    numero_proxima: int,
    tipo_proxima: str,
    rodadas_iniciais: int,
    r2_rotativo: bool,
    permitir_gestor_antecipado: bool,
    limite_gestor_antecipado: int
):

    candidatos = []

    origem_candidatos = None

    pode_encaminhar_gestor = False

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

    elif tipo_proxima == "GESTOR":

        raise HTTPException(
            status_code=400,
            detail=(
                "A próxima etapa configurada é GESTOR. "
                "Não deve ser criada como rodada "
                "operacional. Utilize a análise gerencial."
            )
        )

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

    return {
        "candidatos":
            candidatos,

        "origem_candidatos":
            origem_candidatos,

        "pode_encaminhar_gestor":
            pode_encaminhar_gestor,
    }


def _validar_candidatos_divergencia(
    cursor,
    inventario,
    rodada_atual,
    tipo_proxima: str,
    candidatos,
    r2_rotativo: bool
):

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

    return None


def _criar_registro_nova_rodada(
    cursor,
    id_inventario: int,
    numero_proxima: int
):

    return inserir_rodada_aberta(
        cursor=cursor,
        id_inventario=id_inventario,
        numero_rodada=numero_proxima
    )


def _gerar_itens_nova_rodada(
    cursor,
    inventario,
    nova,
    tipo_proxima: str,
    candidatos
):

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

    return itens_gerados


def _gerar_localizacoes_nova_rodada(
    cursor,
    inventario,
    nova,
    tipo_proxima: str,
    recontagem_por_localizacao: bool,
    r2_rotativo: bool,
    candidatos,
    itens_gerados: int
):

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

    return {
        "localizacoes_geradas":
            localizacoes_geradas,

        "localizacoes":
            localizacoes,
    }


def _atualizar_rodada_atual_inventario(
    cursor,
    id_inventario: int,
    numero_proxima: int
):

    atualizar_rodada_atual(
        cursor=cursor,
        id_inventario=id_inventario,
        numero_rodada=numero_proxima
    )


def _montar_retorno_criacao(
    nova,
    tipo_proxima: str,
    numero_atual: int,
    origem_candidatos,
    itens_gerados: int,
    localizacoes_geradas: int,
    localizacoes,
    candidatos,
    rodadas_iniciais: int,
    max_rodadas: int,
    recontagem_por_localizacao: bool,
    permitir_gestor_antecipado: bool,
    limite_gestor_antecipado: int,
    pode_encaminhar_gestor: bool
):

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


def criar_proxima_rodada(
    cursor,
    inventario,
    rodada_atual
):

    contexto = (
        _montar_contexto_basico(
            inventario=inventario,
            rodada_atual=rodada_atual
        )
    )

    numero_atual = contexto[
        "numero_atual"
    ]

    numero_proxima = contexto[
        "numero_proxima"
    ]

    tipo_inventario = contexto[
        "tipo_inventario"
    ]

    r2_rotativo = contexto[
        "r2_rotativo"
    ]

    if (
        tipo_inventario == "ROTATIVO"
        and
        numero_atual == 2
    ):

        return (
            _encerrar_inventario_rotativo_apos_r2(
                cursor=cursor,
                inventario=inventario,
                rodada_atual=rodada_atual
            )
        )

    configuracao = (
        _carregar_configuracao_criacao(
            cursor=cursor,
            inventario=inventario,
            numero_atual=numero_atual,
            numero_proxima=numero_proxima
        )
    )

    tipo_proxima = configuracao[
        "tipo_proxima"
    ]

    _validar_sem_sessoes_abertas(
        cursor=cursor,
        inventario=inventario,
        rodada_atual=rodada_atual
    )

    _serializar_criacao_r2_rotativo(
        cursor=cursor,
        inventario=inventario,
        numero_proxima=numero_proxima,
        r2_rotativo=r2_rotativo
    )

    existente = (
        _buscar_proxima_rodada_existente(
            cursor=cursor,
            id_inventario=(
                inventario.ID_Inventario
            ),
            numero_proxima=numero_proxima
        )
    )

    if existente:

        return (
            _retornar_rodada_existente(
                cursor=cursor,
                inventario=inventario,
                rodada_atual=rodada_atual,
                existente=existente,
                tipo_proxima=tipo_proxima,
                numero_atual=numero_atual
            )
        )

    selecao = (
        _selecionar_candidatos(
            cursor=cursor,
            inventario=inventario,
            rodada_atual=rodada_atual,
            numero_proxima=numero_proxima,
            tipo_proxima=tipo_proxima,
            rodadas_iniciais=(
                configuracao[
                    "rodadas_iniciais"
                ]
            ),
            r2_rotativo=r2_rotativo,
            permitir_gestor_antecipado=(
                configuracao[
                    "permitir_gestor_antecipado"
                ]
            ),
            limite_gestor_antecipado=(
                configuracao[
                    "limite_gestor_antecipado"
                ]
            )
        )
    )

    candidatos = selecao[
        "candidatos"
    ]

    encerramento = (
        _validar_candidatos_divergencia(
            cursor=cursor,
            inventario=inventario,
            rodada_atual=rodada_atual,
            tipo_proxima=tipo_proxima,
            candidatos=candidatos,
            r2_rotativo=r2_rotativo
        )
    )

    if encerramento is not None:
        return encerramento

    _finalizar_rodada_atual(
        cursor=cursor,
        id_inventario=(
            inventario.ID_Inventario
        ),
        id_rodada=(
            rodada_atual.ID_Rodada
        )
    )

    nova = (
        _criar_registro_nova_rodada(
            cursor=cursor,
            id_inventario=(
                inventario.ID_Inventario
            ),
            numero_proxima=numero_proxima
        )
    )

    itens_gerados = (
        _gerar_itens_nova_rodada(
            cursor=cursor,
            inventario=inventario,
            nova=nova,
            tipo_proxima=tipo_proxima,
            candidatos=candidatos
        )
    )

    localizacoes = (
        _gerar_localizacoes_nova_rodada(
            cursor=cursor,
            inventario=inventario,
            nova=nova,
            tipo_proxima=tipo_proxima,
            recontagem_por_localizacao=(
                configuracao[
                    "recontagem_por_localizacao"
                ]
            ),
            r2_rotativo=r2_rotativo,
            candidatos=candidatos,
            itens_gerados=itens_gerados
        )
    )

    _atualizar_rodada_atual_inventario(
        cursor=cursor,
        id_inventario=(
            inventario.ID_Inventario
        ),
        numero_proxima=numero_proxima
    )

    return (
        _montar_retorno_criacao(
            nova=nova,
            tipo_proxima=tipo_proxima,
            numero_atual=numero_atual,
            origem_candidatos=(
                selecao[
                    "origem_candidatos"
                ]
            ),
            itens_gerados=itens_gerados,
            localizacoes_geradas=(
                localizacoes[
                    "localizacoes_geradas"
                ]
            ),
            localizacoes=(
                localizacoes[
                    "localizacoes"
                ]
            ),
            candidatos=candidatos,
            rodadas_iniciais=(
                configuracao[
                    "rodadas_iniciais"
                ]
            ),
            max_rodadas=(
                configuracao[
                    "max_rodadas"
                ]
            ),
            recontagem_por_localizacao=(
                configuracao[
                    "recontagem_por_localizacao"
                ]
            ),
            permitir_gestor_antecipado=(
                configuracao[
                    "permitir_gestor_antecipado"
                ]
            ),
            limite_gestor_antecipado=(
                configuracao[
                    "limite_gestor_antecipado"
                ]
            ),
            pode_encaminhar_gestor=(
                selecao[
                    "pode_encaminhar_gestor"
                ]
            )
        )
    )
