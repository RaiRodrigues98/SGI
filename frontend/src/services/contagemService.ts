import { z } from "zod";
import { apiRequest } from "@/services/apiClient";
import type {
  AnaliseSessao,
  ContagemItem,
  Localizacao,
  NovaContagem,
  RodadaAtualOperacional,
  SessaoContagem,
} from "@/types/inventory";

const localizacaoSchema = z.string().trim().max(50, "Localização muito longa.");

export interface ConfiguracaoOperacionalInventario {
  id_configuracao: number | null;
  id_inventario: number;
  cliente_id: number;
  tipo_inventario: "OFICIAL" | "ROTATIVO";
  origem: "PADRAO" | "CLIENTE";
  localizacao: {
    obrigatoria: boolean;
    validar_estoque: boolean;
  };
  codigo: {
    obrigatorio: boolean;
    validar_estoque: boolean;
  };
  lote: {
    obrigatorio_quando_existir: boolean;
    validar_codigo: boolean;
    selecao_automatica: false;
  };
  quantidade: {
    obrigatoria: boolean;
    minimo: number;
    maximo: number;
  };
  atualizado_por: string | null;
  data_hora_atualizacao: string | null;
}

export interface ProdutoContagem {
  valido: true;
  id_inventario: number;
  codigo_inventario: string;
  tipo_inventario: "OFICIAL" | "ROTATIVO";
  status_inventario: string;
  codigo: string;
  produto: string | null;
  unidade: string | null;
  categoria: string | null;
  possui_lote: boolean;
  lotes: string[];
  contagem_cega: true;
  proximo_passo: "INFORMAR_LOTE" | "INFORMAR_QUANTIDADE";
}

export interface ContagemAtualLocalizacao {
  localizacao: string;
  id_sessao: number | null;
  status: "PENDENTE" | "EM_CONTAGEM" | "CONCLUIDA";
}

export interface ContagemAtualOperacional {
  id_inventario: number;
  codigo_inventario: string;
  tipo: "OFICIAL" | "ROTATIVO";
  status_inventario: string;
  rodada: RodadaAtualOperacional;
  resumo_operacional: {
    total_localizacoes: number;
    pendentes: number;
    em_contagem: number;
    concluidas: number;
  };
  localizacoes: ContagemAtualLocalizacao[];
}

export interface DetalheLocalizacaoOperacional {
  id_inventario: number;
  codigo_inventario: string;
  tipo_inventario: "OFICIAL" | "ROTATIVO";
  status_inventario: string;
  id_rodada: number;
  numero_rodada: number;
  status_rodada: string;
  localizacao: string;
  status_localizacao: "PENDENTE" | "EM_CONTAGEM" | "CONCLUIDA";
  id_sessao_atual: number | null;
  usuario_sessao_login: string | null;
  usuario_sessao_nome: string | null;
  localizacao_vazia: boolean;
  contagem_cega: true;
  resumo: {
    registros_bipados: number;
    quantidade_total_bipada: number;
    total_sessoes: number;
    sessoes_abertas: number;
    sessoes_encerradas: number;
  };
  itens_bipados: Array<{
    codigo: string;
    produto: string | null;
    lote: string;
    unidade: string | null;
    categoria: string | null;
    quantidade: number;
  }>;
}

export const novaContagemSchema = z.object({
  idSessao: z.number().int().positive("Sessão inválida."),
  localizacao: localizacaoSchema,
  codigo: z.string().trim().max(60, "Código muito longo."),
  lote: z.string().trim().max(60, "Lote muito longo."),
  quantidade: z
    .number({ invalid_type_error: "Quantidade inválida." })
    .refine(Number.isFinite, "Quantidade inválida."),
});

export interface IniciarLocalizacaoInput {
  idInventario: number;
  idRodada: number;
  localizacao: string;
}

interface IniciarLocalizacaoResponse {
  id_sessao: number;
  localizacao?: string | null;
}

interface RegistrarContagemResponse {
  id_contagem: number;
}

interface ContagemSessaoApi {
  id_contagem: number;
  id_sessao: number;
  localizacao: string;
  codigo: string;
  produto?: string | null;
  lote: string | null;
  quantidade: number;
  data_hora: string;
}

function normalizarLocalizacao(valor: string): string {
  return valor.trim().toUpperCase();
}

function validarIdInventario(idInventario: number): number {
  const id = Number(idInventario);
  if (!Number.isSafeInteger(id) || id <= 0) {
    throw new Error("Inventário inválido.");
  }
  return id;
}

export async function consultarConfiguracaoOperacional(
  idInventario: number,
  signal?: AbortSignal,
): Promise<ConfiguracaoOperacionalInventario> {
  const id = validarIdInventario(idInventario);
  return apiRequest<ConfiguracaoOperacionalInventario>(
    `/inventarios/${id}/configuracao-operacional`,
    signal ? { signal } : {},
  );
}

export async function buscarProdutoContagem(
  idInventario: number,
  codigo: string,
  signal?: AbortSignal,
): Promise<ProdutoContagem> {
  const id = validarIdInventario(idInventario);
  const codigoNormalizado = codigo.trim();

  if (!codigoNormalizado || codigoNormalizado.length > 60) {
    throw new Error("Informe um código válido com até 60 caracteres.");
  }

  return apiRequest<ProdutoContagem>(
    `/inventarios/${id}/produtos/${encodeURIComponent(codigoNormalizado)}`,
    signal ? { signal } : {},
  );
}

export async function consultarContagemAtual(
  idInventario: number,
  signal?: AbortSignal,
): Promise<ContagemAtualOperacional> {
  const id = validarIdInventario(idInventario);
  const dados = await apiRequest<ContagemAtualOperacional>(
    `/inventarios/${id}/contagem-atual`,
    signal ? { signal } : {},
  );

  if (!Array.isArray(dados.localizacoes)) {
    throw new Error("A API retornou uma contagem atual inválida.");
  }

  return dados;
}

export async function consultarDetalheLocalizacao(
  idInventario: number,
  localizacao: string,
  signal?: AbortSignal,
): Promise<DetalheLocalizacaoOperacional> {
  const id = validarIdInventario(idInventario);
  const codigo = normalizarLocalizacao(localizacaoSchema.parse(localizacao));

  if (!codigo) {
    throw new Error("Informe a localização.");
  }

  const dados = await apiRequest<DetalheLocalizacaoOperacional>(
    `/inventarios/${id}/localizacoes/${encodeURIComponent(codigo)}`,
    signal ? { signal } : {},
  );

  if (dados.contagem_cega !== true) {
    throw new Error("A API retornou uma localização operacional inválida.");
  }

  return dados;
}

export async function iniciarLocalizacao(
  entrada: IniciarLocalizacaoInput,
): Promise<Localizacao> {
  const idInventario = Number(entrada.idInventario);
  const idRodada = Number(entrada.idRodada);
  const codigo = normalizarLocalizacao(
    localizacaoSchema.parse(entrada.localizacao),
  );

  if (!Number.isInteger(idInventario) || idInventario <= 0) {
    throw new Error("Inventário inválido.");
  }
  if (!Number.isInteger(idRodada) || idRodada <= 0) {
    throw new Error("Rodada inválida.");
  }

  const resposta = await apiRequest<IniciarLocalizacaoResponse>(
    "/localizacoes/iniciar",
    {
      method: "POST",
      body: {
        id_inventario: idInventario,
        id_rodada: idRodada,
        localizacao: codigo,
      },
    },
  );

  const idSessao = Number(resposta.id_sessao);
  if (!Number.isInteger(idSessao) || idSessao <= 0) {
    throw new Error("A API não retornou uma sessão válida.");
  }

  return {
    idSessao,
    codigo: normalizarLocalizacao(resposta.localizacao ?? codigo),
    iniciadaEm: new Date().toISOString(),
  };
}

export async function registrarItem(
  entrada: NovaContagem,
): Promise<ContagemItem> {
  const dados = novaContagemSchema.parse(entrada);
  const localizacao = normalizarLocalizacao(dados.localizacao);

  const resposta = await apiRequest<RegistrarContagemResponse>("/contagens", {
    method: "POST",
    body: {
      id_sessao: dados.idSessao,
      codigo: dados.codigo.trim(),
      lote: dados.lote.trim() || null,
      quantidade: dados.quantidade,
    },
  });

  return {
    id: String(resposta.id_contagem),
    idSessao: dados.idSessao,
    localizacao,
    codigo: dados.codigo.trim(),
    lote: dados.lote.trim(),
    quantidade: dados.quantidade,
    registradoEm: new Date().toISOString(),
  };
}

export async function listarItens(idSessao: number): Promise<ContagemItem[]> {
  if (!Number.isInteger(idSessao) || idSessao <= 0) {
    throw new Error("Sessão inválida.");
  }

  const dados = await apiRequest<{
    id_sessao: number;
    id_inventario: number;
    id_rodada: number;
    localizacao: string;
    status_sessao: string;
    localizacao_vazia: boolean;
    contagem_cega: boolean;
    total_registros: number;
    contagens: ContagemSessaoApi[];
  }>(`/sessoes/${idSessao}/contagens`);

  return dados.contagens.map((item) => {
    const descricao = item.produto?.trim();

    return {
      id: String(item.id_contagem),
      idSessao: Number(item.id_sessao),
      localizacao: item.localizacao,
      codigo: item.codigo,
      ...(descricao ? { descricao } : {}),
      lote: item.lote ?? "",
      quantidade: Number(item.quantidade),
      registradoEm: item.data_hora,
    };
  });
}

export async function encerrarLocalizacao(
  idSessao: number,
  localizacaoVazia = false,
): Promise<void> {
  if (!Number.isInteger(idSessao) || idSessao <= 0) {
    throw new Error("Sessão inválida.");
  }

  await apiRequest<unknown>("/localizacoes/encerrar", {
    method: "POST",
    body: {
      id_sessao: idSessao,
      localizacao_vazia: localizacaoVazia,
    },
  });
}

export async function buscarAnaliseSessao(
  idSessao: number,
): Promise<AnaliseSessao> {
  if (!Number.isInteger(idSessao) || idSessao <= 0) {
    throw new Error("Sessão inválida.");
  }
  return apiRequest<AnaliseSessao>(`/sessoes/${idSessao}/analise`);
}

export async function listarSessoes(): Promise<SessaoContagem[]> {
  return apiRequest<SessaoContagem[]>("/sessoes");
}

// Contrato informado: PATCH /contagens/{id_contagem}/cancelar, sem body.
export async function cancelarContagem(idContagem: string): Promise<void> {
  if (!/^[1-9]\d*$/.test(idContagem)) {
    throw new Error("Registro de contagem inválido.");
  }
  await apiRequest<unknown>(`/contagens/${idContagem}/cancelar`, {
    method: "PATCH",
  });
}
