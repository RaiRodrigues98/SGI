import { Link, useRouterState } from "@tanstack/react-router";
import { Menu, RefreshCw, Bell, CheckCheck, PanelLeftClose } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { navItems, type NavItem } from "@/components/layout/navItems";
import {
  EVENTO_INVENTARIO_ATUAL_ALTERADO,
  limparInventarioAtual,
  obterTipoInventarioAtual,
  type TipoInventarioAtual,
} from "@/lib/inventarioAtual";
import {
  logout,
  obterUsuarioSalvo,
} from "@/services/authService";
import {
  consultarQuantidadeNaoLidas,
  listarNotificacoes,
  marcarNotificacaoComoLida,
  marcarTodasComoLidas,
  type Notificacao,
} from "@/services/notificationService";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

function classesItem(ativo: boolean, habilitado: boolean, expandido: boolean) {
  return cn(
    "flex items-center rounded-lg text-sm font-medium transition-colors",
    expandido ? "gap-3 px-3 py-2.5" : "size-11 justify-center",
    ativo
      ? "bg-gold-light text-primary"
      : habilitado
        ? "text-foreground/70 hover:bg-gold-light/40 hover:text-primary"
        : "text-muted-foreground/45",
  );
}

type AcaoNotificacaoOperador = {
  destino: string;
  rotulo: string;
};

function obterAcaoNotificacaoOperador(
  notificacao: Notificacao,
): AcaoNotificacaoOperador | null {
  const tipo = String(
    notificacao.tipo ?? "",
  )
    .trim()
    .toUpperCase();

  /*
   * Eventos que realmente representam
   * trabalho operacional de contagem.
   */
  if (
    notificacao.id_inventario &&
    tipo === "RECONTAGEM_GERADA"
  ) {
    return {
      destino:
        `/contagem?inventario=${notificacao.id_inventario}`,
      rotulo: "Iniciar recontagem",
    };
  }

  if (
    notificacao.id_inventario &&
    tipo === "RECONTAGEM_SOLICITADA"
  ) {
    return {
      destino:
        `/contagem?inventario=${notificacao.id_inventario}`,
      rotulo: "Ver recontagem",
    };
  }

  /*
   * Uma URL explicitamente operacional
   * continua sendo respeitada.
   */
  const url =
    notificacao.url?.trim() ?? "";

  if (
    url === "/contagem" ||
    url.startsWith("/contagem?")
  ) {
    return {
      destino: url,
      rotulo: "Ir para contagem",
    };
  }

  /*
   * O operador restrito nao recebe CTA
   * para telas gerenciais, administrativas
   * ou detalhe geral do inventario.
   */
  return null;
}

function ItemLateral({
  item,
  ativo,
  expandido,
  onNavegar,
}: {
  item: NavItem;
  ativo: boolean;
  expandido: boolean;
  onNavegar?: () => void;
}) {
  const Icone = item.icone;
  const classes = classesItem(ativo, Boolean(item.to), expandido);

  const conteudo = item.to ? (
    <Link to={item.to} onClick={onNavegar} className={classes} aria-label={item.nome}>
      <Icone className="size-5 shrink-0" aria-hidden="true" />
      {expandido ? <span className="truncate">{item.nome}</span> : null}
    </Link>
  ) : (
    <span className={classes} aria-disabled="true">
      <Icone className="size-5 shrink-0" aria-hidden="true" />
      {expandido ? <span className="truncate">{item.nome}</span> : null}
    </span>
  );

  if (expandido) return conteudo;

  return (
    <Tooltip>
      <TooltipTrigger asChild>{conteudo}</TooltipTrigger>
      <TooltipContent side="right">
        {item.nome}
        {item.to ? "" : " (em breve)"}
      </TooltipContent>
    </Tooltip>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [menuAberto, setMenuAberto] = useState(false);
  const [expandido, setExpandido] = useState(true);
  const [recarregando, setRecarregando] = useState(false);
  const [notificacoesAbertas, setNotificacoesAbertas] = useState(false);
  const [notificacoes, setNotificacoes] = useState<Notificacao[]>([]);
  const [quantidadeNaoLidas, setQuantidadeNaoLidas] = useState(0);
  const [carregandoNotificacoes, setCarregandoNotificacoes] = useState(false);
  const [erroNotificacoes, setErroNotificacoes] = useState<string | null>(null);

  const [
    notificacaoSelecionada,
    setNotificacaoSelecionada,
  ] = useState<Notificacao | null>(null);

  const [
    menuUsuarioAberto,
    setMenuUsuarioAberto,
  ] = useState(false);
  const pathname = useRouterState({ select: (r) => r.location.pathname });

  const [usuario, setUsuario] =
    useState<ReturnType<typeof obterUsuarioSalvo>>(null);

  const [
    tipoInventarioAtual,
    setTipoInventarioAtual,
  ] = useState<TipoInventarioAtual | null>(
    null,
  );

  useEffect(() => {
    setUsuario(obterUsuarioSalvo());
  }, []);

  useEffect(() => {
    if (!notificacaoSelecionada) {
      return;
    }

    function fecharComEscape(
      evento: KeyboardEvent,
    ) {
      if (evento.key === "Escape") {
        setNotificacaoSelecionada(null);
      }
    }

    window.addEventListener(
      "keydown",
      fecharComEscape,
    );

    return () => {
      window.removeEventListener(
        "keydown",
        fecharComEscape,
      );
    };
  }, [notificacaoSelecionada]);

  useEffect(() => {
    if (!usuario?.id_usuario) {
      return;
    }

    let ativo = true;

    async function atualizarContador() {
      try {
        const quantidade =
          await consultarQuantidadeNaoLidas();

        if (ativo) {
          setQuantidadeNaoLidas(quantidade);
        }
      } catch {
        // O sino não deve interromper o restante do sistema.
      }
    }

    void atualizarContador();

    const intervalo = window.setInterval(
      atualizarContador,
      30_000,
    );

    return () => {
      ativo = false;
      window.clearInterval(intervalo);
    };
  }, [usuario?.id_usuario]);

  useEffect(() => {
    function atualizarTipoInventario() {
      setTipoInventarioAtual(
        obterTipoInventarioAtual(),
      );
    }

    atualizarTipoInventario();

    window.addEventListener(
      EVENTO_INVENTARIO_ATUAL_ALTERADO,
      atualizarTipoInventario,
    );

    return () => {
      window.removeEventListener(
        EVENTO_INVENTARIO_ATUAL_ALTERADO,
        atualizarTipoInventario,
      );
    };
  }, [pathname]);

  const permissoes = new Set(
    (usuario?.permissoes ?? [])
      .map((permissao) =>
        typeof permissao === "string"
          ? permissao
          : permissao.codigo,
      )
      .filter(Boolean),
  );

  const operadorRestrito =
    permissoes.has("CONTAGEM_EXECUTAR") &&
    ![
      "ANALISE_VISUALIZAR",
      "CONFIGURACAO_EDITAR",
      "CONFIGURACAO_VISUALIZAR",
      "GESTOR_DECIDIR",
      "INVENTARIO_CRIAR",
      "INVENTARIO_FINALIZAR",
      "INVENTARIO_ROTATIVO_DECIDIR",
      "PLANO_ACAO_GERENCIAR",
      "PLANO_ACAO_VISUALIZAR",
      "RODADA_GERAR",
      "USUARIO_GERENCIAR",
    ].some((permissao) =>
      permissoes.has(permissao),
    );

  const podeAcessarHistorico =
    permissoes.has("ANALISE_VISUALIZAR") ||
    permissoes.has("PLANO_ACAO_VISUALIZAR");

  const navItemsVisiveis = navItems.filter(
    (item) => {
      /*
       * Historico concentra tambem Tratativas.
       * O item fica visivel para quem pode consultar
       * analises ou planos de acao.
       */
      if (item.to === "/historico") {
        if (!podeAcessarHistorico) {
          return false;
        }
      } else if (
        item.permissao &&
        !permissoes.has(item.permissao)
      ) {
        return false;
      }

      if (item.to === "/analise-ciclica") {
        return (
          tipoInventarioAtual ===
          "ROTATIVO"
        );
      }

      if (
        item.to === "/analise-oficial"
      ) {
        return (
          tipoInventarioAtual ===
          "OFICIAL"
        );
      }

      return true;
    },
  );

  const itensPrincipais =
    navItemsVisiveis.filter(
      (item) =>
        item.secao !== "ADMINISTRACAO",
    );

  const itensAdministrativos =
    navItemsVisiveis.filter(
      (item) =>
        item.secao === "ADMINISTRACAO",
    );

  async function carregarPainelNotificacoes() {
    setCarregandoNotificacoes(true);
    setErroNotificacoes(null);

    try {
      const resposta = await listarNotificacoes();
      setNotificacoes(resposta.notificacoes);

      setQuantidadeNaoLidas(
        resposta.notificacoes.filter(
          (notificacao) => !notificacao.lida,
        ).length,
      );
    } catch {
      setErroNotificacoes(
        "Não foi possível carregar as notificações.",
      );
    } finally {
      setCarregandoNotificacoes(false);
    }
  }

  function irParaDestinoNotificacao() {
    if (
      !notificacaoSelecionada ||
      typeof window === "undefined"
    ) {
      return;
    }

    const acao =
      obterAcaoNotificacaoOperador(
        notificacaoSelecionada,
      );

    if (!acao) {
      return;
    }

    setNotificacaoSelecionada(null);

    window.location.href =
      acao.destino;
  }

  async function abrirNotificacao(
    notificacao: Notificacao,
  ) {
    setNotificacoesAbertas(false);

    /*
     * O operador consulta primeiro o detalhe
     * da notificacao antes de navegar.
     */
    if (operadorRestrito) {
      setNotificacaoSelecionada(
        notificacao,
      );
    }

    if (!notificacao.lida) {
      try {
        await marcarNotificacaoComoLida(
          notificacao.id_notificacao,
        );

        const dataLeitura =
          new Date().toISOString();

        setNotificacoes((atuais) =>
          atuais.map((item) =>
            item.id_notificacao ===
            notificacao.id_notificacao
              ? {
                  ...item,
                  lida: true,
                  data_leitura:
                    dataLeitura,
                }
              : item,
          ),
        );

        if (operadorRestrito) {
          setNotificacaoSelecionada(
            (atual) =>
              atual?.id_notificacao ===
              notificacao.id_notificacao
                ? {
                    ...atual,
                    lida: true,
                    data_leitura:
                      dataLeitura,
                  }
                : atual,
          );
        }

        setQuantidadeNaoLidas(
          (atual) =>
            Math.max(
              0,
              atual - 1,
            ),
        );

        setErroNotificacoes(null);
      } catch {
        setErroNotificacoes(
          "N\u00e3o foi poss\u00edvel marcar a notifica\u00e7\u00e3o como lida.",
        );
      }
    }

    /*
     * Para OPERADOR, nao navega automaticamente.
     */
    if (operadorRestrito) {
      return;
    }

    /*
     * Demais perfis mantem o comportamento atual.
     */
    if (
      notificacao.url &&
      typeof window !== "undefined"
    ) {
      window.location.href =
        notificacao.url;
    }
  }

  async function lerTodasNotificacoes() {
    try {
      await marcarTodasComoLidas();

      setNotificacoes((atuais) =>
        atuais.map((item) => ({
          ...item,
          lida: true,
          data_leitura:
            item.data_leitura ??
            new Date().toISOString(),
        })),
      );

      setQuantidadeNaoLidas(0);
      setErroNotificacoes(null);
    } catch {
      setErroNotificacoes(
        "Não foi possível marcar todas como lidas.",
      );
    }
  }

  function recarregarSistema() {
    if (recarregando || typeof window === "undefined") {
      return;
    }

    setRecarregando(true);

    window.setTimeout(() => {
      window.location.reload();
    }, 150);
  }

  function sairDoSistema() {
    limparInventarioAtual();
    logout();

    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  }

  const partesNomeUsuario = (
    usuario?.nome ?? "U"
  )
    .trim()
    .split(/\s+/)
    .filter(Boolean);

  const primeiroNome =
    partesNomeUsuario[0] ?? "U";

  const ultimoNome =
    partesNomeUsuario[
      partesNomeUsuario.length - 1
    ] ?? primeiroNome;

  const iniciaisUsuario =
    partesNomeUsuario.length > 1
      ? (
          primeiroNome.charAt(0) +
          ultimoNome.charAt(0)
        ).toUpperCase()
      : primeiroNome
          .slice(0, 2)
          .toUpperCase();

  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex min-h-screen w-full overflow-x-hidden bg-background">

        {/* ==================================================
            SIDEBAR DESKTOP
        ================================================== */}
        <aside
          className={cn(
            "sticky top-0 z-40 hidden h-screen shrink-0 flex-col border-r border-border bg-card transition-[width] duration-200 lg:flex",
            expandido ? "w-64" : "w-[72px]",
          )}
        >
          <div
            className={cn(
              "flex h-14 shrink-0 items-center",
              expandido
                ? "justify-between bg-brand px-3 text-brand-foreground"
                : "justify-center bg-card px-0 text-primary",
            )}
          >
            {expandido ? (
              <div className="flex min-w-0 items-center overflow-hidden">
                <img
                  src="/logo-alzarsi.png"
                  alt="Alzarsi Logística"
                  className="h-auto w-[150px] shrink-0 object-contain object-left"
                />
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setExpandido(true)}
                aria-label="Expandir menu"
                title="Expandir menu"
                className="flex size-11 items-center justify-center overflow-hidden rounded-lg transition-colors hover:bg-muted"
              >
                <span
                  className="flex h-10 w-10 items-center overflow-hidden"
                  aria-hidden="true"
                >
                  <img
                    src="/logo-alzarsi.png"
                    alt=""
                    className="h-auto w-[125px] max-w-none shrink-0 object-contain object-left"
                  />
                </span>
              </button>
            )}

            {expandido && (
              <button
                type="button"
                onClick={() => setExpandido(false)}
                aria-label="Recolher menu"
                title="Recolher menu"
                className="flex size-8 shrink-0 items-center justify-center rounded-md text-brand-foreground transition-colors hover:bg-brand-foreground/10"
              >
                <PanelLeftClose
                  className="size-5"
                  aria-hidden="true"
                />
              </button>
            )}
          </div>

          <nav
            className={cn(
              "flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto py-3",
              expandido ? "px-2" : "items-center px-2",
            )}
          >
            {itensPrincipais.map((item) => (
              <ItemLateral
                key={item.nome}
                item={item}
                ativo={item.to === pathname}
                expandido={expandido}
              />
            ))}

          </nav>

          {!expandido && (
            <div className="flex shrink-0 justify-center px-2 pb-4 pt-2">
              <div
                className="flex size-8 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground"
                title={usuario?.nome ?? "Usuario"}
                aria-label={usuario?.nome ?? "Usuario"}
              >
                {iniciaisUsuario || "U"}
              </div>
            </div>
          )}
        </aside>

        {/* ==================================================
            CONTEUDO
        ================================================== */}
        <div className="flex min-w-0 flex-1 flex-col">

          {/* HEADER */}
          <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-2 bg-brand px-2 text-brand-foreground sm:px-3">

            {/* MOBILE */}
            <button
              type="button"
              onClick={() =>
                setMenuAberto(true)
              }
              aria-label="Abrir menu"
              className="flex size-10 items-center justify-center rounded-md hover:bg-brand-foreground/10 lg:hidden"
            >
              <Menu
                className="size-5"
                aria-hidden="true"
              />
            </button>

            <div className="flex shrink-0 items-center lg:hidden">
              <img
                src="/logo-alzarsi.png"
                alt="Alzarsi Logística"
                className="h-auto w-[135px] object-contain"
              />
            </div>

            <div className="flex-1" />

            <div className="ml-auto flex items-center gap-1">

              <button
                type="button"
                onClick={recarregarSistema}
                disabled={recarregando}
                aria-label={recarregando ? "Atualizando sistema" : "Atualizar sistema"}
                title={recarregando ? "Atualizando..." : "Atualizar"}
                className="hidden size-9 items-center justify-center rounded-md text-brand-foreground/80 transition-colors hover:bg-brand-foreground/10 hover:text-brand-foreground disabled:cursor-wait disabled:opacity-60 sm:flex"
              >
                <RefreshCw
                  className={cn(
                    "size-5",
                    recarregando && "animate-spin",
                  )}
                  aria-hidden="true"
                />
              </button>

              <div className="relative hidden sm:block">
                <button
                  type="button"
                  onClick={() => {
                    const abrir =
                      !notificacoesAbertas;

                    setNotificacoesAbertas(abrir);
                    setMenuUsuarioAberto(false);

                    if (abrir) {
                      void carregarPainelNotificacoes();
                    }
                  }}
                  aria-label="Abrir notificações"
                  aria-expanded={notificacoesAbertas}
                  title="Notificações"
                  className="relative flex size-9 items-center justify-center rounded-md text-brand-foreground/80 transition-colors hover:bg-brand-foreground/10 hover:text-brand-foreground"
                >
                  <Bell
                    className="size-5"
                    aria-hidden="true"
                  />

                  {quantidadeNaoLidas > 0 && (
                    <span className="absolute -right-0.5 -top-0.5 flex min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold leading-4 text-white">
                      {quantidadeNaoLidas > 99
                        ? "99+"
                        : quantidadeNaoLidas}
                    </span>
                  )}
                </button>

                {notificacoesAbertas && (
                  <div className="absolute right-0 top-11 z-50 w-[min(92vw,380px)] overflow-hidden rounded-lg border border-border bg-popover text-popover-foreground shadow-xl">
                    <div className="flex items-center justify-between border-b border-border px-4 py-3">
                      <div>
                        <div className="text-sm font-semibold">
                          Notificações
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {quantidadeNaoLidas} não lida(s)
                        </div>
                      </div>

                      <button
                        type="button"
                        onClick={() =>
                          void lerTodasNotificacoes()
                        }
                        disabled={
                          quantidadeNaoLidas === 0 ||
                          carregandoNotificacoes
                        }
                        className="flex items-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <CheckCheck className="size-4" />
                        Marcar todas
                      </button>
                    </div>

                    {erroNotificacoes && (
                      <div className="border-b border-border bg-destructive/10 px-4 py-2 text-xs text-destructive">
                        {erroNotificacoes}
                      </div>
                    )}

                    <div className="max-h-[420px] overflow-y-auto">
                      {carregandoNotificacoes ? (
                        <div className="flex items-center justify-center gap-2 px-4 py-10 text-sm text-muted-foreground">
                          <RefreshCw className="size-4 animate-spin" />
                          Carregando...
                        </div>
                      ) : notificacoes.length === 0 ? (
                        <div className="px-4 py-10 text-center">
                          <Bell className="mx-auto mb-2 size-7 text-muted-foreground/60" />
                          <div className="text-sm font-medium">
                            Nenhuma notificação
                          </div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            Novos avisos aparecerão aqui.
                          </div>
                        </div>
                      ) : (
                        notificacoes.map((notificacao) => (
                          <button
                            key={
                              notificacao.id_notificacao
                            }
                            type="button"
                            onClick={() =>
                              void abrirNotificacao(
                                notificacao,
                              )
                            }
                            className={cn(
                              "flex w-full gap-3 border-b border-border px-4 py-3 text-left transition-colors last:border-b-0 hover:bg-muted",
                              !notificacao.lida &&
                                "bg-primary/5",
                            )}
                          >
                            <span
                              className={cn(
                                "mt-1.5 size-2 shrink-0 rounded-full",
                                notificacao.prioridade ===
                                  "CRITICA"
                                  ? "bg-red-500"
                                  : notificacao.prioridade ===
                                      "ALTA"
                                    ? "bg-amber-500"
                                    : notificacao.prioridade ===
                                        "MEDIA"
                                      ? "bg-blue-500"
                                      : "bg-slate-400",
                              )}
                            />

                            <span className="min-w-0 flex-1">
                              <span
                                className={cn(
                                  "block text-sm",
                                  !notificacao.lida
                                    ? "font-semibold"
                                    : "font-medium",
                                )}
                              >
                                {notificacao.titulo}
                              </span>

                              <span className="mt-0.5 block text-xs leading-5 text-muted-foreground">
                                {notificacao.mensagem}
                              </span>

                              <span className="mt-1 block text-[11px] text-muted-foreground">
                                {new Date(
                                  notificacao.data_criacao,
                                ).toLocaleString("pt-BR")}
                              </span>
                            </span>
                          </button>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>

              <div className="relative">
                <button
                  type="button"
                  onClick={() =>
                    setMenuUsuarioAberto(
                      (valor) => !valor,
                    )
                  }
                  aria-label="Abrir menu do usuário"
                  aria-expanded={menuUsuarioAberto}
                  className="flex size-9 items-center justify-center rounded-md text-brand-foreground/80 transition-colors hover:bg-brand-foreground/10 hover:text-brand-foreground"
                >
                  <span
                    aria-hidden="true"
                    className="flex size-8 items-center justify-center rounded-full bg-white text-xs font-semibold text-primary shadow-sm"
                  >
                    {iniciaisUsuario}
                  </span>
                </button>

                {menuUsuarioAberto && (
                  <div className="absolute right-0 top-11 z-50 w-64 overflow-hidden rounded-lg border border-border bg-popover text-popover-foreground shadow-lg">
                    <div className="border-b border-border px-4 py-3">
                      <div className="truncate text-sm font-semibold">
                        {usuario?.nome ?? "Usuário"}
                      </div>

                      <div className="mt-0.5 truncate text-xs text-muted-foreground">
                        {usuario?.email ||
                          usuario?.login ||
                          "-"}
                      </div>
                    </div>

                    <div className="p-1.5">
                      {itensAdministrativos.map((item) => {
                        const Icone = item.icone;

                        return item.to ? (
                          <Link
                            key={item.nome}
                            to={item.to}
                            onClick={() =>
                              setMenuUsuarioAberto(false)
                            }
                            className={cn(
                              "flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors hover:bg-muted",
                              item.to === pathname
                                ? "font-medium text-primary"
                                : "text-foreground",
                            )}
                          >
                            <Icone
                              className="size-4"
                              aria-hidden="true"
                            />
                            {item.nome}
                          </Link>
                        ) : null;
                      })}

                      {itensAdministrativos.length > 0 && (
                        <div
                          aria-hidden="true"
                          className="my-1 border-t border-border"
                        />
                      )}

                      {usuario?.id_usuario && !operadorRestrito ? (
                        <Link
                          to="/usuarios/$idUsuario"
                          params={{
                            idUsuario: String(
                              usuario.id_usuario,
                            ),
                          }}
                          onClick={() =>
                            setMenuUsuarioAberto(false)
                          }
                          className="flex w-full items-center rounded-md px-3 py-2 text-sm transition-colors hover:bg-muted"
                        >
                          Minha conta
                        </Link>
                      ) : null}

                      <div
                        aria-hidden="true"
                        className="my-1 border-t border-border"
                      />

                      <button
                        type="button"
                        onClick={sairDoSistema}
                        className="flex w-full items-center rounded-md px-3 py-2 text-left text-sm text-destructive transition-colors hover:bg-muted"
                      >
                        Sair
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </header>

          <main className="min-w-0 flex-1">
            {children}
          </main>
        </div>

        {operadorRestrito &&
        notificacaoSelecionada ? (
          <div
            className="fixed inset-0 z-[80] flex items-center justify-center bg-black/55 p-4 backdrop-blur-[1px]"
            role="presentation"
            onMouseDown={(evento) => {
              if (
                evento.target ===
                evento.currentTarget
              ) {
                setNotificacaoSelecionada(
                  null,
                );
              }
            }}
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="titulo-notificacao-operador"
              className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl border border-border bg-background shadow-2xl"
            >
              <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
                <div className="min-w-0">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span
                      className={cn(
                        "inline-flex rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide",
                        notificacaoSelecionada
                          .prioridade ===
                          "CRITICA"
                          ? "border-red-200 bg-red-50 text-red-700"
                          : notificacaoSelecionada
                                .prioridade ===
                              "ALTA"
                            ? "border-amber-200 bg-amber-50 text-amber-700"
                            : notificacaoSelecionada
                                  .prioridade ===
                                "MEDIA"
                              ? "border-blue-200 bg-blue-50 text-blue-700"
                              : "border-slate-200 bg-slate-50 text-slate-600",
                      )}
                    >
                      {
                        notificacaoSelecionada
                          .prioridade
                      }
                    </span>

                    <span className="text-xs text-muted-foreground">
                      {new Date(
                        notificacaoSelecionada
                          .data_criacao,
                      ).toLocaleString(
                        "pt-BR",
                      )}
                    </span>
                  </div>

                  <h2
                    id="titulo-notificacao-operador"
                    className="text-lg font-bold leading-snug text-primary"
                  >
                    {
                      notificacaoSelecionada
                        .titulo
                    }
                  </h2>
                </div>

                <button
                  type="button"
                  onClick={() =>
                    setNotificacaoSelecionada(
                      null,
                    )
                  }
                  aria-label="Fechar notificacao"
                  title="Fechar"
                  className="flex size-9 shrink-0 items-center justify-center rounded-md text-xl leading-none text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  {"\u00d7"}
                </button>
              </div>

              <div className="space-y-5 px-5 py-5">
                <div className="rounded-lg border border-border bg-muted/30 p-4">
                  <p className="whitespace-pre-line text-sm leading-6 text-foreground">
                    {
                      notificacaoSelecionada
                        .mensagem
                    }
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-x-5 gap-y-4 text-sm">
                  {notificacaoSelecionada
                    .id_inventario ? (
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                        {"Invent\u00e1rio"}
                      </p>

                      <p className="mt-1 font-mono font-semibold text-foreground">
                        #
                        {
                          notificacaoSelecionada
                            .id_inventario
                        }
                      </p>
                    </div>
                  ) : null}

                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                      Tipo
                    </p>

                    <p className="mt-1 font-medium text-foreground">
                      {
                        notificacaoSelecionada
                          .tipo
                      }
                    </p>
                  </div>

                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                      Origem
                    </p>

                    <p className="mt-1 font-medium text-foreground">
                      {notificacaoSelecionada
                        .nome_usuario_ator ||
                        "Sistema"}
                    </p>
                  </div>

                  {notificacaoSelecionada
                    .entidade_tipo ? (
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                        Contexto
                      </p>

                      <p className="mt-1 font-medium text-foreground">
                        {
                          notificacaoSelecionada
                            .entidade_tipo
                        }

                        {notificacaoSelecionada
                          .entidade_id
                          ? ` #${notificacaoSelecionada.entidade_id}`
                          : ""}
                      </p>
                    </div>
                  ) : null}
                </div>
              </div>

              {obterAcaoNotificacaoOperador(
                notificacaoSelecionada,
              ) ? (
                <div className="mx-5 mb-5 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3">
                  <p className="text-[10px] font-bold uppercase tracking-wide text-primary">
                    Acao operacional disponivel
                  </p>

                  <p className="mt-1 text-xs leading-5 text-muted-foreground">
                    Esta notificacao possui uma atividade
                    relacionada a contagem deste inventario.
                  </p>
                </div>
              ) : (
                <div className="mx-5 mb-5 rounded-lg border border-border bg-muted/30 px-4 py-3">
                  <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                    Notificacao informativa
                  </p>

                  <p className="mt-1 text-xs leading-5 text-muted-foreground">
                    Nenhuma acao operacional e necessaria
                    para esta notificacao.
                  </p>
                </div>
              )}

              <div className="flex flex-col-reverse gap-2 border-t border-border bg-muted/20 px-5 py-4 sm:flex-row sm:justify-end">
                <button
                  type="button"
                  onClick={() =>
                    setNotificacaoSelecionada(
                      null,
                    )
                  }
                  className="inline-flex h-10 items-center justify-center rounded-md border border-border bg-background px-4 text-sm font-semibold text-foreground transition-colors hover:bg-muted"
                >
                  Fechar
                </button>

                {obterAcaoNotificacaoOperador(
                  notificacaoSelecionada,
                ) ? (
                  <button
                    type="button"
                    onClick={
                      irParaDestinoNotificacao
                    }
                    className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
                  >
                    {obterAcaoNotificacaoOperador(
                      notificacaoSelecionada,
                    )?.rotulo}
                  </button>
                ) : null}
              </div>
            </div>
          </div>
        ) : null}

        {/* ==================================================
            MENU MOBILE
        ================================================== */}
        <Sheet
          open={menuAberto}
          onOpenChange={setMenuAberto}
        >
          <SheetContent
            side="left"
            className="w-[280px] p-0"
          >
            <SheetTitle className="border-b border-border bg-brand px-4 py-3">
              <span className="flex items-center">
                <img
                  src="/logo-alzarsi.png"
                  alt="Alzarsi Logística"
                  className="h-auto w-[135px] object-contain"
                />
              </span>
            </SheetTitle>

            <div className="overflow-y-auto p-2">
              {itensPrincipais.map((item) => (
                <ItemLateral
                  key={item.nome}
                  item={item}
                  ativo={item.to === pathname}
                  expandido
                  onNavegar={() =>
                    setMenuAberto(false)
                  }
                />
              ))}

            </div>
          </SheetContent>
        </Sheet>
      </div>
    </TooltipProvider>
  );

}
