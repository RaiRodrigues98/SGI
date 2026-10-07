import { apiRequest } from "@/services/apiClient";

// ============================================================
// OFICIAL - COMPARATIVO R1 x R2
// ============================================================

export interface RodadaComparativaOficial {
  quantidade: number;
  diferenca: number;
  status: string;
  localizacoes_bipadas: unknown[];
}

export interface ItemComparativoOficial {
  chave: string;
  codigo: string;
  lote: string | null;
  descricao: string | null;
  unidade: string | null;
  categoria: string | null;
  qtd_estoque: number;

  localizacoes_snapshot: unknown[];

  rodada_1: RodadaComparativaOficial;
  rodada_2: RodadaComparativaOficial;

  vai_para_r3: boolean;
  motivo_r3: string | null;
  localizacoes_para_recontagem: string[];
}

export interface ComparativoRodadasOficial {
  id_inventario: number;
  codigo_inventario: string;
  tipo: string;
  cliente_id: number | null;
  rodada_atual: number;

  resumo: {
    total_itens: number;
    rodada_1_ok: number;
    rodada_2_ok: number;
    candidatos_r3: number;
  };

  itens: ItemComparativoOficial[];
}

// ============================================================
// OFICIAL - R3+
// ============================================================

export interface ItemRecontagemOficial {
  chave: string;
  codigo: string;
  lote: string | null;
  descricao: string | null;
  unidade: string | null;
  categoria: string | null;

  origem: string;
  item_original_recontagem: boolean;
  motivo_entrada_rodada: string | null;

  qtd_estoque: number;
  qtd_contada: number;
  diferenca: number;

  status: string;
  resultado_definitivo: boolean;

  localizacoes_snapshot: unknown[];
  localizacoes_bipadas: unknown[];

  pendente_proxima_rodada: boolean;
}

export interface AnaliseRecontagemOficial {
  tipo_analise: "RECONTAGEM_OFICIAL";

  id_inventario: number;
  codigo_inventario: string;

  id_rodada: number;
  numero_rodada: number;
  status_rodada: string;

  regra_conciliacao: string;
  considera_localizacao: boolean;
  contagem_cega: boolean;

  status_recontagem: string;
  rodada_operacional_concluida: boolean;
  pode_gerar_proxima_rodada: boolean;
  pode_finalizar_sem_divergencia: boolean;

  resumo: {
    total_itens: number;
    itens_originais_recontagem: number;
    itens_novos_encontrados: number;
    ok: number;
    divergencias: number;
    faltas: number;
    sobras: number;
    aguardando_contagem: number;
    pendentes_proxima_rodada: number;
    total_localizacoes: number;
    localizacoes_concluidas: number;
    localizacoes_pendentes: number;
    [key: string]: number;
  };

  itens: ItemRecontagemOficial[];
}

// ============================================================
// ROTATIVO - R2+
// ============================================================

export interface LocalizacaoRecontagemRotativo {
  localizacao: string;
  qtd_wms: number;
  qtd_r1: number;
  qtd_r2: number;
  diferenca_r2_wms: number;
  status: string;
}

export interface ItemRecontagemRotativo {
  codigo: string;
  lote: string | null;

  qtd_wms_total: number;
  qtd_r1_total: number;
  qtd_r2_total: number;
  diferenca_r2_wms_total: number;

  classificacao: string;
  requer_gestor: boolean;
  pendente_proxima_rodada: boolean;

  localizacoes: LocalizacaoRecontagemRotativo[];
}

export interface AnaliseRecontagemRotativo {
  id_inventario: number;
  id_rodada: number;
  numero_rodada: number;

  rodada_operacional_concluida: boolean;

  total_localizacoes?: number;
  localizacoes_concluidas?: number;
  localizacoes_pendentes?: number;

  resumo: {
    total_itens: number;
    resolvidos_r2: number;
    divergencias_confirmadas: number;
    divergencias_localizacao: number;
    inconsistencias_r1_r2: number;
    itens_para_gestor: number;
    itens_para_nova_recontagem: number;
  };

  pode_encerrar_sem_gestor: boolean;

  itens: ItemRecontagemRotativo[];
}

export type AnaliseRecontagem =
  | AnaliseRecontagemOficial
  | AnaliseRecontagemRotativo;

export interface RodadaHistoricoInventario {
  id_rodada: number;
  numero_rodada: number;
  status: string;
}

export interface HistoricoRodadasInventario {
  id_inventario: number;
  codigo_inventario: string;
  tipo: string;
  rodada_atual: number;
  status_inventario: string;
  total_rodadas: number;
  rodadas: RodadaHistoricoInventario[];
}

// ============================================================
// API
// ============================================================

export async function buscarComparativoRodadas(
  idInventario: number,
) {
  return apiRequest<ComparativoRodadasOficial>(
    `/inventarios/${idInventario}/comparativo-rodadas`,
  );
}

export async function buscarAnaliseRecontagem(
  idInventario: number,
  idRodada: number,
) {
  return apiRequest<AnaliseRecontagem>(
    `/inventarios/${idInventario}/rodadas/${idRodada}/analise-recontagem`,
  );
}

export async function buscarRodadasInventario(
  idInventario: number,
) {
  return apiRequest<HistoricoRodadasInventario>(
    `/inventarios/${idInventario}/rodadas`,
  );
}

