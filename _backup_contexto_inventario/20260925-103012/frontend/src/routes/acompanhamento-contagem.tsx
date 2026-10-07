import {
  createFileRoute,
  Link,
} from "@tanstack/react-router";
import {
  Activity,
  Clock3,
  Gauge,
  MapPin,
  PackageCheck,
  RefreshCcw,
  ScanLine,
  Users,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  obterInventarioAtual,
  salvarInventarioAtual,
} from "@/lib/inventarioAtual";

import {
  buscarAcompanhamento,
  buscarProdutividade,
  listarInventariosIndicadores,
  type AcompanhamentoOperacional,
  type InventarioIndicadores,
  type ProdutividadeOperacional,
} from "@/services/indicadoresService";

interface AcompanhamentoSearch {
  inventario?: number;
}

export const Route = createFileRoute("/acompanhamento-contagem")({
  head: () => ({
    meta: [{ title: "Acompanhamento da Contagem \u2014 SGI" }],
  }),
  validateSearch: (
    search: Record<string, unknown>,
  ): AcompanhamentoSearch => {
    const valor = Number(
      search["inventario"],
    );

    if (
      Number.isInteger(valor) &&
      valor > 0
    ) {
      return {
        inventario: valor,
      };
    }

    return {};
  },
  component: AcompanhamentoContagemPage,
});

function numero(valor: number | null | undefined, casas = 0) {
  if (valor === null || valor === undefined || Number.isNaN(valor)) {
    return "-";
  }

  return valor.toLocaleString("pt-BR", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  });
}

function percentual(valor: number | null | undefined) {
  return `${numero(valor, 2)}%`;
}

function Card({
  titulo,
  valor,
  detalhe,
  icone,
}: {
  titulo: string;
  valor: string | number;
  detalhe?: string;
  icone?: ReactNode;
}) {
  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {titulo}
          </p>

          <p className="mt-2 text-2xl font-semibold">{valor}</p>

          {detalhe ? (
            <p className="mt-1 text-xs text-muted-foreground">{detalhe}</p>
          ) : null}
        </div>

        {icone ? (
          <div className="rounded-lg bg-muted p-2 text-muted-foreground">
            {icone}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function BarraProgresso({
  titulo,
  processados,
  planejados,
  pendentes,
  percentualValor,
}: {
  titulo: string;
  processados: number;
  planejados: number;
  pendentes: number;
  percentualValor: number;
}) {
  const largura = Math.max(0, Math.min(100, percentualValor || 0));

  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-4">
        <div>
          <p className="font-semibold">{titulo}</p>
          <p className="text-xs text-muted-foreground">
            {numero(processados)} de {numero(planejados)} concluídos
          </p>
        </div>

        <span className="text-xl font-semibold">
          {percentual(percentualValor)}
        </span>
      </div>

      <div className="h-3 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-all"
          style={{ width: `${largura}%` }}
        />
      </div>

      <div className="mt-3 flex justify-between text-xs text-muted-foreground">
        <span>Processados: {numero(processados)}</span>
        <span>Pendentes: {numero(pendentes)}</span>
      </div>
    </div>
  );
}

function AcompanhamentoContagemPage() {
  const {
    inventario: idInventarioUrl,
  } = Route.useSearch();

  const [
    idInventarioContexto,
    setIdInventarioContexto,
  ] = useState<number | null>(
    idInventarioUrl ?? null,
  );

  const idInventario =
    idInventarioUrl ??
    idInventarioContexto;

  const [inventarios, setInventarios] =
    useState<InventarioIndicadores[]>([]);

  const [acompanhamento, setAcompanhamento] =
    useState<AcompanhamentoOperacional | null>(null);

  const [produtividade, setProdutividade] =
    useState<ProdutividadeOperacional | null>(null);

  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const requisicaoAtual = useRef(0);

  const inventarioSelecionado = useMemo(
    () =>
      inventarios.find(
        (item) => item.id_inventario === idInventario,
      ) ?? null,
    [inventarios, idInventario],
  );

  const carregarInventarios = useCallback(async () => {
    const dados =
      await listarInventariosIndicadores();

    const inventariosOrdenados = [...dados].sort(
      (inventarioA, inventarioB) =>
        inventarioB.id_inventario -
        inventarioA.id_inventario,
    );

    setInventarios(inventariosOrdenados);

    if (inventariosOrdenados.length === 0) {
      setAcompanhamento(null);
      setProdutividade(null);

      throw new Error(
        "Nenhum invent?rio est? dispon?vel para acompanhamento.",
      );
    }

    const idInventarioPreferido =
      idInventarioUrl ??
      idInventario ??
      obterInventarioAtual();

    const inventarioPreferido =
      idInventarioPreferido
        ? inventariosOrdenados.find(
            (item) =>
              item.id_inventario ===
              idInventarioPreferido,
          ) ?? null
        : null;

    if (
      idInventarioUrl &&
      !inventarioPreferido
    ) {
      setAcompanhamento(null);
      setProdutividade(null);

      throw new Error(
        "O invent?rio informado n?o foi encontrado ou n?o est? dispon?vel para acompanhamento.",
      );
    }

    const inventarioEncontrado =
      inventarioPreferido ??
      inventariosOrdenados[0]!;

    salvarInventarioAtual(
      inventarioEncontrado.id_inventario,
      inventarioEncontrado.tipo,
    );

    setIdInventarioContexto(
      inventarioEncontrado.id_inventario,
    );

    setErro(null);
  }, [
    idInventario,
    idInventarioUrl,
  ]);

  const carregarAcompanhamento = useCallback(async () => {
    if (!inventarioSelecionado) return;

    const idRequisicao = ++requisicaoAtual.current;

    setCarregando(true);
    setErro(null);
    setAcompanhamento(null);
    setProdutividade(null);

    try {
            const [
        dadosAcompanhamento,
        dadosProdutividade,
      ] = await Promise.all([
        buscarAcompanhamento(
          inventarioSelecionado.id_inventario,
        ),
        buscarProdutividade(
          inventarioSelecionado.id_inventario,
        ),
      ]);

      if (idRequisicao !== requisicaoAtual.current) {
        return;
      }

      setAcompanhamento(dadosAcompanhamento);
      setProdutividade(dadosProdutividade);
    } catch (e) {
      if (idRequisicao !== requisicaoAtual.current) {
        return;
      }

      setErro(
        e instanceof Error
          ? e.message
          : "Falha ao carregar o acompanhamento da contagem.",
      );
    } finally {
      if (idRequisicao === requisicaoAtual.current) {
        setCarregando(false);
      }
    }
  }, [inventarioSelecionado]);

  useEffect(() => {
    void carregarInventarios().catch((e) => {
      setErro(
        e instanceof Error
          ? e.message
          : "Falha ao listar inventários.",
      );
    });
  }, [carregarInventarios]);

  useEffect(() => {
    void carregarAcompanhamento();
  }, [carregarAcompanhamento]);

  return (
    <div className="space-y-6 p-4 md:p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Activity className="h-6 w-6" />
            <h1 className="text-2xl font-bold">
              Acompanhamento da Contagem
            </h1>
          </div>

          <p className="mt-1 text-sm text-muted-foreground">
            Acompanhe o progresso operacional da rodada, volume,
            atividade e produtividade da equipe.
          </p>
        </div>

        {idInventario ? (
          <div className="flex flex-col gap-2 sm:flex-row">
            <button
              type="button"
              onClick={() => void carregarAcompanhamento()}
              disabled={!inventarioSelecionado || carregando}
              className="inline-flex items-center justify-center gap-2 rounded-md border px-3 py-2 text-sm font-medium disabled:opacity-50"
            >
              <RefreshCcw
                className={`h-4 w-4 ${
                  carregando ? "animate-spin" : ""
                }`}
              />
              Atualizar
            </button>
          </div>
        ) : null}
      </div>

      {erro ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          <p>{erro}</p>


        </div>
      ) : null}

      {acompanhamento ? (
        <>
          <section className="space-y-3">
            <div>
              <h2 className="text-lg font-semibold">
                Progresso da rodada
              </h2>
              <p className="text-sm text-muted-foreground">
                Evolução do escopo planejado para a rodada atual.
              </p>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <BarraProgresso
                titulo="Itens"
                processados={
                  acompanhamento.progresso.itens.processados
                }
                planejados={
                  acompanhamento.progresso.itens.planejados
                }
                pendentes={
                  acompanhamento.progresso.itens.pendentes
                }
                percentualValor={
                  acompanhamento.progresso.itens.percentual
                }
              />

              <BarraProgresso
                titulo="Localizações"
                processados={
                  acompanhamento.progresso.localizacoes
                    .concluidas
                }
                planejados={
                  acompanhamento.progresso.localizacoes
                    .planejadas
                }
                pendentes={
                  acompanhamento.progresso.localizacoes
                    .pendentes
                }
                percentualValor={
                  acompanhamento.progresso.localizacoes
                    .percentual
                }
              />
            </div>
          </section>

          {inventarioSelecionado ? (
            <section className="rounded-xl border bg-card p-5 shadow-sm">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-lg font-semibold">
                    {
                      "Acompanhamento por localiza\u00e7\u00e3o"
                    }
                  </h2>

                  <p className="mt-1 text-sm text-muted-foreground">
                    {
                      "Consulte cada endere\u00e7o com filtros, pesquisa e pagina\u00e7\u00e3o."
                    }
                  </p>
                </div>

                <Link
                  to="/acompanhamento-contagem/localizacoes"
                  search={{
                    inventario:
                      inventarioSelecionado.id_inventario,
                  }}
                  className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm transition hover:bg-primary/90"
                >
                  <MapPin className="h-4 w-4" />
                  {"Ver localiza\u00e7\u00f5es"}
                </Link>
              </div>
            </section>
          ) : null}

          <section className="space-y-3">
            <h2 className="text-lg font-semibold">
              Operação
            </h2>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
              <Card
                titulo="Quantidade planejada"
                valor={numero(
                  acompanhamento.volume.quantidade_planejada,
                  2,
                )}
                icone={<PackageCheck className="h-4 w-4" />}
              />

              <Card
                titulo="Quantidade registrada"
                valor={numero(
                  acompanhamento.volume.quantidade_registrada,
                  2,
                )}
                icone={<PackageCheck className="h-4 w-4" />}
              />

              <Card
                titulo="Bipagens"
                valor={numero(
                  acompanhamento.atividade.total_bipagens,
                )}
                icone={<ScanLine className="h-4 w-4" />}
              />

              <Card
                titulo="Operadores identificados"
                valor={numero(
                  produtividade?.qualidade_dado_operador
                    .operadores_identificados ??
                    acompanhamento.atividade
                      .operadores_com_contagem,
                )}
                icone={<Users className="h-4 w-4" />}
              />

              <Card
                titulo="Tempo da rodada"
                valor={acompanhamento.tempo.tempo_formatado}
                detalhe={`Rodada ${acompanhamento.numero_rodada}`}
                icone={<Clock3 className="h-4 w-4" />}
              />

              <Card
                titulo="Localizações concluídas"
                valor={numero(
                  acompanhamento.progresso.localizacoes
                    .concluidas,
                )}
                detalhe={`${percentual(
                  acompanhamento.progresso.localizacoes
                    .percentual,
                )} do planejado`}
                icone={<MapPin className="h-4 w-4" />}
              />
            </div>
          </section>
        </>
      ) : null}

      {produtividade ? (
        <section className="space-y-3">
          <div>
            <h2 className="text-lg font-semibold">
              Produtividade
            </h2>
            <p className="text-sm text-muted-foreground">
              Desempenho calculado sobre o tempo operacional da
              rodada.
            </p>
          </div>

          {produtividade.qualidade_dado_operador
            .possui_bipagens_sem_usuario ? (
            <div
              role="status"
              className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200"
            >
              <p className="font-semibold">
                Dados de operador incompletos
              </p>

              <p className="mt-1">
                Existem{" "}
                {numero(
                  produtividade.qualidade_dado_operador
                    .bipagens_sem_usuario,
                )}{" "}
                {produtividade.qualidade_dado_operador
                  .bipagens_sem_usuario === 1
                  ? "bipagem"
                  : "bipagens"}{" "}
                sem operador identificado. Esses registros permanecem
                no volume e na produtividade, mas {"n\u00e3o"} entram
                no total de operadores identificados.
              </p>
            </div>
          ) : null}

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Card
              titulo="Tempo operacional"
              valor={
                produtividade.tempo.tempo_operacional_formatado
              }
              icone={<Clock3 className="h-4 w-4" />}
            />

            <Card
              titulo="Bipagens/h"
              valor={numero(
                produtividade.produtividade.operacional
                  .bipagens_hora,
                2,
              )}
              icone={<Gauge className="h-4 w-4" />}
            />

            <Card
              titulo="Quantidade/h"
              valor={numero(
                produtividade.produtividade.operacional
                  .quantidade_hora,
                2,
              )}
              icone={<Gauge className="h-4 w-4" />}
            />

            <Card
              titulo="Tempo médio/localização"
              valor={
                produtividade.tempo
                  .tempo_medio_localizacao_formatado
              }
              icone={<MapPin className="h-4 w-4" />}
            />
          </div>

          <div className="space-y-3">
            <div>
              <h3 className="font-semibold text-foreground">
                Produtividade por operador
              </h3>

              <p className="text-sm text-muted-foreground">
                Desempenho individual dos operadores identificados
                na rodada atual.
              </p>
            </div>

            {produtividade.operadores.some(
              (operador) =>
                operador.operador !== "SEM_USUARIO",
            ) ? (
              <div className="overflow-x-auto rounded-xl border bg-card shadow-sm">
                <table className="min-w-full text-sm">
                  <thead className="bg-muted/50 text-left">
                    <tr>
                      <th className="px-4 py-3 font-semibold">
                        Operador
                      </th>

                      <th className="px-4 py-3 text-right font-semibold">
                        Bipagens
                      </th>

                      <th className="px-4 py-3 text-right font-semibold">
                        Quantidade
                      </th>

                      <th className="px-4 py-3 text-right font-semibold">
                        Itens
                      </th>

                      <th className="px-4 py-3 text-right font-semibold">
                        {"Localiza\u00e7\u00f5es"}
                      </th>

                      <th className="px-4 py-3 text-right font-semibold">
                        Tempo ativo
                      </th>

                      <th className="px-4 py-3 text-right font-semibold">
                        Bipagens/h
                      </th>

                      <th className="px-4 py-3 text-right font-semibold">
                        Quantidade/h
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {produtividade.operadores
                      .filter(
                        (operador) =>
                          operador.operador !==
                          "SEM_USUARIO",
                      )
                      .sort(
                        (operadorA, operadorB) =>
                          operadorB.total_bipagens -
                          operadorA.total_bipagens,
                      )
                      .map((operador) => (
                        <tr
                          key={operador.operador}
                          className="border-t border-border"
                        >
                          <td className="whitespace-nowrap px-4 py-3 font-medium">
                            {operador.operador}
                          </td>

                          <td className="px-4 py-3 text-right">
                            {numero(
                              operador.total_bipagens,
                            )}
                          </td>

                          <td className="px-4 py-3 text-right">
                            {numero(
                              operador.quantidade_registrada,
                              2,
                            )}
                          </td>

                          <td className="px-4 py-3 text-right">
                            {numero(
                              operador
                                .itens_distintos_com_bipagem,
                            )}
                          </td>

                          <td className="px-4 py-3 text-right">
                            {numero(
                              operador
                                .localizacoes_com_atividade,
                            )}
                          </td>

                          <td className="whitespace-nowrap px-4 py-3 text-right">
                            {operador.tempo_ativo_formatado}
                          </td>

                          <td className="px-4 py-3 text-right">
                            {numero(
                              operador.bipagens_hora,
                              2,
                            )}
                          </td>

                          <td className="px-4 py-3 text-right">
                            {numero(
                              operador.quantidade_hora,
                              2,
                            )}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="rounded-xl border border-dashed bg-muted/20 p-5 text-sm text-muted-foreground">
                Nenhum operador identificado nesta rodada.
                As bipagens sem {"usu\u00e1rio"} permanecem
                contabilizadas nos indicadores gerais.
              </div>
            )}
          </div>

        </section>
      ) : null}

      {!acompanhamento && !erro && carregando ? (
        <div className="rounded-xl border bg-card p-8 text-center text-sm text-muted-foreground">
          Carregando acompanhamento...
        </div>
      ) : null}


    </div>
  );
}
