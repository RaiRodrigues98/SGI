"""
SGI - REGRESSÃO FINAL
=====================

Gate técnico final do núcleo de inventário antes da homologação operacional.

Estratégia
----------
1. Executa a regressão acumulada já existente (base dos estágios anteriores).
2. Executa novamente o guard do inventário OFICIAL.
3. Executa os estágios mais recentes e críticos:
   - Estágio 13: integridade transacional
   - Estágio 14: concorrência real
   - Estágio 15: segurança/RBAC
   - Estágio 16: carga/performance/readiness
4. Gera log completo e resumo final.

O runner NÃO altera banco nem código de produção diretamente.
Cada teste E2E continua responsável por criar seus próprios dados controlados.

Execução
--------
python tests_e2e\\regressao_final_sgi.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


# ======================================================================
# CAMINHOS
# ======================================================================

THIS_FILE = Path(__file__).resolve()
TESTS_DIR = THIS_FILE.parent
PROJECT_ROOT = TESTS_DIR.parent

LOG_DIR = TESTS_DIR / "logs"
LOG_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

TIMESTAMP = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

LOG_FILE = (
    LOG_DIR
    / f"regressao_final_sgi_{TIMESTAMP}.log"
)


# ======================================================================
# CONFIGURAÇÃO
# ======================================================================

BASE_URL = os.getenv(
    "SGI_BASE_URL",
    "http://127.0.0.1:8000",
)

STOP_ON_FAILURE = (
    os.getenv(
        "SGI_REGRESSAO_STOP_ON_FAILURE",
        "false",
    )
    .strip()
    .lower()
    in {
        "1",
        "true",
        "yes",
        "sim",
    }
)


# ======================================================================
# GRUPOS
# ======================================================================

@dataclass
class Group:
    name: str
    candidates: list[str]
    required: bool = True


GROUPS = [
    Group(
        name="Regressão acumulada base",
        candidates=[
            "regressao_completa.py",
            "teste_regressao_completa.py",
            "regressao_automatizada.py",
            "regressao_automatica.py",
        ],
    ),
    Group(
        name="OFICIAL - Guard de regressão",
        candidates=[
            "teste_oficial_estagio10.py",
        ],
    ),
    Group(
        name="Estágio 13 - Integridade transacional",
        candidates=[
            "teste_rotativo_estagio13.py",
            "teste_rotativo_estagio13_corrigido.py",
        ],
    ),
    Group(
        name="Estágio 14 - Concorrência real",
        candidates=[
            "teste_rotativo_estagio14.py",
            "teste_rotativo_estagio14_corrigido.py",
        ],
    ),
    Group(
        name="Estágio 15 - Segurança e RBAC",
        candidates=[
            "teste_rotativo_estagio15.py",
        ],
    ),
    Group(
        name="Estágio 16 - Performance e readiness",
        candidates=[
            "teste_rotativo_estagio16.py",
            "teste_rotativo_estagio16_corrigido.py",
        ],
    ),
]


# ======================================================================
# RESULTADOS
# ======================================================================

@dataclass
class Result:
    group: str
    file: str | None
    status: str
    returncode: int | None
    duration: float
    output: str


RESULTS: list[Result] = []


# ======================================================================
# HELPERS
# ======================================================================

def line(
    char: str = "=",
    width: int = 88,
):
    print(
        char * width
    )


def log(
    text: str = "",
):
    print(text)

    with LOG_FILE.open(
        "a",
        encoding="utf-8",
    ) as fp:
        fp.write(
            text + "\n"
        )


def resolve_file(
    group: Group,
) -> Path | None:

    for name in group.candidates:

        path = TESTS_DIR / name

        if (
            path.exists()
            and
            path.resolve() != THIS_FILE
        ):
            return path

    return None


def extract_result_line(
    output: str,
) -> str | None:

    lines = [
        ln.strip()
        for ln in output.splitlines()
        if ln.strip()
    ]

    for ln in reversed(lines):

        upper = ln.upper()

        if (
            "RESULTADO" in upper
            or
            "APROVADO" in upper
            or
            "REPROVADO" in upper
        ):
            return ln

    return None


def run_test(
    group: Group,
) -> Result:

    path = resolve_file(
        group
    )

    if path is None:

        return Result(
            group=group.name,
            file=None,
            status=(
                "FAIL"
                if group.required
                else "SKIP"
            ),
            returncode=None,
            duration=0.0,
            output=(
                "Nenhum arquivo candidato encontrado. "
                f"Candidatos: {group.candidates}"
            ),
        )

    started = time.perf_counter()

    env = os.environ.copy()

    proc = subprocess.run(
        [
            sys.executable,
            str(path),
        ],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    duration = (
        time.perf_counter()
        - started
    )

    stdout = (
        proc.stdout
        or ""
    )

    stderr = (
        proc.stderr
        or ""
    )

    output = stdout

    if stderr.strip():

        if output and not output.endswith(
            "\n"
        ):
            output += "\n"

        output += (
            "\n[STDERR]\n"
            + stderr
        )

    status = (
        "PASS"
        if proc.returncode == 0
        else "FAIL"
    )

    return Result(
        group=group.name,
        file=path.name,
        status=status,
        returncode=proc.returncode,
        duration=duration,
        output=output,
    )


def print_result(
    result: Result,
):

    summary = extract_result_line(
        result.output
    )

    tag = (
        "[PASS]"
        if result.status == "PASS"
        else
        "[SKIP]"
        if result.status == "SKIP"
        else
        "[FAIL]"
    )

    filename = (
        result.file
        or "ARQUIVO NÃO ENCONTRADO"
    )

    log(
        (
            f"{tag} {result.group} "
            f"({filename}) "
            f"- {result.duration:.2f}s"
        )
    )

    if summary:
        log(
            f"       {summary}"
        )

    if result.status == "FAIL":

        log("")
        log(
            "------- SAÍDA DO TESTE REPROVADO -------"
        )

        for ln in result.output.rstrip().splitlines():
            log(
                ln
            )

        log(
            "------- FIM DA SAÍDA -------"
        )
        log("")


# ======================================================================
# MAIN
# ======================================================================

def main():

    LOG_FILE.write_text(
        "",
        encoding="utf-8",
    )

    line()
    log(
        "SGI - REGRESSÃO FINAL DO NÚCLEO DE INVENTÁRIO"
    )
    log(
        f"API: {BASE_URL}"
    )
    log(
        f"Projeto: {PROJECT_ROOT}"
    )
    log(
        f"Python: {sys.executable}"
    )
    log(
        f"Log: {LOG_FILE}"
    )
    line()

    started_all = time.perf_counter()

    for group in GROUPS:

        result = run_test(
            group
        )

        RESULTS.append(
            result
        )

        print_result(
            result
        )

        if (
            STOP_ON_FAILURE
            and
            result.status == "FAIL"
        ):
            log(
                "[INFO] Execução interrompida por "
                "SGI_REGRESSAO_STOP_ON_FAILURE=true."
            )
            break

    total_duration = (
        time.perf_counter()
        - started_all
    )

    passed = [
        r
        for r in RESULTS
        if r.status == "PASS"
    ]

    failed = [
        r
        for r in RESULTS
        if r.status == "FAIL"
    ]

    skipped = [
        r
        for r in RESULTS
        if r.status == "SKIP"
    ]

    line()
    log(
        "RESUMO FINAL"
    )
    line("-")

    for result in RESULTS:

        icon = (
            "OK"
            if result.status == "PASS"
            else
            "SKIP"
            if result.status == "SKIP"
            else
            "FALHOU"
        )

        log(
            f"{icon:6} | "
            f"{result.group:42} | "
            f"{result.duration:7.2f}s"
        )

    line("-")

    log(
        (
            f"PASS: {len(passed)} | "
            f"FAIL: {len(failed)} | "
            f"SKIP: {len(skipped)} | "
            f"DURAÇÃO TOTAL: {total_duration:.2f}s"
        )
    )

    if not failed:

        line()
        log(
            "RESULTADO FINAL: APROVADO PARA HOMOLOGAÇÃO CONTROLADA"
        )
        line()

        return

    line()
    log(
        "RESULTADO FINAL: REPROVADO"
    )
    log(
        "O núcleo não deve avançar para homologação "
        "até a(s) falha(s) serem classificadas e corrigidas."
    )
    line()

    raise SystemExit(1)


if __name__ == "__main__":
    main()
