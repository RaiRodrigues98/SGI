import { createFileRoute } from "@tanstack/react-router";
import {
  ArrowLeft,
  ArrowRight,
  MailCheck,
  Send,
  ShieldCheck,
} from "lucide-react";
import { useState, type FormEvent } from "react";

import { solicitarRecuperacaoSenha } from "@/services/passwordResetService";

import "./login.css";

export const Route = createFileRoute("/esqueci-senha")({
  head: () => ({
    meta: [{ title: "Esqueci minha senha \u2014 SGI" }],
  }),
  component: EsqueciSenhaPage,
});

function EsqueciSenhaPage() {
  const [email, setEmail] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [enviado, setEnviado] = useState(false);

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setErro(null);
    setEnviando(true);

    try {
      await solicitarRecuperacaoSenha(email.trim());
      setEnviado(true);
    } catch (falha) {
      setErro(
        falha instanceof Error
          ? falha.message
          : "Nao foi possivel solicitar a recuperacao.",
      );
    } finally {
      setEnviando(false);
    }
  }

  return (
    <main className="login-v4">
      <section className="login-v4__access" style={{ width: "100%" }}>
        <div className="login-v4__orb login-v4__orb--top" />
        <div className="login-v4__orb login-v4__orb--bottom" />

        <img
          src="/logo-alzarsi.png"
          alt="Alzarsi Logistica"
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

            {enviado ? (
              <>
                <div className="login-v4__heading">
                  <span>Recuperacao de acesso</span>
                  <h2>Verifique seu e-mail</h2>
                  <p>
                    Se o endereco <strong>{email}</strong> estiver
                    cadastrado em uma conta ativa do SGI, enviamos um
                    link para voce criar uma nova senha.
                  </p>
                  <p style={{ marginTop: 12, fontSize: 13, color: "#64748b" }}>
                    O link expira em 30 minutos e so pode ser usado uma vez.
                  </p>
                </div>

                <div className="login-v4__register">
                  <a href="/login">
                    <ArrowLeft />
                    Voltar para o login
                  </a>
                </div>
              </>
            ) : (
              <>
                <div className="login-v4__heading">
                  <span>Recuperacao de acesso</span>
                  <h2>Esqueci minha senha</h2>
                  <p>
                    Informe o e-mail cadastrado na sua conta. Enviaremos
                    um link para voce criar uma nova senha.
                  </p>
                </div>

                <form onSubmit={enviar} className="login-v4__form">
                  <div className="login-v4__field">
                    <label htmlFor="email">E-mail</label>

                    <div className="login-v4__input">
                      <Send />

                      <input
                        id="email"
                        type="email"
                        autoComplete="email"
                        value={email}
                        disabled={enviando}
                        placeholder="seu.email@alzarsilog.com.br"
                        onChange={(evento) => setEmail(evento.target.value)}
                        required
                      />
                    </div>
                  </div>

                  {erro ? <div className="login-v4__error">{erro}</div> : null}

                  <button
                    type="submit"
                    className="login-v4__submit"
                    disabled={enviando || !email.trim()}
                  >
                    <span>{enviando ? "Enviando..." : "Enviar link"}</span>
                    {!enviando ? <ArrowRight /> : null}
                  </button>
                </form>

                <div className="login-v4__register">
                  <a href="/login">
                    <ArrowLeft />
                    Voltar para o login
                  </a>
                </div>
              </>
            )}

            <div className="login-v4__security">
              <div>
                <MailCheck />
              </div>
              <p>
                <strong>Privacidade garantida</strong>
                <span>
                  Nao revelamos se um e-mail esta ou nao cadastrado.
                </span>
              </p>
            </div>
          </div>

          <div className="login-v4__company">
            <span>Alzarsi Logistica</span>
            <b />
            <small>Mais valor em cada destino.</small>
          </div>
        </div>
      </section>
    </main>
  );
}
