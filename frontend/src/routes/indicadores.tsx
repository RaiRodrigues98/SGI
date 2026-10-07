import { createFileRoute } from "@tanstack/react-router";
import {
  AlertTriangle,
  BarChart3,
  Gauge,
  PackageCheck,
  RefreshCcw,
  ShieldAlert,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  limparInventarioAtual,
  obterInventarioAtual,
  salvarInventarioAtual,
} from "@/lib/inventarioAtual";

import {
  buscarAcompanhamento,
  buscarAcompanhamentoLocalizacoes,
  buscarPainelRotativo,
  buscarProdutividade,
  buscarTendenciasRotativo,
  listarInventariosIndicadores,
  type AcompanhamentoLocalizacoes,
  type AcompanhamentoOperacional,
  type InventarioIndicadores,
  type PainelRotativo,
  type ProdutividadeOperacional,
  type TendenciasRotativo,
} from "@/services/indicadoresService";

interface IndicadoresSearch {
  inventario?: number;
}

export const Route = createFileRoute("/indicadores")({
  head: () => ({
    meta: [{ title: "Indicadores — SGI" }],
  }),
  validateSearch: (
    search: Record<string, unknown>,
  ): IndicadoresSearch => {
    const idInventario = Number(
      search["inventario"],
    );

    if (
      Number.isInteger(idInventario) &&
      idInventario > 0
    ) {
      return {
        inventario: idInventario,
      };
    }

    return {};
  },
  component: IndicadoresPage,
});

const CORES_GRAFICO = {
  azul: "#2563eb",
  verde: "#16a34a",
  amarelo: "#d97706",
  laranja: "#ea580c",
  vermelho: "#dc2626",
  roxo: "#7c3aed",
  cinza: "#64748b",
  ciano: "#0891b2",
};

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

function percentual(
  valor: number | null | undefined,
) {
  return `${numero(valor, 2)}%`;
}

function textoSeguro(
  valor: string | null | undefined,
  fallback = "-",
) {
  if (valor === null || valor === undefined) {
    return fallback;
  }

  const texto = String(valor).trim();

  if (
    texto === "" ||
    texto.toLowerCase() === "null" ||
    texto.toLowerCase() === "none" ||
    texto.toLowerCase() === "undefined"
  ) {
    return fallback;
  }

  return texto;
}

function Card({
  titulo,
  valor,
  detalhe,
}: {
  titulo: string;
  valor: string | number;
  detalhe?: string;
}) {
  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {titulo}
      </p>

      <p className="mt-2 text-2xl font-semibold">
        {valor}
      </p>

      {detalhe ? (
        <p className="mt-1 text-xs text-muted-foreground">
          {detalhe}
        </p>
      ) : null}
    </div>
  );
}

function Section({
  titulo,
  children,
}: {
  titulo: string;
  children: ReactNode;
}) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">
        {titulo}
      </h2>

      {children}
    </section>
  );
}

function ChartPanel({
  titulo,
  descricao,
  children,
  compacto = false,
}: {
  titulo: string;
  descricao?: string;
  children: ReactNode;
  compacto?: boolean;
}) {
  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <div>
        <h3 className="font-semibold">
          {titulo}
        </h3>

        {descricao ? (
          <p className="mt-1 text-xs text-muted-foreground">
            {descricao}
          </p>
        ) : null}
      </div>

      <div
        className={
          compacto
            ? "mt-4 h-[110px]"
            : "mt-4 h-[300px]"
        }
      >
        {children}
      </div>
    </div>
  );
}

function EmptyChart({
  mensagem,
}: {
  mensagem: string;
}) {
  return (
    <div className="flex h-full items-center justify-center rounded-lg border border-dashed px-4 text-center text-sm text-muted-foreground">
      {mensagem}
    </div>
  );
}

function IndicadoresPage() {
  const {
    inventario: idInventarioUrl,
  } = Route.useSearch();

  const idInventario =
    idInventarioUrl ??
    obterInventarioAtual();

  const [
    inventarioSelecionado,
    setInventarioSelecionado,
  ] = useState<InventarioIndicadores | null>(
    null,
  );

  const [
    acompanhamento,
    setAcompanhamento,
  ] = useState<AcompanhamentoOperacional | null>(
    null,
  );

  const [
    acompanhamentoLocalizacoes,
    setAcompanhamentoLocalizacoes,
  ] = useState<AcompanhamentoLocalizacoes | null>(
    null,
  );

  const [
    produtividade,
    setProdutividade,
  ] = useState<ProdutividadeOperacional | null>(
    null,
  );

  const [
    painel,
    setPainel,
  ] = useState<PainelRotativo | null>(
    null,
  );

  const [
    tendencias,
    setTendencias,
  ] = useState<TendenciasRotativo | null>(
    null,
  );

  const [
    carregando,
    setCarregando,
  ] = useState(false);

  const [
    erro,
    setErro,
  ] = useState<string | null>(
    null,
  );

  const requisicaoIndicadoresAtual =
    useRef(0);

  const limparDadosIndicadores =
    useCallback(() => {
      setAcompanhamento(null);
      setAcompanhamentoLocalizacoes(null);
      setProdutividade(null);
      setPainel(null);
      setTendencias(null);
    }, []);

  const carregarInventarioAtual =
    useCallback(async () => {
      setCarregando(true);
      setErro(null);
      setInventarioSelecionado(null);
      limparDadosIndicadores();

      try {
        const dados =
          await listarInventariosIndicadores();

        if (dados.length === 0) {
          limparInventarioAtual();
          setInventarioSelecionado(null);
          limparDadosIndicadores();
          setErro(null);
          return;
        }

        const inventarioEncontrado =
          dados.find(
            (item) =>
              item.id_inventario ===
              idInventario,
          ) ??
          (!idInventarioUrl
            ? dados[0] ?? null
            : null);

        if (!inventarioEncontrado) {
          throw new Error(
            `O inventário #${idInventario} não está disponível para consulta dos indicadores.`,
          );
        }

        salvarInventarioAtual(
          inventarioEncontrado.id_inventario,
          inventarioEncontrado.tipo,
        );

        setInventarioSelecionado(
          inventarioEncontrado,
        );
      } catch (e) {
        setErro(
          e instanceof Error
            ? e.message
            : "Falha ao carregar o inventário atual.",
        );
      } finally {
        setCarregando(false);
      }
    }, [
      idInventario,
      idInventarioUrl,
      limparDadosIndicadores,
    ]);

  const carregarIndicadores =
    useCallback(async () => {
      if (!inventarioSelecionado) {
        return;
      }

      const idRequisicao =
        ++requisicaoIndicadoresAtual.current;

      const requisicaoAindaAtual = () =>
        idRequisicao ===
        requisicaoIndicadoresAtual.current;

      setCarregando(true);
      setErro(null);
      limparDadosIndicadores();

      try {
        if (
          inventarioSelecionado.tipo ===
          "OFICIAL"
        ) {
          const [
            dadosAcompanhamento,
            dadosLocalizacoes,
            dadosProdutividade,
          ] = await Promise.all([
            buscarAcompanhamento(
              inventarioSelecionado.id_inventario,
            ),
            buscarAcompanhamentoLocalizacoes(
              inventarioSelecionado.id_inventario,
            ),
            buscarProdutividade(
              inventarioSelecionado.id_inventario,
            ),
          ]);

          if (!requisicaoAindaAtual()) {
            return;
          }

          setAcompanhamento(
            dadosAcompanhamento,
          );

          setAcompanhamentoLocalizacoes(
            dadosLocalizacoes,
          );

          setProdutividade(
            dadosProdutividade,
          );

          return;
        }

        if (
          inventarioSelecionado.tipo ===
          "ROTATIVO"
        ) {
          const [
            dadosPainel,
            dadosTendencias,
          ] = await Promise.all([
            buscarPainelRotativo(
              inventarioSelecionado.cliente_id,
              inventarioSelecionado.armazem,
            ),
            buscarTendenciasRotativo(
              inventarioSelecionado.cliente_id,
              inventarioSelecionado.armazem,
            ),
          ]);

          if (!requisicaoAindaAtual()) {
            return;
          }

          setPainel(
            dadosPainel,
          );

          setTendencias(
            dadosTendencias,
          );
        }
      } catch (e) {
        if (!requisicaoAindaAtual()) {
          return;
        }

        setErro(
          e instanceof Error
            ? e.message
            : "Falha ao carregar indicadores.",
        );
      } finally {
        if (requisicaoAindaAtual()) {
          setCarregando(false);
        }
      }
    }, [
      inventarioSelecionado,
      limparDadosIndicadores,
    ]);

  useEffect(() => {
    void carregarInventarioAtual();
  }, [carregarInventarioAtual]);

  useEffect(() => {
    void carregarIndicadores();
  }, [carregarIndicadores]);

  const oficialSemExecucao =
    inventarioSelecionado?.tipo ===
      "OFICIAL" &&
    acompanhamento !== null &&
    produtividade !== null &&
    acompanhamento.progresso.itens
      .planejados === 0 &&
    acompanhamento.progresso.localizacoes
      .planejadas === 0 &&
    produtividade.producao.total_bipagens ===
      0;

  const statusLocalizacoes =
    acompanhamentoLocalizacoes
      ? [
          {
            nome: "Concluídas",
            valor:
              acompanhamentoLocalizacoes
                .resumo
                .localizacoes_concluidas,
            cor: CORES_GRAFICO.verde,
          },
          {
            nome: "Em andamento",
            valor:
              acompanhamentoLocalizacoes
                .resumo
                .localizacoes_em_andamento,
            cor: CORES_GRAFICO.amarelo,
          },
          {
            nome: "Pendentes",
            valor:
              acompanhamentoLocalizacoes
                .resumo
                .localizacoes_pendentes,
            cor: CORES_GRAFICO.cinza,
          },
        ]
      : [];

  const totalStatusLocalizacoes =
    statusLocalizacoes.reduce(
      (total, item) =>
        total + item.valor,
      0,
    );

  const progressoRodada =
    acompanhamento
      ? [
          {
            nome: "Itens",
            planejado:
              acompanhamento.progresso.itens
                .planejados,
            realizado:
              acompanhamento.progresso.itens
                .processados,
          },
          {
            nome: "Localizações",
            planejado:
              acompanhamento.progresso
                .localizacoes.planejadas,
            realizado:
              acompanhamento.progresso
                .localizacoes.concluidas,
          },
        ]
      : [];

  const produtividadeOperadores =
    produtividade
      ? [...produtividade.operadores]
          .sort(
            (a, b) =>
              b.bipagens_hora -
              a.bipagens_hora,
          )
          .slice(0, 8)
          .map((item) => ({
            operador: item.operador,
            bipagensHora:
              item.bipagens_hora,
            quantidadeHora:
              item.quantidade_hora,
          }))
      : [];

  const tempoLocalizacoes =
    produtividade
      ? [...produtividade.localizacoes_tempo]
          .filter(
            (item) =>
              item.tempo_segundos > 0,
          )
          .sort(
            (a, b) =>
              b.tempo_segundos -
              a.tempo_segundos,
          )
          .slice(0, 8)
          .map((item) => ({
            localizacao:
              item.localizacao,
            minutos:
              Number(
                (
                  item.tempo_segundos /
                  60
                ).toFixed(1),
              ),
          }))
      : [];

  const coberturaRotativo =
    painel
      ? [
          {
            nome: "Contadas",
            valor:
              painel.progresso.contadas,
            cor: CORES_GRAFICO.verde,
          },
          {
            nome: "Em contagem",
            valor:
              painel.progresso
                .em_contagem,
            cor: CORES_GRAFICO.azul,
          },
          {
            nome: "Pendentes",
            valor:
              painel.progresso.pendentes,
            cor: CORES_GRAFICO.cinza,
          },
          {
            nome: "Ignoradas",
            valor:
              painel.progresso.ignoradas,
            cor: CORES_GRAFICO.amarelo,
          },
        ]
      : [];

  const totalCoberturaRotativo =
    coberturaRotativo.reduce(
      (total, item) =>
        total + item.valor,
      0,
    );

  const riscoRotativo =
    painel
      ? [
          {
            nome: "Crítico",
            valor:
              painel.risco.critico,
            cor: CORES_GRAFICO.vermelho,
          },
          {
            nome: "Alto",
            valor:
              painel.risco.alto,
            cor: CORES_GRAFICO.laranja,
          },
          {
            nome: "Médio",
            valor:
              painel.risco.medio,
            cor: CORES_GRAFICO.amarelo,
          },
          {
            nome: "Baixo",
            valor:
              painel.risco.baixo,
            cor: CORES_GRAFICO.verde,
          },
        ]
      : [];

  const tendenciasRotativo =
    painel
      ? [
          {
            nome: "Estáveis",
            valor:
              painel.tendencias.estaveis,
          },
          {
            nome: "Atenção",
            valor:
              painel.tendencias.atencao,
          },
          {
            nome: "Recorrentes",
            valor:
              painel.tendencias.recorrentes,
          },
          {
            nome: "Deteriorando",
            valor:
              painel.tendencias
                .deteriorando,
          },
          {
            nome: "Melhorando",
            valor:
              painel.tendencias.melhorando,
          },
          {
            nome: "Sem histórico",
            valor:
              painel.tendencias
                .sem_historico,
          },
        ]
      : [];

  const prioridadesRotativo =
    painel
      ? painel.top_prioridades
          .filter(
            (item) =>
              item.score_risco !== null,
          )
          .slice(0, 8)
          .map((item) => ({
            localizacao:
              item.localizacao,
            score:
              item.score_risco ?? 0,
          }))
      : [];

  return (
    <div className="space-y-6 p-4 md:p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <BarChart3 className="h-6 w-6" />

            <h1 className="text-2xl font-bold">
              {"Indicadores" +
                (
                  inventarioSelecionado
                    ? " do inventário " +
                      (
                        inventarioSelecionado.tipo ===
                        "ROTATIVO"
                          ? "rotativo"
                          : "oficial"
                      )
                    : ""
                )}
            </h1>
          </div>

          <p className="mt-1 text-sm text-muted-foreground">
            {inventarioSelecionado?.tipo ===
            "ROTATIVO"
              ? "Cobertura do ciclo, prioridades, tratativas e tendências."
              : inventarioSelecionado?.tipo ===
                  "OFICIAL"
                ? "Execução da rodada e produtividade operacional."
                : "Indicadores operacionais do inventário ativo."}
          </p>
        </div>

        <div className="flex flex-col gap-2 sm:flex-row">
          <button
            type="button"
            onClick={() =>
              void carregarIndicadores()
            }
            disabled={
              !inventarioSelecionado ||
              carregando
            }
            className="inline-flex items-center justify-center gap-2 rounded-md border px-3 py-2 text-sm font-medium disabled:opacity-50"
          >
            <RefreshCcw
              className={`h-4 w-4 ${
                carregando
                  ? "animate-spin"
                  : ""
              }`}
            />

            Atualizar
          </button>
        </div>
      </div>

      {erro ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          {erro}
        </div>
      ) : null}

      {inventarioSelecionado?.tipo ===
        "OFICIAL" &&
      acompanhamento &&
      produtividade ? (
        oficialSemExecucao ? (
          <div className="rounded-xl border border-dashed p-6 text-center">
            <p className="font-medium">
              Inventário oficial sem execução disponível
            </p>

            <p className="mt-1 text-sm text-muted-foreground">
              A rodada ainda não possui itens ou localizações planejadas para acompanhamento.
            </p>
          </div>
        ) : (
          <>
            <Section
              titulo={
                "Execução da rodada " +
                acompanhamento.numero_rodada
              }
            >
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                <Card
                  titulo="Itens processados"
                  valor={percentual(
                    acompanhamento.progresso
                      .itens.percentual,
                  )}
                  detalhe={
                    numero(
                      acompanhamento.progresso
                        .itens.processados,
                    ) +
                    " de " +
                    numero(
                      acompanhamento.progresso
                        .itens.planejados,
                    ) +
                    " itens"
                  }
                />

                <Card
                  titulo="Localizações concluídas"
                  valor={percentual(
                    acompanhamento.progresso
                      .localizacoes.percentual,
                  )}
                  detalhe={
                    numero(
                      acompanhamento.progresso
                        .localizacoes.concluidas,
                    ) +
                    " de " +
                    numero(
                      acompanhamento.progresso
                        .localizacoes.planejadas,
                    ) +
                    " localizações"
                  }
                />

                <Card
                  titulo="Bipagens"
                  valor={numero(
                    produtividade.producao
                      .total_bipagens,
                  )}
                  detalhe={
                    numero(
                      produtividade.produtividade
                        .operacional.bipagens_hora,
                      2,
                    ) +
                    " bipagens/h"
                  }
                />

                <Card
                  titulo="Quantidade registrada"
                  valor={numero(
                    produtividade.producao
                      .quantidade_registrada,
                    2,
                  )}
                  detalhe={
                    numero(
                      produtividade.produtividade
                        .operacional
                        .quantidade_hora,
                      2,
                    ) +
                    " un./h"
                  }
                />

                <Card
                  titulo="Operadores"
                  valor={numero(
                    acompanhamento.atividade
                      .operadores_com_contagem,
                  )}
                  detalhe={
                    numero(
                      produtividade
                        .qualidade_dado_operador
                        .operadores_identificados,
                    ) +
                    " identificados"
                  }
                />

                <Card
                  titulo="Tempo operacional"
                  valor={
                    produtividade.tempo
                      .tempo_operacional_formatado
                  }
                  detalhe={
                    "Média por localização: " +
                    textoSeguro(
                      produtividade.tempo
                        .tempo_medio_localizacao_formatado,
                    )
                  }
                />
              </div>

              {produtividade
                .qualidade_dado_operador
                .possui_bipagens_sem_usuario ? (
                <div className="mt-3 flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-sm">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />

                  <span>
                    {numero(
                      produtividade
                        .qualidade_dado_operador
                        .bipagens_sem_usuario,
                    )}{" "}
                    bipagens estão sem usuário identificado.
                  </span>
                </div>
              ) : null}
            </Section>

            <Section titulo="Visão gráfica da execução">
              <div className="grid gap-4 xl:grid-cols-2">
                <ChartPanel
                  titulo="Status das localizações"
                  descricao="Distribuição da rodada entre concluídas, em andamento e pendentes."
                >
                  {totalStatusLocalizacoes >
                  0 ? (
                    <ResponsiveContainer
                      width="100%"
                      height="100%"
                    >
                      <PieChart>
                        <Pie
                          data={
                            statusLocalizacoes
                          }
                          dataKey="valor"
                          nameKey="nome"
                          innerRadius={58}
                          outerRadius={92}
                          paddingAngle={2}
                        >
                          {statusLocalizacoes.map(
                            (item) => (
                              <Cell
                                key={
                                  item.nome
                                }
                                fill={
                                  item.cor
                                }
                              />
                            ),
                          )}
                        </Pie>

                        <Tooltip />
                        <Legend />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : (
                    <EmptyChart mensagem="Ainda não há localizações com status para apresentar." />
                  )}
                </ChartPanel>

                <ChartPanel
                  titulo="Progresso da rodada"
                  descricao="Comparação entre planejado e realizado."
                >
                  <ResponsiveContainer
                    width="100%"
                    height="100%"
                  >
                    <BarChart
                      data={progressoRodada}
                      margin={{
                        top: 10,
                        right: 10,
                        left: 0,
                        bottom: 0,
                      }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        vertical={false}
                      />

                      <XAxis
                        dataKey="nome"
                      />

                      <YAxis
                        allowDecimals={false}
                      />

                      <Tooltip />
                      <Legend />

                      <Bar
                        dataKey="planejado"
                        name="Planejado"
                        fill={
                          CORES_GRAFICO.cinza
                        }
                        radius={[
                          4,
                          4,
                          0,
                          0,
                        ]}
                      />

                      <Bar
                        dataKey="realizado"
                        name="Realizado"
                        fill={
                          CORES_GRAFICO.azul
                        }
                        radius={[
                          4,
                          4,
                          0,
                          0,
                        ]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartPanel>

                <ChartPanel
                  titulo="Produtividade por operador"
                  descricao="Até 8 operadores ordenados por bipagens por hora."
                  compacto={
                    produtividadeOperadores.length ===
                    0
                  }
                >
                  {produtividadeOperadores.length >
                  0 ? (
                    <ResponsiveContainer
                      width="100%"
                      height="100%"
                    >
                      <BarChart
                        data={
                          produtividadeOperadores
                        }
                        layout="vertical"
                        margin={{
                          top: 0,
                          right: 20,
                          left: 10,
                          bottom: 0,
                        }}
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          horizontal={false}
                        />

                        <XAxis
                          type="number"
                        />

                        <YAxis
                          dataKey="operador"
                          type="category"
                          width={115}
                        />

                        <Tooltip />
                        <Legend />

                        <Bar
                          dataKey="bipagensHora"
                          name="Bipagens/h"
                          fill={
                            CORES_GRAFICO.azul
                          }
                          radius={[
                            0,
                            4,
                            4,
                            0,
                          ]}
                        />

                        <Bar
                          dataKey="quantidadeHora"
                          name="Quantidade/h"
                          fill={
                            CORES_GRAFICO.ciano
                          }
                          radius={[
                            0,
                            4,
                            4,
                            0,
                          ]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <EmptyChart mensagem="Ainda não há produtividade por operador para apresentar." />
                  )}
                </ChartPanel>

                <ChartPanel
                  titulo="Tempo por localização"
                  descricao="Localizações mais demoradas da rodada, em minutos."
                  compacto={
                    tempoLocalizacoes.length ===
                    0
                  }
                >
                  {tempoLocalizacoes.length >
                  0 ? (
                    <ResponsiveContainer
                      width="100%"
                      height="100%"
                    >
                      <BarChart
                        data={
                          tempoLocalizacoes
                        }
                        layout="vertical"
                        margin={{
                          top: 0,
                          right: 20,
                          left: 10,
                          bottom: 0,
                        }}
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          horizontal={false}
                        />

                        <XAxis
                          type="number"
                          unit=" min"
                        />

                        <YAxis
                          dataKey="localizacao"
                          type="category"
                          width={115}
                        />

                        <Tooltip />

                        <Bar
                          dataKey="minutos"
                          name="Tempo"
                          fill={
                            CORES_GRAFICO.roxo
                          }
                          radius={[
                            0,
                            4,
                            4,
                            0,
                          ]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <EmptyChart mensagem="Ainda não há tempo de localização suficiente para o gráfico." />
                  )}
                </ChartPanel>
              </div>
            </Section>
          </>
        )
      ) : null}

      {inventarioSelecionado?.tipo ===
        "ROTATIVO" &&
      painel ? (
        <Section titulo="Cobertura e inteligência do ciclo">
          {painel.possui_ciclo_aberto ? (
            <>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                <Card
                  titulo="Cobertura contada"
                  valor={percentual(
                    painel.progresso
                      .percentual_contado,
                  )}
                  detalhe={
                    numero(
                      painel.progresso
                        .contadas,
                    ) +
                    " de " +
                    numero(
                      painel.progresso
                        .total_localizacoes,
                    ) +
                    " localizações"
                  }
                />

                <Card
                  titulo="Pendentes"
                  valor={numero(
                    painel.progresso
                      .pendentes,
                  )}
                  detalhe={
                    percentual(
                      painel.progresso
                        .percentual_pendente,
                    ) +
                    " do ciclo"
                  }
                />

                <Card
                  titulo="Ignoradas"
                  valor={numero(
                    painel.progresso
                      .ignoradas,
                  )}
                  detalhe={
                    numero(
                      painel.execucao_dia
                        .localizacoes_ignoradas_hoje,
                    ) +
                    " hoje"
                  }
                />

                <Card
                  titulo="Risco alto/crítico pendente"
                  valor={numero(
                    painel.backlog
                      .risco_alto_critico_pendente,
                  )}
                  detalhe="Priorizar contagens com maior risco"
                />

                <Card
                  titulo="Alertas"
                  valor={numero(
                    painel.tendencias
                      .alertas,
                  )}
                  detalhe={
                    numero(
                      painel.tendencias
                        .deteriorando,
                    ) +
                    " deteriorando"
                  }
                />

                <Card
                  titulo="Tratativas pendentes"
                  valor={numero(
                    painel.tratativas
                      .ocorrencias_pendentes,
                  )}
                  detalhe={
                    numero(
                      painel.tratativas
                        .grupos_pendentes,
                    ) +
                    " grupos"
                  }
                />
              </div>

              <div className="grid gap-4 xl:grid-cols-2">
                <ChartPanel
                  titulo="Cobertura do ciclo"
                  descricao="Contadas, em contagem, pendentes e ignoradas."
                >
                  {totalCoberturaRotativo >
                  0 ? (
                    <ResponsiveContainer
                      width="100%"
                      height="100%"
                    >
                      <PieChart>
                        <Pie
                          data={
                            coberturaRotativo
                          }
                          dataKey="valor"
                          nameKey="nome"
                          innerRadius={58}
                          outerRadius={92}
                          paddingAngle={2}
                        >
                          {coberturaRotativo.map(
                            (item) => (
                              <Cell
                                key={
                                  item.nome
                                }
                                fill={
                                  item.cor
                                }
                              />
                            ),
                          )}
                        </Pie>

                        <Tooltip />
                        <Legend />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : (
                    <EmptyChart mensagem="Ainda não há cobertura do ciclo para apresentar." />
                  )}
                </ChartPanel>

                <ChartPanel
                  titulo="Distribuição de risco"
                  descricao="Localizações classificadas por criticidade."
                >
                  <ResponsiveContainer
                    width="100%"
                    height="100%"
                  >
                    <BarChart
                      data={riscoRotativo}
                      margin={{
                        top: 10,
                        right: 10,
                        left: 0,
                        bottom: 0,
                      }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        vertical={false}
                      />

                      <XAxis
                        dataKey="nome"
                      />

                      <YAxis
                        allowDecimals={false}
                      />

                      <Tooltip />

                      <Bar
                        dataKey="valor"
                        name="Localizações"
                        radius={[
                          4,
                          4,
                          0,
                          0,
                        ]}
                      >
                        {riscoRotativo.map(
                          (item) => (
                            <Cell
                              key={
                                item.nome
                              }
                              fill={
                                item.cor
                              }
                            />
                          ),
                        )}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </ChartPanel>

                <ChartPanel
                  titulo="Tendências do ciclo"
                  descricao="Distribuição das classificações de tendência."
                >
                  <ResponsiveContainer
                    width="100%"
                    height="100%"
                  >
                    <BarChart
                      data={
                        tendenciasRotativo
                      }
                      margin={{
                        top: 10,
                        right: 10,
                        left: 0,
                        bottom: 40,
                      }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        vertical={false}
                      />

                      <XAxis
                        dataKey="nome"
                        angle={-25}
                        textAnchor="end"
                        interval={0}
                        height={70}
                      />

                      <YAxis
                        allowDecimals={false}
                      />

                      <Tooltip />

                      <Bar
                        dataKey="valor"
                        name="Localizações"
                        fill={
                          CORES_GRAFICO.roxo
                        }
                        radius={[
                          4,
                          4,
                          0,
                          0,
                        ]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartPanel>

                <ChartPanel
                  titulo="Top prioridades por risco"
                  descricao="Até 8 localizações sugeridas pelo ciclo."
                >
                  {prioridadesRotativo.length >
                  0 ? (
                    <ResponsiveContainer
                      width="100%"
                      height="100%"
                    >
                      <BarChart
                        data={
                          prioridadesRotativo
                        }
                        layout="vertical"
                        margin={{
                          top: 0,
                          right: 20,
                          left: 10,
                          bottom: 0,
                        }}
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          horizontal={false}
                        />

                        <XAxis
                          type="number"
                        />

                        <YAxis
                          dataKey="localizacao"
                          type="category"
                          width={115}
                        />

                        <Tooltip />

                        <Bar
                          dataKey="score"
                          name="Score de risco"
                          fill={
                            CORES_GRAFICO.laranja
                          }
                          radius={[
                            0,
                            4,
                            4,
                            0,
                          ]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <EmptyChart mensagem="Não há prioridades com score de risco para apresentar." />
                  )}
                </ChartPanel>
              </div>

              {painel.top_prioridades.length ? (
                <div className="rounded-xl border">
                  <div className="border-b p-4">
                    <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <h3 className="font-semibold">
                          Prioridades do ciclo
                        </h3>

                        <p className="text-xs text-muted-foreground">
                          Ordem operacional sugerida pelo ciclo rotativo.
                        </p>
                      </div>

                      <p className="text-xs text-muted-foreground">
                        {painel.risco
                          .sugestoes_por_risco}{" "}
                        por risco ·{" "}
                        {painel.risco
                          .sugestoes_por_cobertura}{" "}
                        por cobertura
                      </p>
                    </div>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[760px] text-sm">
                      <thead className="bg-muted/50 text-left">
                        <tr>
                          <th className="px-3 py-2">
                            Prioridade
                          </th>

                          <th className="px-3 py-2">
                            Localização
                          </th>

                          <th className="px-3 py-2">
                            Tipo
                          </th>

                          <th className="px-3 py-2">
                            Score
                          </th>

                          <th className="px-3 py-2">
                            Risco
                          </th>

                          <th className="px-3 py-2">
                            Motivo
                          </th>
                        </tr>
                      </thead>

                      <tbody>
                        {painel.top_prioridades.map(
                          (item) => (
                            <tr
                              key={
                                item.id_ciclo_localizacao
                              }
                              className="border-t"
                            >
                              <td className="px-3 py-2 font-semibold">
                                {item.prioridade ??
                                  "-"}
                              </td>

                              <td className="px-3 py-2 font-medium">
                                {
                                  item.localizacao
                                }
                              </td>

                              <td className="px-3 py-2">
                                {item.tipo_sugestao ===
                                "RISCO"
                                  ? "Risco"
                                  : item.tipo_sugestao ===
                                      "COBERTURA_CICLO"
                                    ? "Cobertura"
                                    : "-"}
                              </td>

                              <td className="px-3 py-2">
                                {numero(
                                  item.score_risco,
                                  2,
                                )}
                              </td>

                              <td className="px-3 py-2">
                                {item.classificacao_risco ??
                                  "-"}
                              </td>

                              <td className="px-3 py-2 text-muted-foreground">
                                {item.motivo ??
                                  "-"}
                              </td>
                            </tr>
                          ),
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : null}

              <div className="grid gap-3 lg:grid-cols-2">
                {painel.alerta_principal ? (
                  <div className="rounded-xl border p-4">
                    <div className="flex items-center gap-2 font-semibold">
                      <ShieldAlert className="h-4 w-4" />
                      Alerta principal
                    </div>

                    <p className="mt-3 text-sm">
                      <strong>
                        {
                          painel
                            .alerta_principal
                            .localizacao
                        }
                      </strong>{" "}
                      ·{" "}
                      {
                        painel
                          .alerta_principal
                          .classificacao_tendencia
                      }{" "}
                      · risco{" "}
                      {numero(
                        painel
                          .alerta_principal
                          .score_risco,
                        2,
                      )}{" "}
                      (
                      {
                        painel
                          .alerta_principal
                          .classificacao_risco
                      }
                      )
                    </p>

                    <p className="mt-2 text-sm text-muted-foreground">
                      {
                        painel
                          .alerta_principal
                          .motivo_principal
                      }
                    </p>
                  </div>
                ) : null}

                {painel.alerta_tratativa ? (
                  <div className="rounded-xl border p-4">
                    <div className="flex items-center gap-2 font-semibold">
                      <PackageCheck className="h-4 w-4" />
                      Alerta de tratativa
                    </div>

                    <p className="mt-3 text-sm">
                      <strong>
                        {
                          painel
                            .alerta_tratativa
                            .localizacao
                        }
                      </strong>{" "}
                      ·{" "}
                      {
                        painel
                          .alerta_tratativa
                          .ocorrencias_pendentes
                      }{" "}
                      ocorrências pendentes
                    </p>

                    <p className="mt-2 text-sm text-muted-foreground">
                      Risco{" "}
                      {numero(
                        painel
                          .alerta_tratativa
                          .score_risco,
                        2,
                      )}{" "}
                      ·{" "}
                      {
                        painel
                          .alerta_tratativa
                          .classificacao_risco
                      }
                    </p>
                  </div>
                ) : null}
              </div>
            </>
          ) : (
            <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
              Não há ciclo rotativo aberto para apresentar cobertura e prioridades.
            </div>
          )}
        </Section>
      ) : null}

      {inventarioSelecionado?.tipo ===
        "ROTATIVO" &&
      tendencias?.possui_ciclo_aberto &&
      tendencias.tendencias.length ? (
        <Section titulo="Tendências por localização">
          <div className="overflow-x-auto rounded-xl border">
            <table className="w-full min-w-[980px] text-sm">
              <thead className="bg-muted/50 text-left">
                <tr>
                  <th className="px-3 py-2">
                    Localização
                  </th>

                  <th className="px-3 py-2">
                    Tendência
                  </th>

                  <th className="px-3 py-2">
                    Direção
                  </th>

                  <th className="px-3 py-2">
                    Risco
                  </th>

                  <th className="px-3 py-2">
                    Evidência
                  </th>

                  <th className="px-3 py-2">
                    Recorrência
                  </th>

                  <th className="px-3 py-2">
                    Pendências
                  </th>

                  <th className="px-3 py-2">
                    Última eficácia
                  </th>
                </tr>
              </thead>

              <tbody>
                {tendencias.tendencias.map(
                  (item) => (
                    <tr
                      key={
                        item.id_ciclo_localizacao
                      }
                      className="border-t"
                    >
                      <td className="px-3 py-2 font-medium">
                        {item.localizacao}
                      </td>

                      <td className="px-3 py-2">
                        <span className="inline-flex items-center gap-1">
                          {item.direcao ===
                          "PIORA" ? (
                            <TrendingDown className="h-4 w-4" />
                          ) : item.direcao ===
                            "MELHORA" ? (
                            <TrendingUp className="h-4 w-4" />
                          ) : (
                            <Gauge className="h-4 w-4" />
                          )}

                          {
                            item.classificacao_tendencia
                          }
                        </span>
                      </td>

                      <td className="px-3 py-2">
                        {item.direcao}
                      </td>

                      <td className="px-3 py-2">
                        {numero(
                          item.score_risco,
                          2,
                        )}{" "}
                        ·{" "}
                        {
                          item.classificacao_risco
                        }
                      </td>

                      <td className="px-3 py-2">
                        {
                          item.nivel_evidencia
                        }
                      </td>

                      <td className="px-3 py-2">
                        {item.recorrencia
                          .possui_recorrencia_item_lote
                          ? "Sim"
                          : "Não"}
                      </td>

                      <td className="px-3 py-2">
                        {
                          item.tratativa
                            .ocorrencias_pendentes
                        }
                      </td>

                      <td className="px-3 py-2">
                        {item.eficacia
                          .ultima_classificacao ??
                          "-"}
                      </td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>
        </Section>
      ) : null}

      {carregando &&
      !inventarioSelecionado ? (
        <div className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
          Carregando indicadores...
        </div>
      ) : null}

      {!carregando &&
      !inventarioSelecionado &&
      !erro ? (
        <div className="rounded-xl border border-dashed p-6 text-center">
          <p className="font-medium">
            Nenhum inventário aberto
          </p>

          <p className="mt-1 text-sm text-muted-foreground">
            Os indicadores aparecem quando houver uma operação ativa.
          </p>
        </div>
      ) : null}

      {!carregando &&
      inventarioSelecionado?.tipo ===
        "OFICIAL" &&
      !acompanhamento &&
      !produtividade &&
      !erro ? (
        <div className="rounded-xl border p-6 text-center text-sm text-muted-foreground">
          Nenhum indicador de execução disponível para este inventário oficial.
        </div>
      ) : null}

      {!carregando &&
      inventarioSelecionado?.tipo ===
        "ROTATIVO" &&
      !painel &&
      !erro ? (
        <div className="rounded-xl border p-6 text-center text-sm text-muted-foreground">
          Nenhum indicador do ciclo rotativo disponível para este inventário.
        </div>
      ) : null}
    </div>
  );
}
