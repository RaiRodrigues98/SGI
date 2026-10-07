import { apiRequest } from "@/services/apiClient";

export type PrioridadeNotificacao =
  | "INFORMATIVA"
  | "MEDIA"
  | "ALTA"
  | "CRITICA";

export interface Notificacao {
  id_notificacao: number;
  tipo: string;
  titulo: string;
  mensagem: string;
  prioridade: PrioridadeNotificacao;
  entidade_tipo: string | null;
  entidade_id: number | null;
  id_inventario: number | null;
  url: string | null;
  lida: boolean;
  data_leitura: string | null;
  data_criacao: string;
  id_usuario_ator: number | null;
  nome_usuario_ator: string | null;
}

interface ListaNotificacoesResposta {
  total: number;
  notificacoes: Notificacao[];
}

interface QuantidadeNaoLidasResposta {
  quantidade: number;
}

export async function listarNotificacoes(
  signal?: AbortSignal,
): Promise<ListaNotificacoesResposta> {
  return apiRequest<ListaNotificacoesResposta>(
    "/notificacoes?limite=30",
    signal ? { signal } : {},
  );
}

export async function consultarQuantidadeNaoLidas(
  signal?: AbortSignal,
): Promise<number> {
  const resposta =
    await apiRequest<QuantidadeNaoLidasResposta>(
      "/notificacoes/nao-lidas/quantidade",
      signal ? { signal } : {},
    );

  return resposta.quantidade;
}

export async function marcarNotificacaoComoLida(
  idNotificacao: number,
): Promise<void> {
  await apiRequest(
    `/notificacoes/${idNotificacao}/ler`,
    { method: "PATCH" },
  );
}

export async function marcarTodasComoLidas(): Promise<void> {
  await apiRequest(
    "/notificacoes/ler-todas",
    { method: "PATCH" },
  );
}
