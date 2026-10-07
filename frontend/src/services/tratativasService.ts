import { ApiError, apiRequest } from "@/services/apiClient";

// ============================================================
// OCORRENCIAS
// ============================================================

export interface OcorrenciaTratativa {
  id_ocorrencia: number;
  cliente_id: number;
  id_inventario: number;
  id_rodada: number | null;
  tipo_inventario: string;
  localizacao: string | null;
  codigo: string;
  lote: string;
  qtd_estoque: number;
  qtd_contada: number;
  diferenca: number;
  tipo_divergencia: string;
  subtipo_divergencia: string | null;
  status_resolucao: string;
  justificativa: string | null;
  tipo_resolucao: string | null;
  observacao_resolucao: string | null;
  criado_por: string;
  data_hora_criacao: string;
  resolvido_por: string | null;
  data_hora_resolucao: string | null;
}

export interface FiltrosOcorrenciasTratativas {
  cliente_id: number | null;
  id_inventario: number | null;
  status: string | null;
  localizacao: string | null;
  codigo: string | null;
  somente_pendentes: boolean;
}

export interface PaginacaoTratativas {
  page: number;
  page_size: number;
  total_registros: number;
  total_paginas: number;
  registros_pagina: number;
  tem_anterior: boolean;
  tem_proxima: boolean;
}

export interface OcorrenciasTratativasResponse {
  filtros: FiltrosOcorrenciasTratativas;
  paginacao: PaginacaoTratativas;
  ocorrencias: OcorrenciaTratativa[];
}

export interface ListarOcorrenciasTratativasParams {
  clienteId?: number | null;
  idInventario?: number | null;
  status?: string | null;
  localizacao?: string | null;
  codigo?: string | null;
  somentePendentes?: boolean;
  page?: number;
  pageSize?: number;
}

export async function listarOcorrenciasTratativas(
  {
    clienteId,
    idInventario,
    status,
    localizacao,
    codigo,
    somentePendentes = true,
    page = 1,
    pageSize = 50,
  }: ListarOcorrenciasTratativasParams = {},
): Promise<OcorrenciasTratativasResponse> {
  const params = new URLSearchParams();

  if (clienteId != null) {
    params.set("cliente_id", String(clienteId));
  }

  if (idInventario != null) {
    params.set("id_inventario", String(idInventario));
  }

  if (status?.trim()) {
    params.set("status", status.trim());
  }

  if (localizacao?.trim()) {
    params.set("localizacao", localizacao.trim());
  }

  if (codigo?.trim()) {
    params.set("codigo", codigo.trim());
  }

  params.set("somente_pendentes", String(somentePendentes));
  params.set("page", String(page));
  params.set("page_size", String(pageSize));

  return apiRequest<OcorrenciasTratativasResponse>(
    `/ocorrencias?${params.toString()}`,
  );
}

// ============================================================
// ANALISE / CAUSA RAIZ
// ============================================================

export interface AnalisePayload {
  categoria_causa: string;
  causa_raiz: string;
  observacao?: string | null;
}

export type StatusAnaliseOcorrencia =
  | "ATIVA"
  | "ENCERRADA";

export interface AnaliseOcorrencia {
  id_analise: number;
  id_ocorrencia: number;
  categoria_causa: string;
  causa_raiz: string;
  observacao: string | null;
  status: StatusAnaliseOcorrencia;
  analisado_por: string;
  data_hora_analise: string;
  data_hora_criacao: string;
  data_hora_atualizacao: string | null;
  atualizado_por: string | null;
  encerrado_por: string | null;
  data_hora_encerramento: string | null;
}

export async function consultarAnaliseOcorrencia(
  idOcorrencia: number,
): Promise<AnaliseOcorrencia | null> {
  try {
    return await apiRequest<AnaliseOcorrencia>(
      `/ocorrencias/${idOcorrencia}/analise`,
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }

    throw error;
  }
}

export async function criarAnaliseOcorrencia(
  idOcorrencia: number,
  dados: AnalisePayload,
): Promise<AnaliseOcorrencia> {
  return apiRequest<AnaliseOcorrencia>(
    `/ocorrencias/${idOcorrencia}/analise`,
    {
      method: "POST",
      body: dados,
    },
  );
}

export async function atualizarAnaliseOcorrencia(
  idAnalise: number,
  dados: AnalisePayload,
): Promise<AnaliseOcorrencia> {
  return apiRequest<AnaliseOcorrencia>(
    `/analises/${idAnalise}`,
    {
      method: "PUT",
      body: dados,
    },
  );
}

export async function encerrarAnaliseOcorrencia(
  idAnalise: number,
): Promise<AnaliseOcorrencia> {
  return apiRequest<AnaliseOcorrencia>(
    `/analises/${idAnalise}/encerrar`,
    {
      method: "POST",
      body: {},
    },
  );
}

// ============================================================
// PLANOS DE ACAO
// ============================================================

export type PrioridadePlanoAcao =
  | "CRITICA"
  | "ALTA"
  | "MEDIA"
  | "BAIXA";

export type StatusPlanoAcao =
  | "ABERTO"
  | "EM_ANDAMENTO"
  | "CONCLUIDO"
  | "CANCELADO";

export interface PlanoAcao {
  id_plano_acao: number;
  id_analise: number;
  descricao_acao: string;
  responsavel: string;
  data_prazo: string;
  prioridade: PrioridadePlanoAcao;
  status: StatusPlanoAcao;
  observacao: string | null;
  criado_por: string;
  data_hora_criacao: string;
  atualizado_por: string | null;
  data_hora_atualizacao: string | null;
  concluido_por: string | null;
  data_hora_conclusao: string | null;
}

export interface CriarPlanoAcaoPayload {
  descricao_acao: string;
  responsavel: string;
  data_prazo: string;
  prioridade: PrioridadePlanoAcao;
  observacao?: string | null;
}

export interface AtualizarPlanoAcaoPayload
  extends CriarPlanoAcaoPayload {
  status: Exclude<StatusPlanoAcao, "CONCLUIDO">;
}

export async function listarPlanosAcao(
  idAnalise: number,
): Promise<PlanoAcao[]> {
  return apiRequest<PlanoAcao[]>(
    `/analises/${idAnalise}/planos`,
  );
}

export async function consultarPlanoAcao(
  idPlano: number,
): Promise<PlanoAcao> {
  return apiRequest<PlanoAcao>(
    `/planos-acao/${idPlano}`,
  );
}

export async function criarPlanoAcao(
  idAnalise: number,
  dados: CriarPlanoAcaoPayload,
): Promise<PlanoAcao> {
  return apiRequest<PlanoAcao>(
    `/analises/${idAnalise}/planos`,
    {
      method: "POST",
      body: dados,
    },
  );
}

export async function atualizarPlanoAcao(
  idPlano: number,
  dados: AtualizarPlanoAcaoPayload,
): Promise<PlanoAcao> {
  return apiRequest<PlanoAcao>(
    `/planos-acao/${idPlano}`,
    {
      method: "PUT",
      body: dados,
    },
  );
}

export async function concluirPlanoAcao(
  idPlano: number,
): Promise<PlanoAcao> {
  return apiRequest<PlanoAcao>(
    `/planos-acao/${idPlano}/concluir`,
    {
      method: "POST",
      body: {},
    },
  );
}

// ============================================================
// EVIDENCIAS
// ============================================================

export interface EvidenciaPlano {
  id_evidencia: number;
  id_plano_acao: number;
  tipo_evidencia: string;
  descricao: string | null;
  referencia_arquivo: string | null;
  criado_por: string;
  data_hora_criacao: string;
}

export interface CriarEvidenciaPayload {
  tipo_evidencia: string;
  descricao?: string | null;
  referencia_arquivo?: string | null;
}

export async function listarEvidenciasPlano(
  idPlano: number,
): Promise<EvidenciaPlano[]> {
  return apiRequest<EvidenciaPlano[]>(
    `/planos-acao/${idPlano}/evidencias`,
  );
}

export async function criarEvidenciaPlano(
  idPlano: number,
  dados: CriarEvidenciaPayload,
): Promise<EvidenciaPlano> {
  return apiRequest<EvidenciaPlano>(
    `/planos-acao/${idPlano}/evidencias`,
    {
      method: "POST",
      body: dados,
    },
  );
}

export async function removerEvidenciaPlano(
  idEvidencia: number,
): Promise<EvidenciaPlano> {
  return apiRequest<EvidenciaPlano>(
    `/evidencias/${idEvidencia}`,
    {
      method: "DELETE",
    },
  );
}

// ============================================================
// VALIDACAO DE EFICACIA
// ============================================================

export type ResultadoValidacaoEficacia =
  | "EFICAZ"
  | "INEFICAZ";

export interface ValidacaoEficaciaPlano {
  id_validacao_eficacia: number;
  id_plano_acao: number;
  resultado: ResultadoValidacaoEficacia;
  criterio_validacao: string;
  observacao: string | null;
  validado_por: string;
  data_hora_validacao: string;
  data_hora_criacao: string;
}

export interface CriarValidacaoEficaciaPayload {
  resultado: ResultadoValidacaoEficacia;
  criterio_validacao: string;
  observacao?: string | null;
}

export async function listarValidacoesEficacia(
  idPlano: number,
): Promise<ValidacaoEficaciaPlano[]> {
  return apiRequest<ValidacaoEficaciaPlano[]>(
    `/planos-acao/${idPlano}/validacoes-eficacia`,
  );
}

export async function criarValidacaoEficacia(
  idPlano: number,
  dados: CriarValidacaoEficaciaPayload,
): Promise<ValidacaoEficaciaPlano> {
  return apiRequest<ValidacaoEficaciaPlano>(
    `/planos-acao/${idPlano}/validacoes-eficacia`,
    {
      method: "POST",
      body: dados,
    },
  );
}

