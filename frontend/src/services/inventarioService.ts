import { apiRequest } from "@/services/apiClient";

import type {
  AtualizacaoConfiguracaoResposta,
  AtualizacaoEscopoResposta,
  EscopoInventario,
  EstoqueCandidatosInventario,
  GerarSnapshotResposta,
  EscopoLocalizacoesEntrada,
  AtualizacaoRodadasResposta,
  ClienteDisponivelInventario,
  AtualizacaoConfiguracaoInventarioAplicadaResposta,
  AtualizarConfiguracaoInventarioAplicadaEntrada,
  ConfiguracaoInventario,
  ConfiguracaoInventarioAplicada,
  ConfiguracaoInventarioEntrada,
  HistoricoConfiguracaoInventarioResposta,
  ConfiguracoesRodadasEntrada,
  InventarioCriacaoEntrada,
  InventarioCriacaoResposta,
  InventarioCancelamentoEntrada,
  InventarioCancelamentoResposta,
  InventarioDetalhe,
  InventarioResumo,
  LocalizacoesCandidatasInventario,
  RodadaAtualOperacional,
  StatusSnapshotInventario,
  TipoInventario,
  StatusEscopoInventario,
} from "@/types/inventory";

// PAGINACAO_CENTRAL_SGI_V1
export interface FiltrosCentralInventarios {
  pagina: number;
  por_pagina: number;
  pesquisa?: string | undefined;
  tipo?: string | undefined;
  status?: string | undefined;
  cliente_id?: number | undefined;
  fase?: string | undefined;
  pendencias?: string | undefined;
  periodo?: string | undefined;
  data_inicial?: string | undefined;
  data_final?: string | undefined;
}

export interface RespostaCentralInventarios {
  itens: InventarioResumo[];
  pagina: number;
  por_pagina: number;
  total_registros: number;
  total_paginas: number;
  totais: {
    preparacao: number;
    execucao: number;
    aguardando_decisao: number;
    recontagem: number;
    pronto_finalizar: number;
    encerrados: number;
  };
  status_disponiveis: string[];
  clientes_filtro: Array<{ id: number; nome: string }>;
  fases_disponiveis: string[];
  inventarios_ativos: InventarioResumo[];
  proximo_codigo: string;
}

export async function listarInventariosCentral(
  filtros: FiltrosCentralInventarios,
  signal?: AbortSignal,
): Promise<RespostaCentralInventarios> {
  const parametros = new URLSearchParams();
  parametros.set("pagina", String(filtros.pagina));
  parametros.set("por_pagina", String(filtros.por_pagina));

  for (const [chave, valor] of Object.entries(filtros)) {
    if (["pagina", "por_pagina"].includes(chave) || valor === undefined || valor === "") {
      continue;
    }
    parametros.set(chave, String(valor));
  }

  const dados = await apiRequest<RespostaCentralInventarios>(
    `/inventarios/central?${parametros.toString()}`,
    signal ? { signal } : {},
  );

  if (!dados || !Array.isArray(dados.itens)) {
    throw new Error("A API retornou uma página de inventários inválida.");
  }
  return dados;
}

export async function listarInventarios(): Promise<InventarioResumo[]> {
  const dados = await apiRequest<InventarioResumo[]>("/inventarios");

  if (!Array.isArray(dados)) {
    throw new Error("A API retornou uma lista de inventários inválida.");
  }

  return dados;
}

export async function listarInventariosAbertos(): Promise<InventarioResumo[]> {
  const dados = await apiRequest<InventarioResumo[]>("/inventarios?status=ABERTO");

  if (!Array.isArray(dados)) {
    throw new Error("A API retornou uma lista de inventários inválida.");
  }

  return dados;
}

export async function salvarLocalizacoesEscopo(
  idInventario: number,
  entrada: EscopoLocalizacoesEntrada,
): Promise<AtualizacaoEscopoResposta> {
  if (!Number.isInteger(idInventario) || idInventario <= 0) {
    throw new Error("Inventário inválido.");
  }

  if (!Array.isArray(entrada.localizacoes) || entrada.localizacoes.length === 0) {
    throw new Error("Selecione pelo menos uma localização.");
  }

  const criadoPor = entrada.criado_por.trim();

  if (!criadoPor) {
    throw new Error("Usuário responsável pelo escopo não informado.");
  }

  return apiRequest<AtualizacaoEscopoResposta>(`/inventarios/${idInventario}/escopo/localizacoes`, {
    method: "POST",
    body: {
      localizacoes: entrada.localizacoes,
      criado_por: criadoPor,
    },
  });
}

export async function consultarEscopoInventario(
  idInventario: number,
  somenteSelecionados = false,
): Promise<EscopoInventario> {
  if (!Number.isInteger(idInventario) || idInventario <= 0) {
    throw new Error("Inventário inválido.");
  }

  const query = somenteSelecionados ? "?somente_selecionados=true" : "";

  return apiRequest<EscopoInventario>(`/inventarios/${idInventario}/escopo${query}`);
}

export async function consultarStatusSnapshot(
  idInventario: number,
): Promise<StatusSnapshotInventario> {
  if (!Number.isInteger(idInventario) || idInventario <= 0) {
    throw new Error("Inventário inválido.");
  }

  return apiRequest<StatusSnapshotInventario>(`/inventarios/${idInventario}/snapshot/status`);
}

export async function gerarSnapshot(idInventario: number): Promise<GerarSnapshotResposta> {
  if (!Number.isInteger(idInventario) || idInventario <= 0) {
    throw new Error("Inventário inválido.");
  }

  return apiRequest<GerarSnapshotResposta>(`/inventarios/${idInventario}/snapshot`, {
    method: "POST",
    body: {},
  });
}

export async function consultarSnapshotInventario(
  idInventario: number,
): Promise<EstoqueCandidatosInventario> {
  if (!Number.isInteger(idInventario) || idInventario <= 0) {
    throw new Error("Inventario invalido.");
  }

  return apiRequest<EstoqueCandidatosInventario>(`/inventarios/${idInventario}/snapshot`);
}

export async function listarEstoqueCandidatos(
  idInventario: number,
  localizacao?: string,
): Promise<EstoqueCandidatosInventario> {
  if (!Number.isInteger(idInventario) || idInventario <= 0) {
    throw new Error("Inventário inválido.");
  }

  const params = new URLSearchParams();

  if (localizacao?.trim()) {
    params.set("localizacao", localizacao.trim());
  }

  const query = params.toString();

  return apiRequest<EstoqueCandidatosInventario>(
    `/inventarios/${idInventario}/estoque-candidatos${query ? `?${query}` : ""}`,
  );
}

export async function listarLocalizacoesCandidatas(
  idInventario: number,
): Promise<LocalizacoesCandidatasInventario> {
  if (!Number.isInteger(idInventario) || idInventario <= 0) {
    throw new Error("Inventário inválido.");
  }

  return apiRequest<LocalizacoesCandidatasInventario>(
    `/inventarios/${idInventario}/localizacoes-candidatas`,
  );
}

export async function consultarInventarioDetalhe(idInventario: number): Promise<InventarioDetalhe> {
  if (!Number.isInteger(idInventario) || idInventario <= 0) {
    throw new Error("Inventário inválido.");
  }

  return apiRequest<InventarioDetalhe>(`/inventarios/${idInventario}`);
}

export async function cancelarInventario(
  idInventario: number,
  entrada: InventarioCancelamentoEntrada,
): Promise<InventarioCancelamentoResposta> {
  if (!Number.isInteger(idInventario) || idInventario <= 0) {
    throw new Error("Inventário inválido.");
  }

  const motivo = entrada.motivo.trim();

  if (!motivo) {
    throw new Error("Informe o motivo do cancelamento.");
  }

  return apiRequest<InventarioCancelamentoResposta>(`/inventarios/${idInventario}/cancelar`, {
    method: "PATCH",
    body: {
      motivo,
    },
  });
}

export async function listarClientesDisponiveis(): Promise<ClienteDisponivelInventario[]> {
  const dados = await apiRequest<ClienteDisponivelInventario[]>(
    "/inventarios/clientes-disponiveis",
  );

  if (!Array.isArray(dados)) {
    throw new Error("A API retornou uma lista de clientes inválida.");
  }

  return dados;
}

export async function criarInventario(
  entrada: InventarioCriacaoEntrada,
): Promise<InventarioCriacaoResposta> {
  const codigoInventario = entrada.codigo_inventario.trim();
  const cliente = entrada.cliente.trim();
  const armazem = entrada.armazem.trim().toUpperCase();
  const descricao = entrada.descricao?.trim() || null;

  if (!codigoInventario) {
    throw new Error("Informe o código do inventário.");
  }

  if (!Number.isInteger(entrada.cliente_id) || entrada.cliente_id <= 0) {
    throw new Error("Informe um Cliente ID válido.");
  }

  if (!cliente) {
    throw new Error("Informe o cliente.");
  }

  if (!armazem) {
    throw new Error("Informe o armazém.");
  }

  if (entrada.tipo !== "ROTATIVO" && entrada.tipo !== "OFICIAL") {
    throw new Error("Tipo de inventário inválido.");
  }

  return apiRequest<InventarioCriacaoResposta>("/inventarios", {
    method: "POST",
    body: {
      codigo_inventario: codigoInventario,
      tipo: entrada.tipo,
      cliente_id: entrada.cliente_id,
      cliente,
      descricao,
      armazem,
    },
  });
}

export async function consultarRodadaAtual(idInventario: number): Promise<RodadaAtualOperacional> {
  if (!Number.isInteger(idInventario) || idInventario <= 0) {
    throw new Error("Inventário inválido.");
  }

  return apiRequest<RodadaAtualOperacional>(`/inventarios/${idInventario}/rodada-atual`);
}

export async function consultarStatusEscopoInventario(
  idInventario: number,
): Promise<StatusEscopoInventario> {
  if (!Number.isInteger(idInventario) || idInventario <= 0) {
    throw new Error("Inventario invalido.");
  }

  return apiRequest<StatusEscopoInventario>(`/inventarios/${idInventario}/escopo/status`);
}

export async function consultarConfiguracaoPorInventario(
  idInventario: number,
): Promise<ConfiguracaoInventarioAplicada> {
  if (!Number.isInteger(idInventario) || idInventario <= 0) {
    throw new Error("Inventario invalido.");
  }

  return apiRequest<ConfiguracaoInventarioAplicada>(
    `/inventarios/${idInventario}/configuracao`,
  );
}

export async function consultarConfiguracaoInventario(
  clienteId: number,
  tipo: TipoInventario,
): Promise<ConfiguracaoInventario> {
  if (!Number.isInteger(clienteId) || clienteId <= 0) {
    throw new Error("Cliente ID invalido.");
  }

  if (tipo !== "ROTATIVO" && tipo !== "OFICIAL") {
    throw new Error("Tipo de inventario invalido.");
  }

  return apiRequest<ConfiguracaoInventario>(`/configuracoes/inventario/${clienteId}/${tipo}`);
}

export async function criarConfiguracaoInventario(
  clienteId: number,
  tipo: TipoInventario,
  entrada: ConfiguracaoInventarioEntrada & {
    rodadas: ConfiguracoesRodadasEntrada["rodadas"];
  },
): Promise<AtualizacaoConfiguracaoResposta> {
  if (!Number.isInteger(clienteId) || clienteId <= 0) {
    throw new Error("Cliente ID invalido.");
  }

  if (tipo !== "ROTATIVO" && tipo !== "OFICIAL") {
    throw new Error("Tipo de inventario invalido.");
  }

  if (!Array.isArray(entrada.rodadas) || entrada.rodadas.length === 0) {
    throw new Error("Informe ao menos uma rodada.");
  }

  return apiRequest<AtualizacaoConfiguracaoResposta>(
    `/configuracoes/inventario/${clienteId}/${tipo}`,
    {
      method: "POST",
      body: entrada,
    },
  );
}

export async function atualizarConfiguracaoInventario(
  clienteId: number,
  tipo: TipoInventario,
  entrada: ConfiguracaoInventarioEntrada,
): Promise<AtualizacaoConfiguracaoResposta> {
  if (!Number.isInteger(clienteId) || clienteId <= 0) {
    throw new Error("Cliente ID invalido.");
  }

  if (tipo !== "ROTATIVO" && tipo !== "OFICIAL") {
    throw new Error("Tipo de inventario invalido.");
  }

  return apiRequest<AtualizacaoConfiguracaoResposta>(
    `/configuracoes/inventario/${clienteId}/${tipo}`,
    {
      method: "PUT",
      body: entrada,
    },
  );
}

export async function atualizarRodadasConfiguracaoInventario(
  clienteId: number,
  tipo: TipoInventario,
  entrada: ConfiguracoesRodadasEntrada,
): Promise<AtualizacaoRodadasResposta> {
  if (!Number.isInteger(clienteId) || clienteId <= 0) {
    throw new Error("Cliente ID invalido.");
  }

  if (tipo !== "ROTATIVO" && tipo !== "OFICIAL") {
    throw new Error("Tipo de inventario invalido.");
  }

  if (!Array.isArray(entrada.rodadas) || entrada.rodadas.length === 0) {
    throw new Error("Informe ao menos uma rodada.");
  }

  return apiRequest<AtualizacaoRodadasResposta>(
    `/configuracoes/inventario/${clienteId}/${tipo}/rodadas`,
    {
      method: "PUT",
      body: entrada,
    },
  );
}


export async function atualizarConfiguracaoAplicadaInventario(
  idInventario: number,
  entrada: AtualizarConfiguracaoInventarioAplicadaEntrada,
): Promise<AtualizacaoConfiguracaoInventarioAplicadaResposta> {
  if (!Number.isInteger(idInventario) || idInventario <= 0) {
    throw new Error("Inventario invalido.");
  }

  return apiRequest<AtualizacaoConfiguracaoInventarioAplicadaResposta>(
    `/inventarios/${idInventario}/configuracao`,
    {
      method: "PUT",
      body: entrada,
    },
  );
}

export async function consultarHistoricoConfiguracaoInventario(
  idInventario: number,
): Promise<HistoricoConfiguracaoInventarioResposta> {
  if (!Number.isInteger(idInventario) || idInventario <= 0) {
    throw new Error("Inventario invalido.");
  }

  return apiRequest<HistoricoConfiguracaoInventarioResposta>(
    `/inventarios/${idInventario}/configuracao/historico`,
  );
}



/*
 * ============================================================
 * ESTOQUE ATUAL DO ARMAZEM
 * ============================================================
 *
 * Consulta independente de inventario.
 *
 * Retorna o estoque fisico corrente de todos
 * os clientes existentes no armazem.
 */

export interface EstoqueAtualItem {
  id: number;

  armazem: string;

  localizacao: string;

  codigo: string;

  lote: string | null;

  cliente_id: number;

  cliente: string;

  descricao: string | null;

  unidade: string | null;

  categoria: string | null;

  validade: string | null;

  q_armazenado: number;

  q_reservado: number;

  q_bloqueado: number;

  q_estimado: number;

  saldo_disponivel: number;

  status_estoque: string | null;

  tipo_localizacao: string | null;
}


export interface EstoqueAtualResponse {
  armazem: string;

  cliente_id: number | null;

  localizacao: string | null;

  somente_com_estoque: boolean;

  total: number;

  itens: EstoqueAtualItem[];
}


export async function listarEstoqueAtual(
  armazem: string,
  clienteId?: number,
  localizacao?: string,
): Promise<EstoqueAtualResponse> {
  const armazemNormalizado =
    armazem.trim();


  if (!armazemNormalizado) {
    throw new Error(
      "Armazem invalido.",
    );
  }


  const params =
    new URLSearchParams();


  params.set(
    "armazem",
    armazemNormalizado,
  );


  if (
    clienteId !== undefined
  ) {
    params.set(
      "cliente_id",
      String(clienteId),
    );
  }


  if (
    localizacao?.trim()
  ) {
    params.set(
      "localizacao",
      localizacao.trim(),
    );
  }


  /*
   * Para o mapa queremos somente registros
   * com estoque fisico atual.
   */
  params.set(
    "somente_com_estoque",
    "true",
  );


  return apiRequest<EstoqueAtualResponse>(
    `/estoque/atual?${params.toString()}`,
  );
}
