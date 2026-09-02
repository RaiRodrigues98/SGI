"""
SGI - REGRESSÃO COMPLETA
=======================

Executa, em sequência, todos os testes E2E consolidados do projeto SGI.

Objetivos:
- validar o fluxo ROTATIVO;
- validar proteções e estados-limite;
- validar os Estágios 3 a 9;
- validar a regressão do inventário OFICIAL (Estágio 10);
- validar coexistência e isolamento ROTATIVO x OFICIAL (Estágio 12);
- continuar executando os demais testes mesmo quando um deles falhar;
- apresentar um resumo único ao final.

Uso:
    python tests_e2e\regressao_completa.py

Variáveis de ambiente utilizadas pelos testes filhos:
    SGI_BASE_URL
    SGI_LOGIN
    SGI_PASSWORD
    SGI_CLIENTE_ID
    SGI_CLIENTE
    SGI_ARMAZEM
    SGI_LOCALIZACAO
    SGI_TIMEOUT

Importante:
- Este arquivo NÃO altera banco diretamente.
- Cada teste continua responsável pela criação dos próprios dados E2E.
- O executor usa o mesmo interpretador Python da execução atual.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


# ============================================================
# CONFIGURAÇÃO
# ============================================================

PASTA_TESTES = Path(__file__).resolve().parent

TIMEOUT_TESTE = int(
    os.getenv(
        "SGI_REGRESSAO_TIMEOUT",
        "600"
    )
)

MOSTRAR_SAIDA_COMPLETA = (
    os.getenv(
        "SGI_REGRESSAO_VERBOSE",
        "1"
    ).strip().lower()
    not in
    {
        "0",
        "false",
        "nao",
        "não",
        "no",
    }
)


# ============================================================
# ORDEM OFICIAL DA SUÍTE
# ============================================================

# Cada item pode possuir alternativas.
# A PRIMEIRA alternativa existente será executada.
#
# Isso evita executar simultaneamente:
# - versão antiga;
# - versão corrigida;
# - versão substituída do mesmo estágio.

GRUPOS_TESTES = [
    {
        "nome": "ROTATIVO - Fluxo E2E",
        "alternativas": [
            "teste_rotativo_e2e_v2.py",
            "teste_rotativo_e2e.py",
        ],
    },
    {
        "nome": "ROTATIVO - Proteções",
        "alternativas": [
            "teste_rotativo_protecoes.py",
        ],
    },
    {
        "nome": "ESTÁGIO 3 - Estados limite e consistência",
        "alternativas": [
            "teste_rotativo_estagio3.py",
        ],
    },
    {
        "nome": "ESTÁGIO 4",
        "alternativas": [
            "teste_rotativo_estagio4.py",
        ],
    },
    {
        "nome": "ESTÁGIO 5",
        "alternativas": [
            "teste_rotativo_estagio5.py",
        ],
    },
    {
        "nome": "ESTÁGIO 6",
        "alternativas": [
            "teste_rotativo_estagio6.py",
        ],
    },
    {
        "nome": "ESTÁGIO 7",
        "alternativas": [
            "teste_rotativo_estagio7_corrigido.py",
            "teste_rotativo_estagio7.py",
        ],
    },
    {
        "nome": "ESTÁGIO 8",
        "alternativas": [
            "teste_rotativo_estagio8.py",
        ],
    },
    {
        "nome": "ESTÁGIO 9",
        "alternativas": [
            "teste_rotativo_estagio9_corrigido.py",
            "teste_rotativo_estagio9.py",
        ],
    },
    {
        "nome": "ESTÁGIO 10 - Regressão OFICIAL",
        "alternativas": [
            "teste_oficial_estagio10.py",
        ],
    },
    {
        "nome": "ESTÁGIO 12 - Coexistência ROTATIVO x OFICIAL",
        "alternativas": [
            "teste_estagio12_coexistencia.py",
        ],
    },
]


# ============================================================
# MODELOS
# ============================================================

@dataclass
class ResultadoTeste:
    nome: str
    arquivo: str | None
    status: str
    returncode: int | None
    duracao_segundos: float
    saida: str = ""
    detalhe: str = ""


# ============================================================
# UTILITÁRIOS
# ============================================================

def linha(
    caractere: str = "=",
    tamanho: int = 78
):
    print(
        caractere
        *
        tamanho
    )


def formatar_tempo(
    segundos: float
) -> str:

    segundos = max(
        float(
            segundos
        ),
        0.0
    )

    if segundos < 60:

        return (
            f"{segundos:.1f}s"
        )

    minutos = int(
        segundos
        //
        60
    )

    restante = (
        segundos
        %
        60
    )

    return (
        f"{minutos}m "
        f"{restante:.1f}s"
    )


def encontrar_arquivo(
    alternativas: list[str]
) -> Path | None:

    for nome in alternativas:

        caminho = (
            PASTA_TESTES
            /
            nome
        )

        if caminho.is_file():
            return caminho

    return None


def limpar_ansi(
    texto: str
) -> str:

    return re.sub(
        r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])",
        "",
        texto,
    )


def detectar_resultado_textual(
    saida: str
) -> str | None:

    texto = limpar_ansi(
        saida
    ).upper()

    # Dá prioridade explícita à reprovação.
    if (
        "RESULTADO: REPROVADO"
        in texto
    ):
        return "REPROVADO"

    if (
        "RESULTADO GERAL: REPROVADO"
        in texto
    ):
        return "REPROVADO"

    if (
        "RESULTADO: APROVADO"
        in texto
    ):
        return "APROVADO"

    if (
        "RESULTADO GERAL: APROVADO"
        in texto
    ):
        return "APROVADO"

    return None


def executar_teste(
    nome: str,
    arquivo: Path
) -> ResultadoTeste:

    print()
    linha()
    print(
        f"EXECUTANDO: {nome}"
    )
    print(
        f"ARQUIVO:   {arquivo.name}"
    )
    linha()

    inicio = time.perf_counter()

    try:

        processo = subprocess.run(
            [
                sys.executable,
                str(
                    arquivo
                ),
            ],
            cwd=str(
                PASTA_TESTES.parent
            ),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_TESTE,
        )

        duracao = (
            time.perf_counter()
            -
            inicio
        )

        saida = (
            (
                processo.stdout
                or
                ""
            )
            +
            (
                "\n"
                +
                processo.stderr
                if processo.stderr
                else
                ""
            )
        ).strip()

        if (
            MOSTRAR_SAIDA_COMPLETA
            and
            saida
        ):

            print(
                saida
            )

        textual = (
            detectar_resultado_textual(
                saida
            )
        )

        # Critério principal: código de saída.
        #
        # Critério adicional:
        # se o teste imprimir explicitamente REPROVADO,
        # tratamos como falha mesmo que por algum erro legado
        # ele retorne exit code 0.
        if (
            processo.returncode
            ==
            0
            and
            textual
            !=
            "REPROVADO"
        ):

            status = "APROVADO"

            detalhe = (
                "Processo finalizado "
                "com código 0."
            )

        else:

            status = "REPROVADO"

            detalhe = (
                f"Código de saída: "
                f"{processo.returncode}"
            )

            if textual:
                detalhe += (
                    f" | Resultado textual: "
                    f"{textual}"
                )

        print()
        print(
            f"[{status}] {nome} "
            f"({formatar_tempo(duracao)})"
        )

        return ResultadoTeste(
            nome=nome,
            arquivo=arquivo.name,
            status=status,
            returncode=processo.returncode,
            duracao_segundos=duracao,
            saida=saida,
            detalhe=detalhe,
        )

    except subprocess.TimeoutExpired as erro:

        duracao = (
            time.perf_counter()
            -
            inicio
        )

        stdout = (
            erro.stdout
            or
            ""
        )

        stderr = (
            erro.stderr
            or
            ""
        )

        if isinstance(
            stdout,
            bytes
        ):
            stdout = stdout.decode(
                "utf-8",
                errors="replace"
            )

        if isinstance(
            stderr,
            bytes
        ):
            stderr = stderr.decode(
                "utf-8",
                errors="replace"
            )

        saida = (
            str(
                stdout
            )
            +
            (
                "\n"
                +
                str(
                    stderr
                )
                if stderr
                else
                ""
            )
        ).strip()

        if (
            MOSTRAR_SAIDA_COMPLETA
            and
            saida
        ):
            print(
                saida
            )

        print()
        print(
            f"[REPROVADO] {nome} "
            f"- TIMEOUT após "
            f"{formatar_tempo(duracao)}"
        )

        return ResultadoTeste(
            nome=nome,
            arquivo=arquivo.name,
            status="REPROVADO",
            returncode=None,
            duracao_segundos=duracao,
            saida=saida,
            detalhe=(
                "Tempo limite excedido. "
                f"Limite configurado: "
                f"{TIMEOUT_TESTE}s."
            ),
        )

    except Exception as erro:

        duracao = (
            time.perf_counter()
            -
            inicio
        )

        print()
        print(
            f"[REPROVADO] {nome}: "
            f"{erro}"
        )

        return ResultadoTeste(
            nome=nome,
            arquivo=arquivo.name,
            status="REPROVADO",
            returncode=None,
            duracao_segundos=duracao,
            detalhe=str(
                erro
            ),
        )


# ============================================================
# DESCOBERTA DA SUÍTE
# ============================================================

def montar_suite() -> list[
    tuple[
        str,
        Path | None
    ]
]:

    suite = []

    for grupo in GRUPOS_TESTES:

        arquivo = encontrar_arquivo(
            grupo[
                "alternativas"
            ]
        )

        suite.append(
            (
                grupo[
                    "nome"
                ],
                arquivo,
            )
        )

    return suite


# ============================================================
# RESUMO
# ============================================================

def imprimir_resumo(
    resultados: list[ResultadoTeste],
    duracao_total: float
):

    print()
    linha()
    print(
        "SGI - RESUMO DA REGRESSÃO COMPLETA"
    )
    linha()

    largura_nome = max(
        [
            len(
                resultado.nome
            )
            for resultado in resultados
        ]
        +
        [
            len(
                "TESTE"
            )
        ]
    )

    largura_nome = min(
        max(
            largura_nome,
            30
        ),
        52
    )

    print(
        f"{'TESTE':<{largura_nome}}  "
        f"{'STATUS':<10}  "
        f"{'TEMPO':>10}  "
        f"ARQUIVO"
    )

    print(
        "-"
        *
        110
    )

    for resultado in resultados:

        nome = resultado.nome

        if (
            len(
                nome
            )
            >
            largura_nome
        ):

            nome = (
                nome[
                    :
                    largura_nome
                    -
                    3
                ]
                +
                "..."
            )

        arquivo = (
            resultado.arquivo
            or
            "-"
        )

        print(
            f"{nome:<{largura_nome}}  "
            f"{resultado.status:<10}  "
            f"{formatar_tempo(resultado.duracao_segundos):>10}  "
            f"{arquivo}"
        )

    total = len(
        resultados
    )

    aprovados = sum(
        1
        for resultado
        in resultados
        if (
            resultado.status
            ==
            "APROVADO"
        )
    )

    reprovados = sum(
        1
        for resultado
        in resultados
        if (
            resultado.status
            ==
            "REPROVADO"
        )
    )

    ausentes = sum(
        1
        for resultado
        in resultados
        if (
            resultado.status
            ==
            "AUSENTE"
        )
    )

    executados = (
        total
        -
        ausentes
    )

    print()
    print(
        f"TOTAL PREVISTO: {total}"
    )

    print(
        f"EXECUTADOS:     {executados}"
    )

    print(
        f"APROVADOS:      {aprovados}"
    )

    print(
        f"REPROVADOS:     {reprovados}"
    )

    print(
        f"AUSENTES:       {ausentes}"
    )

    print(
        "TEMPO TOTAL:    "
        f"{formatar_tempo(duracao_total)}"
    )

    print()

    # A regressão só é considerada verde quando:
    # - nenhum teste falhou;
    # - nenhum teste previsto está ausente.
    if (
        reprovados
        ==
        0
        and
        ausentes
        ==
        0
        and
        total
        >
        0
    ):

        print(
            "RESULTADO GERAL: APROVADO"
        )

        linha()

        return 0

    print(
        "RESULTADO GERAL: REPROVADO"
    )

    if ausentes:

        print()
        print(
            "ATENÇÃO: existem arquivos "
            "de teste previstos que não "
            "foram encontrados."
        )

    if reprovados:

        print()
        print(
            "FALHAS:"
        )

        for resultado in resultados:

            if (
                resultado.status
                !=
                "REPROVADO"
            ):
                continue

            print(
                f" - {resultado.nome}: "
                f"{resultado.detalhe}"
            )

    linha()

    return 1


# ============================================================
# MAIN
# ============================================================

def main():

    inicio_total = (
        time.perf_counter()
    )

    print()
    linha()
    print(
        "SGI - REGRESSÃO COMPLETA DO INVENTÁRIO"
    )
    print(
        f"Python: {sys.executable}"
    )
    print(
        f"Pasta:  {PASTA_TESTES}"
    )
    print(
        f"Timeout por teste: {TIMEOUT_TESTE}s"
    )
    print(
        (
            "Saída completa: "
            f"{'SIM' if MOSTRAR_SAIDA_COMPLETA else 'NÃO'}"
        )
    )
    linha()

    suite = montar_suite()

    resultados: list[
        ResultadoTeste
    ] = []

    for nome, arquivo in suite:

        if arquivo is None:

            alternativas = next(
                grupo[
                    "alternativas"
                ]
                for grupo in GRUPOS_TESTES
                if (
                    grupo[
                        "nome"
                    ]
                    ==
                    nome
                )
            )

            detalhe = (
                "Nenhuma alternativa encontrada: "
                +
                ", ".join(
                    alternativas
                )
            )

            print()
            print(
                f"[AUSENTE] {nome}"
            )

            print(
                f"          {detalhe}"
            )

            resultados.append(
                ResultadoTeste(
                    nome=nome,
                    arquivo=None,
                    status="AUSENTE",
                    returncode=None,
                    duracao_segundos=0.0,
                    detalhe=detalhe,
                )
            )

            continue

        resultado = executar_teste(
            nome,
            arquivo
        )

        resultados.append(
            resultado
        )

    duracao_total = (
        time.perf_counter()
        -
        inicio_total
    )

    codigo_saida = imprimir_resumo(
        resultados,
        duracao_total
    )

    sys.exit(
        codigo_saida
    )


if __name__ == "__main__":
    main()
