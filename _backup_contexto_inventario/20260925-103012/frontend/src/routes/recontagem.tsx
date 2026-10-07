import { createFileRoute } from "@tanstack/react-router";
import { Fragment, useEffect, useMemo, useState } from "react";

import {
  obterInventarioAtual,
  salvarInventarioAtual,
} from "@/lib/inventarioAtual";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  RefreshCcw,
  Search,
} from "lucide-react";

import {
  listarInventariosIndicadores,
  type InventarioIndicadores,
} from "@/services/indicadoresService";
import {
  buscarRodadaAtual,
  type RodadaAtual,
} from "@/services/rodadasService";
import {
  buscarAnaliseRecontagem,
  buscarComparativoRodadas,
  type AnaliseRecontagemOficial,
  type AnaliseRecontagemRotativo,
  type ComparativoRodadasOficial,
  type ItemComparativoOficial,
  type ItemRecontagemOficial,
  type ItemRecontagemRotativo,
} from "@/services/recontagemService";

interface RecontagemSearch {
  inventario?: number;
}

type ModoAnalise =
  | "SEM_RECONTAGEM"
  | "TIPO_INCOMPATIVEL"
  | "RODADA_INVALIDA"
  | "ROTATIVO_R2"
  | "OFICIAL_R2"
  | "OFICIAL_R3_MAIS";

type DadosAnalise =
  | AnaliseRecontagemRotativo
  | AnaliseRecontagemOficial
  | ComparativoRodadasOficial;

export const Route = createFileRoute("/recontagem")({
  validateSearch: (search: Record<string, unknown>): RecontagemSearch => {
    const idInventario = Number(search["inventario"]);

    return Number.isInteger(idInventario) && idInventario > 0
      ? { inventario: idInventario }
      : {};
  },
  head: () => ({
    meta: [{ title: "Recontagem — SGI" }],
  }),
  component: RecontagemPage,
});

function RecontagemPage() {
  const { inventario: idInventarioUrl } = Route.useSearch();
  const idInventario = idInventarioUrl ?? obterInventarioAtual();

  const [inventario, setInventario] =
    useState<InventarioIndicadores | null>(null);
  const [rodada, setRodada] = useState<RodadaAtual | null>(null);
  const [dados, setDados] = useState<DadosAnalise | null>(null);
  const [modo, setModo] = useState<ModoAnalise>("SEM_RECONTAGEM");
  const [carregando, setCarregando] = useState(true);
  const [atualizando, setAtualizando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    void carregarTela();
  }, [idInventario]);

  async function carregarTela() {
    setCarregando(true);
    setErro(null);
    setInventario(null);

    try {
      if (!idInventario) {
        throw new Error(
          "Nenhum inventário foi selecionado. Abra o inventário desejado pelo Controle de Inventários.",
        );
      }

      const inventarios = await listarInventariosIndicadores();
      const encontrado = inventarios.find(
        (item) => item.id_inventario === idInventario,
      );

      if (!encontrado) {
        throw new Error(
          `O inventário #${idInventario} não está disponível para recontagem.`,
        );
      }

      salvarInventarioAtual(encontrado.id_inventario, encontrado.tipo);
      setInventario(encontrado);
      await carregarAnalise(encontrado.id_inventario);
    } catch (e) {
      setErro(mensagemErro(e, "Erro ao carregar o inventário atual."));
    } finally {
      setCarregando(false);
    }
  }

  async function carregarAnalise(inventarioId: number) {
    setAtualizando(true);
    setErro(null);
    setRodada(null);
    setDados(null);
    setModo("SEM_RECONTAGEM");

    try {
      const rodadaAtual = await buscarRodadaAtual(inventarioId);
      const tipo = rodadaAtual.tipo_inventario.trim().toUpperCase();

      setRodada(rodadaAtual);

      if (rodadaAtual.numero_rodada < 2) {
        setModo("SEM_RECONTAGEM");
        return;
      }

      if (tipo === "ROTATIVO") {
        if (rodadaAtual.numero_rodada !== 2) {
          setModo("RODADA_INVALIDA");
          return;
        }

        const resultado = await buscarAnaliseRecontagem(
          inventarioId,
          rodadaAtual.id_rodada,
        );

        if ("tipo_analise" in resultado) {
          throw new Error(
            "A API retornou uma análise oficial para um inventário rotativo.",
          );
        }

        setDados(resultado);
        setModo("ROTATIVO_R2");
        return;
      }

      if (tipo === "OFICIAL") {
        if (rodadaAtual.numero_rodada === 2) {
          const resultado = await buscarComparativoRodadas(inventarioId);
          setDados(resultado);
          setModo("OFICIAL_R2");
          return;
        }

        const resultado = await buscarAnaliseRecontagem(
          inventarioId,
          rodadaAtual.id_rodada,
        );

        if (!("tipo_analise" in resultado)) {
          throw new Error(
            "A API retornou uma análise rotativa para um inventário oficial.",
          );
        }

        setDados(resultado);
        setModo("OFICIAL_R3_MAIS");
        return;
      }

      setModo("TIPO_INCOMPATIVEL");
    } catch (e) {
      setErro(mensagemErro(e, "Erro ao consultar a recontagem."));
    } finally {
      setAtualizando(false);
    }
  }

  if (carregando) {
    return (
      <main className="p-4 sm:p-6">
        <p className="text-sm text-muted-foreground">
          Carregando recontagens...
        </p>
      </main>
    );
  }

  return (
    <main className="space-y-6 p-4 sm:p-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-3">
          <RefreshCcw className="size-7 text-primary" />
          <div>
            <h1 className="text-xl font-bold tracking-tight text-primary">
              Recontagem
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Analise as recontagens e compare os resultados entre rodadas.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => {
            if (idInventario) void carregarAnalise(idInventario);
          }}
          disabled={!idInventario || atualizando}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-md border bg-background px-4 text-sm font-medium transition hover:bg-muted disabled:opacity-50"
        >
          <RefreshCcw
            className={`size-4 ${atualizando ? "animate-spin" : ""}`}
          />
          Atualizar
        </button>
      </header>

      {inventario ? (
        <ContextoInventario inventario={inventario} rodada={rodada} />
      ) : null}

      {erro ? <AlertaErro mensagem={erro} /> : null}

      {atualizando ? (
        <div className="rounded-lg border border-dashed p-5 text-sm text-muted-foreground">
          Consultando recontagem...
        </div>
      ) : null}

      {!atualizando && !erro && modo === "SEM_RECONTAGEM" ? (
        <MensagemEstado
          titulo="Recontagem ainda não iniciada"
          texto="Este inventário ainda está na primeira rodada. A comparação ficará disponível quando a R2 for gerada."
        />
      ) : null}

      {!atualizando && !erro && modo === "TIPO_INCOMPATIVEL" ? (
        <MensagemEstado
          titulo="Tipo de inventário não suportado"
          texto="A tela de Recontagem está disponível para inventários ROTATIVO e OFICIAL."
          variante="erro"
        />
      ) : null}

      {!atualizando && !erro && modo === "RODADA_INVALIDA" ? (
        <MensagemEstado
          titulo="Rodada incompatível"
          texto="No inventário ROTATIVO, a R2 é a rodada final. Não existe R3 nesse fluxo."
          variante="erro"
        />
      ) : null}

      {!atualizando && modo === "ROTATIVO_R2" && isRotativo(dados) ? (
        <PainelRotativo analise={dados} />
      ) : null}

      {!atualizando && modo === "OFICIAL_R2" && isComparativo(dados) ? (
        <PainelOficialR2 comparativo={dados} />
      ) : null}

      {!atualizando && modo === "OFICIAL_R3_MAIS" && isOficial(dados) ? (
        <PainelOficialRecontagem analise={dados} />
      ) : null}
    </main>
  );
}

function ContextoInventario({
  inventario,
  rodada,
}: {
  inventario: InventarioIndicadores;
  rodada: RodadaAtual | null;
}) {
  return (
    <section className="rounded-lg border bg-card px-5 py-4 shadow-xs">
      <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
        <span><strong>Inventário:</strong> {inventario.codigo_inventario}</span>
        <span><strong>Tipo:</strong> {inventario.tipo}</span>
        <span><strong>Rodada:</strong> R{rodada?.numero_rodada ?? inventario.rodada_atual}</span>
        <span><strong>Status:</strong> {formatarTexto(inventario.status)}</span>
        <span><strong>Armazém:</strong> {inventario.armazem || "-"}</span>
      </div>
    </section>
  );
}

function PainelRotativo({
  analise,
}: {
  analise: AnaliseRecontagemRotativo;
}) {
  const concluida =
    analise.rodada_operacional_concluida;

  const totalItens =
    analise.resumo.total_itens;

  const resolvidosR2 =
    analise.resumo.resolvidos_r2;

  const divergentesAposR2 = Math.max(
    totalItens - resolvidosR2,
    0,
  );

  const totalLocalizacoes =
    analise.total_localizacoes ?? 0;

  const localizacoesPendentes =
    analise.localizacoes_pendentes ?? 0;

  const localizacoesConcluidas = Math.max(
    totalLocalizacoes - localizacoesPendentes,
    0,
  );

  const textoConclusao =
    divergentesAposR2 > 0
      ? `${resolvidosR2} de ${totalItens} item(ns) foram reconciliados na R2. ` +
        `${divergentesAposR2} item(ns) permanecem divergentes e requerem ` +
        `an\u00e1lise antes do encerramento. A R2 \u00e9 a \u00faltima rodada ` +
        `operacional do invent\u00e1rio ROTATIVO. N\u00e3o existe R3.`
      : `Todos os ${totalItens} item(ns) foram reconciliados na R2. ` +
        `A R2 \u00e9 a \u00faltima rodada operacional do invent\u00e1rio ` +
        `ROTATIVO. N\u00e3o existe R3.`;

  return (
    <PainelDados
      aviso={
        <AvisoResultado
          concluido={concluida}
          titulo={
            concluida
              ? "Recontagem rotativa R2 conclu\u00edda"
              : "Recontagem rotativa R2 em andamento"
          }
          texto={
            concluida
              ? textoConclusao
              : "Os resultados permanecem provis\u00f3rios enquanto existirem localiza\u00e7\u00f5es pendentes na R2."
          }
        />
      }
      cards={
        <>
          <Resumo
            titulo="Itens recontados"
            valor={totalItens}
          />

          <Resumo
            titulo={"Localiza\u00e7\u00f5es R2"}
            valor={totalLocalizacoes}
          />

          <Resumo
            titulo={"Conclu\u00eddas R2"}
            valor={localizacoesConcluidas}
          />

          <Resumo
            titulo="Pendentes de contagem"
            valor={localizacoesPendentes}
            destaque={localizacoesPendentes > 0}
          />

          <Resumo
            titulo="Resolvidos na R2"
            valor={resolvidosR2}
          />

          <Resumo
            titulo={"Divergentes ap\u00f3s R2"}
            valor={divergentesAposR2}
            destaque={divergentesAposR2 > 0}
          />
        </>
      }
      itens={analise.itens}
      obterChave={(item) =>
        `${item.codigo}|${item.lote ?? ""}`
      }
      obterBusca={(item) => ({
        localizacoes: item.localizacoes.map(
          (localizacao) =>
            localizacao.localizacao,
        ),
        codigo: item.codigo,
        lote: item.lote,
        status: concluida
          ? rotuloResultadoRotativo(
              item.classificacao,
            )
          : "RESULTADO_PROVISORIO",
      })}
      cabecalho={
        <tr>
          <Th>{"C\u00f3digo"}</Th>
          <Th>Lote</Th>
          <Th>WMS</Th>
          <Th>R1</Th>
          <Th>R2</Th>
          <Th>{"Diferen\u00e7a"}</Th>
          <Th>Resultado R2</Th>
          <Th>{"Localiza\u00e7\u00f5es"}</Th>
        </tr>
      }
      renderizar={(
        item,
        expandido,
        alternar,
      ) => (
        <LinhasRotativo
          item={item}
          expandido={expandido}
          alternar={alternar}
          concluida={concluida}
        />
      )}
      totalColunas={8}
    />
  );
}

function PainelOficialR2({
  comparativo,
}: {
  comparativo: ComparativoRodadasOficial;
}) {
  return (
    <PainelDados
      aviso={
        <AvisoResultado
          concluido={comparativo.resumo.candidatos_r3 === 0}
          titulo="Comparativo oficial R1 × R2"
          texto="A R2 oficial compara novamente os itens do inventário. Os itens que permanecerem divergentes serão candidatos à próxima etapa configurada."
        />
      }
      cards={
        <>
          <Resumo titulo="Itens comparados" valor={comparativo.resumo.total_itens} />
          <Resumo titulo="OK na R1" valor={comparativo.resumo.rodada_1_ok} />
          <Resumo titulo="OK na R2" valor={comparativo.resumo.rodada_2_ok} />
          <Resumo titulo="Candidatos à próxima etapa" valor={comparativo.resumo.candidatos_r3} destaque={comparativo.resumo.candidatos_r3 > 0} />
        </>
      }
      itens={comparativo.itens}
      obterChave={(item) => item.chave}
      obterBusca={(item) => ({
        localizacoes: localizacoesComparativo(item),
        codigo: item.codigo,
        lote: item.lote,
        status: item.vai_para_r3 ? "DIVERGENTE" : item.rodada_2.status,
      })}
      cabecalho={
        <tr>
          <Th>Código</Th><Th>Lote</Th><Th>Produto</Th><Th>Estoque</Th>
          <Th>R1</Th><Th>R2</Th><Th>Diferença R2</Th><Th>Resultado</Th>
        </tr>
      }
      renderizar={(item, expandido, alternar) => (
        <LinhasOficialR2 item={item} expandido={expandido} alternar={alternar} />
      )}
      totalColunas={8}
    />
  );
}

function PainelOficialRecontagem({
  analise,
}: {
  analise: AnaliseRecontagemOficial;
}) {
  const concluida = analise.rodada_operacional_concluida;

  return (
    <PainelDados
      aviso={
        <AvisoResultado
          concluido={concluida}
          titulo={concluida ? `Recontagem oficial R${analise.numero_rodada} concluída` : `Recontagem oficial R${analise.numero_rodada} em andamento`}
          texto={
            concluida
              ? analise.pode_finalizar_sem_divergencia
                ? "A rodada foi concluída sem divergências remanescentes."
                : "A rodada foi concluída e ainda possui itens para a próxima decisão operacional."
              : "Os resultados são provisórios enquanto existirem localizações pendentes nesta rodada."
          }
        />
      }
      cards={
        <>
          <Resumo titulo="Itens" valor={analise.resumo.total_itens} />
          <Resumo titulo="Originais da rodada" valor={analise.resumo.itens_originais_recontagem} />
          <Resumo titulo="Novos encontrados" valor={analise.resumo.itens_novos_encontrados} />
          <Resumo titulo="OK" valor={analise.resumo.ok} />
          <Resumo titulo="Divergências" valor={analise.resumo.divergencias} destaque={analise.resumo.divergencias > 0} />
          <Resumo titulo="Próxima rodada" valor={analise.resumo.pendentes_proxima_rodada} destaque={analise.resumo.pendentes_proxima_rodada > 0} />
        </>
      }
      itens={analise.itens}
      obterChave={(item) => item.chave}
      obterBusca={(item) => ({
        localizacoes: [
          ...extrairLocalizacoes(item.localizacoes_snapshot),
          ...extrairLocalizacoes(item.localizacoes_bipadas),
        ],
        codigo: item.codigo,
        lote: item.lote,
        status: item.resultado_definitivo ? item.status : "RESULTADO_PROVISORIO",
      })}
      cabecalho={
        <tr>
          <Th>Código</Th><Th>Lote</Th><Th>Produto</Th><Th>Estoque</Th>
          <Th>Contado</Th><Th>Diferença</Th><Th>Status</Th><Th>Origem</Th>
        </tr>
      }
      renderizar={(item, expandido, alternar) => (
        <LinhasOficialRecontagem item={item} expandido={expandido} alternar={alternar} />
      )}
      totalColunas={8}
    />
  );
}

interface BuscaItem {
  localizacoes: string[];
  codigo: string;
  lote: string | null;
  status: string;
}

function PainelDados<T>({
  aviso,
  cards,
  itens,
  obterChave,
  obterBusca,
  cabecalho,
  renderizar,
  totalColunas,
}: {
  aviso: React.ReactNode;
  cards: React.ReactNode;
  itens: T[];
  obterChave: (item: T) => string;
  obterBusca: (item: T) => BuscaItem;
  cabecalho: React.ReactNode;
  renderizar: (item: T, expandido: boolean, alternar: () => void) => React.ReactNode;
  totalColunas: number;
}) {
  const [localizacao, setLocalizacao] = useState("");
  const [codigo, setCodigo] = useState("");
  const [lote, setLote] = useState("");
  const [status, setStatus] = useState("");
  const [pagina, setPagina] = useState(1);
  const [porPagina, setPorPagina] = useState(25);
  const [expandidos, setExpandidos] = useState<Set<string>>(() => new Set());

  const filtrados = useMemo(() => {
    const buscaLocalizacao = normalizar(localizacao);
    const buscaCodigo = normalizar(codigo);
    const buscaLote = normalizar(lote);
    const buscaStatus = normalizar(status);

    return itens.filter((item) => {
      const busca = obterBusca(item);

      return (
        (!buscaLocalizacao || busca.localizacoes.some((valor) => normalizar(valor).includes(buscaLocalizacao))) &&
        (!buscaCodigo || normalizar(busca.codigo).includes(buscaCodigo)) &&
        (!buscaLote || normalizar(busca.lote).includes(buscaLote)) &&
        (!buscaStatus || normalizar(busca.status.replaceAll("_", " ")).includes(buscaStatus))
      );
    });
  }, [itens, localizacao, codigo, lote, status, obterBusca]);

  useEffect(() => {
    setPagina(1);
    setExpandidos(new Set());
  }, [localizacao, codigo, lote, status, porPagina]);

  const totalPaginas = Math.max(1, Math.ceil(filtrados.length / porPagina));
  const paginaSegura = Math.min(pagina, totalPaginas);
  const inicio = (paginaSegura - 1) * porPagina;
  const paginados = filtrados.slice(inicio, inicio + porPagina);
  const primeiro = filtrados.length ? inicio + 1 : 0;
  const ultimo = Math.min(inicio + porPagina, filtrados.length);
  const possuiFiltro = Boolean(localizacao || codigo || lote || status);

  return (
    <>
      {aviso}
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {cards}
      </section>

      <section className="rounded-lg border bg-card p-4 shadow-xs">
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <Filtro valor={localizacao} alterar={setLocalizacao} placeholder="Buscar localização" />
          <Filtro valor={codigo} alterar={setCodigo} placeholder="Buscar código" />
          <Filtro valor={lote} alterar={setLote} placeholder="Buscar lote" />
          <Filtro valor={status} alterar={setStatus} placeholder="Buscar status" />
        </div>

        <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-muted-foreground">
            Exibindo {primeiro}–{ultimo} de {filtrados.length} item(ns)
            {filtrados.length !== itens.length ? ` · ${itens.length} no total` : ""}
          </p>

          <div className="flex flex-wrap items-center gap-3">
            {possuiFiltro ? (
              <button
                type="button"
                onClick={() => {
                  setLocalizacao(""); setCodigo(""); setLote(""); setStatus("");
                }}
                className="h-9 rounded-md border bg-background px-3 text-xs font-medium transition hover:bg-muted"
              >
                Limpar filtros
              </button>
            ) : null}

            <label className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Por página</span>
              <select
                value={porPagina}
                onChange={(event) => setPorPagina(Number(event.target.value))}
                className="h-9 rounded-md border bg-background px-3"
                aria-label="Quantidade de itens por página"
              >
                <option value={25}>25</option><option value={50}>50</option><option value={100}>100</option>
              </select>
            </label>
          </div>
        </div>
      </section>

      <section className="overflow-hidden rounded-lg border bg-card shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[980px] text-sm">
            <thead className="border-b bg-muted/40">{cabecalho}</thead>
            <tbody>
              {paginados.map((item) => {
                const chave = obterChave(item);
                const expandido = expandidos.has(chave);

                return (
                  <Fragment key={chave}>
                    {renderizar(item, expandido, () => {
                      setExpandidos((atual) => {
                        const proximo = new Set(atual);
                        if (proximo.has(chave)) proximo.delete(chave);
                        else proximo.add(chave);
                        return proximo;
                      });
                    })}
                  </Fragment>
                );
              })}

              {!paginados.length ? (
                <tr><td colSpan={totalColunas} className="p-6 text-center text-sm text-muted-foreground">Nenhum item encontrado para os filtros informados.</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>

        {filtrados.length ? (
          <div className="flex flex-col gap-3 border-t px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between">
            <span className="text-muted-foreground">Página {paginaSegura} de {totalPaginas}</span>
            <div className="flex gap-2">
              <button type="button" disabled={paginaSegura <= 1} onClick={() => setPagina((valor) => Math.max(1, valor - 1))} className="h-9 rounded-md border bg-background px-3 font-medium transition hover:bg-muted disabled:opacity-50">Anterior</button>
              <button type="button" disabled={paginaSegura >= totalPaginas} onClick={() => setPagina((valor) => Math.min(totalPaginas, valor + 1))} className="h-9 rounded-md border bg-background px-3 font-medium transition hover:bg-muted disabled:opacity-50">Próxima</button>
            </div>
          </div>
        ) : null}
      </section>
    </>
  );
}

function LinhasRotativo({
  item,
  expandido,
  alternar,
  concluida,
}: {
  item: ItemRecontagemRotativo;
  expandido: boolean;
  alternar: () => void;
  concluida: boolean;
}) {
  const resolvido =
    item.classificacao === "RESOLVIDO_R2";

  const localizacoesDivergentes =
    item.localizacoes.filter(
      (localizacao) =>
        localizacao.status
          .trim()
          .toUpperCase() !== "OK",
    ).length;

  return (
    <>
      <tr
        className={
          "border-b last:border-0 " +
          (
            concluida && !resolvido
              ? "bg-amber-50/35 dark:bg-amber-950/10"
              : ""
          )
        }
      >
        <Td>{item.codigo}</Td>

        <Td>{item.lote || "-"}</Td>

        <Td>
          {formatarQuantidade(
            item.qtd_wms_total,
          )}
        </Td>

        <Td>
          {formatarQuantidade(
            item.qtd_r1_total,
          )}
        </Td>

        <Td>
          {formatarQuantidade(
            item.qtd_r2_total,
          )}
        </Td>

        <Td>
          <span
            className={
              item.diferenca_r2_wms_total !== 0
                ? "font-semibold text-amber-700 dark:text-amber-300"
                : ""
            }
          >
            {formatarQuantidade(
              item.diferenca_r2_wms_total,
            )}
          </span>
        </Td>

        <Td>
          {concluida ? (
            <div>
              <StatusRotativo
                valor={item.classificacao}
              />

              {!resolvido &&
              localizacoesDivergentes > 0 ? (
                <div className="mt-1 text-xs text-muted-foreground">
                  {localizacoesDivergentes}{" "}
                  {localizacoesDivergentes === 1
                    ? "localiza\u00e7\u00e3o divergente"
                    : "localiza\u00e7\u00f5es divergentes"}
                </div>
              ) : null}
            </div>
          ) : (
            <StatusTexto
              valor="RESULTADO_PROVISORIO"
            />
          )}
        </Td>

        <Td>
          <BotaoDetalhe
            aberto={expandido}
            quantidade={item.localizacoes.length}
            alternar={alternar}
          />
        </Td>
      </tr>

      {expandido ? (
        <tr className="border-b bg-muted/20">
          <td
            colSpan={8}
            className="px-4 py-4"
          >
            <TabelaLocalizacoesRotativo
              item={item}
              concluida={concluida}
            />
          </td>
        </tr>
      ) : null}
    </>
  );
}

function TabelaLocalizacoesRotativo({
  item,
  concluida,
}: {
  item: ItemRecontagemRotativo;
  concluida: boolean;
}) {
  const resolvido =
    item.classificacao === "RESOLVIDO_R2";

  return (
    <div className="space-y-3">
      <div>
        <h3 className="font-semibold">
          {"Detalhamento por localiza\u00e7\u00e3o"}
        </h3>

        <p className="mt-1 text-xs text-muted-foreground">
          {concluida
            ? "Resultado definitivo da R2 por endere\u00e7o."
            : "Valores provis\u00f3rios enquanto a R2 estiver em andamento."}
        </p>
      </div>

      {concluida ? (
        <div
          className={
            "rounded-md border px-4 py-3 " +
            (
              resolvido
                ? "border-emerald-200 bg-emerald-50/60 dark:border-emerald-900 dark:bg-emerald-950/20"
                : "border-amber-200 bg-amber-50/70 dark:border-amber-900 dark:bg-amber-950/20"
            )
          }
        >
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {"Leitura para decis\u00e3o"}
          </div>

          <p className="mt-1 text-sm font-medium">
            {descricaoResultadoRotativo(
              item.classificacao,
            )}
          </p>
        </div>
      ) : null}

      <div className="overflow-x-auto rounded-md border bg-background">
        <table className="w-full min-w-[700px] text-sm">
          <thead className="border-b bg-muted/40">
            <tr>
              <Th>{"Localiza\u00e7\u00e3o"}</Th>
              <Th>WMS</Th>
              <Th>R1</Th>
              <Th>R2</Th>
              <Th>{"Diferen\u00e7a"}</Th>
              <Th>Status</Th>
            </tr>
          </thead>

          <tbody>
            {item.localizacoes.map(
              (loc) => {
                const localOk =
                  loc.status
                    .trim()
                    .toUpperCase() === "OK";

                return (
                  <tr
                    key={loc.localizacao}
                    className={
                      "border-b last:border-0 " +
                      (
                        concluida && !localOk
                          ? "bg-amber-50/40 dark:bg-amber-950/10"
                          : ""
                      )
                    }
                  >
                    <Td>{loc.localizacao}</Td>

                    <Td>
                      {formatarQuantidade(
                        loc.qtd_wms,
                      )}
                    </Td>

                    <Td>
                      {formatarQuantidade(
                        loc.qtd_r1,
                      )}
                    </Td>

                    <Td>
                      {formatarQuantidade(
                        loc.qtd_r2,
                      )}
                    </Td>

                    <Td>
                      {formatarQuantidade(
                        loc.diferenca_r2_wms,
                      )}
                    </Td>

                    <Td>
                      <StatusTexto
                        valor={
                          concluida
                            ? loc.status
                            : "RESULTADO_PROVISORIO"
                        }
                      />
                    </Td>
                  </tr>
                );
              },
            )}
          </tbody>

          {concluida ? (
            <tfoot className="border-t bg-muted/30 font-semibold">
              <tr>
                <Td>Total do item</Td>

                <Td>
                  {formatarQuantidade(
                    item.qtd_wms_total,
                  )}
                </Td>

                <Td>
                  {formatarQuantidade(
                    item.qtd_r1_total,
                  )}
                </Td>

                <Td>
                  {formatarQuantidade(
                    item.qtd_r2_total,
                  )}
                </Td>

                <Td>
                  {formatarQuantidade(
                    item.diferenca_r2_wms_total,
                  )}
                </Td>

                <Td>
                  <StatusRotativo
                    valor={item.classificacao}
                  />
                </Td>
              </tr>
            </tfoot>
          ) : null}
        </table>
      </div>
    </div>
  );
}

function LinhasOficialR2({ item, expandido, alternar }: { item: ItemComparativoOficial; expandido: boolean; alternar: () => void }) {
  const localizacoes = localizacoesComparativo(item);

  return (
    <>
      <tr className="border-b last:border-0">
        <Td>{item.codigo}</Td><Td>{item.lote || "-"}</Td><Td><span className="line-clamp-2 max-w-[320px]">{item.descricao || "-"}</span></Td>
        <Td>{formatarQuantidade(item.qtd_estoque)}</Td><Td>{formatarQuantidade(item.rodada_1.quantidade)}</Td><Td>{formatarQuantidade(item.rodada_2.quantidade)}</Td><Td>{formatarQuantidade(item.rodada_2.diferenca)}</Td>
        <Td><button type="button" onClick={alternar} aria-expanded={expandido} className="inline-flex items-center gap-2"><StatusTexto valor={item.vai_para_r3 ? "CANDIDATO_PROXIMA_RODADA" : item.rodada_2.status} />{expandido ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}</button></Td>
      </tr>
      {expandido ? (
        <tr className="border-b bg-muted/20"><td colSpan={8} className="px-4 py-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Detalhe titulo="Motivo" valor={item.motivo_r3 || "Item conciliado na R2."} />
            <Detalhe titulo="Localizações relacionadas" valor={localizacoes.length ? localizacoes.join(", ") : "Nenhuma localização informada."} />
            <Detalhe titulo="Unidade" valor={item.unidade || "-"} />
            <Detalhe titulo="Categoria" valor={item.categoria || "-"} />
          </div>
        </td></tr>
      ) : null}
    </>
  );
}

function LinhasOficialRecontagem({ item, expandido, alternar }: { item: ItemRecontagemOficial; expandido: boolean; alternar: () => void }) {
  const localizacoes = Array.from(new Set([
    ...extrairLocalizacoes(item.localizacoes_snapshot),
    ...extrairLocalizacoes(item.localizacoes_bipadas),
  ])).sort();

  return (
    <>
      <tr className="border-b last:border-0">
        <Td>{item.codigo}</Td><Td>{item.lote || "-"}</Td><Td><span className="line-clamp-2 max-w-[320px]">{item.descricao || "-"}</span></Td>
        <Td>{formatarQuantidade(item.qtd_estoque)}</Td><Td>{formatarQuantidade(item.qtd_contada)}</Td><Td>{formatarQuantidade(item.diferenca)}</Td>
        <Td><StatusTexto valor={item.resultado_definitivo ? item.status : "RESULTADO_PROVISORIO"} /></Td>
        <Td><button type="button" onClick={alternar} aria-expanded={expandido} className="inline-flex items-center gap-2"><span>{formatarTexto(item.origem)}</span>{expandido ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}</button></Td>
      </tr>
      {expandido ? (
        <tr className="border-b bg-muted/20"><td colSpan={8} className="px-4 py-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Detalhe titulo="Entrada na rodada" valor={item.motivo_entrada_rodada || "Sem motivo complementar."} />
            <Detalhe titulo="Localizações relacionadas" valor={localizacoes.length ? localizacoes.join(", ") : "Nenhuma localização informada."} />
            <Detalhe titulo="Tipo do item" valor={item.item_original_recontagem ? "Item original da recontagem" : "Item novo encontrado durante a rodada"} />
            <Detalhe titulo="Próxima etapa" valor={item.pendente_proxima_rodada ? "Pendente para nova decisão" : "Sem pendência para a próxima rodada"} />
          </div>
        </td></tr>
      ) : null}
    </>
  );
}

function Filtro({ valor, alterar, placeholder }: { valor: string; alterar: (valor: string) => void; placeholder: string }) {
  return (
    <div className="relative">
      <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
      <input type="search" value={valor} onChange={(event) => alterar(event.target.value)} placeholder={placeholder} className="h-9 w-full rounded-md border bg-background pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
    </div>
  );
}

function AvisoResultado({ concluido, titulo, texto }: { concluido: boolean; titulo: string; texto: string }) {
  return (
    <section className={concluido ? "rounded-lg border border-emerald-300 bg-emerald-50 p-4 text-emerald-900" : "rounded-lg border border-sky-300 bg-sky-50 p-4 text-sky-900"}>
      <div className="flex items-start gap-3">
        {concluido ? <CheckCircle2 className="mt-0.5 size-5 shrink-0" /> : <RefreshCcw className="mt-0.5 size-5 shrink-0" />}
        <div><h2 className="font-semibold">{titulo}</h2><p className="mt-1 text-sm">{texto}</p></div>
      </div>
    </section>
  );
}

function MensagemEstado({ titulo, texto, variante = "neutro" }: { titulo: string; texto: string; variante?: "neutro" | "erro" }) {
  return (
    <section className={variante === "erro" ? "rounded-lg border border-amber-300 bg-amber-50 p-6 text-amber-900 shadow-xs" : "rounded-lg border bg-card p-6 shadow-xs"}>
      <div className="flex items-start gap-3"><AlertTriangle className="mt-0.5 size-5 shrink-0" /><div><h2 className="font-semibold">{titulo}</h2><p className="mt-1 text-sm">{texto}</p></div></div>
    </section>
  );
}

function AlertaErro({ mensagem }: { mensagem: string }) {
  return <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{mensagem}</div>;
}

function Resumo({ titulo, valor, destaque = false }: { titulo: string; valor: number; destaque?: boolean }) {
  return (
    <div className="rounded-lg border bg-card p-4 shadow-xs"><div className="text-sm text-muted-foreground">{titulo}</div><div className={`mt-1 text-2xl font-bold ${destaque ? "text-amber-600" : "text-primary"}`}>{formatarQuantidade(valor)}</div></div>
  );
}

function StatusTexto({ valor }: { valor: string }) {
  const normalizado = valor.trim().toUpperCase();
  const ok = ["OK", "RESOLVIDO_R2", "CONCILIADA"].includes(normalizado);

  return (
    <span className="inline-flex items-center gap-1.5 font-medium">
      {ok ? <CheckCircle2 className="size-4 text-emerald-600" /> : <AlertTriangle className="size-4 text-amber-600" />}
      {formatarTexto(valor)}
    </span>
  );
}

function rotuloResultadoRotativo(
  valor: string,
) {
  const normalizado =
    valor.trim().toUpperCase();

  const rotulos: Record<string, string> = {
    RESOLVIDO_R2:
      "Resolvido na R2",
    DIVERGENCIA_LOCALIZACAO:
      "Diverg\u00eancia de localiza\u00e7\u00e3o",
    DIVERGENCIA_CONFIRMADA:
      "Diverg\u00eancia confirmada ap\u00f3s R2",
    INCONSISTENCIA_R1_R2:
      "Diverg\u00eancia ap\u00f3s R2",
  };

  return (
    rotulos[normalizado] ??
    formatarTexto(valor)
  );
}

function descricaoResultadoRotativo(
  valor: string,
) {
  const normalizado =
    valor.trim().toUpperCase();

  const descricoes: Record<string, string> = {
    RESOLVIDO_R2:
      "A R2 conciliou todas as localiza\u00e7\u00f5es deste item com o WMS.",

    DIVERGENCIA_LOCALIZACAO:
      "O total contado na R2 coincide com o WMS, mas a distribui\u00e7\u00e3o por localiza\u00e7\u00e3o permanece divergente.",

    DIVERGENCIA_CONFIRMADA:
      "A R1 e a R2 repetiram o mesmo resultado divergente em rela\u00e7\u00e3o ao WMS. O resultado requer an\u00e1lise antes do encerramento.",

    INCONSISTENCIA_R1_R2:
      "A R2 divergiu da R1 e o resultado final ainda n\u00e3o coincide com o WMS. Como a R2 \u00e9 terminal no ROTATIVO, o item deve ser analisado antes do encerramento.",
  };

  return (
    descricoes[normalizado] ??
    "Revise o comparativo entre WMS, R1 e R2 antes do encerramento."
  );
}

function StatusRotativo({
  valor,
}: {
  valor: string;
}) {
  const normalizado =
    valor.trim().toUpperCase();

  const resolvido =
    normalizado === "RESOLVIDO_R2";

  return (
    <span className="inline-flex items-center gap-1.5 font-medium">
      {resolvido ? (
        <CheckCircle2 className="size-4 text-emerald-600" />
      ) : (
        <AlertTriangle className="size-4 text-amber-600" />
      )}

      {rotuloResultadoRotativo(valor)}
    </span>
  );
}

function BotaoDetalhe({ aberto, quantidade, alternar }: { aberto: boolean; quantidade: number; alternar: () => void }) {
  return (
    <button type="button" onClick={alternar} aria-expanded={aberto} className="inline-flex h-8 items-center gap-1.5 rounded-md border bg-background px-2.5 text-xs font-medium transition hover:bg-muted">
      {aberto ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
      {quantidade} {quantidade === 1 ? "localização" : "localizações"}
    </button>
  );
}

function Detalhe({ titulo, valor }: { titulo: string; valor: string }) {
  return <div><div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{titulo}</div><div className="mt-1 text-sm">{valor}</div></div>;
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="whitespace-nowrap px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">{children}</th>;
}

function Td({ children }: { children: React.ReactNode }) {
  return <td className="px-4 py-3 align-middle">{children}</td>;
}

function isRotativo(dados: DadosAnalise | null): dados is AnaliseRecontagemRotativo {
  return Boolean(dados && "pode_encerrar_sem_gestor" in dados);
}

function isComparativo(dados: DadosAnalise | null): dados is ComparativoRodadasOficial {
  return Boolean(dados && "rodada_atual" in dados && !("status_recontagem" in dados));
}

function isOficial(dados: DadosAnalise | null): dados is AnaliseRecontagemOficial {
  return Boolean(dados && "tipo_analise" in dados && dados.tipo_analise === "RECONTAGEM_OFICIAL");
}

function localizacoesComparativo(item: ItemComparativoOficial) {
  return Array.from(new Set([
    ...item.localizacoes_para_recontagem,
    ...extrairLocalizacoes(item.localizacoes_snapshot),
    ...extrairLocalizacoes(item.rodada_1.localizacoes_bipadas),
    ...extrairLocalizacoes(item.rodada_2.localizacoes_bipadas),
  ])).sort();
}

function extrairLocalizacoes(valores: unknown[]) {
  return valores.flatMap((valor) => {
    if (typeof valor === "string") return [valor];
    if (!valor || typeof valor !== "object") return [];
    const localizacao = (valor as Record<string, unknown>)["localizacao"];
    return typeof localizacao === "string" ? [localizacao] : [];
  });
}

function formatarQuantidade(valor: number) {
  return Number(valor || 0).toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 3,
  });
}

function formatarTexto(valor: string | null | undefined) {
  if (!valor) return "-";
  return valor.replaceAll("_", " ").toLowerCase().replace(/(^|\s)\S/g, (letra) => letra.toUpperCase());
}

function normalizar(valor: string | null | undefined) {
  return (valor ?? "").trim().toLocaleLowerCase("pt-BR");
}

function mensagemErro(erro: unknown, fallback: string) {
  return erro instanceof Error ? erro.message : fallback;
}
