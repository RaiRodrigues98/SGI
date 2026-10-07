import { apiRequest } from "@/services/apiClient";

export interface InventarioOficial {
  id_inventario: number;
  codigo_inventario: string;
  tipo: string;
  cliente: string;
  cliente_id: number;
  descricao: string | null;
  armazem: string;
  rodada_atual: number;
  status: string;
  em_analise_gestor: boolean;
  data_hora_encaminhamento_gestor: string | null;
  encaminhado_gestor_por: string | null;
}

export interface RodadaAtualOficial {
  id_inventario: number;
  codigo_inventario: string;
  tipo_inventario: string;
  rodada_atual: number;
  id_rodada: number;
  numero_rodada: number;
  status: string;
  data_hora_inicio: string | null;
}

export interface LocalizacaoBipadaOficial {
  localizacao: string;
  quantidade: number;
}

export interface ItemAnaliseOficial {
  chave: string;
  codigo: string;
  lote: string;
  descricao: string | null;
  unidade: string | null;
  categoria: string | null;
  qtd_estoque: number;
  qtd_contada: number;
  diferenca: number;
  status: string;
  subtipo_divergencia: string | null;
  detalhe: string | null;
  resultado_definitivo: boolean;
  localizacoes_bipadas: LocalizacaoBipadaOficial[];
}

export interface AnaliseOficial {
  tipo_analise: "OFICIAL";
  id_inventario: number;
  codigo_inventario: string;
  id_rodada: number;
  numero_rodada: number;
  status_rodada: string;
  regra_conciliacao: string;
  considera_localizacao: boolean;
  resumo: {
    total_registros: number;
    ok: number;
    divergencias: number;
    faltas: number;
    sobras: number;
    aguardando_contagem: number;
  };
  itens: ItemAnaliseOficial[];
}

export async function listarInventariosOficiais() {
  return apiRequest<InventarioOficial[]>("/inventarios?tipo=OFICIAL");
}

export async function buscarRodadaAtualOficial(idInventario: number) {
  return apiRequest<RodadaAtualOficial>(
    `/inventarios/${idInventario}/rodada-atual`,
  );
}

export async function buscarAnaliseOficial(
  idInventario: number,
  idRodada: number,
) {
  return apiRequest<AnaliseOficial>(
    `/inventarios/${idInventario}/rodadas/${idRodada}/analise`,
  );
}
