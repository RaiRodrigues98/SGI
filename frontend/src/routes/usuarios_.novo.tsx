import {
  createFileRoute,
  useNavigate,
} from "@tanstack/react-router";
import { useState } from "react";

import {
  criarUsuario,
} from "@/services/usuariosService";

export const Route = createFileRoute("/usuarios_/novo")({
  head: () => ({
    meta: [
      {
        title: "Novo Usu\u00e1rio \u2014 SGI",
      },
    ],
  }),
  component: NovoUsuarioPage,
});

function NovoUsuarioPage() {
  const navigate = useNavigate();

  const [nome, setNome] = useState("");
  const [login, setLogin] = useState("");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [ativo, setAtivo] = useState(true);

  const [salvando, setSalvando] =
    useState(false);

  const [erro, setErro] =
    useState<string | null>(null);

  async function salvar() {
    const nomeNormalizado = nome.trim();
    const loginNormalizado = login.trim();
    const emailNormalizado = email.trim();

    if (nomeNormalizado.length < 2) {
      setErro(
        "Informe um nome com pelo menos 2 caracteres.",
      );
      return;
    }

    if (loginNormalizado.length < 3) {
      setErro(
        "Informe um login com pelo menos 3 caracteres.",
      );
      return;
    }

    if (senha.length < 8) {
      setErro(
        "A senha deve ter pelo menos 8 caracteres.",
      );
      return;
    }

    try {
      setSalvando(true);
      setErro(null);

      await criarUsuario({
        nome: nomeNormalizado,
        login: loginNormalizado,
        email: emailNormalizado || null,
        senha,
        ativo,
      });

      await navigate({
        to: "/usuarios",
      });
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Erro ao criar usuário.",
      );
    } finally {
      setSalvando(false);
    }
  }

  function cancelar() {
    void navigate({
      to: "/usuarios",
    });
  }

  return (
    <main className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">
          Novo usuário
        </h1>

        <p className="mt-1 text-sm text-muted-foreground">
          Cadastre um novo usuário para acesso ao SGI.
        </p>
      </div>

      {erro && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {erro}
        </div>
      )}

      <section className="max-w-4xl space-y-6 rounded-lg border bg-card p-6 shadow-xs">
        <div className="grid gap-5 md:grid-cols-2">
          <Campo
            titulo="Nome"
            obrigatorio
          >
            <input
              value={nome}
              onChange={(event) =>
                setNome(event.target.value)
              }
              maxLength={150}
              autoFocus
              className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          </Campo>

          <Campo
            titulo="Login"
            obrigatorio
          >
            <input
              value={login}
              onChange={(event) =>
                setLogin(event.target.value)
              }
              maxLength={100}
              autoComplete="off"
              className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          </Campo>

          <Campo titulo="E-mail">
            <input
              type="email"
              value={email}
              onChange={(event) =>
                setEmail(event.target.value)
              }
              className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          </Campo>

          <Campo
            titulo="Senha"
            obrigatorio
          >
            <input
              type="password"
              value={senha}
              onChange={(event) =>
                setSenha(event.target.value)
              }
              minLength={8}
              maxLength={128}
              autoComplete="new-password"
              placeholder="Mínimo de 8 caracteres"
              className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          </Campo>
        </div>

        <label className="flex items-center gap-3 rounded-md border p-3 text-sm">
          <input
            type="checkbox"
            checked={ativo}
            onChange={(event) =>
              setAtivo(event.target.checked)
            }
            className="size-4"
          />

          <div>
            <div className="font-medium">
              Usuário ativo
            </div>

            <div className="text-xs text-muted-foreground">
              Permite que o usuário utilize sua conta no SGI.
            </div>
          </div>
        </label>

        <div className="flex justify-end gap-2 border-t pt-5">
          <button
            type="button"
            onClick={cancelar}
            disabled={salvando}
            className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted disabled:opacity-50"
          >
            Cancelar
          </button>

          <button
            type="button"
            onClick={() => void salvar()}
            disabled={salvando}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
          >
            {salvando
              ? "Salvando..."
              : "Criar usuário"}
          </button>
        </div>
      </section>
    </main>
  );
}

function Campo({
  titulo,
  obrigatorio = false,
  children,
}: {
  titulo: string;
  obrigatorio?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="space-y-1.5">
      <span className="text-sm font-medium">
        {titulo}
        {obrigatorio && (
          <span className="ml-1 text-destructive">
            *
          </span>
        )}
      </span>

      {children}
    </label>
  );
}
