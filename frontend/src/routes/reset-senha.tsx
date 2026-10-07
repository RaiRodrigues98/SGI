import { createFileRoute, useNavigate } from "@tanstack/react-router";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Eye,
  EyeOff,
  KeyRound,
  LockKeyhole,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { redefinirSenha } from "@/services/passwordResetService";

import "./login.css";

export const Route = createFileRoute("/reset-senha")({
  head: () => ({
    meta: [{ title: "Redefinir senha \u2014 SGI" }],
  }),
  component: ResetSenhaPage,
});

function ResetSenhaPage() {
  const navigate = useNavigate();

  const [token, setToken] = useState<string | null>(null);
  const [novaSenha, setNovaSenha] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [mostrarSenha, setMostrarSenha] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setToken(params.get("token"));
  }, []);

  const senhaValida = novaSenha.length >= 8;
  const senhasConferem =
    novaSenha.length > 0 && novaSenha === confirmacao;

  async function redefinir(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setErro(null);

    if (!token) {
      setErro("Token ausente. Solicite um novo link de recuperacao.");
      return;
    }

    if (!senhaValida) {
      setErro("A nova senha deve ter ao menos 8 caracteres.");
      return;
    }

    if (!senhasConferem) {
      setErro("As senhas nao coincidem.");
      return;
    }

    setEnviando(true);

    try {
      await redefinirSenha(token, novaSenha);
      setSucesso(true);
      setTimeout(() => {
        void navigate({ to: "/login" });
      }, 2500);
    } catch (falha) {
      setErro(
        falha instanceof Error
          ? falha.message
          : "Nao foi possivel redefinir a senha.",
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

            {!token ? (
              <>
                <div className="login-v4__heading">
                  <span>Link invalido</span>
                  <h2>Nao foi possivel validar o link</h2>
                  <p>
                    O link de recuperacao esta incompleto ou foi copiado
                    incorretamente. Solicite um novo.
                  </p>
                </div>

                <div className="login-v4__register">
                  <a href="/esqueci-senha">
                    Solicitar novo link
                    <ArrowRight />
                  </a>
                </div>
              </>
            ) : sucesso ? (
              <>
                <div className="login-v4__heading">
                  <span>Tudo certo</span>
                  <h2>Senha redefinida</h2>
                  <p>
                    Sua nova senha foi salva com sucesso. Voce sera
                    redirecionado para a tela de login em instantes.
                  </p>
                </div>

                <div className="login-v4__register">
                  <a href="/login">
                    Ir para o login agora
                    <ArrowRight />
                  </a>
                </div>

                <div className="login-v4__security">
                  <div>
                    <CheckCircle2 />
                  </div>
                  <p>
                    <strong>Alteracao concluida</strong>
                    <span>Use a nova senha no proximo acesso.</span>
                  </p>
                </div>
              </>
            ) : (
              <>
                <div className="login-v4__heading">
                  <span>Redefinicao de senha</span>
                  <h2>Crie uma nova senha</h2>
                  <p>
                    Escolha uma senha com pelo menos 8 caracteres.
                    Ela sera usada no seu proximo acesso ao SGI.
                  </p>
                </div>

                <form onSubmit={redefinir} className="login-v4__form">
                  <div className="login-v4__field">
                    <label htmlFor="nova-senha">Nova senha</label>

                    <div className="login-v4__input">
                      <KeyRound />

                      <input
                        id="nova-senha"
                        type={mostrarSenha ? "text" : "password"}
                        autoComplete="new-password"
                        value={novaSenha}
                        disabled={enviando}
                        placeholder="Digite a nova senha"
                        onChange={(evento) =>
                          setNovaSenha(evento.target.value)
                        }
                      />

                      <button
                        type="button"
                        onClick={() =>
                          setMostrarSenha((valor) => !valor)
                        }
                        aria-label={
                          mostrarSenha
                            ? "Ocultar senha"
                            : "Mostrar senha"
                        }
                      >
                        {mostrarSenha ? <EyeOff /> : <Eye />}
                      </button>
                    </div>
                  </div>

                  <div className="login-v4__field">
                    <label htmlFor="confirmacao">
                      Confirmar nova senha
                    </label>

                    <div className="login-v4__input">
                      <LockKeyhole />

                      <input
                        id="confirmacao"
                        type={mostrarSenha ? "text" : "password"}
                        autoComplete="new-password"
                        value={confirmacao}
                        disabled={enviando}
                        placeholder="Repita a nova senha"
                        onChange={(evento) =>
                          setConfirmacao(evento.target.value)
                        }
                      />
                    </div>
                  </div>

                  {erro ? (
                    <div className="login-v4__error">{erro}</div>
                  ) : null}

                  <button
                    type="submit"
                    className="login-v4__submit"
                    disabled={
                      enviando ||
                      !novaSenha ||
                      !confirmacao ||
                      !senhaValida ||
                      !senhasConferem
                    }
                  >
                    <span>
                      {enviando ? "Salvando..." : "Redefinir senha"}
                    </span>
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
                <ShieldCheck />
              </div>
              <p>
                <strong>Ambiente seguro e corporativo</strong>
                <span>Acesso protegido e controlado pelo SGI</span>
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
