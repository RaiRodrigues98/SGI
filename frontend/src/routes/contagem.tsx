import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";

import { EncerrarDialog } from "@/components/contagem/EncerrarDialog";
import { ItemForm } from "@/components/contagem/ItemForm";
import { ItensContadosList } from "@/components/contagem/ItensContadosList";
import { LocalizacaoBanner } from "@/components/contagem/LocalizacaoBanner";
import { LocalizacaoForm } from "@/components/contagem/LocalizacaoForm";
import { Button } from "@/components/ui/button";
import { useContagem } from "@/hooks/useContagem";
import {
  consultarContagemAtual,
  consultarConfiguracaoOperacional,
  consultarDetalheLocalizacao,
  type ConfiguracaoOperacionalInventario,
} from "@/services/contagemService";
import {
  consultarStatusSnapshot,
  listarInventariosAbertos,
} from "@/services/inventarioService";
import type {
  LocalizacaoOperacional,
} from "@/services/localizacaoService";
import type { ContextoContagem, InventarioResumo } from "@/types/inventory";

interface ContagemSearch {
  inventario?: number;
}

export const Route = createFileRoute("/contagem")({
  validateSearch: (search: Record<string, unknown>): ContagemSearch => {
    const valor = Number(search["inventario"]);

    if (Number.isInteger(valor) && valor > 0) {
      return {
        inventario: valor,
      };
    }

    return {};
  },
  head: () => ({
    meta: [{ title: "Contagem \u2014 SGI" }],
  }),
  component: ContagemPage,
});

function normalizarLocalizacao(valor: string): string {
  return valor.trim().toUpperCase();
}

function rotuloStatus(status: LocalizacaoOperacional["status"]): string {
  if (status === "EM_CONTAGEM") return "Em contagem";
  if (status === "CONCLUIDA") return "Concluída";
  return "Pendente";
}

function ContagemPage() {
  const { inventario } = Route.useSearch();
  const [contexto, setContexto] = useState<ContextoContagem | null>(null);
  const [configuracaoOperacional, setConfiguracaoOperacional] =
    useState<ConfiguracaoOperacionalInventario | null>(null);
  const [localizacoesEscopo, setLocalizacoesEscopo] = useState<
    LocalizacaoOperacional[]
  >([]);
  const [carregandoContexto, setCarregandoContexto] = useState(true);
  const [erroContexto, setErroContexto] = useState<string | null>(null);
  const [erroLocalizacao, setErroLocalizacao] = useState<string | null>(null);
  const [dialogAberto, setDialogAberto] = useState(false);
  const [tentativaCarregamento, setTentativaCarregamento] = useState(0);

  useEffect(() => {
    let ativo = true;

    async function resolverInventario(): Promise<number> {
      if (inventario) {
        return inventario;
      }

      const inventariosAbertos = await listarInventariosAbertos();

      const verificacoes = await Promise.all(
        inventariosAbertos.map(async (inventarioAberto) => {
          const statusSnapshot = await consultarStatusSnapshot(
            inventarioAberto.id_inventario,
          );

          return statusSnapshot.snapshot_gerado ? inventarioAberto : null;
        }),
      );

      const inventariosProntos = verificacoes.filter(
        (item): item is InventarioResumo => item !== null,
      );

      if (inventariosProntos.length === 0) {
        throw new Error(
          "Nenhuma contagem disponível no momento. " +
            "Aguarde o gestor preparar e liberar um inventário.",
        );
      }

      if (inventariosProntos.length > 1) {
        throw new Error(
          "Existe mais de um inventário pronto para contagem. " +
            "Solicite ao gestor a regularização dos inventários em aberto.",
        );
      }

      return inventariosProntos[0]!.id_inventario;
    }

    async function carregarContexto() {
      setCarregandoContexto(true);
      setContexto(null);
      setConfiguracaoOperacional(null);
      setErroContexto(null);
      setErroLocalizacao(null);
      setLocalizacoesEscopo([]);

      try {
        const idInventarioAtual = await resolverInventario();

        const [contagemAtual, configuracao] = await Promise.all([
          consultarContagemAtual(idInventarioAtual),
          consultarConfiguracaoOperacional(idInventarioAtual),
        ]);

        const rodada = contagemAtual.rodada;

        if (!ativo) {
          return;
        }

        if (
          Number(contagemAtual.id_inventario) !== Number(rodada.id_inventario)
        ) {
          throw new Error(
            "A contagem atual não corresponde à rodada do inventário.",
          );
        }

        if (
          Number(configuracao.id_inventario) !== Number(rodada.id_inventario)
        ) {
          throw new Error(
            "A configuração operacional não corresponde ao inventário atual.",
          );
        }

        setContexto({
          idInventario: rodada.id_inventario,
          codigoInventario: rodada.codigo_inventario,
          idRodada: rodada.id_rodada,
          numeroRodada: rodada.numero_rodada,
          tipoInventario: rodada.tipo_inventario,
          statusRodada: rodada.status,
        });

        setLocalizacoesEscopo(contagemAtual.localizacoes);
        setConfiguracaoOperacional(configuracao);
      } catch (erro: unknown) {
        if (!ativo) {
          return;
        }

        setContexto(null);
        setConfiguracaoOperacional(null);
        setLocalizacoesEscopo([]);

        setErroContexto(
          erro instanceof Error
            ? erro.message
            : "Não foi possível carregar o contexto da contagem.",
        );
      } finally {
        if (ativo) {
          setCarregandoContexto(false);
        }
      }
    }

    void carregarContexto();

    return () => {
      ativo = false;
    };
  }, [inventario, tentativaCarregamento]);

  const {
    localizacao,
    itens,
    resumo,
    salvando,
    cancelando,
    cancelarItem,
    iniciarLocalizacao,
    restaurarContagemAtual,
    validarCodigo,
    salvarItem,
    encerrarLocalizacao,
  } = useContagem(contexto, configuracaoOperacional);

  useEffect(() => {
    if (!contexto || carregandoContexto || localizacao) return;

    void restaurarContagemAtual(localizacoesEscopo).then((resultado) => {
      if (!resultado.ok && resultado.erro) {
        setErroLocalizacao(resultado.erro);
      }
    });
  }, [
    carregandoContexto,
    contexto,
    localizacao,
    localizacoesEscopo,
    restaurarContagemAtual,
  ]);

  async function atualizarLocalizacoesEscopo() {
    const idInventarioAtual = contexto?.idInventario;

    if (!idInventarioAtual) {
      return;
    }

    try {
      const contagemAtualizada =
        await consultarContagemAtual(idInventarioAtual);

      if (
        !contexto ||
        Number(contagemAtualizada.rodada.id_rodada) !==
          Number(contexto.idRodada)
      ) {
        return;
      }

      setLocalizacoesEscopo(
        contagemAtualizada.localizacoes,
      );
    } catch {
      // A operacao principal ja foi concluida.
      // Falha no refresh nao deve desfazer a contagem.
    }
  }

  const resumoLocalizacoes = useMemo(() => {
    return {
      total: localizacoesEscopo.length,
      pendentes: localizacoesEscopo.filter((item) => item.status === "PENDENTE")
        .length,
      emContagem: localizacoesEscopo.filter(
        (item) => item.status === "EM_CONTAGEM",
      ).length,
      concluidas: localizacoesEscopo.filter(
        (item) => item.status === "CONCLUIDA",
      ).length,
    };
  }, [localizacoesEscopo]);

  const percentualLocalizacoes =
    resumoLocalizacoes.total > 0
      ? Math.round(
          (
            resumoLocalizacoes.concluidas /
            resumoLocalizacoes.total
          ) * 100,
        )
      : 0;

  async function iniciarLocalizacaoValidada(
    codigoInformado: string,
  ): Promise<{ ok: boolean; erro?: string }> {
    setErroLocalizacao(null);

    if (!configuracaoOperacional) {
      const mensagem = "Configuração operacional não carregada.";
      setErroLocalizacao(mensagem);
      return { ok: false, erro: mensagem };
    }

    const codigo = normalizarLocalizacao(codigoInformado);

    if (configuracaoOperacional.localizacao.obrigatoria && !codigo) {
      const mensagem = "Informe a localização.";
      setErroLocalizacao(mensagem);
      return { ok: false, erro: mensagem };
    }

    if (!configuracaoOperacional.localizacao.validar_estoque) {
      const resultado = await iniciarLocalizacao(codigo);

      if (resultado.ok) await atualizarLocalizacoesEscopo();
      if (!resultado.ok && resultado.erro) setErroLocalizacao(resultado.erro);
      return resultado;
    }

    if (!contexto) {
      const mensagem = "Contexto da contagem ainda não carregado.";
      setErroLocalizacao(mensagem);
      return { ok: false, erro: mensagem };
    }

    try {
      const detalhe = await consultarDetalheLocalizacao(
        contexto.idInventario,
        codigo,
      );

      if (
        Number(detalhe.id_inventario) !== Number(contexto.idInventario) ||
        Number(detalhe.id_rodada) !== Number(contexto.idRodada) ||
        normalizarLocalizacao(detalhe.localizacao) !== codigo
      ) {
        throw new Error(
          "A localização retornada não corresponde à contagem atual.",
        );
      }

      if (detalhe.status_localizacao === "CONCLUIDA") {
        const mensagem = `A localização ${detalhe.localizacao} já foi concluída nesta rodada.`;
        setErroLocalizacao(mensagem);
        return { ok: false, erro: mensagem };
      }

      if (detalhe.status_localizacao === "EM_CONTAGEM") {
        const retomada = await iniciarLocalizacao(
          detalhe.localizacao,
        );

        if (retomada.ok) {
          await atualizarLocalizacoesEscopo();
          return retomada;
        }

        const usuarioSessao =
          detalhe.usuario_sessao_nome?.trim() ||
          detalhe.usuario_sessao_login?.trim();

        const mensagem =
          retomada.erro ??
          (usuarioSessao
            ? `A localização ${detalhe.localizacao} já está em contagem por ${usuarioSessao}.`
            : `A localização ${detalhe.localizacao} já está em contagem por outro usuário.`);

        setErroLocalizacao(mensagem);
        return { ok: false, erro: mensagem };
      }

      const resultado = await iniciarLocalizacao(detalhe.localizacao);

      if (resultado.ok) await atualizarLocalizacoesEscopo();
      if (!resultado.ok && resultado.erro) setErroLocalizacao(resultado.erro);
      return resultado;
    } catch (erro: unknown) {
      const mensagem =
        erro instanceof Error
          ? erro.message
          : "Não foi possível validar a localização.";
      setErroLocalizacao(mensagem);
      return { ok: false, erro: mensagem };
    }
  }

  async function encerrarLocalizacaoComRefresh() {
    const localizacaoVazia = itens.length === 0;

    const resultado = await encerrarLocalizacao(localizacaoVazia);

    if (resultado.ok) {
      await atualizarLocalizacoesEscopo();
    }

    return resultado;
  }

  return (
    <div className="mx-auto w-full max-w-6xl space-y-4 p-3 sm:p-5 lg:p-6">
      <section className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
        <div className="flex flex-col gap-3 border-b border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-base font-bold uppercase tracking-wide text-primary sm:text-lg">
                {"Contagem de Invent\u00e1rio"}
              </h1>

              {contexto ? (
                <span
                  className={
                    localizacao
                      ? "inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-emerald-700"
                      : "inline-flex rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-700"
                  }
                >
                  {localizacao
                    ? "Contagem em andamento"
                    : "Aguardando localiza\u00e7\u00e3o"}
                </span>
              ) : null}
            </div>

            <p className="mt-1 text-xs text-muted-foreground sm:text-sm">
              {localizacao
                ? "Registre os itens encontrados na localiza\u00e7\u00e3o atual."
                : "Inicie uma localiza\u00e7\u00e3o para continuar a contagem."}
            </p>
          </div>

          {localizacao ? (
            <Button
              type="button"
              variant="outline"
              disabled={salvando || cancelando}
              onClick={() =>
                setDialogAberto(true)
              }
              className="h-10 shrink-0 border-gold px-3 text-xs font-bold uppercase tracking-wide text-gold hover:bg-gold-light/40 hover:text-gold sm:px-4"
            >
              {"Encerrar localiza\u00e7\u00e3o"}
            </Button>
          ) : null}
        </div>

        {contexto ? (
          <div className="grid grid-cols-2 border-border sm:grid-cols-4">
            <div className="border-b border-r border-border px-4 py-3 sm:border-b-0">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                {"Invent\u00e1rio"}
              </p>

              <p
                className="mt-1 truncate font-mono text-sm font-bold text-foreground"
                title={contexto.codigoInventario}
              >
                {contexto.codigoInventario}
              </p>
            </div>

            <div className="border-b border-border px-4 py-3 sm:border-b-0 sm:border-r">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                Tipo
              </p>

              <p className="mt-1 text-sm font-semibold">
                {contexto.tipoInventario}
              </p>
            </div>

            <div className="border-r border-border px-4 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                Rodada
              </p>

              <p className="mt-1 text-sm font-semibold">
                R{contexto.numeroRodada}
              </p>
            </div>

            <div className="px-4 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                Status
              </p>

              <p className="mt-1 text-sm font-semibold">
                {contexto.statusRodada}
              </p>
            </div>
          </div>
        ) : null}
      </section>

      {carregandoContexto ? (
        <div className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground shadow-xs">
          Carregando contexto do inventário...
        </div>
      ) : erroContexto ? (
        <div className="rounded-lg border border-border bg-card p-4 shadow-xs sm:max-w-md">
          <p className="text-sm text-destructive">{erroContexto}</p>

          <Button
            type="button"
            variant="outline"
            className="mt-3"
            onClick={() => setTentativaCarregamento((valor) => valor + 1)}
          >
            Tentar novamente
          </Button>
        </div>
      ) : !configuracaoOperacional ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          Configuração operacional não disponível para esta contagem.
        </div>
      ) : !localizacao ? (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
          <div className="space-y-3">
<div className="rounded-lg border border-border bg-card p-4 shadow-xs">
              <LocalizacaoForm
                configuracao={configuracaoOperacional.localizacao}
                onIniciar={iniciarLocalizacaoValidada}
              />
            </div>

            <div className="rounded-lg border border-border bg-card p-4 shadow-xs">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-xs font-bold uppercase tracking-wide text-foreground">
                    Progresso da rodada
                  </h2>

                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {"Localiza\u00e7\u00f5es conclu\u00eddas do escopo atual."}
                  </p>
                </div>

                <span className="shrink-0 font-mono text-lg font-bold text-primary">
                  {percentualLocalizacoes}%
                </span>
              </div>

              <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary transition-[width] duration-300"
                  style={{
                    width: `${percentualLocalizacoes}%`,
                  }}
                />
              </div>

              <div className="mt-4 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4 lg:grid-cols-2">
                <div className="rounded-md border border-border bg-muted/20 px-3 py-2.5">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                    Total
                  </p>

                  <p className="mt-0.5 font-mono text-lg font-bold">
                    {resumoLocalizacoes.total}
                  </p>
                </div>

                <div className="rounded-md border border-border bg-muted/20 px-3 py-2.5">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                    Pendentes
                  </p>

                  <p className="mt-0.5 font-mono text-lg font-bold">
                    {resumoLocalizacoes.pendentes}
                  </p>
                </div>

                <div className="rounded-md border border-border bg-muted/20 px-3 py-2.5">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                    Em contagem
                  </p>

                  <p className="mt-0.5 font-mono text-lg font-bold">
                    {resumoLocalizacoes.emContagem}
                  </p>
                </div>

                <div className="rounded-md border border-border bg-muted/20 px-3 py-2.5">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {"Conclu\u00eddas"}
                  </p>

                  <p className="mt-0.5 font-mono text-lg font-bold">
                    {resumoLocalizacoes.concluidas}
                  </p>
                </div>
              </div>
            </div>

          </div>

          <div className="rounded-lg border border-border bg-card p-4 shadow-xs">
            <div className="mb-3">
              <h2 className="text-sm font-bold uppercase tracking-wide">
                Localizações da rodada
              </h2>
            </div>

            {localizacoesEscopo.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Nenhuma localização disponível para esta rodada.
              </p>
            ) : (
              <div className="max-h-[420px] space-y-2 overflow-y-auto pr-1">
                {localizacoesEscopo.map((item) => (
                  <div
                    key={`${item.localizacao}-${item.id_sessao ?? "sem-sessao"}`}
                    className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-mono text-sm font-semibold">
                        {item.localizacao}
                      </p>
                    </div>

                    <span className="shrink-0 text-xs font-semibold uppercase tracking-wide">
                      {rotuloStatus(item.status)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : (
        <>
          <LocalizacaoBanner codigo={localizacao.codigo} />
          <div className="rounded-lg border border-border bg-card p-4 shadow-xs">
            <ItemForm
              salvando={salvando || cancelando}
              configuracao={configuracaoOperacional}
              onValidarCodigo={validarCodigo}
              onSalvar={salvarItem}
            />
          </div>
          <ItensContadosList
            itens={itens}
            resumo={resumo}
            bloqueado={salvando || cancelando}
            onCancelar={cancelarItem}
          />
          <EncerrarDialog
            aberto={dialogAberto}
            localizacao={localizacao.codigo}
            onOpenChange={setDialogAberto}
            onConfirmar={() => {
              setDialogAberto(false);
              void encerrarLocalizacaoComRefresh();
            }}
          />
        </>
      )}
    </div>
  );
}
