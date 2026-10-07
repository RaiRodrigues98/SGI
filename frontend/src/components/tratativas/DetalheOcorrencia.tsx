import { useState } from "react";
import type { ReactNode } from "react";

import { AnaliseCausaRaiz } from "@/components/tratativas/AnaliseCausaRaiz";
import { obterUsuarioSalvo } from "@/services/authService";
import {
  resolverTratativaRotativa,
  type OcorrenciaResolvidaTratativaRotativa,
  type TipoResolucaoTratativaRotativa,
} from "@/services/rotativoService";
import type { OcorrenciaTratativa } from "@/services/tratativasService";

interface DetalheOcorrenciaProps {
  ocorrencia: OcorrenciaTratativa;
  fechar: () => void;
  aoResolver: (
    ocorrencia: OcorrenciaResolvidaTratativaRotativa,
  ) => Promise<void>;
}

const buttonClass =
  "h-10 rounded-md border border-slate-300 bg-white px-4 text-sm font-medium hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50";

const inputClass =
  "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-slate-500";

const primaryButtonClass =
  "h-10 rounded-md bg-slate-900 px-4 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50";

export function DetalheOcorrencia({
  ocorrencia,
  fechar,
  aoResolver,
}: DetalheOcorrenciaProps) {
  const [tipoResolucao, setTipoResolucao] =
    useState<TipoResolucaoTratativaRotativa>("RECONTAGEM");
  const [observacaoResolucao, setObservacaoResolucao] = useState("");
  const [inventarioResolucao, setInventarioResolucao] = useState("");
  const [rodadaResolucao, setRodadaResolucao] = useState("");
  const [processandoResolucao, setProcessandoResolucao] = useState(false);
  const [erroResolucao, setErroResolucao] = useState<string | null>(null);
  const [sucessoResolucao, setSucessoResolucao] = useState<string | null>(null);

  const ocorrenciaRotativa =
    ocorrencia.tipo_inventario.toUpperCase() === "ROTATIVO";
  const ocorrenciaResolvida = ocorrencia.status_resolucao
    .toUpperCase()
    .startsWith("RESOLVIDA");

  async function resolverOcorrencia() {
    if (!ocorrencia.justificativa?.trim()) {
      setErroResolucao(
        "A ocorrência precisa possuir uma justificativa antes da resolução.",
      );
      return;
    }

    const usuario = obterUsuarioSalvo();

    if (!usuario?.login) {
      setErroResolucao(
        "Não foi possível identificar o usuário autenticado.",
      );
      return;
    }

    const idInventarioResolucao =
      numeroInteiroOpcional(inventarioResolucao);
    const idRodadaResolucao = numeroInteiroOpcional(rodadaResolucao);

    if (rodadaResolucao.trim() && idRodadaResolucao === null) {
      setErroResolucao("Informe um ID de rodada válido.");
      return;
    }

    if (inventarioResolucao.trim() && idInventarioResolucao === null) {
      setErroResolucao("Informe um ID de inventário válido.");
      return;
    }

    if (idRodadaResolucao !== null && idInventarioResolucao === null) {
      setErroResolucao("Informe o inventário relacionado antes da rodada.");
      return;
    }

    if (!window.confirm("Confirma a resolução desta ocorrência?")) {
      return;
    }

    setProcessandoResolucao(true);
    setErroResolucao(null);
    setSucessoResolucao(null);

    try {
      const observacao = observacaoResolucao.trim();
      const resposta = await resolverTratativaRotativa(
        ocorrencia.id_ocorrencia,
        {
          tipo_resolucao: tipoResolucao,
          resolvido_por: usuario.login,
          ...(observacao ? { observacao_resolucao: observacao } : {}),
          ...(idInventarioResolucao !== null
            ? { id_inventario_resolucao: idInventarioResolucao }
            : {}),
          ...(idRodadaResolucao !== null
            ? { id_rodada_resolucao: idRodadaResolucao }
            : {}),
        },
      );

      await aoResolver(resposta.ocorrencia);
      setSucessoResolucao(
        resposta.resolvido
          ? "Ocorrência resolvida com sucesso."
          : "Esta ocorrência já estava resolvida.",
      );
    } catch (e) {
      setErroResolucao(
        e instanceof Error ? e.message : "Erro ao resolver a ocorrência.",
      );
    } finally {
      setProcessandoResolucao(false);
    }
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="text-sm text-slate-500">
            Ocorrência #{ocorrencia.id_ocorrencia}
          </div>
          <h2 className="mt-1 text-lg font-semibold text-slate-900">
            {ocorrencia.codigo}
            {ocorrencia.lote ? ` · Lote ${ocorrencia.lote}` : ""}
          </h2>
          <div className="mt-2">
            <Status valor={ocorrencia.status_resolucao} />
          </div>
        </div>

        <button type="button" className={buttonClass} onClick={fechar}>
          Fechar
        </button>
      </div>

      <div className="mt-5 grid gap-4 border-t border-slate-100 pt-5 sm:grid-cols-2 lg:grid-cols-4">
        <Info titulo="Cliente" valor={ocorrencia.cliente_id} />
        <Info titulo="Inventário" valor={`#${ocorrencia.id_inventario}`} />
        <Info titulo="Rodada" valor={ocorrencia.id_rodada ?? "-"} />
        <Info titulo="Tipo" valor={ocorrencia.tipo_inventario} />
        <Info titulo="Localização" valor={ocorrencia.localizacao ?? "-"} />
        <Info
          titulo="Tipo divergência"
          valor={tecnico(ocorrencia.tipo_divergencia)}
        />
        <Info
          titulo="Subtipo"
          valor={
            ocorrencia.subtipo_divergencia
              ? tecnico(ocorrencia.subtipo_divergencia)
              : "-"
          }
        />
        <Info
          titulo="Criada em"
          valor={data(ocorrencia.data_hora_criacao)}
        />
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        <Valor titulo="Estoque" valor={ocorrencia.qtd_estoque} />
        <Valor titulo="Contado" valor={ocorrencia.qtd_contada} />
        <Valor titulo="Diferença" valor={ocorrencia.diferenca} />
      </div>

      {(ocorrencia.justificativa ||
        ocorrencia.observacao_resolucao ||
        ocorrencia.tipo_resolucao) && (
        <div className="mt-5 grid gap-4 border-t border-slate-100 pt-5 md:grid-cols-2">
          {ocorrencia.justificativa && (
            <Texto titulo="Justificativa" valor={ocorrencia.justificativa} />
          )}
          {ocorrencia.tipo_resolucao && (
            <Texto
              titulo="Tipo de resolução"
              valor={tecnico(ocorrencia.tipo_resolucao)}
            />
          )}
          {ocorrencia.observacao_resolucao && (
            <Texto
              titulo="Observação da resolução"
              valor={ocorrencia.observacao_resolucao}
            />
          )}
        </div>
      )}

      {sucessoResolucao && (
        <div className="mt-5 rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-700">
          {sucessoResolucao}
        </div>
      )}

      {ocorrenciaRotativa && !ocorrenciaResolvida && (
        <div className="mt-5 space-y-4 border-t border-slate-100 pt-5">
          <div>
            <h3 className="font-semibold text-slate-900">
              Resolver tratativa rotativa
            </h3>
            <p className="mt-1 text-sm text-slate-500">
              Registre como a divergência foi solucionada.
            </p>
          </div>

          {!ocorrencia.justificativa?.trim() ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              Registre primeiro uma justificativa para liberar a resolução.
            </div>
          ) : (
            <>
              <div className="grid gap-4 md:grid-cols-2">
                <Campo titulo="Tipo de resolução">
                  <select
                    className={inputClass}
                    value={tipoResolucao}
                    disabled={processandoResolucao}
                    onChange={(evento) =>
                      setTipoResolucao(
                        evento.target.value as TipoResolucaoTratativaRotativa,
                      )
                    }
                  >
                    <option value="RECONTAGEM">Resolvida por recontagem</option>
                    <option value="AJUSTE_ESTOQUE">
                      Resolvida por ajuste de estoque
                    </option>
                    <option value="OFICIAL">
                      Encaminhada para inventário oficial
                    </option>
                  </select>
                </Campo>

                <Campo titulo="Inventário relacionado (opcional)">
                  <input
                    type="number"
                    min="1"
                    className={inputClass}
                    value={inventarioResolucao}
                    disabled={processandoResolucao}
                    placeholder="Ex.: 21"
                    onChange={(evento) =>
                      setInventarioResolucao(evento.target.value)
                    }
                  />
                </Campo>

                <Campo titulo="Rodada relacionada (opcional)">
                  <input
                    type="number"
                    min="1"
                    className={inputClass}
                    value={rodadaResolucao}
                    disabled={processandoResolucao}
                    placeholder="Ex.: 41"
                    onChange={(evento) => setRodadaResolucao(evento.target.value)}
                  />
                </Campo>

                <Campo titulo="Observação da resolução">
                  <textarea
                    className="min-h-24 w-full rounded-md border border-slate-300 bg-white p-3 text-sm outline-none focus:border-slate-500 disabled:bg-slate-50"
                    value={observacaoResolucao}
                    disabled={processandoResolucao}
                    placeholder="Descreva como a divergência foi resolvida."
                    onChange={(evento) =>
                      setObservacaoResolucao(evento.target.value)
                    }
                  />
                </Campo>
              </div>

              {erroResolucao && (
                <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                  {erroResolucao}
                </div>
              )}

              <button
                type="button"
                className={primaryButtonClass}
                disabled={processandoResolucao}
                onClick={() => void resolverOcorrencia()}
              >
                {processandoResolucao
                  ? "Resolvendo..."
                  : "Confirmar resolução"}
              </button>
            </>
          )}
        </div>
      )}

      <AnaliseCausaRaiz ocorrencia={ocorrencia} />
    </section>
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

function Info({ titulo, valor }: { titulo: string; valor: string | number }) {
  return (
    <div>
      <div className="text-xs uppercase text-slate-500">{titulo}</div>
      <div className="mt-1 break-words font-medium text-slate-900">{valor}</div>
    </div>
  );
}

function Valor({ titulo, valor }: { titulo: string; valor: number }) {
  return (
    <div className="rounded-lg bg-slate-50 p-4">
      <div className="text-xs uppercase text-slate-500">{titulo}</div>
      <div className="mt-1 text-xl font-semibold text-slate-900">
        {numero(valor)}
      </div>
    </div>
  );
}

function Texto({ titulo, valor }: { titulo: string; valor: string }) {
  return (
    <div>
      <div className="text-sm text-slate-500">{titulo}</div>
      <div className="mt-1 whitespace-pre-wrap text-sm text-slate-800">
        {valor}
      </div>
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
