import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import {
  limparInventarioAtual,
  obterInventarioAtual,
  salvarInventarioAtual,
} from "@/lib/inventarioAtual";
import {
  buscarAuditoriaInventario,
  type AuditoriaEvento,
  type AuditoriaResponse,
} from "../services/auditoriaService";
import { listarInventariosIndicadores } from "@/services/indicadoresService";

interface AuditoriaSearch {
  inventario?: number;
}

export const Route = createFileRoute("/auditoria")({
  head: () => ({
    meta: [{ title: "Auditoria \u2014 SGI" }],
  }),
  validateSearch: (search: Record<string, unknown>): AuditoriaSearch => {
    const idInventario = Number(search["inventario"]);

    if (Number.isInteger(idInventario) && idInventario > 0) {
      return {
        inventario: idInventario,
      };
    }

    return {};
  },
  component: AuditoriaPage,
});

const buttonClass =
  "h-10 rounded-md border border-slate-300 bg-white px-4 text-sm font-medium hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50";
const primaryButtonClass =
  "h-10 rounded-md bg-slate-900 px-4 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50";

function AuditoriaPage() {
  const { inventario: idInventarioUrl } = Route.useSearch();

  const [
    idInventarioContexto,
    setIdInventarioContexto,
  ] = useState<number | null>(
    idInventarioUrl ?? null,
  );

  const id =
    idInventarioUrl ??
    idInventarioContexto;

  const [page, setPage] = useState(1);

  const [resultado, setResultado] = useState<AuditoriaResponse | null>(null);

  const [loading, setLoading] = useState(false);

  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (idInventarioUrl) {
      setIdInventarioContexto(
        idInventarioUrl,
      );
      return;
    }

    let ativo = true;

    void listarInventariosIndicadores()
      .then((inventarios) => {
        if (!ativo) return;

        const idPersistido =
          obterInventarioAtual();

        const inventarioAtivo =
          inventarios.find(
            (item) =>
              item.id_inventario ===
              idPersistido,
          ) ??
          inventarios[0] ??
          null;

        if (!inventarioAtivo) {
          limparInventarioAtual();
          setIdInventarioContexto(null);
          setResultado(null);
          setErro(null);
          return;
        }

        salvarInventarioAtual(
          inventarioAtivo.id_inventario,
          inventarioAtivo.tipo,
        );

        setIdInventarioContexto(
          inventarioAtivo.id_inventario,
        );
      })
      .catch((falha: unknown) => {
        if (!ativo) return;

        setIdInventarioContexto(null);
        setResultado(null);

        setErro(
          falha instanceof Error
            ? falha.message
            : "Erro ao localizar o inventário ativo.",
        );
      });

    return () => {
      ativo = false;
    };
  }, [idInventarioUrl]);

  useEffect(() => {
    setResultado(null);
    setPage(1);

    if (!id) {
      setErro(
        "Nenhum invent\u00e1rio foi selecionado. Acesse o Controle de Invent\u00e1rios e abra o invent\u00e1rio desejado.",
      );
      return;
    }

    void carregar(1);
  }, [id]);

  async function carregar(pagina = page) {
    if (id === null || !Number.isInteger(id) || id < 1) {
      setErro("Informe um ID de inventário válido.");
      return;
    }

    setLoading(true);
    setErro(null);

    try {
      const data = await buscarAuditoriaInventario(id, pagina, 20);
      setResultado(data);
      setPage(pagina);

    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar a auditoria.");
    } finally {
      setLoading(false);
    }
  }
  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Auditoria</h1>
        <p className="mt-1 text-sm text-slate-600">
          Rastreabilidade dos eventos registrados durante o ciclo do inventário.
        </p>
      </div>
      <div className="flex justify-end">
        <button
          type="button"
          className={primaryButtonClass}
          disabled={loading || !id}
          onClick={() => void carregar(1)}
        >
          {loading ? "Carregando..." : "Atualizar auditoria"}
        </button>
      </div>

      {erro && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {erro}
        </div>
      )}

      {resultado?.inventario && (
        <>
          <section className="space-y-3">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <Resumo titulo="Inventário" valor={`#${resultado.inventario.id_inventario}`} />
              <Resumo titulo="Código" valor={resultado.inventario.codigo_inventario} />
              <Resumo titulo="Tipo" valor={resultado.inventario.tipo} />
              <Resumo titulo="Status" valor={resultado.inventario.status} />
              <Resumo titulo="Cliente" valor={resultado.inventario.cliente} />
              <Resumo titulo="Armazém" valor={resultado.inventario.armazem ?? "-"} />
              <Resumo titulo="Total de eventos" valor={resultado.resumo.total_eventos} />
              <Resumo
                titulo="Período auditado"
                valor={`${fmtData(resultado.resumo.primeiro_evento)} - ${fmtData(resultado.resumo.ultimo_evento)}`}
              />
            </div>
          </section>

          <section className="space-y-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Linha do tempo</h2>
              <p className="mt-1 text-sm text-slate-500">
                Eventos exibidos do mais recente para o mais antigo.
              </p>
            </div>

            <div className="space-y-3">
              {resultado.eventos.map((evento, index) => (
                <EventoCard
                  key={`${evento.data_hora}-${evento.tipo_evento}-${evento.entidade_id ?? index}`}
                  evento={evento}
                />
              ))}

              {!loading && resultado.eventos.length === 0 && (
                <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-500">
                  Nenhum evento de auditoria encontrado para este inventário.
                </div>
              )}
            </div>

            {resultado.paginacao.total_paginas > 0 && (
              <div className="flex items-center justify-between gap-3">
                <button
                  className={buttonClass}
                  disabled={loading || !resultado.paginacao.tem_anterior}
                  onClick={() => void carregar(page - 1)}
                >
                  Anterior
                </button>

                <span className="text-sm text-slate-600">
                  Página {resultado.paginacao.page} de {resultado.paginacao.total_paginas}
                  {" · "}
                  {resultado.paginacao.total_registros} eventos
                </span>

                <button
                  className={buttonClass}
                  disabled={loading || !resultado.paginacao.tem_proxima}
                  onClick={() => void carregar(page + 1)}
                >
                  Próxima
                </button>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function EventoCard({ evento }: { evento: AuditoriaEvento }) {
  const detalhes = [
    ["Usuário", evento.usuario ?? "Não registrado"],
    ["Localização", evento.localizacao],
    ["Código", evento.codigo],
    ["Lote", evento.lote],
    ["Status atual", evento.status],
    ["Entidade", evento.entidade],
    ["ID entidade", evento.entidade_id],
  ].filter(([, valor]) => valor !== null && valor !== undefined && valor !== "");

  return (
    <article className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
              {formatarTipoEvento(evento.tipo_evento)}
            </span>
            <span className="text-xs text-slate-500">{evento.categoria}</span>
          </div>
          <h3 className="mt-2 font-semibold text-slate-900">
            {evento.titulo || formatarTipoEvento(evento.tipo_evento)}
          </h3>
          {evento.descricao && <p className="mt-1 text-sm text-slate-600">{evento.descricao}</p>}
        </div>

        <time className="shrink-0 text-sm text-slate-500">{fmtData(evento.data_hora)}</time>
      </div>

      {detalhes.length > 0 && (
        <div className="mt-4 grid gap-3 border-t border-slate-100 pt-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
          {detalhes.map(([nome, valor]) => (
            <div key={nome}>
              <div className="text-slate-500">{nome}</div>
              <div className="break-words font-medium text-slate-900">{valor}</div>
            </div>
          ))}
        </div>
      )}

      {(evento.motivo || evento.justificativa) && (
        <div className="mt-4 grid gap-3 border-t border-slate-100 pt-4 text-sm md:grid-cols-2">
          {evento.motivo && <TextoDetalhe titulo="Motivo" valor={evento.motivo} />}
          {evento.justificativa && (
            <TextoDetalhe titulo="Justificativa" valor={evento.justificativa} />
          )}
        </div>
      )}
    </article>
  );
}

function Resumo({ titulo, valor }: { titulo: string; valor: string | number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-sm text-slate-500">{titulo}</div>
      <div className="mt-1 break-words text-lg font-semibold text-slate-900">{valor}</div>
    </div>
  );
}

function TextoDetalhe({ titulo, valor }: { titulo: string; valor: string }) {
  return (
    <div>
      <div className="text-slate-500">{titulo}</div>
      <div className="mt-1 whitespace-pre-wrap text-slate-800">{valor}</div>
    </div>
  );
}

function formatarTipoEvento(value: string) {
  return value
    .toLowerCase()
    .split("_")
    .map((parte) => parte.charAt(0).toUpperCase() + parte.slice(1))
    .join(" ");
}

function fmtData(value: string | null | undefined) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("pt-BR");
}
