import { apiRequest } from "@/services/apiClient";

export interface RodadaAtual {
  id_inventario: number;
  codigo_inventario: string;
  tipo_inventario: string;
  rodada_atual: number;
  id_rodada: number;
  numero_rodada: number;
  status: string;
  data_hora_inicio: string | null;
}

export interface ItemCandidatoProximaRodada {
  codigo?: string;
  lote?: string | null;
  status?: string | null;
  localizacao?: string;
  localizacoes?: string[];
  [key: string]: unknown;
}

export interface ConfiguracaoPreviewRodada {
  rodadas_iniciais: number;
  max_rodadas: number;
  permitir_gestor_antecipado: boolean;
  limite_itens_gestor_antecipado: number;
}

export interface PreviewProximaRodada {
  pode_criar: boolean;
  pode_encerrar?: boolean;
  motivo: string | null;
  id_inventario?: number;
  numero_rodada_atual: number;
  numero_proxima_rodada: number | null;
  tipo_proxima_rodada: string;
  candidatos: number;
  origem_candidatos?: string | null;
  pode_encaminhar_gestor: boolean;
  sessoes_abertas?: number;
  id_rodada_existente?: number;
  configuracao?: ConfiguracaoPreviewRodada;
  itens_candidatos?: ItemCandidatoProximaRodada[];
  resumo_r2?: Record<string, unknown>;
}

export interface PreviewProximaRodadaResposta {
  id_inventario: number;
  codigo_inventario: string;
  tipo_inventario: string;
  status_inventario: string;
  preview: PreviewProximaRodada;
}

export interface ProximaRodadaCriada {
  criada: boolean;
  id_rodada: number;
  numero_rodada: number;
  status: string;
  data_hora_inicio: string | null;
  tipo_rodada: string;
  rodada_origem: number;
  rodada_anterior_finalizada?: boolean;
  origem_candidatos?: string | null;
  itens_gerados?: number;
  localizacoes_geradas?: number;
  localizacoes?: string[];
  candidatos?: number;
  configuracao?: {
    rodadas_iniciais: number;
    max_rodadas: number;
    recontagem_por_localizacao: boolean;
    permitir_gestor_antecipado: boolean;
    limite_itens_gestor_antecipado: number;
  };
  pode_encaminhar_gestor?: boolean;
  mensagem?: string;
}

export interface GerarProximaRodadaResposta {
  sucesso: boolean;
  id_inventario: number;
  codigo_inventario: string;
  tipo_inventario: string;
  rodada_anterior: number;
  proxima_rodada: ProximaRodadaCriada;
}

export interface SincronizacaoLocalizacoesResultado {
  id_inventario: number;
  id_rodada: number;
  numero_rodada: number;
  localizacoes_geradas: number;
  localizacoes: string[];
}

export interface SincronizarLocalizacoesResposta {
  sucesso: boolean;
  id_inventario: number;
  codigo_inventario: string;
  id_rodada: number;
  numero_rodada: number;
  resultado: SincronizacaoLocalizacoesResultado;
}

export async function buscarRodadaAtual(
  idInventario: number,
): Promise<RodadaAtual> {
  return apiRequest<RodadaAtual>(
    `/inventarios/${idInventario}/rodada-atual`,
  );
}

export async function buscarPreviewProximaRodada(
  idInventario: number,
): Promise<PreviewProximaRodadaResposta> {
  return apiRequest<PreviewProximaRodadaResposta>(
    `/inventarios/${idInventario}/rodadas/proxima-preview`,
  );
}

export async function gerarProximaRodada(
  idInventario: number,
): Promise<GerarProximaRodadaResposta> {
  return apiRequest<GerarProximaRodadaResposta>(
    `/inventarios/${idInventario}/rodadas/proxima`,
    {
      method: "POST",
      body: {},
    },
  );
}

export async function sincronizarLocalizacoesRodada(
  idInventario: number,
  idRodada: number,
): Promise<SincronizarLocalizacoesResposta> {
  return apiRequest<SincronizarLocalizacoesResposta>(
    `/inventarios/${idInventario}/rodadas/${idRodada}/sincronizar-localizacoes`,
    {
      method: "POST",
      body: {},
    },
  );
}
