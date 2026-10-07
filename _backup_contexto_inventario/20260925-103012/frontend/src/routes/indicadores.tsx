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
  obterInventarioAtual,
  salvarInventarioAtual,
} from "@/lib/inventarioAtual";

import {
  buscarAcompanhamento,
  buscarPainelRotativo,
  buscarPriorizacaoRisco,
  buscarProdutividade,
  buscarResultadoFinalIndicadores,
  buscarTendenciasRotativo,
  listarInventariosIndicadores,
  type AcompanhamentoOperacional,
  type InventarioIndicadores,
  type PainelRotativo,
  type PriorizacaoRisco,
  type ProdutividadeOperacional,
  type ResultadoFinalIndicadores,
  type TendenciasRotativo,
} from "@/services/indicadoresService";

interface IndicadoresSearch {
  inventario?: number;
}

export const Route = createFileRoute("/indicadores")({
  head: () => ({
    meta: [{ title: "Indicadores \u2014 SGI" }],
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

function numero(valor: number | null | undefined, casas = 0) {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return "-";
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
      <p className="mt-2 text-2xl font-semibold">{valor}</p>
      {detalhe ? <p className="mt-1 text-xs text-muted-foreground">{detalhe}</p> : null}
    </div>
  );
}

function Section({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">{titulo}</h2>
      {children}
    </section>
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

  const [acompanhamento, setAcompanhamento] =
    useState<AcompanhamentoOperacional | null>(
      null,
    );

  const [produtividade, setProdutividade] =
    useState<ProdutividadeOperacional | null>(
      null,
    );

  const [resultadoFinal, setResultadoFinal] =
    useState<ResultadoFinalIndicadores | null>(
      null,
    );

  const [risco, setRisco] =
    useState<PriorizacaoRisco | null>(null);

  const [painel, setPainel] =
    useState<PainelRotativo | null>(null);

  const [tendencias, setTendencias] =
    useState<TendenciasRotativo | null>(null);

  const [carregando, setCarregando] =
    useState(false);

  const [erro, setErro] =
    useState<string | null>(null);

  const requisicaoIndicadoresAtual =
    useRef(0);

  const carregarInventarioAtual =
    useCallback(async () => {
      setCarregando(true);
      setErro(null);
      setInventarioSelecionado(null);
      setAcompanhamento(null);
      setProdutividade(null);
      setResultadoFinal(null);
      setRisco(null);
      setPainel(null);
      setTendencias(null);

      try {
        if (!idInventario) {
          throw new Error(
            "Nenhum invent\u00e1rio foi selecionado. Acesse o Controle de Invent\u00e1rios e abra o invent\u00e1rio desejado.",
          );
        }

        const dados =
          await listarInventariosIndicadores();

        const inventarioEncontrado =
          dados.find(
            (item) =>
              item.id_inventario ===
              idInventario,
          );

        if (!inventarioEncontrado) {
          throw new Error(
            `O invent\u00e1rio #${idInventario} n\u00e3o est\u00e1 dispon\u00edvel para consulta dos indicadores.`,
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
            : "Falha ao carregar o invent\u00e1rio atual.",
        );
      } finally {
        setCarregando(false);
      }
    }, [idInventario]);

  const carregarIndicadores = useCallback(async () => {
    if (!inventarioSelecionado) return;

    const idRequisicao = ++requisicaoIndicadoresAtual.current;

    const requisicaoAindaAtual = () =>
      idRequisicao === requisicaoIndicadoresAtual.current;

    setCarregando(true);
    setErro(null);

    // Evita exibir indicadores pertencentes ao inventario anterior
    // enquanto o novo contexto ainda esta sendo carregado.
    setAcompanhamento(null);
    setProdutividade(null);
    setResultadoFinal(null);
    setRisco(null);
    setPainel(null);
    setTendencias(null);

    try {
      const [dadosAcompanhamento, dadosProdutividade, dadosRisco] =
        await Promise.all([
          buscarAcompanhamento(
            inventarioSelecionado.id_inventario,
          ),
          buscarProdutividade(
            inventarioSelecionado.id_inventario,
          ),
          buscarPriorizacaoRisco(
            inventarioSelecionado.cliente_id,
            inventarioSelecionado.armazem,
            10,
          ),
        ]);

      if (!requisicaoAindaAtual()) return;

      setAcompanhamento(dadosAcompanhamento);
      setProdutividade(dadosProdutividade);
      setRisco(dadosRisco);

      if (inventarioSelecionado.status === "FINALIZADO") {
        try {
          const dadosResultadoFinal =
            await buscarResultadoFinalIndicadores(
              inventarioSelecionado.id_inventario,
            );

          if (!requisicaoAindaAtual()) return;

          setResultadoFinal(dadosResultadoFinal);
        } catch {
          if (!requisicaoAindaAtual()) return;

          setResultadoFinal(null);
        }
      } else {
        if (!requisicaoAindaAtual()) return;

        setResultadoFinal(null);
      }

      if (inventarioSelecionado.tipo === "ROTATIVO") {
        const [dadosPainel, dadosTendencias] =
          await Promise.all([
            buscarPainelRotativo(
              inventarioSelecionado.cliente_id,
              inventarioSelecionado.armazem,
            ),
            buscarTendenciasRotativo(
              inventarioSelecionado.cliente_id,
              inventarioSelecionado.armazem,
            ),
          ]);

        if (!requisicaoAindaAtual()) return;

        setPainel(dadosPainel);
        setTendencias(dadosTendencias);
      } else {
        if (!requisicaoAindaAtual()) return;

        setPainel(null);
        setTendencias(null);
      }
    } catch (e) {
      if (!requisicaoAindaAtual()) return;

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
  }, [inventarioSelecionado]);

  useEffect(() => {
    void carregarInventarioAtual();
  }, [carregarInventarioAtual]);

  useEffect(() => {
    void carregarIndicadores();
  }, [carregarIndicadores]);

  return (
    <div className="space-y-6 p-4 md:p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <BarChart3 className="h-6 w-6" />
            <h1 className="text-2xl font-bold">Indicadores</h1>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Acompanhamento operacional, produtividade, acuracidade, risco e inteligência do inventário.
          </p>
        </div>

        <div className="flex flex-col gap-2 sm:flex-row">
          <button
            type="button"
            onClick={() => void carregarIndicadores()}
            disabled={!inventarioSelecionado || carregando}
            className="inline-flex items-center justify-center gap-2 rounded-md border px-3 py-2 text-sm font-medium disabled:opacity-50"
          >
            <RefreshCcw className={`h-4 w-4 ${carregando ? "animate-spin" : ""}`} />
            Atualizar
          </button>
        </div>
      </div>

      {erro ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          {erro}
        </div>
      ) : null}

      {inventarioSelecionado ? (
        <div className="rounded-xl border bg-card p-4">
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-5">
            <div><p className="text-xs text-muted-foreground">Inventário</p><p className="font-medium">{inventarioSelecionado.codigo_inventario}</p></div>
            <div><p className="text-xs text-muted-foreground">Cliente</p><p className="font-medium">{inventarioSelecionado.cliente}</p></div>
            <div><p className="text-xs text-muted-foreground">Armazém</p><p className="font-medium">{inventarioSelecionado.armazem}</p></div>
            <div><p className="text-xs text-muted-foreground">Tipo</p><p className="font-medium">{inventarioSelecionado.tipo}</p></div>
            <div><p className="text-xs text-muted-foreground">Status</p><p className="font-medium">{inventarioSelecionado.status}</p></div>
          </div>
        </div>
      ) : null}

      {acompanhamento ? (
        <Section titulo="Acompanhamento operacional">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
            <Card titulo="Itens processados" valor={numero(acompanhamento.progresso.itens.processados)} detalhe={`${percentual(acompanhamento.progresso.itens.percentual)} do planejado`} />
            <Card titulo="Localizações concluídas" valor={numero(acompanhamento.progresso.localizacoes.concluidas)} detalhe={`${percentual(acompanhamento.progresso.localizacoes.percentual)} do planejado`} />
            <Card titulo="Quantidade registrada" valor={numero(acompanhamento.volume.quantidade_registrada, 2)} />
            <Card titulo="Bipagens" valor={numero(acompanhamento.atividade.total_bipagens)} />
            <Card titulo="Operadores" valor={numero(acompanhamento.atividade.operadores_com_contagem)} />
            <Card titulo="Tempo da rodada" valor={acompanhamento.tempo.tempo_formatado} detalhe={`Rodada ${acompanhamento.numero_rodada} · ${acompanhamento.status_rodada}`} />
          </div>
        </Section>
      ) : null}

      {produtividade ? (
        <Section titulo="Produtividade">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Card titulo="Tempo operacional" valor={produtividade.tempo.tempo_operacional_formatado} />
            <Card titulo="Bipagens/h operacional" valor={numero(produtividade.produtividade.operacional.bipagens_hora, 2)} />
            <Card titulo="Quantidade/h operacional" valor={numero(produtividade.produtividade.operacional.quantidade_hora, 2)} />
            <Card titulo="Tempo médio/localização" valor={produtividade.tempo.tempo_medio_localizacao_formatado} />
          </div>

          {produtividade.qualidade_dado_operador.possui_bipagens_sem_usuario ? (
            <div className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-sm">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                Existem {produtividade.qualidade_dado_operador.bipagens_sem_usuario} bipagens sem usuário identificado.
              </span>
            </div>
          ) : null}
        </Section>
      ) : null}

      {resultadoFinal ? (
        <Section titulo="Resultado final">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
            <Card titulo="Acuracidade" valor={percentual(resultadoFinal.resumo.acuracidade_percentual)} />
            <Card titulo="Itens" valor={resultadoFinal.resumo.total_itens} />
            <Card titulo="OK" valor={resultadoFinal.resumo.ok} />
            <Card titulo="NOK" valor={resultadoFinal.resumo.nok} />
            <Card titulo="Faltas" valor={resultadoFinal.resumo.faltas} />
            <Card titulo="Sobras" valor={resultadoFinal.resumo.sobras} />
            <Card titulo="Divergências" valor={resultadoFinal.resumo.divergencias} />
          </div>
        </Section>
      ) : null}

      {risco ? (
        <Section titulo="Risco e priorização">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <Card titulo="Score médio" valor={numero(risco.resumo.score_medio, 2)} />
            <Card titulo="Crítico" valor={risco.resumo.critico} />
            <Card titulo="Alto" valor={risco.resumo.alto} />
            <Card titulo="Médio" valor={risco.resumo.medio} />
            <Card titulo="Baixo" valor={risco.resumo.baixo} />
          </div>

          <div className="overflow-x-auto rounded-xl border">
            <table className="w-full min-w-[900px] text-sm">
              <thead className="bg-muted/50 text-left">
                <tr>
                  <th className="px-3 py-2">Prioridade</th><th className="px-3 py-2">Localização</th>
                  <th className="px-3 py-2">Código</th><th className="px-3 py-2">Lote</th>
                  <th className="px-3 py-2">Score</th><th className="px-3 py-2">Risco</th>
                  <th className="px-3 py-2">Taxa divergência</th><th className="px-3 py-2">Padrão</th>
                </tr>
              </thead>
              <tbody>
                {risco.ranking_prioridade.map((item) => (
                  <tr key={`${item.localizacao}-${item.codigo}-${item.lote}`} className="border-t">
                    <td className="px-3 py-2">{item.prioridade_contagem}</td>
                    <td className="px-3 py-2 font-medium">{item.localizacao}</td>
                    <td className="px-3 py-2">{item.codigo}</td>
                    <td className="px-3 py-2">{item.lote}</td>
                    <td className="px-3 py-2">{numero(item.score_risco, 2)}</td>
                    <td className="px-3 py-2">{item.classificacao}</td>
                    <td className="px-3 py-2">{percentual(item.historico.taxa_divergencia_percentual)}</td>
                    <td className="px-3 py-2">{item.historico.padrao ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      ) : null}

      {painel?.possui_ciclo_aberto ? (
        <Section titulo="Inteligência do ciclo rotativo">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Card titulo="Progresso do ciclo" valor={percentual(painel.progresso.percentual_processado)} detalhe={`${painel.progresso.processadas}/${painel.progresso.total_localizacoes} localizações processadas`} />
            <Card titulo="Tratativas pendentes" valor={painel.tratativas.ocorrencias_pendentes} detalhe={`${painel.tratativas.grupos_pendentes} grupos`} />
            <Card titulo="Alertas de tendência" valor={painel.tendencias.alertas} detalhe={`${painel.tendencias.deteriorando} deteriorando`} />
            <Card titulo="Resoluções eficazes" valor={`${painel.eficacia.eficazes}/${painel.eficacia.resolucoes_avaliadas}`} detalhe={`${painel.eficacia.nao_eficazes} não eficazes`} />
          </div>

                    {painel.top_prioridades.length ? (
            <div className="rounded-xl border">
              <div className="border-b p-4">
                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h3 className="font-semibold">Prioridades do ciclo</h3>
                    <p className="text-xs text-muted-foreground">
                      Ordem operacional sugerida pelo ciclo rotativo.
                    </p>
                  </div>

                  <p className="text-xs text-muted-foreground">
                    {painel.risco.sugestoes_por_risco} por risco {"\u00b7"}{" "}
                    {painel.risco.sugestoes_por_cobertura} por cobertura
                  </p>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px] text-sm">
                  <thead className="bg-muted/50 text-left">
                    <tr>
                      <th className="px-3 py-2">Prioridade</th>
                      <th className="px-3 py-2">{"Localiza\u00e7\u00e3o"}</th>
                      <th className="px-3 py-2">Tipo</th>
                      <th className="px-3 py-2">Score</th>
                      <th className="px-3 py-2">Risco</th>
                      <th className="px-3 py-2">Motivo</th>
                    </tr>
                  </thead>

                  <tbody>
                    {painel.top_prioridades.map((item) => (
                      <tr
                        key={item.id_ciclo_localizacao}
                        className="border-t"
                      >
                        <td className="px-3 py-2 font-semibold">
                          {item.prioridade ?? "-"}
                        </td>

                        <td className="px-3 py-2 font-medium">
                          {item.localizacao}
                        </td>

                        <td className="px-3 py-2">
                          {item.tipo_sugestao === "RISCO"
                            ? "Risco"
                            : item.tipo_sugestao === "COBERTURA_CICLO"
                              ? "Cobertura"
                              : "-"}
                        </td>

                        <td className="px-3 py-2">
                          {numero(item.score_risco, 2)}
                        </td>

                        <td className="px-3 py-2">
                          {item.classificacao_risco ?? "-"}
                        </td>

                        <td className="px-3 py-2 text-muted-foreground">
                          {item.motivo ?? "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}

<div className="grid gap-3 lg:grid-cols-2">
            {painel.alerta_principal ? (
              <div className="rounded-xl border p-4">
                <div className="flex items-center gap-2 font-semibold"><ShieldAlert className="h-4 w-4" />Alerta principal</div>
                <p className="mt-3 text-sm"><strong>{painel.alerta_principal.localizacao}</strong> · {painel.alerta_principal.classificacao_tendencia} · risco {numero(painel.alerta_principal.score_risco, 2)} ({painel.alerta_principal.classificacao_risco})</p>
                <p className="mt-2 text-sm text-muted-foreground">{painel.alerta_principal.motivo_principal}</p>
              </div>
            ) : null}

            {painel.alerta_tratativa ? (
              <div className="rounded-xl border p-4">
                <div className="flex items-center gap-2 font-semibold"><PackageCheck className="h-4 w-4" />Alerta de tratativa</div>
                <p className="mt-3 text-sm"><strong>{painel.alerta_tratativa.localizacao}</strong> · {painel.alerta_tratativa.ocorrencias_pendentes} ocorrências pendentes</p>
                <p className="mt-2 text-sm text-muted-foreground">Risco {numero(painel.alerta_tratativa.score_risco, 2)} · {painel.alerta_tratativa.classificacao_risco}</p>
              </div>
            ) : null}
          </div>
        </Section>
      ) : null}

      {tendencias?.tendencias?.length ? (
        <Section titulo="Tendências por localização">
          <div className="overflow-x-auto rounded-xl border">
            <table className="w-full min-w-[980px] text-sm">
              <thead className="bg-muted/50 text-left">
                <tr>
                  <th className="px-3 py-2">Localização</th><th className="px-3 py-2">Tendência</th>
                  <th className="px-3 py-2">Direção</th><th className="px-3 py-2">Risco</th>
                  <th className="px-3 py-2">Evidência</th><th className="px-3 py-2">Recorrência</th>
                  <th className="px-3 py-2">Pendências</th><th className="px-3 py-2">Última eficácia</th>
                </tr>
              </thead>
              <tbody>
                {tendencias.tendencias.map((item) => (
                  <tr key={item.id_ciclo_localizacao} className="border-t">
                    <td className="px-3 py-2 font-medium">{item.localizacao}</td>
                    <td className="px-3 py-2">
                      <span className="inline-flex items-center gap-1">
                        {item.direcao === "PIORA" ? <TrendingDown className="h-4 w-4" /> : item.direcao === "MELHORA" ? <TrendingUp className="h-4 w-4" /> : <Gauge className="h-4 w-4" />}
                        {item.classificacao_tendencia}
                      </span>
                    </td>
                    <td className="px-3 py-2">{item.direcao}</td>
                    <td className="px-3 py-2">{numero(item.score_risco, 2)} · {item.classificacao_risco}</td>
                    <td className="px-3 py-2">{item.nivel_evidencia}</td>
                    <td className="px-3 py-2">{item.recorrencia.possui_recorrencia_item_lote ? "Sim" : "Não"}</td>
                    <td className="px-3 py-2">{item.tratativa.ocorrencias_pendentes}</td>
                    <td className="px-3 py-2">{item.eficacia.ultima_classificacao ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      ) : null}

      {!carregando && inventarioSelecionado && !acompanhamento && !produtividade && !erro ? (
        <div className="rounded-xl border p-6 text-center text-sm text-muted-foreground">
          Nenhum indicador disponível para o inventário selecionado.
        </div>
      ) : null}
    </div>
  );
}
