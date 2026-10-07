import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";

import { obterUsuarioSalvo } from "@/services/authService";
import { listarClientesDisponiveis } from "@/services/inventarioService";
import {
  consultarTratativasCicloRotativo,
  finalizarCicloRotativo,
  type FinalizarCicloRotativoResposta,
  type OcorrenciaHistoricoTratativaRotativa,
  type TratativasCicloRotativoResposta,
} from "@/services/rotativoService";
import type { ClienteDisponivelInventario } from "@/types/inventory";

interface TratativasSearch {
  inventario?: number;
}

export const Route = createFileRoute("/ciclo-rotativo")({
  validateSearch: (search: Record<string, unknown>): TratativasSearch => {
    const inventario = Number(search["inventario"]);

    return Number.isInteger(inventario) && inventario > 0
      ? { inventario }
      : {};
  },
  component: TratativasPage,
});

const buttonClass =
  "h-10 rounded-md border border-slate-300 bg-white px-4 text-sm font-medium hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50";

const inputClass =
  "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-slate-500";

const primaryButtonClass =
  "h-10 rounded-md bg-slate-900 px-4 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50";

const ARMAZEM_ROTATIVO = "ML007";

type VisaoTratativas = "PENDENTES" | "RECORRENTES" | "TODAS";

function TratativasPage() {
  const navigate = useNavigate();
  const { inventario } = Route.useSearch();

  const [clientes, setClientes] = useState<ClienteDisponivelInventario[]>([]);
  const [carregandoClientes, setCarregandoClientes] = useState(true);
  const [clienteRotativo, setClienteRotativo] = useState("");
  const [visao, setVisao] = useState<VisaoTratativas>("PENDENTES");
  const [resultadoRotativo, setResultadoRotativo] =
    useState<TratativasCicloRotativoResposta | null>(null);
  const [carregandoRotativo, setCarregandoRotativo] = useState(false);
  const [erroRotativo, setErroRotativo] = useState<string | null>(null);
  const [sucessoRotativo, setSucessoRotativo] = useState<string | null>(null);

  useEffect(() => {
    if (!inventario) return;

    void navigate({
      to: "/inventarios/$idInventario",
      params: { idInventario: String(inventario) },
      hash: "ocorrencias-tratativas",
      replace: true,
    });
  }, [inventario, navigate]);

  useEffect(() => {
    let ativo = true;

    async function carregarClientes() {
      setCarregandoClientes(true);

      try {
        const dados = await listarClientesDisponiveis();
        if (!ativo) return;

        const ids = new Set<number>();
        const disponiveis = dados
          .filter(
            (cliente) =>
              cliente.armazem.trim().toUpperCase() === ARMAZEM_ROTATIVO,
          )
          .filter((cliente) => {
            if (ids.has(cliente.cliente_id)) return false;
            ids.add(cliente.cliente_id);
            return true;
          })
          .sort((a, b) => clienteNome(a).localeCompare(clienteNome(b), "pt-BR"));

        setClientes(disponiveis);

        const [clienteUnico] = disponiveis;
        if (disponiveis.length === 1 && clienteUnico) {
          const idClienteUnico = String(clienteUnico.cliente_id);
          setClienteRotativo(idClienteUnico);
          void carregarTratativasRotativas(idClienteUnico, "PENDENTES");
        }
      } catch (e) {
        if (!ativo) return;
        setErroRotativo(
          e instanceof Error ? e.message : "Erro ao carregar os clientes.",
        );
      } finally {
        if (ativo) setCarregandoClientes(false);
      }
    }

    void carregarClientes();

    return () => {
      ativo = false;
    };
  }, []);

  async function carregarTratativasRotativas(
    clienteSelecionado = clienteRotativo,
    visaoSelecionada = visao,
  ) {
    const clienteId = numeroInteiroOpcional(clienteSelecionado);

    if (clienteId === null) {
      setErroRotativo("Selecione um cliente válido.");
      return;
    }

    setCarregandoRotativo(true);
    setErroRotativo(null);
    setSucessoRotativo(null);

    try {
      const data = await consultarTratativasCicloRotativo({
        clienteId,
        armazem: ARMAZEM_ROTATIVO,
        somentePendentes: visaoSelecionada === "PENDENTES",
        somenteRecorrentes: visaoSelecionada === "RECORRENTES",
      });

      setResultadoRotativo(data);
    } catch (e) {
      setErroRotativo(
        e instanceof Error
          ? e.message
          : "Erro ao carregar as tratativas do ciclo rotativo.",
      );
    } finally {
      setCarregandoRotativo(false);
    }
  }

  function selecionarCliente(valor: string) {
    setClienteRotativo(valor);
    setResultadoRotativo(null);
    setErroRotativo(null);
    setSucessoRotativo(null);

    if (valor) {
      void carregarTratativasRotativas(valor, visao);
    }
  }

  function selecionarVisao(novaVisao: VisaoTratativas) {
    setVisao(novaVisao);

    if (clienteRotativo) {
      void carregarTratativasRotativas(clienteRotativo, novaVisao);
    }
  }

  async function processarFinalizacaoCiclo(
    resposta: FinalizarCicloRotativoResposta,
  ) {
    if (resposta.finalizado || resposta.motivo === "CICLO_JA_FINALIZADO") {
      await carregarTratativasRotativas();
      setErroRotativo(null);
      setSucessoRotativo(
        resposta.finalizado
          ? "Ciclo rotativo finalizado com sucesso."
          : "Este ciclo rotativo já estava finalizado.",
      );
      return;
    }

    setSucessoRotativo(null);

    if (resposta.motivo === "CICLO_COM_LOCALIZACOES_ABERTAS") {
      const pendentes = resposta.ciclo?.pendentes ?? 0;
      const emContagem = resposta.ciclo?.em_contagem ?? 0;

      setErroRotativo(
        `${resposta.mensagem ?? "O ciclo possui localizações abertas."} Pendentes: ${pendentes}. Em contagem: ${emContagem}.`,
      );
      return;
    }

    if (resposta.motivo === "STATUS_LOCALIZACAO_NAO_RECONHECIDO") {
      const encontrados = Object.entries(resposta.status_encontrados ?? {})
        .map(([status, quantidade]) => `${status}: ${quantidade}`)
        .join(", ");

      setErroRotativo(
        encontrados
          ? `Status de localização não reconhecidos: ${encontrados}.`
          : resposta.mensagem ?? "Existem status não reconhecidos.",
      );
      return;
    }

    setErroRotativo(
      resposta.mensagem ?? `O ciclo não foi finalizado: ${resposta.motivo}.`,
    );
  }

  function abrirOcorrencia(
    ocorrencia: OcorrenciaHistoricoTratativaRotativa,
  ) {
    void navigate({
      to: "/inventarios/$idInventario",
      params: {
        idInventario: String(ocorrencia.id_inventario),
      },
      hash: "ocorrencias-tratativas",
    });
  }

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6 p-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">
            Gestão do ciclo rotativo
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Acompanhamento consolidado das localizações do ciclo aberto.
          </p>
        </div>
      </header>

      <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">
            Ciclo rotativo aberto
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Visão gerencial por localização, código e lote. As ocorrências de
            cada inventário são tratadas dentro da página do próprio inventário.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
          <Campo titulo="Cliente">
            <select
              className={inputClass}
              value={clienteRotativo}
              disabled={carregandoClientes || carregandoRotativo}
              onChange={(evento) => selecionarCliente(evento.target.value)}
            >
              <option value="">
                {carregandoClientes
                  ? "Carregando clientes..."
                  : "Selecione o cliente"}
              </option>
              {clientes.map((cliente) => (
                <option key={cliente.cliente_id} value={cliente.cliente_id}>
                  {clienteNome(cliente)}
                </option>
              ))}
            </select>
          </Campo>

          <div className="flex h-10 items-center rounded-md border border-slate-200 bg-slate-50 px-4 text-sm text-slate-600">
            Armazém operacional: <strong className="ml-1 text-slate-900">ML007</strong>
          </div>
        </div>

        <div className="flex flex-col gap-3 border-t border-slate-100 pt-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="mb-2 text-sm font-medium text-slate-700">
              Visão do acompanhamento
            </div>
            <div className="flex flex-wrap rounded-lg border border-slate-200 bg-slate-50 p-1">
              <BotaoVisao
                ativo={visao === "PENDENTES"}
                onClick={() => selecionarVisao("PENDENTES")}
              >
                Precisa de ação
              </BotaoVisao>
              <BotaoVisao
                ativo={visao === "RECORRENTES"}
                onClick={() => selecionarVisao("RECORRENTES")}
              >
                Recorrentes
              </BotaoVisao>
              <BotaoVisao
                ativo={visao === "TODAS"}
                onClick={() => selecionarVisao("TODAS")}
              >
                Todos
              </BotaoVisao>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              {descricaoVisao(visao)}
            </p>
          </div>

          <button
            type="button"
            className={buttonClass}
            disabled={carregandoRotativo || !clienteRotativo}
            onClick={() => void carregarTratativasRotativas()}
          >
            {carregandoRotativo ? "Atualizando..." : "Atualizar"}
          </button>
        </div>

        {erroRotativo && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {erroRotativo}
          </div>
        )}

        {sucessoRotativo && (
          <div className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-700">
            {sucessoRotativo}
          </div>
        )}

        {resultadoRotativo && (
          <TratativasRotativas
            resultado={resultadoRotativo}
            abrirOcorrencia={abrirOcorrencia}
            aoFinalizar={processarFinalizacaoCiclo}
          />
        )}
      </section>
    </div>
  );
}

function TratativasRotativas({
  resultado,
  abrirOcorrencia,
  aoFinalizar,
}: {
  resultado: TratativasCicloRotativoResposta;
  abrirOcorrencia: (
    ocorrencia: OcorrenciaHistoricoTratativaRotativa,
  ) => void;
  aoFinalizar: (resposta: FinalizarCicloRotativoResposta) => Promise<void>;
}) {
  const [finalizando, setFinalizando] = useState(false);

  async function finalizarCiclo() {
    const ciclo = resultado.ciclo;
    if (!ciclo) return;

    const usuario = obterUsuarioSalvo();
    if (!usuario?.login) {
      window.alert("Não foi possível identificar o usuário autenticado.");
      return;
    }

    if (
      !window.confirm(
        "Deseja finalizar este ciclo? Todas as localizações precisam estar contadas ou ignoradas.",
      )
    ) {
      return;
    }

    setFinalizando(true);

    try {
      const resposta = await finalizarCicloRotativo(
        ciclo.id_ciclo,
        usuario.login,
      );
      await aoFinalizar(resposta);
    } catch (e) {
      window.alert(
        e instanceof Error ? e.message : "Erro ao finalizar o ciclo rotativo.",
      );
    } finally {
      setFinalizando(false);
    }
  }

  if (!resultado.possui_ciclo_aberto) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
        Não existe ciclo rotativo aberto para o cliente e armazém informados.
      </div>
    );
  }

  return (
    <div className="space-y-4 border-t border-slate-100 pt-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="font-medium text-slate-900">
            {resultado.ciclo?.codigo_ciclo ?? "Ciclo rotativo"}
          </div>
          <div className="text-sm text-slate-500">
            {resultado.ciclo?.armazem ?? "-"} ·{" "}
            {tecnico(resultado.ciclo?.status ?? "-")}
          </div>
          <div className="mt-1 text-sm text-slate-500">
            Início: {data(resultado.ciclo?.data_inicio)}
          </div>
        </div>

        {resultado.ciclo?.status.toUpperCase() === "ABERTO" && (
          <button
            type="button"
            className={primaryButtonClass}
            disabled={finalizando}
            onClick={() => void finalizarCiclo()}
          >
            {finalizando ? "Finalizando..." : "Finalizar ciclo"}
          </button>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Resumo titulo="Grupos" valor={resultado.resumo.grupos_divergencia} />
        <Resumo titulo="Ocorrências" valor={resultado.resumo.ocorrencias} />
        <Resumo titulo="Pendentes" valor={resultado.resumo.necessitam_tratativa} />
        <Resumo titulo="Recorrentes" valor={resultado.resumo.recorrentes} />
      </div>

      {resultado.tratativas.length === 0 ? (
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-5 text-sm text-slate-500">
          Nenhuma tratativa encontrada para os filtros do ciclo.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className="w-full min-w-[1050px] text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Localização</th>
                <th className="px-4 py-3">Código</th>
                <th className="px-4 py-3">Lote</th>
                <th className="px-4 py-3">Tipo predominante</th>
                <th className="px-4 py-3 text-right">Ocorrências</th>
                <th className="px-4 py-3 text-right">Última diferença</th>
                <th className="px-4 py-3">Recorrência</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {resultado.tratativas.map((tratativa) => {
                const ultima =
                  tratativa.historico_ocorrencias.find(
                    (item) =>
                      item.id_ocorrencia ===
                      tratativa.ultima_ocorrencia.id_ocorrencia,
                  ) ?? tratativa.historico_ocorrencias[0];

                return (
                  <tr
                    key={`${tratativa.localizacao}-${tratativa.codigo}-${tratativa.lote ?? ""}`}
                    className="hover:bg-slate-50"
                  >
                    <td className="px-4 py-3 font-medium text-slate-900">
                      {tratativa.localizacao}
                    </td>
                    <td className="px-4 py-3 font-mono">
                      {tratativa.codigo}
                    </td>
                    <td className="px-4 py-3">{tratativa.lote || "-"}</td>
                    <td className="px-4 py-3">
                      {tratativa.tipo_divergencia_predominante
                        ? tecnico(tratativa.tipo_divergencia_predominante)
                        : "-"}
                    </td>
                    <td className="px-4 py-3 text-right font-medium">
                      {tratativa.ocorrencias}
                    </td>
                    <td className="px-4 py-3 text-right font-semibold">
                      {tratativa.ultima_ocorrencia.diferenca === null
                        ? "-"
                        : numero(tratativa.ultima_ocorrencia.diferenca)}
                    </td>
                    <td className="px-4 py-3">
                      {tratativa.recorrente ? (
                        <span className="inline-flex rounded-full bg-violet-100 px-2.5 py-1 text-xs font-medium text-violet-700">
                          Recorrente
                        </span>
                      ) : (
                        "Não"
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <Status valor={tratativa.status_tratativa} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        className={buttonClass}
                        disabled={!ultima}
                        onClick={() => ultima && abrirOcorrencia(ultima)}
                      >
                        Abrir no inventário
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Campo({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <label className="space-y-1.5">
      <span className="text-sm font-medium text-slate-700">{titulo}</span>
      {children}
    </label>
  );
}

function BotaoVisao({
  ativo,
  onClick,
  children,
}: {
  ativo: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={ativo}
      onClick={onClick}
      className={
        ativo
          ? "rounded-md bg-white px-4 py-2 text-sm font-semibold text-slate-900 shadow-sm"
          : "rounded-md px-4 py-2 text-sm font-medium text-slate-600 hover:bg-white hover:text-slate-900"
      }
    >
      {children}
    </button>
  );
}

function clienteNome(cliente: ClienteDisponivelInventario) {
  return cliente.cliente.trim() || `Cliente ${cliente.cliente_id}`;
}

function descricaoVisao(visao: VisaoTratativas) {
  if (visao === "PENDENTES") {
    return "Mostra somente os grupos que ainda precisam de justificativa ou resolução.";
  }

  if (visao === "RECORRENTES") {
    return "Mostra divergências que voltaram a ocorrer no histórico da localização, código e lote.";
  }

  return "Mostra todos os grupos do ciclo, incluindo os que já foram resolvidos.";
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

function data(valor: string | null | undefined) {
  if (!valor) return "-";

  const date = new Date(valor);
  return Number.isNaN(date.getTime()) ? valor : date.toLocaleString("pt-BR");
}

function numeroInteiroOpcional(valor: string): number | null {
  if (!valor.trim()) return null;

  const numeroConvertido = Number(valor);
  return Number.isInteger(numeroConvertido) && numeroConvertido > 0
    ? numeroConvertido
    : null;
}
