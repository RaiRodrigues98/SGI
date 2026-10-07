import { apiRequest } from "@/services/apiClient";

export interface InventarioRotativo {
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

export interface DecisaoRotativo {
  possui_decisao: boolean;
  id_decisao_rotativo: number | null;
  decisao: string | null;
  justificativa: string | null;
  usuario: string | null;
  data_hora: string | null;
}

export interface ItemRotativo {
  chave: string;
  localizacao: string;
  codigo: string;
  produto: string | null;
  lote: string;
  unidade: string | null;
  categoria: string | null;
  qtd_estoque: number;
  qtd_contada: number;
  existe_no_snapshot: boolean;
  diferenca: number;
  status: string;
  subtipo_divergencia: string | null;
  localizacoes_esperadas: string[];
  resultado_definitivo: boolean;
  requer_decisao: boolean;
  pendente_decisao: boolean;
  resolvido: boolean;
  pendente_recontagem: boolean;
  divergencia_justificada: boolean;
  decisao_rotativo: DecisaoRotativo;
}

export interface AnaliseRotativo {
  tipo_analise: "ROTATIVO";
  id_inventario: number;
  codigo_inventario: string;
  cliente_id: number;
  status_inventario: string;
  id_rodada: number;
  numero_rodada: number;
  status_rodada: string;
  regra_conciliacao: string;
  considera_localizacao: boolean;
  contagem_cega: boolean;
  rodada_operacional_concluida: boolean;
  pode_finalizar_inventario: boolean;
  pode_gerar_recontagem: boolean;
  resumo: {
    total_itens: number;
    ok: number;
    faltas: number;
    sobras: number;
    divergencias: number;
    localizacoes_incorretas: number;
    itens_nao_previstos: number;
    itens_sem_saldo: number;
    divergencias_quantidade: number;
    lotes_incorretos: number;
    lote_e_quantidade: number;
    aguardando_contagem: number;
    itens_requerem_decisao: number;
    itens_sem_decisao: number;
    itens_para_recontagem: number;
    divergencias_justificadas: number;
    itens_resolvidos: number;
    total_localizacoes: number;
    localizacoes_concluidas: number;
    localizacoes_pendentes: number;
  };
  localizacoes: Array<{ localizacao: string; status: string; [key: string]: unknown }>;
  itens: ItemRotativo[];
}

export async function listarInventariosRotativos() {
  const inventarios =
    await apiRequest<InventarioRotativo[]>(
      "/inventarios?tipo=ROTATIVO",
    );

  return inventarios.filter(
    (item) => item.status === "ABERTO",
  );
}

export async function buscarAnaliseRotativo(idInventario: number) {
  return apiRequest<AnaliseRotativo>(`/inventarios/${idInventario}/analise-rotativo`);
}

export async function registrarDecisaoRotativo(
  idInventario: number,
  dados: {
    id_rodada: number;
    localizacao: string;
    codigo: string;
    lote?: string | null;
    decisao: "RECONTAR" | "JUSTIFICAR_DIVERGENCIA";
    justificativa?: string | null;
  },
) {
  return apiRequest(`/inventarios/${idInventario}/decisoes-rotativo`, {
    method: "POST",
    body: dados,
  });
}

export async function gerarRecontagemRotativo(idInventario: number, localizacoes: string[]) {
  return apiRequest(`/inventarios/${idInventario}/rodadas/proxima`, {
    method: "POST",
    body: { localizacoes },
  });
}

export async function finalizarInventarioRotativo(idInventario: number) {
  return apiRequest(`/inventarios/${idInventario}/finalizar`, {
    method: "POST",
    body: {},
  });
}

// ============================================================
// CICLO ROTATIVO
// ============================================================

export interface CicloRotativoLocalizacao {
  id_ciclo_localizacao: number;
  id_rotativo_localizacao: number;
  localizacao: string;
  status: string;
  data_inclusao: string | null;
  data_inicio_contagem: string | null;
  data_conclusao: string | null;
  id_inventario: number | null;
  id_rodada: number | null;
  score_risco: number | null;
  classificacao_risco: string | null;
  sugerida: boolean;
  prioridade: number | null;
  usuario_contagem: string | null;
  data_hora_atualizacao: string | null;
}

export interface CicloRotativoResumoLocalizacoes {
  pendentes: number;
  em_contagem: number;
  contadas: number;
  ignoradas: number;
}

export interface CicloRotativo {
  id_ciclo: number;
  codigo_ciclo: string;
  cliente_id: number;
  armazem: string;
  data_inicio?: string | null;
  data_fim_prevista: string | null;
  status: string;
  total_localizacoes: number;
  localizacoes_contadas: number;
  percentual_cobertura: number;
  resumo_localizacoes?: CicloRotativoResumoLocalizacoes;
  localizacoes?: CicloRotativoLocalizacao[];
}

export interface CicloRotativoAtualResposta {
  possui_ciclo_aberto: boolean;
  ciclo: CicloRotativo | null;
}

export interface AbrirCicloRotativoEntrada {
  cliente_id: number;
  armazem: string;
  criado_por?: string | null;
  data_fim_prevista?: string | null;
}

export interface AbrirCicloRotativoResposta {
  criado: boolean;
  motivo: string;
  ciclo: CicloRotativo;
}

export async function consultarCicloRotativoAtual(
  clienteId: number,
  armazem: string,
): Promise<CicloRotativoAtualResposta> {
  if (!Number.isInteger(clienteId) || clienteId <= 0) {
    throw new Error("Cliente invalido.");
  }

  const armazemNormalizado = armazem.trim().toUpperCase();

  if (!armazemNormalizado) {
    throw new Error("Armazem invalido.");
  }

  const params = new URLSearchParams({
    cliente_id: String(clienteId),
    armazem: armazemNormalizado,
  });

  return apiRequest<CicloRotativoAtualResposta>(
    `/rotativo/ciclos/atual?${params.toString()}`,
  );
}

export async function abrirCicloRotativo(
  entrada: AbrirCicloRotativoEntrada,
): Promise<AbrirCicloRotativoResposta> {
  if (
    !Number.isInteger(entrada.cliente_id) ||
    entrada.cliente_id <= 0
  ) {
    throw new Error("Cliente invalido.");
  }

  const armazem = entrada.armazem.trim().toUpperCase();

  if (!armazem) {
    throw new Error("Armazem invalido.");
  }

  return apiRequest<AbrirCicloRotativoResposta>(
    "/rotativo/ciclos",
    {
      method: "POST",
      body: {
        cliente_id: entrada.cliente_id,
        armazem,
        criado_por: entrada.criado_por?.trim() || null,
        data_fim_prevista:
          entrada.data_fim_prevista || null,
      },
    },
  );
}
// ============================================================
// UNIVERSO ROTATIVO
// ============================================================

export interface UniversoRotativoStatus {
  cliente_id: number;
  armazem: string;

  total_localizacoes_estoque: number;
  total_localizacoes_mestre: number;
  total_localizacoes_ativas: number;
  total_localizacoes_inativas: number;

  total_novas_localizacoes: number;
  total_fora_estoque_atual: number;

  configurado: boolean;
  sincronizado: boolean;

  possui_ciclo_aberto: boolean;

  ciclo_aberto: {
    id_ciclo: number;
    codigo_ciclo: string;
    status: string;
  } | null;

  novas_localizacoes: string[];

  localizacoes_fora_estoque_atual: Array<{
    localizacao: string;
    status: string;
  }>;
}

export interface ConfigurarUniversoRotativoEntrada {
  cliente_id: number;
  armazem: string;
}

export interface ConfigurarUniversoRotativoResposta {
  configurado: boolean;
  motivo:
    | "UNIVERSO_CONFIGURADO"
    | "UNIVERSO_JA_CONFIGURADO"
    | string;
  localizacoes_inseridas: number;
  universo: UniversoRotativoStatus;
}

export async function consultarStatusUniversoRotativo(
  clienteId: number,
  armazem: string,
): Promise<UniversoRotativoStatus> {
  if (!Number.isInteger(clienteId) || clienteId <= 0) {
    throw new Error("Cliente invalido.");
  }

  const armazemNormalizado = armazem
    .trim()
    .toUpperCase();

  if (!armazemNormalizado) {
    throw new Error("Armazem invalido.");
  }

  const params = new URLSearchParams({
    cliente_id: String(clienteId),
    armazem: armazemNormalizado,
  });

  return apiRequest<UniversoRotativoStatus>(
    `/rotativo/universo/status?${params.toString()}`,
  );
}

export async function configurarUniversoRotativo(
  entrada: ConfigurarUniversoRotativoEntrada,
): Promise<ConfigurarUniversoRotativoResposta> {
  if (
    !Number.isInteger(entrada.cliente_id) ||
    entrada.cliente_id <= 0
  ) {
    throw new Error("Cliente invalido.");
  }

  const armazem = entrada.armazem
    .trim()
    .toUpperCase();

  if (!armazem) {
    throw new Error("Armazem invalido.");
  }

  return apiRequest<ConfigurarUniversoRotativoResposta>(
    "/rotativo/universo/configurar",
    {
      method: "POST",
      body: {
        cliente_id: entrada.cliente_id,
        armazem,
      },
    },
  );
}


// ============================================================
// LOCALIZACOES DO CICLO ROTATIVO
// ============================================================

export interface LocalizacaoCicloRotativoConsulta {
  id_ciclo_localizacao: number;
  id_rotativo_localizacao: number;
  localizacao: string;

  status_ciclo: string;
  status_cadastro: string;

  ultima_contagem: string | null;
  dias_sem_contagem: number | null;

  id_inventario_ultima_contagem: number | null;
  id_rodada_ultima_contagem: number | null;

  score_risco: number | null;
  classificacao_risco: string | null;

  sugerida: boolean;
  prioridade: number | null;

  motivos: string[];

  contagem_ciclo: {
    data_inclusao: string | null;
    data_inicio: string | null;
    data_conclusao: string | null;
    id_inventario: number | null;
    id_rodada: number | null;
    usuario: string | null;
  };

  ignoracao: {
    ignorada: boolean;
    motivo: string | null;
    usuario: string | null;
    data_hora: string | null;
  };

  snapshot_risco_entrada: {
    score: number | null;
    classificacao: string | null;
    sugerida: boolean;
    prioridade: number | null;
  };
}

export interface LocalizacoesCicloRotativoResposta {
  possui_ciclo: boolean;

  ciclo: {
    id_ciclo: number;
    codigo_ciclo: string;
    cliente_id: number;
    armazem: string;
    status: string;

    data_inicio: string | null;
    data_fim_prevista: string | null;
    data_fim_real: string | null;

    total_localizacoes: number;
    localizacoes_contadas: number;
    localizacoes_ignoradas: number;
    localizacoes_processadas: number;
    localizacoes_pendentes: number;
    localizacoes_em_contagem: number;
    percentual_cobertura: number;
  } | null;

  resumo_retorno?: {
    localizacoes_retornadas: number;
    pendentes: number;
    em_contagem: number;
    contadas: number;
    ignoradas: number;
    sugeridas: number;
    criticas: number;
    altas: number;
    medias: number;
    baixas: number;
    sem_historico_contagem: number;
  };

  localizacoes: LocalizacaoCicloRotativoConsulta[];
}

export async function consultarLocalizacoesPendentesCicloRotativo(
  clienteId: number,
  armazem: string,
  idCiclo?: number,
): Promise<LocalizacoesCicloRotativoResposta> {
  if (!Number.isInteger(clienteId) || clienteId <= 0) {
    throw new Error("Cliente invalido.");
  }

  const armazemNormalizado = armazem
    .trim()
    .toUpperCase();

  if (!armazemNormalizado) {
    throw new Error("Armazem invalido.");
  }

  if (
    idCiclo !== undefined &&
    (!Number.isInteger(idCiclo) || idCiclo <= 0)
  ) {
    throw new Error("Ciclo rotativo invalido.");
  }

  const params = new URLSearchParams({
    cliente_id: String(clienteId),
    armazem: armazemNormalizado,
    somente_pendentes: "true",
    ordenar_por: "PRIORIDADE",
  });

  if (idCiclo !== undefined) {
    params.set(
      "id_ciclo",
      String(idCiclo),
    );
  }

  return apiRequest<LocalizacoesCicloRotativoResposta>(
    `/rotativo/ciclos/localizacoes?${params.toString()}`,
  );
}

export interface SugestaoCicloRotativo {
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
  motivo_principal: string | null;
  dados_ciclo: {
    data_inclusao: string | null;
    data_inicio_contagem: string | null;
    data_conclusao: string | null;
    id_inventario: number | null;
    id_rodada: number | null;
    usuario_contagem: string | null;
    data_hora_atualizacao: string | null;
  };
}

export interface SugestoesCicloRotativoResposta {
  possui_ciclo_aberto: boolean;
  pesquisa: unknown;
  ciclo: unknown | null;
  progresso: unknown;
  resumo: {
    sugeridas_pendentes: number;
    sugestoes_por_risco: number;
    sugestoes_por_cobertura: number;
    sugestoes_retornadas: number;
  };
  sugestao_principal: SugestaoCicloRotativo | null;
  proximas_sugestoes: SugestaoCicloRotativo[];
}

export async function buscarSugestoesCicloRotativo(
  clienteId: number,
  armazem: string,
  limite = 20,
): Promise<SugestoesCicloRotativoResposta> {
  if (!Number.isInteger(clienteId) || clienteId <= 0) {
    throw new Error("Cliente invalido.");
  }

  const armazemNormalizado = armazem.trim().toUpperCase();

  if (!armazemNormalizado) {
    throw new Error("Armazem invalido.");
  }

  const params = new URLSearchParams({
    cliente_id: String(clienteId),
    armazem: armazemNormalizado,
    limite: String(limite),
    somente_pendentes: "true",
  });

  return apiRequest<SugestoesCicloRotativoResposta>(
    `/rotativo/ciclos/sugestoes?${params.toString()}`,
  );
}

// ============================================================
// TRATATIVAS DO CICLO ROTATIVO
// ============================================================

export interface OcorrenciaHistoricoTratativaRotativa {
  id_ocorrencia: number;
  id_inventario: number;
  id_rodada: number | null;
  tipo_inventario: string;
  localizacao: string | null;
  codigo: string;
  lote: string | null;
  qtd_estoque: number | null;
  qtd_contada: number | null;
  diferenca: number | null;
  tipo_divergencia: string;
  status_resolucao: string;
  justificativa: string | null;
  id_decisao_rotativo: number | null;
  id_inventario_resolucao: number | null;
  id_rodada_resolucao: number | null;
  tipo_resolucao: string | null;
  observacao_resolucao: string | null;
  criado_por: string;
  data_hora_criacao: string;
  resolvido_por: string | null;
  data_hora_resolucao: string | null;
  status_tratativa: string;
  possui_justificativa: boolean;
  resolvida: boolean;
  necessita_tratativa: boolean;
}

export interface TratativaCicloRotativo {
  localizacao: string;
  codigo: string;
  lote: string | null;
  tipo_divergencia_predominante: string | null;
  ocorrencias: number;
  recorrente: boolean;
  status_tratativa: string;
  necessita_tratativa: boolean;
  resumo: {
    sem_justificativa: number;
    justificadas_pendentes: number;
    em_tratativa: number;
    resolvidas: number;
  };
  ultima_ocorrencia: {
    id_ocorrencia: number;
    id_inventario: number;
    id_rodada: number | null;
    tipo_divergencia: string;
    diferenca: number | null;
    status_resolucao: string;
    justificativa: string | null;
    tipo_resolucao: string | null;
    observacao_resolucao: string | null;
    data_hora_criacao: string;
    resolvido_por: string | null;
    data_hora_resolucao: string | null;
  };
  historico_ocorrencias: OcorrenciaHistoricoTratativaRotativa[];
}

export interface TratativasCicloRotativoResposta {
  possui_ciclo_aberto: boolean;
  pesquisa?: {
    cliente_id: number;
    armazem: string;
    somente_pendentes: boolean;
    somente_recorrentes: boolean;
  };
  ciclo: {
    id_ciclo: number;
    codigo_ciclo: string;
    cliente_id: number;
    armazem: string;
    status: string;
    data_inicio: string | null;
  } | null;
  resumo: {
    grupos_divergencia: number;
    ocorrencias: number;
    sem_justificativa: number;
    justificadas_pendentes: number;
    em_tratativa: number;
    resolvidas: number;
    recorrentes: number;
    necessitam_tratativa: number;
  };
  tratativas: TratativaCicloRotativo[];
}

export interface ConsultarTratativasCicloRotativoParametros {
  clienteId: number;
  armazem: string;
  somentePendentes?: boolean;
  somenteRecorrentes?: boolean;
  signal?: AbortSignal;
}

export async function consultarTratativasCicloRotativo({
  clienteId,
  armazem,
  somentePendentes = false,
  somenteRecorrentes = false,
  signal,
}: ConsultarTratativasCicloRotativoParametros): Promise<TratativasCicloRotativoResposta> {
  if (!Number.isInteger(clienteId) || clienteId <= 0) {
    throw new Error("Cliente invalido.");
  }

  const armazemNormalizado = armazem.trim().toUpperCase();

  if (!armazemNormalizado) {
    throw new Error("Armazem invalido.");
  }

  const params = new URLSearchParams({
    cliente_id: String(clienteId),
    armazem: armazemNormalizado,
    somente_pendentes: String(somentePendentes),
    somente_recorrentes: String(somenteRecorrentes),
  });

  return apiRequest<TratativasCicloRotativoResposta>(
    `/rotativo/ciclos/tratativas?${params.toString()}`,
    signal ? { signal } : {},
  );
}

// ============================================================
// CONTEXTO GERENCIAL DA LOCALIZACAO ROTATIVA
// ============================================================

export interface HistoricoContagemLocalizacaoRotativa {
  id_historico: number;
  id_inventario: number | null;
  id_rodada: number | null;
  id_ciclo: number | null;
  data_hora_inicio: string | null;
  data_hora_fim: string | null;
  data_hora_contagem: string | null;
  usuario: string | null;
  localizacao_vazia: boolean;
  possui_divergencia: boolean;
  quantidade_itens: number | null;
  quantidade_itens_ok: number | null;
  quantidade_itens_divergentes: number | null;
  score_risco_na_data: number | null;
  classificacao_risco_na_data: string | null;
}

export interface OcorrenciaContextoLocalizacaoRotativa {
  id_ocorrencia: number;
  id_inventario: number;
  id_rodada: number | null;
  localizacao: string;
  codigo: string;
  lote: string | null;
  qtd_estoque: number | null;
  qtd_contada: number | null;
  diferenca: number | null;
  tipo_divergencia: string;
  status_resolucao: string;
  justificativa: string | null;
  status_tratativa: string;
  possui_justificativa: boolean;
  resolvida: boolean;
  necessita_tratativa: boolean;
  tipo_resolucao: string | null;
  observacao_resolucao: string | null;
  id_inventario_resolucao: number | null;
  id_rodada_resolucao: number | null;
  criado_por: string;
  data_hora_criacao: string;
  resolvido_por: string | null;
  data_hora_resolucao: string | null;
  cliente_id: number;
}

export interface GrupoDivergenciaLocalizacaoRotativa {
  localizacao: string;
  codigo: string;
  lote: string | null;
  ocorrencias: number;
  recorrente: boolean;
  status_tratativa: string;
  necessita_tratativa: boolean;
  resumo: {
    justificadas: number;
    sem_justificativa: number;
    resolvidas: number;
    pendentes: number;
  };
  ultima_ocorrencia: OcorrenciaContextoLocalizacaoRotativa;
}

export interface EficaciaResolucaoLocalizacaoRotativa {
  id_ocorrencia: number;
  codigo: string;
  lote: string | null;
  tipo_resolucao: string | null;
  data_resolucao: string | null;
  eficacia: {
    classificacao: "EFICAZ" | "NAO_EFICAZ" | "AINDA_SEM_EVIDENCIA" | string;
    motivo: string;
    nova_ocorrencia?: number;
    data_nova_ocorrencia?: string | null;
    id_historico_validacao?: number;
    data_validacao?: string | null;
  } | null;
}

export interface ContextoLocalizacaoRotativaResposta {
  tipo_contexto: "CONTEXTO_LOCALIZACAO_ROTATIVO";
  cliente_id: number;
  armazem: string;
  localizacao: string;
  ciclo: {
    id_ciclo: number;
    codigo_ciclo: string;
    status: string;
    data_inicio: string | null;
    data_fim_prevista: string | null;
    localizacao_pertence_ciclo: boolean;
    localizacao?: {
      id_ciclo_localizacao: number;
      status: string;
      data_inclusao: string | null;
      data_inicio_contagem: string | null;
      data_conclusao: string | null;
      id_inventario: number | null;
      id_rodada: number | null;
      usuario: string | null;
    };
  } | null;
  cadastro: {
    id_rotativo_localizacao: number;
    status: string;
    ultima_contagem: string | null;
    id_inventario_ultima_contagem: number | null;
    id_rodada_ultima_contagem: number | null;
    data_hora_atualizacao: string | null;
  };
  risco: {
    score: number | null;
    classificacao: string | null;
  };
  priorizacao: {
    sugerida: boolean;
    prioridade: number | null;
    tipo_sugestao: string | null;
    score_snapshot_ciclo: number | null;
    classificacao_snapshot_ciclo: string | null;
  };
  historico: {
    resumo: {
      contagens: number;
      contagens_ok: number;
      contagens_com_divergencia: number;
      taxa_divergencia_percentual: number;
      divergencias_consecutivas: number;
      ultima_contagem: string | null;
      ultima_divergencia: string | null;
    };
    contagens: HistoricoContagemLocalizacaoRotativa[];
  };
  divergencias: {
    ocorrencias: number;
    ocorrencias_resolvidas: number;
    ocorrencias_pendentes: number;
    grupos_divergencia: number;
    grupos_recorrentes: number;
    grupos_pendentes: number;
    possui_recorrencia: boolean;
    necessita_tratativa: boolean;
    grupos: GrupoDivergenciaLocalizacaoRotativa[];
    historico_ocorrencias: OcorrenciaContextoLocalizacaoRotativa[];
  };
  eficacia: {
    resolucoes_avaliadas: number;
    resolucoes: EficaciaResolucaoLocalizacaoRotativa[];
  };
}

export interface ConsultarContextoLocalizacaoRotativaParametros {
  clienteId: number;
  armazem: string;
  localizacao: string;
  limiteHistorico?: number;
  signal?: AbortSignal;
}

export async function consultarContextoLocalizacaoRotativa({
  clienteId,
  armazem,
  localizacao,
  limiteHistorico = 10,
  signal,
}: ConsultarContextoLocalizacaoRotativaParametros): Promise<ContextoLocalizacaoRotativaResposta> {
  if (!Number.isInteger(clienteId) || clienteId <= 0) {
    throw new Error("Cliente invalido.");
  }

  const armazemNormalizado = armazem.trim().toUpperCase();
  const localizacaoNormalizada = localizacao.trim().toUpperCase();

  if (!armazemNormalizado) {
    throw new Error("Armazem invalido.");
  }

  if (!localizacaoNormalizada) {
    throw new Error("Localizacao invalida.");
  }

  if (
    !Number.isInteger(limiteHistorico) ||
    limiteHistorico < 1 ||
    limiteHistorico > 100
  ) {
    throw new Error("O limite do historico deve estar entre 1 e 100.");
  }

  const params = new URLSearchParams({
    cliente_id: String(clienteId),
    armazem: armazemNormalizado,
    localizacao: localizacaoNormalizada,
    limite_historico: String(limiteHistorico),
  });

  return apiRequest<ContextoLocalizacaoRotativaResposta>(
    `/rotativo/contexto/localizacao?${params.toString()}`,
    signal ? { signal } : {},
  );
}

// ============================================================
// RESOLUCAO DE TRATATIVA ROTATIVA
// ============================================================

export type TipoResolucaoTratativaRotativa =
  | "RECONTAGEM"
  | "AJUSTE_ESTOQUE"
  | "OFICIAL";

export interface ResolverTratativaRotativaPayload {
  tipo_resolucao: TipoResolucaoTratativaRotativa;
  observacao_resolucao?: string | null;
  resolvido_por: string;
  id_inventario_resolucao?: number | null;
  id_rodada_resolucao?: number | null;
}

export interface OcorrenciaResolvidaTratativaRotativa {
  id_ocorrencia: number;
  status_resolucao: string;
  tipo_resolucao: string | null;
  observacao_resolucao?: string | null;
  id_inventario_resolucao?: number | null;
  id_rodada_resolucao?: number | null;
  resolvido_por: string | null;
  data_hora_resolucao: string | null;
}

export interface ResolverTratativaRotativaResposta {
  resolvido: boolean;
  motivo: string;
  ocorrencia: OcorrenciaResolvidaTratativaRotativa;
  inteligencia: Record<string, unknown> | null;
}

export async function resolverTratativaRotativa(
  idOcorrencia: number,
  dados: ResolverTratativaRotativaPayload,
): Promise<ResolverTratativaRotativaResposta> {
  if (!Number.isInteger(idOcorrencia) || idOcorrencia <= 0) {
    throw new Error("Ocorrencia invalida.");
  }

  if (!dados.resolvido_por.trim()) {
    throw new Error("Usuario responsavel invalido.");
  }

  if (
    dados.id_rodada_resolucao != null &&
    dados.id_inventario_resolucao == null
  ) {
    throw new Error(
      "Informe o inventario relacionado antes da rodada.",
    );
  }

  return apiRequest<ResolverTratativaRotativaResposta>(
    `/rotativo/ciclos/tratativas/${idOcorrencia}/resolver`,
    {
      method: "POST",
      body: dados,
    },
  );
}

// ============================================================
// FINALIZACAO DO CICLO ROTATIVO
// ============================================================

export interface CicloFinalizadoRotativo {
  id_ciclo: number;
  codigo_ciclo: string;
  cliente_id?: number;
  armazem?: string;
  status: string;
  data_inicio?: string | null;
  data_fim_prevista?: string | null;
  data_fim_real?: string | null;
  finalizado_por?: string | null;
  total_localizacoes?: number;
  pendentes?: number;
  em_contagem?: number;
  contadas?: number;
  ignoradas?: number;
  processadas?: number;
}

export interface ResultadoFinalizacaoCicloRotativo {
  total_localizacoes: number;
  localizacoes_contadas: number;
  localizacoes_ignoradas: number;
  localizacoes_processadas: number;
  localizacoes_pendentes: number;
  localizacoes_em_contagem: number;
  percentual_contado: number;
  percentual_processado: number;
  ciclo_concluido: boolean;
}

export interface FinalizarCicloRotativoResposta {
  finalizado: boolean;
  motivo: string;
  ciclo?: CicloFinalizadoRotativo;
  resultado?: ResultadoFinalizacaoCicloRotativo;
  status_encontrados?: Record<string, number>;
  mensagem?: string;
}

export async function finalizarCicloRotativo(
  idCiclo: number,
  finalizadoPor: string,
): Promise<FinalizarCicloRotativoResposta> {
  if (!Number.isInteger(idCiclo) || idCiclo <= 0) {
    throw new Error("Ciclo rotativo invalido.");
  }

  const usuario = finalizadoPor.trim();
  if (!usuario) {
    throw new Error("Nao foi possivel identificar o usuario responsavel.");
  }

  const params = new URLSearchParams({ finalizado_por: usuario });
  return apiRequest<FinalizarCicloRotativoResposta>(
    `/rotativo/ciclos/${idCiclo}/finalizar?${params.toString()}`,
    { method: "POST", body: {} },
  );
}

// ============================================================
// IGNORAR LOCALIZACAO DO CICLO ROTATIVO
// ============================================================

export interface IgnorarLocalizacaoCicloRotativoPayload {
  id_ciclo_localizacao: number;
  motivo: string;
  usuario: string;
}

export interface CoberturaAposIgnorarLocalizacaoRotativa {
  total_localizacoes: number;
  localizacoes_contadas: number;
  localizacoes_ignoradas: number;
  localizacoes_pendentes: number;
  localizacoes_processadas: number;
  percentual_cobertura: number;
  ciclo_concluido: boolean;
}

export interface IgnorarLocalizacaoCicloRotativoResposta {
  atualizado: boolean;
  motivo: string;
  id_ciclo?: number;
  codigo_ciclo?: string;
  id_ciclo_localizacao: number;
  localizacao: string;
  status?: string;
  status_anterior?: string;
  status_atual?: string;
  justificativa?: string;
  ciclo?: CoberturaAposIgnorarLocalizacaoRotativa;
}

export async function ignorarLocalizacaoCicloRotativo(
  dados: IgnorarLocalizacaoCicloRotativoPayload,
): Promise<IgnorarLocalizacaoCicloRotativoResposta> {
  if (
    !Number.isInteger(dados.id_ciclo_localizacao) ||
    dados.id_ciclo_localizacao <= 0
  ) {
    throw new Error("Localizacao do ciclo invalida.");
  }

  const motivo = dados.motivo.trim();
  const usuario = dados.usuario.trim();

  if (!motivo) {
    throw new Error("O motivo para ignorar a localizacao e obrigatorio.");
  }

  if (!usuario) {
    throw new Error("Nao foi possivel identificar o usuario autenticado.");
  }

  return apiRequest<IgnorarLocalizacaoCicloRotativoResposta>(
    "/rotativo/ciclos/localizacoes/ignorar",
    {
      method: "POST",
      body: {
        id_ciclo_localizacao: dados.id_ciclo_localizacao,
        motivo,
        usuario,
      },
    },
  );
}




export interface ItemDecisaoRotativoLote {
  localizacao: string;
  codigo: string;
  lote?: string | null;
}

export interface DecisaoRotativoLoteEntrada {
  id_rodada: number;
  decisao: "RECONTAR" | "JUSTIFICAR_DIVERGENCIA";
  justificativa?: string | null;
  itens: ItemDecisaoRotativoLote[];
}

export interface DecisaoRotativoLoteResposta {
  sucesso: boolean;
  quantidade_processada: number;
  decisao: string;
  mensagem: string;
  resultados: Array<Record<string, unknown>>;
}

export async function registrarDecisoesRotativoLote(
  idInventario: number,
  dados: DecisaoRotativoLoteEntrada,
) {
  return apiRequest<DecisaoRotativoLoteResposta>(
    `/inventarios/${idInventario}/decisoes-rotativo/lote`,
    {
      method: "POST",
      body: dados,
    },
  );
}
