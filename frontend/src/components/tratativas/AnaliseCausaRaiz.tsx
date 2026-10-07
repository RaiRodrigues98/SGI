import { useEffect, useState } from "react";
import { PlanosAcaoTratativa } from "@/components/tratativas/PlanosAcaoTratativa";
import {
  atualizarAnaliseOcorrencia,
  consultarAnaliseOcorrencia,
  criarAnaliseOcorrencia,
  encerrarAnaliseOcorrencia,
  type AnaliseOcorrencia,
  type OcorrenciaTratativa,
} from "@/services/tratativasService";

interface Props {
  ocorrencia: OcorrenciaTratativa;
}

const inputClass =
  "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-slate-500 disabled:bg-slate-50 disabled:text-slate-600";

const buttonClass =
  "h-10 rounded-md border border-slate-300 bg-white px-4 text-sm font-medium hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50";

const primaryButtonClass =
  "h-10 rounded-md bg-slate-900 px-4 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50";

export function AnaliseCausaRaiz({ ocorrencia }: Props) {
  const [analise, setAnalise] = useState<AnaliseOcorrencia | null>(null);
  const [categoriaCausa, setCategoriaCausa] = useState("");
  const [causaRaiz, setCausaRaiz] = useState("");
  const [observacao, setObservacao] = useState("");
  const [carregando, setCarregando] = useState(true);
  const [processando, setProcessando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);

  useEffect(() => {
    void carregarAnalise();
  }, [ocorrencia.id_ocorrencia]);

  function preencherFormulario(valor: AnaliseOcorrencia | null) {
    setCategoriaCausa(valor?.categoria_causa ?? "");
    setCausaRaiz(valor?.causa_raiz ?? "");
    setObservacao(valor?.observacao ?? "");
  }

  async function carregarAnalise() {
    setCarregando(true);
    setErro(null);
    setSucesso(null);

    try {
      const resultado = await consultarAnaliseOcorrencia(
        ocorrencia.id_ocorrencia,
      );

      setAnalise(resultado);
      preencherFormulario(resultado);
    } catch (e) {
      setErro(mensagemErro(e));
    } finally {
      setCarregando(false);
    }
  }

  async function salvar() {
    const categoria = categoriaCausa.trim();
    const causa = causaRaiz.trim();
    const obs = observacao.trim();

    if (!categoria) {
      setErro("Informe a categoria da causa.");
      return;
    }

    if (!causa) {
      setErro("Informe a causa raiz.");
      return;
    }

    setProcessando(true);
    setErro(null);
    setSucesso(null);

    try {
      const payload = {
        categoria_causa: categoria,
        causa_raiz: causa,
        observacao: obs || null,
      };

      let resultado: AnaliseOcorrencia;
      let mensagem: string;

      if (analise) {
        resultado = await atualizarAnaliseOcorrencia(
          analise.id_analise,
          payload,
        );
        mensagem = "Análise atualizada com sucesso.";
      } else {
        resultado = await criarAnaliseOcorrencia(
          ocorrencia.id_ocorrencia,
          payload,
        );
        mensagem = "Análise criada com sucesso.";
      }

      setAnalise(resultado);
      preencherFormulario(resultado);
      setSucesso(mensagem);
    } catch (e) {
      setErro(mensagemErro(e));
    } finally {
      setProcessando(false);
    }
  }

  async function encerrar() {
    if (!analise || analise.status !== "ATIVA") {
      return;
    }

    const confirmado = window.confirm(
      "Deseja encerrar esta análise? Após o encerramento ela não poderá mais ser alterada.",
    );

    if (!confirmado) {
      return;
    }

    setProcessando(true);
    setErro(null);
    setSucesso(null);

    try {
      const resultado = await encerrarAnaliseOcorrencia(
        analise.id_analise,
      );

      setAnalise(resultado);
      preencherFormulario(resultado);
      setSucesso("Análise encerrada com sucesso.");
    } catch (e) {
      setErro(mensagemErro(e));
    } finally {
      setProcessando(false);
    }
  }

  const editavel = !analise || analise.status === "ATIVA";

  if (carregando) {
    return (
      <div className="mt-6 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
        Carregando análise da ocorrência...
      </div>
    );
  }

  return (
    <>
      <section className="mt-6 rounded-lg border border-slate-200 bg-white p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">
            Análise / Causa Raiz
          </h3>

          <p className="mt-1 text-sm text-slate-500">
            Identificação e registro da causa da divergência.
          </p>
        </div>

        {analise && (
          <span
            className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${
              analise.status === "ATIVA"
                ? "bg-amber-100 text-amber-800"
                : "bg-green-100 text-green-700"
            }`}
          >
            {analise.status}
          </span>
        )}
      </div>

      {erro && (
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {erro}
        </div>
      )}

      {sucesso && (
        <div className="mt-4 rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-700">
          {sucesso}
        </div>
      )}

      {!analise && (
        <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
          Esta ocorrência ainda não possui análise de causa registrada.
        </div>
      )}

      <div className="mt-5 grid gap-4">
        <Campo titulo="Categoria da causa">
          <input
            value={categoriaCausa}
            maxLength={50}
            disabled={!editavel || processando}
            className={inputClass}
            placeholder="Ex.: Processo, Sistema, Operação"
            onChange={(e) => setCategoriaCausa(e.target.value)}
          />
        </Campo>

        <Campo titulo="Causa raiz">
          <textarea
            value={causaRaiz}
            maxLength={2000}
            disabled={!editavel || processando}
            className="min-h-28 w-full rounded-md border border-slate-300 bg-white p-3 text-sm outline-none focus:border-slate-500 disabled:bg-slate-50 disabled:text-slate-600"
            placeholder="Descreva a causa raiz identificada."
            onChange={(e) => setCausaRaiz(e.target.value)}
          />
        </Campo>

        <Campo titulo="Observação">
          <textarea
            value={observacao}
            maxLength={2000}
            disabled={!editavel || processando}
            className="min-h-24 w-full rounded-md border border-slate-300 bg-white p-3 text-sm outline-none focus:border-slate-500 disabled:bg-slate-50 disabled:text-slate-600"
            placeholder="Informações complementares da análise."
            onChange={(e) => setObservacao(e.target.value)}
          />
        </Campo>
      </div>

      {analise && (
        <div className="mt-5 grid gap-3 border-t border-slate-100 pt-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <Info titulo="Análise" valor={`#${analise.id_analise}`} />
          <Info titulo="Analisado por" valor={analise.analisado_por} />
          <Info
            titulo="Data da análise"
            valor={formatarData(analise.data_hora_analise)}
          />
          <Info
            titulo="Última atualização"
            valor={formatarData(analise.data_hora_atualizacao)}
          />

          {analise.encerrado_por && (
            <Info
              titulo="Encerrado por"
              valor={analise.encerrado_por}
            />
          )}

          {analise.data_hora_encerramento && (
            <Info
              titulo="Encerrado em"
              valor={formatarData(analise.data_hora_encerramento)}
            />
          )}
        </div>
      )}

      <div className="mt-5 flex flex-wrap gap-3">
        {editavel && (
          <button
            className={primaryButtonClass}
            disabled={
              processando ||
              !categoriaCausa.trim() ||
              !causaRaiz.trim()
            }
            onClick={() => void salvar()}
          >
            {processando
              ? "Processando..."
              : analise
                ? "Salvar alterações"
                : "Criar análise"}
          </button>
        )}

        {analise?.status === "ATIVA" && (
          <button
            className={buttonClass}
            disabled={processando}
            onClick={() => void encerrar()}
          >
            Encerrar análise
          </button>
        )}

        <button
          className={buttonClass}
          disabled={processando}
          onClick={() => void carregarAnalise()}
        >
          Atualizar
        </button>
      </div>

      {analise?.status === "ENCERRADA" && (
        <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
          Esta análise está encerrada e permanece disponível somente para consulta.
        </div>
      )}
      </section>

      {analise && (
        <PlanosAcaoTratativa
          idAnalise={analise.id_analise}
        />
      )}
    </>
  );
}

function Campo({
  titulo,
  children,
}: {
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <label className="grid gap-1 text-sm">
      <span className="text-slate-600">{titulo}</span>
      {children}
    </label>
  );
}

function Info({
  titulo,
  valor,
}: {
  titulo: string;
  valor: string | number;
}) {
  return (
    <div>
      <div className="text-xs uppercase text-slate-500">{titulo}</div>
      <div className="mt-1 break-words font-medium text-slate-900">
        {valor}
      </div>
    </div>
  );
}

function formatarData(valor: string | null | undefined) {
  if (!valor) {
    return "-";
  }

  const data = new Date(valor);

  return Number.isNaN(data.getTime())
    ? valor
    : data.toLocaleString("pt-BR");
}

function mensagemErro(e: unknown) {
  return e instanceof Error
    ? e.message
    : "Erro inesperado ao processar a análise.";
}
