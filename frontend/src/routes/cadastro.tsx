import {
  createFileRoute,
  useNavigate,
} from "@tanstack/react-router";

import {
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  UserRound,
} from "lucide-react";

import {
  useState,
} from "react";

import type {
  FormEvent,
} from "react";

import { toast } from "sonner";

import { Button } from "@/components/ui/button";

import {
  cadastrarUsuario,
} from "@/services/authService";

export const Route = createFileRoute(
  "/cadastro",
)({
  head: () => ({
    meta: [
      {
        title: "Cadastrar usu\u00e1rio \u2014 SGI",
      },
    ],
  }),
  component: CadastroPage,
});

function CadastroPage() {
  const navigate = useNavigate();

  const [nome, setNome] =
    useState("");

  const [login, setLogin] =
    useState("");

  const [email, setEmail] =
    useState("");

  const [senha, setSenha] =
    useState("");

  const [
    confirmarSenha,
    setConfirmarSenha,
  ] = useState("");

  const [
    mostrarSenha,
    setMostrarSenha,
  ] = useState(false);

  const [
    cadastrando,
    setCadastrando,
  ] = useState(false);

  async function cadastrar(
    evento: FormEvent<HTMLFormElement>,
  ) {
    evento.preventDefault();

    if (nome.trim().length < 2) {
      toast.error(
        "Informe um nome válido.",
      );
      return;
    }

    if (login.trim().length < 3) {
      toast.error(
        "O login deve ter pelo menos 3 caracteres.",
      );
      return;
    }

    if (senha.length < 8) {
      toast.error(
        "A senha deve ter pelo menos 8 caracteres.",
      );
      return;
    }

    if (senha !== confirmarSenha) {
      toast.error(
        "As senhas informadas não coincidem.",
      );
      return;
    }

    try {
      setCadastrando(true);

      const resposta =
        await cadastrarUsuario({
          nome,
          login,
          email: email.trim() || null,
          senha,
        });

      toast.success(
        resposta.mensagem ||
          "Cadastro realizado com sucesso.",
        {
          description:
            "Seu acesso foi criado com o perfil OPERADOR.",
        },
      );

      await navigate({
        to: "/login",
      });
    } catch (erro) {
      toast.error(
        erro instanceof Error
          ? erro.message
          : "Não foi possível realizar o cadastro.",
      );
    } finally {
      setCadastrando(false);
    }
  }

  return (
    <main className="flex min-h-screen bg-background">
      <section className="hidden min-h-screen flex-1 flex-col justify-between bg-brand p-12 text-brand-foreground lg:flex">
        <div>
          <img
            src="/logo-alzarsi.png"
            alt="Alzarsi Logística"
            className="h-auto w-[190px] object-contain object-left"
          />
        </div>

        <div className="max-w-xl">
          <div className="mb-5 h-1 w-16 rounded-full bg-gold" />

          <h1 className="text-4xl font-bold leading-tight">
            Crie seu acesso
            <br />
            ao SGI
          </h1>

          <p className="mt-5 max-w-lg text-base leading-relaxed text-brand-foreground/75">
            O novo usuário será cadastrado
            automaticamente com o perfil OPERADOR,
            mantendo o controle de acesso do sistema.
          </p>
        </div>

        <p className="text-xs text-brand-foreground/55">
          SGI Alzarsilog
        </p>
      </section>

      <section className="flex min-h-screen w-full items-center justify-center px-5 py-10 lg:w-[620px]">
        <div className="w-full max-w-[440px]">
          <div className="mb-7 lg:hidden">
            <img
              src="/logo-alzarsi.png"
              alt="Alzarsi Logística"
              className="h-auto w-[165px] object-contain"
            />
          </div>

          <div className="mb-7">
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-gold">
              Novo acesso
            </p>

            <h2 className="mt-2 text-3xl font-bold tracking-tight">
              Cadastrar usuário
            </h2>

            <p className="mt-2 text-sm text-muted-foreground">
              Preencha os dados para criar seu acesso ao SGI.
            </p>
          </div>

          <form
            onSubmit={cadastrar}
            className="space-y-4"
          >
            <Campo
              titulo="Nome completo"
            >
              <div className="relative">
                <UserRound
                  className="pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-muted-foreground"
                  aria-hidden="true"
                />

                <input
                  value={nome}
                  onChange={(evento) =>
                    setNome(
                      evento.target.value,
                    )
                  }
                  disabled={cadastrando}
                  autoComplete="name"
                  placeholder="Nome e sobrenome"
                  className="h-12 w-full rounded-lg border border-input bg-background pl-11 pr-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/15"
                />
              </div>
            </Campo>

            <Campo
              titulo="Login"
            >
              <div className="relative">
                <UserRound
                  className="pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-muted-foreground"
                  aria-hidden="true"
                />

                <input
                  value={login}
                  onChange={(evento) =>
                    setLogin(
                      evento.target.value,
                    )
                  }
                  disabled={cadastrando}
                  autoComplete="username"
                  placeholder="Escolha seu login"
                  className="h-12 w-full rounded-lg border border-input bg-background pl-11 pr-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/15"
                />
              </div>
            </Campo>

            <Campo
              titulo="E-mail"
              complemento="Opcional"
            >
              <div className="relative">
                <Mail
                  className="pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-muted-foreground"
                  aria-hidden="true"
                />

                <input
                  type="email"
                  value={email}
                  onChange={(evento) =>
                    setEmail(
                      evento.target.value,
                    )
                  }
                  disabled={cadastrando}
                  autoComplete="email"
                  placeholder="email@empresa.com"
                  className="h-12 w-full rounded-lg border border-input bg-background pl-11 pr-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/15"
                />
              </div>
            </Campo>

            <Campo
              titulo="Senha"
            >
              <div className="relative">
                <LockKeyhole
                  className="pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-muted-foreground"
                  aria-hidden="true"
                />

                <input
                  type={
                    mostrarSenha
                      ? "text"
                      : "password"
                  }
                  value={senha}
                  onChange={(evento) =>
                    setSenha(
                      evento.target.value,
                    )
                  }
                  disabled={cadastrando}
                  minLength={8}
                  autoComplete="new-password"
                  placeholder="Mínimo de 8 caracteres"
                  className="h-12 w-full rounded-lg border border-input bg-background pl-11 pr-12 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/15"
                />

                <button
                  type="button"
                  onClick={() =>
                    setMostrarSenha(
                      (valor) => !valor,
                    )
                  }
                  aria-label={
                    mostrarSenha
                      ? "Ocultar senha"
                      : "Mostrar senha"
                  }
                  className="absolute right-2 top-1/2 flex size-9 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground hover:bg-muted"
                >
                  {mostrarSenha ? (
                    <EyeOff
                      className="size-5"
                      aria-hidden="true"
                    />
                  ) : (
                    <Eye
                      className="size-5"
                      aria-hidden="true"
                    />
                  )}
                </button>
              </div>
            </Campo>

            <Campo
              titulo="Confirmar senha"
            >
              <div className="relative">
                <LockKeyhole
                  className="pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-muted-foreground"
                  aria-hidden="true"
                />

                <input
                  type={
                    mostrarSenha
                      ? "text"
                      : "password"
                  }
                  value={confirmarSenha}
                  onChange={(evento) =>
                    setConfirmarSenha(
                      evento.target.value,
                    )
                  }
                  disabled={cadastrando}
                  minLength={8}
                  autoComplete="new-password"
                  placeholder="Repita sua senha"
                  className="h-12 w-full rounded-lg border border-input bg-background pl-11 pr-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/15"
                />
              </div>
            </Campo>

            <div className="rounded-lg border border-border bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
              O cadastro será criado com o perfil
              <strong className="ml-1 text-foreground">
                OPERADOR
              </strong>.
            </div>

            <Button
              type="submit"
              disabled={cadastrando}
              className="h-12 w-full font-bold uppercase tracking-wide"
            >
              {cadastrando
                ? "Cadastrando..."
                : "Cadastrar usuário"}
            </Button>
          </form>

          <div className="mt-6 text-center text-sm text-muted-foreground">
            Já possui uma conta?{" "}
            <a
              href="/login"
              className="font-semibold text-primary hover:underline"
            >
              Voltar para o login
            </a>
          </div>
        </div>
      </section>
    </main>
  );
}

function Campo({
  titulo,
  complemento,
  children,
}: {
  titulo: string;
  complemento?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold">
          {titulo}
        </span>

        {complemento ? (
          <span className="text-xs text-muted-foreground">
            {complemento}
          </span>
        ) : null}
      </div>

      {children}
    </label>
  );
}
