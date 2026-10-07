import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import {
  ArrowLeft,
  History,
  Loader2,
  Save,
  Settings2,
} from "lucide-react";
import { toast } from "sonner";

import { obterUsuarioSalvo } from "@/services/authService";

import {
  atualizarConfiguracaoAplicadaInventario,
  consultarConfiguracaoPorInventario,
  consultarHistoricoConfiguracaoInventario,
  consultarInventarioDetalhe,
} from "@/services/inventarioService";

import type {
  AtualizarConfiguracaoInventarioAplicadaEntrada,
  ConfiguracaoInventarioAplicada,
  HistoricoConfiguracaoInventarioResposta,
  InventarioDetalhe,
  TipoRodadaConfigurada,
} from "@/types/inventory";

export const Route = createFileRoute(
  "/inventarios/$idInventario_/configuracao",
)({
  head: () => ({
    meta: [
      {
        title: "Configura\u00e7\u00e3o Aplicada ao Invent\u00e1rio \u2014 SGI",
      },
    ],
  }),
  component: ConfiguracaoInventarioPage,
});

type ChaveBooleana = {
  [K in keyof AtualizarConfiguracaoInventarioAplicadaEntrada]:
    AtualizarConfiguracaoInventarioAplicadaEntrada[K] extends boolean
      ? K
      : never;
}[keyof AtualizarConfiguracaoInventarioAplicadaEntrada];

interface RegraBooleana {
  campo: ChaveBooleana;
  titulo: string;
  descricao: string;
}

interface GrupoRegras {
  titulo: string;
  descricao: string;
  regras: RegraBooleana[];
}

const grupos: GrupoRegras[] = [
  {
    titulo: "Localiza\u00e7\u00e3o",
    descricao: "Controle da abertura e valida\u00e7\u00e3o dos endere\u00e7os.",
    regras: [
      {
        campo: "localizacao_obrigatoria",
        titulo: "Localiza\u00e7\u00e3o obrigat\u00f3ria",
        descricao: "Exige informar uma localiza\u00e7\u00e3o antes da contagem.",
      },
      {
        campo: "localizacao_validar_estoque",
        titulo: "Validar localiza\u00e7\u00e3o no estoque",
        descricao: "Confere a exist\u00eancia do endere\u00e7o na base de estoque.",
      },
      {
        campo: "validar_localizacao_escopo",
        titulo: "Validar localiza\u00e7\u00e3o no escopo",
        descricao: "Impede contar um endere\u00e7o fora do escopo.",
      },
      {
        campo: "permitir_localizacao_vazia",
        titulo: "Permitir localiza\u00e7\u00e3o vazia",
        descricao: "Permite registrar uma localiza\u00e7\u00e3o sem itens previstos.",
      },
      {
        campo: "permitir_reabertura_localizacao",
        titulo: "Permitir reabertura",
        descricao: "Permite reabrir uma localiza\u00e7\u00e3o encerrada.",
      },
      {
        campo: "permitir_alteracao_escopo_apos_snapshot",
        titulo: "Alterar escopo ap\u00f3s snapshot",
        descricao: "Permite ajustar o escopo conforme as regras do processo.",
      },
    ],
  },
  {
    titulo: "C\u00f3digo do item",
    descricao: "Controle da leitura e valida\u00e7\u00e3o dos produtos.",
    regras: [
      {
        campo: "codigo_obrigatorio",
        titulo: "C\u00f3digo obrigat\u00f3rio",
        descricao: "Exige informar o c\u00f3digo do item.",
      },
      {
        campo: "codigo_validar_estoque",
        titulo: "Validar c\u00f3digo no estoque",
        descricao: "Valida o produto na tela antes de avan\u00e7ar.",
      },
      {
        campo: "codigo_livre",
        titulo: "C\u00f3digo livre",
        descricao: "Permite digitar o c\u00f3digo manualmente.",
      },
      {
        campo: "permitir_codigo_nao_cadastrado",
        titulo: "Permitir c\u00f3digo n\u00e3o cadastrado",
        descricao: "Aceita produto ausente da base de estoque.",
      },
      {
        campo: "permitir_item_fora_localizacao",
        titulo: "Permitir item fora da localiza\u00e7\u00e3o",
        descricao: "Aceita o item em um endere\u00e7o diferente do previsto.",
      },
    ],
  },
  {
    titulo: "Lote",
    descricao: "Regras para produtos controlados por lote.",
    regras: [
      {
        campo: "lote_obrigatorio_quando_existir",
        titulo: "Lote obrigat\u00f3rio na tela",
        descricao: "Exige lote quando o produto possui controle de lote.",
      },
      {
        campo: "lote_validar_codigo",
        titulo: "Validar lote na tela",
        descricao: "Confere o lote durante o fluxo operacional.",
      },
      {
        campo: "lote_obrigatorio_se_existir",
        titulo: "Lote obrigat\u00f3rio no registro",
        descricao: "Impede salvar sem lote quando houver controle.",
      },
      {
        campo: "validar_lote_codigo",
        titulo: "Validar lote x c\u00f3digo",
        descricao: "Confere se o lote pertence ao item.",
      },
      {
        campo: "validar_lote_localizacao",
        titulo: "Validar lote x localiza\u00e7\u00e3o",
        descricao: "Confere se o lote est\u00e1 previsto no endere\u00e7o.",
      },
    ],
  },
  {
    titulo: "Contagem e concilia\u00e7\u00e3o",
    descricao: "Comportamento da contagem e compara\u00e7\u00e3o final.",
    regras: [
      {
        campo: "quantidade_obrigatoria",
        titulo: "Quantidade obrigat\u00f3ria",
        descricao: "Exige quantidade para registrar o item.",
      },
      {
        campo: "contagem_cega",
        titulo: "Contagem cega",
        descricao: "Oculta a quantidade esperada do operador.",
      },
      {
        campo: "considera_localizacao_conciliacao",
        titulo: "Considerar localiza\u00e7\u00e3o",
        descricao: "Inclui o endere\u00e7o na chave da concilia\u00e7\u00e3o.",
      },
      {
        campo: "recontagem_por_localizacao",
        titulo: "Recontagem por localiza\u00e7\u00e3o",
        descricao: "Organiza a recontagem pelos endere\u00e7os divergentes.",
      },
      {
        campo: "permitir_gestor_antecipado",
        titulo: "Permitir gestor antecipado",
        descricao: "Permite encaminhar diverg\u00eancias antes do limite.",
      },
      {
        campo: "divergencia_bloqueia_finalizacao",
        titulo: "Diverg\u00eancia bloqueia finaliza\u00e7\u00e3o",
        descricao: "Impede finalizar com diverg\u00eancias pendentes.",
      },
    ],
  },
];

function montarFormulario(
  configuracao: ConfiguracaoInventarioAplicada,
): AtualizarConfiguracaoInventarioAplicadaEntrada {
  return {
    validar_localizacao_escopo:
      configuracao.validar_localizacao_escopo,
    permitir_localizacao_vazia:
      configuracao.permitir_localizacao_vazia,
    permitir_reabertura_localizacao:
      configuracao.permitir_reabertura_localizacao,
    permitir_alteracao_escopo_apos_snapshot:
      configuracao.permitir_alteracao_escopo_apos_snapshot,

    codigo_livre: configuracao.codigo_livre,
    permitir_codigo_nao_cadastrado:
      configuracao.permitir_codigo_nao_cadastrado,
    permitir_item_fora_localizacao:
      configuracao.permitir_item_fora_localizacao,

    lote_obrigatorio_se_existir:
      configuracao.lote_obrigatorio_se_existir,
    validar_lote_codigo:
      configuracao.validar_lote_codigo,
    validar_lote_localizacao:
      configuracao.validar_lote_localizacao,

    quantidade_minima: configuracao.quantidade_minima,
    quantidade_maxima: configuracao.quantidade_maxima,

    contagem_cega: configuracao.contagem_cega,
    considera_localizacao_conciliacao:
      configuracao.considera_localizacao_conciliacao,

    recontagem_por_localizacao:
      configuracao.recontagem_por_localizacao,
    rodadas_iniciais: configuracao.rodadas_iniciais,
    max_rodadas: configuracao.max_rodadas,

    permitir_gestor_antecipado:
      configuracao.permitir_gestor_antecipado,
    limite_itens_gestor_antecipado:
      configuracao.limite_itens_gestor_antecipado,

    divergencia_bloqueia_finalizacao:
      configuracao.divergencia_bloqueia_finalizacao,

    ativa: true,

    localizacao_obrigatoria:
      configuracao.localizacao_obrigatoria,
    localizacao_validar_estoque:
      configuracao.localizacao_validar_estoque,

    codigo_obrigatorio:
      configuracao.codigo_obrigatorio,
    codigo_validar_estoque:
      configuracao.codigo_validar_estoque,

    lote_obrigatorio_quando_existir:
      configuracao.lote_obrigatorio_quando_existir,
    lote_validar_codigo:
      configuracao.lote_validar_codigo,

    quantidade_obrigatoria:
      configuracao.quantidade_obrigatoria,
    quantidade_operacional_minima:
      configuracao.quantidade_operacional_minima,
    quantidade_operacional_maxima:
      configuracao.quantidade_operacional_maxima,

    versao_esperada: configuracao.versao,
    motivo: "",

    rodadas: configuracao.rodadas.map((rodada) => ({
      numero_rodada: rodada.numero_rodada,
      tipo_rodada: rodada.tipo_rodada,
    })),
  };
}

function ConfiguracaoInventarioPage() {
  const { idInventario } = Route.useParams();
  const id = Number(idInventario);

  const usuarioAtual = obterUsuarioSalvo();

  const permissoesUsuario = new Set(
    (usuarioAtual?.permissoes ?? [])
      .map((permissao) =>
        typeof permissao === "string"
          ? permissao
          : permissao.codigo,
      )
      .filter(Boolean),
  );

  const podeVisualizar =
    permissoesUsuario.has("ANALISE_VISUALIZAR") ||
    permissoesUsuario.has("CONFIGURACAO_VISUALIZAR") ||
    permissoesUsuario.has("CONFIGURACAO_EDITAR");

  const podeEditarPermissao =
    permissoesUsuario.has("CONFIGURACAO_EDITAR");

  const [inventario, setInventario] =
    useState<InventarioDetalhe | null>(null);

  const [configuracao, setConfiguracao] =
    useState<ConfiguracaoInventarioAplicada | null>(null);

  const [form, setForm] =
    useState<AtualizarConfiguracaoInventarioAplicadaEntrada | null>(null);

  const [historico, setHistorico] =
    useState<HistoricoConfiguracaoInventarioResposta | null>(null);

  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function carregar() {
    if (!podeVisualizar) {
      setErro(
        "Você não possui permissão para consultar a configuração deste inventário.",
      );
      setCarregando(false);
      return;
    }

    if (!Number.isInteger(id) || id <= 0) {
      setErro("Invent\u00e1rio inv\u00e1lido.");
      setCarregando(false);
      return;
    }

    setCarregando(true);
    setErro(null);

    try {
      const [inventarioAtual, configuracaoAtual, historicoAtual] =
        await Promise.all([
          consultarInventarioDetalhe(id),
          consultarConfiguracaoPorInventario(id),
          consultarHistoricoConfiguracaoInventario(id),
        ]);

      setInventario(inventarioAtual);
      setConfiguracao(configuracaoAtual);
      setForm(montarFormulario(configuracaoAtual));
      setHistorico(historicoAtual);
    } catch (falha: unknown) {
      setErro(
        falha instanceof Error
          ? falha.message
          : "N\u00e3o foi poss\u00edvel carregar as regras.",
      );
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    void carregar();
  }, [id, podeVisualizar]);

  function alterarBooleano(
    campo: ChaveBooleana,
    valor: boolean,
  ) {
    setForm((atual) =>
      atual
        ? {
            ...atual,
            [campo]: valor,
          }
        : atual,
    );
  }

  function ajustarMaxRodadas(valor: number) {
    if (!form || !inventario) return;

    const maximo = Math.max(
      inventario.rodada_atual,
      Math.trunc(valor || 1),
    );

    const rodadas = Array.from(
      { length: maximo },
      (_, indice) => {
        const numero = indice + 1;
        const existente = form.rodadas.find(
          (rodada) => rodada.numero_rodada === numero,
        );

        return (
          existente ?? {
            numero_rodada: numero,
            tipo_rodada: (
              numero === 1
                ? "COMPLETA"
                : "DIVERGENCIAS"
            ) as TipoRodadaConfigurada,
          }
        );
      },
    );

    setForm({
      ...form,
      max_rodadas: maximo,
      rodadas_iniciais: Math.min(
        form.rodadas_iniciais,
        maximo,
      ),
      rodadas,
    });
  }

  async function salvar() {
    if (!form || !configuracao || !inventario) return;

    const statusInventario = String(
      inventario.status ?? "",
    ).toUpperCase();

    if (
      !podeEditarPermissao ||
      ["FINALIZADO", "CANCELADO"].includes(
        statusInventario,
      )
    ) {
      toast.error(
        "A configuração deste inventário está disponível somente para consulta.",
      );
      return;
    }

    const motivo = form.motivo.trim();

    if (motivo.length < 5) {
      toast.error(
        "Informe um motivo com pelo menos 5 caracteres.",
      );
      return;
    }

    setSalvando(true);

    try {
      const resposta =
        await atualizarConfiguracaoAplicadaInventario(
          id,
          {
            ...form,
            motivo,
            versao_esperada: configuracao.versao,
          },
        );

      setConfiguracao(resposta.configuracao);
      setForm(montarFormulario(resposta.configuracao));

      const historicoAtual =
        await consultarHistoricoConfiguracaoInventario(id);

      setHistorico(historicoAtual);
      toast.success(resposta.mensagem);
    } catch (falha: unknown) {
      toast.error(
        falha instanceof Error
          ? falha.message
          : "N\u00e3o foi poss\u00edvel salvar as regras.",
      );
    } finally {
      setSalvando(false);
    }
  }

  if (carregando) {
    return (
      <main className="flex min-h-[50vh] items-center justify-center">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="size-5 animate-spin" />
          {"Carregando regras do invent\u00e1rio..."}
        </div>
      </main>
    );
  }

  if (erro || !inventario || !configuracao || !form) {
    return (
      <main className="space-y-5 p-4 sm:p-6">
        <Link
          to="/inventarios/$idInventario"
          params={{ idInventario }}
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          {"Voltar ao invent\u00e1rio"}
        </Link>

        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {erro ?? "Configura\u00e7\u00e3o n\u00e3o encontrada."}
        </div>
      </main>
    );
  }

  const statusInventario = String(
    inventario.status ?? "",
  ).toUpperCase();

  const inventarioEncerrado = [
    "FINALIZADO",
    "CANCELADO",
  ].includes(statusInventario);

  const somenteLeitura =
    inventarioEncerrado ||
    !podeEditarPermissao;

  return (
    <main className="space-y-6 p-4 sm:p-6">
      <Link
        to="/inventarios/$idInventario"
        params={{ idInventario }}
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        {"Voltar ao invent\u00e1rio"}
      </Link>

      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <Settings2 className="mt-0.5 size-7 text-primary" />

          <div>
            <h1 className="text-xl font-bold text-primary">
              {"Configura\u00e7\u00e3o aplicada ao invent\u00e1rio"}
            </h1>

            <p className="mt-1 text-sm text-muted-foreground">
              {inventario.codigo_inventario}
              {" \u00b7 "}
              {inventario.cliente}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <span className="rounded-full border bg-muted/30 px-3 py-1 text-xs font-semibold">
            {"Vers\u00e3o "}
            {configuracao.versao}
          </span>

          <span className="rounded-full border border-primary/30 bg-primary/5 px-3 py-1 text-xs font-semibold text-primary">
            {"C\u00f3pia exclusiva"}
          </span>

          <span
            className={
              somenteLeitura
                ? "rounded-full border border-slate-300 bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700"
                : "rounded-full border border-emerald-300 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700"
            }
          >
            {somenteLeitura
              ? "Somente leitura"
              : "Edição permitida"}
          </span>
        </div>
      </header>

      <div
        className={
          somenteLeitura
            ? "rounded-lg border border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-200"
            : "rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800 dark:border-blue-900 dark:bg-blue-950/30 dark:text-blue-200"
        }
      >
        {inventarioEncerrado
          ? "Este inventário está encerrado. A configuração aplicada e seu histórico permanecem disponíveis somente para consulta."
          : somenteLeitura
            ? "Você possui permissão para consultar esta configuração, mas não para alterá-la."
            : "As alterações desta tela afetam somente este inventário. A configuração padrão do cliente não será modificada."}
      </div>

      {grupos.map((grupo) => (
        <section
          key={grupo.titulo}
          className="rounded-lg border bg-card p-5 shadow-xs"
        >
          <h2 className="font-semibold">{grupo.titulo}</h2>

          <p className="mt-1 text-sm text-muted-foreground">
            {grupo.descricao}
          </p>

          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {grupo.regras.map((regra) => (
              <label
                key={regra.campo}
                className={`flex items-start gap-3 rounded-lg border bg-background p-4 transition ${
                  somenteLeitura
                    ? "cursor-default opacity-80"
                    : "cursor-pointer hover:border-primary/50"
                }`}
              >
                <input
                  type="checkbox"
                  checked={Boolean(form[regra.campo])}
                  onChange={(event) =>
                    alterarBooleano(
                      regra.campo,
                      event.target.checked,
                    )
                  }
                  disabled={somenteLeitura || salvando}
                  className="mt-1 size-4 accent-primary"
                />

                <span>
                  <span className="block text-sm font-semibold">
                    {regra.titulo}
                  </span>

                  <span className="mt-1 block text-xs text-muted-foreground">
                    {regra.descricao}
                  </span>
                </span>
              </label>
            ))}
          </div>
        </section>
      ))}

      <section className="rounded-lg border bg-card p-5 shadow-xs">
        <h2 className="font-semibold">
          {"Limites e encaminhamento"}
        </h2>

        <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <CampoNumero
            titulo={"Quantidade m\u00ednima"}
            valor={form.quantidade_minima}
            disabled={somenteLeitura || salvando}
            onChange={(valor) =>
              setForm({
                ...form,
                quantidade_minima: valor,
              })
            }
          />

          <CampoNumero
            titulo={"Quantidade m\u00e1xima"}
            valor={form.quantidade_maxima}
            disabled={somenteLeitura || salvando}
            onChange={(valor) =>
              setForm({
                ...form,
                quantidade_maxima: valor,
              })
            }
          />

          <CampoNumero
            titulo={"M\u00ednimo operacional"}
            valor={form.quantidade_operacional_minima}
            disabled={somenteLeitura || salvando}
            onChange={(valor) =>
              setForm({
                ...form,
                quantidade_operacional_minima: valor,
              })
            }
          />

          <CampoNumero
            titulo={"M\u00e1ximo operacional"}
            valor={form.quantidade_operacional_maxima}
            disabled={somenteLeitura || salvando}
            onChange={(valor) =>
              setForm({
                ...form,
                quantidade_operacional_maxima: valor,
              })
            }
          />

          <CampoNumero
            titulo={"Limite para gestor"}
            valor={form.limite_itens_gestor_antecipado}
            disabled={somenteLeitura || salvando}
            onChange={(valor) =>
              setForm({
                ...form,
                limite_itens_gestor_antecipado: valor,
              })
            }
          />
        </div>
      </section>

      <section className="rounded-lg border bg-card p-5 shadow-xs">
        <h2 className="font-semibold">Rodadas</h2>

        <p className="mt-1 text-sm text-muted-foreground">
          {
            "Rodadas alcan\u00e7adas ficam protegidas. Somente rodadas futuras podem ter o tipo alterado."
          }
        </p>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <CampoNumero
            titulo={"Rodadas iniciais"}
            valor={form.rodadas_iniciais}
            minimo={1}
            disabled={somenteLeitura || salvando}
            onChange={(valor) =>
              setForm({
                ...form,
                rodadas_iniciais: valor,
              })
            }
          />

          <CampoNumero
            titulo={"M\u00e1ximo de rodadas"}
            valor={form.max_rodadas}
            minimo={inventario.rodada_atual}
            disabled={somenteLeitura || salvando}
            onChange={ajustarMaxRodadas}
          />
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {form.rodadas.map((rodada) => {
            const protegida =
              rodada.numero_rodada <= inventario.rodada_atual;

            return (
              <div
                key={rodada.numero_rodada}
                className="rounded-lg border bg-background p-4"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold">
                    Rodada {rodada.numero_rodada}
                  </span>

                  {protegida && (
                    <span className="rounded-full bg-muted px-2 py-1 text-[11px] font-medium text-muted-foreground">
                      Protegida
                    </span>
                  )}
                </div>

                <select
                  value={rodada.tipo_rodada}
                  disabled={
                    somenteLeitura ||
                    protegida ||
                    salvando
                  }
                  onChange={(event) => {
                    const tipo =
                      event.target.value as TipoRodadaConfigurada;

                    setForm({
                      ...form,
                      rodadas: form.rodadas.map((item) =>
                        item.numero_rodada === rodada.numero_rodada
                          ? {
                              ...item,
                              tipo_rodada: tipo,
                            }
                          : item,
                      ),
                    });
                  }}
                  className="mt-3 h-10 w-full rounded-md border bg-background px-3 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <option value="COMPLETA">Completa</option>
                  <option value="DIVERGENCIAS">
                    Diverg\u00eancias
                  </option>
                  <option value="GESTOR">Gestor</option>
                </select>
              </div>
            );
          })}
        </div>
      </section>

      {!somenteLeitura && (
        <section className="rounded-lg border bg-card p-5 shadow-xs">
          <label
            htmlFor="motivo-alteracao"
            className="font-semibold"
          >
            {"Motivo da altera\u00e7\u00e3o"}
          </label>

          <textarea
            id="motivo-alteracao"
            value={form.motivo}
            onChange={(event) =>
              setForm({
                ...form,
                motivo: event.target.value,
              })
            }
            disabled={salvando}
            rows={4}
            placeholder="Explique por que a configuração deste inventário está sendo alterada."
            className="mt-3 w-full resize-none rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
          />

          <div className="mt-4 flex justify-end">
            <button
              type="button"
              onClick={() => void salvar()}
              disabled={
                salvando ||
                form.motivo.trim().length < 5
              }
              className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-primary px-5 text-sm font-semibold text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {salvando ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Save className="size-4" />
              )}

              {salvando
                ? "Salvando..."
                : "Salvar configuração aplicada"}
            </button>
          </div>
        </section>
      )}

      <section className="rounded-lg border bg-card p-5 shadow-xs">
        <div className="flex items-start gap-3">
          <History className="mt-0.5 size-5 text-primary" />

          <div>
            <h2 className="font-semibold">
              {"Hist\u00f3rico das regras"}
            </h2>

            <p className="mt-1 text-sm text-muted-foreground">
              {historico?.total ?? 0}
              {" altera\u00e7\u00e3o(\u00f5es) registrada(s)."}
            </p>
          </div>
        </div>

        <div className="mt-4 space-y-3">
          {historico?.historico.map((item) => (
            <div
              key={item.id_historico_configuracao}
              className="rounded-lg border bg-background px-4 py-3"
            >
              <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                <span className="font-medium">
                  {"Vers\u00e3o "}
                  {item.versao_nova}
                </span>

                <span className="text-xs text-muted-foreground">
                  {formatarData(item.data_hora_alteracao)}
                </span>
              </div>

              <p className="mt-2 text-sm">
                {item.motivo}
              </p>

              <p className="mt-2 text-xs text-muted-foreground">
                {"Alterado por: "}
                {item.alterado_por}
              </p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}

function CampoNumero({
  titulo,
  valor,
  minimo = 0,
  disabled = false,
  onChange,
}: {
  titulo: string;
  valor: number;
  minimo?: number;
  disabled?: boolean;
  onChange: (valor: number) => void;
}) {
  return (
    <label className="space-y-1.5">
      <span className="text-sm font-medium">
        {titulo}
      </span>

      <input
        type="number"
        value={valor}
        min={minimo}
        disabled={disabled}
        onChange={(event) =>
          onChange(Number(event.target.value))
        }
        className="h-11 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
      />
    </label>
  );
}

function formatarData(valor: string | null | undefined) {
  if (!valor) return "-";

  const data = new Date(valor);

  if (Number.isNaN(data.getTime())) {
    return valor;
  }

  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(data);
}
