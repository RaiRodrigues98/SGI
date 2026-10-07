import { apiRequest } from "@/services/apiClient";
import type {
  LoginEntrada,
  LoginResposta,
  UsuarioAutenticado,
} from "@/types/auth";

export const AUTH_TOKEN_KEY = "sgi.access_token";
export const AUTH_USER_KEY = "sgi.usuario";

export interface CadastroPublicoEntrada {
  nome: string;
  login: string;
  email?: string | null;
  senha: string;
}

export interface CadastroPublicoResposta {
  sucesso: boolean;
  mensagem: string;
  usuario: {
    id_usuario: number;
    nome: string;
    login: string;
    email: string | null;
    ativo: boolean;
  };
  perfil: {
    id_perfil: number;
    nome: string;
  };
}

interface MeuUsuarioResposta {
  autenticado: boolean;
  usuario: UsuarioAutenticado;
}

function temWindow(): boolean {
  return typeof window !== "undefined";
}

export function obterToken(): string | null {
  if (!temWindow()) return null;
  return window.localStorage.getItem(AUTH_TOKEN_KEY);
}

export function estaAutenticado(): boolean {
  return Boolean(obterToken());
}

export function obterUsuarioSalvo(): UsuarioAutenticado | null {
  if (!temWindow()) return null;
  const valor = window.localStorage.getItem(AUTH_USER_KEY);
  if (!valor) return null;

  try {
    return JSON.parse(valor) as UsuarioAutenticado;
  } catch {
    window.localStorage.removeItem(AUTH_USER_KEY);
    return null;
  }
}

function salvarUsuario(usuario: UsuarioAutenticado): void {
  if (!temWindow()) return;
  window.localStorage.setItem(AUTH_USER_KEY, JSON.stringify(usuario));
}

export async function consultarMeuUsuario(
  signal?: AbortSignal,
): Promise<UsuarioAutenticado> {
  const resposta = await apiRequest<MeuUsuarioResposta>(
    "/auth/me",
    signal ? { signal } : {},
  );

  const usuario = resposta.usuario;

  if (
    resposta.autenticado !== true ||
    !usuario ||
    !Number.isSafeInteger(Number(usuario.id_usuario)) ||
    !usuario.login?.trim() ||
    !Array.isArray(usuario.perfis) ||
    !Array.isArray(usuario.permissoes)
  ) {
    throw new Error("A API retornou um usuário autenticado inválido.");
  }

  salvarUsuario(usuario);
  return usuario;
}

export async function login(entrada: LoginEntrada): Promise<LoginResposta> {
  const loginNormalizado = entrada.login.trim();

  if (!loginNormalizado) throw new Error("Informe o login.");
  if (!entrada.senha) throw new Error("Informe a senha.");

  const resposta = await apiRequest<LoginResposta>("/auth/login", {
    method: "POST",
    authenticated: false,
    body: {
      login: loginNormalizado,
      senha: entrada.senha,
    },
  });

  if (!resposta.access_token) {
    throw new Error("A API não retornou o token de acesso.");
  }

  if (temWindow()) {
    window.localStorage.setItem(AUTH_TOKEN_KEY, resposta.access_token);
    salvarUsuario(resposta.usuario);
  }

  return resposta;
}

export async function cadastrarUsuario(
  entrada: CadastroPublicoEntrada,
): Promise<CadastroPublicoResposta> {
  const nome = entrada.nome.trim();
  const loginNormalizado = entrada.login.trim();
  const email = entrada.email?.trim() || null;

  if (nome.length < 2) {
    throw new Error("Informe um nome válido.");
  }

  if (loginNormalizado.length < 3) {
    throw new Error("O login deve ter pelo menos 3 caracteres.");
  }

  if (entrada.senha.length < 8) {
    throw new Error("A senha deve ter pelo menos 8 caracteres.");
  }

  return apiRequest<CadastroPublicoResposta>("/auth/cadastro", {
    method: "POST",
    authenticated: false,
    body: {
      nome,
      login: loginNormalizado,
      email,
      senha: entrada.senha,
    },
  });
}

export function logout(): void {
  if (!temWindow()) return;
  window.localStorage.removeItem(AUTH_TOKEN_KEY);
  window.localStorage.removeItem(AUTH_USER_KEY);
}
