import type ExcelJSTypes from "exceljs";
import { consultarInventarioDetalhe, consultarSnapshotInventario } from "@/services/inventarioService";
import { buscarRodadasInventario } from "@/services/recontagemService";
import { buscarAnaliseOficial } from "@/services/oficialService";
import { buscarAnaliseGestor } from "@/services/gestorService";
import {
  buscarMovimentacao12Meses,
  buscarResultadoFinalIndicadores,
  buscarValoracaoEstoque,
} from "@/services/indicadoresService";

type AnaliseOficial = Awaited<ReturnType<typeof buscarAnaliseOficial>>;
type ItemAnaliseOficial = AnaliseOficial["itens"][number];
type AnaliseGestor = Awaited<ReturnType<typeof buscarAnaliseGestor>>;
type ItemAnaliseGestor = AnaliseGestor["itens"][number];

const COR_PRIMARIA = "25206E";
const COR_SECUNDARIA = "E8E6F7";
const COR_CABECALHO = "F1F5F9";
const COR_BORDA = "CBD5E1";
const COR_TEXTO = "0F172A";

function chaveItem(codigo: string, lote: string | null | undefined) {
  return `${codigo.trim()}::${String(lote ?? "").trim()}`;
}

function dataExcel(valor: string | null | undefined): Date | null {
  if (!valor) return null;

  // DATA_EXCEL_SEM_CONVERSAO_FUSO_V1
  //
  // Datas operacionais do SQL Server sao armazenadas sem timezone.
  // Ao usar new Date(valor), o navegador interpreta o horario como
  // local e o ExcelJS grava o instante UTC, adicionando 3 horas em
  // ambientes UTC-03.
  //
  // Para o Excel, preservamos exatamente os componentes de data/hora
  // recebidos do SGI, sem deslocamento de fuso.
  const partes = valor.match(
    /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?/,
  );

  if (partes) {
    const [
      ,
      ano,
      mes,
      dia,
      hora,
      minuto,
      segundo,
      fracao = "0",
    ] = partes;

    const milissegundo = Number(
      fracao
        .slice(0, 3)
        .padEnd(3, "0"),
    );

    return new Date(
      Date.UTC(
        Number(ano),
        Number(mes) - 1,
        Number(dia),
        Number(hora),
        Number(minuto),
        Number(segundo),
        milissegundo,
      ),
    );
  }

  const data = new Date(valor);

  return Number.isNaN(data.getTime())
    ? null
    : data;
}

function estilizarTitulo(planilha: ExcelJSTypes.Worksheet, ultimaColuna: number, titulo: string, subtitulo: string) {
  planilha.mergeCells(1, 1, 1, ultimaColuna);
  planilha.getCell(1, 1).value = titulo;
  planilha.getCell(1, 1).font = { bold: true, color: { argb: "FFFFFFFF" }, size: 16 };
  planilha.getCell(1, 1).fill = { type: "pattern", pattern: "solid", fgColor: { argb: `FF${COR_PRIMARIA}` } };
  planilha.getCell(1, 1).alignment = { vertical: "middle", horizontal: "left" };
  planilha.getRow(1).height = 28;

  planilha.mergeCells(2, 1, 2, ultimaColuna);
  planilha.getCell(2, 1).value = subtitulo;
  planilha.getCell(2, 1).font = { color: { argb: "FF475569" }, italic: true, size: 10 };
  planilha.getCell(2, 1).alignment = { vertical: "middle", horizontal: "left" };
  planilha.getRow(2).height = 22;
}

function estilizarCabecalho(planilha: ExcelJSTypes.Worksheet, linha: number, primeiraColuna: number, ultimaColuna: number) {
  const row = planilha.getRow(linha);
  row.height = 30;
  for (let coluna = primeiraColuna; coluna <= ultimaColuna; coluna += 1) {
    const celula = row.getCell(coluna);
    celula.font = { bold: true, color: { argb: `FF${COR_TEXTO}` }, size: 10 };
    celula.fill = { type: "pattern", pattern: "solid", fgColor: { argb: `FF${COR_CABECALHO}` } };
    celula.alignment = { vertical: "middle", horizontal: "center", wrapText: true };
    celula.border = {
      top: { style: "thin", color: { argb: `FF${COR_BORDA}` } },
      left: { style: "thin", color: { argb: `FF${COR_BORDA}` } },
      bottom: { style: "thin", color: { argb: `FF${COR_BORDA}` } },
      right: { style: "thin", color: { argb: `FF${COR_BORDA}` } },
    };
  }
}

function estilizarDados(planilha: ExcelJSTypes.Worksheet, linhaInicial: number, ultimaColuna: number) {
  for (let linha = linhaInicial; linha <= planilha.rowCount; linha += 1) {
    const row = planilha.getRow(linha);
    for (let coluna = 1; coluna <= ultimaColuna; coluna += 1) {
      const celula = row.getCell(coluna);
      celula.alignment = { vertical: "top", wrapText: true };
      celula.border = {
        bottom: { style: "hair", color: { argb: "FFE2E8F0" } },
      };
    }
  }
}

function largura(planilha: ExcelJSTypes.Worksheet, larguras: number[]) {
  larguras.forEach((valor, indice) => {
    planilha.getColumn(indice + 1).width = valor;
  });
}

function ordinal(numero: number) {
  return `${numero}ª Contagem${numero === 5 ? " - física" : ""}`;
}

export async function exportarAnaliseInventarioExcel(idInventario: number): Promise<void> {
  if (!Number.isInteger(idInventario) || idInventario <= 0) {
    throw new Error("Inventário inválido para exportação.");
  }

  const [detalhe, snapshot, historicoRodadas] = await Promise.all([
    consultarInventarioDetalhe(idInventario),
    consultarSnapshotInventario(idInventario),
    buscarRodadasInventario(idInventario),
  ]);

  const tipo = String(detalhe.tipo).trim().toUpperCase();
  const rodadasOrdenadas = [...historicoRodadas.rodadas].sort(
    (a, b) => a.numero_rodada - b.numero_rodada,
  );

  const analises: AnaliseOficial[] = tipo === "OFICIAL"
    ? await Promise.all(
        rodadasOrdenadas.map((rodada) =>
          buscarAnaliseOficial(idInventario, rodada.id_rodada),
        ),
      )
    : [];

  // ANALISE_EXECUTIVA_V11_MOV12
  const inventarioFinalizado =
    String(detalhe.status)
      .trim()
      .toUpperCase() === "FINALIZADO";

  const [
    gestorResultado,
    finalResultado,
    movimentacaoResultado,
    valoracaoResultado,
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

    tipo === "OFICIAL" && inventarioFinalizado
      ? buscarValoracaoEstoque(idInventario)
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

  const valoracaoEstoque =
    valoracaoResultado.status === "fulfilled"
      ? valoracaoResultado.value
      : null;

  const [{ default: ExcelJS }, { saveAs }] = await Promise.all([
    import("exceljs"),
    import("file-saver"),
  ]);

  const workbook = new ExcelJS.Workbook();
  workbook.creator = "SGI - Sistema de Governança de Inventário";
  workbook.created = new Date();
  workbook.modified = new Date();


  // ANALISE_EXECUTIVA_V1
  //
  // Painel executivo do resultado final do inventário oficial.
  // Base financeira:
  //   Quantidade sistema = q_armazenado do snapshot.
  //   Valor sistema = q_armazenado x custo unitario resolvido.
  //   Prioridade: snapshot, ultimo recebimento codigo + lote,
  //   ultimo recebimento codigo.
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

    // VALORACAO_ESTOQUE_V1
    const mapaValoracaoEstoque = new Map(
      (valoracaoEstoque?.itens ?? []).map(
        (item) => [
          chaveItem(
            item.codigo,
            item.lote,
          ),
          item,
        ] as const,
      ),
    );

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
    let itensComCustoFallback = 0;
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

      let custoViaFallback = false;

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

      if (custoUnitario === null) {
        const valoracaoItem =
          mapaValoracaoEstoque.get(chave);

        const custoValoracao =
          valoracaoItem?.valor_unitario == null
            ? null
            : Number(
                valoracaoItem.valor_unitario,
              );

        if (
          custoValoracao !== null &&
          Number.isFinite(custoValoracao) &&
          valoracaoItem?.linhas_sem_custo === 0
        ) {
          custoUnitario =
            custoValoracao;

          custoViaFallback =
            valoracaoItem.origem_custo !==
            "SNAPSHOT";
        }
      }

      if (custoViaFallback) {
        itensComCustoFallback += 1;
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

    const financeiroCompleto =
      itensSemCusto === 0;

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
          divergenciaFinanceiraPercentual ?? "N/D",
        formato:
          divergenciaFinanceiraPercentual === null
            ? "@"
            : "0.00%",
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
      valor: number | string,
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

      if (typeof valor === "number") {
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
      financeiroCompleto
        ? valorEstoqueSistema
        : "N/D",
    );

    preencherLinhaTabela(
      15,
      "Inventário Físico",
      quantidadeInventarioFisico,
      financeiroCompleto
        ? valorInventarioFisico
        : "N/D",
    );

    preencherLinhaTabela(
      16,
      "Diferença Líquida",
      quantidadeInventarioFisico -
        quantidadeEstoqueSistema,
      financeiroCompleto
        ? diferencaLiquidaValor
        : "N/D",
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
      financeiroCompleto
        ? valorFaltas
        : "N/D",
      "falta",
    );

    preencherLinhaTabela(
      21,
      "Sobras",
      quantidadeSobras,
      financeiroCompleto
        ? valorSobras
        : "N/D",
      "sobra",
    );

    preencherLinhaTabela(
      22,
      "Divergência Absoluta",
      quantidadeDivergenciaAbsoluta,
      financeiroCompleto
        ? valorDivergenciaAbsoluta
        : "N/D",
      "total",
    );

    preencherLinhaTabela(
      23,
      "Saldo Líquido",
      quantidadeSaldoLiquido,
      financeiroCompleto
        ? valorSaldoLiquido
        : "N/D",
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
          number | string,
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

    // ========================================================
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

    // CALCULO_ALLOWANCE_V1
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

    executiva.mergeCells(
      linhaNota,
      1,
      linhaNota + 1,
      8,
    );

    const notas: string[] = [
      "Base financeira: quantidade armazenada congelada no snapshot. O custo utiliza o valor do snapshot e, quando ausente, o histórico de recebimentos anterior à finalização.",
      "Faltas e sobras em quantidade representam unidades físicas; os indicadores de itens representam código + lote.",
    ];

    if (itensComCustoFallback > 0) {
      notas.push(
        `${itensComCustoFallback} item(ns) tiveram o custo complementado pelo histórico de recebimentos anterior à finalização do inventário, priorizando código + lote e, quando necessário, código.`,
      );
    }

    if (itensSemCusto > 0) {
      notas.push(
        `${itensSemCusto} item(ns) sem custo disponível. Os indicadores financeiros do inventário são apresentados como N/D para evitar valores parciais ou incorretos.`,
      );
    }

    if (
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

  const resumo = workbook.addWorksheet("Resumo do inventário", {
    views: [{ state: "frozen", ySplit: 3 }],
    properties: { defaultRowHeight: 20 },
  });
  estilizarTitulo(
    resumo,
    6,
    `Resumo do inventário ${detalhe.codigo_inventario}`,
    `Gerado pelo SGI em ${new Date().toLocaleString("pt-BR")}`,
  );
  largura(resumo, [28, 28, 28, 28, 28, 28]);

  const secoes: Array<[string, Array<[string, unknown]>]> = [
    ["Identificação", [
      ["ID", detalhe.id_inventario],
      ["Código", detalhe.codigo_inventario],
      ["Cliente", detalhe.cliente],
      ["Cliente ID", detalhe.cliente_id],
      ["Armazém", detalhe.armazem],
      ["Descrição", detalhe.descricao ?? "-"],
      ["Tipo", detalhe.tipo],
      ["Status", detalhe.status],
    ]],
    ["Período e responsáveis", [
      ["Criado em", dataExcel(detalhe.data_hora_criacao)],
      ["Criado por", detalhe.criado_por ?? "-"],
      ["Início", dataExcel(detalhe.data_hora_inicio)],
      ["Fim", dataExcel(detalhe.data_hora_fim)],
      ["Finalizado por", detalhe.finalizado_por ?? resultadoFinal?.finalizado_por ?? "-"],
      ["Encaminhado ao gestor em", dataExcel(detalhe.data_hora_encaminhamento_gestor)],
      ["Encaminhado por", detalhe.encaminhado_gestor_por ?? "-"],
    ]],
    ["Operação", [
      ["Fase operacional", detalhe.fase_operacional],
      ["Próxima ação", detalhe.proxima_acao],
      ["Rodada atual", detalhe.rodada_atual],
      ["Total de rodadas", historicoRodadas.total_rodadas],
      ["Localizações", detalhe.total_localizacoes],
      ["Localizações concluídas", detalhe.localizacoes_concluidas],
      ["Localizações pendentes", detalhe.localizacoes_pendentes],
      ["Localizações em contagem", detalhe.localizacoes_em_contagem],
      ["Progresso", Number(detalhe.percentual_progresso) / 100],
      ["Divergências", detalhe.total_divergencias],
      ["Divergências sem decisão", detalhe.divergencias_sem_decisao],
      ["Recontagens pendentes", detalhe.recontagens_pendentes],
    ]],
    ["Resultado", [
      ["Rodada final", resultadoFinal?.rodada_final ?? "-"],
      ["Total de itens", resultadoFinal?.resumo.total_itens ?? snapshot.total],
      ["Itens OK", resultadoFinal?.resumo.ok ?? "-"],
      ["Itens NOK", resultadoFinal?.resumo.nok ?? "-"],
      ["Faltas", resultadoFinal?.resumo.faltas ?? "-"],
      ["Sobras", resultadoFinal?.resumo.sobras ?? "-"],
      ["Divergências finais", resultadoFinal?.resumo.divergencias ?? "-"],
      ["Acuracidade", resultadoFinal ? Number(resultadoFinal.resumo.acuracidade_percentual) / 100 : "-"],
      ["Data de finalização", dataExcel(resultadoFinal?.data_hora_finalizacao)],
    ]],
  ];

  let linhaResumo = 4;
  for (const [titulo, campos] of secoes) {
    resumo.mergeCells(linhaResumo, 1, linhaResumo, 6);
    const tituloCelula = resumo.getCell(linhaResumo, 1);
    tituloCelula.value = titulo;
    tituloCelula.font = { bold: true, color: { argb: `FF${COR_PRIMARIA}` }, size: 12 };
    tituloCelula.fill = { type: "pattern", pattern: "solid", fgColor: { argb: `FF${COR_SECUNDARIA}` } };
    linhaResumo += 1;

    for (let indice = 0; indice < campos.length; indice += 2) {
      const esquerda = campos[indice];
      const direita = campos[indice + 1];

      if (!esquerda) {
        continue;
      }

      resumo.getCell(linhaResumo, 1).value = esquerda[0];
      resumo.getCell(linhaResumo, 1).font = { bold: true, color: { argb: "FF475569" } };
      resumo.getCell(linhaResumo, 2).value = esquerda[1] as ExcelJSTypes.CellValue;
      if (esquerda[1] instanceof Date) resumo.getCell(linhaResumo, 2).numFmt = "dd/mm/yyyy hh:mm:ss";
      if (esquerda[0] === "Progresso" || esquerda[0] === "Acuracidade") resumo.getCell(linhaResumo, 2).numFmt = "0.00%";

      if (direita) {
        resumo.getCell(linhaResumo, 4).value = direita[0];
        resumo.getCell(linhaResumo, 4).font = { bold: true, color: { argb: "FF475569" } };
        resumo.getCell(linhaResumo, 5).value = direita[1] as ExcelJSTypes.CellValue;
        if (direita[1] instanceof Date) resumo.getCell(linhaResumo, 5).numFmt = "dd/mm/yyyy hh:mm:ss";
        if (direita[0] === "Progresso" || direita[0] === "Acuracidade") resumo.getCell(linhaResumo, 5).numFmt = "0.00%";
      }
      linhaResumo += 1;
    }
    linhaResumo += 1;
  }

  const estoque = workbook.addWorksheet("Estoque do inventário", {
    views: [{ state: "frozen", ySplit: 4 }],
    properties: { defaultRowHeight: 20 },
  });
  const colunasEstoque = [
    "ID origem", "Armazém", "Localização", "Código", "Descrição", "Lote",
    "Unidade", "Categoria", "Validade", "Qtd armazenada", "Qtd reservada",
    "Qtd separando", "Qtd bloqueada", "Qtd recebimento", "Saldo inventário",
    "Valor unitário", "Valor total", "Status estoque", "Tipo localização",
  ];
  estilizarTitulo(
    estoque,
    colunasEstoque.length,
    "Estoque do inventário",
    `${detalhe.codigo_inventario} · Snapshot com ${snapshot.total} registro(s)`,
  );
  estoque.addRow([]);
  estoque.addRow(colunasEstoque);
  estilizarCabecalho(estoque, 4, 1, colunasEstoque.length);
  for (const item of snapshot.itens) {
    estoque.addRow([
      item.id_origem, item.c_armazem, item.localizacao, item.codigo,
      item.descricao, item.lote ?? "", item.unidade ?? "", item.categoria ?? "",
      dataExcel(item.validade), item.q_armazenado, item.q_reservado,
      item.q_separando, item.q_bloqueado, item.q_recebimento,
      item.saldo_inventario, item.valor_unitario, item.valor_total,
      item.status_estoque, item.tipo_localizacao ?? "",
    ]);
  }
  estoque.autoFilter = { from: { row: 4, column: 1 }, to: { row: 4, column: colunasEstoque.length } };
  largura(estoque, [12, 12, 18, 18, 40, 18, 12, 18, 14, 15, 14, 14, 14, 15, 16, 16, 16, 14, 18]);
  estoque.getColumn(9).numFmt = "dd/mm/yyyy";
  for (const coluna of [10, 11, 12, 13, 14, 15]) estoque.getColumn(coluna).numFmt = "#,##0.00";
  for (const coluna of [16, 17]) estoque.getColumn(coluna).numFmt = 'R$ #,##0.00';
  estilizarDados(estoque, 5, colunasEstoque.length);

  if (tipo === "OFICIAL") {
    const analisesOrdenadas = [...analises].sort((a, b) => a.numero_rodada - b.numero_rodada);
    const estoqueAgrupado = new Map<string, { codigo: string; lote: string; descricao: string; armazenado: number }>();
    for (const item of snapshot.itens) {
      const chave = chaveItem(item.codigo, item.lote);
      const atual = estoqueAgrupado.get(chave);
      if (atual) atual.armazenado += Number(item.q_armazenado ?? 0);
      else estoqueAgrupado.set(chave, {
        codigo: item.codigo,
        lote: item.lote ?? "",
        descricao: item.descricao,
        armazenado: Number(item.q_armazenado ?? 0),
      });
    }

    const mapasRodadas = analisesOrdenadas.map((analise) =>
      new Map(analise.itens.map((item) => [chaveItem(item.codigo, item.lote), item])),
    );
    const mapaGestor = new Map<string, ItemAnaliseGestor>();
    for (const item of gestor?.itens ?? []) mapaGestor.set(chaveItem(item.codigo, item.lote), item);

    const chaves = new Set<string>(estoqueAgrupado.keys());
    for (const mapa of mapasRodadas) for (const chave of mapa.keys()) chaves.add(chave);
    for (const chave of mapaGestor.keys()) chaves.add(chave);

    const consolidado = workbook.addWorksheet("Inventário", {
      views: [{ state: "frozen", ySplit: 5, xSplit: 4 }],
      properties: { defaultRowHeight: 20 },
    });

    let ultimaColuna = 4;
    for (const analise of analisesOrdenadas) {
      ultimaColuna += analise.numero_rodada >= 3 ? 3 : 2;
      if (analise.numero_rodada === 5) ultimaColuna += 1;
    }
    const colunaFinalInicio = ultimaColuna + 1;
    ultimaColuna += 5;
    estilizarTitulo(
      consolidado,
      ultimaColuna,
      "Inventário consolidado",
      `${detalhe.codigo_inventario} · ${analisesOrdenadas.length} rodada(s) oficial(is)`,
    );

    consolidado.mergeCells(3, 1, 3, 4);
    consolidado.getCell(3, 1).value = "Estoque de referência";
    let coluna = 5;
    for (const analise of analisesOrdenadas) {
      const quantidadeColunas = (analise.numero_rodada >= 3 ? 3 : 2) + (analise.numero_rodada === 5 ? 1 : 0);
      consolidado.mergeCells(3, coluna, 3, coluna + quantidadeColunas - 1);
      consolidado.getCell(3, coluna).value = ordinal(analise.numero_rodada);
      coluna += quantidadeColunas;
    }
    consolidado.mergeCells(3, colunaFinalInicio, 3, ultimaColuna);
    consolidado.getCell(3, colunaFinalInicio).value = "Inventário final";
    estilizarCabecalho(consolidado, 3, 1, ultimaColuna);

    const cabecalho = ["Código", "Descrição", "Lote", "Armazenado"];
    for (const analise of analisesOrdenadas) {
      if (analise.numero_rodada >= 3) cabecalho.push("Realizou contagem?");
      cabecalho.push("Qtd", "Diferença");
      if (analise.numero_rodada === 5) cabecalho.push("Observação");
    }
    cabecalho.push("Qtd", "Diferença", "Situação final", "Decisão gestor", "Justificativa");
    consolidado.addRow(cabecalho);
    estilizarCabecalho(consolidado, 4, 1, ultimaColuna);

    const chavesOrdenadas = [...chaves].sort((a, b) => a.localeCompare(b, "pt-BR"));
    for (const chave of chavesOrdenadas) {
      const estoqueItem = estoqueAgrupado.get(chave);
      const primeiroItem = mapasRodadas.map((mapa) => mapa.get(chave)).find(Boolean) as ItemAnaliseOficial | undefined;
      const gestorItem = mapaGestor.get(chave);
      const ultimaAnaliseItem = [...mapasRodadas].reverse().map((mapa) => mapa.get(chave)).find(Boolean);
      const codigo = estoqueItem?.codigo ?? primeiroItem?.codigo ?? gestorItem?.codigo ?? "";
      const lote = estoqueItem?.lote ?? primeiroItem?.lote ?? gestorItem?.lote ?? "";
      const descricao = estoqueItem?.descricao ?? primeiroItem?.descricao ?? gestorItem?.descricao ?? "";
      const armazenado = estoqueItem?.armazenado ?? primeiroItem?.qtd_estoque ?? gestorItem?.qtd_estoque ?? 0;
      const valores: Array<string | number | null> = [codigo, descricao ?? "", lote, armazenado];

      for (const [indice, analise] of analisesOrdenadas.entries()) {
        const mapaRodada = mapasRodadas[indice];

        if (!mapaRodada) {
          continue;
        }

        const item = mapaRodada.get(chave);
        const realizou = item != null && !["AGUARDANDO_CONTAGEM", "SEM_CONTAGEM"].includes(String(item.status).toUpperCase());
        if (analise.numero_rodada >= 3) valores.push(realizou ? "Sim" : "Não");
        valores.push(item?.qtd_contada ?? null, item?.diferenca ?? null);
        if (analise.numero_rodada === 5) valores.push(item?.detalhe ?? "");
      }

      const quantidadeFinal = gestorItem?.quantidade_final_gerencial
        ?? (ultimaAnaliseItem?.resultado_definitivo ? ultimaAnaliseItem.qtd_contada : null);
      valores.push(
        quantidadeFinal,
        quantidadeFinal === null ? null : Number(quantidadeFinal) - Number(armazenado),
        gestorItem?.situacao_gerencial ?? ultimaAnaliseItem?.status ?? "",
        gestorItem?.decisao_gestor.decisao ?? "",
        gestorItem?.decisao_gestor.justificativa ?? "",
      );
      consolidado.addRow(valores);
    }
    consolidado.autoFilter = { from: { row: 4, column: 1 }, to: { row: 4, column: ultimaColuna } };
    largura(consolidado, Array.from({ length: ultimaColuna }, (_, i) => i === 1 ? 38 : i < 4 ? 17 : 15));
    estilizarDados(consolidado, 5, ultimaColuna);
    for (let c = 4; c <= ultimaColuna; c += 1) consolidado.getColumn(c).numFmt = "#,##0.00";

    for (const analise of analisesOrdenadas) {
      const planilha = workbook.addWorksheet(`${analise.numero_rodada}_Contagem`, {
        views: [{ state: "frozen", ySplit: 4 }],
        properties: { defaultRowHeight: 20 },
      });
      const cabecalhos = [
        "Código", "Descrição", "Lote", "Unidade", "Categoria", "Qtd estoque",
        "Qtd contada", "Diferença", "Status", "Resultado definitivo?",
        "Localizações bipadas", "Subtipo divergência", "Detalhe / observação",
      ];
      estilizarTitulo(
        planilha,
        cabecalhos.length,
        `${ordinal(analise.numero_rodada)} - ${detalhe.codigo_inventario}`,
        `Status: ${analise.status_rodada} · Regra: ${analise.regra_conciliacao}`,
      );
      planilha.addRow([]);
      planilha.addRow(cabecalhos);
      estilizarCabecalho(planilha, 4, 1, cabecalhos.length);
      for (const item of analise.itens) {
        planilha.addRow([
          item.codigo, item.descricao ?? "", item.lote ?? "", item.unidade ?? "",
          item.categoria ?? "", item.qtd_estoque, item.qtd_contada, item.diferenca,
          item.status, item.resultado_definitivo ? "Sim" : "Não",
          item.localizacoes_bipadas.map((local) => `${local.localizacao}: ${local.quantidade}`).join("; "),
          item.subtipo_divergencia ?? "", item.detalhe ?? "",
        ]);
      }
      planilha.autoFilter = { from: { row: 4, column: 1 }, to: { row: 4, column: cabecalhos.length } };
      largura(planilha, [18, 40, 18, 12, 18, 15, 15, 15, 20, 18, 40, 22, 40]);
      for (const c of [6, 7, 8]) planilha.getColumn(c).numFmt = "#,##0.00";
      estilizarDados(planilha, 5, cabecalhos.length);
    }
  }

  const buffer = await workbook.xlsx.writeBuffer();
  const nomeSeguro = detalhe.codigo_inventario.replace(/[^a-zA-Z0-9_-]+/g, "-");
  const dataArquivo = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  saveAs(
    new Blob([buffer as BlobPart], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }),
    `SGI_${nomeSeguro}_${dataArquivo}.xlsx`,
  );
}
