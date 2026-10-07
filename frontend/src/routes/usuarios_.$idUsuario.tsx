import {
  Link,
  createFileRoute,
} from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  KeyRound,
  ShieldCheck,
  UserRound,
} from "lucide-react";

import {
  obterUsuarioSalvo,
} from "@/services/authService";

import {
  alterarSenhaUsuario,
  atualizarUsuario,
  consultarUsuario,
  listarPerfisUsuario,
  listarPerfisDisponiveis,
  vincularPerfilUsuario,
  removerPerfilUsuario,
  listarPermissoesUsuario,
  type PerfilUsuario,
  type PermissaoUsuario,
  type Usuario,
} from "@/services/usuariosService";

export const Route = createFileRoute(
  "/usuarios_/$idUsuario",
)({
  head: () => ({
    meta: [
      {
        title: "Gerenciar Usu\u00e1rio \u2014 SGI",
      },
    ],
  }),
  component: GerenciarUsuarioPage,
});

function GerenciarUsuarioPage() {
  const { idUsuario } = Route.useParams();

  const id = Number(idUsuario);

  const [
    idUsuarioAtual,
    setIdUsuarioAtual,
  ] = useState<number | null>(null);

  useEffect(() => {
    const usuarioSalvo =
      obterUsuarioSalvo();

    setIdUsuarioAtual(
      usuarioSalvo?.id_usuario ?? null,
    );
  }, []);

  const ehProprioUsuario =
    idUsuarioAtual !== null &&
    idUsuarioAtual === id;

  const [usuario, setUsuario] =
    useState<Usuario | null>(null);

  const [perfis, setPerfis] =
    useState<PerfilUsuario[]>([]);

  const [
    perfisDisponiveis,
    setPerfisDisponiveis,
  ] = useState<PerfilUsuario[]>([]);

  const [
    idPerfilSelecionado,
    setIdPerfilSelecionado,
  ] = useState<number | "">("");

  const [
    alterandoPerfil,
    setAlterandoPerfil,
  ] = useState(false);

  const [permissoes, setPermissoes] =
    useState<PermissaoUsuario[]>([]);

  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [ativo, setAtivo] = useState(true);

  const [novaSenha, setNovaSenha] =
    useState("");

  const [confirmarSenha, setConfirmarSenha] =
    useState("");

  const [editando, setEditando] =
    useState(false);

  const [alterandoSenha, setAlterandoSenha] =
    useState(false);

  const [carregando, setCarregando] =
    useState(true);

  const [salvando, setSalvando] =
    useState(false);

  const [erro, setErro] =
    useState<string | null>(null);

  useEffect(() => {
    void carregar();
  }, [id]);

  async function carregar() {
    if (!Number.isInteger(id) || id <= 0) {
      setErro("Usuário inválido.");
      setCarregando(false);
      return;
    }

    try {
      setCarregando(true);
      setErro(null);

      const [
        dadosUsuario,
        dadosPerfis,
        dadosPermissoes,
        dadosPerfisDisponiveis,
      ] = await Promise.all([
        consultarUsuario(id),
        listarPerfisUsuario(id),
        listarPermissoesUsuario(id),
        listarPerfisDisponiveis(),
      ]);

      setUsuario(dadosUsuario);
      setPerfis(dadosPerfis.perfis);
      setPerfisDisponiveis(
        dadosPerfisDisponiveis.perfis,
      );
      setPermissoes(
        dadosPermissoes.permissoes,
      );

      setNome(dadosUsuario.nome);
      setEmail(dadosUsuario.email ?? "");
      setAtivo(dadosUsuario.ativo);
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Erro ao carregar o usuário.",
      );
    } finally {
      setCarregando(false);
    }
  }

  async function vincularPerfil() {
    if (!idPerfilSelecionado) {
      const mensagem =
        "Selecione um perfil para vincular.";

      setErro(mensagem);
      toast.error(mensagem);
      return;
    }

    try {
      setAlterandoPerfil(true);
      setErro(null);

      await vincularPerfilUsuario(
        id,
        idPerfilSelecionado,
      );

      setIdPerfilSelecionado("");

      await carregar();

      toast.success(
        "Perfil vinculado com sucesso.",
      );
    } catch (error) {
      const mensagem =
        error instanceof Error
          ? error.message
          : "Erro ao vincular perfil.";

      setErro(mensagem);
      toast.error(mensagem);
    } finally {
      setAlterandoPerfil(false);
    }
  }

  async function removerPerfil(
    perfil: PerfilUsuario,
  ) {
    const confirmou = window.confirm(
      `Remover o perfil ${perfil.nome} deste usuário?`,
    );

    if (!confirmou) {
      return;
    }

    try {
      setAlterandoPerfil(true);
      setErro(null);

      await removerPerfilUsuario(
        id,
        perfil.id_perfil,
      );

      await carregar();

      toast.success(
        "Perfil removido com sucesso.",
      );
    } catch (error) {
      const mensagem =
        error instanceof Error
          ? error.message
          : "Erro ao remover perfil.";

      setErro(mensagem);
      toast.error(mensagem);
    } finally {
      setAlterandoPerfil(false);
    }
  }

  async function salvarDados() {
    const nomeNormalizado = nome.trim();
    const emailNormalizado = email.trim();

    if (nomeNormalizado.length < 2) {
      const mensagem =
        "Informe um nome com pelo menos 2 caracteres.";

      setErro(mensagem);
      toast.error(mensagem);
      return;
    }

    try {
      setSalvando(true);
      setErro(null);

      await atualizarUsuario(id, {
        nome: nomeNormalizado,
        email: emailNormalizado || null,
        ativo,
      });

      await carregar();

      setEditando(false);
      toast.success(
        "Dados do usuário atualizados com sucesso.",
      );
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Erro ao atualizar o usuário.",
      );
    } finally {
      setSalvando(false);
    }
  }

  async function salvarSenha() {
    if (novaSenha.length < 8) {
      const mensagem =
        "A nova senha deve ter pelo menos 8 caracteres.";

      setErro(mensagem);
      toast.error(mensagem);
      return;
    }

    if (novaSenha !== confirmarSenha) {
      setErro(
        "A confirmação da senha não confere.",
      );
      return;
    }

    try {
      setSalvando(true);
      setErro(null);

      await alterarSenhaUsuario(id, {
        nova_senha: novaSenha,
      });

      setNovaSenha("");
      setConfirmarSenha("");
      setAlterandoSenha(false);

      toast.success(
        "Senha alterada com sucesso.",
      );
    } catch (error) {
      const mensagem =
        error instanceof Error
          ? error.message
          : "Erro ao alterar a senha.";

      setErro(mensagem);
      toast.error(mensagem);
    } finally {
      setSalvando(false);
    }
  }

  if (carregando) {
    return (
      <main className="p-6">
        <div className="text-sm text-muted-foreground">
          Carregando usuário...
        </div>
      </main>
    );
  }

  if (!usuario) {
    return (
      <main className="space-y-4 p-6">
        <Link
          to="/usuarios"
          className="text-sm font-medium text-primary hover:underline"
        >
          Voltar para usuários
        </Link>

        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          {erro || "Usuário não encontrado."}
        </div>
      </main>
    );
  }

  return (
    <main className="space-y-6 p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link
            to="/usuarios"
            className="text-sm font-medium text-primary hover:underline"
          >
            ← Voltar para usuários
          </Link>

          <h1 className="mt-3 text-2xl font-semibold">
            {usuario.nome}
          </h1>

          <p className="mt-1 text-sm text-muted-foreground">
            Gerencie os dados, acesso, perfis e
            permissões deste usuário.
          </p>
        </div>

        <StatusUsuario ativo={usuario.ativo} />
      </div>

      {erro && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {erro}
        </div>
      )}

      <section className="rounded-lg border bg-card shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b p-5">
          <div className="flex items-center gap-2">
            <UserRound className="size-5" />

            <div>
              <h2 className="font-semibold">
                Dados do usuário
              </h2>

              <p className="text-sm text-muted-foreground">
                Informações de identificação e acesso.
              </p>
            </div>
          </div>

          {!editando && (
            <button
              type="button"
              onClick={() => {
                setEditando(true);
                setErro(null);
                        }}
              className="rounded-md border px-3 py-2 text-sm font-medium hover:bg-muted"
            >
              Editar dados
            </button>
          )}
        </div>

        <div className="p-5">
          {editando ? (
            <div className="space-y-5">
              <div className="grid gap-4 md:grid-cols-2">
                <Campo titulo="Nome">
                  <input
                    value={nome}
                    onChange={(event) =>
                      setNome(event.target.value)
                    }
                    maxLength={150}
                    className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                  />
                </Campo>

                <Campo titulo="Login">
                  <input
                    value={usuario.login}
                    disabled
                    className="h-10 w-full rounded-md border bg-muted px-3 text-sm text-muted-foreground"
                  />
                </Campo>

                <Campo titulo="E-mail">
                  <input
                    type="email"
                    value={email}
                    onChange={(event) =>
                      setEmail(event.target.value)
                    }
                    className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                  />
                </Campo>

                <label className="flex items-center gap-3 self-end rounded-md border p-3 text-sm">
                  <input
                    type="checkbox"
                    checked={ativo}
                    disabled={ehProprioUsuario}
                    onChange={(event) =>
                      setAtivo(
                        event.target.checked,
                      )
                    }
                    className="size-4"
                  />

                  Usuário ativo
                </label>
              </div>

              <div className="flex justify-end gap-2 border-t pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setNome(usuario.nome);
                    setEmail(
                      usuario.email ?? "",
                    );
                    setAtivo(usuario.ativo);
                    setEditando(false);
                  }}
                  disabled={salvando}
                  className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted disabled:opacity-50"
                >
                  Cancelar
                </button>

                <button
                  type="button"
                  onClick={() =>
                    void salvarDados()
                  }
                  disabled={salvando}
                  className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
                >
                  {salvando
                    ? "Salvando..."
                    : "Salvar alterações"}
                </button>
              </div>
            </div>
          ) : (
            <dl className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              <Linha
                titulo="Login"
                valor={usuario.login}
              />

              <Linha
                titulo="E-mail"
                valor={usuario.email || "-"}
              />

              <Linha
                titulo="Status"
                valor={
                  usuario.ativo
                    ? "Ativo"
                    : "Inativo"
                }
              />

              <Linha
                titulo="Criado em"
                valor={formatarDataHora(
                  usuario.data_hora_criacao,
                )}
              />

              <Linha
                titulo="Atualizado em"
                valor={formatarDataHora(
                  usuario.data_hora_atualizacao,
                )}
              />

              <Linha
                titulo="Último acesso"
                valor={formatarDataHora(
                  usuario.ultimo_login,
                )}
              />
            </dl>
          )}
        </div>
      </section>

      <section className="rounded-lg border bg-card shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b p-5">
          <div className="flex items-center gap-2">
            <KeyRound className="size-5" />

            <div>
              <h2 className="font-semibold">
                Senha
              </h2>

              <p className="text-sm text-muted-foreground">
                Redefina a senha de acesso do usuário.
              </p>
            </div>
          </div>

          {!alterandoSenha && (
            <button
              type="button"
              onClick={() => {
                setAlterandoSenha(true);
                setErro(null);
                        }}
              className="rounded-md border px-3 py-2 text-sm font-medium hover:bg-muted"
            >
              Alterar senha
            </button>
          )}
        </div>

        {alterandoSenha && (
          <div className="space-y-5 p-5">
            <div className="grid gap-4 md:grid-cols-2">
              <Campo titulo="Nova senha">
                <input
                  type="password"
                  value={novaSenha}
                  onChange={(event) =>
                    setNovaSenha(
                      event.target.value,
                    )
                  }
                  minLength={8}
                  maxLength={128}
                  autoComplete="new-password"
                  placeholder="Mínimo de 8 caracteres"
                  className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                />
              </Campo>

              <Campo titulo="Confirmar nova senha">
                <input
                  type="password"
                  value={confirmarSenha}
                  onChange={(event) =>
                    setConfirmarSenha(
                      event.target.value,
                    )
                  }
                  minLength={8}
                  maxLength={128}
                  autoComplete="new-password"
                  className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                />
              </Campo>
            </div>

            <div className="flex justify-end gap-2 border-t pt-4">
              <button
                type="button"
                onClick={() => {
                  setNovaSenha("");
                  setConfirmarSenha("");
                  setAlterandoSenha(false);
                }}
                disabled={salvando}
                className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted disabled:opacity-50"
              >
                Cancelar
              </button>

              <button
                type="button"
                onClick={() =>
                  void salvarSenha()
                }
                disabled={salvando}
                className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
              >
                {salvando
                  ? "Salvando..."
                  : "Alterar senha"}
              </button>
            </div>
          </div>
        )}
      </section>

      <section className="rounded-lg border bg-card shadow-xs">
        <div className="border-b p-5">
          <div className="flex items-center gap-2">
            <ShieldCheck className="size-5" />

            <div>
              <h2 className="font-semibold">
                Perfis
              </h2>

              <p className="text-sm text-muted-foreground">
                {ehProprioUsuario
                  ? "Seus perfis são somente para consulta."
                  : "Gerencie os perfis vinculados ao usuário."}
              </p>
            </div>
          </div>
        </div>

        <div className="space-y-5 p-5">
          {!ehProprioUsuario && (
          <div className="flex flex-wrap items-end gap-3">
            <label className="min-w-[260px] flex-1 space-y-1.5">
              <span className="text-sm font-medium">
                Vincular perfil
              </span>

              <select
                value={idPerfilSelecionado}
                onChange={(event) =>
                  setIdPerfilSelecionado(
                    event.target.value
                      ? Number(event.target.value)
                      : "",
                  )
                }
                disabled={alterandoPerfil}
                className="h-10 w-full rounded-md border bg-background px-3 text-sm"
              >
                <option value="">
                  Selecione um perfil
                </option>

                {perfisDisponiveis
                  .filter(
                    (perfilDisponivel) =>
                      !perfis.some(
                        (perfilAtual) =>
                          perfilAtual.id_perfil ===
                          perfilDisponivel.id_perfil,
                      ),
                  )
                  .map((perfil) => (
                    <option
                      key={perfil.id_perfil}
                      value={perfil.id_perfil}
                    >
                      {perfil.nome}
                    </option>
                  ))}
              </select>
            </label>

            <button
              type="button"
              onClick={() =>
                void vincularPerfil()
              }
              disabled={
                alterandoPerfil ||
                !idPerfilSelecionado
              }
              className="h-10 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground disabled:opacity-50"
            >
              {alterandoPerfil
                ? "Processando..."
                : "Vincular"}
            </button>
          </div>
          )}

          <div className="space-y-2">
            {perfis.map((perfil) => (
              <div
                key={perfil.id_perfil}
                className="flex flex-wrap items-center justify-between gap-3 rounded-md border p-4"
              >
                <div>
                  <div className="font-medium">
                    {perfil.nome}
                  </div>

                  <div className="mt-1 text-sm text-muted-foreground">
                    {perfil.descricao || "-"}
                  </div>
                </div>

                {!ehProprioUsuario && (
                  <button
                    type="button"
                    onClick={() =>
                      void removerPerfil(perfil)
                    }
                    disabled={alterandoPerfil}
                    className="rounded-md border px-3 py-2 text-sm font-medium hover:bg-muted disabled:opacity-50"
                  >
                    Remover
                  </button>
                )}
              </div>
            ))}

            {perfis.length === 0 && (
              <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                Nenhum perfil vinculado.
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="rounded-lg border bg-card shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b p-5">
          <div>
            <h2 className="font-semibold">
              Permissões efetivas
            </h2>

            <p className="text-sm text-muted-foreground">
              Permissões resultantes dos perfis vinculados.
            </p>
          </div>

          <span className="text-sm text-muted-foreground">
            {permissoes.length} permissões
          </span>
        </div>

        <div className="grid gap-3 p-5 md:grid-cols-2 xl:grid-cols-3">
          {permissoes.map(
            (permissao) => (
              <div
                key={permissao.id_permissao}
                className="rounded-md border p-3"
              >
                <div className="text-sm font-medium">
                  {permissao.codigo}
                </div>

                <div className="mt-1 text-xs text-muted-foreground">
                  {permissao.descricao || "-"}
                </div>
              </div>
            ),
          )}

          {permissoes.length === 0 && (
            <div className="text-sm text-muted-foreground">
              Nenhuma permissão efetiva encontrada.
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

function Campo({
  titulo,
  children,
}: {
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <label className="space-y-1.5">
      <span className="text-sm font-medium">
        {titulo}
      </span>

      {children}
    </label>
  );
}

function Linha({
  titulo,
  valor,
}: {
  titulo: string;
  valor: string;
}) {
  return (
    <div className="rounded-md border p-3">
      <dt className="text-xs text-muted-foreground">
        {titulo}
      </dt>

      <dd className="mt-1 text-sm font-medium">
        {valor}
      </dd>
    </div>
  );
}

function StatusUsuario({
  ativo,
}: {
  ativo: boolean;
}) {
  return (
    <span
      className={
        ativo
          ? "inline-flex rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700"
          : "inline-flex rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground"
      }
    >
      {ativo ? "Ativo" : "Inativo"}
    </span>
  );
}

function formatarDataHora(
  valor: string | null,
) {
  if (!valor) {
    return "-";
  }

  const data = new Date(valor);

  if (Number.isNaN(data.getTime())) {
    return valor;
  }

  return new Intl.DateTimeFormat(
    "pt-BR",
    {
      dateStyle: "short",
      timeStyle: "short",
    },
  ).format(data);
}
