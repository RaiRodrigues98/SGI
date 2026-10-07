import { useEffect, useState } from "react";
import {
  atualizarPlanoAcao,
  concluirPlanoAcao,
  consultarPlanoAcao,
  criarEvidenciaPlano,
  criarPlanoAcao,
  criarValidacaoEficacia,
  listarEvidenciasPlano,
  listarPlanosAcao,
  listarValidacoesEficacia,
  removerEvidenciaPlano,
  type EvidenciaPlano,
  type PlanoAcao,
  type PrioridadePlanoAcao,
  type ResultadoValidacaoEficacia,
  type StatusPlanoAcao,
  type ValidacaoEficaciaPlano,
} from "@/services/tratativasService";

interface Props {
  idAnalise: number;
}

type StatusEditavel = Exclude<StatusPlanoAcao, "CONCLUIDO">;

const inputClass =
  "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-slate-500 disabled:bg-slate-50 disabled:text-slate-600";

const textareaClass =
  "min-h-24 w-full rounded-md border border-slate-300 bg-white p-3 text-sm outline-none focus:border-slate-500 disabled:bg-slate-50 disabled:text-slate-600";

const buttonClass =
  "h-10 rounded-md border border-slate-300 bg-white px-4 text-sm font-medium hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50";

const primaryButtonClass =
  "h-10 rounded-md bg-slate-900 px-4 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50";

export function PlanosAcaoTratativa({ idAnalise }: Props) {
  const [planos, setPlanos] = useState<PlanoAcao[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [processando, setProcessando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);

  const [editandoId, setEditandoId] = useState<number | null>(null);
  const [descricaoAcao, setDescricaoAcao] = useState("");
  const [responsavel, setResponsavel] = useState("");
  const [dataPrazo, setDataPrazo] = useState("");
  const [prioridade, setPrioridade] =
    useState<PrioridadePlanoAcao>("MEDIA");
  const [statusEdicao, setStatusEdicao] =
    useState<StatusEditavel>("ABERTO");
  const [observacao, setObservacao] = useState("");

  const [planoDetalheId, setPlanoDetalheId] =
    useState<number | null>(null);

  const [evidencias, setEvidencias] =
    useState<Record<number, EvidenciaPlano[]>>({});

  const [validacoes, setValidacoes] =
    useState<Record<number, ValidacaoEficaciaPlano[]>>({});

  const [tipoEvidencia, setTipoEvidencia] = useState("DOCUMENTO");
  const [descricaoEvidencia, setDescricaoEvidencia] = useState("");
  const [referenciaArquivo, setReferenciaArquivo] = useState("");

  const [resultadoEficacia, setResultadoEficacia] =
    useState<ResultadoValidacaoEficacia>("EFICAZ");
  const [criterioValidacao, setCriterioValidacao] = useState("");
  const [observacaoValidacao, setObservacaoValidacao] = useState("");

  useEffect(() => {
    void carregarPlanos();
  }, [idAnalise]);

  async function carregarPlanos() {
    setCarregando(true);
    setErro(null);

    try {
      const dados = await listarPlanosAcao(idAnalise);
      setPlanos(dados);
    } catch (e) {
      setErro(mensagemErro(e));
    } finally {
      setCarregando(false);
    }
  }

  function limparFormularioPlano() {
    setEditandoId(null);
    setDescricaoAcao("");
    setResponsavel("");
    setDataPrazo("");
    setPrioridade("MEDIA");
    setStatusEdicao("ABERTO");
    setObservacao("");
  }

  function iniciarEdicao(plano: PlanoAcao) {
    if (plano.status === "CONCLUIDO") {
      return;
    }

    setEditandoId(plano.id_plano_acao);
    setDescricaoAcao(plano.descricao_acao);
    setResponsavel(plano.responsavel);
    setDataPrazo(plano.data_prazo);
    setPrioridade(plano.prioridade);
    setStatusEdicao(plano.status);
    setObservacao(plano.observacao ?? "");
    setErro(null);
    setSucesso(null);
  }

  async function salvarPlano() {
    const descricao = descricaoAcao.trim();
    const resp = responsavel.trim();

    if (!descricao) {
      setErro("Informe a ação do plano.");
      return;
    }

    if (!resp) {
      setErro("Informe o responsável.");
      return;
    }

    if (!dataPrazo) {
      setErro("Informe o prazo.");
      return;
    }

    setProcessando(true);
    setErro(null);
    setSucesso(null);

    try {
      if (editandoId !== null) {
        await atualizarPlanoAcao(editandoId, {
          descricao_acao: descricao,
          responsavel: resp,
          data_prazo: dataPrazo,
          prioridade,
          status: statusEdicao,
          observacao: observacao.trim() || null,
        });

        setSucesso("Plano de ação atualizado com sucesso.");
      } else {
        await criarPlanoAcao(idAnalise, {
          descricao_acao: descricao,
          responsavel: resp,
          data_prazo: dataPrazo,
          prioridade,
          observacao: observacao.trim() || null,
        });

        setSucesso("Plano de ação criado com sucesso.");
      }

      limparFormularioPlano();
      await carregarPlanos();
    } catch (e) {
      setErro(mensagemErro(e));
    } finally {
      setProcessando(false);
    }
  }

  async function concluir(plano: PlanoAcao) {
    const confirmado = window.confirm(
      "Deseja concluir este plano de ação?",
    );

    if (!confirmado) {
      return;
    }

    setProcessando(true);
    setErro(null);
    setSucesso(null);

    try {
      await concluirPlanoAcao(plano.id_plano_acao);
      setSucesso("Plano de ação concluído com sucesso.");
      await carregarPlanos();

      if (planoDetalheId === plano.id_plano_acao) {
        await carregarDetalhes({
          ...plano,
          status: "CONCLUIDO",
        });
      }
    } catch (e) {
      setErro(mensagemErro(e));
    } finally {
      setProcessando(false);
    }
  }

  async function alternarDetalhes(plano: PlanoAcao) {
    if (planoDetalheId === plano.id_plano_acao) {
      setPlanoDetalheId(null);
      return;
    }

    setPlanoDetalheId(plano.id_plano_acao);
    await carregarDetalhes(plano);
  }

  async function carregarDetalhes(plano: PlanoAcao) {
    const idPlano = plano.id_plano_acao;

    setErro(null);

    try {
      const [planoAtualizado, listaEvidencias] = await Promise.all([
        consultarPlanoAcao(idPlano),
        listarEvidenciasPlano(idPlano),
      ]);

      setPlanos((atuais) =>
        atuais.map((item) =>
          item.id_plano_acao === idPlano
            ? planoAtualizado
            : item,
        ),
      );

      setEvidencias((atual) => ({
        ...atual,
        [idPlano]: listaEvidencias,
      }));

      if (planoAtualizado.status === "CONCLUIDO") {
        const listaValidacoes =
          await listarValidacoesEficacia(idPlano);

        setValidacoes((atual) => ({
          ...atual,
          [idPlano]: listaValidacoes,
        }));
      } else {
        setValidacoes((atual) => {
          const atualizado = { ...atual };
          delete atualizado[idPlano];
          return atualizado;
        });
      }
    } catch (e) {
      setErro(mensagemErro(e));
    }
  }
  async function adicionarEvidencia(idPlano: number) {
    if (
      !descricaoEvidencia.trim() &&
      !referenciaArquivo.trim()
    ) {
      setErro(
        "Informe uma descrição ou referência para a evidência.",
      );
      return;
    }

    setProcessando(true);
    setErro(null);
    setSucesso(null);

    try {
      await criarEvidenciaPlano(idPlano, {
        tipo_evidencia: tipoEvidencia.trim(),
        descricao: descricaoEvidencia.trim() || null,
        referencia_arquivo: referenciaArquivo.trim() || null,
      });

      const lista = await listarEvidenciasPlano(idPlano);

      setEvidencias((atual) => ({
        ...atual,
        [idPlano]: lista,
      }));

      setDescricaoEvidencia("");
      setReferenciaArquivo("");
      setSucesso("Evidência adicionada com sucesso.");
    } catch (e) {
      setErro(mensagemErro(e));
    } finally {
      setProcessando(false);
    }
  }

  async function removerEvidencia(
    idPlano: number,
    idEvidencia: number,
  ) {
    const confirmado = window.confirm(
      "Deseja remover esta evidência?",
    );

    if (!confirmado) {
      return;
    }

    setProcessando(true);
    setErro(null);
    setSucesso(null);

    try {
      await removerEvidenciaPlano(idEvidencia);

      setEvidencias((atual) => ({
        ...atual,
        [idPlano]: (atual[idPlano] ?? []).filter(
          (item) => item.id_evidencia !== idEvidencia,
        ),
      }));

      setSucesso("Evidência removida com sucesso.");
    } catch (e) {
      setErro(mensagemErro(e));
    } finally {
      setProcessando(false);
    }
  }

  async function validarEficacia(idPlano: number) {
    const criterio = criterioValidacao.trim();

    if (!criterio) {
      setErro("Informe o critério utilizado na validação.");
      return;
    }

    setProcessando(true);
    setErro(null);
    setSucesso(null);

    try {
      await criarValidacaoEficacia(idPlano, {
        resultado: resultadoEficacia,
        criterio_validacao: criterio,
        observacao: observacaoValidacao.trim() || null,
      });

      const lista = await listarValidacoesEficacia(idPlano);

      setValidacoes((atual) => ({
        ...atual,
        [idPlano]: lista,
      }));

      setCriterioValidacao("");
      setObservacaoValidacao("");
      setResultadoEficacia("EFICAZ");

      setSucesso(
        resultadoEficacia === "EFICAZ"
          ? "Plano validado como eficaz."
          : "Plano validado como ineficaz.",
      );
    } catch (e) {
      setErro(mensagemErro(e));
    } finally {
      setProcessando(false);
    }
  }

  if (carregando) {
    return (
      <section className="mt-6 rounded-lg border border-slate-200 bg-white p-5 text-sm text-slate-500">
        Carregando planos de ação...
      </section>
    );
  }

  return (
    <section className="mt-6 rounded-lg border border-slate-200 bg-white p-5">
      <div>
        <h3 className="text-lg font-semibold text-slate-900">
          Plano de Ação
        </h3>
        <p className="mt-1 text-sm text-slate-500">
          Definição, acompanhamento e validação das ações corretivas.
        </p>
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

      <div className="mt-5 grid gap-4 rounded-md border border-slate-200 bg-slate-50 p-4">
        <div className="font-medium text-slate-900">
          {editandoId !== null
            ? `Editar plano #${editandoId}`
            : "Novo plano de ação"}
        </div>

        <Campo titulo="Ação">
          <textarea
            className={textareaClass}
            value={descricaoAcao}
            maxLength={2000}
            disabled={processando}
            onChange={(e) => setDescricaoAcao(e.target.value)}
            placeholder="Descreva a ação corretiva."
          />
        </Campo>

        <div className="grid gap-4 md:grid-cols-2">
          <Campo titulo="Responsável">
            <input
              className={inputClass}
              value={responsavel}
              maxLength={100}
              disabled={processando}
              onChange={(e) => setResponsavel(e.target.value)}
            />
          </Campo>

          <Campo titulo="Prazo">
            <input
              className={inputClass}
              type="date"
              value={dataPrazo}
              disabled={processando}
              onChange={(e) => setDataPrazo(e.target.value)}
            />
          </Campo>

          <Campo titulo="Prioridade">
            <select
              className={inputClass}
              value={prioridade}
              disabled={processando}
              onChange={(e) =>
                setPrioridade(
                  e.target.value as PrioridadePlanoAcao,
                )
              }
            >
              <option value="BAIXA">Baixa</option>
              <option value="MEDIA">Média</option>
              <option value="ALTA">Alta</option>
              <option value="CRITICA">Crítica</option>
            </select>
          </Campo>

          {editandoId !== null && (
            <Campo titulo="Status">
              <select
                className={inputClass}
                value={statusEdicao}
                disabled={processando}
                onChange={(e) =>
                  setStatusEdicao(
                    e.target.value as StatusEditavel,
                  )
                }
              >
                <option value="ABERTO">Aberto</option>
                <option value="EM_ANDAMENTO">
                  Em andamento
                </option>
                <option value="CANCELADO">Cancelado</option>
              </select>
            </Campo>
          )}
        </div>

        <Campo titulo="Observação">
          <textarea
            className={textareaClass}
            value={observacao}
            maxLength={2000}
            disabled={processando}
            onChange={(e) => setObservacao(e.target.value)}
          />
        </Campo>

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className={primaryButtonClass}
            disabled={processando}
            onClick={() => void salvarPlano()}
          >
            {processando
              ? "Processando..."
              : editandoId !== null
                ? "Salvar alterações"
                : "Criar plano"}
          </button>

          {editandoId !== null && (
            <button
              type="button"
              className={buttonClass}
              disabled={processando}
              onClick={limparFormularioPlano}
            >
              Cancelar edição
            </button>
          )}
        </div>
      </div>

      <div className="mt-6 grid gap-4">
        {planos.length === 0 && (
          <div className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            Nenhum plano de ação registrado.
          </div>
        )}

        {planos.map((plano) => {
          const aberto =
            planoDetalheId === plano.id_plano_acao;

          return (
            <div
              key={plano.id_plano_acao}
              className="rounded-lg border border-slate-200"
            >
              <div className="p-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-slate-900">
                        Plano #{plano.id_plano_acao}
                      </span>

                      <BadgeStatus status={plano.status} />

                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
                        {plano.prioridade}
                      </span>
                    </div>

                    <div className="mt-3 whitespace-pre-wrap text-sm text-slate-700">
                      {plano.descricao_acao}
                    </div>

                    <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
                      <Info
                        titulo="Responsável"
                        valor={plano.responsavel}
                      />
                      <Info
                        titulo="Prazo"
                        valor={formatarDataCurta(plano.data_prazo)}
                      />
                      <Info
                        titulo="Criado por"
                        valor={plano.criado_por}
                      />
                      <Info
                        titulo="Conclusão"
                        valor={formatarData(
                          plano.data_hora_conclusao,
                        )}
                      />
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {plano.status !== "CONCLUIDO" && (
                      <button
                        type="button"
                        className={buttonClass}
                        disabled={processando}
                        onClick={() => iniciarEdicao(plano)}
                      >
                        Editar
                      </button>
                    )}

                    {plano.status !== "CONCLUIDO" &&
                      plano.status !== "CANCELADO" && (
                        <button
                          type="button"
                          className={buttonClass}
                          disabled={processando}
                          onClick={() => void concluir(plano)}
                        >
                          Concluir
                        </button>
                      )}

                    <button
                      type="button"
                      className={buttonClass}
                      disabled={processando}
                      onClick={() => void alternarDetalhes(plano)}
                    >
                      {aberto
                        ? "Ocultar detalhes"
                        : "Evidências / Eficácia"}
                    </button>
                  </div>
                </div>
              </div>

              {aberto && (
                <div className="border-t border-slate-200 bg-slate-50 p-4">
                  <div>
                    <h4 className="font-semibold text-slate-900">
                      Evidências
                    </h4>

                    <div className="mt-3 grid gap-3">
                      {(evidencias[plano.id_plano_acao] ?? [])
                        .length === 0 ? (
                        <div className="text-sm text-slate-500">
                          Nenhuma evidência registrada.
                        </div>
                      ) : (
                        (
                          evidencias[plano.id_plano_acao] ?? []
                        ).map((item) => (
                          <div
                            key={item.id_evidencia}
                            className="rounded-md border border-slate-200 bg-white p-3"
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="text-sm">
                                <div className="font-medium text-slate-900">
                                  {item.tipo_evidencia}
                                </div>

                                {item.descricao && (
                                  <div className="mt-1 text-slate-600">
                                    {item.descricao}
                                  </div>
                                )}

                                {item.referencia_arquivo && (
                                  <div className="mt-1 break-all text-slate-500">
                                    {item.referencia_arquivo}
                                  </div>
                                )}

                                <div className="mt-2 text-xs text-slate-400">
                                  {item.criado_por} ·{" "}
                                  {formatarData(
                                    item.data_hora_criacao,
                                  )}
                                </div>
                              </div>

                              <button
                                type="button"
                                className="text-xs font-medium text-red-600 hover:underline"
                                disabled={processando}
                                onClick={() =>
                                  void removerEvidencia(
                                    plano.id_plano_acao,
                                    item.id_evidencia,
                                  )
                                }
                              >
                                Remover
                              </button>
                            </div>
                          </div>
                        ))
                      )}
                    </div>

                    <div className="mt-4 grid gap-3 rounded-md border border-slate-200 bg-white p-3">
                      <div className="grid gap-3 md:grid-cols-2">
                        <Campo titulo="Tipo">
                          <input
                            className={inputClass}
                            value={tipoEvidencia}
                            maxLength={30}
                            disabled={processando}
                            onChange={(e) =>
                              setTipoEvidencia(e.target.value)
                            }
                          />
                        </Campo>

                        <Campo titulo="Referência / arquivo">
                          <input
                            className={inputClass}
                            value={referenciaArquivo}
                            maxLength={1000}
                            disabled={processando}
                            onChange={(e) =>
                              setReferenciaArquivo(
                                e.target.value,
                              )
                            }
                          />
                        </Campo>
                      </div>

                      <Campo titulo="Descrição">
                        <textarea
                          className={textareaClass}
                          value={descricaoEvidencia}
                          maxLength={1000}
                          disabled={processando}
                          onChange={(e) =>
                            setDescricaoEvidencia(
                              e.target.value,
                            )
                          }
                        />
                      </Campo>

                      <div>
                        <button
                          type="button"
                          className={buttonClass}
                          disabled={processando}
                          onClick={() =>
                            void adicionarEvidencia(
                              plano.id_plano_acao,
                            )
                          }
                        >
                          Adicionar evidência
                        </button>
                      </div>
                    </div>
                  </div>

                  {plano.status === "CONCLUIDO" && (
                    <div className="mt-6 border-t border-slate-200 pt-5">
                      <div className="flex flex-col gap-1">
                        <h4 className="font-semibold text-slate-900">
                          Validação de Eficácia
                        </h4>
                        <p className="text-sm text-slate-500">
                          Verifique se a ação corretiva eliminou ou
                          reduziu efetivamente a causa da divergência.
                        </p>
                      </div>

                      <div className="mt-4 grid gap-3">
                        {(validacoes[plano.id_plano_acao] ?? [])
                          .length === 0 ? (
                          <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                            Este plano ainda não possui validação de
                            eficácia.
                          </div>
                        ) : (
                          (
                            validacoes[plano.id_plano_acao] ?? []
                          ).map((item) => (
                            <div
                              key={
                                item.id_validacao_eficacia
                              }
                              className="rounded-md border border-slate-200 bg-white p-3"
                            >
                              <div className="flex flex-wrap items-center gap-2">
                                <span
                                  className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                                    item.resultado === "EFICAZ"
                                      ? "bg-green-100 text-green-700"
                                      : "bg-red-100 text-red-700"
                                  }`}
                                >
                                  {item.resultado}
                                </span>

                                <span className="text-xs text-slate-500">
                                  {item.validado_por} ·{" "}
                                  {formatarData(
                                    item.data_hora_validacao,
                                  )}
                                </span>
                              </div>

                              <div className="mt-2 text-sm text-slate-700">
                                <strong>Critério:</strong>{" "}
                                {item.criterio_validacao}
                              </div>

                              {item.observacao && (
                                <div className="mt-1 text-sm text-slate-600">
                                  <strong>Observação:</strong>{" "}
                                  {item.observacao}
                                </div>
                              )}
                            </div>
                          ))
                        )}
                      </div>

                      {validacoes[
                        plano.id_plano_acao
                      ]?.[0]?.resultado === "INEFICAZ" && (
                        <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-4">
                          <div className="font-medium text-red-800">
                            Ação corretiva não eficaz
                          </div>

                          <p className="mt-1 text-sm text-red-700">
                            {planos.some(
                              (outroPlano) =>
                                outroPlano.id_plano_acao !==
                                  plano.id_plano_acao &&
                                (
                                  outroPlano.status === "ABERTO" ||
                                  outroPlano.status === "EM_ANDAMENTO"
                                ),
                            )
                              ? "A tratativa permanece aberta e já existe outra ação corretiva ativa."
                              : "A tratativa permanece aberta e uma nova ação corretiva deve ser criada."}
                          </p>
                        </div>
                      )}

                      <div className="mt-4 grid gap-3 rounded-md border border-slate-200 bg-white p-4">
                        <Campo titulo="Resultado">
                          <select
                            className={inputClass}
                            value={resultadoEficacia}
                            disabled={processando}
                            onChange={(e) =>
                              setResultadoEficacia(
                                e.target
                                  .value as ResultadoValidacaoEficacia,
                              )
                            }
                          >
                            <option value="EFICAZ">Eficaz</option>
                            <option value="INEFICAZ">
                              Ineficaz
                            </option>
                          </select>
                        </Campo>

                        <Campo titulo="Critério de validação">
                          <textarea
                            className={textareaClass}
                            value={criterioValidacao}
                            maxLength={2000}
                            disabled={processando}
                            placeholder="Ex.: ausência de reincidência após nova contagem, auditoria ou período de acompanhamento."
                            onChange={(e) =>
                              setCriterioValidacao(
                                e.target.value,
                              )
                            }
                          />
                        </Campo>

                        <Campo titulo="Observação">
                          <textarea
                            className={textareaClass}
                            value={observacaoValidacao}
                            maxLength={2000}
                            disabled={processando}
                            onChange={(e) =>
                              setObservacaoValidacao(
                                e.target.value,
                              )
                            }
                          />
                        </Campo>

                        <div>
                          <button
                            type="button"
                            className={primaryButtonClass}
                            disabled={
                              processando ||
                              !criterioValidacao.trim()
                            }
                            onClick={() =>
                              void validarEficacia(
                                plano.id_plano_acao,
                              )
                            }
                          >
                            Registrar validação
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
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
      <div className="text-xs uppercase text-slate-500">
        {titulo}
      </div>
      <div className="mt-1 break-words font-medium text-slate-900">
        {valor}
      </div>
    </div>
  );
}

function BadgeStatus({
  status,
}: {
  status: StatusPlanoAcao;
}) {
  let classe = "bg-slate-100 text-slate-700";

  if (status === "CONCLUIDO") {
    classe = "bg-green-100 text-green-700";
  } else if (status === "EM_ANDAMENTO") {
    classe = "bg-amber-100 text-amber-800";
  } else if (status === "CANCELADO") {
    classe = "bg-red-100 text-red-700";
  }

  return (
    <span
      className={`rounded-full px-2.5 py-1 text-xs font-medium ${classe}`}
    >
      {status}
    </span>
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

function formatarDataCurta(valor: string | null | undefined) {
  if (!valor) {
    return "-";
  }

  const partes = valor.slice(0, 10).split("-");

  if (partes.length !== 3) {
    return valor;
  }

  return `${partes[2]}/${partes[1]}/${partes[0]}`;
}

function mensagemErro(e: unknown) {
  return e instanceof Error
    ? e.message
    : "Erro inesperado ao processar o plano de ação.";
}
