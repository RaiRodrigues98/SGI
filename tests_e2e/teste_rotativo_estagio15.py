"""
SGI - ESTÁGIO 15
SEGURANÇA, PERMISSÕES E ISOLAMENTO LÓGICO
=========================================

Objetivo
--------
Validar pela API pública:
1. endpoints protegidos exigem autenticação;
2. token inválido não é aceito;
3. ID_Rodada de outro inventário não pode ser combinado com ID_Inventario;
4. análise de uma rodada não pode ser acessada pelo inventário errado;
5. decisão ROTATIVO não pode usar rodada pertencente a outro inventário;
6. sessão inexistente/adulterada não pode receber contagem;
7. opcionalmente, isolamento real entre clientes/tenants usando uma segunda
   credencial configurada por variáveis de ambiente.

Observação
----------
Os testes 1-6 são obrigatórios e compõem o RESULTADO do Estágio 15.
O teste de tenant real é adicional porque exige uma segunda identidade
não-administradora pertencente a outro ClienteId.

Variáveis principais
--------------------
SGI_BASE_URL
SGI_LOGIN
SGI_PASSWORD
SGI_CLIENTE_ID
SGI_CLIENTE
SGI_ARMAZEM
SGI_LOCALIZACAO
SGI_TIMEOUT

Tenant adicional opcional
-------------------------
SGI_CLIENTE2_LOGIN
SGI_CLIENTE2_PASSWORD
SGI_CLIENTE2_ID

Execução
--------
python tests_e2e\\teste_rotativo_estagio15.py
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any


# ======================================================================
# .env
# ======================================================================

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


# ======================================================================
# CONFIGURAÇÃO
# ======================================================================

BASE = os.getenv(
    "SGI_BASE_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

LOGIN = os.getenv("SGI_LOGIN", "")
PASSWORD = os.getenv("SGI_PASSWORD", "")

CLIENTE_ID = int(
    os.getenv("SGI_CLIENTE_ID", "53")
)

CLIENTE = os.getenv(
    "SGI_CLIENTE",
    "endress",
)

ARMAZEM = os.getenv(
    "SGI_ARMAZEM",
    "ML007",
)

LOCALIZACAO = os.getenv(
    "SGI_LOCALIZACAO",
    "01PLAQUETA",
).strip().upper()

TIMEOUT = float(
    os.getenv("SGI_TIMEOUT", "30")
)

CLIENTE2_LOGIN = os.getenv(
    "SGI_CLIENTE2_LOGIN",
    "",
)

CLIENTE2_PASSWORD = os.getenv(
    "SGI_CLIENTE2_PASSWORD",
    "",
)

CLIENTE2_ID_RAW = os.getenv(
    "SGI_CLIENTE2_ID",
    "",
)

CLIENTE2_ID = (
    int(CLIENTE2_ID_RAW)
    if CLIENTE2_ID_RAW.strip()
    else None
)


# ======================================================================
# API
# ======================================================================

class ApiError(RuntimeError):

    def __init__(
        self,
        status: int,
        data: Any,
        method: str,
        path: str,
    ):
        self.status = status
        self.status_code = status
        self.data = data
        self.method = method
        self.path = path

        super().__init__(
            f"HTTP {status} {method} {path}: {data}"
        )


class API:

    def __init__(
        self,
        token: str = "",
    ):
        self.token = token

    def request(
        self,
        method: str,
        path: str,
        body: Any = None,
        expected=(200, 201),
    ) -> Any:

        headers = {
            "Accept": "application/json",
        }

        if self.token:
            headers["Authorization"] = (
                f"Bearer {self.token}"
            )

        raw = None

        if body is not None:
            raw = json.dumps(
                body
            ).encode("utf-8")

            headers[
                "Content-Type"
            ] = "application/json"

        req = urllib.request.Request(
            BASE + path,
            data=raw,
            headers=headers,
            method=method,
        )

        try:

            with urllib.request.urlopen(
                req,
                timeout=TIMEOUT,
            ) as response:

                raw_body = (
                    response
                    .read()
                    .decode("utf-8")
                )

                data = (
                    json.loads(raw_body)
                    if raw_body
                    else None
                )

                if response.status not in expected:
                    raise ApiError(
                        response.status,
                        data,
                        method,
                        path,
                    )

                return data

        except urllib.error.HTTPError as error:

            try:
                raw_error = (
                    error
                    .read()
                    .decode("utf-8")
                )

                data = (
                    json.loads(raw_error)
                    if raw_error
                    else None
                )

            except Exception:
                data = str(error)

            if error.code in expected:
                return data

            raise ApiError(
                error.code,
                data,
                method,
                path,
            )

    def login_with(
        self,
        login: str,
        password: str,
    ):
        retorno = self.request(
            "POST",
            "/auth/login",
            {
                "login": login,
                "senha": password,
            },
        )

        self.token = retorno[
            "access_token"
        ]

        return retorno

    def login(self):
        if not LOGIN or not PASSWORD:
            raise RuntimeError(
                "Defina SGI_LOGIN e SGI_PASSWORD antes de executar."
            )

        return self.login_with(
            LOGIN,
            PASSWORD,
        )


api = API()


# ======================================================================
# RELATÓRIO
# ======================================================================

@dataclass
class Report:
    passed: list[str] = field(
        default_factory=list
    )
    failed: list[str] = field(
        default_factory=list
    )

    def ok(self, name: str):
        self.passed.append(name)
        print(f"[PASS] {name}")

    def fail(
        self,
        name: str,
        error: Exception | str,
    ):
        message = f"{name}: {error}"
        self.failed.append(message)
        print(f"[FAIL] {message}")


R = Report()


def assert_c15(
    condition,
    message: str,
):
    if not condition:
        raise AssertionError(message)


def unique_code(tag: str) -> str:
    sufixo = str(
        int(time.time() * 1000)
    )[-10:]

    tag = "".join(
        ch
        for ch in str(tag).upper()
        if ch.isalnum()
    )[:8]

    return (
        f"E2E-C15-{tag}-{sufixo}"
    )[:30]


def denied_status(
    status: int | None,
) -> bool:
    return status in (
        400,
        401,
        403,
        404,
        409,
        422,
    )


def expect_denied(
    fn,
    description: str,
):
    try:
        value = fn()

    except ApiError as exc:

        assert_c15(
            denied_status(exc.status),
            (
                f"{description}: deveria ser rejeitado com "
                "4xx controlado, porém retornou "
                f"HTTP {exc.status}: {exc.data}"
            ),
        )

        return exc

    raise AssertionError(
        f"{description}: operação indevida foi aceita. Retorno: {value}"
    )


# ======================================================================
# HELPERS E2E
# ======================================================================

def create_rotativo(
    tag: str,
    api_client: API = api,
    cliente_id: int = CLIENTE_ID,
    cliente: str = CLIENTE,
) -> dict:

    return api_client.request(
        "POST",
        "/inventarios",
        {
            "codigo_inventario":
                unique_code(tag),

            "tipo":
                "ROTATIVO",

            "cliente_id":
                cliente_id,

            "cliente":
                cliente,

            "descricao":
                f"Estagio 15 - {tag}",

            "armazem":
                ARMAZEM,
        },
    )


def add_scope(
    iid: int,
    api_client: API = api,
):
    return api_client.request(
        "POST",
        (
            f"/inventarios/"
            f"{iid}"
            f"/escopo/localizacoes"
        ),
        {
            "localizacoes": [
                LOCALIZACAO
            ],
        },
    )


def snapshot(
    iid: int,
    api_client: API = api,
):
    return api_client.request(
        "POST",
        (
            f"/inventarios/"
            f"{iid}"
            f"/snapshot"
        ),
        {},
    )


def analysis(
    iid: int,
    rid: int,
    api_client: API = api,
):
    return api_client.request(
        "GET",
        (
            f"/inventarios/"
            f"{iid}"
            f"/rodadas/"
            f"{rid}"
            f"/analise"
        ),
    )


def start_location(
    iid: int,
    rid: int,
    api_client: API = api,
):
    return api_client.request(
        "POST",
        "/localizacoes/iniciar",
        {
            "id_inventario":
                iid,

            "id_rodada":
                rid,

            "localizacao":
                LOCALIZACAO,
        },
    )


def count_raw(
    sid: int,
    codigo: str,
    lote: str,
    quantidade: float,
    api_client: API = api,
):
    return api_client.request(
        "POST",
        "/contagens",
        {
            "id_sessao":
                sid,

            "codigo":
                codigo,

            "lote":
                lote,

            "quantidade":
                quantidade,
        },
    )


def decision_raw(
    iid: int,
    rid: int,
    item: dict,
    api_client: API = api,
):
    return api_client.request(
        "POST",
        (
            f"/inventarios/"
            f"{iid}"
            f"/decisoes-rotativo"
        ),
        {
            "id_rodada":
                rid,

            "localizacao":
                (
                    item.get(
                        "localizacao"
                    )
                    or
                    LOCALIZACAO
                ),

            "codigo":
                str(
                    item["codigo"]
                ),

            "lote":
                (
                    item.get("lote")
                    or
                    ""
                ),

            "decisao":
                "RECONTAR",
        },
    )


def positive_item(
    iid: int,
    rid: int,
    api_client: API = api,
) -> dict:

    data = analysis(
        iid,
        rid,
        api_client=api_client,
    )

    for item in data.get(
        "itens",
        [],
    ):

        quantidade = item.get(
            "qtd_estoque",
            item.get(
                "quantidade_estoque",
                0,
            ),
        )

        try:
            quantidade = float(
                quantidade or 0
            )

        except Exception:
            quantidade = 0

        if quantidade > 0:
            cp = dict(item)
            cp["_q"] = quantidade
            return cp

    raise AssertionError(
        (
            "Nenhum item com estoque positivo encontrado "
            f"no inventário {iid}, rodada {rid}. "
            f"Análise: {data}"
        )
    )


def prepare_pair():
    inv_a = create_rotativo(
        "A",
    )

    # pequeno intervalo apenas para garantir códigos distintos
    time.sleep(0.002)

    inv_b = create_rotativo(
        "B",
    )

    iid_a = int(
        inv_a["id_inventario"]
    )
    rid_a = int(
        inv_a["id_rodada"]
    )

    iid_b = int(
        inv_b["id_inventario"]
    )
    rid_b = int(
        inv_b["id_rodada"]
    )

    assert_c15(
        iid_a != iid_b,
        (
            "Os inventários A e B receberam "
            "o mesmo ID_Inventario."
        ),
    )

    assert_c15(
        rid_a != rid_b,
        (
            "Os inventários A e B receberam "
            "o mesmo ID_Rodada físico."
        ),
    )

    add_scope(iid_a)
    snapshot(iid_a)

    add_scope(iid_b)
    snapshot(iid_b)

    item_a = positive_item(
        iid_a,
        rid_a,
    )

    item_b = positive_item(
        iid_b,
        rid_b,
    )

    return {
        "a": {
            "iid": iid_a,
            "rid": rid_a,
            "item": item_a,
        },
        "b": {
            "iid": iid_b,
            "rid": rid_b,
            "item": item_b,
        },
    }


# ======================================================================
# TESTES
# ======================================================================

def test_autenticacao_obrigatoria():
    sem_token = API()

    expect_denied(
        lambda: sem_token.request(
            "POST",
            "/inventarios",
            {
                "codigo_inventario":
                    unique_code("NOTOKEN"),

                "tipo":
                    "ROTATIVO",

                "cliente_id":
                    CLIENTE_ID,

                "cliente":
                    CLIENTE,

                "descricao":
                    "Estagio 15 sem token",

                "armazem":
                    ARMAZEM,
            },
        ),
        "Criação de inventário sem token",
    )


def test_token_invalido():
    invalida = API(
        token=(
            "token-e2e-invalido."
            "nao-assinado."
            "estagio15"
        )
    )

    expect_denied(
        lambda: invalida.request(
            "POST",
            "/inventarios",
            {
                "codigo_inventario":
                    unique_code("BADTOKEN"),

                "tipo":
                    "ROTATIVO",

                "cliente_id":
                    CLIENTE_ID,

                "cliente":
                    CLIENTE,

                "descricao":
                    "Estagio 15 token invalido",

                "armazem":
                    ARMAZEM,
            },
        ),
        "Criação com token inválido",
    )


def test_rodada_de_outro_inventario_na_sessao(
    pair,
):
    a = pair["a"]
    b = pair["b"]

    expect_denied(
        lambda: start_location(
            a["iid"],
            b["rid"],
        ),
        (
            "Iniciar localização usando "
            "Inventário A + Rodada B"
        ),
    )

    # controle positivo: combinação legítima continua funcionando
    sessao = start_location(
        a["iid"],
        a["rid"],
    )

    assert_c15(
        int(
            sessao["id_inventario"]
        )
        ==
        a["iid"],
        (
            "Controle positivo retornou inventário "
            f"incorreto: {sessao}"
        ),
    )

    assert_c15(
        int(
            sessao["id_rodada"]
        )
        ==
        a["rid"],
        (
            "Controle positivo retornou rodada "
            f"incorreta: {sessao}"
        ),
    )


def test_analise_nao_aceita_rodada_de_outro_inventario(
    pair,
):
    a = pair["a"]
    b = pair["b"]

    expect_denied(
        lambda: analysis(
            a["iid"],
            b["rid"],
        ),
        (
            "Consultar análise usando "
            "Inventário A + Rodada B"
        ),
    )

    controle = analysis(
        a["iid"],
        a["rid"],
    )

    assert_c15(
        int(
            controle.get(
                "id_inventario",
                a["iid"],
            )
        )
        ==
        a["iid"],
        (
            "Análise legítima apresentou "
            f"ID_Inventario inesperado: {controle}"
        ),
    )


def test_decisao_nao_aceita_rodada_de_outro_inventario(
    pair,
):
    a = pair["a"]
    b = pair["b"]

    # Usa item do próprio A, porém tenta gravar a decisão com ID_Rodada de B.
    # Isso isola exatamente o vínculo Inventário <-> Rodada.
    expect_denied(
        lambda: decision_raw(
            a["iid"],
            b["rid"],
            a["item"],
        ),
        (
            "Registrar decisão no Inventário A "
            "usando Rodada B"
        ),
    )


def test_sessao_inexistente_nao_pode_receber_contagem(
    pair,
):
    a = pair["a"]

    item = a["item"]

    # ID propositalmente fora da faixa normal sem depender de consulta SQL.
    sid_falso = 2_000_000_000

    expect_denied(
        lambda: count_raw(
            sid_falso,
            str(item["codigo"]),
            item.get("lote") or "",
            item["_q"],
        ),
        (
            "Registrar contagem em sessão "
            "inexistente/adulterada"
        ),
    )


def test_tenant_real_opcional():
    if not (
        CLIENTE2_LOGIN
        and CLIENTE2_PASSWORD
        and CLIENTE2_ID is not None
    ):
        print(
            "[INFO] Isolamento real entre tenants não executado: "
            "defina SGI_CLIENTE2_LOGIN, SGI_CLIENTE2_PASSWORD "
            "e SGI_CLIENTE2_ID para habilitar."
        )
        return

    api2 = API()

    api2.login_with(
        CLIENTE2_LOGIN,
        CLIENTE2_PASSWORD,
    )

    # Cria um inventário pelo usuário principal para o ClienteId principal.
    inv_a = create_rotativo(
        "TENANT1",
    )

    iid_a = int(
        inv_a["id_inventario"]
    )

    # O segundo usuário não pode operar objeto do primeiro tenant.
    expect_denied(
        lambda: api2.request(
            "POST",
            (
                f"/inventarios/"
                f"{iid_a}"
                f"/escopo/localizacoes"
            ),
            {
                "localizacoes": [
                    LOCALIZACAO
                ],
            },
        ),
        (
            "Usuário do Cliente 2 acessando "
            "inventário do Cliente 1"
        ),
    )

    print(
        "[PASS-EXTRA] Isolamento real entre tenants "
        "validado com segunda credencial."
    )


# ======================================================================
# RUNNER
# ======================================================================

def run_case(
    name: str,
    fn,
):
    try:
        fn()
        R.ok(name)

    except Exception as exc:
        R.fail(
            name,
            exc,
        )


def main():

    print()
    print("=" * 76)
    print(
        "SGI - ESTÁGIO 15 | "
        "SEGURANÇA, PERMISSÕES E ISOLAMENTO"
    )
    print("=" * 76)

    run_case(
        "Autenticação obrigatória nos endpoints protegidos",
        test_autenticacao_obrigatoria,
    )

    run_case(
        "Token inválido é rejeitado",
        test_token_invalido,
    )

    pair_holder = {}

    def preparar():
        api.login()
        pair_holder["data"] = prepare_pair()

    run_case(
        "Autenticação e preparação dos inventários isolados",
        preparar,
    )

    if "data" in pair_holder:

        pair = pair_holder["data"]

        run_case(
            "Rodada de outro inventário não inicia sessão",
            lambda: (
                test_rodada_de_outro_inventario_na_sessao(
                    pair
                )
            ),
        )

        run_case(
            "Análise não aceita rodada de outro inventário",
            lambda: (
                test_analise_nao_aceita_rodada_de_outro_inventario(
                    pair
                )
            ),
        )

        run_case(
            "Decisão ROTATIVO não aceita rodada de outro inventário",
            lambda: (
                test_decisao_nao_aceita_rodada_de_outro_inventario(
                    pair
                )
            ),
        )

        run_case(
            "Sessão inexistente/adulterada não recebe contagem",
            lambda: (
                test_sessao_inexistente_nao_pode_receber_contagem(
                    pair
                )
            ),
        )

        # O extra não altera o placar obrigatório.
        try:
            test_tenant_real_opcional()
        except Exception as exc:
            R.fail(
                "Isolamento real entre tenants (extra)",
                exc,
            )

    print()
    print("=" * 76)

    total_pass = len(
        R.passed
    )

    total_fail = len(
        R.failed
    )

    print(
        f"PASS: {total_pass} | FAIL: {total_fail}"
    )

    if total_fail == 0:
        print(
            "RESULTADO: APROVADO"
        )
    else:
        print(
            "RESULTADO: REPROVADO"
        )

        for erro in R.failed:
            print(
                f" - {erro}"
            )

    print("=" * 76)

    if total_fail > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
