/**
 * Serviço isolado do Mapa 3D do Estoque.
 *
 * Toda a tela consome os dados por aqui. No futuro, basta trocar a
 * implementação interna por chamadas ao SGI mantendo a mesma assinatura.
 */

import {
  DAMAGE_AREA,
  FACES,
  MODULOS_POR_FACE,
  NIVEIS_POR_MODULO,
  POSICOES_POR_NIVEL,
  generateLocations,
  type DamageArea,
  type WarehouseLocation,
} from "@/data/warehouseData";
import {
  consultarInventarioDetalhe,
  consultarSnapshotInventario,
  listarEstoqueAtual,
} from "@/services/inventarioService";
import {
  buscarAnaliseOficial,
  buscarRodadaAtualOficial,
} from "@/services/oficialService";
import {
  buscarSugestoesCicloRotativo,
  buscarAnaliseRotativo,
  type SugestaoCicloRotativo,
} from "@/services/rotativoService";
import {
  buscarAnaliseRecontagem,
} from "@/services/recontagemService";


export interface WarehouseSummary {
  totalPosicoes: number;
  totalModulos: number;
  porRua: Record<string, number>;
  modulosPorRua: Record<string, number>;
}

export interface ValidationResult {
  ok: boolean;
  checks: { label: string; expected: string; received: string; ok: boolean }[];
}

let cache: WarehouseLocation[] | null = null;

export function getLocations(): WarehouseLocation[] {
  if (!cache) cache = generateLocations();
  return cache;
}

export function getDamageArea(): DamageArea {
  return DAMAGE_AREA;
}

export function getSummary(): WarehouseSummary {
  const locations = getLocations();
  const porRua: Record<string, number> = {};
  const modulos = new Set<string>();
  const modulosPorRua: Record<string, number> = {};

  for (const l of locations) {
    porRua[l.rua] = (porRua[l.rua] ?? 0) + 1;
    modulos.add(`${l.rua}-${l.modulo}`);
  }
  for (const key of modulos) {
    const rua = key.split("-")[0] ?? "";
    modulosPorRua[rua] = (modulosPorRua[rua] ?? 0) + 1;
  }

  return {
    totalPosicoes: locations.length,
    totalModulos: modulos.size,
    porRua,
    modulosPorRua,
  };
}

/** Normaliza a busca: aceita espaços, traços e minúsculas. */
export function normalizeCode(query: string): string {
  return query.replace(/[\s\-._/]/g, "").toUpperCase();
}

export function findLocation(query: string): WarehouseLocation | null {
  const code = normalizeCode(query);
  if (!code) return null;
  return getLocations().find((l) => l.code === code) ?? null;
}

export function isDamageAreaQuery(query: string): boolean {
  return normalizeCode(query) === DAMAGE_AREA.code;
}


export type WarehouseMapViewType =
  | "estoque-atual"
  | "estoque-inventario"
  | "divergencia";

export interface WarehouseMapRealSummary {
  totalPosicoes: number;
  ocupadas: number;
  livres: number;
  registrosEstoque: number;
  registrosInventario: number;
  localizacoesForaLayout: number;
  divergencias: number;
  recontagem: number;
}

export interface WarehouseTop20Detail {
  ordem: number;
  localizacao: string;
  status: string;

  prioridade: number | null;
  scoreRisco: number | null;
  classificacaoRisco: string | null;

  tipoSugestao: string | null;
  motivoPrincipal: string | null;

  ultimaContagem: string | null;
  idInventarioUltimaContagem: number | null;
  idRodadaUltimaContagem: number | null;

  dadosCiclo: SugestaoCicloRotativo["dados_ciclo"];
}


export interface WarehouseTop20Result {
  localizacoesTop20: string[];
  top20Detalhes: WarehouseTop20Detail[];
  avisoTop20: string | null;
}


export async function buscarTop20ArmazemCliente(
  clienteId: number,
  armazem: string,
  limite = 20,
): Promise<WarehouseTop20Result> {
  if (
    !Number.isInteger(
      clienteId,
    ) ||
    clienteId <= 0
  ) {
    return {
      localizacoesTop20: [],
      top20Detalhes: [],
      avisoTop20:
        "Cliente inv\u00e1lido para consultar o ranking.",
    };
  }

  const armazemNormalizado =
    armazem
      .trim()
      .toUpperCase();

  if (
    !armazemNormalizado
  ) {
    return {
      localizacoesTop20: [],
      top20Detalhes: [],
      avisoTop20:
        "Armaz\u00e9m inv\u00e1lido para consultar o ranking.",
    };
  }

  try {
    const ranking =
      await buscarSugestoesCicloRotativo(
        clienteId,
        armazemNormalizado,
        limite,
      );

    if (
      !ranking.possui_ciclo_aberto
    ) {
      return {
        localizacoesTop20: [],
        top20Detalhes: [],
        avisoTop20:
          "Nenhum ciclo rotativo aberto para este cliente no armaz\u00e9m.",
      };
    }

    const sugestoes = [
      ...(ranking.sugestao_principal
        ? [
            ranking.sugestao_principal,
          ]
        : []),

      ...ranking.proximas_sugestoes,
    ];

    const top20Detalhes:
      WarehouseTop20Detail[] =
        sugestoes
          .slice(
            0,
            limite,
          )
          .map(
            (
              sugestao,
              index,
            ) => ({
              ordem:
                index + 1,

              localizacao:
                normalizeCode(
                  sugestao.localizacao,
                ),

              status:
                sugestao.status,

              prioridade:
                sugestao.prioridade,

              scoreRisco:
                sugestao.score_risco,

              classificacaoRisco:
                sugestao.classificacao_risco,

              tipoSugestao:
                sugestao.tipo_sugestao,

              motivoPrincipal:
                sugestao.motivo_principal,

              ultimaContagem:
                sugestao.ultima_contagem,

              idInventarioUltimaContagem:
                sugestao.id_inventario_ultima_contagem,

              idRodadaUltimaContagem:
                sugestao.id_rodada_ultima_contagem,

              dadosCiclo:
                sugestao.dados_ciclo,
            }),
          )
          .filter(
            (
              sugestao,
            ) =>
              sugestao.localizacao.length >
              0,
          );

    const localizacoesTop20 =
      Array.from(
        new Set(
          top20Detalhes.map(
            (
              sugestao,
            ) =>
              normalizeCode(
                sugestao.localizacao,
              ),
          ),
        ),
      ).slice(
        0,
        limite,
      );

    return {
      localizacoesTop20,
      top20Detalhes,
      avisoTop20: null,
    };
  } catch (erro) {
    return {
      localizacoesTop20: [],
      top20Detalhes: [],
      avisoTop20:
        erro instanceof Error
          ? erro.message
          : "N\u00e3o foi poss\u00edvel consultar o ranking Top 20.",
    };
  }
}


export interface WarehouseMapRealResult {
  locations: WarehouseLocation[];

  armazem: string;

  tipoInventario: "ROTATIVO" | "OFICIAL";

  /**
   * Cliente usado para consultar o ranking rotativo.
   */
  clienteInventarioId: number;

  localizacoesTop20: string[];

  /**
   * Ranking completo das localizacoes priorizadas.
   * Mantem os dados recebidos do ciclo rotativo
   * para uso no painel do Mapa 3D.
   */
  top20Detalhes: WarehouseTop20Detail[];

  avisoTop20: string | null;

  visoes: {
    estoqueAtual: WarehouseLocation[];
    estoqueInventario: WarehouseLocation[];
    divergencia: WarehouseLocation[];
  };

  resumo: WarehouseMapRealSummary;

  atualizadoEm: string;

  snapshotDisponivel: boolean;
  avisoSnapshot: string | null;

  divergenciasDisponiveis: boolean;
  avisoDivergencias: string | null;
}

function limparDadosSimulados(
  location: WarehouseLocation,
): WarehouseLocation {
  return {
    ...location,
    status: "livre",
    produto: null,
    lote: null,
    quantidade: 0,
    itensEstoque: [],
    itensContados: [],
  };
}


function chaveProdutoLote(
  codigo: string | null | undefined,
  lote: string | null | undefined,
): string {
  return [
    String(codigo ?? "").trim().toUpperCase(),
    String(lote ?? "").trim().toUpperCase(),
  ].join("|");
}

function possuiDivergencia(
  status: string | null | undefined,
  diferenca: number | null | undefined,
): boolean {
  const valorDiferenca =
    Number(diferenca ?? 0);

  if (
    Number.isFinite(valorDiferenca) &&
    valorDiferenca !== 0
  ) {
    return true;
  }

  const statusNormalizado =
    String(status ?? "")
      .trim()
      .toUpperCase();

  return (
    statusNormalizado.includes("DIVERG") ||
    statusNormalizado.includes("FALTA") ||
    statusNormalizado.includes("SOBRA") ||
    statusNormalizado.includes("INCORRETA") ||
    statusNormalizado.includes("INCORRETO")
  );
}

function marcarDivergencia(
  porCodigo: Map<string, WarehouseLocation>,
  localizacao: string | null | undefined,
  recontagem: boolean,
  foraLayout: Set<string>,
): void {
  const codigoLocalizacao =
    normalizeCode(
      String(localizacao ?? ""),
    );

  if (
    !codigoLocalizacao ||
    codigoLocalizacao === "R02AVARIA"
  ) {
    return;
  }

  const location =
    porCodigo.get(codigoLocalizacao);

  if (!location) {
    foraLayout.add(codigoLocalizacao);
    return;
  }

  if (recontagem) {
    location.status = "recontagem";
    return;
  }

  if (
    location.status !== "recontagem"
  ) {
    location.status = "divergencia";
  }
}

function obterArmazemDoInventario(
  inventario: unknown,
): string {
  if (
    typeof inventario !== "object" ||
    inventario === null
  ) {
    throw new Error(
      "Nao foi possivel identificar o armazem do inventario.",
    );
  }


  const dados =
    inventario as Record<
      string,
      unknown
    >;


  const candidatos = [
    dados["armazem"],
    dados["c_armazem"],
    dados["cArmazem"],
    dados["cArmazemCodigo"],
  ];


  const encontrado =
    candidatos.find(
      (valor) =>
        typeof valor ===
          "string" &&
        valor.trim().length >
          0,
    );


  if (
    typeof encontrado !==
    "string"
  ) {
    throw new Error(
      "Armazem do inventario nao localizado.",
    );
  }


  return encontrado.trim();
}



/*
 * MAPA_ESTOQUE_ARMAZEM_INDEPENDENTE_V1
 *
 * Estoque fisico do armazem nao depende
 * da existencia de inventario.
 */
export interface WarehouseMapArmazemResult {
  armazem: string;

  locations:
    WarehouseLocation[];

  resumo: {
    totalPosicoes: number;
    ocupadas: number;
    livres: number;
    registrosEstoque: number;
    localizacoesForaLayout: number;
  };

  atualizadoEm: string;
}


export async function buscarMapaEstoqueArmazem(
  armazem: string,
): Promise<WarehouseMapArmazemResult> {
  const armazemNormalizado =
    armazem
      .trim()
      .toUpperCase();

  if (!armazemNormalizado) {
    throw new Error(
      "Armazem invalido.",
    );
  }


  const estoque =
    await listarEstoqueAtual(
      armazemNormalizado,
    );


  const locationsEstoqueAtual =
    getLocations().map(
      limparDadosSimulados,
    );

  /*
   * Visao 2:
   * snapshot congelado do inventario.
   */
  const locationsEstoqueInventario =
    getLocations().map(
      limparDadosSimulados,
    );


  const porCodigoAtual =
    new Map(
      locationsEstoqueAtual.map(
        (location) => [
          location.code,
          location,
        ],
      ),
    );

  const porCodigoInventario =
    new Map(
      locationsEstoqueInventario.map(
        (location) => [
          location.code,
          location,
        ],
      ),
    );

  const foraLayout =
    new Set<string>();


  /*
   * Associa um resultado de contagem somente
   * a visao Estoque do Inventario.
   *
   * Nao altera snapshot, estoque atual ou status.
   */
  function adicionarItemContado(
    localizacao:
      string | null | undefined,
    item:
      NonNullable<
        WarehouseLocation[
          "itensContados"
        ]
      >[number],
  ): void {
    const codigoLocalizacao =
      normalizeCode(
        String(
          localizacao ?? "",
        ),
      );

    if (
      !codigoLocalizacao ||
      codigoLocalizacao ===
        "R02AVARIA"
    ) {
      return;
    }

    const location =
      porCodigoInventario.get(
        codigoLocalizacao,
      );

    if (!location) {
      foraLayout.add(
        codigoLocalizacao,
      );

      return;
    }

    if (
      !location.itensContados
    ) {
      location.itensContados =
        [];
    }

    location.itensContados.push(
      item,
    );
  }


  // ==========================================================
  // ESTOQUE ATUAL
  // ==========================================================

  for (const item of estoque.itens) {
    const codigoLocalizacao =
      normalizeCode(
        item.localizacao,
      );

    if (
      codigoLocalizacao ===
      "R02AVARIA"
    ) {
      continue;
    }

    const location =
      porCodigoAtual.get(
        codigoLocalizacao,
      );

    if (!location) {
      if (codigoLocalizacao) {
        foraLayout.add(
          codigoLocalizacao,
        );
      }

      continue;
    }

    const quantidade =
      Number(
        item.q_armazenado ?? 0,
      );


    const quantidadeFisica =
      Number.isFinite(
        quantidade,
      )
        ? quantidade
        : 0;


    location.itensEstoque ??= [];


    location.itensEstoque.push({
      clienteId:
        item.cliente_id,

      cliente:
        item.cliente?.trim() ||
        `Cliente ${item.cliente_id}`,

      codigo:
        item.codigo,

      descricao:
        item.descricao,

      lote:
        item.lote,

      quantidade:
        quantidadeFisica,

      unidade:
        item.unidade,

      categoria:
        item.categoria,

      validade:
        item.validade,

      reservado:
        Number.isFinite(
          Number(
            item.q_reservado ??
            0,
          ),
        )
          ? Number(
              item.q_reservado ??
              0,
            )
          : 0,

      bloqueado:
        Number.isFinite(
          Number(
            item.q_bloqueado ??
            0,
          ),
        )
          ? Number(
              item.q_bloqueado ??
              0,
            )
          : 0,

      estimado:
        Number.isFinite(
          Number(
            item.q_estimado ??
            0,
          ),
        )
          ? Number(
              item.q_estimado ??
              0,
            )
          : 0,

      disponivel:
        Number.isFinite(
          Number(
            item.saldo_disponivel ??
            0,
          ),
        )
          ? Number(
              item.saldo_disponivel ??
              0,
            )
          : 0,

      statusEstoque:
        item.status_estoque,

      tipoLocalizacao:
        item.tipo_localizacao,
    });

    location.quantidade +=
      Number.isFinite(
        quantidade,
      )
        ? quantidade
        : 0;

    if (!location.produto) {
      location.produto =
        item.descricao?.trim() ||
        item.codigo;
    } else if (
      !location.produto.includes(
        item.descricao ?? "",
      )
    ) {
      location.produto =
        `${location.produto} (+ outros itens)`;
    }

    if (
      !location.lote &&
      item.lote
    ) {
      location.lote =
        item.lote;
    }

    location.status =
      "ocupada";
  }


  // ==========================================================
  // ESTOQUE DO INVENTARIO / SNAPSHOT
  // ==========================================================



  void locationsEstoqueInventario;
  void porCodigoInventario;

  const ocupadas =
    locationsEstoqueAtual.filter(
      (location) =>
        location.quantidade !== 0 ||
        location.produto !== null,
    ).length;


  return {
    armazem:
      estoque.armazem?.trim() ||
      armazemNormalizado,

    locations:
      locationsEstoqueAtual,

    resumo: {
      totalPosicoes:
        locationsEstoqueAtual.length,

      ocupadas,

      livres:
        locationsEstoqueAtual.length -
        ocupadas,

      registrosEstoque:
        estoque.itens.length,

      localizacoesForaLayout:
        foraLayout.size,
    },

    atualizadoEm:
      new Date().toISOString(),
  };
}


export async function buscarMapaEstoqueReal(
  idInventario: number,
): Promise<WarehouseMapRealResult> {
  if (
    !Number.isInteger(idInventario) ||
    idInventario <= 0
  ) {
    throw new Error(
      "Selecione um invent\u00e1rio v\u00e1lido.",
    );
  }

  /*
   * Primeiro identificamos o inventario apenas
   * para obter o armazem e continuar suportando
   * snapshot/divergencias.
   */
  const inventario =
    await consultarInventarioDetalhe(
      idInventario,
    );

  console.warn(
    "[SGI MAPA DEBUG] INVENTARIO",
    {
      idInventario,
      tipo: inventario.tipo,
      inventario,
    },
  );



  // MAPA_ESTOQUE_ARMAZEM_INDEPENDENTE_V1 - INVENTARIO_ABERTO
  const dadosInventarioMapa =
    inventario as unknown as Record<
      string,
      unknown
    >;

  const statusInventarioMapa =
    String(
      dadosInventarioMapa["status"] ??
      dadosInventarioMapa["status_inventario"] ??
      "",
    )
      .trim()
      .toUpperCase();

  if (
    statusInventarioMapa &&
    statusInventarioMapa !==
      "ABERTO"
  ) {
    throw new Error(
      "Inventario nao esta aberto.",
    );
  }


  const armazem =
    obterArmazemDoInventario(
      inventario,
    );


  /*
   * ==========================================================
   * TOP 20 DE POSICOES PRIORIZADAS
   * ==========================================================
   *
   * Consulta somente leitura.
   *
   * Nao altera:
   * - ciclo
   * - inventario
   * - estoque
   * - escopo
   * - snapshot
   */
  let localizacoesTop20:
    string[] = [];

  let top20Detalhes:
    WarehouseTop20Detail[] = [];

  let avisoTop20:
    string | null = null;


  if (
    inventario.tipo ===
    "ROTATIVO"
  ) {
    try {
      const ranking =
        await buscarSugestoesCicloRotativo(
          inventario.cliente_id,
          armazem,
          20,
        );


      if (
        !ranking.possui_ciclo_aberto
      ) {
        avisoTop20 =
          "Nenhum ciclo rotativo aberto para consultar o ranking.";
      } else {
        const sugestoes = [
          ...(ranking.sugestao_principal
            ? [
                ranking.sugestao_principal,
              ]
            : []),

          ...ranking.proximas_sugestoes,
        ];


        top20Detalhes =
          sugestoes
            .slice(
              0,
              20,
            )
            .map(
              (
                sugestao,
                index,
              ) => ({
                ordem:
                  index + 1,

                localizacao:
                  normalizeCode(
                    sugestao.localizacao,
                  ),

                status:
                  sugestao.status,

                prioridade:
                  sugestao.prioridade,

                scoreRisco:
                  sugestao.score_risco,

                classificacaoRisco:
                  sugestao.classificacao_risco,

                tipoSugestao:
                  sugestao.tipo_sugestao,

                motivoPrincipal:
                  sugestao.motivo_principal,

                ultimaContagem:
                  sugestao.ultima_contagem,

                idInventarioUltimaContagem:
                  sugestao.id_inventario_ultima_contagem,

                idRodadaUltimaContagem:
                  sugestao.id_rodada_ultima_contagem,

                dadosCiclo:
                  sugestao.dados_ciclo,
              }),
            )
            .filter(
              (
                sugestao,
              ) =>
                sugestao.localizacao
                  .length >
                0,
            );


        localizacoesTop20 =
          Array.from(
            new Set(
              top20Detalhes
                .map(
                  (
                    sugestao,
                  ) =>
                    normalizeCode(
                      sugestao.localizacao,
                    ),
                )
                .filter(
                  (
                    localizacao,
                  ) =>
                    localizacao.length >
                    0,
                ),
            ),
          ).slice(
            0,
            20,
          );
      }
    } catch (erro) {
      avisoTop20 =
        erro instanceof Error
          ? erro.message
          : "Nao foi possivel carregar o ranking das posicoes.";
    }
  }


  /*
   * IMPORTANTE:
   *
   * Estoque atual nao depende mais do cliente
   * nem do escopo do inventario.
   *
   * Aqui carregamos todo o estoque fisico
   * corrente do armazem.
   */
  const estoque =
    await listarEstoqueAtual(
      armazem,
    );

  let snapshot:
    Awaited<
      ReturnType<
        typeof consultarSnapshotInventario
      >
    > | null = null;

  let avisoSnapshot:
    string | null = null;

  try {
    snapshot =
      await consultarSnapshotInventario(
        idInventario,
      );
  } catch (erro) {
    avisoSnapshot =
      erro instanceof Error
        ? erro.message
        : "N\u00e3o foi poss\u00edvel carregar o estoque do invent\u00e1rio.";
  }

  /*
   * Visao 1:
   * estoque atual consultado no SGI/WMS.
   */
  const locationsEstoqueAtual =
    getLocations().map(
      limparDadosSimulados,
    );

  /*
   * Visao 2:
   * snapshot congelado do inventario.
   */
  const locationsEstoqueInventario =
    getLocations().map(
      limparDadosSimulados,
    );


  const porCodigoAtual =
    new Map(
      locationsEstoqueAtual.map(
        (location) => [
          location.code,
          location,
        ],
      ),
    );

  const porCodigoInventario =
    new Map(
      locationsEstoqueInventario.map(
        (location) => [
          location.code,
          location,
        ],
      ),
    );

  const foraLayout =
    new Set<string>();


  /*
   * Associa um resultado de contagem somente
   * a visao Estoque do Inventario.
   *
   * Nao altera snapshot, estoque atual ou status.
   */
  function adicionarItemContado(
    localizacao:
      string | null | undefined,
    item:
      NonNullable<
        WarehouseLocation[
          "itensContados"
        ]
      >[number],
  ): void {
    const codigoLocalizacao =
      normalizeCode(
        String(
          localizacao ?? "",
        ),
      );

    if (
      !codigoLocalizacao ||
      codigoLocalizacao ===
        "R02AVARIA"
    ) {
      return;
    }

    const location =
      porCodigoInventario.get(
        codigoLocalizacao,
      );

    if (!location) {
      foraLayout.add(
        codigoLocalizacao,
      );

      return;
    }

    if (
      !location.itensContados
    ) {
      location.itensContados =
        [];
    }

    location.itensContados.push(
      item,
    );
  }


  // ==========================================================
  // ESTOQUE ATUAL
  // ==========================================================

  for (const item of estoque.itens) {
    const codigoLocalizacao =
      normalizeCode(
        item.localizacao,
      );

    if (
      codigoLocalizacao ===
      "R02AVARIA"
    ) {
      continue;
    }

    const location =
      porCodigoAtual.get(
        codigoLocalizacao,
      );

    if (!location) {
      if (codigoLocalizacao) {
        foraLayout.add(
          codigoLocalizacao,
        );
      }

      continue;
    }

    const quantidade =
      Number(
        item.q_armazenado ?? 0,
      );


    const quantidadeFisica =
      Number.isFinite(
        quantidade,
      )
        ? quantidade
        : 0;


    location.itensEstoque ??= [];


    location.itensEstoque.push({
      clienteId:
        item.cliente_id,

      cliente:
        item.cliente?.trim() ||
        `Cliente ${item.cliente_id}`,

      codigo:
        item.codigo,

      descricao:
        item.descricao,

      lote:
        item.lote,

      quantidade:
        quantidadeFisica,

      unidade:
        item.unidade,

      categoria:
        item.categoria,

      validade:
        item.validade,

      reservado:
        Number.isFinite(
          Number(
            item.q_reservado ??
            0,
          ),
        )
          ? Number(
              item.q_reservado ??
              0,
            )
          : 0,

      bloqueado:
        Number.isFinite(
          Number(
            item.q_bloqueado ??
            0,
          ),
        )
          ? Number(
              item.q_bloqueado ??
              0,
            )
          : 0,

      estimado:
        Number.isFinite(
          Number(
            item.q_estimado ??
            0,
          ),
        )
          ? Number(
              item.q_estimado ??
              0,
            )
          : 0,

      disponivel:
        Number.isFinite(
          Number(
            item.saldo_disponivel ??
            0,
          ),
        )
          ? Number(
              item.saldo_disponivel ??
              0,
            )
          : 0,

      statusEstoque:
        item.status_estoque,

      tipoLocalizacao:
        item.tipo_localizacao,
    });

    location.quantidade +=
      Number.isFinite(
        quantidade,
      )
        ? quantidade
        : 0;

    if (!location.produto) {
      location.produto =
        item.descricao?.trim() ||
        item.codigo;
    } else if (
      !location.produto.includes(
        item.descricao ?? "",
      )
    ) {
      location.produto =
        `${location.produto} (+ outros itens)`;
    }

    if (
      !location.lote &&
      item.lote
    ) {
      location.lote =
        item.lote;
    }

    location.status =
      "ocupada";
  }


  // ==========================================================
  // ESTOQUE DO INVENTARIO / SNAPSHOT
  // ==========================================================

  if (snapshot) {
    for (
      const item
      of snapshot.itens
    ) {
      const codigoLocalizacao =
        normalizeCode(
          item.localizacao,
        );

      if (
        codigoLocalizacao ===
        "R02AVARIA"
      ) {
        continue;
      }

      const location =
        porCodigoInventario.get(
          codigoLocalizacao,
        );

      if (!location) {
        if (
          codigoLocalizacao
        ) {
          foraLayout.add(
            codigoLocalizacao,
          );
        }

        continue;
      }

      /*
       * O snapshot pode evoluir sem quebrar
       * o mapa. Estes campos sao tratados
       * como alternativas.
       */
      const extras =
        item as {
          descricao?:
            string | null;

          saldo_inventario?:
            number | null;

          quantidade?:
            number | null;

          q_armazenado?:
            number | null;
        };

      const quantidade =
        Number(
          extras.saldo_inventario ??
          extras.quantidade ??
          extras.q_armazenado ??
          0,
        );

      location.quantidade +=
        Number.isFinite(
          quantidade,
        )
          ? quantidade
          : 0;

      const produto =
        extras.descricao?.trim() ||
        item.codigo;

      if (
        !location.produto
      ) {
        location.produto =
          produto;
      } else if (
        produto &&
        !location.produto.includes(
          produto,
        )
      ) {
        location.produto =
          `${location.produto} (+ outros itens)`;
      }

      if (
        !location.lote &&
        item.lote
      ) {
        location.lote =
          item.lote;
      }

      /*
       * Mesmo que a quantidade seja zero,
       * a existencia do item no snapshot
       * caracteriza uma referencia de estoque.
       */
      location.status =
        "ocupada";
    }
  }


  // ==========================================================
  // DIVERGENCIAS / RECONTAGEM
  // ==========================================================

  let divergenciasDisponiveis =
    false;

  let avisoDivergencias:
    string | null = null;


  function marcarNasVisoes(
    localizacao:
      string | null | undefined,
    recontagem: boolean,
  ) {

    // DIVERGENCIA_VISUAL_SOMENTE_ROTATIVO
    if (
      inventario.tipo !==
      "ROTATIVO"
    ) {
      return;
    }

    /*
     * O status operacional pertence somente
     * ao snapshot do inventario.
     *
     * Estoque do Armazem permanece representando
     * exclusivamente o estoque fisico atual.
     */


    marcarDivergencia(
      porCodigoInventario,
      localizacao,
      recontagem,
      foraLayout,
    );
  }


  try {
    if (
      inventario.tipo ===
      "ROTATIVO"
    ) {
      const analise =
        await buscarAnaliseRotativo(
          idInventario,
        );


      // MAPA_ITENS_CONTADOS_ROTATIVO
      for (
        const item
        of analise.itens
      ) {
        const status =
          String(
            item.status ?? "",
          )
            .trim()
            .toUpperCase();

        /*
         * Aguardando contagem ainda nao
         * representa resultado operacional.
         */
        if (
          status ===
          "AGUARDANDO_CONTAGEM"
        ) {
          continue;
        }

        const quantidade =
          Number(
            item.qtd_contada ??
            0,
          );

        const qtdEstoque =
          Number(
            item.qtd_estoque ??
            0,
          );

        const diferenca =
          Number(
            item.diferenca ??
            0,
          );

        adicionarItemContado(
          item.localizacao,
          {
            codigo:
              item.codigo,

            descricao:
              item.produto,

            lote:
              item.lote?.trim() ||
              null,

            quantidade:
              Number.isFinite(
                quantidade,
              )
                ? quantidade
                : 0,

            status:
              item.status,

            qtdEstoque:
              Number.isFinite(
                qtdEstoque,
              )
                ? qtdEstoque
                : 0,

            diferenca:
              Number.isFinite(
                diferenca,
              )
                ? diferenca
                : 0,
          },
        );
      }

      for (
        const item
        of analise.itens
      ) {
        if (
          !possuiDivergencia(
            item.status,
            item.diferenca,
          ) &&
          !item.pendente_recontagem
        ) {
          continue;
        }

        const localizacoes =
          new Set<string>([
            item.localizacao,
            ...(
              item.localizacoes_esperadas ??
              []
            ),
          ]);

        for (
          const localizacao
          of localizacoes
        ) {
          marcarNasVisoes(
            localizacao,
            item.pendente_recontagem ||
              analise.numero_rodada >= 2,
          );
        }
      }

      divergenciasDisponiveis =
        true;
    } else {
      /*
       * No oficial o snapshot e necessario
       * para recuperar as localizacoes esperadas.
       */
      if (!snapshot) {
        throw new Error(
          "O snapshot do invent\u00e1rio n\u00e3o est\u00e1 dispon\u00edvel para calcular as diverg\u00eancias.",
        );
      }

      const snapshotPorItem =
        new Map<
          string,
          Set<string>
        >();

      for (
        const item
        of snapshot.itens
      ) {
        const chave =
          chaveProdutoLote(
            item.codigo,
            item.lote,
          );

        const localizacoes =
          snapshotPorItem.get(
            chave,
          ) ??
          new Set<string>();

        localizacoes.add(
          item.localizacao,
        );

        snapshotPorItem.set(
          chave,
          localizacoes,
        );
      }

      const rodada =
        await buscarRodadaAtualOficial(
          idInventario,
        );

      const analise =
        await buscarAnaliseOficial(
          idInventario,
          rodada.id_rodada,
        );


      // MAPA_ITENS_CONTADOS_OFICIAL
      for (
        const item
        of analise.itens
      ) {
        const status =
          String(
            item.status ?? "",
          )
            .trim()
            .toUpperCase();

        if (
          status ===
          "AGUARDANDO_CONTAGEM"
        ) {
          continue;
        }

        const qtdEstoque =
          Number(
            item.qtd_estoque ??
            0,
          );

        const diferenca =
          Number(
            item.diferenca ??
            0,
          );

        /*
         * No OFICIAL, a fonte correta para
         * localizar o que foi efetivamente
         * bipado e a lista localizacoes_bipadas.
         *
         * A quantidade usada e a quantidade
         * especifica daquela localizacao.
         */
        for (
          const localizacaoBipada
          of (
            item.localizacoes_bipadas ??
            []
          )
        ) {
          const quantidade =
            Number(
              localizacaoBipada
                .quantidade ??
              0,
            );

          adicionarItemContado(
            localizacaoBipada
              .localizacao,
            {
              codigo:
                item.codigo,

              descricao:
                item.descricao,

              lote:
                item.lote?.trim() ||
                null,

              quantidade:
                Number.isFinite(
                  quantidade,
                )
                  ? quantidade
                  : 0,

              status:
                item.status,

              qtdEstoque:
                Number.isFinite(
                  qtdEstoque,
                )
                  ? qtdEstoque
                  : 0,

              diferenca:
                Number.isFinite(
                  diferenca,
                )
                  ? diferenca
                  : 0,
            },
          );
        }
      }

      console.warn(
        "[SGI MAPA DEBUG] ANALISE OFICIAL",
        {
          idInventario,
          idRodada:
            rodada.id_rodada,
          numeroRodada:
            rodada.numero_rodada,
          itens:
            analise.itens.map(
              (item) => ({
                codigo:
                  item.codigo,
                lote:
                  item.lote,
                status:
                  item.status,
                diferenca:
                  item.diferenca,
                localizacoes_bipadas:
                  (
                    item.localizacoes_bipadas ??
                    []
                  ).map(
                    (localizacao) =>
                      localizacao.localizacao,
                  ),
              }),
            ),
        },
      );

      console.group(
        "[MAPA 3D] ANALISE OFICIAL",
      );

      console.log(
        "Inventario:",
        idInventario,
      );

      console.log(
        "Rodada:",
        rodada.id_rodada,
      );

      console.table(
        analise.itens.map(
          (item) => ({
            codigo:
              item.codigo,
            lote:
              item.lote,
            status:
              item.status,
            diferenca:
              item.diferenca,
            localizacoes_bipadas:
              (
                item.localizacoes_bipadas ??
                []
              )
                .map(
                  (localizacao) =>
                    localizacao.localizacao,
                )
                .join(", "),
          }),
        ),
      );

      console.groupEnd();

      for (
        const item
        of analise.itens
      ) {
        if (
          !possuiDivergencia(
            item.status,
            item.diferenca,
          )
        ) {
          continue;
        }

        /*
         * A divergencia deve ser associada a localizacao
         * fisicamente observada sempre que houver bipagem.
         *
         * Nao somamos automaticamente todas as posicoes
         * do snapshot com o mesmo Codigo + Lote, pois isso
         * propagava uma divergencia para enderecos que
         * poderiam estar corretos.
         *
         * Fallback:
         * quando nao existe nenhuma localizacao bipada
         * (ex.: item em FALTA), usamos as localizacoes
         * esperadas registradas no snapshot.
         */
        const localizacoesBipadas =
          new Set<string>();

        for (
          const localizacaoBipada
          of (
            item.localizacoes_bipadas ??
            []
          )
        ) {
          const localizacao =
            String(
              localizacaoBipada.localizacao ??
              "",
            ).trim();

          if (localizacao) {
            localizacoesBipadas.add(
              localizacao,
            );
          }
        }

        const localizacoesEsperadas =
          snapshotPorItem.get(
            chaveProdutoLote(
              item.codigo,
              item.lote,
            ),
          );

        const localizacoes =
          localizacoesBipadas.size > 0
            ? localizacoesBipadas
            : new Set<string>(
                localizacoesEsperadas ?? [],
              );

        for (
          const localizacao
          of localizacoes
        ) {
          marcarNasVisoes(
            localizacao,
            false,
          );
        }
      }


      /*
       * OFICIAL:
       *
       * R1 e R2 pertencem ao fluxo inicial.
       * R3+ sao rodadas de recontagem.
       *
       * A fonte da verdade continua sendo o backend.
       */
      if (rodada.numero_rodada >= 3) {
        const analiseRecontagem =
          await buscarAnaliseRecontagem(
            idInventario,
            rodada.id_rodada,
          );

        if (
          "tipo_analise" in analiseRecontagem &&
          analiseRecontagem.tipo_analise ===
            "RECONTAGEM_OFICIAL"
        ) {
          for (
            const itemRecontagem
            of analiseRecontagem.itens
          ) {
            /*
             * Estamos na visao Estoque do Inventario.
             * Portanto usamos Codigo + Lote para
             * recuperar as localizacoes congeladas
             * no snapshot.
             */
            const localizacoesRecontagem =
              snapshotPorItem.get(
                chaveProdutoLote(
                  itemRecontagem.codigo,
                  itemRecontagem.lote,
                ),
              );

            for (
              const localizacaoRecontagem
              of localizacoesRecontagem ?? []
            ) {
              marcarNasVisoes(
                localizacaoRecontagem,
                true,
              );
            }
          }
        }
      }

      divergenciasDisponiveis =
        true;
    }
  } catch (erro) {
    avisoDivergencias =
      erro instanceof Error
        ? erro.message
        : "N\u00e3o foi poss\u00edvel carregar as diverg\u00eancias.";
  }


  // ==========================================================
  // VISAO EXCLUSIVA DE DIVERGENCIAS
  // ==========================================================

  const locationsDivergencia =
    locationsEstoqueInventario.filter(
      (location) =>
        location.status ===
          "divergencia" ||
        location.status ===
          "recontagem",
    );


  const divergencias =
    locationsEstoqueInventario.filter(
      (location) =>
        location.status ===
        "divergencia",
    ).length;


  const recontagem =
    locationsEstoqueInventario.filter(
      (location) =>
        location.status ===
        "recontagem",
    ).length;


  const ocupadas =
    locationsEstoqueAtual.filter(
      (location) =>
        location.quantidade !== 0 ||
        location.produto !== null,
    ).length;


  return {
    armazem,

    tipoInventario: inventario.tipo,

    clienteInventarioId:
      inventario.cliente_id,

    localizacoesTop20,

    top20Detalhes,

    avisoTop20,

    /*
     * Mantido para compatibilidade.
     */
    locations:
      locationsEstoqueAtual,

    visoes: {
      estoqueAtual:
        locationsEstoqueAtual,

      estoqueInventario:
        locationsEstoqueInventario,

      divergencia:
        locationsDivergencia,
    },

    resumo: {
      totalPosicoes:
        locationsEstoqueAtual.length,

      ocupadas,

      livres:
        locationsEstoqueAtual.length -
        ocupadas,

      registrosEstoque:
        estoque.itens.length,

      registrosInventario:
        snapshot?.itens.length ??
        0,

      localizacoesForaLayout:
        foraLayout.size,

      divergencias,

      recontagem,
    },

    atualizadoEm:
      new Date().toISOString(),

    snapshotDisponivel:
      snapshot !== null,

    avisoSnapshot,

    divergenciasDisponiveis,

    avisoDivergencias,
  };
}


/** Validação automática exigida pelo protótipo. */
export function validateWarehouse(): ValidationResult {
  const summary = getSummary();
  const has = (code: string) => findLocation(code) !== null;

  const checks = [
    {
      label: "R01 possui 288 posições",
      expected: "288",
      received: String(summary.porRua["R01"] ?? 0),
      ok: summary.porRua["R01"] === 288,
    },
    {
      label: "R02 possui 288 posições",
      expected: "288",
      received: String(summary.porRua["R02"] ?? 0),
      ok: summary.porRua["R02"] === 288,
    },
    {
      label: "R03 possui 144 posições",
      expected: "144",
      received: String(summary.porRua["R03"] ?? 0),
      ok: summary.porRua["R03"] === 144,
    },
    {
      label: "Total de posições",
      expected: "720",
      received: String(summary.totalPosicoes),
      ok: summary.totalPosicoes === 720,
    },
    {
      label: "Total de módulos",
      expected: "45",
      received: String(summary.totalModulos),
      ok: summary.totalModulos === 45,
    },
    {
      label: "R03 não possui lado par",
      expected: "0 posições",
      received: `${getLocations().filter((l) => l.rua === "R03" && l.lado === "par").length} posições`,
      ok: getLocations().every((l) => !(l.rua === "R03" && l.lado === "par")),
    },
    {
      label: "R0100100101 existe",
      expected: "true",
      received: String(has("R0100100101")),
      ok: has("R0100100101"),
    },
    {
      label: "R0201800802 existe",
      expected: "true",
      received: String(has("R0201800802")),
      ok: has("R0201800802"),
    },
    {
      label: "R0301700802 existe",
      expected: "true",
      received: String(has("R0301700802")),
      ok: has("R0301700802"),
    },
    {
      label: "R0300200101 não existe",
      expected: "false",
      received: String(has("R0300200101")),
      ok: !has("R0300200101"),
    },
    {
      label: "Faces / módulos por face / níveis / posições",
      expected: "5 / 9 / 8 / 2",
      received: `${FACES.length} / ${MODULOS_POR_FACE} / ${NIVEIS_POR_MODULO} / ${POSICOES_POR_NIVEL}`,
      ok: FACES.length === 5,
    },
  ];

  return { ok: checks.every((c) => c.ok), checks };
}
