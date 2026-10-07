import { apiRequest } from "./apiClient";

export interface Usuario {
  id_usuario: number;
  nome: string;
  login: string;
  email: string | null;
  ativo: boolean;
  data_hora_criacao: string;
  data_hora_atualizacao: string | null;
  ultimo_login: string | null;
}

export interface CriarUsuarioEntrada {
  nome: string;
  login: string;
  email: string | null;
  senha: string;
  ativo: boolean;
}

export interface AtualizarUsuarioEntrada {
  nome: string;
  email: string | null;
  ativo: boolean;
}

export interface AlterarSenhaUsuarioEntrada {
  nova_senha: string;
}

export interface PerfilUsuario {
  id_perfil: number;
  nome: string;
  descricao: string | null;
  ativo: boolean;
}

export interface PerfisUsuarioResposta {
  id_usuario: number;
  perfis: PerfilUsuario[];
}

export interface PerfisDisponiveisResposta {
  total: number;
  perfis: PerfilUsuario[];
}

export interface VincularPerfilEntrada {
  id_perfil: number;
}

export interface PermissaoUsuario {
  id_permissao: number;
  codigo: string;
  descricao: string | null;
}

export interface PermissoesUsuarioResposta {
  id_usuario: number;
  total: number;
  permissoes: PermissaoUsuario[];
}

export async function listarUsuarios(
  ativo?: boolean,
) {
  const query =
    ativo === undefined
      ? ""
      : `?ativo=${ativo}`;

  return apiRequest<Usuario[]>(
    `/usuarios${query}`,
  );
}

export async function consultarUsuario(
  idUsuario: number,
) {
  return apiRequest<Usuario>(
    `/usuarios/${idUsuario}`,
  );
}

export async function criarUsuario(
  dados: CriarUsuarioEntrada,
) {
  return apiRequest<unknown>(
    "/usuarios",
    {
      method: "POST",
      body: dados,
    },
  );
}

export async function atualizarUsuario(
  idUsuario: number,
  dados: AtualizarUsuarioEntrada,
) {
  return apiRequest<unknown>(
    `/usuarios/${idUsuario}`,
    {
      method: "PUT",
      body: dados,
    },
  );
}

export async function alterarSenhaUsuario(
  idUsuario: number,
  dados: AlterarSenhaUsuarioEntrada,
) {
  return apiRequest<unknown>(
    `/usuarios/${idUsuario}/senha`,
    {
      method: "PATCH",
      body: dados,
    },
  );
}

export async function listarPerfisUsuario(
  idUsuario: number,
) {
  return apiRequest<PerfisUsuarioResposta>(
    `/usuarios/${idUsuario}/perfis`,
  );
}

export async function vincularPerfilUsuario(
  idUsuario: number,
  idPerfil: number,
) {
  const dados: VincularPerfilEntrada = {
    id_perfil: idPerfil,
  };

  return apiRequest<unknown>(
    `/usuarios/${idUsuario}/perfis`,
    {
      method: "POST",
      body: dados,
    },
  );
}

export async function removerPerfilUsuario(
  idUsuario: number,
  idPerfil: number,
) {
  return apiRequest<unknown>(
    `/usuarios/${idUsuario}/perfis/${idPerfil}`,
    {
      method: "DELETE",
    },
  );
}

export async function listarPermissoesUsuario(
  idUsuario: number,
) {
  return apiRequest<PermissoesUsuarioResposta>(
    `/usuarios/${idUsuario}/permissoes`,
  );
}

export async function listarPerfisDisponiveis() {
  return apiRequest<PerfisDisponiveisResposta>(
    "/usuarios/perfis/disponiveis",
  );
}

