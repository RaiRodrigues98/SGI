"""
SGI - ESTÁGIO 16
CARGA, PERFORMANCE E READINESS DE PRODUÇÃO
==========================================

Objetivo
--------
Validar o núcleo do SGI antes da homologação operacional controlada:

1. autenticação funcional em modo protegido;
2. AUTH_ENABLED=True;
3. todas as permissões exigidas pelos routers existem e estão ativas no banco;
4. preparação E2E de um inventário ROTATIVO real;
5. estabilidade de leitura sequencial;
6. estabilidade sob carga concorrente de leitura;
7. ausência de HTTP 5xx durante a carga;
8. integridade da análise antes/depois da carga;
9. latência P95 dentro de limite configurável.

Este teste NÃO substitui teste de capacidade de infraestrutura em produção.
Ele é um gate técnico de readiness do núcleo da aplicação.

Variáveis
---------
SGI_BASE_URL
SGI_LOGIN
SGI_PASSWORD
SGI_CLIENTE_ID
SGI_CLIENTE
SGI_ARMAZEM
SGI_LOCALIZACAO
SGI_TIMEOUT

Parâmetros de carga opcionais
-----------------------------
SGI_C16_SEQ_REQUESTS      default: 20
SGI_C16_CONC_REQUESTS     default: 40
SGI_C16_WORKERS           default: 8
SGI_C16_MAX_P95_SEQ       default: 2.0   segundos
SGI_C16_MAX_P95_CONC      default: 3.0   segundos

Execução
--------
python tests_e2e\\teste_rotativo_estagio16.py
"""

from __future__ import annotations

import json
import math
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ======================================================================
# RAIZ DO PROJETO
#
# Ao executar:
# python tests_e2e\\teste_rotativo_estagio16.py
#
# o Python pode manter apenas tests_e2e no sys.path. Isso impede imports
# do próprio SGI, como dependencies.auth e database.
# ======================================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


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

SEQ_REQUESTS = max(
    5,
    int(
        os.getenv(
            "SGI_C16_SEQ_REQUESTS",
            "20",
        )
    ),
)

CONC_REQUESTS = max(
    10,
    int(
        os.getenv(
            "SGI_C16_CONC_REQUESTS",
            "40",
        )
    ),
)

WORKERS = max(
    2,
    int(
        os.getenv(
            "SGI_C16_WORKERS",
            "8",
        )
    ),
)

MAX_P95_SEQ = float(
    os.getenv(
        "SGI_C16_MAX_P95_SEQ",
        "2.0",
    )
)

MAX_P95_CONC = float(
    os.getenv(
        "SGI_C16_MAX_P95_CONC",
        "3.0",
    )
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

            raise ApiError(
                error.code,
                data,
                method,
                path,
            )

    def login(self):
        if not LOGIN or not PASSWORD:
            raise RuntimeError(
                "Defina SGI_LOGIN e SGI_PASSWORD antes de executar."
            )

        retorno = self.request(
            "POST",
            "/auth/login",
            {
                "login": LOGIN,
                "senha": PASSWORD,
            },
        )

        self.token = retorno[
            "access_token"
        ]

        return retorno


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


def assert_c16(
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
        f"E2E-C16-{tag}-{sufixo}"
    )[:30]


def percentile(
    values: list[float],
    pct: float,
) -> float:

    if not values:
        return 0.0

    ordered = sorted(values)

    idx = max(
        0,
        min(
            len(ordered) - 1,
            math.ceil(
                (pct / 100.0)
                * len(ordered)
            ) - 1,
        ),
    )

    return ordered[idx]


def print_metrics(
    title: str,
    tempos: list[float],
):
    if not tempos:
        return

    print(
        f"       {title}: "
        f"n={len(tempos)} | "
        f"média={statistics.mean(tempos):.3f}s | "
        f"p50={percentile(tempos, 50):.3f}s | "
        f"p95={percentile(tempos, 95):.3f}s | "
        f"máx={max(tempos):.3f}s"
    )


# ======================================================================
# HELPERS
# ======================================================================

def create_rotativo() -> dict:
    return api.request(
        "POST",
        "/inventarios",
        {
            "codigo_inventario":
                unique_code("LOAD"),

            "tipo":
                "ROTATIVO",

            "cliente_id":
                CLIENTE_ID,

            "cliente":
                CLIENTE,

            "descricao":
                "Estagio 16 - carga e readiness",

            "armazem":
                ARMAZEM,
        },
    )


def add_scope(
    iid: int,
):
    return api.request(
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
):
    return api.request(
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
):
    return api.request(
        "GET",
        (
            f"/inventarios/"
            f"{iid}"
            f"/rodadas/"
            f"{rid}"
            f"/analise"
        ),
    )


def normalizar_analise(
    data: dict,
) -> dict:

    resumo = data.get(
        "resumo",
        {},
    )

    itens = data.get(
        "itens",
        [],
    )

    chaves = []

    for item in itens:
        chaves.append(
            (
                str(
                    item.get(
                        "localizacao",
                        "",
                    )
                ).strip().upper(),

                str(
                    item.get(
                        "codigo",
                        "",
                    )
                ).strip(),

                str(
                    item.get(
                        "lote",
                        "",
                    )
                    or ""
                ).strip(),

                str(
                    item.get(
                        "status",
                        "",
                    )
                ).strip().upper(),
            )
        )

    return {
        "id_inventario":
            data.get(
                "id_inventario"
            ),

        "id_rodada":
            data.get(
                "id_rodada"
            ),

        "numero_rodada":
            data.get(
                "numero_rodada"
            ),

        "resumo":
            resumo,

        "itens":
            sorted(chaves),
    }


def timed_call(
    fn,
):
    ini = time.perf_counter()

    try:
        value = fn()

        return {
            "ok": True,
            "status": 200,
            "value": value,
            "elapsed":
                time.perf_counter()
                - ini,
            "error": None,
        }

    except ApiError as exc:
        return {
            "ok": False,
            "status": exc.status,
            "value": None,
            "elapsed":
                time.perf_counter()
                - ini,
            "error": str(exc),
        }

    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "value": None,
            "elapsed":
                time.perf_counter()
                - ini,
            "error": repr(exc),
        }


# ======================================================================
# TESTE 1 - AUTENTICAÇÃO
# ======================================================================

def test_autenticacao():
    retorno = api.login()

    assert_c16(
        bool(
            retorno.get(
                "access_token"
            )
        ),
        (
            "Login não retornou access_token."
        ),
    )


# ======================================================================
# TESTE 2 - AUTH_ENABLED
# ======================================================================

def test_auth_enabled():

    # Valida o comportamento EFETIVO da API em execução.
    # Isso é mais confiável que importar AUTH_ENABLED no processo do teste,
    # pois o servidor pode ter sido iniciado em outro terminal/processo com
    # variáveis de ambiente próprias.
    sem_token = API()

    try:
        sem_token.request(
            "GET",
            (
                "/inventarios/"
                "2147483647"
                "/rodadas/"
                "2147483647"
                "/analise"
            ),
        )

    except ApiError as exc:

        assert_c16(
            exc.status == 401,
            (
                "Endpoint protegido sem token deveria retornar HTTP 401, "
                f"mas retornou HTTP {exc.status}: {exc.data}. "
                "Isso pode indicar AUTH_ENABLED=False ou proteção "
                "inconsistente no servidor em execução."
            ),
        )

        return

    raise AssertionError(
        (
            "Endpoint protegido respondeu sem autenticação. "
            "O servidor em execução não está em modo protegido."
        )
    )


# ======================================================================
# TESTE 3 - CATÁLOGO DE PERMISSÕES
# ======================================================================

def test_catalogo_permissoes():

    raiz = PROJECT_ROOT

    routers = raiz / "routers"

    assert_c16(
        routers.exists(),
        (
            f"Pasta de routers não encontrada: {routers}"
        ),
    )

    pattern = re.compile(
        r'exigir_permissao\s*\(\s*["\']([^"\']+)["\']\s*\)',
        flags=re.MULTILINE,
    )

    exigidas = set()

    for arquivo in routers.glob(
        "*.py"
    ):

        conteudo = arquivo.read_text(
            encoding="utf-8",
            errors="ignore",
        )

        for codigo in pattern.findall(
            conteudo
        ):
            codigo = (
                codigo
                .strip()
                .upper()
            )

            if codigo:
                exigidas.add(
                    codigo
                )

    assert_c16(
        exigidas,
        (
            "Nenhuma chamada exigir_permissao(...) "
            "foi identificada nos routers."
        ),
    )

    try:
        from database import get_connection
    except Exception as exc:
        raise AssertionError(
            (
                "Não foi possível importar database.get_connection "
                f"para auditar permissões: {exc}"
            )
        )

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                Codigo,
                Ativo

            FROM dbo.Permissoes
            """
        )

        cadastradas = {
            str(
                linha.Codigo
            ).strip().upper():
                bool(
                    linha.Ativo
                )
            for linha in cursor.fetchall()
        }

    finally:
        if cursor:
            cursor.close()

        if conn:
            conn.close()

    ausentes = sorted(
        codigo
        for codigo in exigidas
        if codigo not in cadastradas
    )

    inativas = sorted(
        codigo
        for codigo in exigidas
        if (
            codigo in cadastradas
            and
            not cadastradas[codigo]
        )
    )

    assert_c16(
        not ausentes,
        (
            "Permissões exigidas pelo código não existem "
            f"em dbo.Permissoes: {ausentes}"
        ),
    )

    assert_c16(
        not inativas,
        (
            "Permissões exigidas pelo código estão inativas "
            f"em dbo.Permissoes: {inativas}"
        ),
    )

    print(
        f"       Permissões auditadas: {len(exigidas)}"
    )


# ======================================================================
# TESTE 4 - PREPARAÇÃO E2E
# ======================================================================

CTX = {}


def test_preparacao():

    inv = create_rotativo()

    iid = int(
        inv["id_inventario"]
    )

    rid = int(
        inv["id_rodada"]
    )

    add_scope(
        iid
    )

    snapshot(
        iid
    )

    baseline = analysis(
        iid,
        rid,
    )

    assert_c16(
        isinstance(
            baseline.get(
                "itens",
                []
            ),
            list,
        ),
        (
            "A análise baseline não retornou lista de itens."
        ),
    )

    CTX.update(
        {
            "iid": iid,
            "rid": rid,
            "baseline":
                normalizar_analise(
                    baseline
                ),
        }
    )

    print(
        f"       Inventário: {iid} | Rodada: {rid} | "
        f"Itens baseline: {len(baseline.get('itens', []))}"
    )


# ======================================================================
# TESTE 5 - CARGA SEQUENCIAL
# ======================================================================

SEQ_METRICS = {}


def test_carga_sequencial():

    iid = CTX["iid"]
    rid = CTX["rid"]

    resultados = []

    for _ in range(
        SEQ_REQUESTS
    ):

        resultados.append(
            timed_call(
                lambda: analysis(
                    iid,
                    rid,
                )
            )
        )

    falhas = [
        r
        for r in resultados
        if not r["ok"]
    ]

    erros_5xx = [
        r
        for r in resultados
        if (
            r["status"] is not None
            and
            r["status"] >= 500
        )
    ]

    assert_c16(
        not erros_5xx,
        (
            "Carga sequencial produziu HTTP 5xx: "
            f"{erros_5xx[:3]}"
        ),
    )

    assert_c16(
        not falhas,
        (
            "Carga sequencial apresentou falhas: "
            f"{falhas[:3]}"
        ),
    )

    tempos = [
        r["elapsed"]
        for r in resultados
    ]

    p95 = percentile(
        tempos,
        95,
    )

    SEQ_METRICS[
        "p95"
    ] = p95

    print_metrics(
        "Sequencial",
        tempos,
    )

    assert_c16(
        p95 <= MAX_P95_SEQ,
        (
            f"P95 sequencial {p95:.3f}s excedeu "
            f"o limite configurado de {MAX_P95_SEQ:.3f}s."
        ),
    )


# ======================================================================
# TESTE 6 - CARGA CONCORRENTE
# ======================================================================

CONC_METRICS = {}


def test_carga_concorrente():

    iid = CTX["iid"]
    rid = CTX["rid"]

    def executar():
        # Cada chamada usa a API stateless com o mesmo JWT.
        # urllib cria uma conexão independente por chamada.
        return timed_call(
            lambda: analysis(
                iid,
                rid,
            )
        )

    resultados = []

    with ThreadPoolExecutor(
        max_workers=WORKERS
    ) as pool:

        futures = [
            pool.submit(
                executar
            )
            for _ in range(
                CONC_REQUESTS
            )
        ]

        for future in as_completed(
            futures
        ):
            resultados.append(
                future.result()
            )

    erros_5xx = [
        r
        for r in resultados
        if (
            r["status"] is not None
            and
            r["status"] >= 500
        )
    ]

    outras_falhas = [
        r
        for r in resultados
        if (
            not r["ok"]
            and
            r not in erros_5xx
        )
    ]

    assert_c16(
        not erros_5xx,
        (
            "Carga concorrente produziu HTTP 5xx: "
            f"{erros_5xx[:5]}"
        ),
    )

    assert_c16(
        not outras_falhas,
        (
            "Carga concorrente apresentou falhas: "
            f"{outras_falhas[:5]}"
        ),
    )

    tempos = [
        r["elapsed"]
        for r in resultados
    ]

    p95 = percentile(
        tempos,
        95,
    )

    CONC_METRICS[
        "p95"
    ] = p95

    print_metrics(
        (
            f"Concorrente "
            f"({WORKERS} workers)"
        ),
        tempos,
    )

    assert_c16(
        p95 <= MAX_P95_CONC,
        (
            f"P95 concorrente {p95:.3f}s excedeu "
            f"o limite configurado de {MAX_P95_CONC:.3f}s."
        ),
    )


# ======================================================================
# TESTE 7 - INTEGRIDADE APÓS CARGA
# ======================================================================

def test_integridade_pos_carga():

    iid = CTX["iid"]
    rid = CTX["rid"]

    depois = normalizar_analise(
        analysis(
            iid,
            rid,
        )
    )

    baseline = CTX[
        "baseline"
    ]

    assert_c16(
        depois == baseline,
        (
            "A análise mudou após carga exclusivamente de leitura. "
            "Isso sugere efeito colateral indevido ou inconsistência "
            "de leitura.\n"
            f"Antes: {baseline}\n"
            f"Depois: {depois}"
        ),
    )


# ======================================================================
# TESTE 8 - READINESS RESUMIDO
# ======================================================================

def test_readiness_resumido():

    assert_c16(
        "p95" in SEQ_METRICS,
        "Métrica P95 sequencial não foi produzida.",
    )

    assert_c16(
        "p95" in CONC_METRICS,
        "Métrica P95 concorrente não foi produzida.",
    )

    print(
        "       Readiness técnico:"
    )
    print(
        "       - autenticação habilitada"
    )
    print(
        "       - catálogo RBAC consistente"
    )
    print(
        "       - leitura sequencial estável"
    )
    print(
        "       - leitura concorrente estável"
    )
    print(
        "       - nenhum HTTP 5xx aceito"
    )
    print(
        "       - integridade preservada após carga"
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
    print("=" * 78)
    print(
        "SGI - ESTÁGIO 16 | "
        "CARGA, PERFORMANCE E READINESS DE PRODUÇÃO"
    )
    print(
        f"API: {BASE} | Cliente: {CLIENTE_ID} | "
        f"Armazém: {ARMAZEM} | Local: {LOCALIZACAO}"
    )
    print(
        f"Carga: seq={SEQ_REQUESTS} | "
        f"conc={CONC_REQUESTS} | workers={WORKERS}"
    )
    print(
        f"Limites P95: seq<={MAX_P95_SEQ:.2f}s | "
        f"conc<={MAX_P95_CONC:.2f}s"
    )
    print("=" * 78)

    run_case(
        "Autenticação",
        test_autenticacao,
    )

    run_case(
        "API em execução está com autenticação obrigatória",
        test_auth_enabled,
    )

    run_case(
        "Catálogo RBAC cobre todas as permissões exigidas pelos routers",
        test_catalogo_permissoes,
    )

    run_case(
        "Preparação E2E para carga",
        test_preparacao,
    )

    if (
        "iid" in CTX
        and
        "rid" in CTX
    ):

        run_case(
            "Carga sequencial sem falhas e dentro do P95",
            test_carga_sequencial,
        )

        run_case(
            "Carga concorrente sem 5xx e dentro do P95",
            test_carga_concorrente,
        )

        run_case(
            "Integridade preservada após carga",
            test_integridade_pos_carga,
        )

        if (
            "p95" in SEQ_METRICS
            and
            "p95" in CONC_METRICS
            and
            len(R.failed) == 0
        ):
            run_case(
                "Readiness técnico resumido",
                test_readiness_resumido,
            )

    print()
    print("=" * 78)

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

    print("=" * 78)

    if total_fail > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
