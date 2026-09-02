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




# ======================================================================
# ESTÁGIO 14 — CONCORRÊNCIA REAL / MULTIUSUÁRIO
# ======================================================================

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


def assert_c14(cond, msg):
    if not cond:
        raise AssertionError(msg)


def _status_from_exc(exc):
    return getattr(
        exc,
        "status",
        getattr(exc, "status_code", None),
    )


def _unique_code(tag):
    sufixo = str(int(time.time() * 1000))[-10:]
    tag = "".join(
        ch for ch in str(tag).upper()
        if ch.isalnum()
    )[:8]
    return f"E2E-C14-{tag}-{sufixo}"[:30]


def _create_rotativo(tag):
    return api.request(
        "POST",
        "/inventarios",
        {
            "codigo_inventario": _unique_code(tag),
            "tipo": "ROTATIVO",
            "cliente_id": CLIENTE_ID,
            "cliente": CLIENTE,
            "descricao": f"Estagio 14 - {tag}",
            "armazem": ARMAZEM,
        },
    )


def _scope(iid, locations):
    return api.request(
        "POST",
        f"/inventarios/{iid}/escopo/localizacoes",
        {"localizacoes": locations},
    )


def _snapshot(iid):
    return api.request(
        "POST",
        f"/inventarios/{iid}/snapshot",
        {},
    )


def _analysis(iid, rid):
    return api.request(
        "GET",
        f"/inventarios/{iid}/rodadas/{rid}/analise",
    )


def _start(iid, rid, location):
    return api.request(
        "POST",
        "/localizacoes/iniciar",
        {
            "id_inventario": iid,
            "id_rodada": rid,
            "localizacao": location,
        },
    )


def _count(sid, item, qty):
    return api.request(
        "POST",
        "/contagens",
        {
            "id_sessao": sid,
            "codigo": str(item["codigo"]),
            "lote": item.get("lote") or "",
            "quantidade": qty,
        },
    )


def _close(sid, empty=False):
    return api.request(
        "POST",
        "/localizacoes/encerrar",
        {
            "id_sessao": sid,
            "localizacao_vazia": empty,
        },
    )


def _next_round(iid):
    return api.request(
        "POST",
        f"/inventarios/{iid}/rodadas/proxima",
        {},
    )


def _decision_recontar(iid, rid, location, item):
    return api.request(
        "POST",
        f"/inventarios/{iid}/decisoes-rotativo",
        {
            "id_rodada": rid,
            "localizacao": location,
            "codigo": str(item["codigo"]),
            "lote": item.get("lote") or "",
            "decisao": "RECONTAR",
        },
    )


def _positive_items(iid, rid):
    a = _analysis(iid, rid)
    items = []

    for it in a.get("itens", []):
        q = it.get(
            "qtd_estoque",
            it.get("quantidade_estoque", 0),
        )

        try:
            q = float(q or 0)
        except Exception:
            q = 0

        if q > 0:
            cp = dict(it)
            cp["_q"] = q
            items.append(cp)

    assert_c14(
        items,
        f"Nenhum item positivo encontrado na análise: {a}",
    )

    return items


def _prepare(tag, locations=None):
    if locations is None:
        locations = [LOCALIZACAO]

    inv = _create_rotativo(tag)

    iid = inv["id_inventario"]
    r1 = inv["id_rodada"]

    _scope(iid, locations)
    _snapshot(iid)

    items = _positive_items(iid, r1)

    return iid, r1, items


def _run_parallel(callables, max_workers=None):
    if max_workers is None:
        max_workers = len(callables)

    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(fn)
            for fn in callables
        ]

        for future in as_completed(futures):
            try:
                results.append(
                    {
                        "ok": True,
                        "value": future.result(),
                        "error": None,
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "ok": False,
                        "value": None,
                        "error": exc,
                        "status": _status_from_exc(exc),
                    }
                )

    return results


def test_duas_sessoes_mesma_localizacao():
    iid, r1, items = _prepare(
        "SESSAO"
    )

    barrier = threading.Barrier(2)

    def abrir():
        barrier.wait()
        return _start(
            iid,
            r1,
            LOCALIZACAO,
        )

    results = _run_parallel(
        [abrir, abrir],
        max_workers=2,
    )

    sucessos = [
        r for r in results
        if r["ok"]
    ]

    bloqueios = [
        r for r in results
        if (
            not r["ok"]
            and r.get("status")
            in (400, 409, 422)
        )
    ]

    # São aceitos dois contratos seguros:
    # 1) uma chamada cria e a segunda é bloqueada; ou
    # 2) ambas retornam sucesso, mas recuperando a MESMA sessão física.
    assert_c14(
        len(sucessos) >= 1,
        f"Nenhuma chamada conseguiu abrir/recuperar a sessão: {results}",
    )

    ids = {
        r["value"].get("id_sessao")
        for r in sucessos
        if r["value"].get("id_sessao") is not None
    }

    assert_c14(
        len(ids) == 1,
        (
            "Foram criadas duas sessões físicas para a mesma "
            f"localização/rodada. Retorno: {results}"
        ),
    )

    assert_c14(
        len(sucessos) + len(bloqueios) == 2,
        (
            "A segunda chamada deve recuperar a mesma sessão "
            "ou ser explicitamente bloqueada. "
            f"Retorno: {results}"
        ),
    )

    sid = next(iter(ids))

    for it in items:
        _count(
            sid,
            it,
            it["_q"],
        )

    _close(sid)

def test_contagem_simultanea_mesmo_item():
    iid, r1, items = _prepare(
        "COUNT"
    )

    s = _start(
        iid,
        r1,
        LOCALIZACAO,
    )

    sid = s["id_sessao"]
    target = items[0]

    barrier = threading.Barrier(2)

    def contar():
        barrier.wait()
        return _count(
            sid,
            target,
            target["_q"],
        )

    results = _run_parallel(
        [contar, contar],
        max_workers=2,
    )

    sucessos = [
        r for r in results
        if r["ok"]
    ]

    bloqueios = [
        r for r in results
        if (
            not r["ok"]
            and r.get("status")
            in (400, 409, 422)
        )
    ]

    # Contagens é uma tabela de eventos. Portanto não assumimos
    # que Código+Lote seja UNIQUE dentro da sessão.
    # O que precisa ser garantido sob concorrência:
    # - nenhuma falha 5xx;
    # - cada gravação aceita possui ID próprio;
    # - a sessão permanece íntegra;
    # - a análise final reflete deterministicamente os eventos aceitos.
    assert_c14(
        len(sucessos) + len(bloqueios) == 2,
        f"Resultado concorrente inesperado: {results}",
    )

    ids_contagem = [
        r["value"].get("id_contagem")
        for r in sucessos
        if r["value"].get("id_contagem") is not None
    ]

    assert_c14(
        len(ids_contagem) == len(set(ids_contagem)),
        (
            "Duas respostas de sucesso apontaram para o mesmo "
            f"registro físico de contagem: {results}"
        ),
    )

    # Completa os demais itens apenas uma vez.
    for it in items[1:]:
        _count(
            sid,
            it,
            it["_q"],
        )

    _close(sid)

    a = _analysis(
        iid,
        r1,
    )

    resumo = a.get("resumo", {})

    # Se as duas gravações concorrentes foram aceitas, o item-alvo foi
    # contado duas vezes e a análise DEVE mostrar divergência.
    # Se uma foi bloqueada, a rodada deve permanecer conciliada.
    if len(sucessos) == 2:
        assert_c14(
            int(
                resumo.get("divergencias", 0)
                or 0
            ) >= 1,
            (
                "Duas contagens-evento foram aceitas, porém a análise "
                "não refletiu a quantidade acumulada. "
                f"Análise: {a}"
            ),
        )
    elif len(sucessos) == 1:
        assert_c14(
            int(
                resumo.get("divergencias", 0)
                or 0
            ) == 0,
            (
                "Somente uma contagem foi aceita, mas a rodada ficou "
                f"divergente. Análise: {a}"
            ),
        )

def test_encerramento_simultaneo():
    iid, r1, items = _prepare(
        "CLOSE"
    )

    s = _start(
        iid,
        r1,
        LOCALIZACAO,
    )

    sid = s["id_sessao"]

    for it in items:
        _count(
            sid,
            it,
            it["_q"],
        )

    barrier = threading.Barrier(2)

    def encerrar():
        barrier.wait()
        return _close(
            sid,
            False,
        )

    results = _run_parallel(
        [encerrar, encerrar],
        max_workers=2,
    )

    sucessos = [
        r for r in results
        if r["ok"]
    ]

    bloqueios = [
        r for r in results
        if (
            not r["ok"]
            and r.get("status")
            in (400, 409, 422)
        )
    ]

    assert_c14(
        len(sucessos) == 1,
        (
            "Encerramento concorrente deveria efetivar "
            f"uma única transição de estado. Retorno: {results}"
        ),
    )

    assert_c14(
        len(bloqueios) == 1,
        (
            "A segunda tentativa concorrente de encerramento "
            f"deveria ser bloqueada. Retorno: {results}"
        ),
    )

    a = _analysis(
        iid,
        r1,
    )

    assert_c14(
        int(
            a.get("resumo", {})
            .get("divergencias", 0)
            or 0
        ) == 0,
        (
            "Encerramento concorrente corrompeu análise "
            f"da rodada: {a}"
        ),
    )


def test_criacao_r2_simultanea():
    iid, r1, items = _prepare(
        "R2"
    )

    s = _start(
        iid,
        r1,
        LOCALIZACAO,
    )

    sid = s["id_sessao"]
    target = items[0]

    for it in items:
        q = (
            it["_q"] + 1
            if it is target
            else it["_q"]
        )

        _count(
            sid,
            it,
            q,
        )

    _close(
        sid,
        False,
    )

    _decision_recontar(
        iid,
        r1,
        LOCALIZACAO,
        target,
    )

    barrier = threading.Barrier(2)

    def criar():
        barrier.wait()
        return _next_round(
            iid
        )

    results = _run_parallel(
        [criar, criar],
        max_workers=2,
    )

    sucessos = [
        r for r in results
        if r["ok"]
    ]

    erros_validos = [
        r for r in results
        if (
            not r["ok"]
            and r.get("status")
            in (400, 409, 422)
        )
    ]

    assert_c14(
        len(sucessos) >= 1,
        (
            "Nenhuma das chamadas concorrentes conseguiu "
            f"criar/obter a R2. Retorno: {results}"
        ),
    )

    ids_r2 = set()

    for r in sucessos:
        payload = r["value"]
        pr = payload.get(
            "proxima_rodada",
            payload,
        )

        rid = pr.get(
            "id_rodada"
        )

        numero = pr.get(
            "numero_rodada"
        )

        if rid is not None:
            ids_r2.add(
                rid
            )

        if numero is not None:
            assert_c14(
                int(numero) <= 2,
                (
                    "Chamada concorrente criou rodada além "
                    f"da R2: {payload}"
                ),
            )

    assert_c14(
        len(ids_r2) <= 1,
        (
            "Concorrência criou mais de uma R2 física "
            f"para o mesmo inventário: {results}"
        ),
    )

    assert_c14(
        (
            len(sucessos) == 2
            or
            len(erros_validos) == 1
        ),
        (
            "A segunda chamada deve ser idempotente ou "
            f"explicitamente bloqueada. Retorno: {results}"
        ),
    )


def test_isolamento_sessoes_simultaneas_inventarios_distintos():
    inv_a, r1_a, items_a = _prepare(
        "ISOA"
    )

    inv_b, r1_b, items_b = _prepare(
        "ISOB"
    )

    barrier = threading.Barrier(2)

    def fluxo_a():
        barrier.wait()

        s = _start(
            inv_a,
            r1_a,
            LOCALIZACAO,
        )

        sid = s["id_sessao"]

        for it in items_a:
            _count(
                sid,
                it,
                it["_q"],
            )

        return _close(
            sid,
            False,
        )

    def fluxo_b():
        barrier.wait()

        s = _start(
            inv_b,
            r1_b,
            LOCALIZACAO,
        )

        sid = s["id_sessao"]

        for it in items_b:
            _count(
                sid,
                it,
                it["_q"],
            )

        return _close(
            sid,
            False,
        )

    results = _run_parallel(
        [fluxo_a, fluxo_b],
        max_workers=2,
    )

    assert_c14(
        all(
            r["ok"]
            for r in results
        ),
        (
            "Inventários distintos interferiram entre si "
            f"sob concorrência: {results}"
        ),
    )

    a = _analysis(
        inv_a,
        r1_a,
    )

    b = _analysis(
        inv_b,
        r1_b,
    )

    assert_c14(
        int(
            a.get("resumo", {})
            .get("divergencias", 0)
            or 0
        ) == 0,
        f"Inventário A inconsistente: {a}",
    )

    assert_c14(
        int(
            b.get("resumo", {})
            .get("divergencias", 0)
            or 0
        ) == 0,
        f"Inventário B inconsistente: {b}",
    )


def run_case(name, fn, passed, failed):
    try:
        fn()
        passed.append(name)
        print(
            f"[PASS] {name}"
        )
    except Exception as exc:
        failed.append(
            f"{name}: {exc}"
        )
        print(
            f"[FAIL] {name}: {exc}"
        )


def main():
    print("=" * 76)
    print(
        "SGI - ESTÁGIO 14 | CONCORRÊNCIA REAL / MULTIUSUÁRIO"
    )
    print(
        f"API: {BASE} | Cliente: {CLIENTE_ID} | "
        f"Armazém: {ARMAZEM} | Local: {LOCALIZACAO}"
    )
    print("=" * 76)

    passed = []
    failed = []

    try:
        api.login()
        passed.append(
            "Autenticação"
        )
        print(
            "[PASS] Autenticação"
        )
    except Exception as exc:
        print(
            f"[FAIL] Autenticação: {exc}"
        )
        print()
        print("=" * 76)
        print(
            "PASS: 0 | FAIL: 1"
        )
        print(
            "RESULTADO: REPROVADO"
        )
        print("=" * 76)
        sys.exit(1)

    run_case(
        "Concorrência mantém uma única sessão física por localização/rodada",
        test_duas_sessoes_mesma_localizacao,
        passed,
        failed,
    )

    run_case(
        "Contagens simultâneas permanecem consistentes como eventos",
        test_contagem_simultanea_mesmo_item,
        passed,
        failed,
    )

    run_case(
        "Encerramento simultâneo efetiva uma única transição",
        test_encerramento_simultaneo,
        passed,
        failed,
    )

    run_case(
        "Criação concorrente da R2 não gera duplicidade",
        test_criacao_r2_simultanea,
        passed,
        failed,
    )

    run_case(
        "Inventários distintos permanecem isolados sob concorrência",
        test_isolamento_sessoes_simultaneas_inventarios_distintos,
        passed,
        failed,
    )

    print()
    print("=" * 76)
    print(
        f"PASS: {len(passed)} | FAIL: {len(failed)}"
    )

    if failed:
        print(
            "RESULTADO: REPROVADO"
        )

        for item in failed:
            print(
                " -",
                item,
            )

        print("=" * 76)
        sys.exit(1)

    print(
        "RESULTADO: APROVADO"
    )
    print("=" * 76)


if __name__ == "__main__":
    main()
