import { createFileRoute } from "@tanstack/react-router";
import { useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  obterInventarioAtual,
  salvarInventarioAtual,
} from "@/lib/inventarioAtual";
import {
  buscarAnaliseRotativo,
  finalizarInventarioRotativo,
  gerarRecontagemRotativo,
  listarInventariosRotativos,
  registrarDecisoesRotativoLote,
  type AnaliseRotativo,
} from "@/services/rotativoService";

interface AnaliseCiclicaSearch {
  inventario?: number;
}

type TipoDecisao =
  | "RECONTAR"
  | "JUSTIFICAR_DIVERGENCIA";

export const Route = createFileRoute("/analise-ciclica")({
  head: () => ({
    meta: [
      {
        title:
          "An\u00e1lise C\u00edclica \u2014 SGI",
      },
    ],
  }),
  validateSearch: (
    search: Record<string, unknown>,
  ): AnaliseCiclicaSearch => {
    const idInventario = Number(
      search["inventario"],
    );

    if (
      Number.isInteger(idInventario) &&
      idInventario > 0
    ) {
      return {
        inventario: idInventario,
      };
    }

    return {};
  },
  component: AnaliseCiclicaPage,
});

function AnaliseCiclicaPage() {
  const navigate = useNavigate();

  const {
    inventario: idInventarioUrl,
  } = Route.useSearch();

  const idInventario =
    idInventarioUrl ??
    obterInventarioAtual();

  const [analise, setAnalise] =
    useState<AnaliseRotativo | null>(null);

  const [
    chavesSelecionadas,
    setChavesSelecionadas,
  ] = useState<Set<string>>(
    () => new Set<string>(),
  );

  const [
    acaoConfirmacao,
    setAcaoConfirmacao,
  ] = useState<TipoDecisao | null>(null);

  const [justificativa, setJustificativa] =
    useState("");

  const [carregando, setCarregando] =
    useState(true);

  const [processando, setProcessando] =
    useState(false);

  const [erro, setErro] =
    useState<string | null>(null);

  const [sucesso, setSucesso] =
    useState<string | null>(null);

  const pendentes = useMemo(
    () =>
      analise?.itens.filter(
        (item) =>
          item.requer_decisao &&
          item.pendente_decisao,
      ) ?? [],
    [analise],
  );

  const itensSelecionados = useMemo(
    () =>
      pendentes.filter((item) =>
        chavesSelecionadas.has(
          item.chave,
        ),
      ),
    [pendentes, chavesSelecionadas],
  );

  const todasSelecionadas =
    pendentes.length > 0 &&
    itensSelecionados.length ===
      pendentes.length;

  useEffect(() => {
    void iniciar();
  }, [idInventario]);

  async function iniciar() {
    setCarregando(true);
    setErro(null);
    setSucesso(null);
    setAnalise(null);
    setChavesSelecionadas(
      new Set<string>(),
    );

    try {
      if (!idInventario) {
        throw new Error(
          "Nenhum invent\u00e1rio foi selecionado.",
        );
      }

      const lista =
        await listarInventariosRotativos();

      const inventarioEncontrado =
        lista.find(
          (item) =>
            item.id_inventario ===
            idInventario,
        );

      if (!inventarioEncontrado) {
        throw new Error(
          `O invent\u00e1rio #${idInventario} n\u00e3o ` +
            "\u00e9 ROTATIVO ou n\u00e3o est\u00e1 dispon\u00edvel.",
        );
      }

      salvarInventarioAtual(
        inventarioEncontrado.id_inventario,
        "ROTATIVO",
      );

      setAnalise(
        await buscarAnaliseRotativo(
          inventarioEncontrado.id_inventario,
        ),
      );
    } catch (e) {
      setErro(msg(e));
    } finally {
      setCarregando(false);
    }
  }

  async function atualizar() {
    if (!idInventario) return;

    setErro(null);

    try {
      setAnalise(
        await buscarAnaliseRotativo(
          idInventario,
        ),
      );

      setChavesSelecionadas(
        new Set<string>(),
      );
    } catch (e) {
      setErro(msg(e));
    }
  }

  function alternarItem(
    chave: string,
  ) {
    setChavesSelecionadas(
      (selecionadas) => {
        const novas =
          new Set(selecionadas);

        if (novas.has(chave)) {
          novas.delete(chave);
        } else {
          novas.add(chave);
        }

        return novas;
      },
    );
  }

  function alternarTodas() {
    if (todasSelecionadas) {
      setChavesSelecionadas(
        new Set<string>(),
      );
      return;
    }

    setChavesSelecionadas(
      new Set(
        pendentes.map(
          (item) => item.chave,
        ),
      ),
    );
  }

  function solicitarConfirmacao(
    acao: TipoDecisao,
  ) {
    if (
      itensSelecionados.length === 0
    ) {
      setErro(
        "Selecione pelo menos uma diverg\u00eancia.",
      );
      return;
    }

    setJustificativa("");
    setErro(null);
    setSucesso(null);
    setAcaoConfirmacao(acao);
  }

  function fecharConfirmacao() {
    if (processando) return;

    setAcaoConfirmacao(null);
    setJustificativa("");
  }

  async function confirmarDecisao() {
    if (
      !analise ||
      !acaoConfirmacao ||
      itensSelecionados.length === 0
    ) {
      return;
    }

    if (
      acaoConfirmacao === "RECONTAR" &&
      analise.numero_rodada >= 2
    ) {
      setErro(
        "A R2 e a rodada final do inventario ROTATIVO. " +
          "Divergencias remanescentes devem ser justificadas.",
      );
      setAcaoConfirmacao(null);
      return;
    }

    if (
      acaoConfirmacao ===
        "JUSTIFICAR_DIVERGENCIA" &&
      !justificativa.trim()
    ) {
      setErro(
        "Informe a justificativa.",
      );
      return;
    }

    const acao = acaoConfirmacao;
    const quantidade =
      itensSelecionados.length;

    setProcessando(true);
    setErro(null);
    setSucesso(null);

    try {
      const resultado =
        await registrarDecisoesRotativoLote(
          analise.id_inventario,
          {
            id_rodada:
              analise.id_rodada,
            decisao: acao,
            justificativa:
              acao ===
              "JUSTIFICAR_DIVERGENCIA"
                ? justificativa.trim()
                : null,
            itens:
              itensSelecionados.map(
                (item) => ({
                  localizacao:
                    item.localizacao,
                  codigo:
                    item.codigo,
                  lote:
                    item.lote || null,
                }),
              ),
          },
        );

      setAcaoConfirmacao(null);
      setJustificativa("");
      setChavesSelecionadas(
        new Set<string>(),
      );

      let analiseAtualizada =
        await buscarAnaliseRotativo(
          analise.id_inventario,
        );

      let recontagemGerada = false;

      if (
        analiseAtualizada.numero_rodada === 1 &&
        analiseAtualizada
          .pode_gerar_recontagem
      ) {
        const localizacoes =
          Array.from(
            new Set(
              analiseAtualizada.itens
                .filter(
                  (item) =>
                    item.pendente_recontagem,
                )
                .map(
                  (item) =>
                    item.localizacao,
                ),
            ),
          );

        if (localizacoes.length > 0) {
          await gerarRecontagemRotativo(
            analise.id_inventario,
            localizacoes,
          );

          recontagemGerada = true;

          analiseAtualizada =
            await buscarAnaliseRotativo(
              analise.id_inventario,
            );
        }
      }

      setAnalise(analiseAtualizada);

      const total =
        resultado.quantidade_processada ||
        quantidade;

      if (recontagemGerada) {
        setSucesso(
          `${total} item(ns) processado(s). ` +
            "A rodada de recontagem foi gerada automaticamente.",
        );
      } else if (
        acao === "RECONTAR"
      ) {
        setSucesso(
          `${total} item(ns) marcado(s) para recontagem.`,
        );
      } else {
        setSucesso(
          `${total} diverg\u00eancia(s) justificada(s).`,
        );
      }
    } catch (e) {
      setErro(msg(e));

      try {
        setAnalise(
          await buscarAnaliseRotativo(
            analise.id_inventario,
          ),
        );
      } catch {
        // Mantem o erro original.
      }
    } finally {
      setProcessando(false);
    }
  }

  async function finalizar() {
    if (!analise) return;

    setProcessando(true);
    setErro(null);
    setSucesso(null);

    try {
      await finalizarInventarioRotativo(
        analise.id_inventario,
      );

      setSucesso(
        "Invent?rio finalizado com sucesso.",
      );

      await navigate({
        to: "/historico",
        search: {
          inventario:
            analise.id_inventario,
          aba: "resultado-final",
        },
      });

      return;

      setSucesso(
        "Invent\u00e1rio finalizado com sucesso.",
      );

      await atualizar();
    } catch (e) {
      setErro(msg(e));
    } finally {
      setProcessando(false);
    }
  }

  const confirmandoRecontagem =
    acaoConfirmacao === "RECONTAR";

  return (
    <main className="mx-auto w-full max-w-7xl space-y-5 p-4">
      <header>
        <h1 className="text-lg font-bold uppercase text-primary">
          {"An\u00e1lise C\u00edclica"}
        </h1>

        <p className="text-sm text-muted-foreground">
          {(analise?.numero_rodada ?? 0) >= 2
            ? "R2 conclu\u00edda: analise as diverg\u00eancias remanescentes e registre a justificativa para o encerramento. N\u00e3o existe R3 no ROTATIVO."
            : "Analise as diverg\u00eancias e defina o tratamento dos itens."}
        </p>
      </header>

      {erro ? (
        <Box
          texto={erro}
          classe="border-destructive/40 bg-destructive/5 text-destructive"
        />
      ) : null}

      {sucesso ? (
        <Box
          texto={sucesso}
          classe="border-green-300 bg-green-50 text-green-800"
        />
      ) : null}

      {carregando ? (
        <Box texto="Carregando..." />
      ) : analise ? (
        <>
          <section className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
            <Kpi
              titulo="Itens"
              valor={analise.resumo.total_itens}
            />
            <Kpi
              titulo="OK"
              valor={analise.resumo.ok}
            />
            <Kpi
              titulo="Faltas"
              valor={analise.resumo.faltas}
            />
            <Kpi
              titulo="Sobras"
              valor={analise.resumo.sobras}
            />
            <Kpi
              titulo={"\u0044iverg\u00eancias"}
              valor={
                analise.resumo.divergencias
              }
            />
            <Kpi
              titulo={"\u0053em decis\u00e3o"}
              valor={
                analise.resumo.itens_sem_decisao
              }
            />
            <Kpi
              titulo="Recontagem"
              valor={
                analise.resumo.itens_para_recontagem
              }
            />
            <Kpi
              titulo="Justificadas"
              valor={
                analise.resumo
                  .divergencias_justificadas
              }
            />
          </section>

          <section className="rounded-lg border bg-card p-4">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              <Info
                titulo={"\u0049nvent\u00e1rio"}
                valor={
                  analise.codigo_inventario
                }
              />
              <Info
                titulo="Status"
                valor={
                  analise.status_inventario
                }
              />
              <Info
                titulo="Rodada"
                valor={String(
                  analise.numero_rodada,
                )}
              />
              <Info
                titulo="Status rodada"
                valor={
                  analise.status_rodada
                }
              />
              <Info
                titulo={"\u004cocaliza\u00e7\u00f5es"}
                valor={
                  `${analise.resumo.localizacoes_concluidas}/` +
                  `${analise.resumo.total_localizacoes}`
                }
              />
            </div>
          </section>

          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={
                processando ||
                !analise.pode_finalizar_inventario
              }
              onClick={() =>
                void finalizar()
              }
            >
              {"Finalizar invent\u00e1rio"}
            </Button>

            <Button
              type="button"
              variant="outline"
              disabled={processando}
              onClick={() =>
                void atualizar()
              }
            >
              Atualizar
            </Button>
          </div>

          <section className="space-y-3">
            <div>
              <h2 className="font-bold uppercase text-primary">
                {
                  "Pend\u00eancias para decis\u00e3o"
                }
              </h2>

              <p className="text-sm text-muted-foreground">
                {pendentes.length}
                {" item(ns) aguardando tratamento"}
              </p>
            </div>

            {pendentes.length > 0 ? (
              <div className="rounded-lg border border-primary/20 bg-card p-4 shadow-sm">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                  <div className="flex flex-wrap items-center gap-3">
                    <Button
                      type="button"
                      variant="outline"
                      disabled={processando}
                      onClick={alternarTodas}
                    >
                      {todasSelecionadas
                        ? "Limpar sele\u00e7\u00e3o"
                        : "Selecionar todas"}
                    </Button>

                    <span className="text-sm font-semibold text-primary">
                      {itensSelecionados.length}
                      {" de "}
                      {pendentes.length}
                      {" selecionado(s)"}
                    </span>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {analise.numero_rodada === 1 ? (
                    <Button
                      type="button"
                      disabled={
                        processando ||
                        itensSelecionados.length ===
                          0
                      }
                      onClick={() =>
                        solicitarConfirmacao(
                          "RECONTAR",
                        )
                      }
                    >
                      Recontar
                    </Button>
                    ) : null}

                    <Button
                      type="button"
                      variant="outline"
                      disabled={
                        processando ||
                        itensSelecionados.length ===
                          0
                      }
                      onClick={() =>
                        solicitarConfirmacao(
                          "JUSTIFICAR_DIVERGENCIA",
                        )
                      }
                    >
                      {
                        "Justificar diverg\u00eancia"
                      }
                    </Button>
                  </div>
                </div>
              </div>
            ) : null}

            {pendentes.length === 0 ? (
              <Box
                texto={
                  "Nenhuma diverg\u00eancia aguarda decis\u00e3o."
                }
              />
            ) : (
              pendentes.map((item) => {
                const selecionado =
                  chavesSelecionadas.has(
                    item.chave,
                  );

                return (
                  <article
                    key={item.chave}
                    className={
                      "rounded-lg border bg-card p-4 transition " +
                      (selecionado
                        ? "border-primary ring-2 ring-primary/15"
                        : "hover:border-primary/40")
                    }
                  >
                    <div className="flex items-start gap-3">
                      <input
                        type="checkbox"
                        checked={selecionado}
                        disabled={processando}
                        onChange={() =>
                          alternarItem(
                            item.chave,
                          )
                        }
                        aria-label={
                          `Selecionar ${item.codigo}`
                        }
                        className="mt-1 size-5 shrink-0 accent-primary"
                      />

                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <p className="font-mono font-bold text-primary">
                              {item.codigo}
                              {item.lote
                                ? ` \u00b7 Lote ${item.lote}`
                                : ""}
                            </p>

                            <p className="mt-1 text-sm text-muted-foreground">
                              {item.produto ??
                                "Produto sem descri\u00e7\u00e3o"}
                            </p>

                            <p className="text-xs text-muted-foreground">
                              {"Localiza\u00e7\u00e3o: "}
                              {item.localizacao}
                            </p>
                          </div>

                          <span className="rounded-full bg-orange-100 px-3 py-1 text-xs font-bold text-orange-800">
                            {tecnico(
                              item.status,
                            )}
                          </span>
                        </div>

                        <div className="mt-3 rounded-md border border-orange-200/70 bg-orange-50/50 px-3 py-2 dark:border-orange-900/60 dark:bg-orange-950/20">
                          <p className="text-[10px] font-bold uppercase tracking-wide text-orange-700 dark:text-orange-300">
                            {"Motivo da diverg\u00eancia"}
                          </p>

                          <p className="mt-0.5 text-sm font-semibold text-foreground">
                            {motivoDivergencia(item)}
                          </p>

                          {item.subtipo_divergencia ? (
                            <p className="mt-0.5 text-[11px] text-muted-foreground">
                              {"Classifica\u00e7\u00e3o: "}
                              {tecnico(
                                item.subtipo_divergencia,
                              )}
                            </p>
                          ) : null}
                        </div>

                        <div className="mt-4 grid grid-cols-3 gap-3 border-t pt-3">
                          <Valor
                            titulo="Estoque"
                            valor={
                              item.qtd_estoque
                            }
                          />
                          <Valor
                            titulo="Contado"
                            valor={
                              item.qtd_contada
                            }
                          />
                          <Valor
                            titulo={"\u0044iferen\u00e7a"}
                            valor={
                              item.diferenca
                            }
                          />
                        </div>
                      </div>
                    </div>
                  </article>
                );
              })
            )}
          </section>
        </>
      ) : (
        <Box
          texto={
            "Selecione um invent\u00e1rio ROTATIVO."
          }
        />
      )}

      <AlertDialog
        open={acaoConfirmacao !== null}
        onOpenChange={(aberto) => {
          if (!aberto) {
            fecharConfirmacao();
          }
        }}
      >
        <AlertDialogContent className="max-w-lg">
          <AlertDialogHeader>
            <AlertDialogTitle>
              {confirmandoRecontagem
                ? "Confirmar recontagem"
                : "Confirmar justificativa"}
            </AlertDialogTitle>

            <AlertDialogDescription>
              {confirmandoRecontagem
                ? `Voc\u00ea selecionou ${itensSelecionados.length} item(ns). Tem certeza de que deseja envi\u00e1-los para recontagem?`
                : `Voc\u00ea selecionou ${itensSelecionados.length} diverg\u00eancia(s). Informe a justificativa e confirme a decis\u00e3o.`}
            </AlertDialogDescription>
          </AlertDialogHeader>

          {!confirmandoRecontagem ? (
            <textarea
              value={justificativa}
              onChange={(event) =>
                setJustificativa(
                  event.target.value,
                )
              }
              placeholder={
                "Justificativa para as diverg\u00eancias selecionadas"
              }
              autoFocus
              disabled={processando}
              className="min-h-32 w-full rounded-md border bg-background p-3 text-sm outline-none focus:ring-2 focus:ring-primary"
            />
          ) : null}

          <div className="rounded-md bg-muted px-3 py-2 text-sm">
            <span className="font-semibold">
              Quantidade selecionada:
            </span>{" "}
            {itensSelecionados.length}
          </div>

          <AlertDialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={processando}
              onClick={
                fecharConfirmacao
              }
            >
              Cancelar
            </Button>

            <Button
              type="button"
              disabled={
                processando ||
                itensSelecionados.length ===
                  0 ||
                (
                  !confirmandoRecontagem &&
                  !justificativa.trim()
                )
              }
              onClick={() =>
                void confirmarDecisao()
              }
            >
              {processando
                ? "Processando..."
                : "Confirmar"}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </main>
  );
}

function motivoDivergencia(
  item: AnaliseRotativo["itens"][number],
): string {
  const subtipo = item.subtipo_divergencia
    ?.trim()
    .toUpperCase();

  const diferenca = Number(item.diferenca);
  const quantidade = Math.abs(diferenca);
  const quantidadeFormatada = numero(quantidade);
  const unidade =
    quantidade === 1 ? "unidade" : "unidades";

  if (subtipo === "QUANTIDADE") {
    if (diferenca < 0) {
      return `Falta de ${quantidadeFormatada} ${unidade} em rela\u00e7\u00e3o ao estoque`;
    }

    if (diferenca > 0) {
      return `Sobra de ${quantidadeFormatada} ${unidade} em rela\u00e7\u00e3o ao estoque`;
    }

    return "Diverg\u00eancia de quantidade";
  }

  const motivos: Record<string, string> = {
    LOTE_INCORRETO:
      "Lote contado diferente do lote esperado",
    LOTE_E_QUANTIDADE:
      "Lote e quantidade divergentes",
    LOCALIZACAO_INCORRETA:
      "Produto contado em localiza\u00e7\u00e3o diferente da esperada",
    ITEM_SEM_SALDO:
      "Item contado sem saldo no estoque de refer\u00eancia",
    ITEM_NAO_PREVISTO:
      "Item n\u00e3o previsto no estoque de refer\u00eancia",
  };

  if (subtipo && motivos[subtipo]) {
    return motivos[subtipo];
  }

  if (subtipo) {
    return tecnico(subtipo);
  }

  if (diferenca < 0) {
    return `Falta de ${quantidadeFormatada} ${unidade} em rela\u00e7\u00e3o ao estoque`;
  }

  if (diferenca > 0) {
    return `Sobra de ${quantidadeFormatada} ${unidade} em rela\u00e7\u00e3o ao estoque`;
  }

  return "Motivo n\u00e3o informado";
}

function Kpi({
  titulo,
  valor,
}: {
  titulo: string;
  valor: number;
}) {
  return (
    <div className="rounded-lg border bg-card p-3">
      <p className="text-xs font-bold uppercase text-muted-foreground">
        {titulo}
      </p>

      <p className="text-2xl font-bold text-primary">
        {valor}
      </p>
    </div>
  );
}

function Info({
  titulo,
  valor,
}: {
  titulo: string;
  valor: string;
}) {
  return (
    <div>
      <p className="text-xs uppercase text-muted-foreground">
        {titulo}
      </p>

      <p className="font-bold text-primary">
        {valor}
      </p>
    </div>
  );
}

function Valor({
  titulo,
  valor,
}: {
  titulo: string;
  valor: number;
}) {
  return (
    <div>
      <p className="text-xs uppercase text-muted-foreground">
        {titulo}
      </p>

      <p className="text-lg font-bold text-primary">
        {numero(valor)}
      </p>
    </div>
  );
}

function Box({
  texto,
  classe = "text-muted-foreground",
}: {
  texto: string;
  classe?: string;
}) {
  return (
    <div
      className={
        `rounded-lg border bg-card p-4 text-sm ${classe}`
      }
    >
      {texto}
    </div>
  );
}

function numero(valor: number) {
  return new Intl.NumberFormat(
    "pt-BR",
    {
      maximumFractionDigits: 3,
    },
  ).format(valor);
}

function tecnico(valor: string) {
  return valor.replaceAll("_", " ");
}

function msg(e: unknown) {
  return e instanceof Error
    ? e.message
    : "Erro inesperado.";
}
