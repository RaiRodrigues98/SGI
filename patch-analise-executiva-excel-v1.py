from pathlib import Path
from datetime import datetime
import shutil
import sys

ARQUIVO = Path("frontend/src/services/exportacaoInventarioExcel.ts")
MARCADOR = "// ANALISE_EXECUTIVA_V1"

if not ARQUIVO.exists():
    raise RuntimeError(f"Arquivo não encontrado: {ARQUIVO}")

texto = ARQUIVO.read_text(encoding="utf-8-sig")

if MARCADOR in texto:
    raise RuntimeError(
        "[ERRO] ANALISE_EXECUTIVA_V1 já está presente. "
        "Patch não reaplicado."
    )

ancora = '''  const resumo = workbook.addWorksheet("Resumo do inventário", {'''

quantidade = texto.count(ancora)

if quantidade != 1:
    raise RuntimeError(
        f"[ERRO] Âncora esperada 1 vez, encontrada {quantidade}. "
        "Patch interrompido por segurança."
    )

timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
pasta_backup = Path("backups") / f"analise-executiva-excel-{timestamp}"
pasta_backup.mkdir(parents=True, exist_ok=False)

backup = pasta_backup / ARQUIVO.name
shutil.copy2(ARQUIVO, backup)

bloco = r'''
  // ANALISE_EXECUTIVA_V1
  //
  // Painel executivo do resultado final do inventário oficial.
  // Base financeira:
  //   Quantidade sistema = q_armazenado do snapshot.
  //   Valor sistema = q_armazenado x valor_unitario do snapshot.
  //
  // A quantidade final respeita a mesma precedência utilizada
  // no consolidado atual:
  //   1. quantidade_final_gerencial;
  //   2. última contagem marcada como resultado definitivo.
  //
  // Itens sem custo não recebem valor financeiro artificial.
  if (tipo === "OFICIAL" && resultadoFinal) {
    const analisesExecutiva = [...analises].sort(
      (a, b) => a.numero_rodada - b.numero_rodada,
    );

    type BaseFinanceiraExecutiva = {
      codigo: string;
      lote: string;
      quantidadeSistema: number;
      valorSistemaConhecido: number;
      quantidadeComCusto: number;
      custoFallback: number | null;
      custoIncompleto: boolean;
    };

    const baseFinanceira = new Map<
      string,
      BaseFinanceiraExecutiva
    >();

    for (const item of snapshot.itens) {
      const chave = chaveItem(
        item.codigo,
        item.lote,
      );

      const quantidade =
        Number(item.q_armazenado ?? 0);

      const valorUnitario =
        item.valor_unitario == null
          ? null
          : Number(item.valor_unitario);

      const valorTotal =
        item.valor_total == null
          ? null
          : Number(item.valor_total);

      const atual =
        baseFinanceira.get(chave) ?? {
          codigo: item.codigo,
          lote: item.lote ?? "",
          quantidadeSistema: 0,
          valorSistemaConhecido: 0,
          quantidadeComCusto: 0,
          custoFallback: null,
          custoIncompleto: false,
        };

      atual.quantidadeSistema += quantidade;

      if (
        valorUnitario !== null &&
        Number.isFinite(valorUnitario)
      ) {
        if (atual.custoFallback === null) {
          atual.custoFallback = valorUnitario;
        }

        if (
          valorTotal !== null &&
          Number.isFinite(valorTotal)
        ) {
          atual.valorSistemaConhecido +=
            valorTotal;
        } else {
          atual.valorSistemaConhecido +=
            valorUnitario * quantidade;
        }

        atual.quantidadeComCusto +=
          quantidade;
      } else if (quantidade !== 0) {
        atual.custoIncompleto = true;
      }

      baseFinanceira.set(
        chave,
        atual,
      );
    }

    const mapasRodadasExecutiva =
      analisesExecutiva.map(
        (analise) =>
          new Map(
            analise.itens.map(
              (item) => [
                chaveItem(
                  item.codigo,
                  item.lote,
                ),
                item,
              ],
            ),
          ),
      );

    const mapaGestorExecutiva =
      new Map<string, ItemAnaliseGestor>();

    for (const item of gestor?.itens ?? []) {
      mapaGestorExecutiva.set(
        chaveItem(
          item.codigo,
          item.lote,
        ),
        item,
      );
    }

    const chavesExecutiva =
      new Set<string>(
        baseFinanceira.keys(),
      );

    for (const mapa of mapasRodadasExecutiva) {
      for (const chave of mapa.keys()) {
        chavesExecutiva.add(chave);
      }
    }

    for (const chave of mapaGestorExecutiva.keys()) {
      chavesExecutiva.add(chave);
    }

    let quantidadeEstoqueSistema = 0;
    let quantidadeInventarioFisico = 0;

    let quantidadeFaltas = 0;
    let quantidadeSobras = 0;

    let valorEstoqueSistema = 0;
    let valorInventarioFisico = 0;

    let valorFaltas = 0;
    let valorSobras = 0;

    let itensSemCusto = 0;
    let itensSemResultadoFinal = 0;

    for (const chave of chavesExecutiva) {
      const base =
        baseFinanceira.get(chave);

      const primeiroItem =
        mapasRodadasExecutiva
          .map(
            (mapa) =>
              mapa.get(chave),
          )
          .find(Boolean) as
            | ItemAnaliseOficial
            | undefined;

      const ultimoItem =
        [...mapasRodadasExecutiva]
          .reverse()
          .map(
            (mapa) =>
              mapa.get(chave),
          )
          .find(Boolean) as
            | ItemAnaliseOficial
            | undefined;

      const gestorItem =
        mapaGestorExecutiva.get(chave);

      const quantidadeSistema =
        base?.quantidadeSistema ??
        primeiroItem?.qtd_estoque ??
        gestorItem?.qtd_estoque ??
        0;

      quantidadeEstoqueSistema +=
        Number(quantidadeSistema);

      let custoUnitario:
        | number
        | null = null;

      if (
        base &&
        !base.custoIncompleto
      ) {
        if (
          base.quantidadeSistema !== 0 &&
          base.quantidadeComCusto !== 0
        ) {
          custoUnitario =
            base.valorSistemaConhecido /
            base.quantidadeSistema;
        } else if (
          base.custoFallback !== null
        ) {
          custoUnitario =
            base.custoFallback;
        }
      }

      const quantidadeFinalBruta =
        gestorItem
          ?.quantidade_final_gerencial ??
        (
          ultimoItem?.resultado_definitivo
            ? ultimoItem.qtd_contada
            : null
        );

      if (
        quantidadeFinalBruta == null
      ) {
        itensSemResultadoFinal += 1;

        if (
          Number(quantidadeSistema) !== 0 &&
          custoUnitario === null
        ) {
          itensSemCusto += 1;
        }

        if (
          custoUnitario !== null
        ) {
          valorEstoqueSistema +=
            Number(quantidadeSistema) *
            custoUnitario;
        }

        continue;
      }

      const quantidadeFinal =
        Number(quantidadeFinalBruta);

      quantidadeInventarioFisico +=
        quantidadeFinal;

      const diferenca =
        quantidadeFinal -
        Number(quantidadeSistema);

      if (diferenca < 0) {
        quantidadeFaltas +=
          Math.abs(diferenca);
      }

      if (diferenca > 0) {
        quantidadeSobras +=
          diferenca;
      }

      const exigeCusto =
        Number(quantidadeSistema) !== 0 ||
        quantidadeFinal !== 0;

      if (
        custoUnitario === null
      ) {
        if (exigeCusto) {
          itensSemCusto += 1;
        }

        continue;
      }

      const valorSistemaItem =
        Number(quantidadeSistema) *
        custoUnitario;

      const valorInventarioItem =
        quantidadeFinal *
        custoUnitario;

      valorEstoqueSistema +=
        valorSistemaItem;

      valorInventarioFisico +=
        valorInventarioItem;

      if (diferenca < 0) {
        valorFaltas +=
          Math.abs(diferenca) *
          custoUnitario;
      }

      if (diferenca > 0) {
        valorSobras +=
          diferenca *
          custoUnitario;
      }
    }

    const quantidadeDivergenciaAbsoluta =
      quantidadeFaltas +
      quantidadeSobras;

    const quantidadeSaldoLiquido =
      quantidadeSobras -
      quantidadeFaltas;

    const valorDivergenciaAbsoluta =
      valorFaltas +
      valorSobras;

    const valorSaldoLiquido =
      valorSobras -
      valorFaltas;

    const diferencaLiquidaValor =
      valorInventarioFisico -
      valorEstoqueSistema;

    const acuracidadeItens =
      Number(
        resultadoFinal
          .resumo
          .acuracidade_percentual,
      ) / 100;

    const acuracidadeQuantidade =
      quantidadeEstoqueSistema > 0
        ? Math.max(
            0,
            1 -
              (
                quantidadeDivergenciaAbsoluta /
                quantidadeEstoqueSistema
              ),
          )
        : quantidadeDivergenciaAbsoluta === 0
          ? 1
          : 0;

    const divergenciaFinanceiraPercentual =
      valorEstoqueSistema > 0
        ? (
            valorDivergenciaAbsoluta /
            valorEstoqueSistema
          )
        : 0;

    const executiva =
      workbook.addWorksheet(
        "Análise Executiva",
        {
          views: [
            {
              state: "frozen",
              ySplit: 3,
            },
          ],
          properties: {
            defaultRowHeight: 21,
          },
        },
      );

    estilizarTitulo(
      executiva,
      8,
      "Análise final do inventário oficial",
      `${detalhe.codigo_inventario} · Resultado consolidado do inventário`,
    );

    largura(
      executiva,
      [
        18,
        18,
        18,
        18,
        18,
        18,
        18,
        18,
      ],
    );

    const aplicarBordaExecutiva = (
      celula: ExcelJSTypes.Cell,
    ) => {
      celula.border = {
        top: {
          style: "thin",
          color: {
            argb: `FF${COR_BORDA}`,
          },
        },
        left: {
          style: "thin",
          color: {
            argb: `FF${COR_BORDA}`,
          },
        },
        bottom: {
          style: "thin",
          color: {
            argb: `FF${COR_BORDA}`,
          },
        },
        right: {
          style: "thin",
          color: {
            argb: `FF${COR_BORDA}`,
          },
        },
      };
    };

    const preencherMeta = (
      linha: number,
      colunaLabel: number,
      colunaValorInicio: number,
      colunaValorFim: number,
      label: string,
      valor: ExcelJSTypes.CellValue,
    ) => {
      executiva.getCell(
        linha,
        colunaLabel,
      ).value = label;

      executiva.getCell(
        linha,
        colunaLabel,
      ).font = {
        bold: true,
        color: {
          argb: "FF475569",
        },
      };

      executiva.mergeCells(
        linha,
        colunaValorInicio,
        linha,
        colunaValorFim,
      );

      executiva.getCell(
        linha,
        colunaValorInicio,
      ).value = valor;
    };

    preencherMeta(
      4,
      1,
      2,
      3,
      "Inventário",
      detalhe.codigo_inventario,
    );

    preencherMeta(
      4,
      4,
      5,
      6,
      "Cliente",
      detalhe.cliente,
    );

    preencherMeta(
      4,
      7,
      8,
      8,
      "Armazém",
      detalhe.armazem,
    );

    preencherMeta(
      5,
      1,
      2,
      3,
      "Tipo",
      detalhe.tipo,
    );

    preencherMeta(
      5,
      4,
      5,
      6,
      "Status",
      detalhe.status,
    );

    preencherMeta(
      5,
      7,
      8,
      8,
      "Finalizado em",
      dataExcel(
        resultadoFinal
          .data_hora_finalizacao,
      ),
    );

    executiva.getCell(
      5,
      8,
    ).numFmt =
      "dd/mm/yyyy hh:mm:ss";

    const cards = [
      {
        inicio: 1,
        fim: 2,
        label:
          "ACURACIDADE POR ITEM",
        valor: acuracidadeItens,
        formato: "0.00%",
      },
      {
        inicio: 3,
        fim: 4,
        label:
          "ACURACIDADE POR QUANTIDADE",
        valor: acuracidadeQuantidade,
        formato: "0.00%",
      },
      {
        inicio: 5,
        fim: 6,
        label:
          "DIVERGÊNCIA FINANCEIRA",
        valor:
          divergenciaFinanceiraPercentual,
        formato: "0.00%",
      },
      {
        inicio: 7,
        fim: 8,
        label:
          "ITENS DIVERGENTES",
        valor:
          resultadoFinal.resumo
            .divergencias,
        formato: "#,##0",
      },
    ];

    for (const card of cards) {
      executiva.mergeCells(
        8,
        card.inicio,
        8,
        card.fim,
      );

      executiva.mergeCells(
        9,
        card.inicio,
        10,
        card.fim,
      );

      const label =
        executiva.getCell(
          8,
          card.inicio,
        );

      label.value =
        card.label;

      label.font = {
        bold: true,
        color: {
          argb: "FF475569",
        },
        size: 9,
      };

      label.fill = {
        type: "pattern",
        pattern: "solid",
        fgColor: {
          argb: `FF${COR_CABECALHO}`,
        },
      };

      label.alignment = {
        horizontal: "center",
        vertical: "middle",
        wrapText: true,
      };

      const valor =
        executiva.getCell(
          9,
          card.inicio,
        );

      valor.value =
        card.valor;

      valor.numFmt =
        card.formato;

      valor.font = {
        bold: true,
        color: {
          argb: `FF${COR_PRIMARIA}`,
        },
        size: 18,
      };

      valor.alignment = {
        horizontal: "center",
        vertical: "middle",
      };

      for (
        let linha = 8;
        linha <= 10;
        linha += 1
      ) {
        for (
          let coluna = card.inicio;
          coluna <= card.fim;
          coluna += 1
        ) {
          aplicarBordaExecutiva(
            executiva.getCell(
              linha,
              coluna,
            ),
          );
        }
      }
    }

    executiva.mergeCells(
      12,
      1,
      12,
      8,
    );

    executiva.getCell(
      12,
      1,
    ).value =
      "Posição final do estoque";

    executiva.getCell(
      12,
      1,
    ).font = {
      bold: true,
      color: {
        argb: `FF${COR_PRIMARIA}`,
      },
      size: 12,
    };

    executiva.getCell(
      12,
      1,
    ).fill = {
      type: "pattern",
      pattern: "solid",
      fgColor: {
        argb: `FF${COR_SECUNDARIA}`,
      },
    };

    const criarCabecalhoTabela = (
      linha: number,
    ) => {
      executiva.mergeCells(
        linha,
        1,
        linha,
        4,
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
      ).value = "Indicador";

      executiva.getCell(
        linha,
        5,
      ).value = "Quantidade";

      executiva.getCell(
        linha,
        7,
      ).value = "Valor";

      for (
        const coluna of [1, 5, 7]
      ) {
        const celula =
          executiva.getCell(
            linha,
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
          horizontal: "center",
          vertical: "middle",
        };
      }

      for (
        let coluna = 1;
        coluna <= 8;
        coluna += 1
      ) {
        aplicarBordaExecutiva(
          executiva.getCell(
            linha,
            coluna,
          ),
        );
      }
    };

    const preencherLinhaTabela = (
      linha: number,
      indicador: string,
      quantidade: number,
      valor: number,
      destaque:
        | "normal"
        | "falta"
        | "sobra"
        | "total" = "normal",
    ) => {
      executiva.mergeCells(
        linha,
        1,
        linha,
        4,
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
      ).value = indicador;

      executiva.getCell(
        linha,
        5,
      ).value = quantidade;

      executiva.getCell(
        linha,
        7,
      ).value = valor;

      executiva.getCell(
        linha,
        5,
      ).numFmt = "#,##0.00";

      executiva.getCell(
        linha,
        7,
      ).numFmt =
        'R$ #,##0.00;[Red]-R$ #,##0.00';

      let corFundo =
        "FFFFFFFF";

      if (destaque === "falta") {
        corFundo =
          "FFFEE2E2";
      }

      if (destaque === "sobra") {
        corFundo =
          "FFDCFCE7";
      }

      if (destaque === "total") {
        corFundo =
          "FFE8E6F7";
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

        celula.alignment = {
          vertical: "middle",
        };

        aplicarBordaExecutiva(
          celula,
        );
      }

      if (
        destaque !== "normal"
      ) {
        executiva.getCell(
          linha,
          1,
        ).font = {
          bold: true,
          color: {
            argb: `FF${COR_TEXTO}`,
          },
        };

        executiva.getCell(
          linha,
          5,
        ).font = {
          bold: true,
        };

        executiva.getCell(
          linha,
          7,
        ).font = {
          bold: true,
        };
      }
    };

    criarCabecalhoTabela(13);

    preencherLinhaTabela(
      14,
      "Estoque Sistema",
      quantidadeEstoqueSistema,
      valorEstoqueSistema,
    );

    preencherLinhaTabela(
      15,
      "Inventário Físico",
      quantidadeInventarioFisico,
      valorInventarioFisico,
    );

    preencherLinhaTabela(
      16,
      "Diferença Líquida",
      quantidadeInventarioFisico -
        quantidadeEstoqueSistema,
      diferencaLiquidaValor,
      "total",
    );

    executiva.mergeCells(
      18,
      1,
      18,
      8,
    );

    executiva.getCell(
      18,
      1,
    ).value =
      "Análise das divergências";

    executiva.getCell(
      18,
      1,
    ).font = {
      bold: true,
      color: {
        argb: `FF${COR_PRIMARIA}`,
      },
      size: 12,
    };

    executiva.getCell(
      18,
      1,
    ).fill = {
      type: "pattern",
      pattern: "solid",
      fgColor: {
        argb: `FF${COR_SECUNDARIA}`,
      },
    };

    criarCabecalhoTabela(19);

    preencherLinhaTabela(
      20,
      "Faltas",
      quantidadeFaltas,
      valorFaltas,
      "falta",
    );

    preencherLinhaTabela(
      21,
      "Sobras",
      quantidadeSobras,
      valorSobras,
      "sobra",
    );

    preencherLinhaTabela(
      22,
      "Divergência Absoluta",
      quantidadeDivergenciaAbsoluta,
      valorDivergenciaAbsoluta,
      "total",
    );

    preencherLinhaTabela(
      23,
      "Saldo Líquido",
      quantidadeSaldoLiquido,
      valorSaldoLiquido,
      "total",
    );

    executiva.mergeCells(
      26,
      1,
      26,
      8,
    );

    executiva.getCell(
      26,
      1,
    ).value =
      "Indicadores complementares";

    executiva.getCell(
      26,
      1,
    ).font = {
      bold: true,
      color: {
        argb: `FF${COR_PRIMARIA}`,
      },
      size: 12,
    };

    executiva.getCell(
      26,
      1,
    ).fill = {
      type: "pattern",
      pattern: "solid",
      fgColor: {
        argb: `FF${COR_SECUNDARIA}`,
      },
    };

    const indicadoresComplementares:
      Array<
        [
          string,
          number,
          string,
        ]
      > = [
        [
          "Itens analisados (código + lote)",
          resultadoFinal.resumo
            .total_itens,
          "#,##0",
        ],
        [
          "Itens OK",
          resultadoFinal.resumo.ok,
          "#,##0",
        ],
        [
          "Itens divergentes",
          resultadoFinal.resumo
            .divergencias,
          "#,##0",
        ],
        [
          "Itens com falta",
          resultadoFinal.resumo
            .faltas,
          "#,##0",
        ],
        [
          "Itens com sobra",
          resultadoFinal.resumo
            .sobras,
          "#,##0",
        ],
        [
          "Itens sem custo disponível",
          itensSemCusto,
          "#,##0",
        ],
        [
          "Itens sem resultado final",
          itensSemResultadoFinal,
          "#,##0",
        ],
      ];

    let linhaIndicador = 27;

    for (
      const [
        label,
        valor,
        formato,
      ] of indicadoresComplementares
    ) {
      executiva.mergeCells(
        linhaIndicador,
        1,
        linhaIndicador,
        5,
      );

      executiva.mergeCells(
        linhaIndicador,
        6,
        linhaIndicador,
        8,
      );

      executiva.getCell(
        linhaIndicador,
        1,
      ).value = label;

      executiva.getCell(
        linhaIndicador,
        6,
      ).value = valor;

      executiva.getCell(
        linhaIndicador,
        6,
      ).numFmt = formato;

      executiva.getCell(
        linhaIndicador,
        1,
      ).font = {
        color: {
          argb: `FF${COR_TEXTO}`,
        },
      };

      executiva.getCell(
        linhaIndicador,
        6,
      ).font = {
        bold: true,
        color: {
          argb: `FF${COR_PRIMARIA}`,
        },
      };

      for (
        let coluna = 1;
        coluna <= 8;
        coluna += 1
      ) {
        aplicarBordaExecutiva(
          executiva.getCell(
            linhaIndicador,
            coluna,
          ),
        );
      }

      linhaIndicador += 1;
    }

    const linhaNota =
      linhaIndicador + 1;

    executiva.mergeCells(
      linhaNota,
      1,
      linhaNota + 1,
      8,
    );

    const notas: string[] = [
      "Base financeira: quantidade armazenada e valor unitário congelados no snapshot do inventário.",
      "Faltas e sobras em quantidade representam unidades físicas; os indicadores de itens representam código + lote.",
    ];

    if (itensSemCusto > 0) {
      notas.push(
        `${itensSemCusto} item(ns) sem custo foram excluídos dos indicadores financeiros.`,
      );
    }

    if (
      itensSemResultadoFinal > 0
    ) {
      notas.push(
        `${itensSemResultadoFinal} item(ns) não possuem resultado final e exigem validação.`,
      );
    }

    executiva.getCell(
      linhaNota,
      1,
    ).value =
      notas.join(" ");

    executiva.getCell(
      linhaNota,
      1,
    ).font = {
      italic: true,
      color: {
        argb: "FF64748B",
      },
      size: 9,
    };

    executiva.getCell(
      linhaNota,
      1,
    ).alignment = {
      vertical: "top",
      wrapText: true,
    };

    executiva.getRow(
      linhaNota,
    ).height = 30;
  }

'''

novo = texto.replace(
    ancora,
    bloco + ancura if False else bloco + ancora,
    1,
)

if novo == texto:
    raise RuntimeError(
        "[ERRO] Nenhuma alteração foi produzida."
    )

ARQUIVO.write_text(
    novo,
    encoding="utf-8",
    newline="\n",
)

print("==============================================")
print("PATCH APLICADO COM SUCESSO")
print("==============================================")
print(f"Arquivo : {ARQUIVO}")
print(f"Backup  : {backup}")
print("")
print("Incluído:")
print("- Aba Análise Executiva")
print("- Quantidade Sistema x Inventário")
print("- Valores Sistema x Inventário")
print("- Faltas e Sobras em unidades")
print("- Divergência absoluta")
print("- Saldo líquido")
print("- Acuracidade por item")
print("- Acuracidade por quantidade")
print("- Divergência financeira")
print("- Controle de itens sem custo")
print("- Controle de itens sem resultado final")
