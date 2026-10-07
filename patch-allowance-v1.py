from pathlib import Path
from datetime import datetime
import shutil

arquivo = Path(
    "frontend/src/services/exportacaoInventarioExcel.ts"
)

if not arquivo.exists():
    raise SystemExit(
        "[ERRO] exportacaoInventarioExcel.ts não encontrado."
    )

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

backup_dir = Path(
    f"backups/allowance-v1-{stamp}"
)

backup_dir.mkdir(
    parents=True,
    exist_ok=True,
)

shutil.copy2(
    arquivo,
    backup_dir / arquivo.name,
)

print(f"[OK] Backup: {backup_dir}")

texto = arquivo.read_text(
    encoding="utf-8",
)

marker = "// CALCULO_ALLOWANCE_V1"

if marker in texto:
    raise SystemExit(
        "[SKIP] CALCULO_ALLOWANCE_V1 já existe."
    )

ancora = """    const linhaNota =
      linhaMovimentacaoFim + 2;
"""

if ancora not in texto:
    raise SystemExit(
        "[ERRO] Âncora linhaNota não encontrada."
    )

bloco = r'''    // CALCULO_ALLOWANCE_V1
    //
    // Regra:
    // Volume total = expedição + recebimento + estoque.
    // Cobertura = volume total x 0,5%.
    //
    // Para a base de penalidade, faltas e sobras são
    // tratadas como impactos financeiros negativos:
    //
    // divergência = -(faltas + sobras)
    //
    // penalidade =
    //   divergência + cobertura >= 0
    //     ? 0
    //     : divergência + cobertura

    const movimentacaoExpedicaoAllowance =
      movimentacao12Meses
        ?.expedicoes
        .valor ?? null;

    const movimentacaoRecebimentoAllowance =
      movimentacao12Meses
        ?.recebimentos
        .valor ?? null;

    const volumeTotalMovimentadoMaisEstoque =
      financeiroCompleto &&
      movimentacaoExpedicaoAllowance !== null &&
      movimentacaoRecebimentoAllowance !== null
        ? (
            movimentacaoExpedicaoAllowance +
            movimentacaoRecebimentoAllowance +
            valorEstoqueSistema
          )
        : null;

    const totalPerdasAllowance =
      financeiroCompleto
        ? -Math.abs(valorFaltas)
        : null;

    const totalSobrasAllowance =
      financeiroCompleto
        ? -Math.abs(valorSobras)
        : null;

    const divergenciaLiquidaAllowance =
      totalPerdasAllowance !== null &&
      totalSobrasAllowance !== null
        ? (
            totalPerdasAllowance +
            totalSobrasAllowance
          )
        : null;

    const coberturaAllowance =
      volumeTotalMovimentadoMaisEstoque !== null
        ? (
            volumeTotalMovimentadoMaisEstoque *
            0.005
          )
        : null;

    const penalidadeInventario =
      divergenciaLiquidaAllowance !== null &&
      coberturaAllowance !== null
        ? (
            divergenciaLiquidaAllowance +
              coberturaAllowance >=
            0
              ? 0
              : (
                  divergenciaLiquidaAllowance +
                  coberturaAllowance
                )
          )
        : null;

    const periodoInicioAllowance =
      movimentacao12Meses
        ? new Date(
            movimentacao12Meses
              .periodo
              .inicio,
          ).toLocaleDateString(
            "pt-BR",
            {
              month: "2-digit",
              year: "2-digit",
            },
          )
        : "--/--";

    const periodoFimAllowance =
      movimentacao12Meses
        ? new Date(
            movimentacao12Meses
              .periodo
              .fim,
          ).toLocaleDateString(
            "pt-BR",
            {
              month: "2-digit",
              year: "2-digit",
            },
          )
        : "--/--";

    const linhaAllowanceCabecalho =
      linhaMovimentacaoFim + 2;

    executiva.mergeCells(
      linhaAllowanceCabecalho,
      1,
      linhaAllowanceCabecalho,
      6,
    );

    executiva.mergeCells(
      linhaAllowanceCabecalho,
      7,
      linhaAllowanceCabecalho,
      8,
    );

    executiva.getCell(
      linhaAllowanceCabecalho,
      1,
    ).value =
      "Cálculo Allowance 0,5%";

    executiva.getCell(
      linhaAllowanceCabecalho,
      7,
    ).value =
      "Valor Total";

    for (
      let coluna = 1;
      coluna <= 8;
      coluna += 1
    ) {
      const celula =
        executiva.getCell(
          linhaAllowanceCabecalho,
          coluna,
        );

      celula.fill = {
        type: "pattern",
        pattern: "solid",
        fgColor: {
          argb: "FFF2C94C",
        },
      };

      celula.font = {
        bold: true,
        color: {
          argb: `FF${COR_TEXTO}`,
        },
      };

      celula.alignment = {
        vertical: "middle",
        horizontal: "center",
      };

      aplicarBordaExecutiva(
        celula,
      );
    }

    const preencherLinhaAllowance = (
      linha: number,
      descricao: string,
      valor: number | null,
      destaque:
        | "normal"
        | "perda"
        | "sobra"
        | "cobertura"
        | "penalidade" = "normal",
    ) => {
      executiva.mergeCells(
        linha,
        1,
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
      ).value = descricao;

      executiva.getCell(
        linha,
        7,
      ).value =
        valor === null
          ? "N/D"
          : valor;

      if (valor !== null) {
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

      let corFundo =
        "FFF3F4F6";

      let corTexto =
        `FF${COR_TEXTO}`;

      let negrito =
        false;

      if (
        destaque === "perda"
      ) {
        corTexto =
          "FFDC2626";

        negrito =
          true;
      }

      if (
        destaque === "sobra"
      ) {
        corTexto =
          "FF1D4ED8";

        negrito =
          true;
      }

      if (
        destaque === "cobertura"
      ) {
        corFundo =
          "FFD4A017";

        negrito =
          true;
      }

      if (
        destaque === "penalidade"
      ) {
        corFundo =
          "FFD1D5DB";

        negrito =
          true;

        if (
          valor !== null &&
          valor < 0
        ) {
          corTexto =
            "FFDC2626";
        }
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

        celula.fill = {
          type: "pattern",
          pattern: "solid",
          fgColor: {
            argb: corFundo,
          },
        };

        celula.font = {
          bold: negrito,
          color: {
            argb: corTexto,
          },
        };

        celula.alignment = {
          vertical: "middle",
          horizontal:
            coluna <= 6
              ? "center"
              : "right",
        };

        aplicarBordaExecutiva(
          celula,
        );
      }
    };

    preencherLinhaAllowance(
      linhaAllowanceCabecalho + 1,
      `Movimentação Expedição (${periodoInicioAllowance} a ${periodoFimAllowance})`,
      movimentacaoExpedicaoAllowance,
    );

    preencherLinhaAllowance(
      linhaAllowanceCabecalho + 2,
      `Movimentação Recebimento (${periodoInicioAllowance} a ${periodoFimAllowance})`,
      movimentacaoRecebimentoAllowance,
    );

    preencherLinhaAllowance(
      linhaAllowanceCabecalho + 3,
      "Volume Total Movimentado + Estoque",
      volumeTotalMovimentadoMaisEstoque,
      "normal",
    );

    preencherLinhaAllowance(
      linhaAllowanceCabecalho + 4,
      "Total de Perdas (Faltas e/ou Inversões)",
      totalPerdasAllowance,
      "perda",
    );

    preencherLinhaAllowance(
      linhaAllowanceCabecalho + 5,
      "Total de Sobras e/ou Inversões",
      totalSobrasAllowance,
      "sobra",
    );

    preencherLinhaAllowance(
      linhaAllowanceCabecalho + 6,
      "Divergência líquida",
      divergenciaLiquidaAllowance,
      "normal",
    );

    preencherLinhaAllowance(
      linhaAllowanceCabecalho + 7,
      "Cobertura Allowance 0,5%",
      coberturaAllowance,
      "cobertura",
    );

    preencherLinhaAllowance(
      linhaAllowanceCabecalho + 8,
      "Penalidade de Inventário",
      penalidadeInventario,
      "penalidade",
    );

    const linhaAllowanceFim =
      linhaAllowanceCabecalho + 8;

    const linhaNota =
      linhaAllowanceFim + 2;
'''

texto = texto.replace(
    ancora,
    bloco,
    1,
)

arquivo.write_text(
    texto,
    encoding="utf-8",
)

print(
    "[OK] Cálculo Allowance inserido."
)

print("")
print(
    "=============================================="
)
print(
    "PATCH CALCULO ALLOWANCE V1 CONCLUIDO"
)
print(
    "=============================================="
)
