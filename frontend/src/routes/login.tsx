import {
  createFileRoute,
  useNavigate,
} from "@tanstack/react-router";

import {
  ArrowRight,
  BarChart3,
  Boxes,
  Eye,
  EyeOff,
  LockKeyhole,
  ShieldCheck,
  UserRound,
} from "lucide-react";

import {
  useEffect,
  useState,
} from "react";

import type {
  FormEvent,
} from "react";

import {
  estaAutenticado,
  login,
} from "@/services/authService";

import "./login.css";

export const Route = createFileRoute(
  "/login",
)({
  head: () => ({
    meta: [
      {
        title: "Login \u2014 SGI",
      },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();

  const [usuario, setUsuario] =
    useState("");

  const [senha, setSenha] =
    useState("");

  const [mostrarSenha, setMostrarSenha] =
    useState(false);

  const [erro, setErro] =
    useState<string | null>(null);

  const [entrando, setEntrando] =
    useState(false);

  useEffect(() => {
    if (estaAutenticado()) {
      void navigate({
        to: "/",
      });
    }
  }, [navigate]);

  async function entrar(
    evento: FormEvent<HTMLFormElement>,
  ) {
    evento.preventDefault();

    setErro(null);
    setEntrando(true);

    try {
      await login({
        login: usuario,
        senha,
      });

      await navigate({
        to: "/",
      });
    } catch (falha) {
      setErro(
        falha instanceof Error
          ? falha.message
          : "Não foi possível realizar o login.",
      );
    } finally {
      setEntrando(false);
    }
  }

  return (
    <main className="login-v4">
      <section className="login-v4__hero">
        <div className="login-v4__photo" />

        <div className="login-v4__hero-inner">
          <header className="login-v4__brand">
            <img
              src="/logo-alzarsi.png"
              alt="Alzarsi Logística"
            />

            <span>
              Pessoas
              <i />
              Processos
              <i />
              Resultados
            </span>
          </header>

          <div className="login-v4__content">
            <div className="login-v4__eyebrow">
              <b />

              <span>
                SGI | Sistema de Gestão de Inventário
              </span>
            </div>

            <h1>
              Controle inteligente
              <strong>
                de inventário
              </strong>
            </h1>

            <p className="login-v4__description">
              Visibilidade, confiabilidade e governança
              do estoque em uma única plataforma.
            </p>

            <div className="login-v4__benefits">
              <Benefit
                icon={<BarChart3 />}
                title="Mais produtividade"
              />

              <Benefit
                icon={<ShieldCheck />}
                title="Mais confiabilidade"
              />

              <Benefit
                icon={<Boxes />}
                title="Mais controle"
              />
            </div>
          </div>

          <div
            className="login-v4__visual"
            aria-hidden="true"
          >
            <div className="login-v4__metric login-v4__metric--stock">
              <span>
                Acuracidade do estoque
              </span>

              <strong>
                98,7%
              </strong>

              <small>
                confiabilidade no inventário
              </small>

              <div className="login-v4__mini-bars">
                <i />
                <i />
                <i />
                <i />
                <i />
                <i />
              </div>
            </div>



            <div className="login-v4__metric login-v4__metric--cycle">
              <span>
                Contagem atual
              </span>

              <strong>
                EM CURSO
              </strong>

              <small>
                monitoramento operacional
              </small>

              <Boxes />
            </div>

            <div className="login-v4__ribbon">
              <div className="login-v4__ribbon-mark">
                <img
                  src="/logo-alzarsi-semnome.png"
                  alt="Alzarsi"
                />
              </div>

              <span>
                Estoque
              </span>

              <span>
                Em movimento
              </span>

              <strong>
                Resultados
              </strong>

              <span>
                Sempre
              </span>

              <b />
            </div>
          </div>

          {/* Mesmo enquadramento da foto; recorte no sistema de coordenadas do asset. */}
          <svg
            className="login-v4__foreground"
            viewBox="0 0 1024 1536"
            preserveAspectRatio="xMidYMid slice"
            aria-hidden="true"
            focusable="false"
          >
            <defs>
              <clipPath id="login-v4-box-clip" clipPathUnits="userSpaceOnUse">
                <polygon points="476,950 590,930 744,932 868,940 869,1184 748,1225 476,1202" />
              </clipPath>
            </defs>
            <image
              href="/login-warehouse-hero.png"
              width="1024"
              height="1536"
              clipPath="url(#login-v4-box-clip)"
            />
          </svg>

          <footer className="login-v4__hero-footer">
            <div>
              <b />

              <strong>
                SGI Alzarsilog
              </strong>

              <span>
                Logística que impulsiona o seu negócio.
              </span>
            </div>

            <span>
              Operações que conectam oportunidades
            </span>
          </footer>
        </div>
      </section>

      <section className="login-v4__access">
        <div className="login-v4__orb login-v4__orb--top" />
        <div className="login-v4__orb login-v4__orb--bottom" />

        <img
          src="/logo-alzarsi.png"
          alt="Alzarsi Logística"
          className="login-v4__mobile-brand"
        />

        <div className="login-v4__login-shell">
          <div className="login-v4__card">
            <div className="login-v4__mark">
              <img
                src="/logo-alzarsi-semnome.png"
                alt=""
                aria-hidden="true"
              />
            </div>

            <div className="login-v4__heading">
              <span>
                Acesso ao sistema
              </span>

              <h2>
                Acesse o SGI
              </h2>

              <p>
                Entre com seu login e senha para continuar.
              </p>
            </div>

            <form
              onSubmit={entrar}
              className="login-v4__form"
            >
              <div className="login-v4__field">
                <label htmlFor="login">
                  Login
                </label>

                <div className="login-v4__input">
                  <UserRound />

                  <input
                    id="login"
                    autoComplete="username"
                    value={usuario}
                    disabled={entrando}
                    placeholder="Digite seu login"
                    onChange={(evento) =>
                      setUsuario(
                        evento.target.value,
                      )
                    }
                  />
                </div>
              </div>

              <div className="login-v4__field">
                <div className="login-v4__field-header">
                  <label htmlFor="senha">
                    Senha
                  </label>

                  <a href="/esqueci-senha">
                    Esqueci minha senha
                  </a>
                </div>

                <div className="login-v4__input">
                  <LockKeyhole />

                  <input
                    id="senha"
                    type={
                      mostrarSenha
                        ? "text"
                        : "password"
                    }
                    autoComplete="current-password"
                    value={senha}
                    disabled={entrando}
                    placeholder="Digite sua senha"
                    onChange={(evento) =>
                      setSenha(
                        evento.target.value,
                      )
                    }
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
                  >
                    {mostrarSenha ? (
                      <EyeOff />
                    ) : (
                      <Eye />
                    )}
                  </button>
                </div>
              </div>

              {erro ? (
                <div className="login-v4__error">
                  {erro}
                </div>
              ) : null}

              <button
                type="submit"
                className="login-v4__submit"
                disabled={
                  entrando ||
                  !usuario.trim() ||
                  !senha
                }
              >
                <span>
                  {entrando
                    ? "Entrando..."
                    : "Entrar"}
                </span>

                {!entrando ? (
                  <ArrowRight />
                ) : null}
              </button>
            </form>

            <div className="login-v4__divider">
              <i />
              <span>
                Novo acesso
              </span>
              <i />
            </div>

            <div className="login-v4__register">
              <a href="/cadastro">
                Cadastrar usuário
                <ArrowRight />
              </a>
            </div>

            <div className="login-v4__security">
              <div>
                <ShieldCheck />
              </div>

              <p>
                <strong>
                  Ambiente seguro e corporativo
                </strong>

                <span>
                  Acesso protegido e controlado pelo SGI
                </span>
              </p>
            </div>
          </div>

          <div className="login-v4__company">
            <span>
              Alzarsi Logística
            </span>

            <b />

            <small>
              Mais valor em cada destino.
            </small>
          </div>
        </div>
      </section>
    </main>
  );
}

function Benefit({
  icon,
  title,
}: {
  icon: React.ReactNode;
  title: string;
}) {
  return (
    <div className="login-v4__benefit">
      <div>
        {icon}
      </div>

      <strong>
        {title}
      </strong>
    </div>
  );
}
