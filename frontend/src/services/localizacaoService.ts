import { apiRequest } from "@/services/apiClient";

export type StatusLocalizacaoOperacional =
  | "PENDENTE"
  | "EM_CONTAGEM"
  | "CONCLUIDA";

export interface LocalizacaoOperacional {
  localizacao: string;
  id_sessao: number | null;
  status: StatusLocalizacaoOperacional;
}

export interface LocalizacoesInventarioResponse {
  id_inventario: number;
  tipo: string;
  rodada_atual: number;
  id_rodada: number | null;
  localizacoes: LocalizacaoOperacional[];
}

export async function consultarLocalizacoesInventario(
  idInventario: number,
): Promise<LocalizacoesInventarioResponse> {
  if (!Number.isInteger(idInventario) || idInventario <= 0) {
    throw new Error("Inventário inválido.");
  }

  const dados = await apiRequest<LocalizacoesInventarioResponse>(
    `/inventarios/${idInventario}/localizacoes`,
  );

  if (!Array.isArray(dados.localizacoes)) {
    throw new Error("A API retornou um escopo de localizações inválido.");
  }

  return dados;
}
