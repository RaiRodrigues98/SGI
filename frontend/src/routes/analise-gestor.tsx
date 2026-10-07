import { createFileRoute, Link } from "@tanstack/react-router";
import { useNavigate } from "@tanstack/react-router";
import {
  ArrowLeft,
  BarChart3,
  CheckCircle2,
  ClipboardCheck,
  Loader2,
  RefreshCcw,
  RotateCcw,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  obterInventarioAtual,
  salvarInventarioAtual,
} from "@/lib/inventarioAtual";
import { obterUsuarioSalvo } from "@/services/authService";
import {
  buscarAnaliseGestor,
  finalizarInventarioGerencial,
  registrarDecisaoGestor,
  type AnaliseGestor,
  type DecisaoGestor,
  type ItemAnaliseGestor,
} from "@/services/gestorService";
import {
  buscarResultadoFinalIndicadores,
  type ResultadoFinalIndicadores,
} from "@/services/indicadoresService";
import { gerarProximaRodada } from "@/services/rodadasService";

interface AnaliseGestorSearch {
  inventario?: number;
}

type FiltroSituacao =
  "TODOS" | "PENDENTES" | "RESOLVIDOS" | "RECONTAGEM" | "OK";

export const Route = createFileRoute("/analise-gestor")({
  validateSearch: (search: Record<string, unknown>): AnaliseGestorSearch => {
    const inventario = Number(search["inventario"]);
    return Number.isSafeInteger(inventario) && inventario > 0
      ? { inventario }
      : {};
  },
  head: () => ({
    meta: [{ title: "An\u00e1lise Gerencial \u2014 SGI" }],
  }),
  component: AnaliseGestorPage,
});

function AnaliseGestorPage() {
  const navigate = useNavigate();

  const { inventario: inventarioUrl } = Route.useSearch();
  const idInventario = inventarioUrl ?? obterInventarioAtual();

  const [analise, setAnalise] = useState<AnaliseGestor | null>(null);
  const [resultadoFinal, setResultadoFinal] =
    useState<ResultadoFinalIndicadores | null>(null);
  const [erroResultadoFinal, setErroResultadoFinal] = useState<string | null>(
    null,
  );
  const [carregando, setCarregando] = useState(true);
  const [atualizando, setAtualizando] = useState(false);
  const [gerandoRecontagem, setGerandoRecontagem] = useState(false);
  const [finalizandoInventario, setFinalizandoInventario] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [pesquisa, setPesquisa] = useState("");
  const [filtro, setFiltro] = useState<FiltroSituacao>("PENDENTES");
  const [itemSelecionado, setItemSelecionado] =
    useState<ItemAnaliseGestor | null>(null);

  const usuario = obterUsuarioSalvo();
  const permissoes = new Set(
    (usuario?.permissoes ?? [])
      .map((permissao) =>
        typeof permissao === "string" ? permissao : permissao.codigo,
      )
      .filter(Boolean),
  );
  const podeDecidir = permissoes.has("GESTOR_DECIDIR");
  const podeGerarRodada = permissoes.has("RODADA_GERAR");
  const podeFinalizarPorPerfil =
    permissoes.has("INVENTARIO_FINALIZAR") || podeDecidir;

  const carregar = useCallback(
    async (signal?: AbortSignal, silencioso = false) => {
      if (
        !idInventario ||
        !Number.isSafeInteger(idInventario) ||
        idInventario <= 0
      ) {
        setAnalise(null);
        setErro(
          "Nenhum inventário foi selecionado. Abra um inventário oficial pelo Controle de Inventários.",
        );
        setCarregando(false);
        return;
      }

      silencioso ? setAtualizando(true) : setCarregando(true);
      setErro(null);

      try {
        const dados = await buscarAnaliseGestor(idInventario, signal);
        if (signal?.aborted) return;

        let resultadoAtual: ResultadoFinalIndicadores | null = null;
        let erroResultadoAtual: string | null = null;

        if (dados.status_inventario.toUpperCase() === "FINALIZADO") {
          try {
            resultadoAtual =
              await buscarResultadoFinalIndicadores(idInventario);
          } catch (falhaResultado: unknown) {
            erroResultadoAtual = mensagemErro(falhaResultado);
          }
        }

        if (signal?.aborted) return;
        setAnalise(dados);
        setResultadoFinal(resultadoAtual);
        setErroResultadoFinal(erroResultadoAtual);
        salvarInventarioAtual(dados.id_inventario, "OFICIAL");
      } catch (falha: unknown) {
        if (signal?.aborted) return;
        setAnalise(null);
        setResultadoFinal(null);
        setErroResultadoFinal(null);
        setErro(mensagemErro(falha));
      } finally {
        if (!signal?.aborted) {
          setCarregando(false);
          setAtualizando(false);
        }
      }
    },
    [idInventario],
  );

  useEffect(() => {
    const controller = new AbortController();
    void carregar(controller.signal);
    return () => controller.abort();
  }, [carregar]);

  async function gerarNovaRecontagem() {
    if (
      !analise ||
      !analise.pode_gerar_nova_recontagem ||
      !podeGerarRodada ||
      gerandoRecontagem
    ) {
      return;
    }

    const confirmou = window.confirm(
      `Gerar uma nova rodada com ${analise.resumo.nova_recontagem} item(ns) marcado(s) para recontagem?`,
    );
    if (!confirmou) return;

    setGerandoRecontagem(true);

    try {
      const resposta = await gerarProximaRodada(analise.id_inventario);
      const numeroRodada = resposta.proxima_rodada.numero_rodada;

      toast.success(
        resposta.proxima_rodada.mensagem ||
          `Rodada R${numeroRodada} criada para nova recontagem.`,
      );
      setFiltro("TODOS");
      await carregar(undefined, true);
    } catch (falha: unknown) {
      toast.error(mensagemErro(falha));
    } finally {
      setGerandoRecontagem(false);
    }
  }

  async function finalizarInventario() {
    if (
      !analise ||
      analise.status_inventario === "FINALIZADO" ||
      !analise.operacao_concluida ||
      !analise.pode_finalizar_inventario ||
      !podeFinalizarPorPerfil ||
      finalizandoInventario
    ) {
      return;
    }

    const confirmou = window.confirm(
      `Finalizar definitivamente o inventário ${analise.codigo_inventario}? Esta ação encerra o fluxo operacional.`,
    );
    if (!confirmou) return;

    setFinalizandoInventario(true);

    try {
      const resposta = await finalizarInventarioGerencial(
        analise.id_inventario,
      );
      toast.success(resposta.mensagem || "Inventário finalizado com sucesso.");
      await navigate({
        to: "/historico",
        search: {
          inventario:
            analise.id_inventario,
          aba: "resultado-final",
        },
      });
    } catch (falha: unknown) {
      toast.error(mensagemErro(falha));
    } finally {
      setFinalizandoInventario(false);
    }
  }

  const itensFiltrados = useMemo(() => {
    if (!analise) return [];
    const termo = pesquisa.trim().toLocaleLowerCase("pt-BR");

    return analise.itens.filter((item) => {
      const correspondePesquisa =
        !termo ||
        item.codigo.toLocaleLowerCase("pt-BR").includes(termo) ||
        item.lote.toLocaleLowerCase("pt-BR").includes(termo) ||
        (item.descricao ?? "").toLocaleLowerCase("pt-BR").includes(termo);

      const correspondeFiltro =
        filtro === "TODOS" ||
        (filtro === "PENDENTES" && item.pendente_decisao_gestor) ||
        (filtro === "RESOLVIDOS" &&
          item.requer_decisao_gestor &&
          item.resolvido_gestor) ||
        (filtro === "RECONTAGEM" && item.nova_recontagem) ||
        (filtro === "OK" && !item.requer_decisao_gestor);

      return correspondePesquisa && correspondeFiltro;
    });
  }, [analise, filtro, pesquisa]);

  return (
    <main className="mx-auto w-full max-w-[1600px] space-y-5 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          to="/controle-inventarios"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Voltar para Controle de Inventários
        </Link>

        <Button
          type="button"
          variant="outline"
          disabled={!analise || carregando || atualizando}
          onClick={() => void carregar(undefined, true)}
        >
          <RefreshCcw
            className={`size-4 ${atualizando ? "animate-spin" : ""}`}
          />
          Atualizar
        </Button>
      </div>

      <header className="rounded-xl border bg-card p-5 shadow-sm">
        <div className="flex items-start gap-3">
          <ShieldCheck className="mt-0.5 size-7 shrink-0 text-primary" />
          <div>
            <h1 className="text-xl font-bold tracking-tight text-primary">
              Análise Gerencial
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Decisão final das divergências do inventário oficial por código e
              lote.
            </p>
          </div>
        </div>
      </header>

      {erro && <Estado mensagem={erro} erro />}
      {carregando && (
        <Estado mensagem="Carregando análise gerencial..." carregando />
      )}

      {!carregando && analise && (
        <>
          <section className="rounded-xl border bg-card p-5 shadow-sm">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              <Info titulo="Inventário" valor={analise.codigo_inventario} />
              <Info
                titulo="Status"
                valor={formatarTecnico(analise.status_inventario)}
              />
              <Info titulo="Rodada atual" valor={`R${analise.rodada_atual}`} />
              <Info titulo="Conciliação" valor="Código + lote" />
              <Info
                titulo="Operação"
                valor={
                  analise.operacao_concluida
                    ? "Concluída"
                    : "Rodada em andamento"
                }
              />
            </div>
          </section>

          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
            <Kpi
              titulo="Total"
              valor={analise.resumo.total_itens}
              onClick={() => setFiltro("TODOS")}
            />
            <Kpi
              titulo="OK"
              valor={analise.resumo.ok}
              onClick={() => setFiltro("OK")}
            />
            <Kpi titulo="Faltas" valor={analise.resumo.faltas} />
            <Kpi titulo="Sobras" valor={analise.resumo.sobras} />
            <Kpi titulo="Divergências" valor={analise.resumo.divergencias} />
            <Kpi
              titulo="Sem decisão"
              valor={analise.resumo.itens_sem_decisao}
              ativo={filtro === "PENDENTES"}
              onClick={() => setFiltro("PENDENTES")}
            />
            <Kpi
              titulo="Recontagem"
              valor={analise.resumo.nova_recontagem}
              ativo={filtro === "RECONTAGEM"}
              onClick={() => setFiltro("RECONTAGEM")}
            />
          </section>

          {!podeDecidir && (
            <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
              Seu perfil pode consultar esta análise, mas não possui a permissão
              GESTOR_DECIDIR.
            </div>
          )}

          <SituacaoFinal
            analise={analise}
            podeGerarRodada={podeGerarRodada}
            gerandoRecontagem={gerandoRecontagem}
            onGerarRecontagem={gerarNovaRecontagem}
            podeFinalizarPorPerfil={podeFinalizarPorPerfil}
            finalizandoInventario={finalizandoInventario}
            onFinalizarInventario={finalizarInventario}
          />

          {analise.status_inventario.toUpperCase() === "FINALIZADO" && (
            <ResultadoFinalPainel
              resultado={resultadoFinal}
              erro={erroResultadoFinal}
            />
          )}

          <section className="space-y-4 rounded-xl border bg-card p-5 shadow-sm">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <h2 className="font-semibold">Itens do inventário</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {itensFiltrados.length} de {analise.itens.length} item(ns)
                  exibido(s).
                </p>
              </div>

              <div className="flex flex-col gap-2 sm:flex-row">
                <label className="relative block">
                  <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    value={pesquisa}
                    onChange={(evento) => setPesquisa(evento.target.value)}
                    placeholder="Código, lote ou descrição"
                    className="h-10 w-full min-w-64 rounded-md border bg-background pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring"
                  />
                </label>

                <select
                  value={filtro}
                  onChange={(evento) =>
                    setFiltro(evento.target.value as FiltroSituacao)
                  }
                  className="h-10 rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="TODOS">Todos</option>
                  <option value="PENDENTES">Aguardando decisão</option>
                  <option value="RESOLVIDOS">Resolvidos pelo gestor</option>
                  <option value="RECONTAGEM">Nova recontagem</option>
                  <option value="OK">Itens OK</option>
                </select>
              </div>
            </div>

            {itensFiltrados.length === 0 ? (
              <Estado mensagem="Nenhum item corresponde aos filtros selecionados." />
            ) : (
              <div className="overflow-x-auto rounded-lg border">
                <table className="min-w-[1200px] w-full text-left text-sm">
                  <thead className="bg-muted/50">
                    <tr>
                      <Th>Código</Th>
                      <Th>Lote</Th>
                      <Th>Descrição</Th>
                      <Th>Estoque</Th>
                      {analise.rodadas.map((rodada) => (
                        <Th key={rodada.id_rodada}>R{rodada.numero_rodada}</Th>
                      ))}
                      <Th>Situação</Th>
                      <Th>Decisão atual</Th>
                      <Th>Ação</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {itensFiltrados.map((item) => (
                      <tr key={item.chave} className="border-t align-top">
                        <Td classe="font-mono font-semibold text-primary">
                          {item.codigo}
                        </Td>
                        <Td>{item.lote || "-"}</Td>
                        <Td classe="min-w-56">
                          {item.descricao ?? "Produto sem descrição"}
                        </Td>
                        <Td>{formatarNumero(item.qtd_estoque)}</Td>
                        {analise.rodadas.map((rodada) => {
                          const historico = item.historico.find(
                            (registro) =>
                              registro.id_rodada === rodada.id_rodada,
                          );
                          return (
                            <Td key={rodada.id_rodada}>
                              <div className="font-semibold">
                                {historico?.participou
                                  ? formatarNumero(historico.quantidade)
                                  : "-"}
                              </div>
                              {historico && (
                                <div className="mt-1 text-xs text-muted-foreground">
                                  {formatarTecnico(historico.status)}
                                </div>
                              )}
                            </Td>
                          );
                        })}
                        <Td>
                          <Badge valor={item.situacao_atual} />
                        </Td>
                        <Td classe="min-w-48">
                          <DecisaoAtual item={item} />
                        </Td>
                        <Td>
                          {item.requer_decisao_gestor ? (
                            <Button
                              type="button"
                              size="sm"
                              variant={
                                item.decisao_gestor.possui_decisao
                                  ? "outline"
                                  : "default"
                              }
                              disabled={!podeDecidir}
                              onClick={() => setItemSelecionado(item)}
                            >
                              {item.decisao_gestor.possui_decisao
                                ? "Alterar"
                                : "Decidir"}
                            </Button>
                          ) : (
                            <span className="text-xs text-muted-foreground">
                              Não necessário
                            </span>
                          )}
                        </Td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}

      {itemSelecionado && analise && (
        <ModalDecisao
          idInventario={analise.id_inventario}
          item={itemSelecionado}
          onFechar={() => setItemSelecionado(null)}
          onSalvo={async (mensagem) => {
            setItemSelecionado(null);
            toast.success(mensagem);
            await carregar(undefined, true);
          }}
        />
      )}
    </main>
  );
}

function SituacaoFinal({
  analise,
  podeGerarRodada,
  gerandoRecontagem,
  onGerarRecontagem,
  podeFinalizarPorPerfil,
  finalizandoInventario,
  onFinalizarInventario,
}: {
  analise: AnaliseGestor;
  podeGerarRodada: boolean;
  gerandoRecontagem: boolean;
  onGerarRecontagem: () => Promise<void>;
  podeFinalizarPorPerfil: boolean;
  finalizandoInventario: boolean;
  onFinalizarInventario: () => Promise<void>;
}) {
  if (analise.status_inventario === "FINALIZADO") {
    return (
      <div className="flex gap-3 rounded-lg border border-emerald-300 bg-emerald-50 p-4 text-sm text-emerald-900">
        <CheckCircle2 className="mt-0.5 size-5 shrink-0" />
        <div>
          <strong>Inventário finalizado.</strong>
          <p className="mt-1">
            As decisões gerenciais e o resultado final estão preservados para
            consulta.
          </p>
        </div>
      </div>
    );
  }

  if (!analise.operacao_concluida) {
    return (
      <div className="flex gap-3 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
        <RotateCcw className="mt-0.5 size-5 shrink-0" />
        <div>
          <strong>Operação ainda não concluída.</strong>
          <p className="mt-1">
            Finalize as rodadas operacionais antes de encerrar o inventário.
          </p>
        </div>
      </div>
    );
  }

  if (analise.pode_gerar_nova_recontagem) {
    return (
      <div className="flex flex-col gap-4 rounded-lg border border-blue-300 bg-blue-50 p-4 text-sm text-blue-900 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-3">
          <RotateCcw className="mt-0.5 size-5 shrink-0" />
          <div>
            <strong>Nova recontagem necessária.</strong>
            <p className="mt-1">
              {analise.resumo.nova_recontagem} item(ns) foi(ram) selecionado(s)
              para a próxima rodada.
            </p>
            {!podeGerarRodada && (
              <p className="mt-2 text-xs font-semibold">
                Permissão RODADA_GERAR necessária para criar a rodada.
              </p>
            )}
          </div>
        </div>

        <Button
          type="button"
          disabled={!podeGerarRodada || gerandoRecontagem}
          onClick={() => void onGerarRecontagem()}
          className="shrink-0"
        >
          {gerandoRecontagem ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <RotateCcw className="size-4" />
          )}
          {gerandoRecontagem
            ? "Gerando recontagem..."
            : "Gerar nova recontagem"}
        </Button>
      </div>
    );
  }

  if (analise.pode_finalizar_inventario) {
    return (
      <div className="flex flex-col gap-4 rounded-lg border border-emerald-300 bg-emerald-50 p-4 text-sm text-emerald-900 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-3">
          <CheckCircle2 className="mt-0.5 size-5 shrink-0" />
          <div>
            <strong>Decisões concluídas.</strong>
            <p className="mt-1">
              Não existem decisões pendentes ou solicitações de nova recontagem.
              O inventário pode ser finalizado.
            </p>
            {!podeFinalizarPorPerfil && (
              <p className="mt-2 text-xs font-semibold">
                Permissão de finalização necessária para concluir o inventário.
              </p>
            )}
          </div>
        </div>

        <Button
          type="button"
          disabled={!podeFinalizarPorPerfil || finalizandoInventario}
          onClick={() => void onFinalizarInventario()}
          className="shrink-0 bg-emerald-700 text-white hover:bg-emerald-800"
        >
          {finalizandoInventario ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <CheckCircle2 className="size-4" />
          )}
          {finalizandoInventario ? "Finalizando..." : "Finalizar inventário"}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex gap-3 rounded-lg border bg-muted/30 p-4 text-sm">
      <ClipboardCheck className="mt-0.5 size-5 shrink-0 text-primary" />
      <div>
        <strong>Decisões pendentes.</strong>
        <p className="mt-1 text-muted-foreground">
          Resolva todos os itens obrigatórios antes de finalizar ou gerar uma
          nova rodada.
        </p>
      </div>
    </div>
  );
}

function ResultadoFinalPainel({
  resultado,
  erro,
}: {
  resultado: ResultadoFinalIndicadores | null;
  erro: string | null;
}) {
  if (erro) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
        Não foi possível carregar o resultado final: {erro}
      </div>
    );
  }

  if (!resultado) {
    return <Estado mensagem="Resultado final ainda não disponível." />;
  }

  return (
    <section className="space-y-5 rounded-xl border bg-card p-5 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <BarChart3 className="mt-0.5 size-6 shrink-0 text-primary" />
          <div>
            <h2 className="font-semibold text-primary">Resultado final</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Consolidação oficial gravada no encerramento do inventário.
            </p>
          </div>
        </div>

        <Button asChild variant="outline" size="sm">
          <Link
            to="/indicadores"
            search={{ inventario: resultado.id_inventario }}
          >
            <BarChart3 className="size-4" />
            Abrir indicadores
          </Link>
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
        <ResultadoKpi
          titulo="Total"
          valor={formatarNumero(resultado.resumo.total_itens)}
        />
        <ResultadoKpi
          titulo="OK"
          valor={formatarNumero(resultado.resumo.ok)}
          positivo
        />
        <ResultadoKpi
          titulo="NOK"
          valor={formatarNumero(resultado.resumo.nok)}
        />
        <ResultadoKpi
          titulo="Faltas"
          valor={formatarNumero(resultado.resumo.faltas)}
        />
        <ResultadoKpi
          titulo="Sobras"
          valor={formatarNumero(resultado.resumo.sobras)}
        />
        <ResultadoKpi
          titulo="Divergências"
          valor={formatarNumero(resultado.resumo.divergencias)}
        />
        <ResultadoKpi
          titulo="Acuracidade"
          valor={`${formatarPercentual(resultado.resumo.acuracidade_percentual)}%`}
          positivo
        />
      </div>

      <div className="grid gap-4 border-t pt-4 sm:grid-cols-2 lg:grid-cols-4">
        <Info titulo="Inventário" valor={resultado.codigo_inventario} />
        <Info titulo="Rodada final" valor={`R${resultado.rodada_final}`} />
        <Info titulo="Finalizado por" valor={resultado.finalizado_por ?? "-"} />
        <Info
          titulo="Finalizado em"
          valor={formatarDataHora(resultado.data_hora_finalizacao)}
        />
      </div>
    </section>
  );
}

function ResultadoKpi({
  titulo,
  valor,
  positivo = false,
}: {
  titulo: string;
  valor: string;
  positivo?: boolean;
}) {
  return (
    <div
      className={`rounded-lg border p-4 ${
        positivo
          ? "border-emerald-300 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950/20"
          : "bg-background"
      }`}
    >
      <p className="text-xs font-semibold uppercase text-muted-foreground">
        {titulo}
      </p>
      <p
        className={`mt-1 text-2xl font-bold ${
          positivo ? "text-emerald-700 dark:text-emerald-300" : "text-primary"
        }`}
      >
        {valor}
      </p>
    </div>
  );
}

function ModalDecisao({
  idInventario,
  item,
  onFechar,
  onSalvo,
}: {
  idInventario: number;
  item: ItemAnaliseGestor;
  onFechar: () => void;
  onSalvo: (mensagem: string) => Promise<void>;
}) {
  const decisaoAtual = item.decisao_gestor.decisao ?? "ACEITAR_ESTOQUE";
  const [decisao, setDecisao] = useState<DecisaoGestor>(decisaoAtual);
  const [quantidade, setQuantidade] = useState(
    item.decisao_gestor.decisao === "ACEITAR_CONTAGEM" &&
      item.decisao_gestor.quantidade_aprovada !== null
      ? String(item.decisao_gestor.quantidade_aprovada)
      : "",
  );
  const [justificativa, setJustificativa] = useState(
    item.decisao_gestor.justificativa ?? "",
  );
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function confirmar() {
    const quantidadeAprovada =
      quantidade.trim() === "" ? null : Number(quantidade);
    setSalvando(true);
    setErro(null);

    try {
      const resposta = await registrarDecisaoGestor(idInventario, {
        codigo: item.codigo,
        lote: item.lote,
        decisao,
        quantidade_aprovada: quantidadeAprovada,
        justificativa,
      });
      await onSalvo(resposta.mensagem);
    } catch (falha: unknown) {
      setErro(mensagemErro(falha));
      setSalvando(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-4"
      role="presentation"
      onMouseDown={(evento) => {
        if (evento.target === evento.currentTarget && !salvando) onFechar();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="titulo-decisao-gestor"
        className="max-h-[92vh] w-full max-w-xl overflow-y-auto rounded-xl border bg-background shadow-2xl"
      >
        <div className="flex items-start justify-between border-b p-5">
          <div>
            <h2 id="titulo-decisao-gestor" className="font-bold text-primary">
              Decisão gerencial
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {item.codigo} · lote {item.lote || "sem lote"}
            </p>
          </div>
          <button
            type="button"
            aria-label="Fechar"
            disabled={salvando}
            onClick={onFechar}
            className="rounded-md p-1 text-muted-foreground hover:bg-muted disabled:opacity-50"
          >
            <X className="size-5" />
          </button>
        </div>

        <div className="space-y-5 p-5">
          <div className="grid gap-3 sm:grid-cols-3">
            <Valor titulo="Estoque" valor={item.qtd_estoque} />
            <Valor
              titulo="Última contagem"
              valor={item.ultima_quantidade_contada}
            />
            <Info
              titulo="Situação"
              valor={formatarTecnico(item.situacao_atual)}
            />
          </div>

          <fieldset className="space-y-2">
            <legend className="mb-2 text-sm font-medium">
              Escolha a decisão
            </legend>
            <OpcaoDecisao
              valor="ACEITAR_ESTOQUE"
              titulo="Aceitar estoque"
              descricao="Mantém como quantidade final o saldo congelado no snapshot."
              selecionada={decisao}
              onChange={setDecisao}
            />
            <OpcaoDecisao
              valor="ACEITAR_CONTAGEM"
              titulo="Aceitar contagem"
              descricao="Define manualmente a quantidade aprovada pelo gestor."
              selecionada={decisao}
              onChange={setDecisao}
            />
            <OpcaoDecisao
              valor="NOVA_RECONTAGEM"
              titulo="Solicitar nova recontagem"
              descricao="Envia este código e lote para uma nova rodada."
              selecionada={decisao}
              onChange={setDecisao}
            />
          </fieldset>

          {decisao === "ACEITAR_CONTAGEM" && (
            <label className="block space-y-2">
              <span className="text-sm font-medium">Quantidade aprovada</span>
              <input
                type="number"
                min="0"
                step="any"
                value={quantidade}
                onChange={(evento) => setQuantidade(evento.target.value)}
                placeholder="Informe a quantidade final"
                className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              />
            </label>
          )}

          <label className="block space-y-2">
            <span className="text-sm font-medium">
              Justificativa {decisao === "NOVA_RECONTAGEM" ? "*" : "(opcional)"}
            </span>
            <textarea
              value={justificativa}
              onChange={(evento) => setJustificativa(evento.target.value)}
              maxLength={500}
              rows={4}
              placeholder="Registre o motivo da decisão"
              className="w-full resize-none rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
            <span className="block text-right text-xs text-muted-foreground">
              {justificativa.length}/500
            </span>
          </label>

          {erro && (
            <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {erro}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t p-5">
          <Button
            type="button"
            variant="outline"
            disabled={salvando}
            onClick={onFechar}
          >
            Cancelar
          </Button>
          <Button
            type="button"
            disabled={salvando}
            onClick={() => void confirmar()}
          >
            {salvando && <Loader2 className="size-4 animate-spin" />}
            Confirmar decisão
          </Button>
        </div>
      </div>
    </div>
  );
}

function OpcaoDecisao({
  valor,
  titulo,
  descricao,
  selecionada,
  onChange,
}: {
  valor: DecisaoGestor;
  titulo: string;
  descricao: string;
  selecionada: DecisaoGestor;
  onChange: (valor: DecisaoGestor) => void;
}) {
  return (
    <label
      className={`flex cursor-pointer gap-3 rounded-lg border p-3 transition ${
        selecionada === valor
          ? "border-primary bg-primary/5 ring-1 ring-primary"
          : "hover:bg-muted/30"
      }`}
    >
      <input
        type="radio"
        name="decisao-gestor"
        value={valor}
        checked={selecionada === valor}
        onChange={() => onChange(valor)}
        className="mt-1"
      />
      <span>
        <span className="block text-sm font-semibold">{titulo}</span>
        <span className="mt-1 block text-xs text-muted-foreground">
          {descricao}
        </span>
      </span>
    </label>
  );
}

function DecisaoAtual({ item }: { item: ItemAnaliseGestor }) {
  if (!item.requer_decisao_gestor) return <Badge valor="NÃO NECESSÁRIA" />;
  if (!item.decisao_gestor.possui_decisao)
    return <Badge valor="AGUARDANDO DECISÃO" />;

  return (
    <div>
      <Badge valor={item.decisao_gestor.decisao ?? "DECISÃO DESCONHECIDA"} />
      {item.decisao_gestor.quantidade_aprovada !== null && (
        <div className="mt-2 text-xs">
          Quantidade aprovada:{" "}
          {formatarNumero(item.decisao_gestor.quantidade_aprovada)}
        </div>
      )}
      {item.decisao_gestor.usuario && (
        <div className="mt-1 text-xs text-muted-foreground">
          Por {item.decisao_gestor.usuario}
        </div>
      )}
    </div>
  );
}

function Badge({ valor }: { valor: string }) {
  const status = valor.toUpperCase();
  const classe =
    status.includes("OK") ||
    status.includes("RESOLVIDO") ||
    status.includes("ACEITAR")
      ? "border-emerald-300 bg-emerald-50 text-emerald-800"
      : status.includes("RECONTAGEM")
        ? "border-blue-300 bg-blue-50 text-blue-800"
        : status.includes("AGUARDANDO") || status.includes("SEM CONTAGEM")
          ? "border-amber-300 bg-amber-50 text-amber-800"
          : "border-red-300 bg-red-50 text-red-800";

  return (
    <span
      className={`inline-flex rounded-full border px-2 py-1 text-xs font-semibold ${classe}`}
    >
      {formatarTecnico(valor)}
    </span>
  );
}

function Kpi({
  titulo,
  valor,
  ativo = false,
  onClick,
}: {
  titulo: string;
  valor: number;
  ativo?: boolean;
  onClick?: () => void;
}) {
  const conteudo = (
    <>
      <span className="text-xs font-semibold uppercase text-muted-foreground">
        {titulo}
      </span>
      <strong className="mt-1 block text-2xl text-primary">{valor}</strong>
    </>
  );

  if (!onClick)
    return (
      <div className="rounded-lg border bg-card p-4 shadow-sm">{conteudo}</div>
    );

  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg border bg-card p-4 text-left shadow-sm transition hover:border-primary ${
        ativo ? "border-primary ring-1 ring-primary" : ""
      }`}
    >
      {conteudo}
    </button>
  );
}

function Info({ titulo, valor }: { titulo: string; valor: string }) {
  return (
    <div>
      <span className="text-xs font-medium uppercase text-muted-foreground">
        {titulo}
      </span>
      <p className="mt-1 font-semibold text-primary">{valor}</p>
    </div>
  );
}

function Valor({ titulo, valor }: { titulo: string; valor: number | null }) {
  return <Info titulo={titulo} valor={formatarNumero(valor)} />;
}

function Th({ children }: { children: ReactNode }) {
  return (
    <th className="whitespace-nowrap px-3 py-3 font-semibold">{children}</th>
  );
}

function Td({
  children,
  classe = "",
}: {
  children: ReactNode;
  classe?: string;
}) {
  return <td className={`px-3 py-3 ${classe}`}>{children}</td>;
}

function Estado({
  mensagem,
  erro = false,
  carregando = false,
}: {
  mensagem: string;
  erro?: boolean;
  carregando?: boolean;
}) {
  return (
    <div
      className={`flex items-center justify-center gap-2 rounded-lg border bg-card p-8 text-center text-sm ${
        erro ? "text-destructive" : "text-muted-foreground"
      }`}
    >
      {carregando && <Loader2 className="size-4 animate-spin" />}
      {mensagem}
    </div>
  );
}

function formatarNumero(valor: number | null | undefined) {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return "-";
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 3 }).format(
    valor,
  );
}

function formatarTecnico(valor: string) {
  return valor.replaceAll("_", " ");
}

function formatarPercentual(valor: number) {
  return new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(valor);
}

function formatarDataHora(valor: string | null) {
  if (!valor) return "-";
  const data = new Date(valor);
  return Number.isNaN(data.getTime())
    ? valor
    : new Intl.DateTimeFormat("pt-BR", {
        dateStyle: "short",
        timeStyle: "short",
      }).format(data);
}

function mensagemErro(falha: unknown) {
  return falha instanceof Error
    ? falha.message
    : "Erro inesperado ao processar a análise gerencial.";
}
