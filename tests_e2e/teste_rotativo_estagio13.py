"""
SGI - ESTÁGIO 12
COEXISTÊNCIA E ISOLAMENTO ENTRE INVENTÁRIO ROTATIVO E OFICIAL
==============================================================

Objetivo
--------
Provar via API pública que inventários ROTATIVO e OFICIAL podem coexistir
para o mesmo ClienteId / Armazém / Localização sem compartilhar estado
operacional, decisões, rodadas ou resultado final.

Cenário
-------
1. Autentica.
2. Cria simultaneamente:
   - 1 inventário ROTATIVO
   - 1 inventário OFICIAL
3. Adiciona o mesmo escopo aos dois.
4. Gera snapshots independentes.
5. Cria divergência no ROTATIVO e trata com JUSTIFICAR_DIVERGENCIA.
6. Confirma que o ROTATIVO finaliza na R1 e o OFICIAL continua ABERTO.
7. No OFICIAL:
   - R1 COMPLETA com 1 divergência;
   - R2 COMPLETA com a mesma divergência;
   - R3 DIVERGENCIAS;
   - R3 corrige a divergência;
   - análise do gestor permite finalizar;
   - finaliza OFICIAL.
8. Compara os resultados finais e garante independência lógica.

Uso
---
PowerShell:

    python tests_e2e\\teste_estagio12_coexistencia.py

Variáveis de ambiente
---------------------
SGI_BASE_URL
SGI_LOGIN
SGI_PASSWORD
SGI_CLIENTE_ID
SGI_CLIENTE
SGI_ARMAZEM
SGI_LOCALIZACAO
SGI_TIMEOUT
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any


# ============================================================
# CARREGAMENTO AUTOMÁTICO DO .env
# ============================================================

def _carregar_env_local():
    candidatos = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]

    for arquivo in candidatos:
        if not arquivo.exists():
            continue

        for linha in arquivo.read_text(
            encoding="utf-8",
            errors="ignore",
        ).splitlines():
            linha = linha.strip()

            if (
                not linha
                or linha.startswith("#")
                or "=" not in linha
            ):
                continue

            chave, valor = linha.split("=", 1)

            chave = chave.strip()
            valor = valor.strip().strip('"').strip("'")

            if chave and chave not in os.environ:
                os.environ[chave] = valor

        break


_carregar_env_local()


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
# API
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

        except urllib.error.HTTPError as error:

            try:

                data = json.loads(
                    error
                    .read()
                    .decode(
                        "utf-8"
                    )
                    or
                    "null"
                )

            except Exception:

                data = str(
                    error
                )

            if error.code in expected:
                return data

            raise ApiError(
                error.code,
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
                "Defina SGI_LOGIN e SGI_PASSWORD antes de executar."
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
        name: str
    ):

        self.passed.append(
            name
        )

        print(
            f"[PASS] {name}"
        )

    def fail(
        self,
        name: str,
        error: Exception | str
    ):

        message = (
            f"{name}: {error}"
        )

        self.failed.append(
            message
        )

        print(
            f"[FAIL] {message}"
        )


R = Report()


# ============================================================
# UTILITÁRIOS
# ============================================================

def section(
    title: str
):

    print()
    print(
        "="
        *
        72
    )

    print(
        title
    )

    print(
        "="
        *
        72
    )


def assert_true(
    value,
    message: str
):

    if not value:

        raise AssertionError(
            message
        )


def norm(
    value
) -> str:

    if value is None:
        return ""

    return str(
        value
    ).strip()


def norm_upper(
    value
) -> str:

    return norm(
        value
    ).upper()


def unique_code(
    prefix: str
) -> str:

    short = "".join(
        ch
        for ch
        in prefix.upper()
        if ch.isalnum()
    )[:7]

    suffix = str(
        int(
            time.time()
            *
            1000
        )
    )[-10:]

    # Banco atual: CodigoInventario <= 30.
    return (
        f"E2E12-{short}-{suffix}"
    )[:30]


def qty_stock(
    item: dict
) -> float:

    for key in (
        "qtd_estoque",
        "quantidade_estoque",
        "saldo_inventario",
    ):

        if (
            key
            in item
            and
            item[
                key
            ]
            is not None
        ):

            return float(
                item[
                    key
                ]
            )

    raise AssertionError(
        f"Quantidade de estoque não encontrada no item: {item}"
    )


def item_key_rotativo(
    item: dict
) -> tuple[str, str, str]:

    return (
        norm_upper(
            item.get(
                "localizacao"
            )
        ),
        norm_upper(
            item.get(
                "codigo"
            )
        ),
        norm_upper(
            item.get(
                "lote"
            )
        ),
    )


def item_key_oficial(
    item: dict
) -> tuple[str, str]:

    return (
        norm_upper(
            item.get(
                "codigo"
            )
        ),
        norm_upper(
            item.get(
                "lote"
            )
        ),
    )


# ============================================================
# OPERAÇÕES COMUNS
# ============================================================

def create_inventory(
    inventory_type: str,
    prefix: str
) -> dict:

    return api.request(
        "POST",
        "/inventarios",
        {
            "codigo_inventario":
                unique_code(
                    prefix
                ),

            "tipo":
                inventory_type,

            "cliente_id":
                CLIENTE_ID,

            "cliente":
                CLIENTE,

            "descricao":
                (
                    "E2E Estágio 12 - "
                    f"{inventory_type}"
                ),

            "armazem":
                ARMAZEM,
        }
    )


def add_scope(
    inventory_id: int
):

    return api.request(
        "POST",
        (
            f"/inventarios/"
            f"{inventory_id}"
            f"/escopo/localizacoes"
        ),
        {
            "localizacoes":
                [
                    LOCALIZACAO
                ]
        }
    )


def snapshot(
    inventory_id: int
):

    return api.request(
        "POST",
        (
            f"/inventarios/"
            f"{inventory_id}"
            f"/snapshot"
        ),
        {}
    )


def start_location(
    inventory_id: int,
    round_id: int,
    location: str = LOCALIZACAO
):

    return api.request(
        "POST",
        "/localizacoes/iniciar",
        {
            "id_inventario":
                inventory_id,

            "id_rodada":
                round_id,

            "localizacao":
                location,
        }
    )


def count_item(
    session_id: int,
    item: dict,
    quantity: float
):

    return api.request(
        "POST",
        "/contagens",
        {
            "id_sessao":
                session_id,

            "codigo":
                str(
                    item[
                        "codigo"
                    ]
                ),

            "lote":
                (
                    item.get(
                        "lote"
                    )
                    or
                    ""
                ),

            "quantidade":
                quantity,
        }
    )


def close_location(
    session_id: int,
    empty: bool = False
):

    return api.request(
        "POST",
        "/localizacoes/encerrar",
        {
            "id_sessao":
                session_id,

            "localizacao_vazia":
                empty,
        }
    )


def next_round(
    inventory_id: int
):

    return api.request(
        "POST",
        (
            f"/inventarios/"
            f"{inventory_id}"
            f"/rodadas/proxima"
        )
    )


def preview_next_round(
    inventory_id: int
):

    return api.request(
        "GET",
        (
            f"/inventarios/"
            f"{inventory_id}"
            f"/rodadas/proxima-preview"
        )
    )


def final_result(
    inventory_id: int
):

    return api.request(
        "GET",
        (
            f"/inventarios/"
            f"{inventory_id}"
            f"/resultado-final"
        )
    )


# ============================================================
# ROTATIVO
# ============================================================

def rotativo_analysis(
    inventory_id: int
):

    return api.request(
        "GET",
        (
            f"/inventarios/"
            f"{inventory_id}"
            f"/analise-rotativo"
        )
    )


def rotativo_decision(
    inventory_id: int,
    round_id: int,
    item: dict,
    decision: str,
    justification: str | None = None
):

    body = {
        "id_rodada":
            round_id,

        "localizacao":
            norm_upper(
                item.get(
                    "localizacao"
                )
                or
                LOCALIZACAO
            ),

        "codigo":
            str(
                item[
                    "codigo"
                ]
            ),

        "lote":
            (
                item.get(
                    "lote"
                )
                or
                ""
            ),

        "decisao":
            decision,
    }

    if justification is not None:

        body[
            "justificativa"
        ] = (
            justification
        )

    return api.request(
        "POST",
        (
            f"/inventarios/"
            f"{inventory_id}"
            f"/decisoes-rotativo"
        ),
        body
    )


def choose_rotativo_target(
    inventory_id: int
) -> tuple[dict, list[dict]]:

    analysis = rotativo_analysis(
        inventory_id
    )

    items = [
        item
        for item
        in analysis.get(
            "itens",
            []
        )
        if (
            norm_upper(
                item.get(
                    "localizacao"
                )
            )
            ==
            LOCALIZACAO
            and
            qty_stock(
                item
            )
            >
            0
        )
    ]

    assert_true(
        bool(
            items
        ),
        (
            "Nenhum item positivo localizado "
            "na análise ROTATIVO."
        )
    )

    return (
        items[
            0
        ],
        items
    )


def execute_rotativo_r1_with_divergence(
    inventory_id: int,
    round_id: int
) -> dict:

    target, items = (
        choose_rotativo_target(
            inventory_id
        )
    )

    session = start_location(
        inventory_id,
        round_id
    )

    session_id = (
        session[
            "id_sessao"
        ]
    )

    for item in items:

        stock_qty = qty_stock(
            item
        )

        if stock_qty <= 0:
            continue

        quantity = (
            stock_qty
            +
            1
            if (
                item_key_rotativo(
                    item
                )
                ==
                item_key_rotativo(
                    target
                )
            )
            else
            stock_qty
        )

        count_item(
            session_id,
            item,
            quantity
        )

    close_location(
        session_id
    )

    analysis = rotativo_analysis(
        inventory_id
    )

    divergences = [
        item
        for item
        in analysis.get(
            "itens",
            []
        )
        if (
            norm_upper(
                item.get(
                    "status"
                )
            )
            not in (
                "",
                "OK",
            )
        )
    ]

    target_key = (
        item_key_rotativo(
            target
        )
    )

    logical_matches = [
        item
        for item
        in divergences
        if (
            item_key_rotativo(
                item
            )
            ==
            target_key
        )
    ]

    assert_true(
        len(
            logical_matches
        )
        ==
        1,
        (
            "A divergência esperada do ROTATIVO "
            "não foi localizada isoladamente. "
            f"Divergências: {divergences}"
        )
    )

    return target


# ============================================================
# OFICIAL
# ============================================================

def official_round_analysis(
    inventory_id: int,
    round_id: int
):

    return api.request(
        "GET",
        (
            f"/inventarios/"
            f"{inventory_id}"
            f"/rodadas/"
            f"{round_id}"
            f"/analise"
        )
    )


def official_recount_analysis(
    inventory_id: int,
    round_id: int
):

    return api.request(
        "GET",
        (
            f"/inventarios/"
            f"{inventory_id}"
            f"/rodadas/"
            f"{round_id}"
            f"/analise-recontagem"
        )
    )


def official_manager_analysis(
    inventory_id: int
):

    return api.request(
        "GET",
        (
            f"/inventarios/"
            f"{inventory_id}"
            f"/analise-gestor"
        )
    )


def finalize_official(
    inventory_id: int
):

    return api.request(
        "POST",
        (
            f"/inventarios/"
            f"{inventory_id}"
            f"/finalizar"
        ),
        {}
    )


def choose_official_target(
    inventory_id: int,
    round_id: int
) -> tuple[dict, list[dict]]:

    analysis = official_round_analysis(
        inventory_id,
        round_id
    )

    assert_true(
        analysis.get(
            "regra_conciliacao"
        )
        ==
        "CODIGO_LOTE",
        (
            "OFICIAL não está usando "
            "regra CODIGO_LOTE."
        )
    )

    assert_true(
        analysis.get(
            "considera_localizacao"
        )
        is False,
        (
            "OFICIAL passou a considerar "
            "localização na chave lógica."
        )
    )

    items = [
        item
        for item
        in analysis.get(
            "itens",
            []
        )
        if (
            qty_stock(
                item
            )
            >
            0
        )
    ]

    assert_true(
        bool(
            items
        ),
        (
            "Nenhum item positivo encontrado "
            "no OFICIAL."
        )
    )

    # Preferência por qtd > 1 para produzir diferença com qtd-1,
    # respeitando a regra de quantidade > 0 da API.
    for item in items:

        if qty_stock(
            item
        ) > 1:

            return (
                item,
                items
            )

    # Fallback: usa qtd + 1.
    return (
        items[
            0
        ],
        items
    )


def official_divergent_quantity(
    item: dict
) -> float:

    stock_qty = qty_stock(
        item
    )

    if stock_qty > 1:
        return stock_qty - 1

    return stock_qty + 1


def count_official_complete_round(
    inventory_id: int,
    round_id: int,
    target: dict,
    items: list[dict]
):

    session = start_location(
        inventory_id,
        round_id
    )

    session_id = (
        session[
            "id_sessao"
        ]
    )

    target_key = (
        item_key_oficial(
            target
        )
    )

    for item in items:

        stock_qty = qty_stock(
            item
        )

        if stock_qty <= 0:
            continue

        quantity = (
            official_divergent_quantity(
                item
            )
            if (
                item_key_oficial(
                    item
                )
                ==
                target_key
            )
            else
            stock_qty
        )

        count_item(
            session_id,
            item,
            quantity
        )

    close_location(
        session_id
    )


def validate_single_official_divergence(
    analysis: dict,
    target: dict
):

    divergences = [
        item
        for item
        in analysis.get(
            "itens",
            []
        )
        if (
            norm_upper(
                item.get(
                    "status"
                )
            )
            !=
            "OK"
        )
    ]

    assert_true(
        len(
            divergences
        )
        ==
        1,
        (
            "Era esperada exatamente 1 divergência "
            "no OFICIAL. "
            f"Encontrado: {divergences}"
        )
    )

    assert_true(
        item_key_oficial(
            divergences[
                0
            ]
        )
        ==
        item_key_oficial(
            target
        ),
        (
            "A divergência encontrada no OFICIAL "
            "não corresponde ao item-alvo."
        )
    )


# ============================================================
# TESTE PRINCIPAL
# ============================================================

def test_coexistence_and_isolation():

    section(
        "1. CRIANDO ROTATIVO E OFICIAL SIMULTANEAMENTE"
    )

    rot = create_inventory(
        "ROTATIVO",
        "ROT"
    )

    off = create_inventory(
        "OFICIAL",
        "OFICIAL"
    )

    rot_id = int(
        rot[
            "id_inventario"
        ]
    )

    off_id = int(
        off[
            "id_inventario"
        ]
    )

    rot_r1 = int(
        rot[
            "id_rodada"
        ]
    )

    off_r1 = int(
        off[
            "id_rodada"
        ]
    )

    assert_true(
        rot_id
        !=
        off_id,
        (
            "ROTATIVO e OFICIAL receberam "
            "o mesmo ID_Inventario."
        )
    )

    assert_true(
        norm_upper(
            rot.get(
                "tipo"
            )
        )
        ==
        "ROTATIVO",
        (
            f"Tipo ROTATIVO inválido: {rot}"
        )
    )

    assert_true(
        norm_upper(
            off.get(
                "tipo"
            )
        )
        ==
        "OFICIAL",
        (
            f"Tipo OFICIAL inválido: {off}"
        )
    )

    print(
        f"ROTATIVO: inventário {rot_id}, R1 {rot_r1}"
    )

    print(
        f"OFICIAL:  inventário {off_id}, R1 {off_r1}"
    )

    section(
        "2. ESCOPO + SNAPSHOT INDEPENDENTES"
    )

    add_scope(
        rot_id
    )

    add_scope(
        off_id
    )

    rot_snapshot = snapshot(
        rot_id
    )

    off_snapshot = snapshot(
        off_id
    )

    rot_total = int(
        rot_snapshot.get(
            "registros_snapshot",
            0
        )
        or
        rot_snapshot.get(
            "total_registros",
            0
        )
        or
        0
    )

    off_total = int(
        off_snapshot.get(
            "registros_snapshot",
            0
        )
        or
        off_snapshot.get(
            "total_registros",
            0
        )
        or
        0
    )

    assert_true(
        rot_total > 0,
        (
            f"Snapshot ROTATIVO vazio: {rot_snapshot}"
        )
    )

    assert_true(
        off_total > 0,
        (
            f"Snapshot OFICIAL vazio: {off_snapshot}"
        )
    )

    print(
        f"Snapshot ROTATIVO: {rot_total}"
    )

    print(
        f"Snapshot OFICIAL:  {off_total}"
    )

    # Captura baseline OFICIAL antes de qualquer decisão ROTATIVO.
    official_before_rot_decision = (
        official_round_analysis(
            off_id,
            off_r1
        )
    )

    section(
        "3. ROTATIVO - DIVERGÊNCIA + JUSTIFICATIVA"
    )

    rot_target = (
        execute_rotativo_r1_with_divergence(
            rot_id,
            rot_r1
        )
    )

    decision = rotativo_decision(
        rot_id,
        rot_r1,
        rot_target,
        "JUSTIFICAR_DIVERGENCIA",
        (
            "E2E Estágio 12 - divergência "
            "ROTATIVO justificada."
        )
    )

    assert_true(
        bool(
            decision
        ),
        (
            "Decisão ROTATIVO não retornou dados."
        )
    )

    # A decisão ROTATIVO não pode alterar a análise da R1 OFICIAL.
    official_after_rot_decision = (
        official_round_analysis(
            off_id,
            off_r1
        )
    )

    assert_true(
        official_before_rot_decision.get(
            "resumo"
        )
        ==
        official_after_rot_decision.get(
            "resumo"
        ),
        (
            "Decisão do ROTATIVO alterou o resumo "
            "do inventário OFICIAL."
        )
    )

    rot_finish = next_round(
        rot_id
    )

    rot_pr = (
        rot_finish.get(
            "proxima_rodada",
            {}
        )
    )

    assert_true(
        rot_pr.get(
            "status_inventario"
        )
        ==
        "FINALIZADO",
        (
            "ROTATIVO justificado não finalizou "
            f"na R1: {rot_finish}"
        )
    )

    assert_true(
        int(
            rot_pr.get(
                "numero_rodada",
                1
            )
            or
            1
        )
        <=
        1,
        (
            "ROTATIVO justificado criou R2 "
            f"indevidamente: {rot_finish}"
        )
    )

    rot_result = final_result(
        rot_id
    )

    assert_true(
        norm_upper(
            rot_result.get(
                "status"
            )
            or
            rot_result.get(
                "status_inventario"
            )
        )
        ==
        "FINALIZADO",
        (
            f"Resultado ROTATIVO inválido: {rot_result}"
        )
    )

    section(
        "4. CONFIRMANDO QUE O OFICIAL CONTINUA INDEPENDENTE"
    )

    # Se o ROTATIVO tivesse contaminado o OFICIAL, esta análise/fluxo
    # tenderia a trazer estado finalizado ou resultados alterados.
    off_analysis_r1_initial = (
        official_round_analysis(
            off_id,
            off_r1
        )
    )

    off_target, off_items_r1 = (
        choose_official_target(
            off_id,
            off_r1
        )
    )

    assert_true(
        len(
            off_analysis_r1_initial.get(
                "itens",
                []
            )
        )
        >
        0,
        (
            "OFICIAL deixou de possuir itens "
            "após finalização do ROTATIVO."
        )
    )

    print(
        "ROTATIVO finalizado; "
        "OFICIAL segue operacional."
    )

    section(
        "5. OFICIAL R1 - CRIANDO DIVERGÊNCIA"
    )

    count_official_complete_round(
        off_id,
        off_r1,
        off_target,
        off_items_r1
    )

    off_analysis_r1 = (
        official_round_analysis(
            off_id,
            off_r1
        )
    )

    validate_single_official_divergence(
        off_analysis_r1,
        off_target
    )

    section(
        "6. OFICIAL R2 - MESMA DIVERGÊNCIA"
    )

    preview_r2 = (
        preview_next_round(
            off_id
        )
    )

    p2 = preview_r2.get(
        "preview",
        {}
    )

    assert_true(
        p2.get(
            "tipo_proxima_rodada"
        )
        ==
        "COMPLETA",
        (
            f"OFICIAL R2 deixou de ser COMPLETA: {preview_r2}"
        )
    )

    r2_created = (
        next_round(
            off_id
        )
    )

    off_r2_data = (
        r2_created[
            "proxima_rodada"
        ]
    )

    off_r2 = int(
        off_r2_data[
            "id_rodada"
        ]
    )

    assert_true(
        int(
            off_r2_data.get(
                "numero_rodada",
                0
            )
        )
        ==
        2,
        (
            f"R2 OFICIAL inválida: {r2_created}"
        )
    )

    off_analysis_r2_initial = (
        official_round_analysis(
            off_id,
            off_r2
        )
    )

    off_items_r2 = (
        off_analysis_r2_initial.get(
            "itens",
            []
        )
    )

    assert_true(
        len(
            off_items_r2
        )
        ==
        len(
            off_items_r1
        ),
        (
            "R2 COMPLETA OFICIAL não contém "
            "o mesmo conjunto lógico da R1."
        )
    )

    count_official_complete_round(
        off_id,
        off_r2,
        off_target,
        off_items_r2
    )

    off_analysis_r2 = (
        official_round_analysis(
            off_id,
            off_r2
        )
    )

    validate_single_official_divergence(
        off_analysis_r2,
        off_target
    )

    section(
        "7. OFICIAL R3 - SOMENTE DIVERGÊNCIAS"
    )

    preview_r3 = (
        preview_next_round(
            off_id
        )
    )

    p3 = preview_r3.get(
        "preview",
        {}
    )

    assert_true(
        p3.get(
            "tipo_proxima_rodada"
        )
        ==
        "DIVERGENCIAS",
        (
            f"OFICIAL R3 não é DIVERGENCIAS: {preview_r3}"
        )
    )

    assert_true(
        int(
            p3.get(
                "candidatos",
                0
            )
        )
        ==
        1,
        (
            "OFICIAL deveria possuir exatamente "
            f"1 candidato para R3: {preview_r3}"
        )
    )

    r3_created = next_round(
        off_id
    )

    off_r3_data = (
        r3_created[
            "proxima_rodada"
        ]
    )

    off_r3 = int(
        off_r3_data[
            "id_rodada"
        ]
    )

    assert_true(
        int(
            off_r3_data.get(
                "itens_gerados",
                0
            )
        )
        ==
        1,
        (
            f"R3 OFICIAL gerou quantidade inválida: {r3_created}"
        )
    )

    assert_true(
        off_r3_data.get(
            "origem_candidatos"
        )
        ==
        "DIVERGENCIAS_R1_R2",
        (
            f"Origem da R3 OFICIAL inválida: {r3_created}"
        )
    )

    recount_before = (
        official_recount_analysis(
            off_id,
            off_r3
        )
    )

    recount_items = [
        item
        for item
        in recount_before.get(
            "itens",
            []
        )
        if bool(
            item.get(
                "item_original_recontagem",
                True
            )
        )
    ]

    assert_true(
        len(
            recount_items
        )
        ==
        1,
        (
            "R3 OFICIAL deveria conter um único "
            f"item original: {recount_items}"
        )
    )

    r3_target = (
        recount_items[
            0
        ]
    )

    assert_true(
        item_key_oficial(
            r3_target
        )
        ==
        item_key_oficial(
            off_target
        ),
        (
            "Candidato da R3 OFICIAL não corresponde "
            "à divergência criada em R1/R2."
        )
    )

    locations_r3 = (
        recount_before.get(
            "localizacoes_rodada",
            []
        )
        or
        off_r3_data.get(
            "localizacoes",
            []
        )
        or
        [
            LOCALIZACAO
        ]
    )

    normalized_locations = []

    for location in locations_r3:

        if isinstance(
            location,
            dict
        ):

            location = (
                location.get(
                    "localizacao"
                )
                or
                location.get(
                    "Localizacao"
                )
            )

        location = norm_upper(
            location
        )

        if (
            location
            and
            location
            not in normalized_locations
        ):

            normalized_locations.append(
                location
            )

    assert_true(
        bool(
            normalized_locations
        ),
        (
            "Nenhuma localização disponível na R3 OFICIAL."
        )
    )

    # Como OFICIAL consolida Código+Lote, conta a quantidade correta
    # somente na primeira localização e encerra eventuais demais como vazias.
    first = True

    for location in normalized_locations:

        session = start_location(
            off_id,
            off_r3,
            location
        )

        session_id = (
            session[
                "id_sessao"
            ]
        )

        if first:

            count_item(
                session_id,
                r3_target,
                qty_stock(
                    r3_target
                )
            )

            close_location(
                session_id,
                empty=False
            )

            first = False

        else:

            close_location(
                session_id,
                empty=True
            )

    recount_after = (
        official_recount_analysis(
            off_id,
            off_r3
        )
    )

    assert_true(
        recount_after.get(
            "rodada_operacional_concluida"
        )
        is True,
        (
            f"R3 OFICIAL não concluiu: {recount_after}"
        )
    )

    assert_true(
        recount_after.get(
            "status_recontagem"
        )
        ==
        "CONCILIADA",
        (
            f"R3 OFICIAL não conciliou: {recount_after}"
        )
    )

    assert_true(
        int(
            recount_after.get(
                "resumo",
                {}
            ).get(
                "pendentes_proxima_rodada",
                0
            )
        )
        ==
        0,
        (
            f"R3 OFICIAL deixou pendências: {recount_after}"
        )
    )

    section(
        "8. GESTOR + FINALIZAÇÃO OFICIAL"
    )

    manager = official_manager_analysis(
        off_id
    )

    manager_summary = (
        manager.get(
            "resumo",
            {}
        )
    )

    assert_true(
        int(
            manager_summary.get(
                "itens_sem_decisao",
                0
            )
        )
        ==
        0,
        (
            f"OFICIAL possui itens sem decisão: {manager}"
        )
    )

    assert_true(
        int(
            manager_summary.get(
                "nova_recontagem",
                0
            )
        )
        ==
        0,
        (
            f"OFICIAL solicitou nova recontagem: {manager}"
        )
    )

    assert_true(
        manager.get(
            "pode_finalizar_inventario"
        )
        is True,
        (
            f"OFICIAL não pode finalizar: {manager}"
        )
    )

    finalized_official = finalize_official(
        off_id
    )

    assert_true(
        finalized_official.get(
            "status"
        )
        ==
        "FINALIZADO",
        (
            f"Finalização OFICIAL falhou: {finalized_official}"
        )
    )

    off_result = final_result(
        off_id
    )

    assert_true(
        norm_upper(
            off_result.get(
                "status"
            )
            or
            off_result.get(
                "status_inventario"
            )
        )
        ==
        "FINALIZADO",
        (
            f"Resultado final OFICIAL inválido: {off_result}"
        )
    )

    section(
        "9. VALIDAÇÕES FINAIS DE ISOLAMENTO"
    )

    # Resultado ROTATIVO continua estável mesmo após todo o OFICIAL.
    rot_result_after_official = final_result(
        rot_id
    )

    assert_true(
        rot_result_after_official
        ==
        rot_result,
        (
            "Resultado final ROTATIVO mudou após "
            "processamento/finalização do OFICIAL."
        )
    )

    # Os IDs precisam permanecer independentes nos retornos finais,
    # quando o endpoint expõe id_inventario.
    if (
        rot_result.get(
            "id_inventario"
        )
        is not None
    ):

        assert_true(
            int(
                rot_result[
                    "id_inventario"
                ]
            )
            ==
            rot_id,
            (
                "Resultado final ROTATIVO aponta "
                "para ID_Inventario incorreto."
            )
        )

    if (
        off_result.get(
            "id_inventario"
        )
        is not None
    ):

        assert_true(
            int(
                off_result[
                    "id_inventario"
                ]
            )
            ==
            off_id,
            (
                "Resultado final OFICIAL aponta "
                "para ID_Inventario incorreto."
            )
        )

    # Chave usada no ROTATIVO não deve ter sido criada como consequência
    # de operações do OFICIAL. O teste principal aqui é estabilidade do
    # resultado final e continuidade independente dos fluxos.
    assert_true(
        rot_id
        !=
        off_id,
        (
            "Falha crítica de isolamento: "
            "IDs dos inventários coincidem."
        )
    )

    print(
        f"ROTATIVO finalizado: {rot_id}"
    )

    print(
        f"OFICIAL finalizado:  {off_id}"
    )

    print(
        "Resultados finais permaneceram independentes."
    )


# ============================================================
# EXECUÇÃO
# ============================================================

def run(
    name: str,
    fn
):

    try:

        fn()

        R.ok(
            name
        )

    except Exception as error:

        R.fail(
            name,
            error
        )



def assert_tx(cond, msg):
    if not cond:
        raise AssertionError(msg)


def expect_block(fn, statuses=(400, 409, 422)):
    try:
        fn()
    except Exception as exc:
        status = getattr(exc, "status", getattr(exc, "status_code", None))
        if status is not None and status not in statuses:
            raise AssertionError(f"HTTP inesperado {status}: {exc}")
        return
    raise AssertionError("Operação inválida foi aceita.")


def test_estagio13():
    import time

    print("=" * 72)
    print("SGI - ESTÁGIO 13 | INTEGRIDADE TRANSACIONAL E RECUPERAÇÃO")
    print("=" * 72)

    # Cenário 1: erro de contagem não pode inutilizar/corromper a sessão.
    code = f"E2E-TX13-{str(int(time.time()*1000))[-10:]}"[:30]
    inv = api.request("POST", "/inventarios", {
        "codigo_inventario": code,
        "tipo": "ROTATIVO",
        "cliente_id": CLIENTE_ID,
        "cliente": CLIENTE,
        "descricao": "Estagio 13 - recuperacao de falha",
        "armazem": ARMAZEM,
    })
    iid, r1 = inv["id_inventario"], inv["id_rodada"]

    api.request("POST", f"/inventarios/{iid}/escopo/localizacoes",
                {"localizacoes": [LOCALIZACAO]})
    api.request("POST", f"/inventarios/{iid}/snapshot", {})

    analise = api.request("GET", f"/inventarios/{iid}/rodadas/{r1}/analise")
    itens = analise.get("itens", [])
    positivos = []
    for it in itens:
        q = it.get("qtd_estoque", it.get("quantidade_estoque", 0))
        try:
            q = float(q or 0)
        except Exception:
            q = 0
        if q > 0:
            x = dict(it)
            x["_q"] = q
            positivos.append(x)

    assert_tx(positivos, f"Snapshot sem itens positivos: {analise}")

    sess = api.request("POST", "/localizacoes/iniciar", {
        "id_inventario": iid,
        "id_rodada": r1,
        "localizacao": LOCALIZACAO,
    })
    sid = sess["id_sessao"]

    target = positivos[0]

    expect_block(lambda: api.request("POST", "/contagens", {
        "id_sessao": sid,
        "codigo": str(target["codigo"]),
        "lote": target.get("lote") or "",
        "quantidade": -1,
    }))

    # A sessão deve continuar funcional depois da requisição rejeitada.
    for it in positivos:
        api.request("POST", "/contagens", {
            "id_sessao": sid,
            "codigo": str(it["codigo"]),
            "lote": it.get("lote") or "",
            "quantidade": it["_q"],
        })

    api.request("POST", "/localizacoes/encerrar", {
        "id_sessao": sid,
        "localizacao_vazia": False,
    })

    a1 = api.request("GET", f"/inventarios/{iid}/rodadas/{r1}/analise")
    assert_tx(
        int(a1.get("resumo", {}).get("divergencias", 0) or 0) == 0,
        f"Erro rejeitado deixou efeito residual: {a1}",
    )
    print("[PASS] Requisição inválida não corrompe sessão")

    # Cenário 2: sessão encerrada não pode sofrer mutação.
    before = a1.get("resumo")
    expect_block(lambda: api.request("POST", "/contagens", {
        "id_sessao": sid,
        "codigo": str(target["codigo"]),
        "lote": target.get("lote") or "",
        "quantidade": target["_q"],
    }))
    after = api.request("GET", f"/inventarios/{iid}/rodadas/{r1}/analise")
    assert_tx(before == after.get("resumo"),
              "Operação após encerramento alterou a rodada.")
    print("[PASS] Falha após encerramento não altera estado")

    # Cenário 3: finalização terminal deve ser estável/idempotente.
    fin = api.request("POST", f"/inventarios/{iid}/rodadas/proxima", {})
    pf = fin.get("proxima_rodada", fin)
    assert_tx(
        str(pf.get("status_inventario", "")).upper() == "FINALIZADO",
        f"Inventário correto não finalizou: {fin}",
    )

    rf1 = api.request("GET", f"/inventarios/{iid}/resultado-final")

    try:
        api.request("POST", f"/inventarios/{iid}/rodadas/proxima", {})
    except Exception as exc:
        status = getattr(exc, "status", getattr(exc, "status_code", None))
        assert_tx(status in (400, 409),
                  f"HTTP inesperado na repetição terminal: {exc}")

    rf2 = api.request("GET", f"/inventarios/{iid}/resultado-final")
    assert_tx(rf1 == rf2,
              "Resultado final mudou após repetição de operação terminal.")
    print("[PASS] Resultado final permanece estável após repetição")

    # Cenário 4: inventário finalizado continua bloqueado para nova sessão.
    expect_block(lambda: api.request("POST", "/localizacoes/iniciar", {
        "id_inventario": iid,
        "id_rodada": r1,
        "localizacao": LOCALIZACAO,
    }), statuses=(400, 409))
    rf3 = api.request("GET", f"/inventarios/{iid}/resultado-final")
    assert_tx(rf2 == rf3,
              "Tentativa pós-finalização alterou resultado final.")
    print("[PASS] Estado final é imutável para operação posterior")


def main():
    import sys

    print("=" * 72)
    print("SGI - ESTÁGIO 13 | INTEGRIDADE TRANSACIONAL E RECUPERAÇÃO DE ESTADO")
    print(f"API: {BASE} | Cliente: {CLIENTE_ID} | Armazém: {ARMAZEM}")
    print("=" * 72)

    try:
        api.login()
        print("[PASS] Autenticação")
        test_estagio13()
    except Exception as exc:
        print(f"[FAIL] Estágio 13: {exc}")
        print()
        print("=" * 72)
        print("PASS: 1 | FAIL: 1")
        print("RESULTADO: REPROVADO")
        print("=" * 72)
        sys.exit(1)

    print()
    print("=" * 72)
    print("PASS: 5 | FAIL: 0")
    print("RESULTADO: APROVADO")
    print("=" * 72)


if __name__ == "__main__":
    main()
