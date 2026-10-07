import { apiRequest } from "./apiClient";

export type HistoricoInventario = {
  id_inventario: number;
  codigo_inventario: string;
  tipo: string;
  cliente: string;
  cliente_id: number;
  armazem: string | null;
  descricao: string | null;
  rodada_atual: number | null;
  status: string;
  data_hora_inicio: string | null;
  data_hora_fim: string | null;
  criado_por: string | null;
  data_hora_criacao: string | null;
  finalizado_por: string | null;
  gestor?: {
    em_analise: boolean;
    data_hora_encaminhamento: string | null;
    encaminhado_por: string | null;
  };
  cancelamento?: {
    cancelado: boolean;
    cancelado_por: string | null;
    motivo: string | null;
    data_hora: string | null;
  };
};

export type HistoricoInventariosResponse = {
  tipo_consulta: string;
  paginacao: {
    page: number;
    page_size: number;
    total_registros: number;
    total_paginas: number;
    possui_proxima_pagina: boolean;
    possui_pagina_anterior: boolean;
  };
  filtros: Record<string, unknown>;
  inventarios: HistoricoInventario[];
};

export type EventoHistorico = {
  id_inventario: number;
  codigo_inventario: string;
  tipo_inventario: string;
  status_inventario: string;
  data_hora_inicio: string | null;
  data_hora_fim: string | null;
  id_resultado_final: number | null;
  data_hora_finalizacao: string | null;
  status: string;
  qtd_estoque: number;
  quantidade_final: number;
  diferenca: number;
  origem_quantidade: string | null;
  rodada_final: number | null;
  usuario_finalizacao: string | null;
  atribuicao_localizacao?: string | null;
  armazem?: string | null;
  origem_armazem?: string | null;
};

export type HistoricoItemInventario = {
  id_inventario: number;
  codigo_inventario: string;
  tipo: string;
  cliente: string;
  cliente_id: number;
  armazem: string | null;
  descricao: string | null;
  status: string;
  rodada_atual: number | null;
  data_hora_inicio: string | null;
  data_hora_fim: string | null;
  criado_por: string | null;
  finalizado_por: string | null;
  consistencia?: {
    resultado_final_esperado: boolean;
    resultado_final_encontrado: boolean;
    status: string;
  };
  snapshot?: unknown[];
  rodadas?: unknown[];
  decisoes_gestor?: unknown[];
  resultado_final?: unknown[];
};

export type HistoricoPaginacao = {
  page: number;
  page_size: number;
  total_registros: number;
  total_paginas: number;
  registros_pagina: number;
  possui_proxima_pagina: boolean;
  possui_pagina_anterior: boolean;
};

export type HistoricoItemResponse = {
  tipo_consulta?: string;
  pesquisa?: Record<string, unknown>;
  paginacao?: HistoricoPaginacao;
  resumo?: Record<string, unknown>;
  inventarios?: HistoricoItemInventario[];
  historico?: HistoricoItemInventario[];
  resultados?: HistoricoItemInventario[];
};

export type HistoricoLocalizacaoInventario = HistoricoItemInventario & {
  consistencia?: {
    resultado_final_esperado: boolean;
    resultado_final_inventario_encontrado?: boolean;
    resultado_final_localizacao_encontrado?: boolean;
    atribuicao_localizacao?: string;
    resultados_nao_atribuidos?: number;
    status: string;
  };
  snapshot?: {
    itens_previstos?: number;
    quantidade_prevista?: number;
    itens?: unknown[];
  };
  resultado_final?: {
    itens?: number;
    ok?: number;
    faltas?: number;
    sobras?: number;
    atribuicao_localizacao?: string;
    detalhes?: unknown[];
    nao_atribuidos?: unknown[];
  };
};

export type HistoricoLocalizacaoResponse = {
  tipo_consulta?: string;
  pesquisa?: Record<string, unknown>;
  paginacao?: HistoricoPaginacao;
  resumo?: Record<string, unknown>;
  itens_recorrentes?: unknown[];
  inventarios?: HistoricoLocalizacaoInventario[];
};

export type RankingRecorrencia = {
  codigo: string;
  lote: string;
  armazem: string;
  localizacao: string;
  divergencias: number;
  divergencias_consecutivas: number;
  taxa_divergencia_percentual: number;
  padrao: string;
};

export type HistoricoDivergenciasResponse = {
  tipo_consulta: string;
  pesquisa: {
    cliente_id: number;
    armazem: string | null;
    localizacao: string | null;
    codigo: string | null;
    lote: string | null;
    tipo_inventario: string | null;
    data_inicio: string | null;
    data_fim: string | null;
    somente_recorrentes: boolean;
  };
  resumo: {
    inventarios_validos: number;
    inventarios_com_divergencia: number;
    resultados_item_validos: number;
    resultados_item_ok: number;
    resultados_item_falta: number;
    resultados_item_sobra: number;
    quantidade_faltante_total: number;
    quantidade_sobrando_total: number;
    quantidade_divergencia_absoluta: number;
    combinacoes_analisadas: number;
    combinacoes_com_divergencia: number;
    combinacoes_recorrentes: number;
    taxa_recorrencia_percentual: number;
    ultima_divergencia: string | null;
    resultados_sem_localizacao_resolvida: number;
    resultados_sem_armazem_resolvido: number;
  };
  ranking_recorrencia: RankingRecorrencia[];
  combinacoes?: unknown[];
};

function qs(params: Record<string, string | number | boolean | null | undefined>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const value = search.toString();
  return value ? `?${value}` : "";
}

export async function buscarHistoricoInventarios(params: {
  cliente_id: number;
  page?: number;
  page_size?: number;
  tipo?: string;
  status?: string;
  data_inicio?: string;
  data_fim?: string;
  codigo_inventario?: string;
}) {
  return apiRequest<HistoricoInventariosResponse>(
    `/historico/inventarios${qs(params)}`
  );
}

export async function buscarHistoricoItem(params: {
  cliente_id: number;
  codigo: string;
  lote?: string;
  page?: number;
  page_size?: number;
}) {
  return apiRequest<HistoricoItemResponse>(
    `/historico/itens${qs(params)}`
  );
}

export async function buscarHistoricoLocalizacao(params: {
  cliente_id: number;
  localizacao: string;
  tipo?: string;
  page?: number;
  page_size?: number;
}) {
  return apiRequest<HistoricoLocalizacaoResponse>(
    `/historico/localizacoes${qs(params)}`
  );
}

export async function buscarHistoricoDivergencias(params: {
  cliente_id: number;
  armazem?: string;
  localizacao?: string;
  codigo?: string;
  lote?: string;
  tipo_inventario?: string;
  data_inicio?: string;
  data_fim?: string;
  somente_recorrentes?: boolean;
}) {
  return apiRequest<HistoricoDivergenciasResponse>(
    `/historico/divergencias${qs(params)}`
  );
}

