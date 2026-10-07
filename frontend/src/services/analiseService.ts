import { apiRequest } from "@/services/apiClient";

export interface SessaoContagem {
  id_sessao: number;
  id_inventario: number;
  id_rodada: number;
  localizacao: string;
  status: string;
  localizacao_vazia: boolean;
  data_hora_inicio: string;
  data_hora_fim: string | null;
  itens_registrados: number;
  quantidade_total: number;
}

export type StatusAnalise =
  | "OK"
  | "DIVERGÊNCIA"
  | "FALTA"
  | "SOBRA"
  | "AGUARDANDO_CONTAGEM"
  | string;

interface DecisaoRotativo {
  possui_decisao: boolean;
  id_decisao_rotativo: number | null;
  decisao: string | null;
  justificativa: string | null;
  usuario: string | null;
  data_hora: string | null;
}

interface ItemRotativoApi {
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
  status: StatusAnalise;
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

interface AnaliseRotativoApi {
  tipo_analise: "ROTATIVO_SESSAO";
  id_sessao: number;
  id_inventario: number;
  id_rodada: number;
  numero_rodada: number;
  localizacao: string;
  status_sessao: string;
  regra_conciliacao: string;
  considera_localizacao: true;
  contagem_cega: boolean;
  itens: ItemRotativoApi[];
}

interface ItemOficialApi {
  chave: string;
  codigo: string;
  lote: string;
  descricao: string | null;
  unidade: string | null;
  categoria: string | null;
  qtd_estoque: number;
  qtd_contada_sessao: number;
  diferenca_sessao: number;
  status_sessao: StatusAnalise;
  localizacao_bipada: string;
}

interface AnaliseOficialApi {
  tipo_analise: "OFICIAL";
  id_sessao: number;
  id_inventario: number;
  id_rodada: number;
  localizacao_bipada: string;
  status_sessao: string;
  observacao: string;
  itens: ItemOficialApi[];
}

type AnaliseSessaoApi = AnaliseRotativoApi | AnaliseOficialApi;

export interface AnaliseItem {
  chave: string;
  codigo: string;
  lote: string;
  descricao: string | null;
  localizacao: string;
  qtd_estoque: number;
  qtd_contada: number;
  diferenca: number;
  status: StatusAnalise;
  subtipo_divergencia: string | null;
  requer_decisao: boolean;
  pendente_decisao: boolean;
  pendente_recontagem: boolean;
  divergencia_justificada: boolean;
  decisao: DecisaoRotativo | null;
}

export interface AnaliseSessao {
  tipo: "ROTATIVO" | "OFICIAL";
  id_sessao: number;
  id_inventario: number;
  id_rodada: number;
  numero_rodada: number | null;
  localizacao: string;
  status_sessao: string;
  observacao: string | null;
  regra_conciliacao: string;
  itens: AnaliseItem[];
}

export function listarSessoes(): Promise<SessaoContagem[]> {
  return apiRequest<SessaoContagem[]>("/sessoes");
}

export async function buscarAnaliseSessao(
  idSessao: number,
): Promise<AnaliseSessao> {
  if (!Number.isInteger(idSessao) || idSessao <= 0) {
    throw new Error("Sessão inválida.");
  }

  const dados = await apiRequest<AnaliseSessaoApi>(
    `/sessoes/${idSessao}/analise`,
  );

  if (dados.tipo_analise === "ROTATIVO_SESSAO") {
    return {
      tipo: "ROTATIVO",
      id_sessao: dados.id_sessao,
      id_inventario: dados.id_inventario,
      id_rodada: dados.id_rodada,
      numero_rodada: dados.numero_rodada,
      localizacao: dados.localizacao,
      status_sessao: dados.status_sessao,
      observacao: null,
      regra_conciliacao: dados.regra_conciliacao,
      itens: dados.itens.map((item) => ({
        chave: item.chave,
        codigo: item.codigo,
        lote: item.lote ?? "",
        descricao: item.produto,
        localizacao: item.localizacao,
        qtd_estoque: Number(item.qtd_estoque),
        qtd_contada: Number(item.qtd_contada),
        diferenca: Number(item.diferenca),
        status: item.status,
        subtipo_divergencia: item.subtipo_divergencia,
        requer_decisao: Boolean(item.requer_decisao),
        pendente_decisao: Boolean(item.pendente_decisao),
        pendente_recontagem: Boolean(item.pendente_recontagem),
        divergencia_justificada: Boolean(item.divergencia_justificada),
        decisao: item.decisao_rotativo ?? null,
      })),
    };
  }

  return {
    tipo: "OFICIAL",
    id_sessao: dados.id_sessao,
    id_inventario: dados.id_inventario,
    id_rodada: dados.id_rodada,
    numero_rodada: null,
    localizacao: dados.localizacao_bipada,
    status_sessao: dados.status_sessao,
    observacao: dados.observacao,
    regra_conciliacao: "CODIGO_LOTE",
    itens: dados.itens.map((item) => ({
      chave: item.chave,
      codigo: item.codigo,
      lote: item.lote ?? "",
      descricao: item.descricao,
      localizacao: item.localizacao_bipada,
      qtd_estoque: Number(item.qtd_estoque),
      qtd_contada: Number(item.qtd_contada_sessao),
      diferenca: Number(item.diferenca_sessao),
      status: item.status_sessao,
      subtipo_divergencia: null,
      requer_decisao: false,
      pendente_decisao: false,
      pendente_recontagem: false,
      divergencia_justificada: false,
      decisao: null,
    })),
  };
}
