export interface PermissaoAutenticada {
  id_permissao: number;
  codigo: string;
  descricao: string | null;
}

export interface LoginEntrada {
  login: string;
  senha: string;
}

export interface UsuarioAutenticado {
  id_usuario: number;
  nome: string;
  login: string;
  email: string | null;
  perfis: string[];
  permissoes: Array<string | PermissaoAutenticada>;
}

export interface LoginResposta {
  sucesso: boolean;
  mensagem: string;
  access_token: string;
  token_type: string;
  expires_in: number;
  expira_em: string;
  usuario: UsuarioAutenticado;
}
