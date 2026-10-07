import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { DetalheOcorrencia } from "@/components/tratativas/DetalheOcorrencia";
import type { OcorrenciaResolvidaTratativaRotativa } from "@/services/rotativoService";
import {
  listarOcorrenciasTratativas,
  type OcorrenciaTratativa,
  type OcorrenciasTratativasResponse,
} from "@/services/tratativasService";

interface Props {
  idInventario: number;
}

interface Filtros {
  localizacao: string;
  codigo: string;
  status: string;
  somentePendentes: boolean;
}

const filtrosIniciais: Filtros = {
  localizacao: "",
  codigo: "",
  status: "",
  somentePendentes: true,
};

const inputClass =
  "h-10 w-full rounded-md border border-input bg-background px-3 text-sm outline-none focus:border-primary";

const buttonClass =
  "inline-flex h-10 items-center justify-center rounded-md border bg-background px-4 text-sm font-medium transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50";

export function OcorrenciasInventario({ idInventario }: Props) {
  const [formulario, setFormulario] = useState<Filtros>(filtrosIniciais);
  const [filtros, setFiltros] = useState<Filtros>(filtrosIniciais);
  const [resultado, setResultado] =
    useState<OcorrenciasTratativasResponse | null>(null);
  const [selecionada, setSelecionada] =
    useState<OcorrenciaTratativa | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    setFormulario(filtrosIniciais);
    setFiltros(filtrosIniciais);
    setSelecionada(null);
    void carregar(1, filtrosIniciais);
  }, [idInventario]);

  async function carregar(pagina: number, filtrosAtuais = filtros) {
    setCarregando(true);
    setErro(null);

    try {
      const dados = await listarOcorrenciasTratativas({
        idInventario,
        somentePendentes: filtrosAtuais.somentePendentes,
        page: pagina,
        pageSize: 20,
        ...(filtrosAtuais.localizacao.trim()
          ? { localizacao: filtrosAtuais.localizacao.trim() }
          : {}),
        ...(filtrosAtuais.codigo.trim()
          ? { codigo: filtrosAtuais.codigo.trim() }
          : {}),
        ...(filtrosAtuais.status.trim()
          ? { status: filtrosAtuais.status.trim() }
          : {}),
      });

      setResultado(dados);

      setSelecionada((atual) =>
        atual
          ? dados.ocorrencias.find(
              (item) => item.id_ocorrencia === atual.id_ocorrencia,
            ) ?? atual
          : null,
      );
    } catch (e) {
      setErro(
        e instanceof Error
          ? e.message
          : "Não foi possível carregar as ocorrências deste inventário.",
      );
    } finally {
      setCarregando(false);
    }
  }

  function aplicarFiltros(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setFiltros(formulario);
    setSelecionada(null);
    void carregar(1, formulario);
  }

  function alterarSituacao(somentePendentes: boolean) {
    const novosFiltros = {
      ...formulario,
      status: "",
      somentePendentes,
    };

    setFormulario(novosFiltros);
    setFiltros(novosFiltros);
    setSelecionada(null);
    void carregar(1, novosFiltros);
  }

  function limparFiltros() {
    setFormulario(filtrosIniciais);
    setFiltros(filtrosIniciais);
    setSelecionada(null);
    void carregar(1, filtrosIniciais);
  }

  async function atualizarDepoisResolucao(
    resolvida: OcorrenciaResolvidaTratativaRotativa,
  ) {
    setSelecionada((atual) =>
      atual && atual.id_ocorrencia === resolvida.id_ocorrencia
        ? {
            ...atual,
            status_resolucao: resolvida.status_resolucao,
            tipo_resolucao: resolvida.tipo_resolucao,
            observacao_resolucao:
              resolvida.observacao_resolucao ?? atual.observacao_resolucao,
            resolvido_por: resolvida.resolvido_por ?? atual.resolvido_por,
            data_hora_resolucao:
              resolvida.data_hora_resolucao ?? atual.data_hora_resolucao,
          }
        : atual,
    );

    await carregar(resultado?.paginacao.page ?? 1, filtros);
  }

  return (
    <section id="ocorrencias-tratativas" className="space-y-5 rounded-lg border bg-card p-5 shadow-xs">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="font-semibold">Ocorrências e tratativas</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Divergências, causas e ações corretivas do inventário #{idInventario}.
          </p>
        </div>

        <div className="flex rounded-md border bg-muted/30 p-1">
          <button
            type="button"
            aria-pressed={formulario.somentePendentes}
            className={situacaoClass(formulario.somentePendentes)}
            onClick={() => alterarSituacao(true)}
          >
            Precisa de ação
          </button>
          <button
            type="button"
            aria-pressed={!formulario.somentePendentes}
            className={situacaoClass(!formulario.somentePendentes)}
            onClick={() => alterarSituacao(false)}
          >
            Todas
          </button>
        </div>
      </div>

      <form onSubmit={aplicarFiltros} className="grid gap-3 md:grid-cols-4">
        <input
          className={inputClass}
          value={formulario.localizacao}
          placeholder="Localização"
          onChange={(evento) =>
            setFormulario((atual) => ({
              ...atual,
              localizacao: evento.target.value.toUpperCase(),
            }))
          }
        />
        <input
          className={inputClass}
          value={formulario.codigo}
          placeholder="Código"
          onChange={(evento) =>
            setFormulario((atual) => ({
              ...atual,
              codigo: evento.target.value.toUpperCase(),
            }))
          }
        />
        <select
          className={inputClass}
          value={formulario.status}
          onChange={(evento) =>
            setFormulario((atual) => ({
              ...atual,
              status: evento.target.value,
              somentePendentes: false,
            }))
          }
        >
          <option value="">Qualquer status</option>
          <option value="SEM_JUSTIFICATIVA">Sem justificativa</option>
          <option value="JUSTIFICADA_PENDENTE_RESOLUCAO">
            Justificada, aguardando resolução
          </option>
          <option value="EM_TRATATIVA">Em tratativa</option>
          <option value="RESOLVIDA">Resolvida</option>
        </select>
        <div className="flex gap-2">
          <button type="submit" className={buttonClass} disabled={carregando}>
            Filtrar
          </button>
          <button
            type="button"
            className={buttonClass}
            disabled={carregando}
            onClick={limparFiltros}
          >
            Limpar
          </button>
        </div>
      </form>

      {erro ? (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {erro}
        </div>
      ) : null}

      {selecionada ? (
        <DetalheOcorrencia
          ocorrencia={selecionada}
          fechar={() => setSelecionada(null)}
          aoResolver={atualizarDepoisResolucao}
        />
      ) : null}

      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">
          {carregando
            ? "Carregando ocorrências..."
            : `${resultado?.paginacao.total_registros ?? 0} ocorrência(s) encontrada(s)`}
        </span>
        <button
          type="button"
          className={buttonClass}
          disabled={carregando}
          onClick={() => void carregar(resultado?.paginacao.page ?? 1, filtros)}
        >
          Atualizar
        </button>
      </div>

      {!carregando && resultado?.ocorrencias.length === 0 ? (
        <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
          Nenhuma ocorrência encontrada para os filtros informados.
        </div>
      ) : null}

      {resultado && resultado.ocorrencias.length > 0 ? (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full min-w-[940px] text-sm">
            <thead className="border-b bg-muted/50 text-left">
              <tr>
                <th className="px-3 py-3">Ocorrência</th>
                <th className="px-3 py-3">Localização</th>
                <th className="px-3 py-3">Código</th>
                <th className="px-3 py-3">Lote</th>
                <th className="px-3 py-3 text-right">Diferença</th>
                <th className="px-3 py-3">Status</th>
                <th className="px-3 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y">
              {resultado.ocorrencias.map((item) => (
                <tr
                  key={item.id_ocorrencia}
                  className={
                    selecionada?.id_ocorrencia === item.id_ocorrencia
                      ? "bg-muted/50"
                      : "hover:bg-muted/30"
                  }
                >
                  <td className="px-3 py-3 font-medium">#{item.id_ocorrencia}</td>
                  <td className="px-3 py-3">{item.localizacao ?? "-"}</td>
                  <td className="px-3 py-3 font-mono">{item.codigo}</td>
                  <td className="px-3 py-3">{item.lote || "-"}</td>
                  <td className="px-3 py-3 text-right font-semibold">
                    {formatarNumero(item.diferenca)}
                  </td>
                  <td className="px-3 py-3">
                    {formatarStatus(item.status_resolucao)}
                  </td>
                  <td className="px-3 py-3 text-right">
                    <button
                      type="button"
                      className={buttonClass}
                      onClick={() => setSelecionada(item)}
                    >
                      Abrir
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {resultado && resultado.paginacao.total_paginas > 1 ? (
        <div className="flex items-center justify-between gap-3">
          <button
            type="button"
            className={buttonClass}
            disabled={carregando || !resultado.paginacao.tem_anterior}
            onClick={() => void carregar(resultado.paginacao.page - 1, filtros)}
          >
            Anterior
          </button>
          <span className="text-sm text-muted-foreground">
            Página {resultado.paginacao.page} de {resultado.paginacao.total_paginas}
          </span>
          <button
            type="button"
            className={buttonClass}
            disabled={carregando || !resultado.paginacao.tem_proxima}
            onClick={() => void carregar(resultado.paginacao.page + 1, filtros)}
          >
            Próxima
          </button>
        </div>
      ) : null}
    </section>
  );
}

function situacaoClass(ativa: boolean) {
  return ativa
    ? "rounded px-3 py-2 text-sm font-semibold shadow-sm bg-background"
    : "rounded px-3 py-2 text-sm text-muted-foreground hover:text-foreground";
}

function formatarNumero(valor: number) {
  return new Intl.NumberFormat("pt-BR", {
    maximumFractionDigits: 3,
  }).format(valor);
}

function formatarStatus(valor: string) {
  return valor.replaceAll("_", " ");
}
