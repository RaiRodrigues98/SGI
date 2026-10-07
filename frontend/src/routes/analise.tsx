import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";

import {
  buscarAnaliseSessao,
  listarSessoes,
  type AnaliseItem,
  type AnaliseSessao,
  type SessaoContagem,
  type StatusAnalise,
} from "@/services/analiseService";

type Filtro =
  | "TODOS"
  | "OK"
  | "DIVERGÊNCIA"
  | "FALTA"
  | "SOBRA"
  | "AGUARDANDO_CONTAGEM";

export const Route = createFileRoute("/analise")({
  head: () => ({
    meta: [{ title: "An\u00e1lise \u2014 SGI" }],
  }),
  component: AnalisePage,
});

function AnalisePage() {
  const [sessoes, setSessoes] = useState<SessaoContagem[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [analise, setAnalise] = useState<AnaliseSessao | null>(null);
  const [carregandoAnalise, setCarregandoAnalise] = useState(false);
  const [filtro, setFiltro] = useState<Filtro>("TODOS");

  useEffect(() => {
    let ativo = true;

    void listarSessoes()
      .then((dados) => {
        if (ativo) setSessoes(dados);
      })
      .catch((e: unknown) => {
        if (ativo) {
          setErro(e instanceof Error ? e.message : "Erro ao carregar sessões.");
        }
      })
      .finally(() => {
        if (ativo) setCarregando(false);
      });

    return () => {
      ativo = false;
    };
  }, []);

  async function abrirAnalise(idSessao: number) {
    setCarregandoAnalise(true);
    setErro(null);
    setFiltro("TODOS");

    try {
      setAnalise(await buscarAnaliseSessao(idSessao));
    } catch (e) {
      setAnalise(null);
      setErro(e instanceof Error ? e.message : "Erro ao carregar análise.");
    } finally {
      setCarregandoAnalise(false);
    }
  }

  const resumo = useMemo(() => {
    const itens = analise?.itens ?? [];
    return {
      todos: itens.length,
      ok: itens.filter((i) => i.status === "OK").length,
      divergencia: itens.filter((i) => i.status === "DIVERGÊNCIA").length,
      falta: itens.filter((i) => i.status === "FALTA").length,
      sobra: itens.filter((i) => i.status === "SOBRA").length,
      aguardando: itens.filter((i) => i.status === "AGUARDANDO_CONTAGEM").length,
      pendenteDecisao: itens.filter((i) => i.pendente_decisao).length,
      recontagem: itens.filter((i) => i.pendente_recontagem).length,
    };
  }, [analise]);

  const itens = useMemo(() => {
    if (!analise) return [];
    return filtro === "TODOS"
      ? analise.itens
      : analise.itens.filter((i) => i.status === filtro);
  }, [analise, filtro]);

  return (
    <div className="mx-auto w-full max-w-6xl space-y-4 p-3 sm:p-5 lg:p-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-base font-bold uppercase tracking-wide text-primary sm:text-lg">
            Análise de Contagem
          </h1>
          <p className="text-xs text-muted-foreground sm:text-sm">
            Sessões e resultados de conciliação
          </p>
        </div>

        {analise ? (
          <button
            type="button"
            onClick={() => {
              setAnalise(null);
              setFiltro("TODOS");
            }}
            className="h-10 rounded-md border px-4 text-sm font-semibold hover:bg-muted"
          >
            Voltar
          </button>
        ) : null}
      </div>

      {erro ? (
        <Estado mensagem={erro} erro />
      ) : carregando || carregandoAnalise ? (
        <Estado mensagem={carregandoAnalise ? "Carregando análise..." : "Carregando sessões..."} />
      ) : !analise ? (
        sessoes.length === 0 ? (
          <Estado mensagem="Nenhuma sessão encontrada." />
        ) : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {sessoes.map((sessao) => (
              <SessaoCard
                key={sessao.id_sessao}
                sessao={sessao}
                onAbrir={() => void abrirAnalise(sessao.id_sessao)}
              />
            ))}
          </div>
        )
      ) : (
        <>
          <div className="rounded-lg border bg-card p-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              <Info titulo="Sessão" valor={`#${analise.id_sessao}`} />
              <Info titulo="Inventário" valor={`#${analise.id_inventario}`} />
              <Info
                titulo="Rodada"
                valor={
                  analise.numero_rodada !== null
                    ? String(analise.numero_rodada)
                    : `#${analise.id_rodada}`
                }
              />
              <Info titulo="Localização" valor={analise.localizacao} />
              <Info titulo="Tipo / Status" valor={`${analise.tipo} · ${analise.status_sessao}`} />
            </div>

            <p className="mt-3 border-t pt-3 text-xs text-muted-foreground">
              Regra de conciliação:{" "}
              <strong className="text-foreground">{analise.regra_conciliacao}</strong>
            </p>

            {analise.observacao ? (
              <p className="mt-3 rounded-md bg-muted/60 p-3 text-sm text-muted-foreground">
                {analise.observacao}
              </p>
            ) : null}
          </div>

          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <Resumo titulo="Todos" valor={resumo.todos} ativo={filtro === "TODOS"} onClick={() => setFiltro("TODOS")} />
            <Resumo titulo="OK" valor={resumo.ok} ativo={filtro === "OK"} onClick={() => setFiltro("OK")} />
            <Resumo titulo="Divergência" valor={resumo.divergencia} ativo={filtro === "DIVERGÊNCIA"} onClick={() => setFiltro("DIVERGÊNCIA")} />
            <Resumo titulo="Falta" valor={resumo.falta} ativo={filtro === "FALTA"} onClick={() => setFiltro("FALTA")} />
            <Resumo titulo="Sobra" valor={resumo.sobra} ativo={filtro === "SOBRA"} onClick={() => setFiltro("SOBRA")} />
            <Resumo titulo="Aguardando" valor={resumo.aguardando} ativo={filtro === "AGUARDANDO_CONTAGEM"} onClick={() => setFiltro("AGUARDANDO_CONTAGEM")} />
          </div>

          {analise.tipo === "ROTATIVO" ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <Indicador titulo="Pendentes de decisão" valor={resumo.pendenteDecisao} />
              <Indicador titulo="Para recontagem" valor={resumo.recontagem} />
            </div>
          ) : null}

          <div className="space-y-3">
            {itens.map((item) => (
              <ItemCard key={item.chave} item={item} tipo={analise.tipo} />
            ))}
            {itens.length === 0 ? <Estado mensagem="Nenhum item neste filtro." /> : null}
          </div>
        </>
      )}
    </div>
  );
}

function SessaoCard({ sessao, onAbrir }: { sessao: SessaoContagem; onAbrir: () => void }) {
  return (
    <div className="rounded-lg border bg-card p-4 shadow-xs">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-lg font-bold text-primary">{sessao.localizacao}</p>
          <p className="text-xs text-muted-foreground">
            Sessão #{sessao.id_sessao} · Inventário #{sessao.id_inventario}
          </p>
        </div>
        <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-bold text-gray-700">
          {sessao.status}
        </span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <Info titulo="Itens" valor={String(sessao.itens_registrados)} />
        <Info titulo="Quantidade" valor={formatarNumero(sessao.quantidade_total)} />
      </div>
      <p className="mt-4 text-xs text-muted-foreground">
        Início: {formatarData(sessao.data_hora_inicio)}
      </p>
      {sessao.data_hora_fim ? (
        <p className="mt-1 text-xs text-muted-foreground">
          Encerramento: {formatarData(sessao.data_hora_fim)}
        </p>
      ) : null}
      <button
        type="button"
        onClick={onAbrir}
        className="mt-4 h-11 w-full rounded-md bg-primary px-4 text-sm font-bold uppercase tracking-wide text-white hover:bg-primary/85"
      >
        Ver análise
      </button>
    </div>
  );
}

function ItemCard({ item, tipo }: { item: AnaliseItem; tipo: "ROTATIVO" | "OFICIAL" }) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex flex-col justify-between gap-3 sm:flex-row">
        <div>
          <p className="font-mono text-sm font-bold text-primary">
            {item.codigo}{item.lote ? ` · Lote ${item.lote}` : ""}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {item.descricao ?? "Produto sem descrição"}
          </p>
          {tipo === "ROTATIVO" ? (
            <p className="mt-1 text-xs text-muted-foreground">Localização: {item.localizacao}</p>
          ) : null}
        </div>
        <Status status={item.status} />
      </div>

      <div className="mt-4 grid grid-cols-3 gap-3">
        <Valor titulo="Estoque" valor={item.qtd_estoque} />
        <Valor titulo="Contado" valor={item.qtd_contada} />
        <Valor titulo="Diferença" valor={item.diferenca} />
      </div>

      {item.subtipo_divergencia ? (
        <p className="mt-3 border-t pt-3 text-xs text-muted-foreground">
          Diagnóstico: <strong className="text-foreground">{tecnico(item.subtipo_divergencia)}</strong>
        </p>
      ) : null}

      {tipo === "ROTATIVO" && item.requer_decisao ? (
        <div className="mt-3 grid gap-2 border-t pt-3 sm:grid-cols-3">
          <Info titulo="Decisão" valor={item.decisao?.decisao ? tecnico(item.decisao.decisao) : "Pendente"} />
          <Info titulo="Recontagem" valor={item.pendente_recontagem ? "Sim" : "Não"} />
          <Info titulo="Justificada" valor={item.divergencia_justificada ? "Sim" : "Não"} />
          {item.decisao?.justificativa ? (
            <div className="sm:col-span-3">
              <span className="text-xs uppercase text-muted-foreground">Justificativa</span>
              <p className="font-medium text-foreground">{item.decisao.justificativa}</p>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function Resumo({ titulo, valor, ativo, onClick }: { titulo: string; valor: number; ativo: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "rounded-lg border bg-card p-4 text-left transition",
        ativo ? "border-gold ring-2 ring-gold/30" : "hover:border-gold/60",
      ].join(" ")}
    >
      <span className="text-xs font-bold uppercase text-muted-foreground">{titulo}</span>
      <p className="mt-1 text-2xl font-bold text-primary">{valor}</p>
    </button>
  );
}

function Indicador({ titulo, valor }: { titulo: string; valor: number }) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <span className="text-xs font-bold uppercase text-muted-foreground">{titulo}</span>
      <p className="mt-1 text-2xl font-bold text-primary">{valor}</p>
    </div>
  );
}

function Info({ titulo, valor }: { titulo: string; valor: string }) {
  return (
    <div>
      <span className="text-xs uppercase text-muted-foreground">{titulo}</span>
      <p className="font-bold text-primary">{valor}</p>
    </div>
  );
}

function Valor({ titulo, valor }: { titulo: string; valor: number }) {
  return (
    <div>
      <span className="text-xs uppercase text-muted-foreground">{titulo}</span>
      <p className="text-lg font-bold text-primary">{formatarNumero(valor)}</p>
    </div>
  );
}

function Status({ status }: { status: StatusAnalise }) {
  const mapa: Record<string, string> = {
    OK: "bg-green-100 text-green-800",
    "DIVERGÊNCIA": "bg-orange-100 text-orange-800",
    FALTA: "bg-red-100 text-red-800",
    SOBRA: "bg-yellow-100 text-yellow-800",
    AGUARDANDO_CONTAGEM: "bg-blue-100 text-blue-800",
  };

  return (
    <span className={`self-start rounded-full px-3 py-1 text-xs font-bold ${mapa[status] ?? "bg-gray-100 text-gray-700"}`}>
      {tecnico(status)}
    </span>
  );
}

function Estado({ mensagem, erro = false }: { mensagem: string; erro?: boolean }) {
  return (
    <div className={`rounded-lg border bg-card p-6 text-center text-sm ${erro ? "text-destructive" : "text-muted-foreground"}`}>
      {mensagem}
    </div>
  );
}

function formatarData(valor: string) {
  const data = new Date(valor);
  return Number.isNaN(data.getTime()) ? valor : data.toLocaleString("pt-BR");
}

function formatarNumero(valor: number) {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 3 }).format(valor);
}

function tecnico(valor: string) {
  return valor.replaceAll("_", " ");
}
