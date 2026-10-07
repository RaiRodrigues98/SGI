import { Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";

import { DetalheOcorrencia } from "@/components/tratativas/DetalheOcorrencia";
import { salvarInventarioAtual } from "@/lib/inventarioAtual";
import { listarClientesDisponiveis } from "@/services/inventarioService";
import type { OcorrenciaResolvidaTratativaRotativa } from "@/services/rotativoService";
import {
  listarOcorrenciasTratativas,
  type OcorrenciaTratativa,
  type OcorrenciasTratativasResponse,
} from "@/services/tratativasService";
import type { ClienteDisponivelInventario } from "@/types/inventory";


export interface TratativasContexto {
  inventario?: number;
  ocorrencia?: number;
}

interface TratativasHistoricoProps {
  inventario?: number;
  ocorrencia?: number;
  onAtualizarContexto?: (contexto: TratativasContexto) => void;
  exibirCabecalho?: boolean;
  exibirVoltarInventario?: boolean;
  integrado?: boolean;
}

const buttonClass =
  "h-10 rounded-md border border-slate-300 bg-white px-4 text-sm font-medium hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50";

const inputClass =
  "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-slate-500";

const primaryButtonClass =
  "h-10 rounded-md bg-slate-900 px-4 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50";

const ARMAZEM_OPERACIONAL = "ML007";

interface FiltrosTela {
  clienteId: string;
  idInventario: string;
  status: string;
  localizacao: string;
  codigo: string;
}

function filtrosIniciais(idInventario?: number): FiltrosTela {
  return {
    clienteId: "",
    idInventario: idInventario ? String(idInventario) : "",
    status: "",
    localizacao: "",
    codigo: "",
  };
}

export function TratativasHistorico({
  inventario,
  ocorrencia,
  onAtualizarContexto,
  exibirCabecalho = true,
  exibirVoltarInventario = true,
  integrado = false,
}: TratativasHistoricoProps) {
  const detalheRef = useRef<HTMLDivElement | null>(null);

  const [filtros, setFiltros] = useState<FiltrosTela>(() =>
    filtrosIniciais(inventario),
  );
  const [resultado, setResultado] =
    useState<OcorrenciasTratativasResponse | null>(null);
  const [selecionada, setSelecionada] =
    useState<OcorrenciaTratativa | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [carregandoClientes, setCarregandoClientes] = useState(true);
  const [clientes, setClientes] = useState<ClienteDisponivelInventario[]>([]);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let ativo = true;

    async function carregarClientes() {
      setCarregandoClientes(true);

      try {
        const dados = await listarClientesDisponiveis();
        if (!ativo) return;

        const ids = new Set<number>();
        setClientes(
          dados
            .filter(
              (cliente) =>
                cliente.armazem.trim().toUpperCase() === ARMAZEM_OPERACIONAL,
            )
            .filter((cliente) => {
              if (ids.has(cliente.cliente_id)) return false;
              ids.add(cliente.cliente_id);
              return true;
            })
            .sort((a, b) =>
              nomeCliente(a).localeCompare(nomeCliente(b), "pt-BR"),
            ),
        );
      } catch (e) {
        if (ativo) {
          setErro(
            e instanceof Error ? e.message : "Erro ao carregar os clientes.",
          );
        }
      } finally {
        if (ativo) setCarregandoClientes(false);
      }
    }

    void carregarClientes();

    return () => {
      ativo = false;
    };
  }, []);

  useEffect(() => {
    const novosFiltros = filtrosIniciais(inventario);
    setFiltros(novosFiltros);
    setSelecionada(null);
    void carregar(1, novosFiltros, ocorrencia ?? null);
  }, [inventario, ocorrencia]);

  useEffect(() => {
    if (!selecionada) return;

    const temporizador = window.setTimeout(() => {
      rolarParaDetalhe();
    }, 50);

    return () => window.clearTimeout(temporizador);
  }, [selecionada?.id_ocorrencia]);

  async function buscarPagina(page: number, filtrosAplicados: FiltrosTela) {
    const clienteId = numeroInteiroOpcional(filtrosAplicados.clienteId);
    const idInventario = numeroInteiroOpcional(
      filtrosAplicados.idInventario,
    );

    return listarOcorrenciasTratativas({
      ...(clienteId !== null ? { clienteId } : {}),
      ...(idInventario !== null ? { idInventario } : {}),
      ...(filtrosAplicados.status.trim()
        ? { status: filtrosAplicados.status.trim() }
        : {}),
      ...(filtrosAplicados.localizacao.trim()
        ? { localizacao: filtrosAplicados.localizacao.trim() }
        : {}),
      ...(filtrosAplicados.codigo.trim()
        ? { codigo: filtrosAplicados.codigo.trim() }
        : {}),
      somentePendentes: false,
      page,
      pageSize: 20,
    });
  }

  async function carregar(
    page = 1,
    filtrosAplicados: FiltrosTela = filtros,
    idOcorrenciaAbrir: number | null = null,
  ) {
    setCarregando(true);
    setErro(null);

    try {
      let dados = await buscarPagina(page, filtrosAplicados);
      let ocorrenciaEncontrada =
        idOcorrenciaAbrir !== null
          ? dados.ocorrencias.find(
              (item) => item.id_ocorrencia === idOcorrenciaAbrir,
            ) ?? null
          : null;

      if (
        idOcorrenciaAbrir !== null &&
        !ocorrenciaEncontrada &&
        dados.paginacao.total_paginas > 1
      ) {
        for (
          let pagina = 1;
          pagina <= dados.paginacao.total_paginas;
          pagina += 1
        ) {
          if (pagina === page) continue;

          const paginaConsultada = await buscarPagina(
            pagina,
            filtrosAplicados,
          );
          const encontrada = paginaConsultada.ocorrencias.find(
            (item) => item.id_ocorrencia === idOcorrenciaAbrir,
          );

          if (encontrada) {
            dados = paginaConsultada;
            ocorrenciaEncontrada = encontrada;
            break;
          }
        }
      }

      setResultado(dados);

      if (ocorrenciaEncontrada) {
        setSelecionada(ocorrenciaEncontrada);
        salvarInventarioAtual(
          ocorrenciaEncontrada.id_inventario,
          ocorrenciaEncontrada.tipo_inventario,
        );
        requestAnimationFrame(rolarParaDetalhe);
      } else if (idOcorrenciaAbrir !== null) {
        setSelecionada(null);
        setErro(
          `A ocorrência #${idOcorrenciaAbrir} não foi encontrada para os filtros informados.`,
        );
      } else if (
        selecionada &&
        !dados.ocorrencias.some(
          (item) => item.id_ocorrencia === selecionada.id_ocorrencia,
        )
      ) {
        setSelecionada(null);
      }
    } catch (e) {
      setErro(
        e instanceof Error
          ? e.message
          : "Erro ao carregar as ocorrências.",
      );
    } finally {
      setCarregando(false);
    }
  }

  function consultar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setSelecionada(null);
    void carregar(1, filtros, null);
  }

  function limparFiltros() {
    const novosFiltros = filtrosIniciais();
    setFiltros(novosFiltros);
    setSelecionada(null);
    onAtualizarContexto?.({});
  }

  function abrirOcorrencia(item: OcorrenciaTratativa) {
    setSelecionada(item);
    salvarInventarioAtual(item.id_inventario, item.tipo_inventario);
    onAtualizarContexto?.({
      inventario: item.id_inventario,
      ocorrencia: item.id_ocorrencia,
    });
    requestAnimationFrame(rolarParaDetalhe);
  }

  function fecharDetalhe() {
    setSelecionada(null);
    const idInventario = numeroInteiroOpcional(filtros.idInventario);

    onAtualizarContexto?.({
      ...(idInventario !== null ? { inventario: idInventario } : {}),
    });
  }

  function rolarParaDetalhe() {
    detalheRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }

  async function atualizarDepoisResolucao(
    resolvida: OcorrenciaResolvidaTratativaRotativa,
  ) {
    setSelecionada((atual) =>
      atual && atual.id_ocorrencia === resolvida.id_ocorrencia
        ? atualizarOcorrencia(atual, resolvida)
        : atual,
    );

    setResultado((atual) =>
      atual
        ? {
            ...atual,
            ocorrencias: atual.ocorrencias.map((item) =>
              item.id_ocorrencia === resolvida.id_ocorrencia
                ? atualizarOcorrencia(item, resolvida)
                : item,
            ),
          }
        : atual,
    );
  }

  return (
    <div
      className={
        integrado
          ? "w-full space-y-6"
          : "mx-auto w-full max-w-7xl space-y-6 p-6"
      }
    >
      {exibirCabecalho && (
        <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">
              Tratativas
            </h1>
            <p className="mt-1 text-sm text-slate-600">
              Ocorrências, resolução, causa raiz e planos de ação.
            </p>
          </div>
        </header>
      )}

      {exibirVoltarInventario && inventario && (
        <div className="flex flex-col gap-3 rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900 sm:flex-row sm:items-center sm:justify-between">
          <div>
            Exibindo as ocorrências vinculadas ao inventário rotativo
            <strong> #{inventario}</strong>.
          </div>
          <Link
            to="/inventarios/$idInventario"
            params={{ idInventario: String(inventario) }}
            className={buttonClass}
          >
            Voltar ao inventário
          </Link>
        </div>
      )}

      <form
        onSubmit={consultar}
        className="space-y-4 rounded-lg border border-slate-200 bg-white p-4"
      >
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <Campo titulo="Cliente">
            <select
              className={inputClass}
              value={filtros.clienteId}
              disabled={carregandoClientes}
              onChange={(evento) =>
                setFiltros((atual) => ({
                  ...atual,
                  clienteId: evento.target.value,
                }))
              }
            >
              <option value="">
                {carregandoClientes ? "Carregando clientes..." : "Todos os clientes"}
              </option>
              {clientes.map((cliente) => (
                <option key={cliente.cliente_id} value={cliente.cliente_id}>
                  {nomeCliente(cliente)}
                </option>
              ))}
            </select>
          </Campo>

          <Campo titulo="Inventário ID">
            <input
              type="number"
              min="1"
              className={inputClass}
              value={filtros.idInventario}
              onChange={(evento) =>
                setFiltros((atual) => ({
                  ...atual,
                  idInventario: evento.target.value,
                }))
              }
            />
          </Campo>

          <Campo titulo="Status">
            <select
              className={inputClass}
              value={filtros.status}
              onChange={(evento) =>
                setFiltros((atual) => ({
                  ...atual,
                  status: evento.target.value,
                }))
              }
            >
              <option value="">Todos os status</option>
              <option value="PENDENTE">Pendente</option>
              <option value="SEM_JUSTIFICATIVA">Sem justificativa</option>
              <option value="JUSTIFICADA">Justificada</option>
              <option value="JUSTIFICADA_PENDENTE_RESOLUCAO">
                Justificada, aguardando resolução
              </option>
              <option value="DIVERGENCIA_CONFIRMADA">
                Divergência confirmada
              </option>
              <option value="EM_RECONTAGEM">Em recontagem</option>
              <option value="EM_TRATATIVA">Em tratativa</option>
              <option value="RESOLVIDA_RECONTAGEM">
                Resolvida por recontagem
              </option>
              <option value="RESOLVIDA_AJUSTE">Resolvida por ajuste</option>
              <option value="RESOLVIDA_OFICIAL">Resolvida no oficial</option>
            </select>
          </Campo>

          <Campo titulo="Localização">
            <input
              className={inputClass}
              value={filtros.localizacao}
              onChange={(evento) =>
                setFiltros((atual) => ({
                  ...atual,
                  localizacao: evento.target.value.toUpperCase(),
                }))
              }
            />
          </Campo>

          <Campo titulo="Código">
            <input
              className={inputClass}
              value={filtros.codigo}
              onChange={(evento) =>
                setFiltros((atual) => ({
                  ...atual,
                  codigo: evento.target.value.toUpperCase(),
                }))
              }
            />
          </Campo>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            className={primaryButtonClass}
            disabled={carregando}
          >
            {carregando ? "Consultando..." : "Consultar ocorrências"}
          </button>

          <button
            type="button"
            className={buttonClass}
            disabled={carregando}
            onClick={limparFiltros}
          >
            Limpar filtros
          </button>
        </div>
      </form>

      {erro && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {erro}
        </div>
      )}

      {selecionada && (
        <div ref={detalheRef} className="scroll-mt-6">
          <DetalheOcorrencia
            ocorrencia={selecionada}
            fechar={fecharDetalhe}
            aoResolver={atualizarDepoisResolucao}
          />
        </div>
      )}

      {resultado && (
        <>
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <Resumo
              titulo="Ocorrências encontradas"
              valor={resultado.paginacao.total_registros}
            />
            <Resumo
              titulo="Registros na página"
              valor={resultado.paginacao.registros_pagina}
            />
            <Resumo
              titulo="Página"
              valor={
                resultado.paginacao.total_paginas > 0
                  ? `${resultado.paginacao.page}/${resultado.paginacao.total_paginas}`
                  : "0/0"
              }
            />
          </section>

          <section className="space-y-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">
                Lista de ocorrências
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Selecione uma ocorrência para consultar seus detalhes.
              </p>
            </div>

            {resultado.ocorrencias.length === 0 ? (
              <div className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-500">
                Nenhuma ocorrência encontrada para os filtros informados.
              </div>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
                <table className="w-full min-w-[1050px] text-left text-sm">
                  <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-4 py-3">Ocorrência</th>
                      <th className="px-4 py-3">Inventário</th>
                      <th className="px-4 py-3">Localização</th>
                      <th className="px-4 py-3">Código</th>
                      <th className="px-4 py-3">Lote</th>
                      <th className="px-4 py-3 text-right">Estoque</th>
                      <th className="px-4 py-3 text-right">Contado</th>
                      <th className="px-4 py-3 text-right">Diferença</th>
                      <th className="px-4 py-3">Status</th>
                      <th className="px-4 py-3" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {resultado.ocorrencias.map((item) => (
                      <tr
                        key={item.id_ocorrencia}
                        className={
                          selecionada?.id_ocorrencia === item.id_ocorrencia
                            ? "bg-slate-50"
                            : "hover:bg-slate-50"
                        }
                      >
                        <td className="px-4 py-3 font-medium text-slate-900">
                          #{item.id_ocorrencia}
                        </td>
                        <td className="px-4 py-3">#{item.id_inventario}</td>
                        <td className="px-4 py-3">
                          {item.localizacao ?? "-"}
                        </td>
                        <td className="px-4 py-3 font-mono">{item.codigo}</td>
                        <td className="px-4 py-3">{item.lote || "-"}</td>
                        <td className="px-4 py-3 text-right">
                          {numero(item.qtd_estoque)}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {numero(item.qtd_contada)}
                        </td>
                        <td className="px-4 py-3 text-right font-semibold">
                          {numero(item.diferenca)}
                        </td>
                        <td className="px-4 py-3">
                          <Status valor={item.status_resolucao} />
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            type="button"
                            className={buttonClass}
                            onClick={() => abrirOcorrencia(item)}
                          >
                            Abrir
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {resultado.paginacao.total_paginas > 0 && (
              <div className="flex items-center justify-between gap-3">
                <button
                  type="button"
                  className={buttonClass}
                  disabled={carregando || !resultado.paginacao.tem_anterior}
                  onClick={() =>
                    void carregar(resultado.paginacao.page - 1, filtros, null)
                  }
                >
                  Anterior
                </button>

                <span className="text-sm text-slate-600">
                  Página {resultado.paginacao.page} de{" "}
                  {resultado.paginacao.total_paginas} ·{" "}
                  {resultado.paginacao.total_registros} ocorrências
                </span>

                <button
                  type="button"
                  className={buttonClass}
                  disabled={carregando || !resultado.paginacao.tem_proxima}
                  onClick={() =>
                    void carregar(resultado.paginacao.page + 1, filtros, null)
                  }
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

function atualizarOcorrencia(
  atual: OcorrenciaTratativa,
  resolvida: OcorrenciaResolvidaTratativaRotativa,
): OcorrenciaTratativa {
  return {
    ...atual,
    status_resolucao: resolvida.status_resolucao,
    tipo_resolucao: resolvida.tipo_resolucao,
    observacao_resolucao:
      resolvida.observacao_resolucao ?? atual.observacao_resolucao,
    resolvido_por: resolvida.resolvido_por ?? atual.resolvido_por,
    data_hora_resolucao:
      resolvida.data_hora_resolucao ?? atual.data_hora_resolucao,
  };
}

function Campo({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <label className="space-y-1.5">
      <span className="text-sm font-medium text-slate-700">{titulo}</span>
      {children}
    </label>
  );
}

function Resumo({ titulo, valor }: { titulo: string; valor: string | number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-sm text-slate-500">{titulo}</div>
      <div className="mt-1 text-xl font-semibold text-slate-900">{valor}</div>
    </div>
  );
}

function Status({ valor }: { valor: string }) {
  const normalizado = valor.toUpperCase();
  let classe = "bg-slate-100 text-slate-700";

  if (
    normalizado === "DIVERGENCIA_CONFIRMADA" ||
    normalizado === "PENDENTE" ||
    normalizado === "SEM_JUSTIFICATIVA"
  ) {
    classe = "bg-red-100 text-red-700";
  } else if (
    normalizado === "EM_RECONTAGEM" ||
    normalizado === "EM_TRATATIVA" ||
    normalizado === "JUSTIFICADA_PENDENTE_RESOLUCAO"
  ) {
    classe = "bg-amber-100 text-amber-800";
  } else if (
    normalizado.startsWith("RESOLVIDA") ||
    normalizado === "CONCLUIDO"
  ) {
    classe = "bg-green-100 text-green-700";
  } else if (normalizado === "JUSTIFICADA") {
    classe = "bg-blue-100 text-blue-700";
  }

  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${classe}`}
    >
      {tecnico(valor)}
    </span>
  );
}

function numero(valor: number) {
  return new Intl.NumberFormat("pt-BR", {
    maximumFractionDigits: 3,
  }).format(valor);
}

function tecnico(valor: string) {
  return valor.replaceAll("_", " ");
}

function numeroInteiroOpcional(valor: string): number | null {
  if (!valor.trim()) return null;

  const numeroConvertido = Number(valor);
  return Number.isInteger(numeroConvertido) && numeroConvertido > 0
    ? numeroConvertido
    : null;
}

function nomeCliente(cliente: ClienteDisponivelInventario) {
  return cliente.cliente.trim() || `Cliente ${cliente.cliente_id}`;
}

