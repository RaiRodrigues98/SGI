"""
SGI - ESTÁGIO 10
REGRESSÃO E2E DO INVENTÁRIO OFICIAL

Objetivo
--------
Garantir que as alterações realizadas no fluxo ROTATIVO não tenham quebrado
o fluxo OFICIAL existente.

Cenário principal:
1. Cria inventário OFICIAL.
2. Adiciona uma localização real ao escopo.
3. Gera snapshot.
4. R1 COMPLETA:
   - conta todos os itens;
   - força exatamente uma divergência controlada.
5. Gera R2 e valida que continua COMPLETA.
6. R2 COMPLETA:
   - repete a mesma divergência controlada.
7. Gera R3 e valida que é DIVERGENCIAS.
8. Confirma que a R3 contém apenas item(ns) divergente(s) de R1/R2.
9. Executa a recontagem correta.
10. Valida que a R3 ficou conciliada.
11. Valida análise gerencial sem pendências.
12. Finaliza o inventário.
13. Consulta resultado final.
14. Garante que o resultado ficou FINALIZADO e conciliado.

Uso no PowerShell
-----------------
$env:SGI_BASE_URL='http://127.0.0.1:8000'
$env:SGI_LOGIN='SEU_LOGIN'
$env:SGI_PASSWORD='SUA_SENHA'

# opcionais:
$env:SGI_CLIENTE_ID='53'
$env:SGI_CLIENTE='endress'
$env:SGI_ARMAZEM='ML007'
$env:SGI_LOCALIZACAO='01PLAQUETA'

python tests_e2e\teste_oficial_estagio10.py

IMPORTANTE
----------
- A suíte usa somente a API pública do SGI.
- Não apaga dados.
- Cria inventários E2E-OF10-*.
- Requer que ClienteId/Armazém/Localização informados possuam estoque.
- O cliente precisa possuir configuração OFICIAL válida.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any


# ============================================================
# CONFIGURAÇÃO
# ============================================================

BASE = os.getenv(
    "SGI_BASE_URL",
    "http://127.0.0.1:8000"
).rstrip("/")

LOGIN = os.getenv(
    "SGI_LOGIN",
    ""
)

PASSWORD = os.getenv(
    "SGI_PASSWORD",
    ""
)

CLIENTE_ID = int(
    os.getenv(
        "SGI_CLIENTE_ID",
        "53"
    )
)

CLIENTE = os.getenv(
    "SGI_CLIENTE",
    "endress"
)

ARMAZEM = os.getenv(
    "SGI_ARMAZEM",
    "ML007"
)

LOCALIZACAO = os.getenv(
    "SGI_LOCALIZACAO",
    "01PLAQUETA"
).strip().upper()

TIMEOUT = float(
    os.getenv(
        "SGI_TIMEOUT",
        "30"
    )
)


# ============================================================
# HTTP
# ============================================================

class ApiError(RuntimeError):

    def __init__(
        self,
        status: int,
        data: Any,
        method: str,
        path: str
    ):
        self.status = status
        self.data = data
        self.method = method
        self.path = path

        super().__init__(
            f"HTTP {status} {method} {path}: {data}"
        )


class API:

    def __init__(self):
        self.token = ""

    def request(
        self,
        method: str,
        path: str,
        body: Any = None,
        expected=(200, 201)
    ) -> Any:

        headers = {
            "Accept":
                "application/json"
        }

        if self.token:
            headers[
                "Authorization"
            ] = (
                f"Bearer {self.token}"
            )

        raw = None

        if body is not None:

            raw = json.dumps(
                body
            ).encode(
                "utf-8"
            )

            headers[
                "Content-Type"
            ] = (
                "application/json"
            )

        req = urllib.request.Request(
            BASE + path,
            data=raw,
            headers=headers,
            method=method
        )

        try:

            with urllib.request.urlopen(
                req,
                timeout=TIMEOUT
            ) as response:

                raw_body = (
                    response
                    .read()
                    .decode(
                        "utf-8"
                    )
                )

                data = (
                    json.loads(
                        raw_body
                    )
                    if raw_body
                    else None
                )

                if (
                    response.status
                    not in expected
                ):

                    raise ApiError(
                        response.status,
                        data,
                        method,
                        path
                    )

                return data

        except urllib.error.HTTPError as erro:

            try:
                data = json.loads(
                    erro
                    .read()
                    .decode(
                        "utf-8"
                    )
                    or
                    "null"
                )
            except Exception:
                data = str(
                    erro
                )

            if erro.code in expected:
                return data

            raise ApiError(
                erro.code,
                data,
                method,
                path
            )

    def login(
        self
    ):

        if (
            not LOGIN
            or
            not PASSWORD
        ):
            raise RuntimeError(
                "Defina SGI_LOGIN e SGI_PASSWORD "
                "antes de executar."
            )

        retorno = self.request(
            "POST",
            "/auth/login",
            {
                "login":
                    LOGIN,

                "senha":
                    PASSWORD
            }
        )

        self.token = (
            retorno[
                "access_token"
            ]
        )


api = API()


# ============================================================
# RELATÓRIO
# ============================================================

@dataclass
class Report:

    passed: list[str] = field(
        default_factory=list
    )

    failed: list[str] = field(
        default_factory=list
    )

    def ok(
        self,
        nome: str
    ):

        self.passed.append(
            nome
        )

        print(
            f"[PASS] {nome}"
        )

    def fail(
        self,
        nome: str,
        erro: Exception | str
    ):

        mensagem = (
            f"{nome}: {erro}"
        )

        self.failed.append(
            mensagem
        )

        print(
            f"[FAIL] {mensagem}"
        )


R = Report()


# ============================================================
# ASSERTS / UTILITÁRIOS
# ============================================================

def assert_true(
    valor,
    mensagem: str
):

    if not valor:
        raise AssertionError(
            mensagem
        )


def normalizar(
    valor
) -> str:

    if valor is None:
        return ""

    return str(
        valor
    ).strip()


def normalizar_upper(
    valor
) -> str:

    return (
        normalizar(
            valor
        )
        .upper()
    )


def quantidade_estoque(
    item: dict
) -> float:

    for chave in (
        "qtd_estoque",
        "quantidade_estoque",
        "saldo_inventario",
    ):

        if (
            chave in item
            and
            item[chave]
            is not None
        ):

            return float(
                item[chave]
            )

    raise AssertionError(
        "Campo de quantidade de estoque "
        f"não encontrado: {item}"
    )


def chave_item(
    item: dict
) -> tuple[str, str]:

    return (
        normalizar(
            item.get(
                "codigo"
            )
        ),
        normalizar(
            item.get(
                "lote"
            )
        ),
    )


def codigo_unico() -> str:

    # Mantemos abaixo de 30 caracteres por compatibilidade
    # com bases antigas do SGI.
    sufixo = str(
        int(
            time.time()
            *
            1000
        )
    )[-10:]

    return (
        f"E2E-OF10-{sufixo}"
    )[:30]


def run(
    nome: str,
    funcao
):

    try:

        funcao()

        R.ok(
            nome
        )

    except Exception as erro:

        R.fail(
            nome,
            erro
        )

        raise


# ============================================================
# API - FLUXO OFICIAL
# ============================================================

def criar_inventario() -> tuple[int, int, dict]:

    retorno = api.request(
        "POST",
        "/inventarios",
        {
            "codigo_inventario":
                codigo_unico(),

            "tipo":
                "OFICIAL",

            "cliente_id":
                CLIENTE_ID,

            "cliente":
                CLIENTE,

            "descricao":
                (
                    "E2E Estágio 10 - "
                    "regressão inventário OFICIAL"
                ),

            "armazem":
                ARMAZEM,
        }
    )

    return (
        int(
            retorno[
                "id_inventario"
            ]
        ),
        int(
            retorno[
                "id_rodada"
            ]
        ),
        retorno,
    )


def adicionar_escopo(
    id_inventario: int
):

    return api.request(
        "POST",
        (
            f"/inventarios/"
            f"{id_inventario}"
            f"/escopo/localizacoes"
        ),
        {
            "localizacoes":
                [
                    LOCALIZACAO
                ]
        }
    )


def gerar_snapshot(
    id_inventario: int
):

    return api.request(
        "POST",
        (
            f"/inventarios/"
            f"{id_inventario}"
            f"/snapshot"
        ),
        {}
    )


def analisar_rodada(
    id_inventario: int,
    id_rodada: int
):

    return api.request(
        "GET",
        (
            f"/inventarios/"
            f"{id_inventario}"
            f"/rodadas/"
            f"{id_rodada}"
            f"/analise"
        )
    )


def analisar_recontagem(
    id_inventario: int,
    id_rodada: int
):

    return api.request(
        "GET",
        (
            f"/inventarios/"
            f"{id_inventario}"
            f"/rodadas/"
            f"{id_rodada}"
            f"/analise-recontagem"
        )
    )


def analisar_gestor(
    id_inventario: int
):

    return api.request(
        "GET",
        (
            f"/inventarios/"
            f"{id_inventario}"
            f"/analise-gestor"
        )
    )


def iniciar_localizacao(
    id_inventario: int,
    id_rodada: int,
    localizacao: str = LOCALIZACAO
):

    return api.request(
        "POST",
        "/localizacoes/iniciar",
        {
            "id_inventario":
                id_inventario,

            "id_rodada":
                id_rodada,

            "localizacao":
                localizacao,
        }
    )


def contar(
    id_sessao: int,
    item: dict,
    quantidade: float
):

    return api.request(
        "POST",
        "/contagens",
        {
            "id_sessao":
                id_sessao,

            "codigo":
                normalizar(
                    item[
                        "codigo"
                    ]
                ),

            "lote":
                normalizar(
                    item.get(
                        "lote"
                    )
                ),

            "quantidade":
                quantidade,
        }
    )


def encerrar_localizacao(
    id_sessao: int,
    localizacao_vazia: bool = False
):

    return api.request(
        "POST",
        "/localizacoes/encerrar",
        {
            "id_sessao":
                id_sessao,

            "localizacao_vazia":
                localizacao_vazia,
        }
    )


def proxima_rodada(
    id_inventario: int
):

    return api.request(
        "POST",
        (
            f"/inventarios/"
            f"{id_inventario}"
            f"/rodadas/proxima"
        )
    )


def preview_proxima_rodada(
    id_inventario: int
):

    return api.request(
        "GET",
        (
            f"/inventarios/"
            f"{id_inventario}"
            f"/rodadas/proxima-preview"
        )
    )


def finalizar(
    id_inventario: int
):

    return api.request(
        "POST",
        (
            f"/inventarios/"
            f"{id_inventario}"
            f"/finalizar"
        ),
        {}
    )


def resultado_final(
    id_inventario: int
):

    return api.request(
        "GET",
        (
            f"/inventarios/"
            f"{id_inventario}"
            f"/resultado-final"
        )
    )


# ============================================================
# CONTAGEM DE UMA RODADA COMPLETA
# ============================================================

def executar_rodada_completa(
    id_inventario: int,
    id_rodada: int,
    itens: list[dict],
    item_divergente: tuple[str, str] | None = None
):

    sessao = iniciar_localizacao(
        id_inventario,
        id_rodada
    )

    id_sessao = int(
        sessao[
            "id_sessao"
        ]
    )

    for item in itens:

        qtd = quantidade_estoque(
            item
        )

        if qtd <= 0:
            continue

        if (
            item_divergente is not None
            and
            chave_item(
                item
            )
            ==
            item_divergente
        ):

            # A API exige quantidade > 0.
            # O item escolhido para divergência sempre terá estoque > 1.
            qtd_contagem = (
                qtd
                -
                1
            )

        else:

            qtd_contagem = qtd

        contar(
            id_sessao,
            item,
            qtd_contagem
        )

    encerrar_localizacao(
        id_sessao
    )

    return id_sessao


# ============================================================
# CENÁRIO PRINCIPAL
# ============================================================

def teste_regressao_oficial_completa():

    print()
    print(
        "=" * 72
    )
    print(
        "1. CRIANDO INVENTÁRIO OFICIAL"
    )
    print(
        "=" * 72
    )

    (
        id_inventario,
        id_r1,
        criacao,
    ) = criar_inventario()

    print(
        "Inventário:",
        id_inventario
    )

    print(
        "Código:",
        criacao.get(
            "codigo_inventario"
        )
    )

    assert_true(
        normalizar_upper(
            criacao.get(
                "tipo"
            )
        )
        ==
        "OFICIAL",
        (
            "Inventário não foi criado "
            f"como OFICIAL: {criacao}"
        )
    )

    assert_true(
        int(
            criacao.get(
                "numero_rodada",
                0
            )
        )
        ==
        1,
        (
            "Inventário não iniciou "
            f"na R1: {criacao}"
        )
    )

    tipo_r1 = normalizar_upper(
        criacao.get(
            "tipo_rodada"
        )
    )

    assert_true(
        tipo_r1
        ==
        "COMPLETA",
        (
            "R1 do OFICIAL deveria ser COMPLETA. "
            f"Recebido: {tipo_r1!r}. "
            f"Retorno: {criacao}"
        )
    )

    print()
    print(
        "=" * 72
    )
    print(
        "2. ESCOPO + SNAPSHOT"
    )
    print(
        "=" * 72
    )

    retorno_escopo = adicionar_escopo(
        id_inventario
    )

    print(
        "Escopo:",
        retorno_escopo
    )

    retorno_snapshot = gerar_snapshot(
        id_inventario
    )

    registros_snapshot = int(
        retorno_snapshot.get(
            "registros_snapshot",
            0
        )
        or
        0
    )

    print(
        "Registros snapshot:",
        registros_snapshot
    )

    assert_true(
        registros_snapshot > 0,
        (
            "Snapshot ficou vazio. "
            "Confira ClienteId, armazém "
            "e localização do teste."
        )
    )

    # A análise oficial da R1, antes de contar, expõe
    # todo o universo do snapshot por Código + Lote.
    analise_r1_inicial = analisar_rodada(
        id_inventario,
        id_r1
    )

    assert_true(
        analise_r1_inicial.get(
            "regra_conciliacao"
        )
        ==
        "CODIGO_LOTE",
        (
            "Regra do OFICIAL foi alterada. "
            f"Retorno: {analise_r1_inicial}"
        )
    )

    assert_true(
        analise_r1_inicial.get(
            "considera_localizacao"
        )
        is False,
        (
            "OFICIAL passou a considerar localização "
            "na conciliação."
        )
    )

    itens_base = (
        analise_r1_inicial.get(
            "itens",
            []
        )
        or
        []
    )

    assert_true(
        len(
            itens_base
        )
        >
        0,
        (
            "Nenhum item disponível "
            "na análise OFICIAL da R1."
        )
    )

    # Precisamos de um item com saldo > 1 para criar uma
    # divergência sem enviar quantidade zero.
    alvo = next(
        (
            item
            for item in itens_base
            if quantidade_estoque(
                item
            )
            >
            1
        ),
        None
    )

    assert_true(
        alvo is not None,
        (
            "Não existe item com QtdEstoque > 1 "
            "na localização informada. "
            "Use outra SGI_LOCALIZACAO para o E2E."
        )
    )

    chave_alvo = chave_item(
        alvo
    )

    print(
        "Item usado para divergência:",
        chave_alvo,
        "| estoque:",
        quantidade_estoque(
            alvo
        )
    )

    # ========================================================
    # R1
    # ========================================================

    print()
    print(
        "=" * 72
    )
    print(
        "3. R1 COMPLETA - GERANDO 1 DIVERGÊNCIA"
    )
    print(
        "=" * 72
    )

    executar_rodada_completa(
        id_inventario=id_inventario,
        id_rodada=id_r1,
        itens=itens_base,
        item_divergente=chave_alvo
    )

    analise_r1 = analisar_rodada(
        id_inventario,
        id_r1
    )

    resumo_r1 = (
        analise_r1.get(
            "resumo",
            {}
        )
        or
        {}
    )

    divergencias_r1 = [
        item
        for item in (
            analise_r1.get(
                "itens",
                []
            )
            or
            []
        )
        if normalizar_upper(
            item.get(
                "status"
            )
        )
        !=
        "OK"
    ]

    print(
        "Resumo R1:",
        resumo_r1
    )

    print(
        "Divergências R1:",
        len(
            divergencias_r1
        )
    )

    assert_true(
        len(
            divergencias_r1
        )
        ==
        1,
        (
            "R1 deveria possuir exatamente "
            "1 divergência controlada. "
            f"Itens divergentes: {divergencias_r1}"
        )
    )

    assert_true(
        chave_item(
            divergencias_r1[
                0
            ]
        )
        ==
        chave_alvo,
        (
            "A divergência da R1 não corresponde "
            "ao item controlado."
        )
    )

    # ========================================================
    # R2
    # ========================================================

    print()
    print(
        "=" * 72
    )
    print(
        "4. GERANDO R2"
    )
    print(
        "=" * 72
    )

    preview_r2 = preview_proxima_rodada(
        id_inventario
    )

    print(
        "Preview R2:",
        preview_r2
    )

    retorno_r2 = proxima_rodada(
        id_inventario
    )

    dados_r2 = (
        retorno_r2.get(
            "proxima_rodada",
            {}
        )
        or
        {}
    )

    id_r2 = int(
        dados_r2[
            "id_rodada"
        ]
    )

    assert_true(
        int(
            dados_r2.get(
                "numero_rodada",
                0
            )
        )
        ==
        2,
        (
            "Próxima rodada deveria ser R2. "
            f"Retorno: {retorno_r2}"
        )
    )

    assert_true(
        normalizar_upper(
            dados_r2.get(
                "tipo_rodada"
            )
        )
        ==
        "COMPLETA",
        (
            "R2 do OFICIAL deveria continuar COMPLETA. "
            f"Retorno: {retorno_r2}"
        )
    )

    # O universo da R2 completa é o mesmo snapshot.
    analise_r2_inicial = analisar_rodada(
        id_inventario,
        id_r2
    )

    itens_r2 = (
        analise_r2_inicial.get(
            "itens",
            []
        )
        or
        []
    )

    assert_true(
        len(
            itens_r2
        )
        ==
        len(
            itens_base
        ),
        (
            "R2 COMPLETA não trouxe o mesmo universo "
            "Código + Lote da R1."
        )
    )

    print()
    print(
        "=" * 72
    )
    print(
        "5. R2 COMPLETA - REPETINDO A MESMA DIVERGÊNCIA"
    )
    print(
        "=" * 72
    )

    executar_rodada_completa(
        id_inventario=id_inventario,
        id_rodada=id_r2,
        itens=itens_r2,
        item_divergente=chave_alvo
    )

    analise_r2 = analisar_rodada(
        id_inventario,
        id_r2
    )

    divergencias_r2 = [
        item
        for item in (
            analise_r2.get(
                "itens",
                []
            )
            or
            []
        )
        if normalizar_upper(
            item.get(
                "status"
            )
        )
        !=
        "OK"
    ]

    print(
        "Resumo R2:",
        analise_r2.get(
            "resumo"
        )
    )

    assert_true(
        len(
            divergencias_r2
        )
        ==
        1,
        (
            "R2 deveria possuir exatamente "
            "1 divergência controlada. "
            f"Divergências: {divergencias_r2}"
        )
    )

    assert_true(
        chave_item(
            divergencias_r2[
                0
            ]
        )
        ==
        chave_alvo,
        (
            "A divergência da R2 não corresponde "
            "à divergência da R1."
        )
    )

    # ========================================================
    # R3 - DIVERGÊNCIAS R1 x R2
    # ========================================================

    print()
    print(
        "=" * 72
    )
    print(
        "6. GERANDO R3 DE DIVERGÊNCIAS"
    )
    print(
        "=" * 72
    )

    preview_r3 = preview_proxima_rodada(
        id_inventario
    )

    print(
        "Preview R3:",
        preview_r3
    )

    tipo_preview_r3 = normalizar_upper(
        preview_r3.get(
            "tipo_rodada"
        )
        or
        (
            preview_r3.get(
                "proxima_rodada",
                {}
            )
            or
            {}
        ).get(
            "tipo_rodada"
        )
    )

    if tipo_preview_r3:

        assert_true(
            tipo_preview_r3
            ==
            "DIVERGENCIAS",
            (
                "Preview da R3 deveria indicar "
                "DIVERGENCIAS. "
                f"Retorno: {preview_r3}"
            )
        )

    retorno_r3 = proxima_rodada(
        id_inventario
    )

    dados_r3 = (
        retorno_r3.get(
            "proxima_rodada",
            {}
        )
        or
        {}
    )

    id_r3 = int(
        dados_r3[
            "id_rodada"
        ]
    )

    print(
        "R3:",
        dados_r3
    )

    assert_true(
        int(
            dados_r3.get(
                "numero_rodada",
                0
            )
        )
        ==
        3,
        (
            "Esperada R3. "
            f"Retorno: {retorno_r3}"
        )
    )

    assert_true(
        normalizar_upper(
            dados_r3.get(
                "tipo_rodada"
            )
        )
        ==
        "DIVERGENCIAS",
        (
            "R3 do OFICIAL deveria ser DIVERGENCIAS. "
            f"Retorno: {retorno_r3}"
        )
    )

    assert_true(
        int(
            dados_r3.get(
                "itens_gerados",
                0
            )
            or
            0
        )
        ==
        1,
        (
            "R3 deveria receber somente a divergência "
            "persistente entre R1 e R2. "
            f"Retorno: {dados_r3}"
        )
    )

    origem_candidatos = normalizar_upper(
        dados_r3.get(
            "origem_candidatos"
        )
    )

    assert_true(
        origem_candidatos
        ==
        "DIVERGENCIAS_R1_R2",
        (
            "Origem dos candidatos da R3 foi alterada. "
            f"Recebido: {origem_candidatos!r}"
        )
    )

    # ========================================================
    # RECONTAGEM R3
    # ========================================================

    print()
    print(
        "=" * 72
    )
    print(
        "7. R3 - RECONTANDO CORRETAMENTE"
    )
    print(
        "=" * 72
    )

    analise_r3_inicial = analisar_recontagem(
        id_inventario,
        id_r3
    )

    assert_true(
        analise_r3_inicial.get(
            "tipo_analise"
        )
        ==
        "RECONTAGEM_OFICIAL",
        (
            "Endpoint da R3 deixou de usar "
            "RECONTAGEM_OFICIAL."
        )
    )

    assert_true(
        analise_r3_inicial.get(
            "regra_conciliacao"
        )
        ==
        "CODIGO_LOTE",
        (
            "Recontagem OFICIAL deixou de conciliar "
            "por Código + Lote."
        )
    )

    itens_r3 = (
        analise_r3_inicial.get(
            "itens",
            []
        )
        or
        []
    )

    candidatos_originais = [
        item
        for item in itens_r3
        if bool(
            item.get(
                "item_original_recontagem"
            )
        )
    ]

    assert_true(
        len(
            candidatos_originais
        )
        ==
        1,
        (
            "A R3 deveria possuir exatamente "
            "1 candidato original."
        )
    )

    item_r3 = candidatos_originais[
        0
    ]

    assert_true(
        chave_item(
            item_r3
        )
        ==
        chave_alvo,
        (
            "R3 recebeu item diferente "
            "da divergência R1/R2."
        )
    )

    localizacoes_r3 = (
        analise_r3_inicial.get(
            "localizacoes_rodada",
            []
        )
        or
        []
    )

    localizacoes_pendentes = [
        normalizar_upper(
            item.get(
                "localizacao"
            )
        )
        for item in localizacoes_r3
        if normalizar_upper(
            item.get(
                "status"
            )
        )
        !=
        "CONCLUIDA"
        and normalizar_upper(
            item.get(
                "localizacao"
            )
        )
    ]

    # Em configuração de recontagem por localização,
    # a própria análise informa as posições da R3.
    # Como o E2E usa uma localização de escopo, normalmente será uma.
    if not localizacoes_pendentes:
        localizacoes_pendentes = [
            LOCALIZACAO
        ]

    print(
        "Localizações R3:",
        localizacoes_pendentes
    )

    for indice, localizacao in enumerate(
        localizacoes_pendentes
    ):

        sessao_r3 = iniciar_localizacao(
            id_inventario,
            id_r3,
            localizacao
        )

        id_sessao_r3 = int(
            sessao_r3[
                "id_sessao"
            ]
        )

        # Como a conciliação OFICIAL ignora localização,
        # a quantidade correta deve ser registrada uma única vez.
        if indice == 0:

            contar(
                id_sessao_r3,
                item_r3,
                quantidade_estoque(
                    item_r3
                )
            )

            encerrar_localizacao(
                id_sessao_r3,
                localizacao_vazia=False
            )

        else:

            # Caso a configuração gere mais de uma localização
            # para o mesmo item, encerramos as demais como vazias
            # para não duplicar a quantidade consolidada.
            encerrar_localizacao(
                id_sessao_r3,
                localizacao_vazia=True
            )

    analise_r3_final = analisar_recontagem(
        id_inventario,
        id_r3
    )

    print(
        "Resumo R3:",
        analise_r3_final.get(
            "resumo"
        )
    )

    print(
        "Status R3:",
        analise_r3_final.get(
            "status_recontagem"
        )
    )

    assert_true(
        analise_r3_final.get(
            "rodada_operacional_concluida"
        )
        is True,
        (
            "R3 física não foi considerada concluída."
        )
    )

    assert_true(
        normalizar_upper(
            analise_r3_final.get(
                "status_recontagem"
            )
        )
        ==
        "CONCILIADA",
        (
            "R3 deveria ficar CONCILIADA. "
            f"Retorno: {analise_r3_final}"
        )
    )

    resumo_r3 = (
        analise_r3_final.get(
            "resumo",
            {}
        )
        or
        {}
    )

    assert_true(
        int(
            resumo_r3.get(
                "pendentes_proxima_rodada",
                0
            )
            or
            0
        )
        ==
        0,
        (
            "Ainda existem pendências após "
            "a recontagem correta da R3."
        )
    )

    assert_true(
        analise_r3_final.get(
            "pode_finalizar_sem_divergencia"
        )
        is True,
        (
            "R3 conciliada deveria permitir "
            "finalização sem divergência."
        )
    )

    # ========================================================
    # ANÁLISE GESTOR
    # ========================================================

    print()
    print(
        "=" * 72
    )
    print(
        "8. VALIDANDO ANÁLISE GERENCIAL"
    )
    print(
        "=" * 72
    )

    gestor = analisar_gestor(
        id_inventario
    )

    resumo_gestor = (
        gestor.get(
            "resumo",
            {}
        )
        or
        {}
    )

    print(
        "Resumo gestor:",
        resumo_gestor
    )

    print(
        "Pode finalizar:",
        gestor.get(
            "pode_finalizar_inventario"
        )
    )

    assert_true(
        int(
            resumo_gestor.get(
                "itens_sem_decisao",
                0
            )
            or
            0
        )
        ==
        0,
        (
            "Inventário conciliado ficou com "
            "item sem decisão gerencial."
        )
    )

    assert_true(
        int(
            resumo_gestor.get(
                "nova_recontagem",
                0
            )
            or
            0
        )
        ==
        0,
        (
            "Inventário conciliado ficou com "
            "NOVA_RECONTAGEM indevida."
        )
    )

    assert_true(
        gestor.get(
            "pode_finalizar_inventario"
        )
        is True,
        (
            "Análise gerencial bloqueou "
            "inventário OFICIAL conciliado."
        )
    )

    # ========================================================
    # FINALIZAÇÃO
    # ========================================================

    print()
    print(
        "=" * 72
    )
    print(
        "9. FINALIZANDO INVENTÁRIO OFICIAL"
    )
    print(
        "=" * 72
    )

    retorno_finalizacao = finalizar(
        id_inventario
    )

    print(
        "Finalização:",
        retorno_finalizacao
    )

    assert_true(
        normalizar_upper(
            retorno_finalizacao.get(
                "status"
            )
        )
        ==
        "FINALIZADO",
        (
            "Finalização OFICIAL não retornou FINALIZADO."
        )
    )

    resumo_finalizacao = (
        retorno_finalizacao.get(
            "resumo_final",
            {}
        )
        or
        {}
    )

    assert_true(
        int(
            resumo_finalizacao.get(
                "divergencias",
                0
            )
            or
            0
        )
        ==
        0,
        (
            "Resultado final possui divergência "
            "mesmo após R3 conciliada."
        )
    )

    # ========================================================
    # RESULTADO FINAL
    # ========================================================

    print()
    print(
        "=" * 72
    )
    print(
        "10. VALIDANDO RESULTADO FINAL"
    )
    print(
        "=" * 72
    )

    resultado = resultado_final(
        id_inventario
    )

    print(
        "Status resultado final:",
        resultado.get(
            "status_inventario"
        )
        or
        resultado.get(
            "status"
        )
    )

    itens_resultado = (
        resultado.get(
            "itens",
            []
        )
        or
        []
    )

    assert_true(
        len(
            itens_resultado
        )
        >
        0,
        (
            "Resultado final não possui itens."
        )
    )

    status_inventario_final = normalizar_upper(
        resultado.get(
            "status_inventario"
        )
        or
        resultado.get(
            "status"
        )
    )

    assert_true(
        status_inventario_final
        ==
        "FINALIZADO",
        (
            "Consulta de resultado final não confirma "
            f"status FINALIZADO: {resultado}"
        )
    )

    item_alvo_final = next(
        (
            item
            for item in itens_resultado
            if chave_item(
                item
            )
            ==
            chave_alvo
        ),
        None
    )

    assert_true(
        item_alvo_final is not None,
        (
            "Item usado na divergência não apareceu "
            "no resultado final."
        )
    )

    assert_true(
        normalizar_upper(
            item_alvo_final.get(
                "status_final"
            )
        )
        ==
        "OK",
        (
            "Item divergente R1/R2 deveria terminar OK "
            "após conciliação da R3. "
            f"Item final: {item_alvo_final}"
        )
    )

    print()
    print(
        "=" * 72
    )
    print(
        "REGRESSÃO OFICIAL CONCLUÍDA COM SUCESSO"
    )
    print(
        "=" * 72
    )

    print(
        "Inventário testado:",
        id_inventario
    )

    print(
        "R1:",
        id_r1
    )

    print(
        "R2:",
        id_r2
    )

    print(
        "R3:",
        id_r3
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "=" * 72
    )

    print(
        "SGI - ESTÁGIO 10 | REGRESSÃO DO INVENTÁRIO OFICIAL"
    )

    print(
        (
            f"API: {BASE} | "
            f"Cliente: {CLIENTE_ID} | "
            f"Armazém: {ARMAZEM} | "
            f"Localização: {LOCALIZACAO}"
        )
    )

    print(
        "=" * 72
    )

    api.login()

    R.ok(
        "Autenticação"
    )

    try:

        run(
            (
                "Fluxo OFICIAL "
                "R1 + R2 + R3 + finalização"
            ),
            teste_regressao_oficial_completa
        )

    except Exception:

        pass

    print()
    print(
        "=" * 72
    )

    print(
        f"PASS: {len(R.passed)} | "
        f"FAIL: {len(R.failed)}"
    )

    if R.failed:

        print(
            "RESULTADO: REPROVADO"
        )

        for falha in R.failed:

            print(
                " -",
                falha
            )

        sys.exit(
            1
        )

    print(
        "RESULTADO: APROVADO"
    )

    print(
        "=" * 72
    )


if __name__ == "__main__":
    main()
