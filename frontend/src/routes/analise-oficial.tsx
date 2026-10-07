import { createFileRoute, Link } from "@tanstack/react-router";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  BarChart3,
  CheckCircle2,
  Clock3,
  Download,
  Loader2,
  PackageMinus,
  PackagePlus,
  RefreshCcw,
  ScanLine,
  Search,
  Send,
  ShieldCheck,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  obterInventarioAtual,
  salvarInventarioAtual,
} from "@/lib/inventarioAtual";
import { obterUsuarioSalvo } from "@/services/authService";
import { encaminharInventarioGestor } from "@/services/gestorService";
import {
  buscarAnaliseOficial,
  buscarRodadaAtualOficial,
  listarInventariosOficiais,
  type AnaliseOficial,
  type InventarioOficial,
} from "@/services/oficialService";
import {
  buscarPreviewProximaRodada,
  type PreviewProximaRodadaResposta,
} from "@/services/rodadasService";

interface AnaliseOficialSearch {
  inventario?: number;
}

type FiltroStatus =
  | "TODOS"
  | "AGUARDANDO_CONTAGEM"
  | "EM_CONTAGEM"
  | "DIVERG\u00caNCIA"
  | "FALTA"
  | "SOBRA"
  | "OK";

type CampoOrdenacao =
  | "localizacao"
  | "codigo"
  | "lote"
  | "descricao"
  | "qtd_estoque"
  | "qtd_contada"
  | "diferenca"
  | "status";

interface LinhaOficial {
  chave: string;
  localizacao: string;
  codigo: string;
  lote: string;
  descricao: string;
  qtd_estoque: number;
  qtd_contada: number;
  diferenca: number;
  status: string;
  detalhe: string;
  resultado_definitivo: boolean;
}

export const Route = createFileRoute("/analise-oficial")({
  validateSearch: (
    search: Record<string, unknown>,
  ): AnaliseOficialSearch => {
    const inventario = Number(
      search["inventario"],
    );

    return (
      Number.isSafeInteger(inventario) &&
      inventario > 0
    )
      ? { inventario }
      : {};
  },
  head: () => ({
    meta: [
      {
        title:
          "An\u00e1lise Oficial \u2014 SGI",
      },
    ],
  }),
  component: AnaliseOficialPage,
});

function AnaliseOficialPage() {
  const {
    inventario: inventarioUrl,
  } = Route.useSearch();

  const idInventario =
    inventarioUrl ?? obterInventarioAtual();

  const [inventario, setInventario] =
    useState<InventarioOficial | null>(null);

  const [analise, setAnalise] =
    useState<AnaliseOficial | null>(null);

  const [preview, setPreview] =
    useState<PreviewProximaRodadaResposta | null>(
      null,
    );

  const [filtro, setFiltro] =
    useState<FiltroStatus>("TODOS");

  const [buscaLocalizacao, setBuscaLocalizacao] =
    useState("");

  const [buscaCodigo, setBuscaCodigo] =
    useState("");

  const [buscaLote, setBuscaLote] =
    useState("");

  const [
    somenteComDiferenca,
    setSomenteComDiferenca,
  ] = useState(false);

  const [paginaAtual, setPaginaAtual] =
    useState(1);

  const [tamanhoPagina, setTamanhoPagina] =
    useState(25);

  const [campoOrdenacao, setCampoOrdenacao] =
    useState<CampoOrdenacao>("localizacao");

  const [direcaoOrdenacao, setDirecaoOrdenacao] =
    useState<"asc" | "desc">("asc");

  const [carregando, setCarregando] =
    useState(true);

  const [atualizando, setAtualizando] =
    useState(false);

  const [exportando, setExportando] =
    useState(false);

  const [encaminhando, setEncaminhando] =
    useState(false);

  const [
    ultimaAtualizacao,
    setUltimaAtualizacao,
  ] = useState<Date | null>(null);

  const [erro, setErro] =
    useState<string | null>(null);

  const usuario = obterUsuarioSalvo();

  const permissoes = new Set(
    (usuario?.permissoes ?? [])
      .map((permissao) =>
        typeof permissao === "string"
          ? permissao
          : permissao.codigo,
      )
      .filter(Boolean),
  );

  const podeEncaminharPorPerfil =
    permissoes.has("GESTOR_DECIDIR");

  const carregar = useCallback(
    async (silencioso = false) => {
      if (
        !idInventario ||
        !Number.isSafeInteger(idInventario)
      ) {
        setErro(
          "Nenhum invent\u00e1rio oficial foi selecionado.",
        );
        setCarregando(false);
        return;
      }

      if (silencioso) {
        setAtualizando(true);
      } else {
        setCarregando(true);
      }

      setErro(null);

      try {
        const inventarios =
          await listarInventariosOficiais();

        const encontrado = inventarios.find(
          (item) =>
            item.id_inventario === idInventario,
        );

        if (!encontrado) {
          throw new Error(
            `O invent\u00e1rio #${idInventario} n\u00e3o \u00e9 OFICIAL ou n\u00e3o est\u00e1 dispon\u00edvel.`,
          );
        }

        const rodadaAtual =
          await buscarRodadaAtualOficial(
            idInventario,
          );

        const [
          analiseAtual,
          previewAtual,
        ] = await Promise.all([
          buscarAnaliseOficial(
            idInventario,
            rodadaAtual.id_rodada,
          ),
          buscarPreviewProximaRodada(
            idInventario,
          ).catch(() => null),
        ]);

        setInventario(encontrado);
        setAnalise(analiseAtual);
        setPreview(previewAtual);
        setUltimaAtualizacao(new Date());

        salvarInventarioAtual(
          encontrado.id_inventario,
          "OFICIAL",
        );
      } catch (falha: unknown) {
        setErro(mensagemErro(falha));

        if (!silencioso) {
          setInventario(null);
          setAnalise(null);
          setPreview(null);
        }
      } finally {
        setCarregando(false);
        setAtualizando(false);
      }
    },
    [idInventario],
  );

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const linhas = useMemo<LinhaOficial[]>(
    () =>
      (analise?.itens ?? []).map(
        (item) => {
          const status =
            item.status ===
              "AGUARDANDO_CONTAGEM" &&
            item.qtd_contada > 0
              ? "EM_CONTAGEM"
              : item.status;

          return {
            chave: item.chave,
            localizacao:
              item.localizacoes_bipadas
                .map(
                  (local) =>
                    local.localizacao,
                )
                .join(", ") || "-",
            codigo: item.codigo,
            lote: item.lote || "-",
            descricao:
              item.descricao ??
              "Produto sem descri\u00e7\u00e3o",
            qtd_estoque: item.qtd_estoque,
            qtd_contada: item.qtd_contada,
            diferenca: item.diferenca,
            status,
            resultado_definitivo:
              item.resultado_definitivo,
            detalhe:
              item.resultado_definitivo
                ? item.detalhe ?? ""
                : detalhePrevio(
                    item.qtd_contada,
                    item.diferenca,
                  ),
          };
        },
      ),
    [analise],
  );

  const resumoOperacional = useMemo(
    () => ({
      naoIniciados: linhas.filter(
        (item) =>
          item.status ===
          "AGUARDANDO_CONTAGEM",
      ).length,
      emContagem: linhas.filter(
        (item) =>
          item.status === "EM_CONTAGEM",
      ).length,
    }),
    [linhas],
  );

  const linhasFiltradas = useMemo(() => {
    const localizacao =
      normalizarBusca(buscaLocalizacao);

    const codigo =
      normalizarBusca(buscaCodigo);

    const lote =
      normalizarBusca(buscaLote);

    return linhas.filter((item) => {
      if (
        filtro !== "TODOS" &&
        item.status !== filtro
      ) {
        return false;
      }

      if (
        somenteComDiferenca &&
        Math.abs(item.diferenca) < 0.000001
      ) {
        return false;
      }

      if (
        localizacao &&
        !normalizarBusca(
          item.localizacao,
        ).includes(localizacao)
      ) {
        return false;
      }

      if (
        codigo &&
        !normalizarBusca(
          item.codigo,
        ).includes(codigo)
      ) {
        return false;
      }

      if (
        lote &&
        !normalizarBusca(
          item.lote,
        ).includes(lote)
      ) {
        return false;
      }

      return true;
    });
  }, [
    linhas,
    filtro,
    somenteComDiferenca,
    buscaLocalizacao,
    buscaCodigo,
    buscaLote,
  ]);

  const linhasOrdenadas = useMemo(() => {
    const resultado = [
      ...linhasFiltradas,
    ];

    resultado.sort((itemA, itemB) => {
      const valorA =
        itemA[campoOrdenacao];

      const valorB =
        itemB[campoOrdenacao];

      let comparacao = 0;

      if (
        typeof valorA === "number" &&
        typeof valorB === "number"
      ) {
        comparacao = valorA - valorB;
      } else {
        comparacao = String(
          valorA,
        ).localeCompare(
          String(valorB),
          "pt-BR",
          {
            numeric: true,
            sensitivity: "base",
          },
        );
      }

      return direcaoOrdenacao === "asc"
        ? comparacao
        : -comparacao;
    });

    return resultado;
  }, [
    linhasFiltradas,
    campoOrdenacao,
    direcaoOrdenacao,
  ]);

  useEffect(() => {
    setPaginaAtual(1);
  }, [
    filtro,
    buscaLocalizacao,
    buscaCodigo,
    buscaLote,
    somenteComDiferenca,
    tamanhoPagina,
    idInventario,
  ]);

  const totalPaginas = Math.max(
    1,
    Math.ceil(
      linhasOrdenadas.length /
        tamanhoPagina,
    ),
  );

  const paginaSegura = Math.min(
    paginaAtual,
    totalPaginas,
  );

  const indiceInicial =
    (paginaSegura - 1) *
    tamanhoPagina;

  const linhasPaginadas =
    linhasOrdenadas.slice(
      indiceInicial,
      indiceInicial + tamanhoPagina,
    );

  const primeiroRegistro =
    linhasOrdenadas.length === 0
      ? 0
      : indiceInicial + 1;

  const ultimoRegistro = Math.min(
    indiceInicial + tamanhoPagina,
    linhasOrdenadas.length,
  );

  const resumo = {
    total:
      analise?.resumo.total_registros ?? 0,
    ok:
      analise?.resumo.ok ?? 0,
    divergencias:
      analise?.resumo.divergencias ?? 0,
    faltas:
      analise?.resumo.faltas ?? 0,
    sobras:
      analise?.resumo.sobras ?? 0,
  };

  const elegivel = Boolean(
    preview?.preview.pode_encaminhar_gestor,
  );

  const encerrado = [
    "FINALIZADO",
    "CANCELADO",
  ].includes(inventario?.status ?? "");

  function selecionarFiltro(
    novoFiltro: FiltroStatus,
  ) {
    setFiltro(novoFiltro);
    setPaginaAtual(1);
  }

  function alternarOrdenacao(
    campo: CampoOrdenacao,
  ) {
    if (campoOrdenacao === campo) {
      setDirecaoOrdenacao(
        (atual) =>
          atual === "asc"
            ? "desc"
            : "asc",
      );
    } else {
      setCampoOrdenacao(campo);
      setDirecaoOrdenacao("asc");
    }

    setPaginaAtual(1);
  }

  function iconeOrdenacao(
    campo: CampoOrdenacao,
  ) {
    if (campoOrdenacao !== campo) {
      return (
        <ArrowUpDown className="size-3.5 opacity-40" />
      );
    }

    return direcaoOrdenacao === "asc" ? (
      <ArrowUp className="size-3.5" />
    ) : (
      <ArrowDown className="size-3.5" />
    );
  }

  function limparFiltros() {
    setFiltro("TODOS");
    setBuscaLocalizacao("");
    setBuscaCodigo("");
    setBuscaLote("");
    setSomenteComDiferenca(false);
    setPaginaAtual(1);
  }

  async function encaminhar() {
    if (
      !inventario ||
      inventario.em_analise_gestor ||
      encaminhando
    ) {
      return;
    }

    if (
      !preview?.preview
        .pode_encaminhar_gestor
    ) {
      toast.error(
        preview?.preview.motivo ??
          "O invent\u00e1rio ainda n\u00e3o pode ser encaminhado ao gestor.",
      );
      return;
    }

    if (!podeEncaminharPorPerfil) {
      toast.error(
        "Seu usu\u00e1rio n\u00e3o possui a permiss\u00e3o GESTOR_DECIDIR.",
      );
      return;
    }

    if (!usuario?.login) {
      toast.error(
        "N\u00e3o foi poss\u00edvel identificar o usu\u00e1rio autenticado.",
      );
      return;
    }

    const confirmou = window.confirm(
      `Encaminhar o invent\u00e1rio ${inventario.codigo_inventario} para an\u00e1lise gerencial?`,
    );

    if (!confirmou) return;

    setEncaminhando(true);

    try {
      const resposta =
        await encaminharInventarioGestor(
          inventario.id_inventario,
          usuario.login,
        );

      toast.success(
        resposta.mensagem ||
          "Invent\u00e1rio encaminhado ao gestor.",
      );

      await carregar(true);
    } catch (falha: unknown) {
      toast.error(
        mensagemErro(falha),
      );
    } finally {
      setEncaminhando(false);
    }
  }

  async function exportarExcel() {
    if (
      !inventario ||
      !analise ||
      linhasOrdenadas.length === 0
    ) {
      return;
    }

    setExportando(true);
    setErro(null);

    try {
      const [
        { default: ExcelJS },
        { saveAs },
      ] = await Promise.all([
        import("exceljs"),
        import("file-saver"),
      ]);

      const workbook =
        new ExcelJS.Workbook();

      workbook.creator = "SGI";
      workbook.company =
        "Alzarsi Log\u00edstica";
      workbook.created = new Date();

      const resumoExcel =
        workbook.addWorksheet("Resumo");

      resumoExcel.columns = [
        {
          header: "Campo",
          key: "campo",
          width: 30,
        },
        {
          header: "Valor",
          key: "valor",
          width: 55,
        },
      ];

      resumoExcel.addRows([
        {
          campo: "Invent\u00e1rio",
          valor:
            inventario.codigo_inventario,
        },
        {
          campo: "Cliente",
          valor: inventario.cliente,
        },
        {
          campo: "Armaz\u00e9m",
          valor: inventario.armazem,
        },
        {
          campo: "Rodada",
          valor: analise.numero_rodada,
        },
        {
          campo: "Filtro de status",
          valor:
            filtro === "TODOS"
              ? "Todos"
              : nomeStatus(filtro),
        },
        {
          campo:
            "Filtro de localiza\u00e7\u00e3o",
          valor:
            buscaLocalizacao.trim() || "-",
        },
        {
          campo: "Filtro de c\u00f3digo",
          valor:
            buscaCodigo.trim() || "-",
        },
        {
          campo: "Filtro de lote",
          valor:
            buscaLote.trim() || "-",
        },
        {
          campo:
            "Somente com diferen\u00e7a",
          valor:
            somenteComDiferenca
              ? "Sim"
              : "N\u00e3o",
        },
        {
          campo: "Registros exportados",
          valor: linhasOrdenadas.length,
        },
        {
          campo: "Gerado em",
          valor:
            new Date().toLocaleString(
              "pt-BR",
            ),
        },
      ]);

      const itensExcel =
        workbook.addWorksheet("Itens", {
          views: [
            {
              state: "frozen",
              ySplit: 1,
            },
          ],
        });

      itensExcel.columns = [
        {
          header: "Localiza\u00e7\u00e3o",
          key: "localizacao",
          width: 24,
        },
        {
          header: "C\u00f3digo",
          key: "codigo",
          width: 20,
        },
        {
          header: "Lote",
          key: "lote",
          width: 20,
        },
        {
          header: "Produto",
          key: "produto",
          width: 55,
        },
        {
          header: "Estoque",
          key: "estoque",
          width: 15,
        },
        {
          header: "Contado",
          key: "contado",
          width: 15,
        },
        {
          header: "Diferen\u00e7a",
          key: "diferenca",
          width: 15,
        },
        {
          header: "Status",
          key: "status",
          width: 22,
        },
        {
          header: "Detalhe",
          key: "detalhe",
          width: 45,
        },
      ];

      itensExcel.addRows(
        linhasOrdenadas.map(
          (item) => ({
            localizacao:
              item.localizacao,
            codigo: item.codigo,
            lote: item.lote,
            produto: item.descricao,
            estoque: item.qtd_estoque,
            contado: item.qtd_contada,
            diferenca: item.diferenca,
            status:
              nomeStatus(item.status),
            detalhe:
              item.resultado_definitivo
                ? item.detalhe || "-"
                : `${item.detalhe} \u2022 Pr\u00e9via`,
          }),
        ),
      );

      for (const aba of [
        resumoExcel,
        itensExcel,
      ]) {
        const cabecalho =
          aba.getRow(1);

        cabecalho.font = {
          bold: true,
          color: {
            argb: "FFFFFFFF",
          },
        };

        cabecalho.fill = {
          type: "pattern",
          pattern: "solid",
          fgColor: {
            argb: "FF1E3A5F",
          },
        };
      }

      itensExcel.autoFilter = {
        from: "A1",
        to: `I${Math.max(
          1,
          itensExcel.rowCount,
        )}`,
      };

      for (const coluna of [
        "estoque",
        "contado",
        "diferenca",
      ]) {
        itensExcel.getColumn(
          coluna,
        ).numFmt =
          '#,##0.00;[Red]-#,##0.00';
      }

      const buffer =
        await workbook.xlsx.writeBuffer();

      const blob = new Blob(
        [buffer as BlobPart],
        {
          type:
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        },
      );

      const dataArquivo = new Date()
        .toISOString()
        .slice(0, 19)
        .replace(/[:T]/g, "-");

      const codigoArquivo =
        inventario.codigo_inventario
          .replace(
            /[^a-zA-Z0-9_-]/g,
            "_",
          );

      saveAs(
        blob,
        `Analise_Oficial_${codigoArquivo}_R${analise.numero_rodada}_${dataArquivo}.xlsx`,
      );
    } catch (falha: unknown) {
      setErro(
        falha instanceof Error
          ? `Falha ao gerar o Excel: ${falha.message}`
          : "Falha ao gerar o arquivo Excel.",
      );
    } finally {
      setExportando(false);
    }
  }

  const possuiFiltros =
    filtro !== "TODOS" ||
    Boolean(buscaLocalizacao.trim()) ||
    Boolean(buscaCodigo.trim()) ||
    Boolean(buscaLote.trim()) ||
    somenteComDiferenca;

  return (
    <main className="space-y-6 p-4 md:p-6">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <BarChart3
              className="size-6"
              aria-hidden="true"
            />

            <h1 className="text-2xl font-bold">
              {"An\u00e1lise Oficial"}
            </h1>
          </div>

          <p className="mt-1 text-sm text-muted-foreground">
            {
              "Acompanhe o que j\u00e1 foi contado, o que ainda est\u00e1 pendente e as diverg\u00eancias encontradas no invent\u00e1rio."
            }
          </p>
        </div>

        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          {ultimaAtualizacao ? (
            <span
              className="mr-1 text-xs text-muted-foreground"
              title={ultimaAtualizacao.toLocaleString(
                "pt-BR",
              )}
            >
              {"Atualizado \u00e0s "}
              {ultimaAtualizacao.toLocaleTimeString(
                "pt-BR",
                {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                },
              )}
            </span>
          ) : null}

          <button
            type="button"
            onClick={() =>
              void carregar(true)
            }
            disabled={
              carregando ||
              atualizando
            }
            className="inline-flex items-center justify-center gap-2 rounded-md border px-3 py-2 text-sm font-medium disabled:opacity-50"
          >
            <RefreshCcw
              className={`size-4 ${
                atualizando
                  ? "animate-spin"
                  : ""
              }`}
            />
            Atualizar
          </button>

          <button
            type="button"
            onClick={() =>
              void exportarExcel()
            }
            disabled={
              carregando ||
              atualizando ||
              exportando ||
              linhasOrdenadas.length === 0
            }
            className="inline-flex items-center justify-center gap-2 rounded-md bg-emerald-600 px-3 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download
              className={`size-4 ${
                exportando
                  ? "animate-bounce"
                  : ""
              }`}
            />

            {exportando
              ? "Gerando Excel..."
              : "Exportar Excel"}
          </button>
        </div>
      </header>

      {erro ? (
        <Box
          texto={erro}
          classe="text-destructive"
        />
      ) : null}

      {carregando ? (
        <Box
          texto={
            "Carregando an\u00e1lise oficial..."
          }
          carregando
        />
      ) : null}

      {!carregando &&
      analise &&
      inventario ? (
        <>
          <section className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
            <Kpi
              titulo="Total"
              valor={resumo.total}
              icone={
                <BarChart3 className="size-4" />
              }
              ativo={filtro === "TODOS"}
              onClick={() =>
                selecionarFiltro("TODOS")
              }
            />

            <Kpi
              titulo="OK"
              valor={resumo.ok}
              icone={
                <CheckCircle2 className="size-4" />
              }
              ativo={filtro === "OK"}
              onClick={() =>
                selecionarFiltro("OK")
              }
            />

            <Kpi
              titulo={
                "N\u00e3o iniciados"
              }
              valor={
                resumoOperacional.naoIniciados
              }
              icone={
                <Clock3 className="size-4" />
              }
              ativo={
                filtro ===
                "AGUARDANDO_CONTAGEM"
              }
              onClick={() =>
                selecionarFiltro(
                  "AGUARDANDO_CONTAGEM",
                )
              }
            />

            <Kpi
              titulo="Em contagem"
              valor={
                resumoOperacional.emContagem
              }
              icone={
                <ScanLine className="size-4" />
              }
              ativo={
                filtro === "EM_CONTAGEM"
              }
              onClick={() =>
                selecionarFiltro(
                  "EM_CONTAGEM",
                )
              }
            />

            <Kpi
              titulo={
                "Diverg\u00eancias"
              }
              valor={resumo.divergencias}
              icone={
                <AlertTriangle className="size-4" />
              }
              ativo={
                filtro ===
                "DIVERG\u00caNCIA"
              }
              onClick={() =>
                selecionarFiltro(
                  "DIVERG\u00caNCIA",
                )
              }
            />

            <Kpi
              titulo="Faltas"
              valor={resumo.faltas}
              icone={
                <PackageMinus className="size-4" />
              }
              ativo={filtro === "FALTA"}
              onClick={() =>
                selecionarFiltro("FALTA")
              }
            />

            <Kpi
              titulo="Sobras"
              valor={resumo.sobras}
              icone={
                <PackagePlus className="size-4" />
              }
              ativo={filtro === "SOBRA"}
              onClick={() =>
                selecionarFiltro("SOBRA")
              }
            />
          </section>

          {!encerrado &&
          inventario.em_analise_gestor ? (
            <section className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-4">
              <div className="flex items-start gap-3">
                <ShieldCheck className="mt-0.5 size-5 shrink-0 text-emerald-600" />

                <div>
                  <p className="font-bold text-emerald-700 dark:text-emerald-400">
                    {
                      "Em an\u00e1lise gerencial"
                    }
                  </p>

                  <p className="text-sm text-muted-foreground">
                    Encaminhado
                    {inventario.encaminhado_gestor_por
                      ? ` por ${inventario.encaminhado_gestor_por}`
                      : ""}
                    {inventario.data_hora_encaminhamento_gestor
                      ? ` em ${formatarDataHora(
                          inventario.data_hora_encaminhamento_gestor,
                        )}`
                      : ""}
                    .
                  </p>
                </div>
              </div>

              <Button asChild>
                <Link
                  to="/analise-gestor"
                  search={{
                    inventario:
                      inventario.id_inventario,
                  }}
                >
                  <ShieldCheck className="size-4" />
                  {
                    "Abrir an\u00e1lise gerencial"
                  }
                </Link>
              </Button>
            </section>
          ) : null}

          {!encerrado &&
          !inventario.em_analise_gestor &&
          elegivel ? (
            <section className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-primary/30 bg-primary/5 p-4">
              <div>
                <p className="font-bold text-primary">
                  {
                    "Invent\u00e1rio dispon\u00edvel para decis\u00e3o do gestor"
                  }
                </p>

                <p className="text-sm text-muted-foreground">
                  {
                    "O invent\u00e1rio atende aos crit\u00e9rios para encaminhamento gerencial."
                  }
                </p>
              </div>

              <Button
                type="button"
                disabled={
                  !podeEncaminharPorPerfil ||
                  encaminhando
                }
                onClick={() =>
                  void encaminhar()
                }
              >
                {encaminhando ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Send className="size-4" />
                )}

                {encaminhando
                  ? "Encaminhando..."
                  : "Encaminhar ao gestor"}
              </Button>
            </section>
          ) : null}

          <section className="rounded-xl border bg-card">
            <div className="flex flex-col gap-3 border-b p-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h2 className="font-semibold">
                  {
                    "Itens do invent\u00e1rio"
                  }
                </h2>

                <p className="text-xs text-muted-foreground">
                  Exibindo {primeiroRegistro}
                  {"\u2013"}
                  {ultimoRegistro} de{" "}
                  {linhasOrdenadas.length}{" "}
                  registro(s)
                  {linhasOrdenadas.length !==
                  linhas.length ? (
                    <>
                      {" \u2022 "}
                      {linhas.length} no total
                    </>
                  ) : null}
                </p>
              </div>

              <div className="flex w-full flex-col gap-2 xl:flex-row xl:items-center xl:justify-end">
                <div className="grid w-full gap-2 sm:grid-cols-3 xl:w-[570px] xl:shrink-0">
                  <CampoBusca
                    valor={buscaLocalizacao}
                    placeholder={
                      "Buscar localiza\u00e7\u00e3o"
                    }
                    onChange={
                      setBuscaLocalizacao
                    }
                  />

                  <CampoBusca
                    valor={buscaCodigo}
                    placeholder={
                      "Buscar c\u00f3digo"
                    }
                    onChange={setBuscaCodigo}
                  />

                  <CampoBusca
                    valor={buscaLote}
                    placeholder="Buscar lote"
                    onChange={setBuscaLote}
                  />
                </div>

                <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
                  <label className="inline-flex h-9 shrink-0 cursor-pointer items-center gap-2 rounded-md border bg-background px-3 text-sm font-medium">
                    <input
                      type="checkbox"
                      checked={
                        somenteComDiferenca
                      }
                      onChange={(event) =>
                        setSomenteComDiferenca(
                          event.target.checked,
                        )
                      }
                      className="size-4 rounded border-border accent-primary"
                    />

                    {
                      "Somente com diferen\u00e7a"
                    }
                  </label>

                  <label className="flex shrink-0 items-center gap-2 text-sm">
                    <span className="text-muted-foreground">
                      {
                        "Por p\u00e1gina"
                      }
                    </span>

                    <select
                      value={tamanhoPagina}
                      onChange={(event) =>
                        setTamanhoPagina(
                          Number(
                            event.target.value,
                          ),
                        )
                      }
                      className="h-9 rounded-md border bg-background px-3"
                    >
                      <option value={25}>
                        25
                      </option>
                      <option value={50}>
                        50
                      </option>
                      <option value={100}>
                        100
                      </option>
                    </select>
                  </label>
                </div>
              </div>
            </div>

            {possuiFiltros ? (
              <div className="flex flex-wrap items-center gap-2 border-b bg-muted/20 px-4 py-3">
                <span className="text-xs font-medium text-muted-foreground">
                  Filtros ativos:
                </span>

                {filtro !== "TODOS" ? (
                  <FiltroAtivo
                    texto={`Status: ${nomeStatus(
                      filtro,
                    )}`}
                    onRemover={() =>
                      setFiltro("TODOS")
                    }
                  />
                ) : null}

                {buscaLocalizacao.trim() ? (
                  <FiltroAtivo
                    texto={`Localiza\u00e7\u00e3o: ${buscaLocalizacao.trim()}`}
                    onRemover={() =>
                      setBuscaLocalizacao("")
                    }
                  />
                ) : null}

                {buscaCodigo.trim() ? (
                  <FiltroAtivo
                    texto={`C\u00f3digo: ${buscaCodigo.trim()}`}
                    onRemover={() =>
                      setBuscaCodigo("")
                    }
                  />
                ) : null}

                {buscaLote.trim() ? (
                  <FiltroAtivo
                    texto={`Lote: ${buscaLote.trim()}`}
                    onRemover={() =>
                      setBuscaLote("")
                    }
                  />
                ) : null}

                {somenteComDiferenca ? (
                  <FiltroAtivo
                    texto={
                      "Com diferen\u00e7a"
                    }
                    onRemover={() =>
                      setSomenteComDiferenca(
                        false,
                      )
                    }
                  />
                ) : null}

                <button
                  type="button"
                  onClick={limparFiltros}
                  className="ml-auto text-xs font-semibold text-primary hover:underline"
                >
                  Limpar filtros
                </button>
              </div>
            ) : null}

            <div className="relative overflow-x-auto">
              <table className="w-full min-w-[1100px] text-sm">
                <thead className="sticky top-0 z-10 bg-muted/95 backdrop-blur">
                  <tr className="border-b text-left">
                    <Cabecalho
                      titulo={
                        "Localiza\u00e7\u00e3o"
                      }
                      campo="localizacao"
                      classe="md:sticky md:left-0 md:z-30 md:w-[170px] md:min-w-[170px] md:bg-muted/95"
                      onOrdenar={
                        alternarOrdenacao
                      }
                      icone={iconeOrdenacao}
                    />

                    <Cabecalho
                      titulo={
                        "C\u00f3digo"
                      }
                      campo="codigo"
                      classe="md:sticky md:left-[170px] md:z-30 md:w-[150px] md:min-w-[150px] md:bg-muted/95 md:shadow-[4px_0_6px_-4px_rgba(0,0,0,0.25)]"
                      onOrdenar={
                        alternarOrdenacao
                      }
                      icone={iconeOrdenacao}
                    />

                    <Cabecalho
                      titulo="Lote"
                      campo="lote"
                      onOrdenar={
                        alternarOrdenacao
                      }
                      icone={iconeOrdenacao}
                    />

                    <Cabecalho
                      titulo="Produto"
                      campo="descricao"
                      onOrdenar={
                        alternarOrdenacao
                      }
                      icone={iconeOrdenacao}
                    />

                    <Cabecalho
                      titulo="Estoque"
                      campo="qtd_estoque"
                      numerico
                      onOrdenar={
                        alternarOrdenacao
                      }
                      icone={iconeOrdenacao}
                    />

                    <Cabecalho
                      titulo="Contado"
                      campo="qtd_contada"
                      numerico
                      onOrdenar={
                        alternarOrdenacao
                      }
                      icone={iconeOrdenacao}
                    />

                    <Cabecalho
                      titulo={
                        "Diferen\u00e7a"
                      }
                      campo="diferenca"
                      numerico
                      onOrdenar={
                        alternarOrdenacao
                      }
                      icone={iconeOrdenacao}
                    />

                    <Cabecalho
                      titulo="Status"
                      campo="status"
                      onOrdenar={
                        alternarOrdenacao
                      }
                      icone={iconeOrdenacao}
                    />

                    <th className="px-3 py-3 font-medium">
                      Detalhe
                    </th>
                  </tr>
                </thead>

                <tbody>
                  {linhasPaginadas.map(
                    (item) => (
                      <tr
                        key={item.chave}
                        className="border-b last:border-0"
                      >
                        <td className="px-3 py-3 font-medium md:sticky md:left-0 md:z-10 md:w-[170px] md:min-w-[170px] md:bg-card">
                          {item.localizacao}
                        </td>

                        <td className="px-3 py-3 font-mono font-medium text-primary md:sticky md:left-[170px] md:z-10 md:w-[150px] md:min-w-[150px] md:bg-card md:shadow-[4px_0_6px_-4px_rgba(0,0,0,0.25)]">
                          {item.codigo}
                        </td>

                        <td className="px-3 py-3">
                          {item.lote}
                        </td>

                        <td className="max-w-[280px] px-3 py-3">
                          {item.descricao}
                        </td>

                        <td className="px-3 py-3 text-right">
                          {numero(
                            item.qtd_estoque,
                            2,
                          )}
                        </td>

                        <td className="px-3 py-3 text-right">
                          {numero(
                            item.qtd_contada,
                            2,
                          )}
                        </td>

                        <td className="px-3 py-3 text-right font-medium">
                          <span
                            className={
                              item.resultado_definitivo
                                ? classeDiferenca(
                                    item.diferenca,
                                  )
                                : "text-sky-700"
                            }
                          >
                            {numero(
                              item.diferenca,
                              2,
                            )}
                          </span>

                          {!item.resultado_definitivo ? (
                            <span className="ml-1.5 rounded-full bg-sky-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-sky-700">
                              {
                                "Pr\u00e9via"
                              }
                            </span>
                          ) : null}
                        </td>

                        <td className="px-3 py-3">
                          <span
                            className={`inline-flex rounded-full border px-2 py-1 text-xs font-semibold ${classeStatus(
                              item.status,
                            )}`}
                          >
                            {nomeStatus(
                              item.status,
                            )}
                          </span>
                        </td>

                        <td className="px-3 py-3 text-xs text-muted-foreground">
                          <div className="flex min-w-[220px] items-center gap-2">
                            <span>
                              {item.detalhe ||
                                "-"}
                            </span>

                            {!item.resultado_definitivo ? (
                              <span className="shrink-0 rounded-full bg-sky-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-sky-700">
                                {
                                  "Pr\u00e9via"
                                }
                              </span>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    ),
                  )}

                  {linhasOrdenadas.length === 0 ? (
                    <tr>
                      <td
                        colSpan={9}
                        className="px-4 py-10 text-center text-sm text-muted-foreground"
                      >
                        Nenhum item encontrado com os filtros atuais.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>

            <div className="flex flex-col gap-3 border-t p-4 sm:flex-row sm:items-center sm:justify-between">
              <span className="text-sm text-muted-foreground">
                {"P\u00e1gina "}
                {paginaSegura} de{" "}
                {totalPaginas}
              </span>

              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={
                    paginaSegura <= 1
                  }
                  onClick={() =>
                    setPaginaAtual(
                      Math.max(
                        1,
                        paginaSegura - 1,
                      ),
                    )
                  }
                  className="inline-flex h-9 items-center justify-center rounded-md border bg-background px-4 text-sm font-medium transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Anterior
                </button>

                <button
                  type="button"
                  disabled={
                    paginaSegura >=
                    totalPaginas
                  }
                  onClick={() =>
                    setPaginaAtual(
                      Math.min(
                        totalPaginas,
                        paginaSegura + 1,
                      ),
                    )
                  }
                  className="inline-flex h-9 items-center justify-center rounded-md border bg-background px-4 text-sm font-medium transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {"Pr\u00f3xima"}
                </button>
              </div>
            </div>
          </section>
        </>
      ) : !carregando && !erro ? (
        <Box
          texto={
            "Nenhum invent\u00e1rio oficial dispon\u00edvel."
          }
        />
      ) : null}
    </main>
  );
}

function Kpi({
  titulo,
  valor,
  icone,
  ativo,
  onClick,
}: {
  titulo: string;
  valor: number;
  icone: ReactNode;
  ativo: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full rounded-lg border bg-card p-3 text-left shadow-sm transition hover:bg-muted/30 ${
        ativo
          ? "ring-2 ring-primary"
          : ""
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="whitespace-nowrap text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            {titulo}
          </p>

          <p className="mt-1.5 text-xl font-semibold leading-none">
            {numero(valor)}
          </p>
        </div>

        <div className="shrink-0 rounded-md bg-muted p-1.5 text-muted-foreground">
          {icone}
        </div>
      </div>
    </button>
  );
}

function CampoBusca({
  valor,
  placeholder,
  onChange,
}: {
  valor: string;
  placeholder: string;
  onChange: (valor: string) => void;
}) {
  return (
    <div className="relative">
      <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />

      <input
        type="search"
        value={valor}
        onChange={(event) =>
          onChange(event.target.value)
        }
        placeholder={placeholder}
        className="h-9 w-full rounded-md border bg-background pl-9 pr-3 text-sm"
      />
    </div>
  );
}

function FiltroAtivo({
  texto,
  onRemover,
}: {
  texto: string;
  onRemover: () => void;
}) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border bg-background px-2.5 py-1 text-xs font-medium">
      {texto}

      <button
        type="button"
        onClick={onRemover}
        aria-label={`Remover ${texto}`}
        className="inline-flex size-4 items-center justify-center rounded-full"
      >
        X
      </button>
    </span>
  );
}

function Cabecalho({
  titulo,
  campo,
  numerico = false,
  classe = "",
  onOrdenar,
  icone,
}: {
  titulo: string;
  campo: CampoOrdenacao;
  numerico?: boolean;
  classe?: string;
  onOrdenar: (
    campo: CampoOrdenacao,
  ) => void;
  icone: (
    campo: CampoOrdenacao,
  ) => ReactNode;
}) {
  return (
    <th
      className={`px-3 py-3 font-medium ${
        numerico ? "text-right" : ""
      } ${classe}`}
    >
      <button
        type="button"
        onClick={() =>
          onOrdenar(campo)
        }
        className={`inline-flex items-center gap-1.5 hover:text-primary ${
          numerico ? "ml-auto" : ""
        }`}
      >
        {titulo}
        {icone(campo)}
      </button>
    </th>
  );
}

function Box({
  texto,
  classe = "text-muted-foreground",
  carregando = false,
}: {
  texto: string;
  classe?: string;
  carregando?: boolean;
}) {
  return (
    <div
      className={`flex items-center gap-2 rounded-lg border bg-card p-4 text-sm ${classe}`}
    >
      {carregando ? (
        <Loader2 className="size-4 animate-spin" />
      ) : null}

      {texto}
    </div>
  );
}

function numero(
  valor: number | null | undefined,
  casas = 0,
) {
  if (
    valor === null ||
    valor === undefined ||
    Number.isNaN(valor)
  ) {
    return "-";
  }

  return valor.toLocaleString(
    "pt-BR",
    {
      minimumFractionDigits: casas,
      maximumFractionDigits: casas,
    },
  );
}

function nomeStatus(status: string) {
  if (
    status === "AGUARDANDO_CONTAGEM"
  ) {
    return "N\u00e3o iniciado";
  }

  if (status === "EM_CONTAGEM") {
    return "Em contagem";
  }

  return status.replaceAll("_", " ");
}

function classeStatus(status: string) {
  if (status === "OK") {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-700";
  }

  if (status === "EM_CONTAGEM") {
    return "border-sky-500/30 bg-sky-500/10 text-sky-700";
  }

  if (
    status === "AGUARDANDO_CONTAGEM"
  ) {
    return "border-amber-500/30 bg-amber-500/10 text-amber-700";
  }

  if (status === "FALTA") {
    return "border-red-500/30 bg-red-500/10 text-red-700";
  }

  if (status === "SOBRA") {
    return "border-blue-500/30 bg-blue-500/10 text-blue-700";
  }

  return "border-orange-500/30 bg-orange-500/10 text-orange-700";
}

function classeDiferenca(
  diferenca: number,
) {
  if (diferenca < 0) {
    return "text-red-700";
  }

  if (diferenca > 0) {
    return "text-amber-700";
  }

  return "text-emerald-700";
}

function detalhePrevio(
  qtdContada: number,
  diferenca: number,
) {
  if (qtdContada <= 0) {
    return "Aguardando contagem do item.";
  }

  if (diferenca === 0) {
    return "Quantidade confere at\u00e9 o momento.";
  }

  if (diferenca < 0) {
    return "Quantidade abaixo do estoque at\u00e9 o momento.";
  }

  return "Quantidade acima do estoque at\u00e9 o momento.";
}

function normalizarBusca(
  valor: string,
) {
  return valor
    .trim()
    .toLocaleLowerCase("pt-BR");
}

function formatarDataHora(
  valor: string,
) {
  const data = new Date(valor);

  return Number.isNaN(data.getTime())
    ? valor
    : new Intl.DateTimeFormat(
        "pt-BR",
        {
          dateStyle: "short",
          timeStyle: "short",
        },
      ).format(data);
}

function mensagemErro(
  falha: unknown,
) {
  return falha instanceof Error
    ? falha.message
    : "Erro inesperado.";
}
