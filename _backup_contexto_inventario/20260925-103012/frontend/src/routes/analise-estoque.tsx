import { createFileRoute } from "@tanstack/react-router";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  BarChart3,
  CheckCircle2,
  Clock3,
  PackageMinus,
  PackagePlus,
  Download,
  RefreshCcw,
  Search,
  ScanLine,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  obterInventarioAtual,
  salvarInventarioAtual,
} from "@/lib/inventarioAtual";

import {
  listarInventariosIndicadores,
  type InventarioIndicadores,
} from "@/services/indicadoresService";

import {
  buscarAnaliseRotativo,
  type AnaliseRotativo,
} from "@/services/rotativoService";

import {
  buscarAnaliseOficial,
  buscarRodadaAtualOficial,
  type AnaliseOficial,
} from "@/services/oficialService";

interface AnaliseEstoqueSearch {
  inventario?: number;
}

export const Route = createFileRoute("/analise-estoque")({
  head: () => ({
    meta: [{ title: "An\u00e1lise de Estoque \u2014 SGI" }],
  }),
  validateSearch: (
    search: Record<string, unknown>,
  ): AnaliseEstoqueSearch => {
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
  component: AnaliseEstoquePage,
});

type FiltroStatus =
  | "TODOS"
  | "AGUARDANDO_CONTAGEM"
  | "EM_CONTAGEM"
  | "DIVERGÊNCIA"
  | "FALTA"
  | "SOBRA"
  | "OK";

interface LinhaAnalise {
  chave: string;
  localizacao: string;
  codigo: string;
  lote: string;
  descricao: string;
  qtd_estoque: number;
  qtd_contada: number;
  diferenca: number;
  resultado_definitivo: boolean;
  status: string;
  detalhe: string;
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

  return valor.toLocaleString("pt-BR", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  });
}

function nomeStatus(status: string) {
  if (status === "AGUARDANDO_CONTAGEM") {
    return "N\u00e3o iniciado";
  }

  if (status === "EM_CONTAGEM") {
    return "Em contagem";
  }

  return status;
}

function classeStatus(status: string) {
  if (status === "OK") {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-700";
  }

  if (status === "EM_CONTAGEM") {
    return "border-sky-500/30 bg-sky-500/10 text-sky-700";
  }

  if (status === "AGUARDANDO_CONTAGEM") {
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

function detalhePrevio({
  qtdContada,
  diferenca,
}: {
  qtdContada: number;
  diferenca: number;
}) {
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


function Kpi({
  titulo,
  valor,
  detalhe,
  icone,
  ativo,
  onClick,
}: {
  titulo: string;
  valor: number;
  detalhe?: string;
  icone: ReactNode;
  ativo?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full self-start rounded-lg border bg-card p-3 text-left shadow-sm transition hover:bg-muted/30 ${
        ativo ? "ring-2 ring-primary" : ""
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="whitespace-nowrap text-[11px] font-medium uppercase leading-tight tracking-wide text-muted-foreground">
            {titulo}
          </p>

          <p className="mt-1.5 text-xl font-semibold leading-none">
            {numero(valor)}
          </p>

          {detalhe ? (
            <p className="mt-1 text-[11px] leading-tight text-muted-foreground">
              {detalhe}
            </p>
          ) : null}
        </div>

        <div className="shrink-0 rounded-md bg-muted p-1.5 text-muted-foreground">
          {icone}
        </div>
      </div>
    </button>
  );
}

function AnaliseEstoquePage() {
  const {
    inventario: idInventarioUrl,
  } = Route.useSearch();

  const idInventario =
    idInventarioUrl ??
    obterInventarioAtual();

  const [
    inventarioSelecionado,
    setInventarioSelecionado,
  ] = useState<InventarioIndicadores | null>(
    null,
  );

  const [analiseRotativo, setAnaliseRotativo] =
    useState<AnaliseRotativo | null>(null);

  const [analiseOficial, setAnaliseOficial] =
    useState<AnaliseOficial | null>(null);

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
    useState<
      | "localizacao"
      | "codigo"
      | "lote"
      | "descricao"
      | "qtd_estoque"
      | "qtd_contada"
      | "diferenca"
      | "status"
    >("localizacao");

  const [direcaoOrdenacao, setDirecaoOrdenacao] =
    useState<"asc" | "desc">("asc");

  const [carregando, setCarregando] =
    useState(false);

  const [exportando, setExportando] =
    useState(false);

  const [
    ultimaAtualizacao,
    setUltimaAtualizacao,
  ] = useState<Date | null>(null);

  const [erro, setErro] =
    useState<string | null>(null);

  const requisicaoAtual = useRef(0);

  const carregarInventarioAtual =
    useCallback(async () => {
      setCarregando(true);
      setErro(null);
      setInventarioSelecionado(null);
      setAnaliseRotativo(null);
      setAnaliseOficial(null);
      setUltimaAtualizacao(null);

      try {
        if (!idInventario) {
          throw new Error(
            "Nenhum invent?rio foi selecionado. Acesse o Controle de Invent?rios e abra o invent?rio desejado.",
          );
        }

        const dados =
          await listarInventariosIndicadores();

        const inventarioEncontrado =
          dados.find(
            (item) =>
              item.id_inventario ===
              idInventario,
          );

        if (!inventarioEncontrado) {
          throw new Error(
            `O invent?rio #${idInventario} n?o est? dispon?vel para an?lise.`,
          );
        }

        salvarInventarioAtual(
          inventarioEncontrado.id_inventario,
          inventarioEncontrado.tipo,
        );

        setInventarioSelecionado(
          inventarioEncontrado,
        );
      } catch (e) {
        setErro(
          e instanceof Error
            ? e.message
            : "Falha ao carregar o invent?rio atual.",
        );
      } finally {
        setCarregando(false);
      }
    }, [idInventario]);

  const carregarAnalise =
    useCallback(async () => {
      if (!inventarioSelecionado) {
        return;
      }

      const idReq =
        ++requisicaoAtual.current;

      setCarregando(true);
      setErro(null);
      setFiltro("TODOS");
      setAnaliseRotativo(null);
      setAnaliseOficial(null);

      try {
        if (
          inventarioSelecionado.tipo ===
          "ROTATIVO"
        ) {
          const dados =
            await buscarAnaliseRotativo(
              inventarioSelecionado.id_inventario,
            );

          if (
            idReq !==
            requisicaoAtual.current
          ) {
            return;
          }

          setAnaliseRotativo(dados);
          setUltimaAtualizacao(new Date());
        } else if (
          inventarioSelecionado.tipo ===
          "OFICIAL"
        ) {
          const rodada =
            await buscarRodadaAtualOficial(
              inventarioSelecionado.id_inventario,
            );

          const dados =
            await buscarAnaliseOficial(
              inventarioSelecionado.id_inventario,
              rodada.id_rodada,
            );

          if (
            idReq !==
            requisicaoAtual.current
          ) {
            return;
          }

          setAnaliseOficial(dados);
          setUltimaAtualizacao(new Date());
        } else {
          throw new Error(
            "Tipo de inventário não suportado nesta análise.",
          );
        }
      } catch (e) {
        if (
          idReq !==
          requisicaoAtual.current
        ) {
          return;
        }

        setErro(
          e instanceof Error
            ? e.message
            : "Falha ao carregar a análise de estoque.",
        );
      } finally {
        if (
          idReq ===
          requisicaoAtual.current
        ) {
          setCarregando(false);
        }
      }
    }, [inventarioSelecionado]);

  useEffect(() => {
    void carregarInventarioAtual();
  }, [carregarInventarioAtual]);

  useEffect(() => {
    void carregarAnalise();
  }, [carregarAnalise]);

  const resumo = useMemo(() => {
    if (analiseRotativo) {
      return {
        total:
          analiseRotativo.resumo.total_itens,
        ok:
          analiseRotativo.resumo.ok,
        aguardando:
          analiseRotativo.resumo
            .aguardando_contagem,
        divergencias:
          analiseRotativo.resumo.divergencias,
        faltas:
          analiseRotativo.resumo.faltas,
        sobras:
          analiseRotativo.resumo.sobras,
      };
    }

    if (analiseOficial) {
      return {
        total:
          analiseOficial.resumo.total_registros,
        ok:
          analiseOficial.resumo.ok,
        aguardando:
          analiseOficial.resumo
            .aguardando_contagem,
        divergencias:
          analiseOficial.resumo.divergencias,
        faltas:
          analiseOficial.resumo.faltas,
        sobras:
          analiseOficial.resumo.sobras,
      };
    }

    return {
      total: 0,
      ok: 0,
      aguardando: 0,
      divergencias: 0,
      faltas: 0,
      sobras: 0,
    };
  }, [
    analiseRotativo,
    analiseOficial,
  ]);

  const linhas = useMemo<LinhaAnalise[]>(
    () => {
      if (analiseRotativo) {
        return analiseRotativo.itens.map(
          (item) => ({
            chave: item.chave,
            localizacao:
              item.localizacao || "-",
            codigo: item.codigo,
            lote: item.lote || "-",
            descricao:
              item.produto ??
              "Produto sem descrição",
            qtd_estoque:
              item.qtd_estoque,
            qtd_contada:
              item.qtd_contada,
            diferenca:
              item.diferenca,
            resultado_definitivo:
              item.resultado_definitivo &&
              item.status !==
                "AGUARDANDO_CONTAGEM",
            status:
              item.status ===
                "AGUARDANDO_CONTAGEM" &&
              item.qtd_contada > 0
                ? "EM_CONTAGEM"
                : item.status,
            detalhe:
              item.status ===
              "AGUARDANDO_CONTAGEM"
                ? detalhePrevio({
                    qtdContada:
                      item.qtd_contada,
                    diferenca:
                      item.diferenca,
                  })
                : item.subtipo_divergencia ??
                  (item.pendente_recontagem
                    ? "Pendente de recontagem"
                    : ""),
          }),
        );
      }

      if (analiseOficial) {
        return analiseOficial.itens.map(
          (item) => ({
            chave: item.chave,
            localizacao:
              item.localizacoes_bipadas
                .map(
                  (loc) =>
                    loc.localizacao,
                )
                .join(", ") || "-",
            codigo: item.codigo,
            lote: item.lote || "-",
            descricao:
              item.descricao ??
              "Produto sem descrição",
            qtd_estoque:
              item.qtd_estoque,
            qtd_contada:
              item.qtd_contada,
            diferenca:
              item.diferenca,
            resultado_definitivo:
              item.resultado_definitivo,
            status:
              item.status ===
                "AGUARDANDO_CONTAGEM" &&
              item.qtd_contada > 0
                ? "EM_CONTAGEM"
                : item.status,
            detalhe:
              item.resultado_definitivo
                ? item.detalhe ?? ""
                : detalhePrevio({
                    qtdContada:
                      item.qtd_contada,
                    diferenca:
                      item.diferenca,
                  }),
          }),
        );
      }

      return [];
    },
    [
      analiseRotativo,
      analiseOficial,
    ],
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

  const linhasFiltradas = useMemo(
    () => {
      const localizacao = buscaLocalizacao
        .trim()
        .toLocaleLowerCase("pt-BR");

      const codigo = buscaCodigo
        .trim()
        .toLocaleLowerCase("pt-BR");

      const lote = buscaLote
        .trim()
        .toLocaleLowerCase("pt-BR");


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
          !item.localizacao
            .toLocaleLowerCase("pt-BR")
            .includes(localizacao)
        ) {
          return false;
        }

        if (
          codigo &&
          !item.codigo
            .toLocaleLowerCase("pt-BR")
            .includes(codigo)
        ) {
          return false;
        }

        if (
          lote &&
          !item.lote
            .toLocaleLowerCase("pt-BR")
            .includes(lote)
        ) {
          return false;
        }


        return true;
      });
    },
    [
      linhas,
      filtro,
      somenteComDiferenca,
      buscaLocalizacao,
      buscaCodigo,
      buscaLote,
    ],
  );

  const linhasOrdenadas = useMemo(
    () => {
      const resultado = [
        ...linhasFiltradas,
      ];

      resultado.sort((itemA, itemB) => {
        if (
          campoOrdenacao === "diferenca" &&
          itemA.resultado_definitivo !==
            itemB.resultado_definitivo
        ) {
          return itemA.resultado_definitivo
            ? -1
            : 1;
        }

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
          comparacao = String(valorA).localeCompare(
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
    },
    [
      linhasFiltradas,
      campoOrdenacao,
      direcaoOrdenacao,
    ],
  );

  function alternarOrdenacao(
    campo: typeof campoOrdenacao,
  ) {
    if (campoOrdenacao === campo) {
      setDirecaoOrdenacao(
        (direcaoAtual) =>
          direcaoAtual === "asc"
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
    campo: typeof campoOrdenacao,
  ) {
    if (campoOrdenacao !== campo) {
      return (
        <ArrowUpDown className="h-3.5 w-3.5 opacity-40" />
      );
    }

    return direcaoOrdenacao === "asc" ? (
      <ArrowUp className="h-3.5 w-3.5" />
    ) : (
      <ArrowDown className="h-3.5 w-3.5" />
    );
  }

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
      linhasFiltradas.length /
        tamanhoPagina,
    ),
  );

  const paginaSegura = Math.min(
    paginaAtual,
    totalPaginas,
  );

  const indiceInicial =
    (paginaSegura - 1) * tamanhoPagina;

  const linhasPaginadas =
    linhasOrdenadas.slice(
      indiceInicial,
      indiceInicial + tamanhoPagina,
    );

  const primeiroRegistro =
    linhasFiltradas.length === 0
      ? 0
      : indiceInicial + 1;

  const ultimoRegistro = Math.min(
    indiceInicial + tamanhoPagina,
    linhasFiltradas.length,
  );

  const numeroRodada =
    analiseRotativo?.numero_rodada ??
    analiseOficial?.numero_rodada ??
    inventarioSelecionado?.rodada_atual ??
    null;

  const statusRodada =
    analiseRotativo?.status_rodada ??
    analiseOficial?.status_rodada ??
    "-";

  async function exportarExcel() {
    if (
      !inventarioSelecionado ||
      linhasFiltradas.length === 0
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

      const workbook = new ExcelJS.Workbook();

      workbook.creator = "SGI";
      workbook.company = "Alzarsi Log\u00edstica";
      workbook.created = new Date();
      workbook.modified = new Date();

      const abaResumo =
        workbook.addWorksheet("Resumo", {
          views: [
            {
              state: "frozen",
              ySplit: 1,
            },
          ],
        });

      abaResumo.columns = [
        {
          header: "Campo",
          key: "campo",
          width: 28,
        },
        {
          header: "Valor",
          key: "valor",
          width: 55,
        },
      ];

      abaResumo.addRows([
        {
          campo: "Invent\u00e1rio",
          valor:
            inventarioSelecionado.codigo_inventario,
        },
        {
          campo: "Cliente",
          valor: inventarioSelecionado.cliente,
        },
        {
          campo: "Armaz\u00e9m",
          valor: inventarioSelecionado.armazem,
        },
        {
          campo: "Tipo",
          valor: inventarioSelecionado.tipo,
        },
        {
          campo: "Rodada",
          valor: numeroRodada ?? "-",
        },
        {
          campo: "Status da rodada",
          valor: statusRodada ?? "-",
        },
        {
          campo: "Filtro de status",
          valor:
            filtro === "TODOS"
              ? "Todos"
              : nomeStatus(filtro),
        },
        {
          campo: "Filtro de localiza\u00e7\u00e3o",
          valor:
            buscaLocalizacao.trim() || "-",
        },
        {
          campo: "Filtro de c\u00f3digo",
          valor: buscaCodigo.trim() || "-",
        },
        {
          campo: "Filtro de lote",
          valor: buscaLote.trim() || "-",
        },
        {
          campo: "Somente com diferen\u00e7a",
          valor:
            somenteComDiferenca
              ? "Sim"
              : "N\u00e3o",
        },
        {
          campo: "Registros exportados",
          valor: linhasFiltradas.length,
        },
        {
          campo: "Total",
          valor: resumo.total,
        },
        {
          campo: "OK",
          valor: resumo.ok,
        },
        {
          campo: "N\u00e3o iniciados",
          valor:
            resumoOperacional.naoIniciados,
        },
        {
          campo: "Em contagem",
          valor:
            resumoOperacional.emContagem,
        },
        {
          campo: "Diverg\u00eancias",
          valor: resumo.divergencias,
        },
        {
          campo: "Faltas",
          valor: resumo.faltas,
        },
        {
          campo: "Sobras",
          valor: resumo.sobras,
        },
        {
          campo: "Gerado em",
          valor: new Date().toLocaleString(
            "pt-BR",
          ),
        },
      ]);

      const abaItens =
        workbook.addWorksheet("Itens", {
          views: [
            {
              state: "frozen",
              ySplit: 1,
            },
          ],
        });

      abaItens.columns = [
        {
          header: "Localiza\u00e7\u00e3o",
          key: "localizacao",
          width: 22,
        },
        {
          header: "C\u00f3digo",
          key: "codigo",
          width: 20,
        },
        {
          header: "Lote",
          key: "lote",
          width: 18,
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
          width: 24,
        },
        {
          header: "Detalhe",
          key: "detalhe",
          width: 38,
        },
      ];

      abaItens.addRows(
        linhasFiltradas.map((item) => ({
          localizacao: item.localizacao,
          codigo: String(item.codigo),
          lote: String(item.lote),
          produto: item.descricao,
          estoque: item.qtd_estoque,
          contado: item.qtd_contada,
          diferenca: item.diferenca,
          status: nomeStatus(item.status),
          detalhe:
            item.resultado_definitivo
              ? item.detalhe || "-"
              : item.detalhe
                ? `${item.detalhe} \u2022 Pr\u00e9via`
                : "Aguardando contagem \u2022 Pr\u00e9via",
        })),
      );

      const corCabecalho = "FF1E3A5F";
      const corTextoCabecalho = "FFFFFFFF";

      for (const aba of [
        abaResumo,
        abaItens,
      ]) {
        const cabecalho = aba.getRow(1);

        cabecalho.height = 24;
        cabecalho.font = {
          bold: true,
          color: {
            argb: corTextoCabecalho,
          },
        };

        cabecalho.fill = {
          type: "pattern",
          pattern: "solid",
          fgColor: {
            argb: corCabecalho,
          },
        };

        cabecalho.alignment = {
          vertical: "middle",
        };

        cabecalho.eachCell((celula) => {
          celula.border = {
            bottom: {
              style: "thin",
              color: {
                argb: "FFD1D5DB",
              },
            },
          };
        });
      }

      abaResumo.getColumn("campo").font = {
        bold: true,
      };

      abaItens.autoFilter = {
        from: "A1",
        to: `I${Math.max(
          1,
          abaItens.rowCount,
        )}`,
      };

      for (const coluna of [
        "estoque",
        "contado",
        "diferenca",
      ]) {
        abaItens.getColumn(coluna).numFmt =
          '#,##0.00;[Red]-#,##0.00';
      }

      abaItens.getColumn("codigo").numFmt = "@";
      abaItens.getColumn("lote").numFmt = "@";

      for (
        let numeroLinha = 2;
        numeroLinha <= abaItens.rowCount;
        numeroLinha += 1
      ) {
        const linha =
          abaItens.getRow(numeroLinha);

        linha.alignment = {
          vertical: "middle",
          wrapText: true,
        };

        const diferenca = Number(
          linha.getCell(7).value ?? 0,
        );

        if (diferenca < 0) {
          linha.getCell(7).font = {
            bold: true,
            color: {
              argb: "FFB91C1C",
            },
          };
        } else if (diferenca > 0) {
          linha.getCell(7).font = {
            bold: true,
            color: {
              argb: "FFB45309",
            },
          };
        }
      }

      const buffer =
        await workbook.xlsx.writeBuffer();

      const arquivoExcel = new Blob(
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
        inventarioSelecionado.codigo_inventario
          .replace(/[^a-zA-Z0-9_-]/g, "_");

      const rodadaArquivo =
        numeroRodada ?? "sem-rodada";

      saveAs(
        arquivoExcel,
        `Analise_Estoque_${codigoArquivo}_R${rodadaArquivo}_${dataArquivo}.xlsx`,
      );
    } catch (erroExportacao) {
      setErro(
        erroExportacao instanceof Error
          ? `Falha ao gerar o Excel: ${erroExportacao.message}`
          : "Falha ao gerar o arquivo Excel.",
      );
    } finally {
      setExportando(false);
    }
  }

  return (
    <div className="space-y-6 p-4 md:p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <BarChart3 className="h-6 w-6" />

            <h1 className="text-2xl font-bold">
              Análise de Estoque
            </h1>
          </div>

          <p className="mt-1 text-sm text-muted-foreground">
            Acompanhe o que já foi contado, o que ainda está pendente e as divergências encontradas no inventário.
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
              void carregarAnalise()
            }
            disabled={
              !inventarioSelecionado ||
              carregando
            }
            className="inline-flex items-center justify-center gap-2 rounded-md border px-3 py-2 text-sm font-medium disabled:opacity-50"
          >
            <RefreshCcw
              className={`h-4 w-4 ${
                carregando
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
              !inventarioSelecionado ||
              carregando ||
              exportando ||
              linhasFiltradas.length === 0
            }
            className="inline-flex items-center justify-center gap-2 rounded-md bg-emerald-600 px-3 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download
              className={`h-4 w-4 ${
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
      </div>

      {erro ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          {erro}
        </div>
      ) : null}

      {(analiseRotativo ||
        analiseOficial) ? (
        <>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
            <Kpi
              titulo="Total"
              valor={resumo.total}
              icone={
                <BarChart3 className="h-4 w-4" />
              }
              ativo={filtro === "TODOS"}
              onClick={() =>
                setFiltro("TODOS")
              }
            />

            <Kpi
              titulo="OK"
              valor={resumo.ok}
              icone={
                <CheckCircle2 className="h-4 w-4" />
              }
              ativo={filtro === "OK"}
              onClick={() =>
                setFiltro("OK")
              }
            />

            <Kpi
              titulo={"N\u00e3o iniciados"}
              valor={
                resumoOperacional.naoIniciados
              }
              icone={
                <Clock3 className="h-4 w-4" />
              }
              ativo={
                filtro ===
                "AGUARDANDO_CONTAGEM"
              }
              onClick={() =>
                setFiltro(
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
                <ScanLine className="h-4 w-4" />
              }
              ativo={
                filtro === "EM_CONTAGEM"
              }
              onClick={() =>
                setFiltro("EM_CONTAGEM")
              }
            />

            <Kpi
              titulo="Divergências"
              valor={resumo.divergencias}
              icone={
                <AlertTriangle className="h-4 w-4" />
              }
              ativo={
                filtro ===
                "DIVERGÊNCIA"
              }
              onClick={() =>
                setFiltro(
                  "DIVERGÊNCIA",
                )
              }
            />

            <Kpi
              titulo="Faltas"
              valor={resumo.faltas}
              icone={
                <PackageMinus className="h-4 w-4" />
              }
              ativo={filtro === "FALTA"}
              onClick={() =>
                setFiltro("FALTA")
              }
            />

            <Kpi
              titulo="Sobras"
              valor={resumo.sobras}
              icone={
                <PackagePlus className="h-4 w-4" />
              }
              ativo={filtro === "SOBRA"}
              onClick={() =>
                setFiltro("SOBRA")
              }
            />
          </div>

          <div className="rounded-xl border bg-card">
            <div className="flex flex-col gap-3 border-b p-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h2 className="font-semibold">
                  Itens do inventário
                </h2>

                <p className="text-xs text-muted-foreground">
                  {"Exibindo "}
                  {numero(primeiroRegistro)}
                  {"\u2013"}
                  {numero(ultimoRegistro)}
                  {" de "}
                  {numero(linhasFiltradas.length)}
                  {" registro(s)"}

                  {linhasFiltradas.length !==
                  linhas.length ? (
                    <>
                      {" \u2022 "}
                      {numero(linhas.length)}
                      {" no total"}
                    </>
                  ) : null}
                </p>
              </div>

              <div className="flex w-full flex-col gap-2 xl:flex-row xl:items-center xl:justify-end">
 <div className="grid w-full gap-2 sm:grid-cols-3 xl:w-[570px] xl:shrink-0">
                  <div className="relative">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />

                    <input
                      type="search"
                      value={buscaLocalizacao}
                      onChange={(e) =>
                        setBuscaLocalizacao(
                          e.target.value,
                        )
                      }
                      placeholder={
                        "Buscar localiza\u00e7\u00e3o"
                      }
                      className="h-9 w-full rounded-md border bg-background pl-9 pr-3 text-sm"
                    />
                  </div>

                  <div className="relative">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />

                    <input
                      type="search"
                      value={buscaCodigo}
                      onChange={(e) =>
                        setBuscaCodigo(
                          e.target.value,
                        )
                      }
                      placeholder={
                        "Buscar c\u00f3digo"
                      }
                      className="h-9 w-full rounded-md border bg-background pl-9 pr-3 text-sm"
                    />
                  </div>

                  <div className="relative">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />

                    <input
                      type="search"
                      value={buscaLote}
                      onChange={(e) =>
                        setBuscaLote(
                          e.target.value,
                        )
                      }
                      placeholder="Buscar lote"
                      className="h-9 w-full rounded-md border bg-background pl-9 pr-3 text-sm"
                    />
                  </div>

                </div>

                <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
                  <label className="inline-flex h-9 shrink-0 cursor-pointer items-center gap-2 rounded-md border bg-background px-3 text-sm font-medium">
                    <input
                      type="checkbox"
                      checked={somenteComDiferenca}
                      onChange={(e) =>
                        setSomenteComDiferenca(
                          e.target.checked,
                        )
                      }
                      className="h-4 w-4 rounded border-border accent-primary"
                    />

                    {"Somente com diferen\u00e7a"}
                  </label>

                  <label className="flex shrink-0 items-center gap-2 text-sm">
                    <span className="text-muted-foreground">
                      {"Por p\u00e1gina"}
                    </span>

                    <select
                      value={tamanhoPagina}
                      onChange={(e) =>
                        setTamanhoPagina(
                          Number(e.target.value),
                        )
                      }
                      className="h-9 rounded-md border bg-background px-3"
                      aria-label={
                        "Quantidade de registros por p\u00e1gina"
                      }
                    >
                      <option value={25}>25</option>
                      <option value={50}>50</option>
                      <option value={100}>100</option>
                    </select>
                  </label>
                </div>
              </div>
            </div>

            {filtro !== "TODOS" ||
            buscaLocalizacao.trim() ||
            buscaCodigo.trim() ||
            buscaLote.trim() ||
            somenteComDiferenca ? (
              <div className="flex flex-wrap items-center gap-2 border-b bg-muted/20 px-4 py-3">
                <span className="text-xs font-medium text-muted-foreground">
                  Filtros ativos:
                </span>

                {filtro !== "TODOS" ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full border bg-background px-2.5 py-1 text-xs font-medium">
                    Status: {nomeStatus(filtro)}
                    <button
                      type="button"
                      onClick={() =>
                        setFiltro("TODOS")
                      }
                      className="inline-flex h-4 w-4 items-center justify-center rounded-full"
                      aria-label="Remover status"
                    >
                      X
                    </button>
                  </span>
                ) : null}

                {buscaLocalizacao.trim() ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full border bg-background px-2.5 py-1 text-xs font-medium">
                    {"Localiza\u00e7\u00e3o: "}
                    {buscaLocalizacao.trim()}
                    <button
                      type="button"
                      onClick={() =>
                        setBuscaLocalizacao("")
                      }
                      aria-label={
                        "Remover localiza\u00e7\u00e3o"
                      }
                    >
                      X
                    </button>
                  </span>
                ) : null}

                {buscaCodigo.trim() ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full border bg-background px-2.5 py-1 text-xs font-medium">
                    {"C\u00f3digo: "}
                    {buscaCodigo.trim()}
                    <button
                      type="button"
                      onClick={() =>
                        setBuscaCodigo("")
                      }
                      aria-label="Remover c?digo"
                    >
                      X
                    </button>
                  </span>
                ) : null}

                {buscaLote.trim() ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full border bg-background px-2.5 py-1 text-xs font-medium">
                    Lote: {buscaLote.trim()}
                    <button
                      type="button"
                      onClick={() =>
                        setBuscaLote("")
                      }
                      aria-label="Remover lote"
                    >
                      X
                    </button>
                  </span>
                ) : null}


                {somenteComDiferenca ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full border bg-background px-2.5 py-1 text-xs font-medium">
                    {"Com diferen\u00e7a"}
                    <button
                      type="button"
                      onClick={() =>
                        setSomenteComDiferenca(
                          false,
                        )
                      }
                      aria-label={
                        "Remover filtro de diferen\u00e7a"
                      }
                    >
                      X
                    </button>
                  </span>
                ) : null}

                <button
                  type="button"
                  onClick={() => {
                    setFiltro("TODOS");
                    setBuscaLocalizacao("");
                    setBuscaCodigo("");
                    setBuscaLote("");
                    setSomenteComDiferenca(false);
                  }}
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
                    <th className="px-3 py-3 font-medium md:sticky md:left-0 md:z-30 md:w-[170px] md:min-w-[170px] md:bg-muted/95">
                      <button
                        type="button"
                        onClick={() =>
                          alternarOrdenacao(
                            "localizacao",
                          )
                        }
                        className="inline-flex items-center gap-1.5 hover:text-primary"
                      >
                        {"Localiza\u00e7\u00e3o"}
                        {iconeOrdenacao(
                          "localizacao",
                        )}
                      </button>
                    </th>

                    <th className="px-3 py-3 font-medium md:sticky md:left-[170px] md:z-30 md:w-[150px] md:min-w-[150px] md:bg-muted/95 md:shadow-[4px_0_6px_-4px_rgba(0,0,0,0.25)]">
                      <button
                        type="button"
                        onClick={() =>
                          alternarOrdenacao(
                            "codigo",
                          )
                        }
                        className="inline-flex items-center gap-1.5 hover:text-primary"
                      >
                        {"C\u00f3digo"}
                        {iconeOrdenacao("codigo")}
                      </button>
                    </th>

                    <th className="px-3 py-3 font-medium">
                      <button
                        type="button"
                        onClick={() =>
                          alternarOrdenacao("lote")
                        }
                        className="inline-flex items-center gap-1.5 hover:text-primary"
                      >
                        Lote
                        {iconeOrdenacao("lote")}
                      </button>
                    </th>

                    <th className="px-3 py-3 font-medium">
                      <button
                        type="button"
                        onClick={() =>
                          alternarOrdenacao(
                            "descricao",
                          )
                        }
                        className="inline-flex items-center gap-1.5 hover:text-primary"
                      >
                        Produto
                        {iconeOrdenacao(
                          "descricao",
                        )}
                      </button>
                    </th>

                    <th className="px-3 py-3 text-right font-medium">
                      <button
                        type="button"
                        onClick={() =>
                          alternarOrdenacao(
                            "qtd_estoque",
                          )
                        }
                        className="ml-auto inline-flex items-center gap-1.5 hover:text-primary"
                      >
                        Estoque
                        {iconeOrdenacao(
                          "qtd_estoque",
                        )}
                      </button>
                    </th>

                    <th className="px-3 py-3 text-right font-medium">
                      <button
                        type="button"
                        onClick={() =>
                          alternarOrdenacao(
                            "qtd_contada",
                          )
                        }
                        className="ml-auto inline-flex items-center gap-1.5 hover:text-primary"
                      >
                        Contado
                        {iconeOrdenacao(
                          "qtd_contada",
                        )}
                      </button>
                    </th>

                    <th className="px-3 py-3 text-right font-medium">
                      <button
                        type="button"
                        onClick={() =>
                          alternarOrdenacao(
                            "diferenca",
                          )
                        }
                        className="ml-auto inline-flex items-center gap-1.5 hover:text-primary"
                      >
                        {"Diferen\u00e7a"}
                        {iconeOrdenacao(
                          "diferenca",
                        )}
                      </button>
                    </th>

                    <th className="px-3 py-3 font-medium">
                      <button
                        type="button"
                        onClick={() =>
                          alternarOrdenacao(
                            "status",
                          )
                        }
                        className="inline-flex items-center gap-1.5 hover:text-primary"
                      >
                        Status
                        {iconeOrdenacao("status")}
                      </button>
                    </th>

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

                        <td className="px-3 py-3 md:sticky md:left-[170px] md:z-10 md:w-[150px] md:min-w-[150px] md:bg-card md:shadow-[4px_0_6px_-4px_rgba(0,0,0,0.25)]">
                          {item.codigo}
                        </td>

                        <td className="px-3 py-3">
                          {item.lote}
                        </td>

                        <td className="max-w-[260px] px-3 py-3">
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
                          {item.resultado_definitivo ? (
                            <span
                              className={
                                item.diferenca < 0
                                  ? "text-red-700"
                                  : item.diferenca > 0
                                    ? "text-amber-700"
                                    : "text-emerald-700"
                              }
                            >
                              {numero(
                                item.diferenca,
                                2,
                              )}
                            </span>
                          ) : (
                            <span
                              className="inline-flex items-center justify-end gap-1.5 text-sky-700"
                              title={
                                "Diferen\u00e7a pr\u00e9via. O resultado definitivo ser\u00e1 consolidado ap\u00f3s o encerramento."
                              }
                            >
                              <span className="font-medium">
                                {numero(
                                  item.diferenca,
                                  2,
                                )}
                              </span>

                              <span className="rounded-full bg-sky-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-sky-700">
                                {"Pr\u00e9via"}
                              </span>
                            </span>
                          )}
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
                              {item.detalhe || "-"}
                            </span>

                            {!item.resultado_definitivo &&
                            item.detalhe ? (
                              <span className="shrink-0 rounded-full bg-sky-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-sky-700">
                                {"Pr\u00e9via"}
                              </span>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    ),
                  )}

                  {linhasFiltradas.length ===
                  0 ? (
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
                {paginaSegura}
                {" de "}
                {totalPaginas}
              </span>

              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={paginaSegura <= 1}
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
                    paginaSegura >= totalPaginas
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
          </div>
        </>
      ) : null}

      {carregando ? (
        <div className="rounded-xl border bg-card p-8 text-center text-sm text-muted-foreground">
          Carregando análise de estoque...
        </div>
      ) : null}
    </div>
  );
}
