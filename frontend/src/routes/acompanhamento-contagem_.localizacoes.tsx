import {
  createFileRoute,
  Link,
} from "@tanstack/react-router";
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  MapPin,
  RefreshCcw,
  Search,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  buscarAcompanhamentoLocalizacoes,
  type AcompanhamentoLocalizacoes,
} from "@/services/indicadoresService";

interface LocalizacoesSearch {
  inventario?: number;
}

type FiltroStatus =
  | "TODAS"
  | "PENDENTE"
  | "EM_ANDAMENTO"
  | "CONCLUIDA";

export const Route = createFileRoute(
  "/acompanhamento-contagem_/localizacoes",
)({
  head: () => ({
    meta: [
      {
        title:
          "Acompanhamento por localiza\u00e7\u00e3o \u2014 SGI",
      },
    ],
  }),

  validateSearch: (
    search: Record<string, unknown>,
  ): LocalizacoesSearch => {
    const idInventario = Number(
      search["inventario"],
    );

    return Number.isSafeInteger(idInventario) &&
      idInventario > 0
      ? { inventario: idInventario }
      : {};
  },

  component: AcompanhamentoLocalizacoesPage,
});

function numero(
  valor: number | null | undefined,
  casas = 0,
) {
  if (
    valor === null ||
    valor === undefined ||
    Number.isNaN(valor)
  ) {
    return "-";
  }

  return valor.toLocaleString("pt-BR", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  });
}

function AcompanhamentoLocalizacoesPage() {
  const { inventario: idInventario } =
    Route.useSearch();

  const [dados, setDados] =
    useState<AcompanhamentoLocalizacoes | null>(null);

  const [filtroStatus, setFiltroStatus] =
    useState<FiltroStatus>("TODAS");

  const [pesquisa, setPesquisa] = useState("");
  const [paginaAtual, setPaginaAtual] = useState(1);
  const [tamanhoPagina, setTamanhoPagina] = useState(25);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    if (!idInventario) {
      setDados(null);
      return;
    }

    setCarregando(true);
    setErro(null);

    try {
      const resposta =
        await buscarAcompanhamentoLocalizacoes(
          idInventario,
        );

      setDados(resposta);
    } catch (erroCarregamento) {
      setErro(
        erroCarregamento instanceof Error
          ? erroCarregamento.message
          : "N\u00e3o foi poss\u00edvel carregar as localiza\u00e7\u00f5es.",
      );
    } finally {
      setCarregando(false);
    }
  }, [idInventario]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  useEffect(() => {
    setPaginaAtual(1);
  }, [
    filtroStatus,
    pesquisa,
    tamanhoPagina,
    idInventario,
  ]);

  const localizacoesFiltradas = useMemo(() => {
    const termo = pesquisa
      .trim()
      .toLocaleUpperCase("pt-BR");

    return (
      dados?.localizacoes.filter((item) => {
        const atendeStatus =
          filtroStatus === "TODAS" ||
          item.status === filtroStatus;

        const atendePesquisa =
          !termo ||
          item.localizacao
            .toLocaleUpperCase("pt-BR")
            .includes(termo);

        return atendeStatus && atendePesquisa;
      }) ?? []
    );
  }, [dados, filtroStatus, pesquisa]);

  const totalPaginas = Math.max(
    1,
    Math.ceil(
      localizacoesFiltradas.length /
        tamanhoPagina,
    ),
  );

  const paginaSegura = Math.min(
    paginaAtual,
    totalPaginas,
  );

  const indiceInicial =
    (paginaSegura - 1) * tamanhoPagina;

  const localizacoesPagina =
    localizacoesFiltradas.slice(
      indiceInicial,
      indiceInicial + tamanhoPagina,
    );

  const primeiroRegistro =
    localizacoesFiltradas.length === 0
      ? 0
      : indiceInicial + 1;

  const ultimoRegistro = Math.min(
    indiceInicial + tamanhoPagina,
    localizacoesFiltradas.length,
  );

  const cards: Array<{
    status: FiltroStatus;
    titulo: string;
    valor: number;
    cor: string;
  }> = [
    {
      status: "TODAS",
      titulo: "Todos os status",
      valor:
        dados?.resumo.localizacoes_planejadas ?? 0,
      cor: "ring-primary",
    },
    {
      status: "PENDENTE",
      titulo: "Pendentes",
      valor:
        dados?.resumo.localizacoes_pendentes ?? 0,
      cor: "ring-amber-500",
    },
    {
      status: "EM_ANDAMENTO",
      titulo: "Em andamento",
      valor:
        dados?.resumo.localizacoes_em_andamento ?? 0,
      cor: "ring-sky-500",
    },
    {
      status: "CONCLUIDA",
      titulo: "Conclu\u00eddas",
      valor:
        dados?.resumo.localizacoes_concluidas ?? 0,
      cor: "ring-emerald-500",
    },
  ];

  if (!idInventario) {
    return (
      <main className="mx-auto max-w-5xl space-y-5 p-4 md:p-6">
        <Link
          to="/acompanhamento-contagem"
          search={{}}
          className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
        >
          <ArrowLeft className="h-4 w-4" />
          Voltar
        </Link>

        <div className="rounded-xl border border-dashed p-8 text-center">
          <h1 className="text-xl font-semibold">
            {
              "Nenhum invent\u00e1rio selecionado"
            }
          </h1>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-[1600px] space-y-6 p-4 md:p-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link
            to="/acompanhamento-contagem"
            search={{ inventario: idInventario }}
            className="mb-3 inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
          >
            <ArrowLeft className="h-4 w-4" />
            Voltar ao acompanhamento
          </Link>

          <h1 className="text-2xl font-semibold tracking-tight">
            {
              "Acompanhamento por localiza\u00e7\u00e3o"
            }
          </h1>

          <p className="mt-1 text-sm text-muted-foreground">
            {dados
              ? `${dados.codigo_inventario} \u2022 Rodada ${dados.numero_rodada}`
              : `Invent\u00e1rio ${idInventario}`}
          </p>
        </div>

        <button
          type="button"
          onClick={() => void carregar()}
          disabled={carregando}
          className="inline-flex h-10 items-center gap-2 rounded-md border bg-background px-4 text-sm font-medium shadow-sm hover:bg-muted disabled:opacity-50"
        >
          <RefreshCcw
            className={`h-4 w-4 ${
              carregando ? "animate-spin" : ""
            }`}
          />
          Atualizar
        </button>
      </header>

      {erro ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {erro}
        </div>
      ) : null}

      {carregando && !dados ? (
        <div className="rounded-xl border p-8 text-center text-sm text-muted-foreground">
          {
            "Carregando localiza\u00e7\u00f5es..."
          }
        </div>
      ) : null}

      {dados ? (
        <>
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {cards.map((card) => (
              <button
                key={card.status}
                type="button"
                aria-pressed={
                  filtroStatus === card.status
                }
                onClick={() =>
                  setFiltroStatus(card.status)
                }
                className={`rounded-xl border bg-card p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${
                  filtroStatus === card.status
                    ? `ring-2 ${card.cor} ring-offset-2 ring-offset-background`
                    : ""
                }`}
              >
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {card.titulo}
                </p>

                <p className="mt-2 text-2xl font-semibold">
                  {numero(card.valor)}
                </p>
              </button>
            ))}
          </section>

          <section className="space-y-4 rounded-xl border bg-card p-4 shadow-sm">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="relative w-full lg:max-w-md">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />

                <input
                  type="search"
                  value={pesquisa}
                  onChange={(evento) =>
                    setPesquisa(evento.target.value)
                  }
                  placeholder={
                    "Pesquisar localiza\u00e7\u00e3o"
                  }
                  className="h-10 w-full rounded-md border bg-background pl-10 pr-3 text-sm outline-none focus:ring-2 focus:ring-primary"
                />
              </div>

              <label className="flex items-center gap-2 text-sm">
                <span className="text-muted-foreground">
                  {"Linhas por p\u00e1gina"}
                </span>

                <select
                  value={tamanhoPagina}
                  onChange={(evento) =>
                    setTamanhoPagina(
                      Number(evento.target.value),
                    )
                  }
                  className="h-10 rounded-md border bg-background px-3"
                >
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </label>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span className="text-muted-foreground">
                Exibindo{" "}
                <strong className="text-foreground">
                  {numero(primeiroRegistro)}
                  {"\u2013"}
                  {numero(ultimoRegistro)}
                </strong>{" "}
                de{" "}
                <strong className="text-foreground">
                  {numero(
                    localizacoesFiltradas.length,
                  )}
                </strong>{" "}
                {"localiza\u00e7\u00f5es"}
              </span>

              {filtroStatus !== "TODAS" ||
              pesquisa.trim() ? (
                <button
                  type="button"
                  onClick={() => {
                    setFiltroStatus("TODAS");
                    setPesquisa("");
                  }}
                  className="font-medium text-primary hover:underline"
                >
                  Limpar filtros
                </button>
              ) : null}
            </div>

            {localizacoesPagina.length > 0 ? (
              <div className="overflow-x-auto rounded-lg border">
                <table className="min-w-full text-sm">
                  <thead className="bg-muted/50 text-left">
                    <tr>
                      <th className="px-4 py-3">
                        {"Localiza\u00e7\u00e3o"}
                      </th>
                      <th className="px-4 py-3">
                        Status
                      </th>
                      <th className="px-4 py-3">
                        Progresso
                      </th>
                      <th className="px-4 py-3 text-right">
                        Bipagens
                      </th>
                      <th className="px-4 py-3 text-right">
                        Quantidade
                      </th>
                      <th className="px-4 py-3">
                        Operadores
                      </th>
                      <th className="px-4 py-3 text-right">
                        Sem atividade
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {localizacoesPagina.map((item) => (
                      <tr
                        key={item.localizacao}
                        className="border-t"
                      >
                        <td className="whitespace-nowrap px-4 py-3 font-semibold">
                          <span className="inline-flex items-center gap-2">
                            <MapPin className="h-4 w-4 text-muted-foreground" />
                            {item.localizacao}
                          </span>
                        </td>

                        <td className="px-4 py-3">
                          <span
                            className={
                              item.status === "CONCLUIDA"
                                ? "rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-800"
                                : item.status ===
                                    "EM_ANDAMENTO"
                                  ? "rounded-full bg-sky-100 px-2.5 py-1 text-xs font-semibold text-sky-800"
                                  : "rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-800"
                            }
                          >
                            {item.status === "CONCLUIDA"
                              ? "Conclu\u00edda"
                              : item.status ===
                                  "EM_ANDAMENTO"
                                ? "Em andamento"
                                : "Pendente"}
                          </span>
                        </td>

                        <td className="min-w-52 px-4 py-3">
                          <div className="flex justify-between gap-3 text-xs">
                            <span>
                              {numero(
                                item.itens_processados,
                              )}{" "}
                              de{" "}
                              {numero(
                                item.itens_planejados,
                              )}
                            </span>

                            <strong>
                              {numero(item.percentual, 2)}%
                            </strong>
                          </div>

                          <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
                            <div
                              className="h-full rounded-full bg-primary"
                              style={{
                                width: `${Math.max(
                                  0,
                                  Math.min(
                                    100,
                                    item.percentual,
                                  ),
                                )}%`,
                              }}
                            />
                          </div>
                        </td>

                        <td className="px-4 py-3 text-right">
                          {numero(item.total_bipagens)}
                        </td>

                        <td className="px-4 py-3 text-right">
                          {numero(
                            item.quantidade_registrada,
                            2,
                          )}
                        </td>

                        <td className="px-4 py-3">
                          {item.operadores.length
                            ? item.operadores.join(", ")
                            : "N\u00e3o identificado"}
                        </td>

                        <td className="whitespace-nowrap px-4 py-3 text-right">
                          {item.status === "CONCLUIDA"
                            ? "-"
                            : item
                                .tempo_sem_atividade_formatado}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
                {
                  "Nenhuma localiza\u00e7\u00e3o encontrada."
                }
              </div>
            )}

            <footer className="flex flex-col gap-3 border-t pt-4 sm:flex-row sm:items-center sm:justify-between">
              <span className="text-sm text-muted-foreground">
                {"P\u00e1gina"} {paginaSegura} de {totalPaginas}
              </span>

              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={paginaSegura <= 1}
                  onClick={() =>
                    setPaginaAtual(
                      Math.max(1, paginaSegura - 1),
                    )
                  }
                  className="inline-flex h-9 items-center gap-1 rounded-md border px-3 text-sm font-medium hover:bg-muted disabled:opacity-40"
                >
                  <ChevronLeft className="h-4 w-4" />
                  Anterior
                </button>

                <button
                  type="button"
                  disabled={
                    paginaSegura >= totalPaginas
                  }
                  onClick={() =>
                    setPaginaAtual(
                      Math.min(
                        totalPaginas,
                        paginaSegura + 1,
                      ),
                    )
                  }
                  className="inline-flex h-9 items-center gap-1 rounded-md border px-3 text-sm font-medium hover:bg-muted disabled:opacity-40"
                >
                  {"Pr\u00f3xima"}
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </footer>
          </section>
        </>
      ) : null}
    </main>
  );
}
