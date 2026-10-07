import { createFileRoute, Link } from "@tanstack/react-router";
import {
  AlertTriangle,
  BarChart3,
  BellRing,
  Boxes,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Clock3,
  LoaderCircle,
  RefreshCcw,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import { Button } from "@/components/ui/button";
import { obterUsuarioSalvo } from "@/services/authService";
import { listarInventarios } from "@/services/inventarioService";
import {
  listarNotificacoes,
  type Notificacao,
} from "@/services/notificationService";
import type { InventarioResumo } from "@/types/inventory";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      {
        title: "Central de Controle — SGI",
      },
    ],
  }),
  component: Index,
});

const STATUS_TERMINAIS = new Set([
  "FINALIZADO",
  "CANCELADO",
]);

const PERMISSOES_GERENCIAIS = [
  "ANALISE_VISUALIZAR",
  "GESTOR_DECIDIR",
  "INVENTARIO_CRIAR",
  "INVENTARIO_FINALIZAR",
  "RODADA_GERAR",
  "USUARIO_GERENCIAR",
];

function normalizar(valor: string | null | undefined) {
  return String(valor ?? "")
    .trim()
    .toUpperCase();
}

function formatarData(
  valor: string | null | undefined,
) {
  if (!valor) return "Não informado";

  const data = new Date(valor);

  if (Number.isNaN(data.getTime())) {
    return "Não informado";
  }

  return data.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function classesStatus(status: string) {
  const valor = normalizar(status);

  if (
    valor === "ABERTO" ||
    valor === "EM ANDAMENTO" ||
    valor === "EM_CONTAGEM"
  ) {
    return "border-blue-200 bg-blue-50 text-blue-700";
  }

  if (
    valor === "AGUARDANDO_GESTOR" ||
    valor === "EM_ANALISE" ||
    valor === "EM ANÁLISE"
  ) {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }

  if (valor === "FINALIZADO") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }

  if (valor === "CANCELADO") {
    return "border-red-200 bg-red-50 text-red-700";
  }

  return "border-border bg-muted text-muted-foreground";
}

function classesPrioridade(
  prioridade: Notificacao["prioridade"],
) {
  if (prioridade === "CRITICA") {
    return "border-red-200 bg-red-50 text-red-700";
  }

  if (prioridade === "ALTA") {
    return "border-orange-200 bg-orange-50 text-orange-700";
  }

  if (prioridade === "MEDIA") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }

  return "border-blue-200 bg-blue-50 text-blue-700";
}

function Index() {
  const usuario = useMemo(
    () => obterUsuarioSalvo(),
    [],
  );

  const permissoes = useMemo(
    () =>
      new Set(
        (usuario?.permissoes ?? [])
          .map((permissao) =>
            typeof permissao === "string"
              ? permissao
              : permissao.codigo,
          )
          .filter(Boolean),
      ),
    [usuario],
  );

  const acessoGerencial = useMemo(
    () =>
      PERMISSOES_GERENCIAIS.some((permissao) =>
        permissoes.has(permissao),
      ),
    [permissoes],
  );

  const [inventarios, setInventarios] = useState<
    InventarioResumo[]
  >([]);

  const [notificacoes, setNotificacoes] = useState<
    Notificacao[]
  >([]);

  const [carregando, setCarregando] =
    useState(true);

  const [atualizando, setAtualizando] =
    useState(false);

  const [erro, setErro] = useState<
    string | null
  >(null);

  useEffect(() => {
    if (
      !acessoGerencial &&
      typeof window !== "undefined"
    ) {
      window.location.replace("/operador");
    }
  }, [acessoGerencial]);

  const carregarDados = useCallback(
    async (manual = false) => {
      if (!acessoGerencial) return;

      if (manual) {
        setAtualizando(true);
      } else {
        setCarregando(true);
      }

      setErro(null);

      try {
        const [
          respostaInventarios,
          respostaNotificacoes,
        ] = await Promise.allSettled([
          listarInventarios(),
          listarNotificacoes(),
        ]);

        if (
          respostaInventarios.status ===
          "fulfilled"
        ) {
          setInventarios(
            respostaInventarios.value,
          );
        }

        if (
          respostaNotificacoes.status ===
          "fulfilled"
        ) {
          setNotificacoes(
            respostaNotificacoes.value
              .notificacoes,
          );
        }

        if (
          respostaInventarios.status ===
            "rejected" &&
          respostaNotificacoes.status ===
            "rejected"
        ) {
          throw new Error(
            "Não foi possível carregar os dados da Central de Controle.",
          );
        }

        if (
          respostaInventarios.status ===
          "rejected"
        ) {
          setErro(
            "As notificações foram carregadas, mas não foi possível consultar os inventários.",
          );
        } else if (
          respostaNotificacoes.status ===
          "rejected"
        ) {
          setErro(
            "Os inventários foram carregados, mas não foi possível consultar as notificações.",
          );
        }
      } catch (erroCarregamento) {
        setErro(
          erroCarregamento instanceof Error
            ? erroCarregamento.message
            : "Não foi possível carregar a Central de Controle.",
        );
      } finally {
        setCarregando(false);
        setAtualizando(false);
      }
    },
    [acessoGerencial],
  );

  useEffect(() => {
    void carregarDados();
  }, [carregarDados]);

  const inventariosAbertos = useMemo(
    () =>
      inventarios
        .filter(
          (inventario) =>
            !STATUS_TERMINAIS.has(
              normalizar(inventario.status),
            ),
        )
        .sort(
          (a, b) =>
            b.id_inventario -
            a.id_inventario,
        ),
    [inventarios],
  );

  const aguardandoGestor = useMemo(
    () =>
      inventariosAbertos.filter(
        (inventario) =>
          inventario.em_analise_gestor,
      ),
    [inventariosAbertos],
  );

  const emRecontagem = useMemo(
    () =>
      inventariosAbertos.filter(
        (inventario) =>
          inventario.rodada_atual > 1,
      ),
    [inventariosAbertos],
  );

  const oficiaisAbertos = useMemo(
    () =>
      inventariosAbertos.filter(
        (inventario) =>
          inventario.tipo === "OFICIAL",
      ).length,
    [inventariosAbertos],
  );

  const rotativosAbertos = useMemo(
    () =>
      inventariosAbertos.filter(
        (inventario) =>
          inventario.tipo === "ROTATIVO",
      ).length,
    [inventariosAbertos],
  );

  const notificacoesNaoLidas = useMemo(
    () =>
      notificacoes.filter(
        (notificacao) =>
          !notificacao.lida,
      ).length,
    [notificacoes],
  );

  const notificacoesRecentes = useMemo(
    () =>
      [...notificacoes]
        .sort(
          (a, b) =>
            new Date(
              b.data_criacao,
            ).getTime() -
            new Date(
              a.data_criacao,
            ).getTime(),
        )
        .slice(0, 5),
    [notificacoes],
  );

  if (!acessoGerencial) {
    return (
      <div className="flex min-h-[55vh] items-center justify-center">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <LoaderCircle
            className="size-4 animate-spin"
            aria-hidden="true"
          />
          Direcionando para a área de contagem...
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6 p-3 sm:p-5 lg:p-6">
      <section className="flex flex-col gap-4 rounded-xl border border-border bg-card p-5 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck
              className="size-6 text-primary"
              aria-hidden="true"
            />

            <h1 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl">
              Central de Controle
            </h1>
          </div>

          <p className="mt-1 text-sm text-muted-foreground">
            Olá,{" "}
            <span className="font-medium text-foreground">
              {usuario?.nome ?? "Usuário"}
            </span>
            . Acompanhe os inventários e as pendências que exigem atenção.
          </p>
        </div>

        <Button
          type="button"
          variant="outline"
          onClick={() =>
            void carregarDados(true)
          }
          disabled={atualizando}
        >
          <RefreshCcw
            className={
              atualizando
                ? "size-4 animate-spin"
                : "size-4"
            }
            aria-hidden="true"
          />
          Atualizar
        </Button>
      </section>

      {erro ? (
        <div
          className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
          role="alert"
        >
          <AlertTriangle
            className="mt-0.5 size-5 shrink-0"
            aria-hidden="true"
          />
          <p>{erro}</p>
        </div>
      ) : null}

      {carregando ? (
        <div className="flex min-h-64 items-center justify-center rounded-xl border bg-card">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <LoaderCircle
              className="size-5 animate-spin"
              aria-hidden="true"
            />
            Carregando Central de Controle...
          </div>
        </div>
      ) : (
        <>
          <section
            className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
            aria-label="Resumo operacional"
          >
            <Link
              to="/controle-inventarios"
              className="group rounded-xl border bg-card p-4 shadow-sm transition hover:border-primary/40 hover:shadow-md"
            >
              <div className="flex items-start justify-between">
                <div className="rounded-lg bg-blue-50 p-2 text-blue-700">
                  <Boxes
                    className="size-5"
                    aria-hidden="true"
                  />
                </div>

                <ChevronRight
                  className="size-4 text-muted-foreground transition-transform group-hover:translate-x-1"
                  aria-hidden="true"
                />
              </div>

              <p className="mt-4 text-3xl font-bold">
                {inventariosAbertos.length}
              </p>

              <p className="text-sm font-medium">
                Inventários em andamento
              </p>

              <p className="mt-1 text-xs text-muted-foreground">
                {rotativosAbertos} rotativo(s) e{" "}
                {oficiaisAbertos} oficial(is)
              </p>
            </Link>

            <Link
              to="/analise-gestor"
              className="group rounded-xl border bg-card p-4 shadow-sm transition hover:border-primary/40 hover:shadow-md"
            >
              <div className="flex items-start justify-between">
                <div className="rounded-lg bg-amber-50 p-2 text-amber-700">
                  <Clock3
                    className="size-5"
                    aria-hidden="true"
                  />
                </div>

                <ChevronRight
                  className="size-4 text-muted-foreground transition-transform group-hover:translate-x-1"
                  aria-hidden="true"
                />
              </div>

              <p className="mt-4 text-3xl font-bold">
                {aguardandoGestor.length}
              </p>

              <p className="text-sm font-medium">
                Aguardando decisão
              </p>

              <p className="mt-1 text-xs text-muted-foreground">
                Encaminhados para análise do gestor
              </p>
            </Link>

            <Link
              to="/recontagem"
              className="group rounded-xl border bg-card p-4 shadow-sm transition hover:border-primary/40 hover:shadow-md"
            >
              <div className="flex items-start justify-between">
                <div className="rounded-lg bg-violet-50 p-2 text-violet-700">
                  <RotateCcw
                    className="size-5"
                    aria-hidden="true"
                  />
                </div>

                <ChevronRight
                  className="size-4 text-muted-foreground transition-transform group-hover:translate-x-1"
                  aria-hidden="true"
                />
              </div>

              <p className="mt-4 text-3xl font-bold">
                {emRecontagem.length}
              </p>

              <p className="text-sm font-medium">
                Em recontagem
              </p>

              <p className="mt-1 text-xs text-muted-foreground">
                Inventários atualmente na R2 ou superior
              </p>
            </Link>

            <div className="rounded-xl border bg-card p-4 shadow-sm">
              <div className="flex items-start justify-between">
                <div className="rounded-lg bg-red-50 p-2 text-red-700">
                  <BellRing
                    className="size-5"
                    aria-hidden="true"
                  />
                </div>

                {notificacoesNaoLidas === 0 ? (
                  <CheckCircle2
                    className="size-4 text-emerald-600"
                    aria-hidden="true"
                  />
                ) : null}
              </div>

              <p className="mt-4 text-3xl font-bold">
                {notificacoesNaoLidas}
              </p>

              <p className="text-sm font-medium">
                Notificações não lidas
              </p>

              <p className="mt-1 text-xs text-muted-foreground">
                Avisos e eventos que ainda não foram consultados
              </p>
            </div>
          </section>

          <section className="grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(320px,1fr)]">
            <div className="overflow-hidden rounded-xl border bg-card shadow-sm">
              <div className="flex items-center justify-between border-b px-4 py-4 sm:px-5">
                <div>
                  <h2 className="font-semibold">
                    Inventários em andamento
                  </h2>

                  <p className="mt-0.5 text-xs text-muted-foreground">
                    Acesse o inventário para consultar escopo, rodadas e decisões.
                  </p>
                </div>

                <Button
                  asChild
                  variant="ghost"
                  size="sm"
                >
                  <Link to="/controle-inventarios">
                    Ver todos
                    <ChevronRight
                      className="size-4"
                      aria-hidden="true"
                    />
                  </Link>
                </Button>
              </div>

              {inventariosAbertos.length === 0 ? (
                <div className="p-8 text-center">
                  <CheckCircle2
                    className="mx-auto size-9 text-emerald-600"
                    aria-hidden="true"
                  />

                  <p className="mt-3 font-medium">
                    Nenhum inventário em andamento
                  </p>

                  <p className="mt-1 text-sm text-muted-foreground">
                    Não existem inventários abertos neste momento.
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[720px] text-left text-sm">
                    <thead className="bg-muted/40 text-xs uppercase text-muted-foreground">
                      <tr>
                        <th className="px-4 py-3 font-medium sm:px-5">
                          Inventário
                        </th>
                        <th className="px-4 py-3 font-medium">
                          Cliente
                        </th>
                        <th className="px-4 py-3 font-medium">
                          Tipo
                        </th>
                        <th className="px-4 py-3 font-medium">
                          Rodada
                        </th>
                        <th className="px-4 py-3 font-medium">
                          Status
                        </th>
                        <th className="px-4 py-3 text-right font-medium sm:px-5">
                          Ação
                        </th>
                      </tr>
                    </thead>

                    <tbody className="divide-y">
                      {inventariosAbertos
                        .slice(0, 8)
                        .map((inventario) => (
                          <tr
                            key={
                              inventario.id_inventario
                            }
                            className="transition-colors hover:bg-muted/30"
                          >
                            <td className="px-4 py-3 sm:px-5">
                              <p className="font-medium">
                                {
                                  inventario.codigo_inventario
                                }
                              </p>

                              <p className="text-xs text-muted-foreground">
                                ID{" "}
                                {
                                  inventario.id_inventario
                                }
                              </p>
                            </td>

                            <td className="px-4 py-3">
                              <p className="font-medium">
                                {inventario.cliente}
                              </p>

                              <p className="text-xs text-muted-foreground">
                                {inventario.armazem}
                              </p>
                            </td>

                            <td className="px-4 py-3">
                              {inventario.tipo}
                            </td>

                            <td className="px-4 py-3">
                              R
                              {
                                inventario.rodada_atual
                              }
                            </td>

                            <td className="px-4 py-3">
                              <span
                                className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${classesStatus(
                                  inventario.em_analise_gestor
                                    ? "EM_ANALISE"
                                    : inventario.status,
                                )}`}
                              >
                                {inventario.em_analise_gestor
                                  ? "Aguardando gestor"
                                  : inventario.status}
                              </span>
                            </td>

                            <td className="px-4 py-3 text-right sm:px-5">
                              <Button
                                asChild
                                variant="outline"
                                size="sm"
                              >
                                <Link
                                  to="/inventarios/$idInventario"
                                  params={{
                                    idInventario:
                                      String(
                                        inventario.id_inventario,
                                      ),
                                  }}
                                >
                                  Abrir
                                </Link>
                              </Button>
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="overflow-hidden rounded-xl border bg-card shadow-sm">
              <div className="border-b px-4 py-4 sm:px-5">
                <h2 className="font-semibold">
                  Notificações recentes
                </h2>

                <p className="mt-0.5 text-xs text-muted-foreground">
                  Últimos avisos direcionados ao seu usuário.
                </p>
              </div>

              {notificacoesRecentes.length === 0 ? (
                <div className="p-8 text-center">
                  <BellRing
                    className="mx-auto size-9 text-muted-foreground"
                    aria-hidden="true"
                  />

                  <p className="mt-3 font-medium">
                    Nenhuma notificação
                  </p>

                  <p className="mt-1 text-sm text-muted-foreground">
                    Os novos avisos aparecerão aqui.
                  </p>
                </div>
              ) : (
                <div className="divide-y">
                  {notificacoesRecentes.map(
                    (notificacao) => {
                      const conteudo = (
                        <>
                          <div className="flex items-start justify-between gap-3">
                            <p className="text-sm font-medium leading-snug">
                              {
                                notificacao.titulo
                              }
                            </p>

                            {!notificacao.lida ? (
                              <span
                                className="mt-1 size-2 shrink-0 rounded-full bg-primary"
                                aria-label="Não lida"
                              />
                            ) : null}
                          </div>

                          <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                            {
                              notificacao.mensagem
                            }
                          </p>

                          <div className="mt-2 flex flex-wrap items-center gap-2">
                            <span
                              className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${classesPrioridade(
                                notificacao.prioridade,
                              )}`}
                            >
                              {
                                notificacao.prioridade
                              }
                            </span>

                            <span className="text-[11px] text-muted-foreground">
                              {formatarData(
                                notificacao.data_criacao,
                              )}
                            </span>
                          </div>
                        </>
                      );

                      if (notificacao.url) {
                        return (
                          <a
                            key={
                              notificacao.id_notificacao
                            }
                            href={notificacao.url}
                            className="block p-4 transition-colors hover:bg-muted/40 sm:px-5"
                          >
                            {conteudo}
                          </a>
                        );
                      }

                      return (
                        <div
                          key={
                            notificacao.id_notificacao
                          }
                          className="p-4 sm:px-5"
                        >
                          {conteudo}
                        </div>
                      );
                    },
                  )}
                </div>
              )}
            </div>
          </section>

          <section className="rounded-xl border bg-card p-5 shadow-sm">
            <div className="mb-4">
              <h2 className="font-semibold">
                Ações rápidas
              </h2>

              <p className="mt-0.5 text-xs text-muted-foreground">
                Acesse as principais áreas gerenciais do SGI.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Button
                asChild
                variant="outline"
                className="h-auto justify-start gap-3 p-4"
              >
                <Link to="/controle-inventarios">
                  <ClipboardList
                    className="size-5 text-primary"
                    aria-hidden="true"
                  />

                  <span className="text-left">
                    <span className="block">
                      Controle
                    </span>
                    <span className="block text-xs font-normal text-muted-foreground">
                      Criar e consultar inventários
                    </span>
                  </span>
                </Link>
              </Button>

              <Button
                asChild
                variant="outline"
                className="h-auto justify-start gap-3 p-4"
              >
                <Link to="/analise-gestor">
                  <ShieldCheck
                    className="size-5 text-primary"
                    aria-hidden="true"
                  />

                  <span className="text-left">
                    <span className="block">
                      Decisões
                    </span>
                    <span className="block text-xs font-normal text-muted-foreground">
                      Analisar divergências
                    </span>
                  </span>
                </Link>
              </Button>

              <Button
                asChild
                variant="outline"
                className="h-auto justify-start gap-3 p-4"
              >
                <Link to="/indicadores">
                  <BarChart3
                    className="size-5 text-primary"
                    aria-hidden="true"
                  />

                  <span className="text-left">
                    <span className="block">
                      Indicadores
                    </span>
                    <span className="block text-xs font-normal text-muted-foreground">
                      Acompanhar desempenho
                    </span>
                  </span>
                </Link>
              </Button>

              <Button
                asChild
                variant="outline"
                className="h-auto justify-start gap-3 p-4"
              >
                <Link
                  to="/historico"
                  search={{ aba: "tratativas" }}
                >
                  <AlertTriangle
                    className="size-5 text-primary"
                    aria-hidden="true"
                  />

                  <span className="text-left">
                    <span className="block">
                      Tratativas
                    </span>
                    <span className="block text-xs font-normal text-muted-foreground">
                      Consultar planos de ação
                    </span>
                  </span>
                </Link>
              </Button>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
