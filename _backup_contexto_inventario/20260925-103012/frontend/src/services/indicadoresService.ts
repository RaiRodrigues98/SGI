import { apiRequest } from "@/services/apiClient";

export interface InventarioIndicadores {
  id_inventario: number;
  codigo_inventario: string;
  tipo: string;
  cliente: string;
  cliente_id: number;
  descricao: string | null;
  armazem: string;
  rodada_atual: number;
  status: string;
}

export interface AcompanhamentoOperacional {
  tipo_indicador: "ACOMPANHAMENTO_OPERACIONAL";
  id_inventario: number;
  codigo_inventario: string;
  tipo_inventario: string;
  cliente_id: number;
  status_inventario: string;
  id_rodada: number;
  numero_rodada: number;
  status_rodada: string;
  progresso: {
    itens: { planejados: number; processados: number; pendentes: number; percentual: number };
    localizacoes: { planejadas: number; concluidas: number; pendentes: number; percentual: number };
  };
  volume: { quantidade_planejada: number; quantidade_registrada: number };
  atividade: { total_bipagens: number; operadores_com_contagem: number };
  tempo: {
    data_hora_inicio: string | null;
    data_hora_fim: string | null;
    segundos: number;
    tempo_formatado: string;
  };
}

export interface AcompanhamentoLocalizacao {
  localizacao: string;
  status: "PENDENTE" | "EM_ANDAMENTO" | "CONCLUIDA";
  status_registro: string;
  itens_planejados: number;
  itens_processados: number;
  itens_pendentes: number;
  percentual: number;
  total_bipagens: number;
  quantidade_registrada: number;
  operadores: string[];
  hora_inicio: string | null;
  ultima_atividade: string | null;
  tempo_sem_atividade_segundos: number | null;
  tempo_sem_atividade_formatado: string;
}

export interface AcompanhamentoLocalizacoes {
  tipo_indicador: "ACOMPANHAMENTO_LOCALIZACOES";
  id_inventario: number;
  codigo_inventario: string;
  tipo_inventario: string;
  cliente_id: number;
  status_inventario: string;
  id_rodada: number;
  numero_rodada: number;
  status_rodada: string;
  resumo: {
    localizacoes_planejadas: number;
    localizacoes_concluidas: number;
    localizacoes_em_andamento: number;
    localizacoes_pendentes: number;
    percentual: number;
  };
  localizacoes: AcompanhamentoLocalizacao[];
}

export interface LocalizacaoTempo {
  localizacao: string;
  data_hora_inicio: string | null;
  data_hora_fim: string | null;
  tempo_segundos: number;
  tempo_formatado: string;
}

export interface ProdutividadeOperacional {
  tipo_indicador: "PRODUTIVIDADE_OPERACIONAL";
  id_inventario: number;
  codigo_inventario: string;
  tipo_inventario: string;
  cliente_id: number;
  status_inventario: string;
  id_rodada: number;
  numero_rodada: number;
  status_rodada: string;
  tempo: {
    data_hora_inicio_rodada: string | null;
    data_hora_fim_rodada: string | null;
    tempo_decorrido_segundos: number;
    tempo_decorrido_formatado: string;
    tempo_operacional_segundos: number;
    tempo_operacional_formatado: string;
    primeira_bipagem: string | null;
    ultima_bipagem: string | null;
    janela_bipagens_segundos: number;
    janela_bipagens_formatada: string;
    tempo_medio_localizacao_segundos: number;
    tempo_medio_localizacao_formatado: string;
  };
  producao: {
    total_bipagens: number;
    quantidade_registrada: number;
    itens_processados: number;
    localizacoes_concluidas: number;
  };
  produtividade: {
    global: {
      bipagens_hora: number;
      quantidade_hora: number;
      itens_processados_hora: number;
      localizacoes_concluidas_hora: number;
    };
    operacional: {
      bipagens_hora: number;
      quantidade_hora: number;
      itens_processados_hora: number;
      localizacoes_concluidas_hora: number;
    };
  };
  qualidade_dado_operador: {
    operadores_identificados: number;
    bipagens_sem_usuario: number;
    possui_bipagens_sem_usuario: boolean;
  };
  extremos_localizacao: {
    mais_rapida: LocalizacaoTempo | null;
    mais_lenta: LocalizacaoTempo | null;
  };
  operadores: Array<{
    operador: string;
    total_bipagens: number;
    quantidade_registrada: number;
    itens_distintos_com_bipagem: number;
    localizacoes_com_atividade: number;
    primeira_atividade: string | null;
    ultima_atividade: string | null;
    tempo_ativo_segundos: number;
    tempo_ativo_formatado: string;
    bipagens_hora: number;
    quantidade_hora: number;
  }>;
  localizacoes_tempo: LocalizacaoTempo[];
}

export interface ResultadoFinalIndicadores {
  tipo_consulta: "RESULTADO_FINAL";
  id_inventario: number;
  codigo_inventario: string;
  tipo_inventario: string;
  cliente_id: number;
  rodada_final: number;
  status_inventario: string;
  data_hora_finalizacao: string | null;
  finalizado_por: string | null;
  resumo: {
    total_itens: number;
    ok: number;
    nok: number;
    faltas: number;
    sobras: number;
    divergencias: number;
    acuracidade_percentual: number;
  };
}

export interface ItemRisco {
  cliente_id: number;
  cliente: string;
  armazem: string;
  localizacao: string;
  codigo: string;
  lote: string;
  descricao: string | null;
  unidade: string | null;
  categoria: string | null;
  score_risco: number;
  classificacao: string;
  historico: {
    inventarios_validos: number;
    ok: number;
    faltas: number;
    sobras: number;
    divergencias: number;
    taxa_divergencia_percentual: number;
    divergencias_consecutivas: number;
    ultima_divergencia: string | null;
    ultima_situacao: string | null;
    direcao_predominante: string | null;
    padrao: string | null;
    recorrente: boolean;
  };
  motivos: string[];
  prioridade_contagem: number;
}

export interface PriorizacaoRisco {
  tipo_indicador: "SCORE_RISCO_PRIORIZACAO";
  pesquisa: {
    cliente_id: number | null;
    armazem: string | null;
    localizacao: string | null;
    codigo: string | null;
    lote: string | null;
    classificacao: string | null;
    somente_prioritarios: boolean;
    limite: number;
  };
  modelo: {
    versao: string;
    score_minimo: number;
    score_maximo: number;
    faixas: Record<string, string>;
    pesos: Record<string, number>;
    confianca_historica: Record<string, number>;
  };
  resumo: {
    combinacoes_elegiveis: number;
    retornadas: number;
    baixo: number;
    medio: number;
    alto: number;
    critico: number;
    score_medio: number;
  };
  ranking_prioridade: ItemRisco[];
}

export interface PrioridadeCicloRotativo {
  id_ciclo_localizacao: number;
  id_rotativo_localizacao: number;
  localizacao: string;
  status: string;
  prioridade: number | null;
  score_risco: number | null;
  classificacao_risco: string | null;
  tipo_sugestao: string | null;
  ultima_contagem: string | null;
  id_inventario_ultima_contagem: number | null;
  id_rodada_ultima_contagem: number | null;
  motivo: string | null;
}

export interface PainelRotativo {
  possui_ciclo_aberto: boolean;
  ciclo: {
    id_ciclo: number;
    codigo_ciclo: string;
    cliente_id: number;
    armazem: string;
    status: string;
    data_inicio: string | null;
    data_fim_prevista: string | null;
    criado_por?: string | null;
  } | null;
  progresso: {
    total_localizacoes: number;
    contadas: number;
    ignoradas: number;
    em_contagem: number;
    pendentes: number;
    processadas: number;
    percentual_contado: number;
    percentual_processado: number;
    percentual_pendente: number;
  };
  risco: {
    critico: number;
    alto: number;
    medio: number;
    baixo: number;
    sugestoes_por_risco: number;
    sugestoes_por_cobertura: number;
  };
  historico: {
    nunca_contadas: number;
    com_divergencia_historica: number;
    com_recorrencia: number;
  };
  execucao_dia: {
    localizacoes_contadas_hoje: number;
    localizacoes_com_divergencia_hoje: number;
    localizacoes_ignoradas_hoje: number;
    tempo_medio_por_localizacao_minutos: number;
    usuarios_ativos: number;
    produtividade_por_usuario: unknown[];
  };
  backlog: {
    pendentes_ciclo: number;
    sem_historico_contagem: number;
    risco_alto_critico_pendente: number;
  };
  tendencias: {
    sem_historico: number;
    estaveis: number;
    atencao: number;
    recorrentes: number;
    deteriorando: number;
    melhorando: number;
    alertas: number;
  };
  tratativas: {
    localizacoes_com_recorrencia: number;
    localizacoes_com_tratativa_pendente: number;
    grupos_recorrentes: number;
    grupos_pendentes: number;
    ocorrencias_pendentes: number;
    ocorrencias_resolvidas: number;
  };
  eficacia: {
    resolucoes_avaliadas: number;
    eficazes: number;
    nao_eficazes: number;
    ainda_sem_evidencia: number;
  };
  alerta_principal: {
    localizacao: string;
    classificacao_tendencia: string;
    direcao: string;
    score_risco: number;
    classificacao_risco: string;
    motivo_principal: string;
    motivos: string[];
  } | null;
  alerta_tratativa: {
    localizacao: string;
    score_risco: number;
    classificacao_risco: string;
    possui_recorrencia: boolean;
    ocorrencias_pendentes: number;
    ocorrencias_resolvidas: number;
    grupos_pendentes: number;
    necessita_tratativa: boolean;
  } | null;
  sugestao_principal: PrioridadeCicloRotativo | null;
  top_prioridades: PrioridadeCicloRotativo[];
}

export interface TendenciaLocalizacao {
  id_ciclo_localizacao: number;
  id_rotativo_localizacao: number;
  localizacao: string;
  status_ciclo: string;
  prioridade: number | null;
  score_risco: number;
  classificacao_risco: string;
  tipo_sugestao: string | null;
  ultima_contagem: string | null;
  classificacao_tendencia: string;
  direcao: string;
  nivel_evidencia: string;
  historico: {
    contagens_analisadas: number;
    contagens_com_divergencia: number;
    taxa_divergencia_percentual: number;
    divergencias_consecutivas: number;
    ultima_divergencia: string | null;
    taxa_divergencia_anterior_percentual: number;
    taxa_divergencia_recente_percentual: number;
    variacao_taxa_percentual: number;
  };
  recorrencia: {
    possui_recorrencia_item_lote: boolean;
    grupos_recorrentes: number;
    grupos_divergencia: number;
  };
  tratativa: {
    necessita_tratativa: boolean;
    ocorrencias_pendentes: number;
    ocorrencias_resolvidas: number;
    grupos_pendentes: number;
  };
  eficacia: {
    resolucoes_avaliadas: number;
    eficazes: number;
    nao_eficazes: number;
    ainda_sem_evidencia: number;
    ultima_classificacao: string | null;
    ultima_resolucao: unknown | null;
  };
  fatores: Record<string, number | boolean>;
  motivos: string[];
}

export interface TendenciasRotativo {
  possui_ciclo_aberto: boolean;
  modelo: {
    versao: string;
    estrategia: string;
    fontes: string[];
    ordem_classificacao: string[];
  };
  pesquisa: {
    cliente_id: number;
    armazem: string;
    limite_historico: number;
    somente_alertas: boolean;
  };
  ciclo: {
    id_ciclo: number;
    codigo_ciclo: string;
    cliente_id: number;
    armazem: string;
    status: string;
    data_inicio: string | null;
    data_fim_prevista: string | null;
  } | null;
  resumo: {
    localizacoes_analisadas: number;
    sem_historico: number;
    estaveis: number;
    atencao: number;
    recorrentes: number;
    deteriorando: number;
    melhorando: number;
    tratativas_pendentes: number;
    localizacoes_com_recorrencia_item_lote: number;
    resolucoes_nao_eficazes: number;
    resolucoes_sem_evidencia: number;
    alertas: number;
  };
  tendencias: TendenciaLocalizacao[];
}

export async function listarInventariosIndicadores() {
  return apiRequest<InventarioIndicadores[]>("/inventarios");
}

export async function buscarAcompanhamento(idInventario: number, rodada?: number) {
  const query = rodada ? `?rodada=${rodada}` : "";
  return apiRequest<AcompanhamentoOperacional>(
    `/inventarios/${idInventario}/indicadores/acompanhamento${query}`,
  );
}

export async function buscarAcompanhamentoLocalizacoes(
  idInventario: number,
  rodada?: number,
) {
  const query = rodada ? `?rodada=${rodada}` : "";

  return apiRequest<AcompanhamentoLocalizacoes>(
    `/inventarios/${idInventario}/indicadores/acompanhamento/localizacoes${query}`,
  );
}

export async function buscarProdutividade(idInventario: number, rodada?: number) {
  const query = rodada ? `?rodada=${rodada}` : "";
  return apiRequest<ProdutividadeOperacional>(
    `/inventarios/${idInventario}/indicadores/produtividade${query}`,
  );
}

export async function buscarResultadoFinalIndicadores(idInventario: number) {
  return apiRequest<ResultadoFinalIndicadores>(
    `/inventarios/${idInventario}/resultado-final`,
  );
}

export async function buscarPriorizacaoRisco(clienteId: number, armazem: string, limite = 10) {
  const params = new URLSearchParams({
    cliente_id: String(clienteId),
    armazem,
    limite: String(limite),
  });
  return apiRequest<PriorizacaoRisco>(`/risco/priorizacao?${params.toString()}`);
}

export async function buscarPainelRotativo(clienteId: number, armazem: string, limitePrioridades = 5) {
  const params = new URLSearchParams({
    cliente_id: String(clienteId),
    armazem,
    limite_prioridades: String(limitePrioridades),
  });
  return apiRequest<PainelRotativo>(`/rotativo/ciclos/painel?${params.toString()}`);
}

export async function buscarTendenciasRotativo(clienteId: number, armazem: string, limiteHistorico = 6) {
  const params = new URLSearchParams({
    cliente_id: String(clienteId),
    armazem,
    limite_historico: String(limiteHistorico),
  });
  return apiRequest<TendenciasRotativo>(`/rotativo/ciclos/tendencias?${params.toString()}`);
}
