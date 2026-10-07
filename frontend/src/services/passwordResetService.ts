import { apiRequest } from "@/services/apiClient";

export interface EsqueciSenhaResposta {
  sucesso: boolean;
  mensagem: string;
}

export interface RedefinirSenhaResposta {
  sucesso: boolean;
  mensagem: string;
}

/**
 * Solicita link de recuperacao de senha.
 * Rota publica: authenticated=false.
 */
export function solicitarRecuperacaoSenha(
  email: string,
): Promise<EsqueciSenhaResposta> {
  return apiRequest<EsqueciSenhaResposta>("/auth/esqueci-senha", {
    method: "POST",
    body: { email },
    authenticated: false,
  });
}

/**
 * Redefine a senha usando o token recebido por e-mail.
 */
export function redefinirSenha(
  token: string,
  novaSenha: string,
): Promise<RedefinirSenhaResposta> {
  return apiRequest<RedefinirSenhaResposta>("/auth/reset-senha", {
    method: "POST",
    body: { token, nova_senha: novaSenha },
    authenticated: false,
  });
}
