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
  limparInventarioAtual,
  obterInventarioAtual,
  salvarInventarioAtual,
} from "@/lib/inventarioAtual";

import {
  buscarAcompanhamento,
  buscarAcompanhamentoLocalizacoes,
  buscarPainelRotativo,
  buscarProdutividade,
  listarInventariosIndicadores,
  type AcompanhamentoLocalizacoes,
  type AcompanhamentoOperacional,
  type InventarioIndicadores,
  type PainelRotativo,
  type ProdutividadeOperacional,
} from "@/services/indicadoresService";

interface AcompanhamentoSearch {
  inventario?: number;
}

export const Route = createFileRoute("/acompanhamento-contagem")({
  head: () => ({
    meta: [{ title: "Acompanhamento da Contagem — SGI" }],
  }),
  validateSearch: (
    search: Record<string, unknown>,
  ): AcompanhamentoSearch => {
    const valor = Number(search["inventario"]);

    if (Number.isInteger(valor) && valor > 0) {
      return { inventario: valor };
    }

    return {};
  },
  component: AcompanhamentoContagemPage,
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

function percentual(valor: number | null | undefined) {
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

function dataHora(valor: string | null | undefined) {
  const texto = textoSeguro(valor, "");

  if (!texto) return "-";

  const data = new Date(texto);

  if (Number.isNaN(data.getTime())) {
    return texto;
  }

  return data.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
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
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {titulo}
          </p>

          <p className="mt-2 break-words text-2xl font-semibold">
            {valor}
          </p>

          {detalhe ? (
            <p className="mt-1 text-xs text-muted-foreground">
              {detalhe}
            </p>
          ) : null}
        </div>

        {icone ? (
          <div className="shrink-0 rounded-lg bg-muted p-2 text-muted-foreground">
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
  rotuloProcessados = "Processados",
  rotuloConclusao = "concluídos",
}: {
  titulo: string;
  processados: number;
  planejados: number;
  pendentes: number;
  percentualValor: number;
  rotuloProcessados?: string;
  rotuloConclusao?: string;
}) {
  const largura = Math.max(
    0,
    Math.min(100, percentualValor || 0),
  );

  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-4">
        <div>
          <p className="font-semibold">{titulo}</p>
          <p className="text-xs text-muted-foreground">
            {numero(processados)} de {numero(planejados)}{" "}
            {rotuloConclusao}
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
        <span>
          {rotuloProcessados}: {numero(processados)}
        </span>
        <span>Pendentes: {numero(pendentes)}</span>
      </div>
    </div>
  );
}

function BadgeTipo({ tipo }: { tipo: string }) {
  const rotativo = tipo === "ROTATIVO";

  return (
    <span
      className={
        rotativo
          ? "inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300"
          : "inline-flex rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs font-semibold text-sky-700 dark:border-sky-900 dark:bg-sky-950/30 dark:text-sky-300"
      }
    >
      {rotativo ? "ROTATIVO" : "OFICIAL"}
    </span>
  );
}

function StatusOperacional({
  titulo,
  detalhe,
}: {
  titulo: string;
  detalhe: string;
}) {
  return (
    <div className="flex flex-col gap-2 rounded-xl border bg-card px-4 py-3 shadow-sm sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-2">
        <span className="relative flex h-2.5 w-2.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-30" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-primary" />
        </span>
        <span className="text-sm font-semibold">{titulo}</span>
      </div>

      <span className="text-xs text-muted-foreground">
        {detalhe}
      </span>
    </div>
  );
}

function ResumoLocalizacoesOficial({
  dados,
  acompanhamento,
}: {
  dados: AcompanhamentoLocalizacoes | null;
  acompanhamento: AcompanhamentoOperacional;
}) {
  const planejadas =
    dados?.resumo.localizacoes_planejadas ??
    acompanhamento.progresso.localizacoes.planejadas;

  const concluidas =
    dados?.resumo.localizacoes_concluidas ??
    acompanhamento.progresso.localizacoes.concluidas;

  const emAndamento =
    dados?.resumo.localizacoes_em_andamento ?? 0;

  const pendentes =
    dados?.resumo.localizacoes_pendentes ??
    acompanhamento.progresso.localizacoes.pendentes;

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Card
        titulo="Planejadas"
        valor={numero(planejadas)}
        icone={<MapPin className="h-4 w-4" />}
      />
      <Card
        titulo="Pendentes"
        valor={numero(pendentes)}
        icone={<MapPin className="h-4 w-4" />}
      />
      <Card
        titulo="Em andamento"
        valor={numero(emAndamento)}
        icone={<Activity className="h-4 w-4" />}
      />
      <Card
        titulo="Concluídas"
        valor={numero(concluidas)}
        detalhe={`${percentual(
          acompanhamento.progresso.localizacoes.percentual,
        )} do planejado`}
        icone={<PackageCheck className="h-4 w-4" />}
      />
    </div>
  );
}

function AcessoLocalizacoes({
  inventario,
  tipo,
}: {
  inventario: InventarioIndicadores;
  tipo: "OFICIAL" | "ROTATIVO";
}) {
  return (
    <section className="rounded-xl border bg-card p-5 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold">
            {tipo === "ROTATIVO"
              ? "Localizações do inventário atual"
              : "Acompanhamento por localização"}
          </h2>

          <p className="mt-1 text-sm text-muted-foreground">
            {tipo === "ROTATIVO"
              ? "Consulte o andamento detalhado das localizações vinculadas a este inventário rotativo."
              : "Consulte cada endereço com status, filtros, pesquisa e paginação."}
          </p>
        </div>

        <div className="flex flex-col gap-2 sm:flex-row">
          <Link
            to="/acompanhamento-contagem/localizacoes"
            search={{
              inventario: inventario.id_inventario,
            }}
            className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm transition hover:bg-primary/90"
          >
            <MapPin className="h-4 w-4" />
            {tipo === "ROTATIVO"
              ? "Ver localizações do inventário"
              : "Ver localizações"}
          </Link>

          {tipo === "ROTATIVO" ? (
            <Link
              to="/ciclo-rotativo"
              className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-md border px-4 text-sm font-medium shadow-sm transition hover:bg-muted"
            >
              <Activity className="h-4 w-4" />
              Abrir ciclo rotativo
            </Link>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function Produtividade({
  dados,
  tipo,
}: {
  dados: ProdutividadeOperacional;
  tipo: "OFICIAL" | "ROTATIVO";
}) {
  const possuiAtividade =
    dados.producao.total_bipagens > 0 ||
    dados.producao.quantidade_registrada > 0 ||
    Boolean(textoSeguro(dados.tempo.primeira_bipagem, ""));

  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold">
          Produtividade
        </h2>
        <p className="text-sm text-muted-foreground">
          {tipo === "OFICIAL"
            ? "Desempenho calculado sobre o tempo operacional da rodada atual."
            : "Desempenho operacional do inventário rotativo atualmente em execução."}
        </p>
      </div>

      {!possuiAtividade ? (
        <div className="rounded-xl border border-dashed bg-muted/20 px-5 py-4 text-sm text-muted-foreground">
          Produtividade disponível após o início da contagem.
        </div>
      ) : (
        <>
          {dados.qualidade_dado_operador
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
                  dados.qualidade_dado_operador
                    .bipagens_sem_usuario,
                )}{" "}
                {dados.qualidade_dado_operador
                  .bipagens_sem_usuario === 1
                  ? "bipagem"
                  : "bipagens"}{" "}
                sem operador identificado. Esses registros permanecem
                no volume e na produtividade, mas não entram no total
                de operadores identificados.
              </p>
            </div>
          ) : null}

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Card
              titulo="Tempo operacional"
              valor={textoSeguro(
                dados.tempo.tempo_operacional_formatado,
              )}
              icone={<Clock3 className="h-4 w-4" />}
            />

            <Card
              titulo="Bipagens/h"
              valor={numero(
                dados.produtividade.operacional
                  .bipagens_hora,
                2,
              )}
              icone={<Gauge className="h-4 w-4" />}
            />

            <Card
              titulo="Quantidade/h"
              valor={numero(
                dados.produtividade.operacional
                  .quantidade_hora,
                2,
              )}
              icone={<Gauge className="h-4 w-4" />}
            />

            <Card
              titulo="Tempo médio/localização"
              valor={textoSeguro(
                dados.tempo
                  .tempo_medio_localizacao_formatado,
              )}
              icone={<MapPin className="h-4 w-4" />}
            />
          </div>

          <div className="space-y-3">
            <div>
              <h3 className="font-semibold text-foreground">
                Produtividade por operador
              </h3>

              <p className="text-sm text-muted-foreground">
                {tipo === "OFICIAL"
                  ? "Desempenho individual dos operadores identificados na rodada atual."
                  : "Desempenho individual dos operadores identificados neste inventário rotativo."}
              </p>
            </div>

            {dados.operadores.some(
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
                        Localizações
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
                    {dados.operadores
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
                            {numero(operador.total_bipagens)}
                          </td>
                          <td className="px-4 py-3 text-right">
                            {numero(
                              operador.quantidade_registrada,
                              2,
                            )}
                          </td>
                          <td className="px-4 py-3 text-right">
                            {numero(
                              operador.itens_distintos_com_bipagem,
                            )}
                          </td>
                          <td className="px-4 py-3 text-right">
                            {numero(
                              operador.localizacoes_com_atividade,
                            )}
                          </td>
                          <td className="whitespace-nowrap px-4 py-3 text-right">
                            {textoSeguro(
                              operador.tempo_ativo_formatado,
                            )}
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
                Nenhum operador identificado nesta contagem.
                As bipagens sem usuário permanecem contabilizadas nos
                indicadores gerais.
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}

function AcompanhamentoContagemPage() {
  const { inventario: idInventarioUrl } =
    Route.useSearch();

  const [
    idInventarioContexto,
    setIdInventarioContexto,
  ] = useState<number | null>(idInventarioUrl ?? null);

  const idInventario =
    idInventarioUrl ?? idInventarioContexto;

  const [inventarios, setInventarios] =
    useState<InventarioIndicadores[]>([]);

  const [acompanhamento, setAcompanhamento] =
    useState<AcompanhamentoOperacional | null>(null);

  const [localizacoesOficial, setLocalizacoesOficial] =
    useState<AcompanhamentoLocalizacoes | null>(null);

  const [produtividade, setProdutividade] =
    useState<ProdutividadeOperacional | null>(null);

  const [painelRotativo, setPainelRotativo] =
    useState<PainelRotativo | null>(null);

  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const requisicaoAtual = useRef(0);

  const inventarioSelecionado = useMemo(
    () =>
      inventarios.find(
        (item) =>
          item.id_inventario === idInventario,
      ) ?? null,
    [inventarios, idInventario],
  );

  const tipoInventario =
    inventarioSelecionado?.tipo === "ROTATIVO"
      ? "ROTATIVO"
      : "OFICIAL";

  const carregarInventarios = useCallback(async () => {
    const dados = await listarInventariosIndicadores();

    const inventariosOrdenados = [...dados].sort(
      (inventarioA, inventarioB) =>
        inventarioB.id_inventario -
        inventarioA.id_inventario,
    );

    setInventarios(inventariosOrdenados);

    if (inventariosOrdenados.length === 0) {
      limparInventarioAtual();
      setAcompanhamento(null);
      setLocalizacoesOficial(null);
      setProdutividade(null);
      setPainelRotativo(null);

      throw new Error(
        "Nenhum inventário está disponível para acompanhamento.",
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

    if (idInventarioUrl && !inventarioPreferido) {
      setAcompanhamento(null);
      setLocalizacoesOficial(null);
      setProdutividade(null);
      setPainelRotativo(null);

      throw new Error(
        "O inventário informado não foi encontrado ou não está disponível para acompanhamento.",
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
  }, [idInventario, idInventarioUrl]);

  const carregarAcompanhamento = useCallback(async () => {
    if (!inventarioSelecionado) return;

    const idRequisicao = ++requisicaoAtual.current;

    setCarregando(true);
    setErro(null);
    setAcompanhamento(null);
    setLocalizacoesOficial(null);
    setProdutividade(null);
    setPainelRotativo(null);

    try {
      if (inventarioSelecionado.tipo === "ROTATIVO") {
        const [
          dadosAcompanhamento,
          dadosProdutividade,
          dadosPainel,
        ] = await Promise.all([
          buscarAcompanhamento(
            inventarioSelecionado.id_inventario,
          ),
          buscarProdutividade(
            inventarioSelecionado.id_inventario,
          ),
          buscarPainelRotativo(
            inventarioSelecionado.cliente_id,
            inventarioSelecionado.armazem,
          ),
        ]);

        if (idRequisicao !== requisicaoAtual.current) {
          return;
        }

        setAcompanhamento(dadosAcompanhamento);
        setProdutividade(dadosProdutividade);
        setPainelRotativo(dadosPainel);
      } else {
        const [
          dadosAcompanhamento,
          dadosProdutividade,
          dadosLocalizacoes,
        ] = await Promise.all([
          buscarAcompanhamento(
            inventarioSelecionado.id_inventario,
          ),
          buscarProdutividade(
            inventarioSelecionado.id_inventario,
          ),
          buscarAcompanhamentoLocalizacoes(
            inventarioSelecionado.id_inventario,
          ),
        ]);

        if (idRequisicao !== requisicaoAtual.current) {
          return;
        }

        setAcompanhamento(dadosAcompanhamento);
        setProdutividade(dadosProdutividade);
        setLocalizacoesOficial(dadosLocalizacoes);
      }
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

  const statusOficial = useMemo(() => {
    if (!acompanhamento) {
      return {
        titulo: "Aguardando dados",
        detalhe: "Inventário oficial",
      };
    }

    const status = acompanhamento.status_rodada
      .trim()
      .toUpperCase();

    if (
      status.includes("CONCL") ||
      status.includes("FINAL") ||
      status.includes("ENCERR")
    ) {
      return {
        titulo: "Rodada concluída",
        detalhe: `Rodada ${acompanhamento.numero_rodada}`,
      };
    }

    if (
      acompanhamento.atividade.total_bipagens > 0 ||
      acompanhamento.volume.quantidade_registrada > 0
    ) {
      return {
        titulo: "Contagem em execução",
        detalhe: `Rodada ${acompanhamento.numero_rodada} • ${acompanhamento.status_rodada}`,
      };
    }

    return {
      titulo: "Aguardando início da contagem",
      detalhe: `Rodada ${acompanhamento.numero_rodada} • ${acompanhamento.status_rodada}`,
    };
  }, [acompanhamento]);

  return (
    <div className="space-y-6 p-4 md:p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Activity className="h-6 w-6" />
            <h1 className="text-2xl font-bold">
              Acompanhamento da Contagem
            </h1>

            {inventarioSelecionado ? (
              <BadgeTipo tipo={tipoInventario} />
            ) : null}
          </div>

          <p className="mt-1 text-sm text-muted-foreground">
            {tipoInventario === "ROTATIVO"
              ? "Cobertura do ciclo e execução operacional do inventário rotativo atual."
              : "Execução da rodada, progresso das localizações e atividade operacional."}
          </p>
        </div>

        {idInventario ? (
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
        ) : null}
      </div>

      {erro ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          <p>{erro}</p>
        </div>
      ) : null}

      {inventarioSelecionado && acompanhamento ? (
        tipoInventario === "OFICIAL" ? (
          <>
            <StatusOperacional
              titulo={statusOficial.titulo}
              detalhe={statusOficial.detalhe}
            />

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
                    acompanhamento.progresso.itens
                      .processados
                  }
                  planejados={
                    acompanhamento.progresso.itens
                      .planejados
                  }
                  pendentes={
                    acompanhamento.progresso.itens
                      .pendentes
                  }
                  percentualValor={
                    acompanhamento.progresso.itens
                      .percentual
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
                  rotuloProcessados="Concluídas"
                  rotuloConclusao="concluídas"
                />
              </div>
            </section>

            <section className="space-y-3">
              <div>
                <h2 className="text-lg font-semibold">
                  Status das localizações
                </h2>
                <p className="text-sm text-muted-foreground">
                  Situação operacional das localizações da rodada.
                </p>
              </div>

              <ResumoLocalizacoesOficial
                dados={localizacoesOficial}
                acompanhamento={acompanhamento}
              />
            </section>

            <AcessoLocalizacoes
              inventario={inventarioSelecionado}
              tipo="OFICIAL"
            />

            <section className="space-y-3">
              <div>
                <h2 className="text-lg font-semibold">
                  Operação
                </h2>
                <p className="text-sm text-muted-foreground">
                  Atividade registrada na rodada atual.
                </p>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
                <Card
                  titulo="Quantidade planejada"
                  valor={numero(
                    acompanhamento.volume
                      .quantidade_planejada,
                    2,
                  )}
                  icone={
                    <PackageCheck className="h-4 w-4" />
                  }
                />

                <Card
                  titulo="Quantidade registrada"
                  valor={numero(
                    acompanhamento.volume
                      .quantidade_registrada,
                    2,
                  )}
                  icone={
                    <PackageCheck className="h-4 w-4" />
                  }
                />

                <Card
                  titulo="Bipagens"
                  valor={numero(
                    acompanhamento.atividade
                      .total_bipagens,
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
                  titulo="Última bipagem"
                  valor={dataHora(
                    produtividade?.tempo.ultima_bipagem,
                  )}
                  detalhe={
                    acompanhamento.atividade.total_bipagens > 0
                      ? "Atividade mais recente"
                      : "Sem atividade registrada"
                  }
                  icone={<Clock3 className="h-4 w-4" />}
                />
              </div>
            </section>

            {produtividade ? (
              <Produtividade
                dados={produtividade}
                tipo="OFICIAL"
              />
            ) : null}
          </>
        ) : (
          <>
            {painelRotativo?.possui_ciclo_aberto &&
            painelRotativo.ciclo ? (
              <>
                <StatusOperacional
                  titulo="Ciclo rotativo em execução"
                  detalhe={`${painelRotativo.ciclo.codigo_ciclo} • ${painelRotativo.ciclo.status}`}
                />

                <section className="space-y-3">
                  <div>
                    <h2 className="text-lg font-semibold">
                      Cobertura do ciclo
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      Cobertura baseada somente nas localizações efetivamente contadas.
                    </p>
                  </div>

                  <BarraProgresso
                    titulo="Localizações contadas"
                    processados={
                      painelRotativo.progresso.contadas
                    }
                    planejados={
                      painelRotativo.progresso
                        .total_localizacoes
                    }
                    pendentes={
                      painelRotativo.progresso.pendentes
                    }
                    percentualValor={
                      painelRotativo.progresso
                        .percentual_contado
                    }
                    rotuloProcessados="Contadas"
                    rotuloConclusao="contadas"
                  />

                  <p className="text-xs text-muted-foreground">
                    Recontagens e localizações ignoradas não aumentam a cobertura contada do ciclo.
                  </p>
                </section>

                <section className="space-y-3">
                  <div>
                    <h2 className="text-lg font-semibold">
                      Status do ciclo
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      Distribuição das localizações no ciclo rotativo atual.
                    </p>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <Card
                      titulo="Contadas"
                      valor={numero(
                        painelRotativo.progresso.contadas,
                      )}
                      detalhe={`${percentual(
                        painelRotativo.progresso
                          .percentual_contado,
                      )} de cobertura`}
                      icone={
                        <PackageCheck className="h-4 w-4" />
                      }
                    />

                    <Card
                      titulo="Em contagem"
                      valor={numero(
                        painelRotativo.progresso
                          .em_contagem,
                      )}
                      icone={
                        <Activity className="h-4 w-4" />
                      }
                    />

                    <Card
                      titulo="Pendentes"
                      valor={numero(
                        painelRotativo.progresso.pendentes,
                      )}
                      detalhe={`${percentual(
                        painelRotativo.progresso
                          .percentual_pendente,
                      )} do ciclo`}
                      icone={<MapPin className="h-4 w-4" />}
                    />

                    <Card
                      titulo="Ignoradas"
                      valor={numero(
                        painelRotativo.progresso.ignoradas,
                      )}
                      detalhe="Não contam como cobertura"
                      icone={<MapPin className="h-4 w-4" />}
                    />
                  </div>
                </section>

                <AcessoLocalizacoes
                  inventario={inventarioSelecionado}
                  tipo="ROTATIVO"
                />

                <section className="space-y-3">
                  <div>
                    <h2 className="text-lg font-semibold">
                      Operação do inventário atual
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      Atividade deste inventário dentro do ciclo rotativo.
                    </p>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
                    <Card
                      titulo="Contadas hoje"
                      valor={numero(
                        painelRotativo.execucao_dia
                          .localizacoes_contadas_hoje,
                      )}
                      icone={
                        <PackageCheck className="h-4 w-4" />
                      }
                    />

                    <Card
                      titulo="Quantidade registrada"
                      valor={numero(
                        acompanhamento.volume
                          .quantidade_registrada,
                        2,
                      )}
                      icone={
                        <PackageCheck className="h-4 w-4" />
                      }
                    />

                    <Card
                      titulo="Bipagens"
                      valor={numero(
                        acompanhamento.atividade
                          .total_bipagens,
                      )}
                      icone={
                        <ScanLine className="h-4 w-4" />
                      }
                    />

                    <Card
                      titulo="Usuários ativos"
                      valor={numero(
                        painelRotativo.execucao_dia
                          .usuarios_ativos,
                      )}
                      detalhe={`${numero(
                        produtividade?.qualidade_dado_operador
                          .operadores_identificados ??
                          acompanhamento.atividade
                            .operadores_com_contagem,
                      )} identificados neste inventário`}
                      icone={<Users className="h-4 w-4" />}
                    />

                    <Card
                      titulo="Última bipagem"
                      valor={dataHora(
                        produtividade?.tempo.ultima_bipagem,
                      )}
                      detalhe={
                        acompanhamento.atividade.total_bipagens > 0
                          ? "Atividade mais recente"
                          : "Sem atividade registrada"
                      }
                      icone={<Clock3 className="h-4 w-4" />}
                    />
                  </div>
                </section>

                {produtividade ? (
                  <Produtividade
                    dados={produtividade}
                    tipo="ROTATIVO"
                  />
                ) : null}
              </>
            ) : (
              <div className="rounded-xl border border-dashed bg-muted/20 p-6 text-sm text-muted-foreground">
                Nenhum ciclo rotativo aberto foi encontrado para o cliente e armazém deste inventário.
              </div>
            )}
          </>
        )
      ) : null}

      {!acompanhamento && !erro && carregando ? (
        <div className="rounded-xl border bg-card p-8 text-center text-sm text-muted-foreground">
          Carregando acompanhamento...
        </div>
      ) : null}
    </div>
  );
}
