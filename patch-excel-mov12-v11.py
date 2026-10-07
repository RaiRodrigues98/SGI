from pathlib import Path
from datetime import datetime
import shutil

ROOT = Path.cwd()

SERVICE = ROOT / "frontend" / "src" / "services" / "indicadoresService.ts"
EXPORTER = ROOT / "frontend" / "src" / "services" / "exportacaoInventarioExcel.ts"

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backup = ROOT / "backups" / f"excel-mov12-v11-{stamp}"
backup.mkdir(parents=True, exist_ok=True)

shutil.copy2(SERVICE, backup / SERVICE.name)
shutil.copy2(EXPORTER, backup / EXPORTER.name)

print(f"[OK] Backup: {backup}")


# ============================================================
# 1. INDICADORES SERVICE
# ============================================================

texto = SERVICE.read_text(encoding="utf-8")

marker = "// MOVIMENTACAO_12_MESES_V1"

if marker not in texto:

    ancora = """export async function buscarResultadoFinalIndicadores(idInventario: number) {
  return apiRequest<ResultadoFinalIndicadores>(
    `/inventarios/${idInventario}/resultado-final`,
  );
}
"""

    if ancora not in texto:
        raise SystemExit(
            "[ERRO] Âncora buscarResultadoFinalIndicadores não encontrada."
        )

    bloco = """
// MOVIMENTACAO_12_MESES_V1
export interface Movimentacao12Meses {
  id_inventario: number;
  codigo_inventario: string;
  cliente_id: number;
  cliente: string;
  armazem: string;

  periodo: {
    inicio: string;
    fim: string;
    dias: number;
  };

  recebimentos: {
    documentos: number;
    linhas: number;
    skus: number;
    quantidade: number;
    valor: number | null;
    linhas_sem_valor: number;
  };

  expedicoes: {
    documentos: number;
    linhas: number;
    skus: number;
    quantidade: number;
    valor: number | null;
    linhas_sem_valor: number;
  };

  total: {
    documentos: number;
    linhas: number;
    quantidade: number;
    valor_movimentado: number | null;
  };
}

export async function buscarMovimentacao12Meses(
  idInventario: number,
) {
  return apiRequest<Movimentacao12Meses>(
    `/inventarios/${idInventario}/indicadores/movimentacao-12-meses`,
  );
}

"""

    texto = texto.replace(
        ancora,
        ancora + bloco,
        1,
    )

    SERVICE.write_text(
        texto,
        encoding="utf-8",
    )

    print("[OK] indicadoresService.ts atualizado.")

else:
    print("[SKIP] indicadoresService.ts já possui MOVIMENTACAO_12_MESES_V1.")


# ============================================================
# 2. EXPORTADOR - IMPORT
# ============================================================

texto = EXPORTER.read_text(encoding="utf-8")

marker_export = "// ANALISE_EXECUTIVA_V11_MOV12"

if marker_export in texto:
    print("[SKIP] Exportador já possui ANALISE_EXECUTIVA_V11_MOV12.")
    raise SystemExit(0)


antigo = """import { buscarResultadoFinalIndicadores } from "@/services/indicadoresService";"""

novo = """import {
  buscarMovimentacao12Meses,
  buscarResultadoFinalIndicadores,
} from "@/services/indicadoresService";"""

if antigo not in texto:
    raise SystemExit(
        "[ERRO] Import de indicadoresService não encontrado."
    )

texto = texto.replace(
    antigo,
    novo,
    1,
)


# ============================================================
# 3. EXPORTADOR - FETCH DA MOVIMENTACAO
# ============================================================

antigo = """  const [gestorResultado, finalResultado] = await Promise.allSettled([
    tipo === "OFICIAL" ? buscarAnaliseGestor(idInventario) : Promise.resolve(null),
    String(detalhe.status).trim().toUpperCase() === "FINALIZADO"
      ? buscarResultadoFinalIndicadores(idInventario)
      : Promise.resolve(null),
  ]);

  const gestor = gestorResultado.status === "fulfilled" ? gestorResultado.value : null;
  const resultadoFinal = finalResultado.status === "fulfilled" ? finalResultado.value : null;
"""

novo = """  // ANALISE_EXECUTIVA_V11_MOV12
  const inventarioFinalizado =
    String(detalhe.status)
      .trim()
      .toUpperCase() === "FINALIZADO";

  const [
    gestorResultado,
    finalResultado,
    movimentacaoResultado,
  ] = await Promise.allSettled([
    tipo === "OFICIAL"
      ? buscarAnaliseGestor(idInventario)
      : Promise.resolve(null),

    inventarioFinalizado
      ? buscarResultadoFinalIndicadores(idInventario)
      : Promise.resolve(null),

    tipo === "OFICIAL" && inventarioFinalizado
      ? buscarMovimentacao12Meses(idInventario)
      : Promise.resolve(null),
  ]);

  const gestor =
    gestorResultado.status === "fulfilled"
      ? gestorResultado.value
      : null;

  const resultadoFinal =
    finalResultado.status === "fulfilled"
      ? finalResultado.value
      : null;

  const movimentacao12Meses =
    movimentacaoResultado.status === "fulfilled"
      ? movimentacaoResultado.value
      : null;
"""

if antigo not in texto:
    raise SystemExit(
        "[ERRO] Bloco Promise.allSettled esperado não encontrado."
    )

texto = texto.replace(
    antigo,
    novo,
    1,
)


# ============================================================
# 4. FINANCEIRO COMPLETO / N-D
# ============================================================

ancora = """    const quantidadeSaldoLiquido =
      quantidadeSobras -
      quantidadeFaltas;

    const valorDivergenciaAbsoluta =
"""

substituto = """    const quantidadeSaldoLiquido =
      quantidadeSobras -
      quantidadeFaltas;

    const financeiroCompleto =
      itensSemCusto === 0;

    const valorDivergenciaAbsoluta =
"""

if ancora not in texto:
    raise SystemExit(
        "[ERRO] Âncora financeiroCompleto não encontrada."
    )

texto = texto.replace(
    ancora,
    substituto,
    1,
)


# ============================================================
# 5. DIVERGENCIA FINANCEIRA KPI
# ============================================================

antigo = """    const divergenciaFinanceiraPercentual =
      valorEstoqueSistema > 0
        ? (
            valorDivergenciaAbsoluta /
            valorEstoqueSistema
          )
        : 0;
"""

novo = """    const divergenciaFinanceiraPercentual =
      financeiroCompleto
        ? (
            valorEstoqueSistema > 0
              ? (
                  valorDivergenciaAbsoluta /
                  valorEstoqueSistema
                )
              : 0
          )
        : null;
"""

if antigo not in texto:
    raise SystemExit(
        "[ERRO] Cálculo divergenciaFinanceiraPercentual não encontrado."
    )

texto = texto.replace(
    antigo,
    novo,
    1,
)


# ============================================================
# 6. KPI DIVERGENCIA FINANCEIRA -> N/D
# ============================================================

antigo = """        label:
          "DIVERGÊNCIA FINANCEIRA",
        valor:
          divergenciaFinanceiraPercentual,
        formato: "0.00%",
"""

novo = """        label:
          "DIVERGÊNCIA FINANCEIRA",
        valor:
          divergenciaFinanceiraPercentual ?? "N/D",
        formato:
          divergenciaFinanceiraPercentual === null
            ? "@"
            : "0.00%",
"""

if antigo not in texto:
    raise SystemExit(
        "[ERRO] Card DIVERGÊNCIA FINANCEIRA não encontrado."
    )

texto = texto.replace(
    antigo,
    novo,
    1,
)


# ============================================================
# 7. HELPER DA TABELA ACEITA N/D
# ============================================================

antigo = """      quantidade: number,
      valor: number,
      destaque:
"""

novo = """      quantidade: number,
      valor: number | string,
      destaque:
"""

if antigo not in texto:
    raise SystemExit(
        "[ERRO] Assinatura preencherLinhaTabela não encontrada."
    )

texto = texto.replace(
    antigo,
    novo,
    1,
)


antigo = """      executiva.getCell(
        linha,
        7,
      ).numFmt =
        'R$ #,##0.00;[Red]-R$ #,##0.00';
"""

novo = """      if (typeof valor === "number") {
        executiva.getCell(
          linha,
          7,
        ).numFmt =
          'R$ #,##0.00;[Red]-R$ #,##0.00';
      } else {
        executiva.getCell(
          linha,
          7,
        ).numFmt = "@";
      }
"""

if antigo not in texto:
    raise SystemExit(
        "[ERRO] Formatação financeira da tabela não encontrada."
    )

texto = texto.replace(
    antigo,
    novo,
    1,
)


# ============================================================
# 8. TROCAR VALORES FINANCEIROS DA TABELA POR N/D
# ============================================================

trocas = {
"""      valorEstoqueSistema,
    );""":
"""      financeiroCompleto
        ? valorEstoqueSistema
        : "N/D",
    );""",

"""      valorInventarioFisico,
    );""":
"""      financeiroCompleto
        ? valorInventarioFisico
        : "N/D",
    );""",

"""      diferencaLiquidaValor,
      "total",
    );""":
"""      financeiroCompleto
        ? diferencaLiquidaValor
        : "N/D",
      "total",
    );""",

"""      valorFaltas,
      "falta",
    );""":
"""      financeiroCompleto
        ? valorFaltas
        : "N/D",
      "falta",
    );""",

"""      valorSobras,
      "sobra",
    );""":
"""      financeiroCompleto
        ? valorSobras
        : "N/D",
      "sobra",
    );""",

"""      valorDivergenciaAbsoluta,
      "total",
    );""":
"""      financeiroCompleto
        ? valorDivergenciaAbsoluta
        : "N/D",
      "total",
    );""",

"""      valorSaldoLiquido,
      "total",
    );""":
"""      financeiroCompleto
        ? valorSaldoLiquido
        : "N/D",
      "total",
    );""",
}

for antigo, novo in trocas.items():
    if antigo not in texto:
        raise SystemExit(
            "[ERRO] Trecho financeiro esperado não encontrado:\n"
            + antigo
        )

    texto = texto.replace(
        antigo,
        novo,
        1,
    )


# ============================================================
# 9. TIPO DOS INDICADORES COMPLEMENTARES
# ============================================================

antigo = """          string,
          number,
          string,
"""

novo = """          string,
          number | string,
          string,
"""

if antigo not in texto:
    raise SystemExit(
        "[ERRO] Tipo indicadoresComplementares não encontrado."
    )

texto = texto.replace(
    antigo,
    novo,
    1,
)


# ============================================================
# 10. BLOCO MOVIMENTACAO 12 MESES
# ============================================================

ancora = """    const linhaNota =
      linhaIndicador + 1;

    executiva.mergeCells(
      linhaNota,
      1,
      linhaNota + 1,
      8,
    );
"""

bloco = """    // ========================================================
    // MOVIMENTAÇÃO DOS ÚLTIMOS 12 MESES
    // ========================================================

    let linhaMovimentacaoFim =
      linhaIndicador - 1;

    if (movimentacao12Meses) {
      const linhaTituloMov =
        linhaIndicador + 1;

      executiva.mergeCells(
        linhaTituloMov,
        1,
        linhaTituloMov,
        8,
      );

      executiva.getCell(
        linhaTituloMov,
        1,
      ).value =
        "MOVIMENTAÇÃO DOS ÚLTIMOS 12 MESES";

      executiva.getCell(
        linhaTituloMov,
        1,
      ).font = {
        bold: true,
        color: {
          argb: `FF${COR_PRIMARIA}`,
        },
        size: 11,
      };

      executiva.getCell(
        linhaTituloMov,
        1,
      ).fill = {
        type: "pattern",
        pattern: "solid",
        fgColor: {
          argb: `FF${COR_SECUNDARIA}`,
        },
      };

      executiva.getCell(
        linhaTituloMov,
        1,
      ).alignment = {
        vertical: "middle",
      };

      const linhaCabecalhoMov =
        linhaTituloMov + 1;

      executiva.mergeCells(
        linhaCabecalhoMov,
        1,
        linhaCabecalhoMov,
        3,
      );

      executiva.mergeCells(
        linhaCabecalhoMov,
        5,
        linhaCabecalhoMov,
        6,
      );

      executiva.mergeCells(
        linhaCabecalhoMov,
        7,
        linhaCabecalhoMov,
        8,
      );

      executiva.getCell(
        linhaCabecalhoMov,
        1,
      ).value = "Operação";

      executiva.getCell(
        linhaCabecalhoMov,
        4,
      ).value = "Documentos";

      executiva.getCell(
        linhaCabecalhoMov,
        5,
      ).value = "Unidades";

      executiva.getCell(
        linhaCabecalhoMov,
        7,
      ).value = "Valor";

      for (
        let coluna = 1;
        coluna <= 8;
        coluna += 1
      ) {
        const celula =
          executiva.getCell(
            linhaCabecalhoMov,
            coluna,
          );

        celula.font = {
          bold: true,
          color: {
            argb: `FF${COR_TEXTO}`,
          },
        };

        celula.fill = {
          type: "pattern",
          pattern: "solid",
          fgColor: {
            argb: `FF${COR_CABECALHO}`,
          },
        };

        celula.alignment = {
          vertical: "middle",
        };

        aplicarBordaExecutiva(
          celula,
        );
      }

      const preencherMovimentacao = (
        linha: number,
        operacao: string,
        documentos: number,
        quantidade: number,
        valor: number | null,
        total = false,
      ) => {
        executiva.mergeCells(
          linha,
          1,
          linha,
          3,
        );

        executiva.mergeCells(
          linha,
          5,
          linha,
          6,
        );

        executiva.mergeCells(
          linha,
          7,
          linha,
          8,
        );

        executiva.getCell(
          linha,
          1,
        ).value = operacao;

        executiva.getCell(
          linha,
          4,
        ).value = documentos;

        executiva.getCell(
          linha,
          5,
        ).value = quantidade;

        executiva.getCell(
          linha,
          7,
        ).value =
          valor === null
            ? "N/D"
            : valor;

        executiva.getCell(
          linha,
          4,
        ).numFmt = "#,##0";

        executiva.getCell(
          linha,
          5,
        ).numFmt = "#,##0.00";

        if (valor !== null) {
          executiva.getCell(
            linha,
            7,
          ).numFmt =
            'R$ #,##0.00;[Red]-R$ #,##0.00';
        }

        for (
          let coluna = 1;
          coluna <= 8;
          coluna += 1
        ) {
          const celula =
            executiva.getCell(
              linha,
              coluna,
            );

          if (total) {
            celula.fill = {
              type: "pattern",
              pattern: "solid",
              fgColor: {
                argb: `FF${COR_SECUNDARIA}`,
              },
            };

            celula.font = {
              bold: true,
              color: {
                argb: `FF${COR_PRIMARIA}`,
              },
            };
          }

          aplicarBordaExecutiva(
            celula,
          );
        }
      };

      preencherMovimentacao(
        linhaCabecalhoMov + 1,
        "Recebimentos",
        movimentacao12Meses
          .recebimentos
          .documentos,
        movimentacao12Meses
          .recebimentos
          .quantidade,
        movimentacao12Meses
          .recebimentos
          .valor,
      );

      preencherMovimentacao(
        linhaCabecalhoMov + 2,
        "Expedições",
        movimentacao12Meses
          .expedicoes
          .documentos,
        movimentacao12Meses
          .expedicoes
          .quantidade,
        movimentacao12Meses
          .expedicoes
          .valor,
      );

      preencherMovimentacao(
        linhaCabecalhoMov + 3,
        "Total movimentado",
        movimentacao12Meses
          .total
          .documentos,
        movimentacao12Meses
          .total
          .quantidade,
        movimentacao12Meses
          .total
          .valor_movimentado,
        true,
      );

      const linhaPeriodoMov =
        linhaCabecalhoMov + 4;

      executiva.mergeCells(
        linhaPeriodoMov,
        1,
        linhaPeriodoMov,
        8,
      );

      const inicioPeriodo =
        new Date(
          movimentacao12Meses
            .periodo
            .inicio,
        );

      const fimPeriodo =
        new Date(
          movimentacao12Meses
            .periodo
            .fim,
        );

      executiva.getCell(
        linhaPeriodoMov,
        1,
      ).value =
        `Período analisado: ${
          inicioPeriodo.toLocaleString(
            "pt-BR",
          )
        } a ${
          fimPeriodo.toLocaleString(
            "pt-BR",
          )
        }`;

      executiva.getCell(
        linhaPeriodoMov,
        1,
      ).font = {
        italic: true,
        color: {
          argb: "FF64748B",
        },
        size: 9,
      };

      linhaMovimentacaoFim =
        linhaPeriodoMov;
    }

    const linhaNota =
      linhaMovimentacaoFim + 2;

    executiva.mergeCells(
      linhaNota,
      1,
      linhaNota + 1,
      8,
    );
"""

if ancora not in texto:
    raise SystemExit(
        "[ERRO] Âncora linhaNota não encontrada."
    )

texto = texto.replace(
    ancora,
    bloco,
    1,
)


# ============================================================
# 11. NOTA SOBRE CUSTO
# ============================================================

antigo = """    if (itensSemCusto > 0) {
      notas.push(
        `${itensSemCusto} item(ns) sem custo foram excluídos dos indicadores financeiros.`,
      );
    }
"""

novo = """    if (itensSemCusto > 0) {
      notas.push(
        `${itensSemCusto} item(ns) sem custo disponível. Os indicadores financeiros do inventário são apresentados como N/D para evitar valores parciais ou incorretos.`,
      );
    }
"""

if antigo not in texto:
    raise SystemExit(
        "[ERRO] Nota de itens sem custo não encontrada."
    )

texto = texto.replace(
    antigo,
    novo,
    1,
)


# ============================================================
# 12. NOTA CASO MOVIMENTACAO NAO ESTEJA DISPONIVEL
# ============================================================

ancora = """    if (
      itensSemResultadoFinal > 0
    ) {
      notas.push(
        `${itensSemResultadoFinal} item(ns) não possuem resultado final e exigem validação.`,
      );
    }
"""

novo = """    if (
      itensSemResultadoFinal > 0
    ) {
      notas.push(
        `${itensSemResultadoFinal} item(ns) não possuem resultado final e exigem validação.`,
      );
    }

    if (!movimentacao12Meses) {
      notas.push(
        "Movimentação dos últimos 12 meses indisponível nesta exportação.",
      );
    }
"""

if ancora not in texto:
    raise SystemExit(
        "[ERRO] Nota de resultado final não encontrada."
    )

texto = texto.replace(
    ancora,
    novo,
    1,
)


EXPORTER.write_text(
    texto,
    encoding="utf-8",
)

print("[OK] exportacaoInventarioExcel.ts atualizado.")
print("")
print("==============================================")
print("PATCH FRONTEND V1.1 CONCLUIDO")
print("==============================================")
print(f"Backup: {backup}")
