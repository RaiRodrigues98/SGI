import { apiRequest } from "@/services/apiClient";

export type DecisaoGestor =
  "ACEITAR_ESTOQUE" | "ACEITAR_CONTAGEM" | "NOVA_RECONTAGEM";

export interface LocalizacaoGerencial {
  localizacao: string;
  quantidade: number;
}

export interface RodadaGerencial {
  id_rodada: number;
  numero_rodada: number;
  status: string;
  data_hora_inicio: string | null;
}

export interface HistoricoItemGerencial {
  numero_rodada: number;
  id_rodada: number;
  participou: boolean;
  quantidade: number | null;
  diferenca: number | null;
  status: string;
  localizacoes_bipadas: LocalizacaoGerencial[];
}

export interface DecisaoGestorAtual {
  possui_decisao: boolean;
  id_decisao: number | null;
  decisao: DecisaoGestor | null;
  quantidade_aprovada: number | null;
  justificativa: string | null;
  usuario: string | null;
  data_hora: string | null;
  status: string | null;
}

export interface ItemAnaliseGestor {
  chave: string;
  codigo: string;
  lote: string;
  descricao: string | null;
  unidade: string | null;
  categoria: string | null;
  qtd_estoque: number;
  localizacoes_snapshot: LocalizacaoGerencial[];
  ultima_rodada_participada: number | null;
  ultima_quantidade_contada: number | null;
  situacao_atual: string;
  requer_decisao_gestor: boolean;
  decisao_gestor: DecisaoGestorAtual;
  situacao_gerencial: string;
  resolvido_gestor: boolean;
  pendente_decisao_gestor: boolean;
  nova_recontagem: boolean;
  quantidade_final_gerencial: number | null;
  historico: HistoricoItemGerencial[];
}

export interface AnaliseGestor {
  tipo_analise: "GERENCIAL_OFICIAL";
  id_inventario: number;
  codigo_inventario: string;
  cliente_id: number;
  status_inventario: string;
  rodada_atual: number;
  ultima_rodada_existente: number;
  regra_conciliacao: "CODIGO_LOTE";
  considera_localizacao: false;
  pode_finalizar_inventario: boolean;
  pode_gerar_nova_recontagem: boolean;
  operacao_concluida: boolean;
  rodadas_nao_finalizadas: RodadaGerencial[];
  resumo: {
    total_itens: number;
    ok: number;
    divergencias: number;
    faltas: number;
    sobras: number;
    sem_contagem: number;
    itens_para_decisao_gestor: number;
    itens_sem_decisao: number;
    aceitaram_estoque: number;
    aceitaram_contagem: number;
    nova_recontagem: number;
    itens_resolvidos_gestor: number;
    itens_resolvidos_total: number;
    rodadas_nao_finalizadas: number;
  };
  rodadas: RodadaGerencial[];
  itens: ItemAnaliseGestor[];
}

export interface DecisaoGestorEntrada {
  codigo: string;
  lote?: string | null;
  decisao: DecisaoGestor;
  quantidade_aprovada?: number | null;
  justificativa?: string | null;
}

export interface DecisaoGestorResposta {
  sucesso: boolean;
  id_decisao: number;
  id_inventario: number;
  codigo_inventario: string;
  codigo: string;
  lote: string;
  decisao: DecisaoGestor;
  quantidade_aprovada: number | null;
  justificativa: string | null;
  usuario: string;
  data_hora: string;
  status: "ATIVA";
  mensagem: string;
}

export interface EncaminhamentoGestorResposta {
  sucesso: boolean;
  id_inventario: number;
  codigo_inventario: string;
  em_analise_gestor: boolean;
  ja_encaminhado: boolean;
  encaminhado_por: string | null;
  mensagem: string;
  // O retorno de "já encaminhado" não contém os campos da primeira operação.
  data_hora_encaminhamento?: string | null;
  tipo_inventario?: string;
  rodada_atual?: number;
  id_rodada?: number;
  total_itens_pendentes?: number;
  limite_itens_gestor?: number;
  itens_pendentes?: Array<{
    codigo: string | null;
    lote: string | null;
    status: string | null;
    qtd_estoque: number | null;
    qtd_contada: number | null;
    diferenca: number | null;
  }>;
}

export interface FinalizacaoInventarioResposta {
  sucesso: boolean;
  id_inventario: number;
  codigo_inventario: string;
  status: string;
  finalizado_por?: string | null;
  data_hora_fim?: string | null;
  mensagem?: string;
}

function validarInventario(id: number): void {
  if (!Number.isSafeInteger(id) || id <= 0) {
    throw new Error("Inventário inválido.");
  }
}

export async function buscarAnaliseGestor(
  idInventario: number,
  signal?: AbortSignal,
): Promise<AnaliseGestor> {
  validarInventario(idInventario);
  return apiRequest<AnaliseGestor>(
    `/inventarios/${idInventario}/analise-gestor`,
    signal ? { signal } : {},
  );
}

export async function encaminharInventarioGestor(
  idInventario: number,
  usuario: string,
): Promise<EncaminhamentoGestorResposta> {
  validarInventario(idInventario);
  const login = usuario.trim();
  if (!login || login.length > 100) {
    throw new Error("Informe um login válido com até 100 caracteres.");
  }
  // Exigido pelo schema atual. O router usa o JWT como autor efetivo.
  return apiRequest<EncaminhamentoGestorResposta>(
    `/inventarios/${idInventario}/encaminhar-gestor`,
    { method: "POST", body: { usuario: login } },
  );
}

export async function registrarDecisaoGestor(
  idInventario: number,
  entrada: DecisaoGestorEntrada,
): Promise<DecisaoGestorResposta> {
  validarInventario(idInventario);
  const codigo = entrada.codigo.trim();
  const lote = entrada.lote?.trim() ?? "";
  const justificativa = entrada.justificativa?.trim() || null;
  const decisao = entrada.decisao;
  if (!codigo || codigo.length > 60) {
    throw new Error("Informe um código com até 60 caracteres.");
  }
  if (lote.length > 60) throw new Error("O lote deve ter até 60 caracteres.");
  if ((justificativa?.length ?? 0) > 500) {
    throw new Error("A justificativa deve ter até 500 caracteres.");
  }
  if (
    !["ACEITAR_ESTOQUE", "ACEITAR_CONTAGEM", "NOVA_RECONTAGEM"].includes(
      decisao,
    )
  ) {
    throw new Error("Decisão gerencial inválida.");
  }
  if (decisao === "NOVA_RECONTAGEM" && !justificativa) {
    throw new Error("Informe a justificativa para solicitar nova recontagem.");
  }
  const quantidade = entrada.quantidade_aprovada;
  if (quantidade != null && (!Number.isFinite(quantidade) || quantidade < 0)) {
    throw new Error("A quantidade aprovada deve ser um número não negativo.");
  }
  if (decisao === "ACEITAR_CONTAGEM" && quantidade == null) {
    throw new Error("Informe a quantidade aprovada.");
  }
  // Nunca inferir quantidade de contagem. Aceitar estoque usa o snapshot no backend.
  // Erros HTTP, inclusive 409, são propagados sem repetição automática do POST.
  return apiRequest<DecisaoGestorResposta>(
    `/inventarios/${idInventario}/decisoes-gestor`,
    {
      method: "POST",
      body: {
        codigo,
        lote,
        decisao,
        justificativa,
        quantidade_aprovada: decisao === "ACEITAR_CONTAGEM" ? quantidade : null,
      },
    },
  );
}

export async function finalizarInventarioGerencial(
  idInventario: number,
): Promise<FinalizacaoInventarioResposta> {
  validarInventario(idInventario);
  return apiRequest<FinalizacaoInventarioResposta>(
    `/inventarios/${idInventario}/finalizar`,
    {
      method: "POST",
      body: {},
    },
  );
}
