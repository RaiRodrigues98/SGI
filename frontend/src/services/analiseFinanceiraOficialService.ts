import { consultarSnapshotInventario } from "@/services/inventarioService";
import { buscarRodadasInventario } from "@/services/recontagemService";
import { buscarAnaliseOficial } from "@/services/oficialService";
import { buscarAnaliseGestor } from "@/services/gestorService";
import {
  buscarMovimentacao12Meses,
  buscarResultadoFinalIndicadores,
  buscarValoracaoEstoque,
  type Movimentacao12Meses,
  type ResultadoFinalIndicadores,
} from "@/services/indicadoresService";

type AnaliseOficial = Awaited<
  ReturnType<typeof buscarAnaliseOficial>
>;

type ItemAnaliseOficial =
  AnaliseOficial["itens"][number];

type AnaliseGestor = Awaited<
  ReturnType<typeof buscarAnaliseGestor>
>;

type ItemAnaliseGestor =
  AnaliseGestor["itens"][number];

function chaveItem(
  codigo: string,
  lote: string | null | undefined,
) {
  return `${codigo.trim()}::${String(
    lote ?? "",
  ).trim()}`;
}

export interface AnaliseFinanceiraOficial {
  id_inventario: number;
  codigo_inventario: string;

  resumo: {
    acuracidade_itens_percentual: number;
    acuracidade_quantidade_percentual: number;
    divergencia_financeira_percentual:
      | number
      | null;
    itens_divergentes: number;
  };

  estoque: {
    sistema: {
      quantidade: number;
      valor: number;
    };
    inventario_fisico: {
      quantidade: number;
      valor: number;
    };
    diferenca_liquida: {
      quantidade: number;
      valor: number;
    };
  };

  divergencias: {
    faltas: {
      quantidade: number;
      valor: number;
    };
    sobras: {
      quantidade: number;
      valor: number;
    };
    absoluta: {
      quantidade: number;
      valor: number;
    };
    saldo_liquido: {
      quantidade: number;
      valor: number;
    };
  };

  qualidade: {
    financeiro_completo: boolean;
    itens_sem_custo: number;
    itens_com_custo_fallback: number;
    itens_sem_resultado_final: number;
  };

  movimentacao:
    | Movimentacao12Meses
    | null;

  allowance: {
    volume_total_movimentado_mais_estoque:
      | number
      | null;
    total_perdas:
      | number
      | null;
    total_sobras:
      | number
      | null;
    divergencia_liquida:
      | number
      | null;
    cobertura:
      | number
      | null;
    penalidade:
      | number
      | null;
  };

  resultado_final: ResultadoFinalIndicadores;
}

export async function buscarAnaliseFinanceiraOficial(
  idInventario: number,
): Promise<AnaliseFinanceiraOficial> {
  if (
    !Number.isInteger(idInventario) ||
    idInventario <= 0
  ) {
    throw new Error(
      "Inventario invalido para analise financeira.",
    );
  }

  const [
    snapshot,
    historicoRodadas,
    resultadoFinal,
  ] = await Promise.all([
    consultarSnapshotInventario(idInventario),
    buscarRodadasInventario(idInventario),
    buscarResultadoFinalIndicadores(idInventario),
  ]);

  const tipoInventario = String(
    resultadoFinal.tipo_inventario ?? "",
  )
    .trim()
    .toUpperCase();

  if (tipoInventario !== "OFICIAL") {
    throw new Error(
      "Analise financeira disponivel somente para inventario OFICIAL.",
    );
  }

  const rodadasOrdenadas = [
    ...historicoRodadas.rodadas,
  ].sort(
    (a, b) =>
      a.numero_rodada -
      b.numero_rodada,
  );

  const analises: AnaliseOficial[] =
    await Promise.all(
      rodadasOrdenadas.map((rodada) =>
        buscarAnaliseOficial(
          idInventario,
          rodada.id_rodada,
        ),
      ),
    );

  const [
    gestorResultado,
    movimentacaoResultado,
    valoracaoResultado,
  ] = await Promise.allSettled([
    buscarAnaliseGestor(idInventario),
    buscarMovimentacao12Meses(idInventario),
    buscarValoracaoEstoque(idInventario),
  ]);

  const gestor =
    gestorResultado.status === "fulfilled"
      ? gestorResultado.value
      : null;

  const movimentacao =
    movimentacaoResultado.status === "fulfilled"
      ? movimentacaoResultado.value
      : null;

  const valoracaoEstoque =
    valoracaoResultado.status === "fulfilled"
      ? valoracaoResultado.value
      : null;

  type BaseFinanceira = {
    codigo: string;
    lote: string;
    quantidadeSistema: number;
    valorSistemaConhecido: number;
    quantidadeComCusto: number;
    custoFallback: number | null;
    custoIncompleto: boolean;
  };

  const baseFinanceira =
    new Map<string, BaseFinanceira>();

  for (const item of snapshot.itens) {
    const chave = chaveItem(
      item.codigo,
      item.lote,
    );

    const quantidade = Number(
      item.q_armazenado ?? 0,
    );

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
        atual.custoFallback =
          valorUnitario;
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

  const mapaValoracaoEstoque =
    new Map(
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

  const mapasRodadas =
    analises.map(
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

  const mapaGestor =
    new Map<
      string,
      ItemAnaliseGestor
    >();

  for (const item of gestor?.itens ?? []) {
    mapaGestor.set(
      chaveItem(
        item.codigo,
        item.lote,
      ),
      item,
    );
  }

  const chaves =
    new Set<string>(
      baseFinanceira.keys(),
    );

  for (const mapa of mapasRodadas) {
    for (const chave of mapa.keys()) {
      chaves.add(chave);
    }
  }

  for (const chave of mapaGestor.keys()) {
    chaves.add(chave);
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

  for (const chave of chaves) {
    const base =
      baseFinanceira.get(chave);

    const primeiroItem =
      mapasRodadas
        .map(
          (mapa) =>
            mapa.get(chave),
        )
        .find(Boolean) as
          | ItemAnaliseOficial
          | undefined;

    const ultimoItem =
      [...mapasRodadas]
        .reverse()
        .map(
          (mapa) =>
            mapa.get(chave),
        )
        .find(Boolean) as
          | ItemAnaliseOficial
          | undefined;

    const gestorItem =
      mapaGestor.get(chave);

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

  const diferencaLiquidaQuantidade =
    quantidadeInventarioFisico -
    quantidadeEstoqueSistema;

  const diferencaLiquidaValor =
    valorInventarioFisico -
    valorEstoqueSistema;

  const acuracidadeItensPercentual =
    Number(
      resultadoFinal
        .resumo
        .acuracidade_percentual,
    );

  const acuracidadeQuantidadePercentual =
    (
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
          : 0
    ) * 100;

  const divergenciaFinanceiraPercentual =
    financeiroCompleto
      ? (
          valorEstoqueSistema > 0
            ? (
                valorDivergenciaAbsoluta /
                valorEstoqueSistema
              ) * 100
            : 0
        )
      : null;

  const movimentacaoExpedicao =
    movimentacao
      ?.expedicoes
      .valor ?? null;

  const movimentacaoRecebimento =
    movimentacao
      ?.recebimentos
      .valor ?? null;

  const volumeTotalMovimentadoMaisEstoque =
    financeiroCompleto &&
    movimentacaoExpedicao !== null &&
    movimentacaoRecebimento !== null
      ? (
          movimentacaoExpedicao +
          movimentacaoRecebimento +
          valorEstoqueSistema
        )
      : null;

  const totalPerdas =
    financeiroCompleto
      ? -Math.abs(valorFaltas)
      : null;

  const totalSobras =
    financeiroCompleto
      ? -Math.abs(valorSobras)
      : null;

  const divergenciaLiquidaAllowance =
    totalPerdas !== null &&
    totalSobras !== null
      ? (
          totalPerdas +
          totalSobras
        )
      : null;

  const cobertura =
    volumeTotalMovimentadoMaisEstoque !== null
      ? (
          volumeTotalMovimentadoMaisEstoque *
          0.005
        )
      : null;

  const penalidade =
    divergenciaLiquidaAllowance !== null &&
    cobertura !== null
      ? (
          divergenciaLiquidaAllowance +
            cobertura >=
          0
            ? 0
            : (
                divergenciaLiquidaAllowance +
                cobertura
              )
        )
      : null;

  return {
    id_inventario: idInventario,
    codigo_inventario:
      resultadoFinal.codigo_inventario,

    resumo: {
      acuracidade_itens_percentual:
        acuracidadeItensPercentual,
      acuracidade_quantidade_percentual:
        acuracidadeQuantidadePercentual,
      divergencia_financeira_percentual:
        divergenciaFinanceiraPercentual,
      itens_divergentes:
        resultadoFinal.resumo.divergencias,
    },

    estoque: {
      sistema: {
        quantidade:
          quantidadeEstoqueSistema,
        valor:
          valorEstoqueSistema,
      },
      inventario_fisico: {
        quantidade:
          quantidadeInventarioFisico,
        valor:
          valorInventarioFisico,
      },
      diferenca_liquida: {
        quantidade:
          diferencaLiquidaQuantidade,
        valor:
          diferencaLiquidaValor,
      },
    },

    divergencias: {
      faltas: {
        quantidade:
          quantidadeFaltas,
        valor:
          valorFaltas,
      },
      sobras: {
        quantidade:
          quantidadeSobras,
        valor:
          valorSobras,
      },
      absoluta: {
        quantidade:
          quantidadeDivergenciaAbsoluta,
        valor:
          valorDivergenciaAbsoluta,
      },
      saldo_liquido: {
        quantidade:
          quantidadeSaldoLiquido,
        valor:
          valorSaldoLiquido,
      },
    },

    qualidade: {
      financeiro_completo:
        financeiroCompleto,
      itens_sem_custo:
        itensSemCusto,
      itens_com_custo_fallback:
        itensComCustoFallback,
      itens_sem_resultado_final:
        itensSemResultadoFinal,
    },

    movimentacao,

    allowance: {
      volume_total_movimentado_mais_estoque:
        volumeTotalMovimentadoMaisEstoque,
      total_perdas:
        totalPerdas,
      total_sobras:
        totalSobras,
      divergencia_liquida:
        divergenciaLiquidaAllowance,
      cobertura,
      penalidade,
    },

    resultado_final:
      resultadoFinal,
  };
}
