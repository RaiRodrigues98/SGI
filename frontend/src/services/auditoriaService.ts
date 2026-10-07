import { apiRequest } from "./apiClient";

export interface AuditoriaInventario {
  id_inventario: number;
  codigo_inventario: string;
  tipo: string;
  cliente: string;
  cliente_id: number | null;
  armazem: string | null;
  status: string;
  data_hora_inicio: string | null;
  data_hora_fim: string | null;
  criado_por: string | null;
  finalizado_por: string | null;
}

export interface AuditoriaResumo {
  total_eventos: number;
  primeiro_evento: string | null;
  ultimo_evento: string | null;
}

export interface AuditoriaPaginacao {
  page: number;
  page_size: number;
  total_registros: number;
  total_paginas: number;
  registros_pagina: number;
  tem_proxima: boolean;
  tem_anterior: boolean;
}

export interface AuditoriaEvento {
  data_hora: string;
  tipo_evento: string;
  categoria: string;
  titulo: string | null;
  descricao: string | null;
  usuario: string | null;
  entidade: string | null;
  entidade_id: string | null;
  localizacao: string | null;
  codigo: string | null;
  lote: string | null;
  status: string | null;
  motivo: string | null;
  justificativa: string | null;
}

export interface AuditoriaResponse {
  tipo_consulta: "AUDITORIA_INVENTARIO";
  inventario: AuditoriaInventario | null;
  resumo: AuditoriaResumo;
  paginacao: AuditoriaPaginacao;
  eventos: AuditoriaEvento[];
}

export async function buscarAuditoriaInventario(
  idInventario: number,
  page = 1,
  pageSize = 20,
  signal?: AbortSignal,
): Promise<AuditoriaResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });

  return apiRequest<AuditoriaResponse>(
    `/auditoria/inventarios/${idInventario}?${params.toString()}`,
    signal ? { signal } : {},
  );
}
