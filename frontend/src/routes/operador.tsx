import {
  createFileRoute,
  Link,
} from "@tanstack/react-router";

import {
  BellRing,
  CheckCircle2,
  ClipboardList,
  MapPin,
  PackageCheck,
  RefreshCw,
  ScanLine,
  Warehouse,
} from "lucide-react";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  limparInventarioAtual,
  obterInventarioAtual,
  salvarInventarioAtual,
} from "@/lib/inventarioAtual";

import {
  obterUsuarioSalvo,
} from "@/services/authService";

import {
  consultarInventarioDetalhe,
  consultarStatusSnapshot,
  listarInventariosAbertos,
} from "@/services/inventarioService";

import {
  consultarQuantidadeNaoLidas,
} from "@/services/notificationService";

import type {
  InventarioDetalhe,
  InventarioResumo,
} from "@/types/inventory";


export const Route = createFileRoute(
  "/operador",
)({
  head: () => ({
    meta: [
      {
        title:
          "\u00c1rea do Operador \u2014 SGI",
      },
    ],
  }),
  component: OperadorPage,
});


function primeiroNome(
  nome: string | null | undefined,
) {
  const valor =
    String(nome ?? "").trim();

  return (
    valor.split(/\s+/)[0] ||
    "Operador"
  );
}


function obterAcaoOperador(
  inventario: InventarioDetalhe,
) {
  const proximaAcao = String(
    inventario.proxima_acao ?? "",
  )
    .trim()
    .toUpperCase();

  /*
   * Nunca apresentar codigos internos
   * da maquina de estados ao operador.
   */
  if (
    proximaAcao.includes(
      "RECONTAGEM",
    )
  ) {
    return {
      titulo:
        "Continuar recontagem",
      descricao:
        `A recontagem da rodada R${inventario.rodada_atual} est\u00e1 em andamento.`,
      botao:
        "Continuar recontagem",
    };
  }

  return {
    titulo:
      "Continuar contagem",
    descricao:
      "Continue a execu\u00e7\u00e3o da rodada atual.",
    botao:
      "Continuar contagem",
  };
}


function CardInformacao({
  titulo,
  valor,
  detalhe,
  icone,
}: {
  titulo: string;
  valor: string | number;
  detalhe?: string;
  icone?: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            {titulo}
          </p>

          <p className="mt-1 truncate text-lg font-bold text-foreground">
            {valor}
          </p>

          {detalhe ? (
            <p className="mt-1 truncate text-xs text-muted-foreground">
              {detalhe}
            </p>
          ) : null}
        </div>

        {icone ? (
          <div className="shrink-0 rounded-lg bg-muted p-2 text-muted-foreground">
            {icone}
          </div>
        ) : null}
      </div>
    </div>
  );
}


function OperadorPage() {
  const usuario = useMemo(
    () => obterUsuarioSalvo(),
    [],
  );

  const [
    inventario,
    setInventario,
  ] = useState<InventarioDetalhe | null>(
    null,
  );

  const [
    atividades,
    setAtividades,
  ] = useState<InventarioResumo[]>([]);

  const [
    quantidadeEmPreparacao,
    setQuantidadeEmPreparacao,
  ] = useState(0);

  const [
    quantidadeNaoLidas,
    setQuantidadeNaoLidas,
  ] = useState(0);

  const [
    carregando,
    setCarregando,
  ] = useState(true);

  const [
    erro,
    setErro,
  ] = useState<string | null>(
    null,
  );


  const carregar = useCallback(
    async () => {
      setCarregando(true);
      setErro(null);

      try {
        const [
          resultadoNotificacoes,
          resultadoAbertos,
        ] = await Promise.allSettled([
          consultarQuantidadeNaoLidas(),
          listarInventariosAbertos(),
        ]);

        if (
          resultadoNotificacoes.status ===
          "fulfilled"
        ) {
          setQuantidadeNaoLidas(
            resultadoNotificacoes.value,
          );
        }

        if (
          resultadoAbertos.status !==
          "fulfilled"
        ) {
          throw new Error(
            "N\u00e3o foi poss\u00edvel consultar as atividades dispon\u00edveis.",
          );
        }

        const abertos =
          resultadoAbertos.value;

        /*
         * A home utiliza a mesma regra operacional
         * da tela de contagem: somente inventario
         * com snapshot gerado esta pronto.
         */
        const verificacoes =
          await Promise.all(
            abertos.map(
              async (item) => {
                const statusSnapshot =
                  await consultarStatusSnapshot(
                    item.id_inventario,
                  );

                return statusSnapshot
                  .snapshot_gerado
                  ? item
                  : null;
              },
            ),
          );

        const prontos =
          verificacoes.filter(
            (
              item,
            ): item is InventarioResumo =>
              item !== null,
          );

        setAtividades(prontos);

        setQuantidadeEmPreparacao(
          Math.max(
            0,
            abertos.length -
              prontos.length,
          ),
        );

        const idSalvo =
          obterInventarioAtual();

        const inventarioSalvo =
          idSalvo
            ? prontos.find(
                (item) =>
                  item.id_inventario ===
                  idSalvo,
              )
            : undefined;

        /*
         * Se o contexto salvo nao esta mais entre
         * as atividades prontas, ele nao deve
         * controlar a home.
         */
        if (
          idSalvo &&
          !inventarioSalvo
        ) {
          limparInventarioAtual();
        }

        /*
         * Prioridade:
         *
         * 1. contexto salvo ainda valido;
         * 2. se existe apenas uma atividade pronta,
         *    ela vira o contexto automaticamente;
         * 3. se existem varias, operador escolhe.
         */
        const selecionado =
          inventarioSalvo ??
          (
            prontos.length === 1
              ? prontos[0]
              : undefined
          );

        if (!selecionado) {
          setInventario(null);
          return;
        }

        if (!inventarioSalvo) {
          salvarInventarioAtual(
            selecionado.id_inventario,
            selecionado.tipo,
          );
        }

        const detalhe =
          await consultarInventarioDetalhe(
            selecionado.id_inventario,
          );

        setInventario(detalhe);
      } catch (erroCarregamento) {
        setInventario(null);
        setAtividades([]);

        setErro(
          erroCarregamento instanceof Error
            ? erroCarregamento.message
            : "N\u00e3o foi poss\u00edvel carregar a \u00e1rea do operador.",
        );
      } finally {
        setCarregando(false);
      }
    },
    [],
  );


  useEffect(() => {
    void carregar();
  }, [carregar]);


  const percentual = Math.max(
    0,
    Math.min(
      100,
      Number(
        inventario?.percentual_progresso ??
          0,
      ),
    ),
  );

  const nome =
    primeiroNome(usuario?.nome);

  const acaoOperador =
    inventario
      ? obterAcaoOperador(
          inventario,
        )
      : null;

  const variasAtividades =
    !inventario &&
    atividades.length > 1;

  const nenhumaAtividade =
    !carregando &&
    !inventario &&
    atividades.length === 0;


  return (
    <div className="space-y-5 p-4 md:p-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">
            {"\u00c1rea do Operador"}
          </p>

          <h1 className="mt-1 text-2xl font-bold tracking-tight">
            {`Ol\u00e1, ${nome}`}
          </h1>

          <p className="mt-1 text-sm text-muted-foreground">
            {
              "Consulte sua atividade atual e continue de onde parou."
            }
          </p>
        </div>

        <button
          type="button"
          onClick={() =>
            void carregar()
          }
          disabled={carregando}
          className="inline-flex h-10 w-fit items-center justify-center gap-2 rounded-md border border-border bg-background px-3 text-sm font-medium transition hover:bg-muted disabled:cursor-wait disabled:opacity-60"
        >
          <RefreshCw
            className={
              carregando
                ? "size-4 animate-spin"
                : "size-4"
            }
            aria-hidden="true"
          />

          Atualizar
        </button>
      </header>


      {erro ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {erro}
        </div>
      ) : null}


      {/* ==================================================
          ACAO PRINCIPAL
      ================================================== */}

      <section className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
        <div className="flex flex-col gap-5 p-5 md:flex-row md:items-center md:justify-between">
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
              {"A\u00e7\u00e3o necess\u00e1ria agora"}
            </p>

            {carregando ? (
              <div className="mt-3 h-16 animate-pulse rounded-lg bg-muted" />
            ) : inventario ? (
              <>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <h2 className="text-xl font-bold text-primary">
                    {acaoOperador?.titulo ??
                      "Continuar contagem"}
                  </h2>

                  <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-bold uppercase text-emerald-700">
                    {inventario.status}
                  </span>
                </div>

                <p className="mt-1 text-sm text-muted-foreground">
                  {inventario.codigo_inventario}
                  {" \u00b7 "}
                  {inventario.cliente}
                  {" \u00b7 "}
                  {inventario.armazem}
                  {" \u00b7 R"}
                  {inventario.rodada_atual}
                </p>

                <p className="mt-3 text-sm">
                  {acaoOperador?.descricao ??
                    "Continue a execu\u00e7\u00e3o da rodada atual."}
                </p>
              </>
            ) : variasAtividades ? (
              <>
                <h2 className="mt-2 text-xl font-bold text-primary">
                  {
                    "Escolha uma atividade para iniciar"
                  }
                </h2>

                <p className="mt-1 text-sm text-muted-foreground">
                  {`${atividades.length} invent\u00e1rios est\u00e3o liberados para contagem.`}
                </p>
              </>
            ) : quantidadeEmPreparacao > 0 ? (
              <>
                <h2 className="mt-2 text-xl font-bold">
                  {
                    "Aguardando libera\u00e7\u00e3o"
                  }
                </h2>

                <p className="mt-1 text-sm text-muted-foreground">
                  {quantidadeEmPreparacao === 1
                    ? "Existe 1 invent\u00e1rio em prepara\u00e7\u00e3o. Ele aparecer\u00e1 aqui quando estiver liberado para contagem."
                    : `Existem ${quantidadeEmPreparacao} invent\u00e1rios em prepara\u00e7\u00e3o. Eles aparecer\u00e3o aqui quando estiverem liberados para contagem.`}
                </p>
              </>
            ) : (
              <>
                <h2 className="mt-2 text-xl font-bold">
                  {
                    "Nenhuma atividade dispon\u00edvel"
                  }
                </h2>

                <p className="mt-1 text-sm text-muted-foreground">
                  {
                    "N\u00e3o h\u00e1 invent\u00e1rios liberados para execu\u00e7\u00e3o neste momento."
                  }
                </p>
              </>
            )}
          </div>

          {inventario ? (
            <Link
              to="/contagem"
              search={{
                inventario:
                  inventario.id_inventario,
              }}
              onClick={() =>
                salvarInventarioAtual(
                  inventario.id_inventario,
                  inventario.tipo,
                )
              }
              className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-md bg-primary px-5 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90"
            >
              <ScanLine
                className="size-4"
                aria-hidden="true"
              />

              {acaoOperador?.botao ??
                "Continuar contagem"}
            </Link>
          ) : null}
        </div>
      </section>


      {/* ==================================================
          VARIAS ATIVIDADES
      ================================================== */}

      {variasAtividades ? (
        <section className="rounded-xl border border-border bg-card shadow-sm">
          <div className="border-b border-border px-5 py-4">
            <h2 className="font-semibold">
              {
                "Atividades dispon\u00edveis"
              }
            </h2>

            <p className="mt-1 text-xs text-muted-foreground">
              {
                "Selecione o invent\u00e1rio que ser\u00e1 executado."
              }
            </p>
          </div>

          <div className="divide-y divide-border">
            {atividades.map(
              (atividade) => (
                <div
                  key={
                    atividade.id_inventario
                  }
                  className="flex flex-col gap-4 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-mono text-sm font-bold text-primary">
                        {
                          atividade.codigo_inventario
                        }
                      </p>

                      <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-bold uppercase text-emerald-700">
                        {
                          atividade.status
                        }
                      </span>
                    </div>

                    <p className="mt-1 truncate text-sm font-semibold">
                      {atividade.cliente}
                    </p>

                    <p className="mt-1 text-xs text-muted-foreground">
                      {atividade.armazem}
                      {" \u00b7 "}
                      {atividade.tipo}
                      {" \u00b7 R"}
                      {atividade.rodada_atual}
                    </p>
                  </div>

                  <Link
                    to="/contagem"
                    search={{
                      inventario:
                        atividade.id_inventario,
                    }}
                    onClick={() =>
                      salvarInventarioAtual(
                        atividade.id_inventario,
                        atividade.tipo,
                      )
                    }
                    className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90"
                  >
                    <ScanLine
                      className="size-4"
                      aria-hidden="true"
                    />

                    Iniciar contagem
                  </Link>
                </div>
              ),
            )}
          </div>
        </section>
      ) : null}


      {/* ==================================================
          CONTEXTO DA ATIVIDADE
      ================================================== */}

      {inventario ? (
        <>
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <CardInformacao
              titulo={"Invent\u00e1rio"}
              valor={
                inventario.codigo_inventario
              }
              detalhe={`#${inventario.id_inventario}`}
              icone={
                <ClipboardList className="size-4" />
              }
            />

            <CardInformacao
              titulo="Cliente"
              valor={inventario.cliente}
              detalhe={inventario.tipo}
              icone={
                <PackageCheck className="size-4" />
              }
            />

            <CardInformacao
              titulo={"Armaz\u00e9m"}
              valor={inventario.armazem}
              detalhe={"Opera\u00e7\u00e3o atual"}
              icone={
                <Warehouse className="size-4" />
              }
            />

            <CardInformacao
              titulo="Rodada"
              valor={`R${inventario.rodada_atual}`}
              detalhe={inventario.status}
              icone={
                <MapPin className="size-4" />
              }
            />
          </section>


          <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="font-semibold">
                  Progresso operacional
                </h2>

                <p className="mt-1 text-xs text-muted-foreground">
                  {
                    "Localiza\u00e7\u00f5es da rodada atual."
                  }
                </p>
              </div>

              <span className="font-mono text-xl font-bold text-primary">
                {percentual.toLocaleString(
                  "pt-BR",
                  {
                    maximumFractionDigits: 1,
                  },
                )}
                %
              </span>
            </div>

            <div className="mt-4 h-2.5 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-[width]"
                style={{
                  width: `${percentual}%`,
                }}
              />
            </div>

            <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
              <div className="rounded-lg border bg-muted/20 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Total
                </p>

                <p className="mt-1 font-mono text-lg font-bold">
                  {
                    inventario.total_localizacoes ??
                    0
                  }
                </p>
              </div>

              <div className="rounded-lg border bg-muted/20 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {"Conclu\u00eddas"}
                </p>

                <p className="mt-1 font-mono text-lg font-bold">
                  {
                    inventario.localizacoes_concluidas ??
                    0
                  }
                </p>
              </div>

              <div className="rounded-lg border bg-muted/20 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Pendentes
                </p>

                <p className="mt-1 font-mono text-lg font-bold">
                  {
                    inventario.localizacoes_pendentes ??
                    0
                  }
                </p>
              </div>

              <div className="rounded-lg border bg-muted/20 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Em contagem
                </p>

                <p className="mt-1 font-mono text-lg font-bold">
                  {
                    inventario.localizacoes_em_contagem ??
                    0
                  }
                </p>
              </div>
            </div>
          </section>
        </>
      ) : null}


      {/* ==================================================
          FLUXO E NOTIFICACOES
      ================================================== */}

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <h2 className="font-semibold">
            Fluxo de trabalho
          </h2>

          <p className="mt-1 text-xs text-muted-foreground">
            {
              "Sequ\u00eancia operacional da contagem."
            }
          </p>

          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            {[
              [
                "1",
                "Iniciar localiza\u00e7\u00e3o",
                "Informe ou bip a localiza\u00e7\u00e3o.",
              ],
              [
                "2",
                "Registrar itens",
                "C\u00f3digo, lote e quantidade.",
              ],
              [
                "3",
                "Encerrar localiza\u00e7\u00e3o",
                "Conclua antes de avan\u00e7ar.",
              ],
            ].map(
              ([
                numero,
                titulo,
                descricao,
              ]) => (
                <div
                  key={numero}
                  className="rounded-lg border border-border bg-muted/20 p-4"
                >
                  <span className="flex size-7 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
                    {numero}
                  </span>

                  <p className="mt-3 text-sm font-semibold">
                    {titulo}
                  </p>

                  <p className="mt-1 text-xs leading-5 text-muted-foreground">
                    {descricao}
                  </p>
                </div>
              ),
            )}
          </div>
        </div>


        <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="font-semibold">
                {"Notifica\u00e7\u00f5es"}
              </h2>

              <p className="mt-1 text-xs text-muted-foreground">
                {
                  "Avisos que ainda precisam ser consultados."
                }
              </p>
            </div>

            <BellRing
              className="size-5 text-muted-foreground"
              aria-hidden="true"
            />
          </div>

          <div className="mt-5 flex items-end justify-between">
            <div>
              <p className="font-mono text-3xl font-bold">
                {quantidadeNaoLidas}
              </p>

              <p className="text-xs text-muted-foreground">
                {"n\u00e3o lida(s)"}
              </p>
            </div>

            {quantidadeNaoLidas ===
            0 ? (
              <CheckCircle2
                className="size-6 text-emerald-600"
                aria-label="Sem notificacoes pendentes"
              />
            ) : (
              <span className="rounded-full bg-red-500 px-2 py-1 text-xs font-bold text-white">
                {quantidadeNaoLidas > 99
                  ? "99+"
                  : quantidadeNaoLidas}
              </span>
            )}
          </div>

          <p className="mt-4 border-t border-border pt-3 text-xs leading-5 text-muted-foreground">
            {
              "Use o sino no topo para abrir os detalhes e executar as a\u00e7\u00f5es dispon\u00edveis."
            }
          </p>
        </div>
      </section>


      {nenhumaAtividade &&
      quantidadeEmPreparacao === 0 ? (
        <p className="text-center text-xs text-muted-foreground">
          {
            "Novas atividades aparecer\u00e3o aqui quando forem liberadas pelo respons\u00e1vel pelo invent\u00e1rio."
          }
        </p>
      ) : null}
    </div>
  );
}
