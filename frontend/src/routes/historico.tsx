import {
  createFileRoute,
  Link,
  useNavigate,
} from "@tanstack/react-router";
import {
  useEffect,
  useMemo,
  useState,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
} from "react";
import {
  consultarInventarioDetalhe,
  listarClientesDisponiveis,
} from "@/services/inventarioService";

import type {
  ClienteDisponivelInventario,
} from "@/types/inventory";

import {
  buscarHistoricoDivergencias,
  buscarHistoricoInventarios,
  buscarHistoricoItem,
  buscarHistoricoLocalizacao,
  type HistoricoDivergenciasResponse,
  type HistoricoInventariosResponse,
  type HistoricoItemInventario,
  type HistoricoLocalizacaoResponse,
} from "../services/historicoService";

import {
  buscarRodadasInventario,
} from "@/services/recontagemService";

import {
  buscarAcompanhamentoLocalizacoes,
  buscarResultadoFinalIndicadores,
  type AcompanhamentoLocalizacoes,
  type ResultadoFinalIndicadores,
} from "@/services/indicadoresService";

import {
  buscarAnaliseFinanceiraOficial,
  type AnaliseFinanceiraOficial,
} from "@/services/analiseFinanceiraOficialService";

import {
  buscarAuditoriaInventario,
  type AuditoriaResponse,
} from "@/services/auditoriaService";

import {
  buscarAnaliseRotativo,
} from "@/services/rotativoService";

import {
  buscarAnaliseOficial,
  buscarRodadaAtualOficial,
} from "@/services/oficialService";

import {
  buscarAnaliseGestor,
} from "@/services/gestorService";

import {
  exportarAnaliseInventarioExcel,
} from "@/services/exportacaoInventarioExcel";

import {
  TratativasHistorico,
  type TratativasContexto,
} from "@/components/tratativas/TratativasHistorico";
import { obterUsuarioSalvo } from "@/services/authService";

interface ItemHistoricoContexto {
  chave: string;
  localizacao: string;
  codigo: string;
  lote: string;
  descricao: string;
  qtd_estoque: number;
  qtd_contada: number;
  diferenca: number;
  status: string;
}

interface DivergenciaHistoricoContexto {
  chave: string;
  rodada: number | null;
  localizacao: string;
  codigo: string;
  lote: string;
  descricao: string;
  qtd_estoque: number;
  qtd_contada: number;
  diferenca: number;
  status: string;
  resultado_definitivo: boolean | null;
  pendente_recontagem: boolean | null;
  pendente_decisao: boolean | null;
  detalhe: string | null;
}

interface DecisaoHistoricoContexto {
  chave: string;
  rodada: number | null;
  localizacao: string;
  codigo: string;
  lote: string;
  descricao: string;
  possui_decisao: boolean;
  decisao: string | null;
  quantidade_aprovada: number | null;
  justificativa: string | null;
  usuario: string | null;
  data_hora: string | null;
  status: string;
  pendente: boolean;
  recontagem: boolean;
  resolvido: boolean;
}

type AbaGlobalSearch =
  | "inventarios"
  | "item"
  | "localizacao"
  | "divergencias"
  | "tratativas";

type AbaContextualSearch =
  | "visao-geral"
  | "rodadas"
  | "itens-contexto"
  | "localizacoes-contexto"
  | "divergencias-contexto"
  | "decisoes"
  | "resultado-final"
  | "indicadores"
  | "eventos";

type AbaSearch =
  | AbaGlobalSearch
  | AbaContextualSearch;

const ABAS_GLOBAIS_VALIDAS =
  new Set<AbaGlobalSearch>([
    "inventarios",
    "item",
    "localizacao",
    "divergencias",
    "tratativas",
  ]);

const ABAS_CONTEXTUAIS_VALIDAS =
  new Set<AbaContextualSearch>([
    "visao-geral",
    "rodadas",
    "itens-contexto",
    "localizacoes-contexto",
    "divergencias-contexto",
    "decisoes",
    "resultado-final",
    "indicadores",
    "eventos",
  ]);

interface HistoricoSearch {
  inventario?: number;
  aba?: AbaSearch;
  tratativa_inventario?: number;
  ocorrencia?: number;
}

function inteiroPositivo(
  valor: unknown,
): number | undefined {
  const numero = Number(valor);

  return Number.isInteger(numero) && numero > 0
    ? numero
    : undefined;
}

export const Route = createFileRoute("/historico")({
  validateSearch: (
    search: Record<string, unknown>,
  ): HistoricoSearch => {
    const abaInformada =
      typeof search["aba"] === "string"
        ? search["aba"]
        : undefined;

    /*
     * Tratativas e historico contextual usam parametros
     * distintos para evitar conflito entre o filtro da
     * tratativa e o contexto historico de um inventario.
     */
    if (abaInformada === "tratativas") {
      const tratativaInventario = inteiroPositivo(
        search["tratativa_inventario"],
      );
      const ocorrencia = inteiroPositivo(
        search["ocorrencia"],
      );

      return {
        aba: "tratativas",
        ...(tratativaInventario !== undefined
          ? { tratativa_inventario: tratativaInventario }
          : {}),
        ...(ocorrencia !== undefined
          ? { ocorrencia }
          : {}),
      };
    }

    const inventario = inteiroPositivo(
      search["inventario"],
    );

    if (inventario !== undefined) {
      const abaContextual =
        abaInformada &&
        ABAS_CONTEXTUAIS_VALIDAS.has(
          abaInformada as AbaContextualSearch,
        )
          ? (abaInformada as AbaContextualSearch)
          : undefined;

      return {
        inventario,
        ...(abaContextual
          ? { aba: abaContextual }
          : {}),
      };
    }

    const abaGlobal =
      abaInformada &&
      ABAS_GLOBAIS_VALIDAS.has(
        abaInformada as AbaGlobalSearch,
      )
        ? (abaInformada as AbaGlobalSearch)
        : undefined;

    return abaGlobal
      ? { aba: abaGlobal }
      : {};
  },
  head: () => ({
    meta: [{ title: "Histórico — SGI" }],
  }),
  component: HistoricoPage,
});

type Aba = AbaSearch;

const ABAS_GLOBAIS: ReadonlyArray<
  readonly [AbaGlobalSearch, string]
> = [
  ["inventarios", "Inventários"],
  ["item", "Item / lote"],
  ["localizacao", "Localização"],
  ["divergencias", "Divergências"],
  ["tratativas", "Tratativas"],
];

const ABAS_CONTEXTUAIS: ReadonlyArray<
  readonly [AbaContextualSearch, string]
> = [
  ["visao-geral", "Visão geral"],
  ["rodadas", "Rodadas"],
  ["itens-contexto", "Itens"],
  ["localizacoes-contexto", "Localizações"],
  ["divergencias-contexto", "Divergências"],
  ["decisoes", "Decisões"],
  ["resultado-final", "Resultado final"],
  ["indicadores", "Indicadores"],
  ["eventos", "Eventos"],
];

type CampoOrdenacaoInventario =
  | "id"
  | "codigo"
  | "cliente"
  | "armazem"
  | "tipo"
  | "status"
  | "rodada"
  | "inicio"
  | "fim";

type ColunaTabelaInventario =
  | CampoOrdenacaoInventario
  | "acao";

type DirecaoOrdenacaoInventario =
  | "asc"
  | "desc";

const LARGURAS_PADRAO_TABELA_INVENTARIO: Record<
  ColunaTabelaInventario,
  number
> = {
  id: 68,
  codigo: 115,
  cliente: 260,
  armazem: 92,
  tipo: 90,
  status: 110,
  rodada: 76,
  inicio: 142,
  fim: 142,
  acao: 120,
};

const LARGURAS_MINIMAS_TABELA_INVENTARIO: Record<
  ColunaTabelaInventario,
  number
> = {
  id: 55,
  codigo: 95,
  cliente: 140,
  armazem: 75,
  tipo: 70,
  status: 90,
  rodada: 65,
  inicio: 115,
  fim: 115,
  acao: 90,
};

const LARGURAS_MAXIMAS_TABELA_INVENTARIO: Record<
  ColunaTabelaInventario,
  number
> = {
  id: 150,
  codigo: 260,
  cliente: 600,
  armazem: 220,
  tipo: 180,
  status: 220,
  rodada: 160,
  inicio: 260,
  fim: 260,
  acao: 240,
};

const inputClass =
  "h-10 w-full min-w-0 rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-slate-500";
const buttonClass =
  "h-10 rounded-md border border-slate-300 bg-white px-4 text-sm font-medium hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50";
const primaryButtonClass =
  "h-10 rounded-md bg-slate-900 px-4 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50";

function HistoricoPage() {
  const navigate = useNavigate();
  const pesquisa = Route.useSearch();

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

  const podeVisualizarHistorico =
    permissoesUsuario.has("ANALISE_VISUALIZAR");
  const podeVisualizarTratativas =
    permissoesUsuario.has("PLANO_ACAO_VISUALIZAR");

  const idInventarioContexto =
    podeVisualizarHistorico
      ? pesquisa.inventario
      : undefined;

  const abaInicial = pesquisa.aba;

  const tratativaInventario =
    pesquisa.aba === "tratativas"
      ? pesquisa.tratativa_inventario
      : undefined;

  const ocorrenciaTratativa =
    pesquisa.aba === "tratativas"
      ? pesquisa.ocorrencia
      : undefined;

  const abaGlobalPadrao: AbaGlobalSearch | null =
    podeVisualizarHistorico
      ? "inventarios"
      : podeVisualizarTratativas
        ? "tratativas"
        : null;

  const abaInicialGlobalPermitida =
    abaInicial &&
    ABAS_GLOBAIS_VALIDAS.has(
      abaInicial as AbaGlobalSearch,
    ) &&
    (abaInicial === "tratativas"
      ? podeVisualizarTratativas
      : podeVisualizarHistorico)
      ? (abaInicial as AbaGlobalSearch)
      : undefined;

  const [inventarioContexto, setInventarioContexto] =
    useState<
      Awaited<
        ReturnType<
          typeof consultarInventarioDetalhe
        >
      > | null
    >(null);

  const [carregandoInventarioContexto, setCarregandoInventarioContexto] =
    useState(false);

  const [aba, setAba] =
    useState<Aba>(
      idInventarioContexto
        ? abaInicial &&
          ABAS_CONTEXTUAIS_VALIDAS.has(
            abaInicial as AbaContextualSearch,
          )
          ? (abaInicial as AbaContextualSearch)
          : "visao-geral"
        : abaInicialGlobalPermitida ??
          abaGlobalPadrao ??
          "inventarios",
    );

  const abasGlobaisVisiveis =
    ABAS_GLOBAIS.filter(([id]) =>
      id === "tratativas"
        ? podeVisualizarTratativas
        : podeVisualizarHistorico,
    );

  const [clientes, setClientes] =
    useState<ClienteDisponivelInventario[]>([]);

  const [
    carregandoClientes,
    setCarregandoClientes,
  ] = useState(true);
  const [clienteId, setClienteId] = useState("53");
  const [armazem, setArmazem] = useState("ML007");
  const [codigo, setCodigo] = useState("71256360");
  const [lote, setLote] = useState("");
  const [localizacao, setLocalizacao] = useState("01PLAQUETA");
  const [tipo, setTipo] = useState("");
  const [status, setStatus] = useState("");
  const [codigoInventario, setCodigoInventario] = useState("");
  const [dataInicio, setDataInicio] = useState("");
  const [dataFim, setDataFim] = useState("");
  const [somenteRecorrentes, setSomenteRecorrentes] = useState(true);
  const [page, setPage] = useState(1);
  const [itemPage, setItemPage] = useState(1);
  const [localizacaoPage, setLocalizacaoPage] = useState(1);

  const [
    campoOrdenacaoInventario,
    setCampoOrdenacaoInventario,
  ] = useState<CampoOrdenacaoInventario | null>(
    null,
  );

  const [
    direcaoOrdenacaoInventario,
    setDirecaoOrdenacaoInventario,
  ] = useState<DirecaoOrdenacaoInventario>(
    "asc",
  );

  const [
    largurasTabelaInventario,
    setLargurasTabelaInventario,
  ] = useState<
    Record<ColunaTabelaInventario, number>
  >({
    ...LARGURAS_PADRAO_TABELA_INVENTARIO,
  });


  const [inventarios, setInventarios] = useState<HistoricoInventariosResponse | null>(null);
  const [itens, setItens] = useState<HistoricoItemInventario[]>([]);
  const [itemResponse, setItemResponse] = useState<Awaited<ReturnType<typeof buscarHistoricoItem>> | null>(null);
  const [localizacoes, setLocalizacoes] = useState<HistoricoLocalizacaoResponse | null>(null);
  const [divergencias, setDivergencias] = useState<HistoricoDivergenciasResponse | null>(null);

  const [
    rodadasContexto,
    setRodadasContexto,
  ] = useState<
    Awaited<
      ReturnType<typeof buscarRodadasInventario>
    > | null
  >(null);

  const [
    carregandoRodadasContexto,
    setCarregandoRodadasContexto,
  ] = useState(false);

  const [
    erroRodadasContexto,
    setErroRodadasContexto,
  ] = useState<string | null>(null);

  const [
    resultadoFinalContexto,
    setResultadoFinalContexto,
  ] =
    useState<ResultadoFinalIndicadores | null>(
      null,
    );

  const [
    carregandoResultadoFinalContexto,
    setCarregandoResultadoFinalContexto,
  ] = useState(false);

  const [
    erroResultadoFinalContexto,
    setErroResultadoFinalContexto,
  ] = useState<string | null>(null);

  const [
    analiseFinanceiraOficialContexto,
    setAnaliseFinanceiraOficialContexto,
  ] = useState<AnaliseFinanceiraOficial | null>(
    null,
  );

  const [
    carregandoAnaliseFinanceiraOficialContexto,
    setCarregandoAnaliseFinanceiraOficialContexto,
  ] = useState(false);

  const [
    erroAnaliseFinanceiraOficialContexto,
    setErroAnaliseFinanceiraOficialContexto,
  ] = useState<string | null>(null);

  const [
    auditoriaContexto,
    setAuditoriaContexto,
  ] = useState<AuditoriaResponse | null>(
    null,
  );

  const [
    carregandoEventosContexto,
    setCarregandoEventosContexto,
  ] = useState(false);

  const [
    erroEventosContexto,
    setErroEventosContexto,
  ] = useState<string | null>(null);

  const [
    paginaEventosContexto,
    setPaginaEventosContexto,
  ] = useState(1);

  const [
    itensContextoHistorico,
    setItensContextoHistorico,
  ] = useState<ItemHistoricoContexto[]>([]);

  const [
    carregandoItensContexto,
    setCarregandoItensContexto,
  ] = useState(false);

  const [
    erroItensContexto,
    setErroItensContexto,
  ] = useState<string | null>(null);

  const [
    localizacoesContextoHistorico,
    setLocalizacoesContextoHistorico,
  ] = useState<AcompanhamentoLocalizacoes | null>(
    null,
  );

  const [
    carregandoLocalizacoesContexto,
    setCarregandoLocalizacoesContexto,
  ] = useState(false);

  const [
    erroLocalizacoesContexto,
    setErroLocalizacoesContexto,
  ] = useState<string | null>(null);

  const [
    rodadaLocalizacoesContexto,
    setRodadaLocalizacoesContexto,
  ] = useState<number | null>(null);

  const [
    divergenciasContextoHistorico,
    setDivergenciasContextoHistorico,
  ] = useState<DivergenciaHistoricoContexto[]>([]);

  const [
    carregandoDivergenciasContexto,
    setCarregandoDivergenciasContexto,
  ] = useState(false);

  const [
    erroDivergenciasContexto,
    setErroDivergenciasContexto,
  ] = useState<string | null>(null);

  const [
    rodadaDivergenciasContexto,
    setRodadaDivergenciasContexto,
  ] = useState<number | null>(null);

  const [
    decisoesContextoHistorico,
    setDecisoesContextoHistorico,
  ] = useState<DecisaoHistoricoContexto[]>([]);

  const [
    carregandoDecisoesContexto,
    setCarregandoDecisoesContexto,
  ] = useState(false);

  const [
    erroDecisoesContexto,
    setErroDecisoesContexto,
  ] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const [exportandoExcel, setExportandoExcel] =
    useState(false);

  const [erroExportacaoExcel, setErroExportacaoExcel] =
    useState<string | null>(null);

  useEffect(() => {
    if (!idInventarioContexto) {
      setRodadasContexto(null);
      setErroRodadasContexto(null);
      setCarregandoRodadasContexto(false);
      return;
    }

    let ativo = true;

    setCarregandoRodadasContexto(true);
    setErroRodadasContexto(null);

    void buscarRodadasInventario(
      idInventarioContexto,
    )
      .then((dados) => {
        if (!ativo) {
          return;
        }

        setRodadasContexto(dados);
      })
      .catch((erro) => {
        if (!ativo) {
          return;
        }

        setRodadasContexto(null);
        setErroRodadasContexto(
          erro instanceof Error
            ? erro.message
            : "Erro ao carregar as rodadas do inventário.",
        );
      })
      .finally(() => {
        if (ativo) {
          setCarregandoRodadasContexto(false);
        }
      });

    return () => {
      ativo = false;
    };
  }, [idInventarioContexto]);

  useEffect(() => {
    if (!idInventarioContexto) {
      setResultadoFinalContexto(null);
      setErroResultadoFinalContexto(null);
      setCarregandoResultadoFinalContexto(false);
      return;
    }

    const statusInventario = String(
      inventarioContexto?.status ?? "",
    )
      .trim()
      .toUpperCase();

    if (!statusInventario) {
      return;
    }

    if (statusInventario !== "FINALIZADO") {
      setResultadoFinalContexto(null);
      setErroResultadoFinalContexto(null);
      setCarregandoResultadoFinalContexto(false);
      return;
    }

    let ativo = true;

    setCarregandoResultadoFinalContexto(true);
    setErroResultadoFinalContexto(null);
    setResultadoFinalContexto(null);

    void buscarResultadoFinalIndicadores(
      idInventarioContexto,
    )
      .then((dados) => {
        if (!ativo) {
          return;
        }

        setResultadoFinalContexto(dados);
      })
      .catch((erro: unknown) => {
        if (!ativo) {
          return;
        }

        setResultadoFinalContexto(null);

        setErroResultadoFinalContexto(
          erro instanceof Error
            ? erro.message
            : "Nao foi possivel carregar o resultado final.",
        );
      })
      .finally(() => {
        if (ativo) {
          setCarregandoResultadoFinalContexto(
            false,
          );
        }
      });

    return () => {
      ativo = false;
    };
  }, [
    idInventarioContexto,
    inventarioContexto?.status,
  ]);

  useEffect(() => {
    const tipoInventario = String(
      inventarioContexto?.tipo ?? "",
    )
      .trim()
      .toUpperCase();

    const statusInventario = String(
      inventarioContexto?.status ?? "",
    )
      .trim()
      .toUpperCase();

    if (
      !idInventarioContexto ||
      aba !== "indicadores" ||
      tipoInventario !== "OFICIAL" ||
      statusInventario !== "FINALIZADO"
    ) {
      setAnaliseFinanceiraOficialContexto(null);
      setErroAnaliseFinanceiraOficialContexto(null);
      setCarregandoAnaliseFinanceiraOficialContexto(
        false,
      );
      return;
    }

    let ativo = true;

    setCarregandoAnaliseFinanceiraOficialContexto(
      true,
    );
    setErroAnaliseFinanceiraOficialContexto(null);
    setAnaliseFinanceiraOficialContexto(null);

    void buscarAnaliseFinanceiraOficial(
      idInventarioContexto,
    )
      .then((dados) => {
        if (!ativo) {
          return;
        }

        setAnaliseFinanceiraOficialContexto(
          dados,
        );
      })
      .catch((erro: unknown) => {
        if (!ativo) {
          return;
        }

        setAnaliseFinanceiraOficialContexto(null);
        setErroAnaliseFinanceiraOficialContexto(
          erro instanceof Error
            ? erro.message
            : "Nao foi possivel carregar os indicadores financeiros do inventario oficial.",
        );
      })
      .finally(() => {
        if (ativo) {
          setCarregandoAnaliseFinanceiraOficialContexto(
            false,
          );
        }
      });

    return () => {
      ativo = false;
    };
  }, [
    idInventarioContexto,
    aba,
    inventarioContexto?.tipo,
    inventarioContexto?.status,
  ]);

  useEffect(() => {
    setPaginaEventosContexto(1);
    setAuditoriaContexto(null);
    setErroEventosContexto(null);
  }, [idInventarioContexto]);

  useEffect(() => {
    if (
      !idInventarioContexto ||
      aba !== "eventos"
    ) {
      return;
    }

    const controller =
      new AbortController();

    setCarregandoEventosContexto(true);
    setErroEventosContexto(null);

    void buscarAuditoriaInventario(
      idInventarioContexto,
      paginaEventosContexto,
      20,
      controller.signal,
    )
      .then((dados) => {
        if (controller.signal.aborted) {
          return;
        }

        setAuditoriaContexto(dados);
      })
      .catch((erro: unknown) => {
        if (controller.signal.aborted) {
          return;
        }

        setAuditoriaContexto(null);

        setErroEventosContexto(
          erro instanceof Error
            ? erro.message
            : "Nao foi possivel carregar os eventos do inventario.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setCarregandoEventosContexto(
            false,
          );
        }
      });

    return () => {
      controller.abort();
    };
  }, [
    idInventarioContexto,
    aba,
    paginaEventosContexto,
  ]);

  useEffect(() => {
    if (
      !idInventarioContexto ||
      ![
        "visao-geral",
        "itens-contexto",
      ].includes(aba)
    ) {
      return;
    }

    /*
     * O ID ja foi validado acima.
     * Mantemos uma referencia local number para que
     * o TypeScript preserve o narrowing dentro da
     * funcao assincrona abaixo.
     */
    const idInventario =
      idInventarioContexto;

    const tipoInventario = String(
      inventarioContexto?.tipo ?? "",
    )
      .trim()
      .toUpperCase();

    if (!tipoInventario) {
      return;
    }

    let ativo = true;

    setCarregandoItensContexto(true);
    setErroItensContexto(null);
    setItensContextoHistorico([]);

    async function carregarItensContexto() {
      try {
        if (tipoInventario === "ROTATIVO") {
          const dados =
            await buscarAnaliseRotativo(
              idInventario,
            );

          if (!ativo) {
            return;
          }

          const itens =
            dados.itens.map(
              (item): ItemHistoricoContexto => ({
                chave:
                  String(
                    item.chave ??
                      `${item.codigo}|${item.lote ?? ""}`,
                  ),
                localizacao:
                  item.localizacao || "-",
                codigo:
                  item.codigo,
                lote:
                  item.lote || "-",
                descricao:
                  item.produto ??
                  "Produto sem descricao",
                qtd_estoque:
                  Number(
                    item.qtd_estoque ?? 0,
                  ),
                qtd_contada:
                  Number(
                    item.qtd_contada ?? 0,
                  ),
                diferenca:
                  Number(
                    item.diferenca ?? 0,
                  ),
                status:
                  item.status || "-",
              }),
            );

          setItensContextoHistorico(
            itens,
          );

          return;
        }

        if (tipoInventario === "OFICIAL") {
          const rodada =
            await buscarRodadaAtualOficial(
              idInventario,
            );

          const dados =
            await buscarAnaliseOficial(
              idInventario,
              rodada.id_rodada,
            );

          if (!ativo) {
            return;
          }

          const itens =
            dados.itens.map(
              (item): ItemHistoricoContexto => ({
                chave:
                  String(
                    item.chave ??
                      `${item.codigo}|${item.lote ?? ""}`,
                  ),
                localizacao:
                  (
                    item.localizacoes_bipadas ??
                    []
                  )
                    .map(
                      (localizacao) =>
                        localizacao.localizacao,
                    )
                    .join(", ") || "-",
                codigo:
                  item.codigo,
                lote:
                  item.lote || "-",
                descricao:
                  item.descricao ??
                  "Produto sem descricao",
                qtd_estoque:
                  Number(
                    item.qtd_estoque ?? 0,
                  ),
                qtd_contada:
                  Number(
                    item.qtd_contada ?? 0,
                  ),
                diferenca:
                  Number(
                    item.diferenca ?? 0,
                  ),
                status:
                  item.status || "-",
              }),
            );

          setItensContextoHistorico(
            itens,
          );

          return;
        }

        throw new Error(
          "Tipo de inventario nao suportado.",
        );
      } catch (erro: unknown) {
        if (!ativo) {
          return;
        }

        setItensContextoHistorico([]);

        setErroItensContexto(
          erro instanceof Error
            ? erro.message
            : "Nao foi possivel carregar os itens do inventario.",
        );
      } finally {
        if (ativo) {
          setCarregandoItensContexto(false);
        }
      }
    }

    void carregarItensContexto();

    return () => {
      ativo = false;
    };
  }, [
    idInventarioContexto,
    aba,
    inventarioContexto?.tipo,
  ]);

  useEffect(() => {
    setRodadaLocalizacoesContexto(null);
    setLocalizacoesContextoHistorico(null);
    setErroLocalizacoesContexto(null);
    setCarregandoLocalizacoesContexto(false);
  }, [idInventarioContexto]);

  useEffect(() => {
    if (
      !idInventarioContexto ||
      !rodadasContexto ||
      rodadasContexto.rodadas.length === 0
    ) {
      return;
    }

    const numerosRodadas =
      rodadasContexto.rodadas.map(
        (rodada) =>
          rodada.numero_rodada,
      );

    const rodadaAtualValida =
      numerosRodadas.includes(
        rodadasContexto.rodada_atual,
      );

    const rodadaPreferidaLocalizacoes =
      rodadaAtualValida
        ? rodadasContexto.rodada_atual
        : Math.max(...numerosRodadas);

    setRodadaLocalizacoesContexto(
      (rodadaAtual) =>
        rodadaAtual !== null &&
        numerosRodadas.includes(rodadaAtual)
          ? rodadaAtual
          : rodadaPreferidaLocalizacoes,
    );
  }, [
    idInventarioContexto,
    rodadasContexto,
  ]);

  useEffect(() => {
    if (
      !idInventarioContexto ||
      ![
        "visao-geral",
        "localizacoes-contexto",
      ].includes(aba) ||
      rodadaLocalizacoesContexto === null
    ) {
      return;
    }

    const idInventario =
      idInventarioContexto;

    const numeroRodada =
      rodadaLocalizacoesContexto;

    let ativo = true;

    setCarregandoLocalizacoesContexto(true);
    setErroLocalizacoesContexto(null);
    setLocalizacoesContextoHistorico(null);

    void buscarAcompanhamentoLocalizacoes(
      idInventario,
      numeroRodada,
    )
      .then((dados) => {
        if (!ativo) {
          return;
        }

        setLocalizacoesContextoHistorico(
          dados,
        );
      })
      .catch((erro: unknown) => {
        if (!ativo) {
          return;
        }

        setLocalizacoesContextoHistorico(
          null,
        );

        setErroLocalizacoesContexto(
          erro instanceof Error
            ? erro.message
            : "Nao foi possivel carregar as localizacoes do inventario.",
        );
      })
      .finally(() => {
        if (ativo) {
          setCarregandoLocalizacoesContexto(
            false,
          );
        }
      });

    return () => {
      ativo = false;
    };
  }, [
    idInventarioContexto,
    aba,
    rodadaLocalizacoesContexto,
  ]);

  useEffect(() => {
    setDivergenciasContextoHistorico([]);
    setErroDivergenciasContexto(null);
    setRodadaDivergenciasContexto(null);
    setCarregandoDivergenciasContexto(false);
  }, [idInventarioContexto]);

  useEffect(() => {
    const tipoInventario = String(
      inventarioContexto?.tipo ?? "",
    )
      .trim()
      .toUpperCase();

    if (tipoInventario !== "OFICIAL") {
      setRodadaDivergenciasContexto(null);
      return;
    }

    if (
      !rodadasContexto ||
      rodadasContexto.rodadas.length === 0
    ) {
      return;
    }

    const numerosRodadas =
      rodadasContexto.rodadas.map(
        (rodada) =>
          rodada.numero_rodada,
      );

    const rodadaAtualValida =
      numerosRodadas.includes(
        rodadasContexto.rodada_atual,
      );

    const rodadaPreferidaDivergencias =
      rodadaAtualValida
        ? rodadasContexto.rodada_atual
        : Math.max(...numerosRodadas);

    setRodadaDivergenciasContexto(
      (rodadaAtual) =>
        rodadaAtual !== null &&
        numerosRodadas.includes(rodadaAtual)
          ? rodadaAtual
          : rodadaPreferidaDivergencias,
    );
  }, [
    inventarioContexto?.tipo,
    rodadasContexto,
  ]);

  useEffect(() => {
    if (
      !idInventarioContexto ||
      ![
        "visao-geral",
        "divergencias-contexto",
      ].includes(aba)
    ) {
      return;
    }

    const idInventario =
      idInventarioContexto;

    const tipoInventario = String(
      inventarioContexto?.tipo ?? "",
    )
      .trim()
      .toUpperCase();

    if (!tipoInventario) {
      return;
    }

    if (
      tipoInventario === "OFICIAL" &&
      rodadaDivergenciasContexto === null
    ) {
      return;
    }

    let ativo = true;

    setCarregandoDivergenciasContexto(true);
    setErroDivergenciasContexto(null);
    setDivergenciasContextoHistorico([]);

    async function carregarDivergencias() {
      try {
        if (tipoInventario === "ROTATIVO") {
          const dados =
            await buscarAnaliseRotativo(
              idInventario,
            );

          if (!ativo) {
            return;
          }

          const divergencias =
            dados.itens
              .filter(
                (item) =>
                  Math.abs(
                    Number(
                      item.diferenca ?? 0,
                    ),
                  ) > 0.000001,
              )
              .map(
                (
                  item,
                ): DivergenciaHistoricoContexto => ({
                  chave:
                    String(
                      item.chave ??
                        `${item.codigo}|${item.lote ?? ""}|${item.localizacao}`,
                    ),
                  rodada:
                    dados.numero_rodada ??
                    null,
                  localizacao:
                    item.localizacao || "-",
                  codigo:
                    item.codigo,
                  lote:
                    item.lote || "-",
                  descricao:
                    item.produto ??
                    "Produto sem descricao",
                  qtd_estoque:
                    Number(
                      item.qtd_estoque ?? 0,
                    ),
                  qtd_contada:
                    Number(
                      item.qtd_contada ?? 0,
                    ),
                  diferenca:
                    Number(
                      item.diferenca ?? 0,
                    ),
                  status:
                    item.status || "-",
                  resultado_definitivo:
                    null,
                  pendente_recontagem:
                    Boolean(
                      item.pendente_recontagem,
                    ),
                  pendente_decisao:
                    Boolean(
                      item.requer_decisao &&
                      item.pendente_decisao,
                    ),
                  detalhe:
                    null,
                }),
              );

          setDivergenciasContextoHistorico(
            divergencias,
          );

          return;
        }

        if (tipoInventario === "OFICIAL") {
          if (
            rodadaDivergenciasContexto === null ||
            !rodadasContexto
          ) {
            return;
          }

          const rodadaSelecionada =
            rodadasContexto.rodadas.find(
              (rodada) =>
                rodada.numero_rodada ===
                rodadaDivergenciasContexto,
            );

          if (!rodadaSelecionada) {
            throw new Error(
              "Rodada selecionada nao encontrada.",
            );
          }

          const dados =
            await buscarAnaliseOficial(
              idInventario,
              rodadaSelecionada.id_rodada,
            );

          if (!ativo) {
            return;
          }

          const divergencias =
            dados.itens
              .filter(
                (item) =>
                  Math.abs(
                    Number(
                      item.diferenca ?? 0,
                    ),
                  ) > 0.000001,
              )
              .map(
                (
                  item,
                ): DivergenciaHistoricoContexto => ({
                  chave:
                    String(
                      item.chave ??
                        `${item.codigo}|${item.lote ?? ""}`,
                    ),
                  rodada:
                    dados.numero_rodada ??
                    rodadaSelecionada.numero_rodada,
                  localizacao:
                    (
                      item.localizacoes_bipadas ??
                      []
                    )
                      .map(
                        (localizacao) =>
                          localizacao.localizacao,
                      )
                      .join(", ") || "-",
                  codigo:
                    item.codigo,
                  lote:
                    item.lote || "-",
                  descricao:
                    item.descricao ??
                    "Produto sem descricao",
                  qtd_estoque:
                    Number(
                      item.qtd_estoque ?? 0,
                    ),
                  qtd_contada:
                    Number(
                      item.qtd_contada ?? 0,
                    ),
                  diferenca:
                    Number(
                      item.diferenca ?? 0,
                    ),
                  status:
                    item.status || "-",
                  resultado_definitivo:
                    Boolean(
                      item.resultado_definitivo,
                    ),
                  pendente_recontagem:
                    null,
                  pendente_decisao:
                    null,
                  detalhe:
                    item.detalhe ?? null,
                }),
              );

          setDivergenciasContextoHistorico(
            divergencias,
          );

          return;
        }

        throw new Error(
          "Tipo de inventario nao suportado.",
        );
      } catch (erro: unknown) {
        if (!ativo) {
          return;
        }

        setDivergenciasContextoHistorico([]);

        setErroDivergenciasContexto(
          erro instanceof Error
            ? erro.message
            : "Nao foi possivel carregar as divergencias.",
        );
      } finally {
        if (ativo) {
          setCarregandoDivergenciasContexto(
            false,
          );
        }
      }
    }

    void carregarDivergencias();

    return () => {
      ativo = false;
    };
  }, [
    idInventarioContexto,
    aba,
    inventarioContexto?.tipo,
    rodadaDivergenciasContexto,
    rodadasContexto,
  ]);

  useEffect(() => {
    setDecisoesContextoHistorico([]);
    setErroDecisoesContexto(null);
    setCarregandoDecisoesContexto(false);
  }, [idInventarioContexto]);

  useEffect(() => {
    if (
      !idInventarioContexto ||
      ![
        "visao-geral",
        "decisoes",
      ].includes(aba)
    ) {
      return;
    }

    const idInventario =
      idInventarioContexto;

    const tipoInventario = String(
      inventarioContexto?.tipo ?? "",
    )
      .trim()
      .toUpperCase();

    if (!tipoInventario) {
      return;
    }

    let ativo = true;

    setCarregandoDecisoesContexto(true);
    setErroDecisoesContexto(null);
    setDecisoesContextoHistorico([]);

    async function carregarDecisoes() {
      try {
        if (tipoInventario === "ROTATIVO") {
          const dados =
            await buscarAnaliseRotativo(
              idInventario,
            );

          if (!ativo) {
            return;
          }

          const decisoes =
            dados.itens
              .filter(
                (item) =>
                  item.requer_decisao ||
                  item.decisao_rotativo
                    .possui_decisao ||
                  item.pendente_recontagem ||
                  item.divergencia_justificada,
              )
              .map(
                (
                  item,
                ): DecisaoHistoricoContexto => {
                  let status =
                    item.status || "-";

                  if (item.pendente_decisao) {
                    status =
                      "AGUARDANDO_DECISAO";
                  } else if (
                    item.pendente_recontagem
                  ) {
                    status = "RECONTAGEM";
                  } else if (
                    item.divergencia_justificada
                  ) {
                    status = "JUSTIFICADA";
                  } else if (item.resolvido) {
                    status = "RESOLVIDO";
                  }

                  return {
                    chave:
                      String(
                        item.chave ??
                          `${item.codigo}|${item.lote ?? ""}|${item.localizacao}`,
                      ),
                    rodada:
                      dados.numero_rodada ??
                      null,
                    localizacao:
                      item.localizacao ||
                      "-",
                    codigo:
                      item.codigo,
                    lote:
                      item.lote || "-",
                    descricao:
                      item.produto ??
                      "Produto sem descricao",
                    possui_decisao:
                      Boolean(
                        item.decisao_rotativo
                          .possui_decisao,
                      ),
                    decisao:
                      item.decisao_rotativo
                        .decisao ??
                      null,
                    quantidade_aprovada:
                      null,
                    justificativa:
                      item.decisao_rotativo
                        .justificativa ??
                      null,
                    usuario:
                      item.decisao_rotativo
                        .usuario ??
                      null,
                    data_hora:
                      item.decisao_rotativo
                        .data_hora ??
                      null,
                    status,
                    pendente:
                      Boolean(
                        item.requer_decisao &&
                        item.pendente_decisao,
                      ),
                    recontagem:
                      Boolean(
                        item.pendente_recontagem ||
                        item.decisao_rotativo
                          .decisao ===
                          "RECONTAR",
                      ),
                    resolvido:
                      Boolean(
                        item.resolvido,
                      ),
                  };
                },
              );

          setDecisoesContextoHistorico(
            decisoes,
          );

          return;
        }

        if (tipoInventario === "OFICIAL") {
          const dados =
            await buscarAnaliseGestor(
              idInventario,
            );

          if (!ativo) {
            return;
          }

          const decisoes =
            dados.itens
              .filter(
                (item) =>
                  item.requer_decisao_gestor ||
                  item.decisao_gestor
                    .possui_decisao ||
                  item.nova_recontagem,
              )
              .map(
                (
                  item,
                ): DecisaoHistoricoContexto => ({
                  chave:
                    String(
                      item.chave ??
                        `${item.codigo}|${item.lote ?? ""}`,
                    ),
                  rodada:
                    item.ultima_rodada_participada ??
                    null,
                  localizacao:
                    (
                      item.localizacoes_snapshot ??
                      []
                    )
                      .map(
                        (localizacao) =>
                          localizacao.localizacao,
                      )
                      .join(", ") || "-",
                  codigo:
                    item.codigo,
                  lote:
                    item.lote || "-",
                  descricao:
                    item.descricao ??
                    "Produto sem descricao",
                  possui_decisao:
                    Boolean(
                      item.decisao_gestor
                        .possui_decisao,
                    ),
                  decisao:
                    item.decisao_gestor
                      .decisao ??
                    null,
                  quantidade_aprovada:
                    item.decisao_gestor
                      .quantidade_aprovada ??
                    null,
                  justificativa:
                    item.decisao_gestor
                      .justificativa ??
                    null,
                  usuario:
                    item.decisao_gestor
                      .usuario ??
                    null,
                  data_hora:
                    item.decisao_gestor
                      .data_hora ??
                    null,
                  status:
                    item.decisao_gestor
                      .status ??
                    item.situacao_gerencial ??
                    item.situacao_atual ??
                    "-",
                  pendente:
                    Boolean(
                      item.pendente_decisao_gestor,
                    ),
                  recontagem:
                    Boolean(
                      item.nova_recontagem ||
                      item.decisao_gestor
                        .decisao ===
                        "NOVA_RECONTAGEM",
                    ),
                  resolvido:
                    Boolean(
                      item.resolvido_gestor,
                    ),
                }),
              );

          setDecisoesContextoHistorico(
            decisoes,
          );

          return;
        }

        throw new Error(
          "Tipo de inventario nao suportado.",
        );
      } catch (erro: unknown) {
        if (!ativo) {
          return;
        }

        setDecisoesContextoHistorico([]);

        setErroDecisoesContexto(
          erro instanceof Error
            ? erro.message
            : "Nao foi possivel carregar as decisoes do inventario.",
        );
      } finally {
        if (ativo) {
          setCarregandoDecisoesContexto(
            false,
          );
        }
      }
    }

    void carregarDecisoes();

    return () => {
      ativo = false;
    };
  }, [
    idInventarioContexto,
    aba,
    inventarioContexto?.tipo,
  ]);

  useEffect(() => {
    if (idInventarioContexto) {
      const abaUrl =
        abaInicial &&
        ABAS_CONTEXTUAIS_VALIDAS.has(
          abaInicial as AbaContextualSearch,
        )
          ? (abaInicial as AbaContextualSearch)
          : "visao-geral";

      setAba(abaUrl);

      /*
       * Canonicaliza o primeiro acesso contextual:
       * /historico?inventario=1652
       * vira:
       * /historico?inventario=1652&aba=visao-geral
       */
      if (!abaInicial) {
        void navigate({
          to: "/historico",
          search: {
            inventario:
              idInventarioContexto,
            aba: "visao-geral",
          },
          replace: true,
        });
      }

      return;
    }

    if (!abaGlobalPadrao) {
      return;
    }

    const abaGlobalSolicitada =
      abaInicial &&
      ABAS_GLOBAIS_VALIDAS.has(
        abaInicial as AbaGlobalSearch,
      )
        ? (abaInicial as AbaGlobalSearch)
        : undefined;

    const solicitadaPermitida =
      abaGlobalSolicitada
        ? abaGlobalSolicitada === "tratativas"
          ? podeVisualizarTratativas
          : podeVisualizarHistorico
        : false;

    const abaDestino = solicitadaPermitida
      ? abaGlobalSolicitada!
      : abaGlobalPadrao;

    setAba(abaDestino);

    const precisaCanonicalizar =
      (abaGlobalSolicitada !== undefined &&
        abaGlobalSolicitada !== abaDestino) ||
      (pesquisa.inventario !== undefined &&
        !idInventarioContexto) ||
      (!podeVisualizarHistorico &&
        podeVisualizarTratativas &&
        abaInicial === undefined);

    if (precisaCanonicalizar) {
      void navigate({
        to: "/historico",
        search: {
          aba: abaDestino,
        },
        replace: true,
      });
    }
  }, [
    idInventarioContexto,
    abaInicial,
    abaGlobalPadrao,
    podeVisualizarHistorico,
    podeVisualizarTratativas,
    pesquisa.inventario,
    navigate,
  ]);

  const sincronizarAbaContextualUrl = (
    novaAba: Aba,
  ) => {
    if (idInventarioContexto) {
      if (
        !podeVisualizarHistorico ||
        !ABAS_CONTEXTUAIS_VALIDAS.has(
          novaAba as AbaContextualSearch,
        )
      ) {
        return;
      }

      setAba(novaAba);

      void navigate({
        to: "/historico",
        search: {
          inventario:
            idInventarioContexto,
          aba:
            novaAba as AbaContextualSearch,
        },
      });

      return;
    }

    if (
      !ABAS_GLOBAIS_VALIDAS.has(
        novaAba as AbaGlobalSearch,
      )
    ) {
      return;
    }

    const abaGlobal =
      novaAba as AbaGlobalSearch;

    if (
      (abaGlobal === "tratativas" &&
        !podeVisualizarTratativas) ||
      (abaGlobal !== "tratativas" &&
        !podeVisualizarHistorico)
    ) {
      return;
    }

    setAba(abaGlobal);

    void navigate({
      to: "/historico",
      search: {
        aba: abaGlobal,
      },
    });
  };

  const atualizarContextoTratativas = (
    contexto: TratativasContexto,
  ) => {
    if (!podeVisualizarTratativas) {
      return;
    }

    void navigate({
      to: "/historico",
      search: {
        aba: "tratativas",
        ...(contexto.inventario !== undefined
          ? {
              tratativa_inventario:
                contexto.inventario,
            }
          : {}),
        ...(contexto.ocorrencia !== undefined
          ? { ocorrencia: contexto.ocorrencia }
          : {}),
      },
      replace: true,
    });
  };

  const cliente = Number(clienteId);

  const inventariosOrdenadosPagina =
    useMemo(() => {
      const lista = [
        ...(inventarios?.inventarios ?? []),
      ];

      if (!campoOrdenacaoInventario) {
        return lista;
      }

      lista.sort((itemA, itemB) => {
        let valorA:
          | string
          | number
          | null
          | undefined;

        let valorB:
          | string
          | number
          | null
          | undefined;

        switch (campoOrdenacaoInventario) {
          case "id":
            valorA = itemA.id_inventario;
            valorB = itemB.id_inventario;
            break;

          case "codigo":
            valorA = itemA.codigo_inventario;
            valorB = itemB.codigo_inventario;
            break;

          case "cliente":
            valorA = itemA.cliente;
            valorB = itemB.cliente;
            break;

          case "armazem":
            valorA = itemA.armazem;
            valorB = itemB.armazem;
            break;

          case "tipo":
            valorA = itemA.tipo;
            valorB = itemB.tipo;
            break;

          case "status":
            valorA = itemA.status;
            valorB = itemB.status;
            break;

          case "rodada":
            valorA = itemA.rodada_atual;
            valorB = itemB.rodada_atual;
            break;

          case "inicio":
            valorA = itemA.data_hora_inicio
              ? new Date(
                  itemA.data_hora_inicio,
                ).getTime()
              : null;

            valorB = itemB.data_hora_inicio
              ? new Date(
                  itemB.data_hora_inicio,
                ).getTime()
              : null;
            break;

          case "fim":
            valorA = itemA.data_hora_fim
              ? new Date(
                  itemA.data_hora_fim,
                ).getTime()
              : null;

            valorB = itemB.data_hora_fim
              ? new Date(
                  itemB.data_hora_fim,
                ).getTime()
              : null;
            break;
        }

        const vazioA =
          valorA === null ||
          valorA === undefined ||
          valorA === "";

        const vazioB =
          valorB === null ||
          valorB === undefined ||
          valorB === "";

        if (vazioA && vazioB) {
          return 0;
        }

        /*
         * Valores vazios permanecem no final,
         * independentemente da direcao.
         */
        if (vazioA) {
          return 1;
        }

        if (vazioB) {
          return -1;
        }

        let comparacao = 0;

        if (
          typeof valorA === "number" &&
          typeof valorB === "number"
        ) {
          comparacao =
            valorA === valorB
              ? 0
              : valorA > valorB
                ? 1
                : -1;
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

        return direcaoOrdenacaoInventario ===
          "asc"
          ? comparacao
          : -comparacao;
      });

      return lista;
    }, [
      inventarios,
      campoOrdenacaoInventario,
      direcaoOrdenacaoInventario,
    ]);

  const larguraTotalTabelaInventario =
    Object.values(
      largurasTabelaInventario,
    ).reduce(
      (total, largura) =>
        total + largura,
      0,
    ) -
    (idInventarioContexto
      ? largurasTabelaInventario.acao
      : 0);


  async function carregarInventarios(pagina = page) {
    setLoading(true);
    setErro(null);

    try {
      if (
        idInventarioContexto &&
        inventarioContexto
      ) {
        const data =
          await buscarHistoricoInventarios({
            cliente_id:
              inventarioContexto.cliente_id,
            codigo_inventario:
              inventarioContexto.codigo_inventario,
            page: 1,
            page_size: 20,
          });

        const registrosContexto =
          data.inventarios.filter(
            (item) =>
              item.id_inventario ===
              idInventarioContexto,
          );

        setInventarios({
          ...data,
          inventarios:
            registrosContexto,
          paginacao: {
            ...data.paginacao,
            page: 1,
            total_registros:
              registrosContexto.length,
            total_paginas: 1,
            possui_proxima_pagina: false,
            possui_pagina_anterior: false,
          },
        });

        setPage(1);
        return;
      }

      const data =
        await buscarHistoricoInventarios({
          cliente_id: cliente,
          page: pagina,
          page_size: 20,
          ...(tipo
            ? { tipo }
            : {}),
          ...(status
            ? { status }
            : {}),
          ...(dataInicio
            ? { data_inicio: dataInicio }
            : {}),
          ...(dataFim
            ? { data_fim: dataFim }
            : {}),
          ...(codigoInventario
            ? {
                codigo_inventario:
                  codigoInventario,
              }
            : {}),
        });
      setInventarios(data);
      setPage(pagina);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar histórico de inventários.");
    } finally {
      setLoading(false);
    }
  }

  async function carregarItem(pagina = itemPage) {
    if (!codigo.trim()) return;
    setLoading(true);
    setErro(null);
    try {
      const data =
        await buscarHistoricoItem({
          cliente_id: cliente,
          codigo: codigo.trim(),
          page: pagina,
          page_size: 20,
          ...(lote.trim()
            ? { lote: lote.trim() }
            : {}),
        });
      const lista = data.inventarios ?? data.historico ?? data.resultados ?? [];
      setItens(lista);
      setItemResponse(data);
      setItemPage(pagina);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar histórico do item.");
    } finally {
      setLoading(false);
    }
  }

  async function carregarLocalizacao(pagina = localizacaoPage) {
    if (!localizacao.trim()) return;
    setLoading(true);
    setErro(null);
    try {
      const data =
        await buscarHistoricoLocalizacao({
          cliente_id: cliente,
          localizacao: localizacao.trim(),
          page: pagina,
          page_size: 20,
          ...(tipo
            ? { tipo }
            : {}),
        });
      setLocalizacoes(data);
      setLocalizacaoPage(pagina);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar histórico da localização.");
    } finally {
      setLoading(false);
    }
  }

  async function carregarDivergencias() {
    setLoading(true);
    setErro(null);
    try {
      const data =
        await buscarHistoricoDivergencias({
          cliente_id: cliente,
          somente_recorrentes:
            somenteRecorrentes,
          ...(armazem.trim()
            ? { armazem: armazem.trim() }
            : {}),
          ...(localizacao.trim()
            ? {
                localizacao:
                  localizacao.trim(),
              }
            : {}),
          ...(codigo.trim()
            ? { codigo: codigo.trim() }
            : {}),
          ...(lote.trim()
            ? { lote: lote.trim() }
            : {}),
          ...(tipo
            ? { tipo_inventario: tipo }
            : {}),
          ...(dataInicio
            ? { data_inicio: dataInicio }
            : {}),
          ...(dataFim
            ? { data_fim: dataFim }
            : {}),
        });
      setDivergencias(data);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar histórico de divergências.");
    } finally {
      setLoading(false);
    }
  }

  function pesquisar() {
    if (aba === "inventarios") void carregarInventarios(1);
    if (aba === "item") void carregarItem(1);
    if (aba === "localizacao") void carregarLocalizacao(1);
    if (aba === "divergencias") void carregarDivergencias();
  }

  async function exportarExcel() {
    if (!idInventarioContexto || exportandoExcel) {
      return;
    }

    setExportandoExcel(true);
    setErroExportacaoExcel(null);

    try {
      await exportarAnaliseInventarioExcel(
        idInventarioContexto,
      );
    } catch (erro: unknown) {
      setErroExportacaoExcel(
        erro instanceof Error
          ? erro.message
          : "Não foi possível gerar o arquivo Excel.",
      );
    } finally {
      setExportandoExcel(false);
    }
  }


  function alternarOrdenacaoInventario(
    campo: CampoOrdenacaoInventario,
  ) {
    if (
      campoOrdenacaoInventario === campo
    ) {
      setDirecaoOrdenacaoInventario(
        (direcaoAtual) =>
          direcaoAtual === "asc"
            ? "desc"
            : "asc",
      );

      return;
    }

    setCampoOrdenacaoInventario(campo);
    setDirecaoOrdenacaoInventario("asc");
  }

  function indicadorOrdenacaoInventario(
    campo: CampoOrdenacaoInventario,
  ) {
    if (
      campoOrdenacaoInventario !== campo
    ) {
      return "\u2195";
    }

    return direcaoOrdenacaoInventario ===
      "asc"
      ? "\u2191"
      : "\u2193";
  }

  function iniciarRedimensionamentoColuna(
    coluna: ColunaTabelaInventario,
    evento: ReactMouseEvent<HTMLSpanElement>,
  ) {
    evento.preventDefault();
    evento.stopPropagation();

    const inicioX =
      evento.clientX;

    const larguraInicial =
      largurasTabelaInventario[coluna];

    const larguraMinima =
      LARGURAS_MINIMAS_TABELA_INVENTARIO[
        coluna
      ];

    const larguraMaxima =
      LARGURAS_MAXIMAS_TABELA_INVENTARIO[
        coluna
      ];

    const mover = (
      eventoMouse: MouseEvent,
    ) => {
      const deslocamento =
        eventoMouse.clientX - inicioX;

      const larguraNova = Math.min(
        larguraMaxima,
        Math.max(
          larguraMinima,
          larguraInicial + deslocamento,
        ),
      );

      setLargurasTabelaInventario(
        (largurasAtuais) => ({
          ...largurasAtuais,
          [coluna]: larguraNova,
        }),
      );
    };

    const finalizar = () => {
      window.removeEventListener(
        "mousemove",
        mover,
      );

      window.removeEventListener(
        "mouseup",
        finalizar,
      );

      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    document.body.style.cursor =
      "col-resize";

    document.body.style.userSelect =
      "none";

    window.addEventListener(
      "mousemove",
      mover,
    );

    window.addEventListener(
      "mouseup",
      finalizar,
    );
  }

  function restaurarLarguraColuna(
    coluna: ColunaTabelaInventario,
  ) {
    setLargurasTabelaInventario(
      (largurasAtuais) => ({
        ...largurasAtuais,
        [coluna]:
          LARGURAS_PADRAO_TABELA_INVENTARIO[
            coluna
          ],
      }),
    );
  }

  function renderCabecalhoInventario({
    titulo,
    coluna,
    ordenavel = true,
    alinhamento = "left",
  }: {
    titulo: ReactNode;
    coluna: ColunaTabelaInventario;
    ordenavel?: boolean;
    alinhamento?:
      | "left"
      | "center"
      | "right";
  }) {
    const largura =
      largurasTabelaInventario[coluna];

    const alinhamentoTexto =
      alinhamento === "center"
        ? "text-center"
        : alinhamento === "right"
          ? "text-right"
          : "text-left";

    const alinhamentoConteudo =
      alinhamento === "center"
        ? "justify-center"
        : alinhamento === "right"
          ? "justify-end"
          : "justify-start";

    return (
      <th
        style={{
          width: largura,
          minWidth: largura,
          maxWidth: largura,
        }}
        className={`relative whitespace-nowrap border-b border-slate-200 bg-slate-50 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500 ${alinhamentoTexto}`}
      >
        {ordenavel &&
        coluna !== "acao" ? (
          <button
            type="button"
            onClick={() =>
              alternarOrdenacaoInventario(
                coluna,
              )
            }
            className={`flex w-full items-center gap-1 px-2.5 transition hover:text-primary ${alinhamentoConteudo}`}
            title="Clique para classificar"
          >
            <span className="truncate">
              {titulo}
            </span>

            <span
              className={
                campoOrdenacaoInventario ===
                coluna
                  ? "text-primary"
                  : "text-slate-400"
              }
              aria-hidden="true"
            >
              {indicadorOrdenacaoInventario(
                coluna,
              )}
            </span>
          </button>
        ) : (
          <div
            className={`flex w-full px-2.5 ${alinhamentoConteudo}`}
          >
            {titulo}
          </div>
        )}

        <span
          role="separator"
          aria-orientation="vertical"
          title="Arraste para redimensionar. Duplo clique para restaurar."
          onMouseDown={(evento) =>
            iniciarRedimensionamentoColuna(
              coluna,
              evento,
            )
          }
          onDoubleClick={() =>
            restaurarLarguraColuna(
              coluna,
            )
          }
          className="absolute inset-y-0 right-0 z-20 w-2 cursor-col-resize select-none border-r-2 border-transparent transition hover:border-primary/40"
        />
      </th>
    );
  }

  useEffect(() => {
    if (!idInventarioContexto) {
      setInventarioContexto(null);
      return;
    }

    let ativo = true;

    setCarregandoInventarioContexto(true);
    setErro(null);

    void consultarInventarioDetalhe(
      idInventarioContexto,
    )
      .then(async (dados) => {
        if (!ativo) {
          return;
        }

        setInventarioContexto(dados);

        setClienteId(
          String(dados.cliente_id),
        );

        setArmazem(
          dados.armazem ?? "",
        );

        setTipo(
          dados.tipo ?? "",
        );

        setCodigoInventario(
          dados.codigo_inventario ?? "",
        );

        setStatus(
          dados.status ?? "",
        );

        setAba(
          abaInicial ??
            "visao-geral",
        );

        const historico =
          await buscarHistoricoInventarios({
            cliente_id: dados.cliente_id,
            codigo_inventario:
              dados.codigo_inventario,
            page: 1,
            page_size: 20,
          });

        if (!ativo) {
          return;
        }

        const registrosContexto =
          historico.inventarios.filter(
            (item) =>
              item.id_inventario ===
              idInventarioContexto,
          );

        setInventarios({
          ...historico,
          inventarios: registrosContexto,
          paginacao: {
            ...historico.paginacao,
            page: 1,
            total_registros:
              registrosContexto.length,
            total_paginas: 1,
            possui_proxima_pagina: false,
            possui_pagina_anterior: false,
          },
        });

        setPage(1);
      })
      .catch((e: unknown) => {
        if (!ativo) {
          return;
        }

        setErro(
          e instanceof Error
            ? e.message
            : "Erro ao carregar o inventário.",
        );
      })
      .finally(() => {
        if (ativo) {
          setCarregandoInventarioContexto(
            false,
          );
        }
      });

    return () => {
      ativo = false;
    };
  }, [idInventarioContexto]);

  useEffect(() => {
    if (
      !podeVisualizarHistorico ||
      idInventarioContexto ||
      aba === "tratativas"
    ) {
      setCarregandoClientes(false);
      return;
    }

    let ativo = true;
    setCarregandoClientes(true);

    void listarClientesDisponiveis()
      .then((dados) => {
        if (!ativo) {
          return;
        }

        const clientesUnicos =
          Array.from(
            new Map(
              dados.map((item) => [
                item.cliente_id,
                item,
              ]),
            ).values(),
          ).sort((a, b) =>
            a.cliente.localeCompare(
              b.cliente,
              "pt-BR",
            ),
          );

        setClientes(clientesUnicos);

        setClienteId((atual) => {
          const clienteAtualExiste =
            clientesUnicos.some(
              (item) =>
                String(item.cliente_id) ===
                atual,
            );

          if (clienteAtualExiste) {
            return atual;
          }

          return clientesUnicos[0]
            ? String(
                clientesUnicos[0].cliente_id,
              )
            : "";
        });
      })
      .catch((e: unknown) => {
        if (!ativo) {
          return;
        }

        setErro(
          e instanceof Error
            ? e.message
            : "Erro ao carregar os clientes.",
        );
      })
      .finally(() => {
        if (ativo) {
          setCarregandoClientes(false);
        }
      });

    return () => {
      ativo = false;
    };
  }, [
    podeVisualizarHistorico,
    idInventarioContexto,
    aba,
  ]);

  useEffect(() => {
    if (
      idInventarioContexto ||
      !podeVisualizarHistorico ||
      aba !== "inventarios"
    ) {
      return;
    }

    if (
      Number.isInteger(cliente) &&
      cliente > 0
    ) {
      void carregarInventarios(1);
    }
  }, [
    clienteId,
    idInventarioContexto,
    podeVisualizarHistorico,
    aba,
  ]);

  if (
    !podeVisualizarHistorico &&
    !podeVisualizarTratativas
  ) {
    return (
      <div className="p-6">
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
          <div className="font-semibold">
            Acesso não disponível
          </div>
          <p className="mt-1">
            Seu perfil não possui permissão para consultar o Histórico ou as Tratativas.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {idInventarioContexto ? (
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <Link
                to="/inventarios/$idInventario"
                params={{
                  idInventario: String(
                    idInventarioContexto,
                  ),
                }}
                className="mb-3 inline-flex text-sm font-medium text-primary hover:underline"
              >
                {"← Voltar ao inventário"}
              </Link>

              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Histórico contextual
              </div>

              <h1 className="mt-1 text-2xl font-semibold text-slate-900">
                Histórico do inventário
              </h1>

              <p className="mt-1 text-sm text-slate-600">
                Consulte a rastreabilidade e acesse todas as visões relacionadas a este inventário.
              </p>
            </div>

            {inventarioContexto && (
              <span className="inline-flex w-fit rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-700">
                #{inventarioContexto.id_inventario}
              </span>
            )}
          </div>

          {carregandoInventarioContexto ? (
            <div className="mt-5 rounded-lg border border-dashed p-5 text-sm text-slate-500">
              Carregando dados do inventário...
            </div>
          ) : inventarioContexto ? (
            <>
              <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
                <CampoContexto
                  titulo="Código"
                  valor={
                    inventarioContexto.codigo_inventario
                  }
                />

                <CampoContexto
                  titulo="Cliente"
                  valor={
                    inventarioContexto.cliente
                  }
                />

                <CampoContexto
                  titulo="Armazém"
                  valor={
                    inventarioContexto.armazem ??
                    "-"
                  }
                />

                <CampoContexto
                  titulo="Tipo"
                  valor={
                    inventarioContexto.tipo
                  }
                />

                <CampoContexto
                  titulo="Status"
                  valor={
                    inventarioContexto.status
                  }
                />

                <CampoContexto
                  titulo="Rodada atual"
                  valor={
                    inventarioContexto.rodada_atual ??
                    "-"
                  }
                />
              </div>
            </>
          ) : null}
        </section>
      ) : (
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">
            Histórico
          </h1>

          <p className="mt-1 text-sm text-slate-600">
            Rastreabilidade de inventários, itens, localizações, divergências e tratativas.
          </p>
        </div>
      )}

      <div className="overflow-x-auto">
        <div className="flex min-w-max gap-2 border-b border-slate-200 pb-3">
          {(idInventarioContexto
            ? ABAS_CONTEXTUAIS
            : abasGlobaisVisiveis
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() =>
                sincronizarAbaContextualUrl(id)
              }
              className={
                aba === id
                  ? "rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow-sm ring-1 ring-slate-900 transition"
                  : "rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:-translate-y-0.5 hover:border-slate-400 hover:bg-slate-50 hover:shadow-sm"
              }
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {!idInventarioContexto &&
        podeVisualizarHistorico &&
        aba !== "tratativas" && (
        <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">
                Filtros de consulta
              </h2>

              <p className="mt-0.5 text-xs text-slate-500">
                Refine os registros exibidos no histórico.
              </p>
            </div>

            <span className="text-xs font-medium text-slate-500">
              Cliente obrigatório
            </span>
          </div>

          <div className="grid gap-x-3 gap-y-3 md:grid-cols-2 xl:grid-cols-12">
            <label
              className={
                aba === "inventarios"
                  ? "grid min-w-0 gap-1 text-sm xl:col-span-6"
                  : "grid min-w-0 gap-1 text-sm xl:col-span-3"
              }
            >
              <span className="font-medium text-slate-600">
                Cliente
              </span>

              <select
                className={inputClass}
                value={clienteId}
                disabled={carregandoClientes}
                onChange={(event) =>
                  setClienteId(
                    event.target.value,
                  )
                }
              >
                <option value="" disabled>
                  {carregandoClientes
                    ? "Carregando clientes..."
                    : "Selecione um cliente"}
                </option>

                {clientes.map((item) => (
                  <option
                    key={item.cliente_id}
                    value={item.cliente_id}
                  >
                    {item.cliente}
                  </option>
                ))}
              </select>
            </label>

            {(aba === "item" ||
              aba === "localizacao" ||
              aba === "divergencias") && (
              <label className="grid gap-1 text-sm xl:col-span-2">
                <span className="font-medium text-slate-600">
                  Armazém
                </span>

                <input
                  className={inputClass}
                  value={armazem}
                  onChange={(event) =>
                    setArmazem(event.target.value)
                  }
                />
              </label>
            )}

            {(aba === "item" ||
              aba === "divergencias") && (
              <label className="grid gap-1 text-sm xl:col-span-2">
                <span className="font-medium text-slate-600">
                  Código
                </span>

                <input
                  className={inputClass}
                  value={codigo}
                  onChange={(event) =>
                    setCodigo(event.target.value)
                  }
                />
              </label>
            )}

            {(aba === "item" ||
              aba === "divergencias") && (
              <label className="grid gap-1 text-sm xl:col-span-2">
                <span className="font-medium text-slate-600">
                  Lote
                </span>

                <input
                  className={inputClass}
                  value={lote}
                  onChange={(event) =>
                    setLote(event.target.value)
                  }
                />
              </label>
            )}

            {(aba === "localizacao" ||
              aba === "divergencias") && (
              <label className="grid gap-1 text-sm xl:col-span-2">
                <span className="font-medium text-slate-600">
                  Localização
                </span>

                <input
                  className={inputClass}
                  value={localizacao}
                  onChange={(event) =>
                    setLocalizacao(event.target.value)
                  }
                />
              </label>
            )}

            {(aba === "inventarios" ||
              aba === "divergencias") && (
              <>
                <label
                  className={
                    aba === "inventarios"
                      ? "grid min-w-0 gap-1 text-sm xl:col-span-3"
                      : "grid min-w-0 gap-1 text-sm xl:col-span-1"
                  }
                >
                  <span className="font-medium text-slate-600">
                    Tipo
                  </span>

                  <select
                    className={inputClass}
                    value={tipo}
                    onChange={(event) =>
                      setTipo(event.target.value)
                    }
                  >
                    <option value="">Todos</option>
                    <option value="ROTATIVO">
                      ROTATIVO
                    </option>
                    <option value="OFICIAL">
                      OFICIAL
                    </option>
                  </select>
                </label>

                <label
                  className={
                    aba === "inventarios"
                      ? "grid min-w-0 gap-1 text-sm xl:col-span-3"
                      : "grid min-w-0 gap-1 text-sm xl:col-span-2"
                  }
                >
                  <span className="font-medium text-slate-600">
                    Data início
                  </span>

                  <input
                    type="date"
                    className={inputClass}
                    value={dataInicio}
                    onChange={(event) =>
                      setDataInicio(event.target.value)
                    }
                  />
                </label>

                <label
                  className={
                    aba === "inventarios"
                      ? "grid min-w-0 gap-1 text-sm xl:col-span-3"
                      : "grid min-w-0 gap-1 text-sm xl:col-span-2"
                  }
                >
                  <span className="font-medium text-slate-600">
                    Data fim
                  </span>

                  <input
                    type="date"
                    className={inputClass}
                    value={dataFim}
                    onChange={(event) =>
                      setDataFim(event.target.value)
                    }
                  />
                </label>
              </>
            )}

            {aba === "inventarios" && (
              <>
                <label className="grid min-w-0 gap-1 text-sm xl:col-span-3">
                  <span className="font-medium text-slate-600">
                    Status
                  </span>

                  <select
                    className={inputClass}
                    value={status}
                    onChange={(event) =>
                      setStatus(event.target.value)
                    }
                  >
                    <option value="">Todos</option>
                    <option value="ABERTO">
                      ABERTO
                    </option>
                    <option value="FINALIZADO">
                      FINALIZADO
                    </option>
                    <option value="CANCELADO">
                      CANCELADO
                    </option>
                  </select>
                </label>

                <label className="grid min-w-0 gap-1 text-sm xl:col-span-6">
                  <span className="font-medium text-slate-600">
                    Código do inventário
                  </span>

                  <input
                    className={inputClass}
                    value={codigoInventario}
                    onChange={(event) =>
                      setCodigoInventario(
                        event.target.value,
                      )
                    }
                  />
                </label>
              </>
            )}

            {aba === "divergencias" && (
              <label className="flex items-end gap-2 pb-2 text-sm xl:col-span-2">
                <input
                  type="checkbox"
                  checked={somenteRecorrentes}
                  onChange={(event) =>
                    setSomenteRecorrentes(
                      event.target.checked,
                    )
                  }
                />

                Somente recorrentes
              </label>
            )}
          </div>

          <div className="mt-3 flex flex-col-reverse gap-2 border-t border-slate-100 pt-3 sm:flex-row sm:items-center sm:justify-end">
            <button
              type="button"
              className={buttonClass}
              disabled={
                loading ||
                !(
                  tipo ||
                  status ||
                  dataInicio ||
                  dataFim ||
                  codigoInventario ||
                  armazem ||
                  codigo ||
                  lote ||
                  localizacao ||
                  somenteRecorrentes
                )
              }
              onClick={() => {
                setTipo("");
                setStatus("");
                setDataInicio("");
                setDataFim("");
                setCodigoInventario("");
                setArmazem("");
                setCodigo("");
                setLote("");
                setLocalizacao("");
                setSomenteRecorrentes(false);
              }}
            >
              Limpar filtros
            </button>

            <button
              type="button"
              className={primaryButtonClass}
              disabled={loading || !cliente}
              onClick={pesquisar}
            >
              {loading
                ? "Carregando..."
                : "Pesquisar"}
            </button>
          </div>
        </section>
      )}

      {aba !== "tratativas" && erro && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {erro}
        </div>
      )}

      {idInventarioContexto &&
        aba === "visao-geral" &&
        inventarioContexto && (
          <section className="space-y-4">
            <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
              <div className="flex flex-col gap-4 bg-gradient-to-r from-slate-950 via-slate-900 to-indigo-950 px-5 py-5 text-white lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-200">
                    Resumo executivo
                  </div>

                  <h2 className="mt-1 text-xl font-semibold">
                    Situação consolidada do inventário
                  </h2>

                  <p className="mt-1 max-w-3xl text-sm text-slate-300">
                    Acompanhe andamento, pendências, resultado e encerramento em uma única visão.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => void exportarExcel()}
                  disabled={exportandoExcel}
                  className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-white px-4 text-sm font-semibold text-slate-900 shadow-sm transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
                >
                  <span aria-hidden="true">
                    {exportandoExcel ? "⋯" : "↓"}
                  </span>

                  {exportandoExcel
                    ? "Gerando Excel..."
                    : "Exportar análise em Excel"}
                </button>
              </div>

              {erroExportacaoExcel && (
                <div
                  role="alert"
                  className="border-t border-red-200 bg-red-50 px-5 py-3 text-sm text-red-700"
                >
                  <span className="font-semibold">
                    Falha na exportação: {" "}
                  </span>
                  {erroExportacaoExcel}
                </div>
              )}
            </div>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
              <button
                type="button"
                onClick={() =>
                  sincronizarAbaContextualUrl("rodadas")
                }
                className="rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-indigo-300 hover:shadow-md"
              >
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Rodada final / atual
                </div>
                <div className="mt-2 text-2xl font-semibold text-slate-900">
                  R{resultadoFinalContexto?.rodada_final ??
                    rodadasContexto?.rodada_atual ??
                    inventarioContexto.rodada_atual ??
                    "-"}
                </div>
                <div className="mt-2 text-xs font-medium text-indigo-700">
                  Ver rodadas →
                </div>
              </button>

              <button
                type="button"
                onClick={() =>
                  sincronizarAbaContextualUrl("itens-contexto")
                }
                className="rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-indigo-300 hover:shadow-md"
              >
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Itens analisados
                </div>
                <div className="mt-2 text-2xl font-semibold text-slate-900">
                  {carregandoItensContexto
                    ? "..."
                    : resultadoFinalContexto?.resumo.total_itens ??
                      itensContextoHistorico.length}
                </div>
                <div className="mt-2 text-xs font-medium text-indigo-700">
                  Ver itens →
                </div>
              </button>

              <button
                type="button"
                onClick={() =>
                  sincronizarAbaContextualUrl("localizacoes-contexto")
                }
                className="rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-indigo-300 hover:shadow-md"
              >
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Localizações
                </div>
                <div className="mt-2 text-2xl font-semibold text-slate-900">
                  {carregandoLocalizacoesContexto
                    ? "..."
                    : localizacoesContextoHistorico
                        ?.resumo.localizacoes_planejadas ??
                      inventarioContexto.total_localizacoes ??
                      "-"}
                </div>
                <div className="mt-2 text-xs font-medium text-indigo-700">
                  Ver localizações →
                </div>
              </button>

              <button
                type="button"
                onClick={() =>
                  sincronizarAbaContextualUrl("divergencias-contexto")
                }
                className="rounded-xl border border-amber-200 bg-amber-50/60 p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-amber-300 hover:shadow-md"
              >
                <div className="text-xs font-semibold uppercase tracking-wide text-amber-700">
                  Divergências
                </div>
                <div className="mt-2 text-2xl font-semibold text-amber-900">
                  {carregandoDivergenciasContexto
                    ? "..."
                    : resultadoFinalContexto?.resumo.divergencias ??
                      divergenciasContextoHistorico.length}
                </div>
                <div className="mt-2 text-xs font-medium text-amber-800">
                  Analisar divergências →
                </div>
              </button>

              <button
                type="button"
                onClick={() =>
                  sincronizarAbaContextualUrl("decisoes")
                }
                className="rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-indigo-300 hover:shadow-md"
              >
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Decisões pendentes
                </div>
                <div className="mt-2 text-2xl font-semibold text-slate-900">
                  {carregandoDecisoesContexto
                    ? "..."
                    : decisoesContextoHistorico.filter(
                        (item) => item.pendente,
                      ).length}
                </div>
                <div className="mt-2 text-xs font-medium text-indigo-700">
                  Ver decisões →
                </div>
              </button>

              <button
                type="button"
                onClick={() =>
                  sincronizarAbaContextualUrl("resultado-final")
                }
                className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-emerald-300 hover:shadow-md"
              >
                <div className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
                  Acuracidade
                </div>
                <div className="mt-2 text-2xl font-semibold text-emerald-900">
                  {carregandoResultadoFinalContexto
                    ? "..."
                    : resultadoFinalContexto
                      ? `${fmtNumero(
                          resultadoFinalContexto.resumo
                            .acuracidade_percentual,
                        )}%`
                      : "-"}
                </div>
                <div className="mt-2 text-xs font-medium text-emerald-800">
                  Ver resultado →
                </div>
              </button>
            </div>

            <div className="grid gap-4 xl:grid-cols-3">
              <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm xl:col-span-2">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h3 className="font-semibold text-slate-900">
                      Situação operacional
                    </h3>
                    <p className="mt-1 text-sm text-slate-500">
                      Etapa atual e ação recomendada para continuidade.
                    </p>
                  </div>

                  <span
                    className={
                      String(inventarioContexto.status).toUpperCase() ===
                      "FINALIZADO"
                        ? "inline-flex w-fit rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200"
                        : String(inventarioContexto.status).toUpperCase() ===
                            "CANCELADO"
                          ? "inline-flex w-fit rounded-full bg-red-50 px-3 py-1 text-xs font-semibold text-red-700 ring-1 ring-inset ring-red-200"
                          : "inline-flex w-fit rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700 ring-1 ring-inset ring-amber-200"
                    }
                  >
                    {inventarioContexto.status}
                  </span>
                </div>

                <div className="mt-5 grid gap-4 sm:grid-cols-2">
                  <div className="rounded-lg bg-slate-50 p-4">
                    <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Fase operacional
                    </div>
                    <div className="mt-2 font-semibold text-slate-900">
                      {inventarioContexto.fase_operacional ??
                        "Não informada"}
                    </div>
                  </div>

                  <div className="rounded-lg border border-indigo-100 bg-indigo-50/60 p-4">
                    <div className="text-xs font-semibold uppercase tracking-wide text-indigo-600">
                      Próxima ação
                    </div>
                    <div className="mt-2 font-semibold text-indigo-950">
                      {inventarioContexto.proxima_acao ??
                        "Nenhuma ação pendente"}
                    </div>
                  </div>
                </div>

                <div className="mt-5">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium text-slate-700">
                      Progresso operacional
                    </span>
                    <span className="font-semibold tabular-nums text-slate-900">
                      {fmtNumero(
                        localizacoesContextoHistorico?.resumo
                          .percentual ??
                          inventarioContexto.percentual_progresso ??
                          0,
                      )}
                      %
                    </span>
                  </div>

                  <div className="mt-2 h-2.5 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-indigo-600 transition-all"
                      style={{
                        width: `${Math.min(
                          100,
                          Math.max(
                            0,
                            Number(
                              localizacoesContextoHistorico?.resumo
                                .percentual ??
                                inventarioContexto.percentual_progresso ??
                                0,
                            ),
                          ),
                        )}%`,
                      }}
                    />
                  </div>
                </div>
              </article>

              <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <h3 className="font-semibold text-slate-900">
                  Pendências
                </h3>
                <p className="mt-1 text-sm text-slate-500">
                  Pontos que ainda exigem acompanhamento.
                </p>

                <dl className="mt-4 divide-y divide-slate-100">
                  <div className="flex items-center justify-between gap-4 py-3">
                    <dt className="text-sm text-slate-600">
                      Divergências sem decisão
                    </dt>
                    <dd className="font-semibold tabular-nums text-slate-900">
                      {inventarioContexto.divergencias_sem_decisao ?? 0}
                    </dd>
                  </div>
                  <div className="flex items-center justify-between gap-4 py-3">
                    <dt className="text-sm text-slate-600">
                      Recontagens pendentes
                    </dt>
                    <dd className="font-semibold tabular-nums text-slate-900">
                      {inventarioContexto.recontagens_pendentes ?? 0}
                    </dd>
                  </div>
                  <div className="flex items-center justify-between gap-4 py-3">
                    <dt className="text-sm text-slate-600">
                      Localizações pendentes
                    </dt>
                    <dd className="font-semibold tabular-nums text-slate-900">
                      {localizacoesContextoHistorico
                        ?.resumo.localizacoes_pendentes ??
                        inventarioContexto.localizacoes_pendentes ??
                        0}
                    </dd>
                  </div>
                </dl>
              </article>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <h3 className="font-semibold text-slate-900">
                  Período e identificação
                </h3>

                <dl className="mt-4 grid gap-4 sm:grid-cols-2">
                  <CampoResumoExecutivo
                    titulo="Código"
                    valor={inventarioContexto.codigo_inventario}
                  />
                  <CampoResumoExecutivo
                    titulo="Tipo"
                    valor={inventarioContexto.tipo}
                  />
                  <CampoResumoExecutivo
                    titulo="Início"
                    valor={fmtData(
                      inventarioContexto.data_hora_inicio,
                    )}
                  />
                  <CampoResumoExecutivo
                    titulo="Fim"
                    valor={fmtData(
                      inventarioContexto.data_hora_fim,
                    )}
                  />
                  <CampoResumoExecutivo
                    titulo="Armazém"
                    valor={inventarioContexto.armazem ?? "-"}
                  />
                  <CampoResumoExecutivo
                    titulo="Total de rodadas"
                    valor={
                      rodadasContexto?.total_rodadas ?? "-"
                    }
                  />
                </dl>
              </article>

              <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="font-semibold text-slate-900">
                      Resultado e encerramento
                    </h3>
                    <p className="mt-1 text-sm text-slate-500">
                      Consolidação disponível após a finalização.
                    </p>
                  </div>

                  {resultadoFinalContexto && (
                    <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">
                      Consolidado
                    </span>
                  )}
                </div>

                {carregandoResultadoFinalContexto ? (
                  <div className="mt-4 rounded-lg bg-slate-50 p-4 text-sm text-slate-600">
                    Carregando resultado final...
                  </div>
                ) : resultadoFinalContexto ? (
                  <dl className="mt-4 grid gap-4 sm:grid-cols-2">
                    <CampoResumoExecutivo
                      titulo="Itens OK"
                      valor={resultadoFinalContexto.resumo.ok}
                    />
                    <CampoResumoExecutivo
                      titulo="Itens NOK"
                      valor={resultadoFinalContexto.resumo.nok}
                    />
                    <CampoResumoExecutivo
                      titulo="Faltas"
                      valor={resultadoFinalContexto.resumo.faltas}
                    />
                    <CampoResumoExecutivo
                      titulo="Sobras"
                      valor={resultadoFinalContexto.resumo.sobras}
                    />
                    <CampoResumoExecutivo
                      titulo="Finalizado em"
                      valor={fmtData(
                        resultadoFinalContexto
                          .data_hora_finalizacao,
                      )}
                    />
                    <CampoResumoExecutivo
                      titulo="Finalizado por"
                      valor={
                        resultadoFinalContexto.finalizado_por ??
                        "-"
                      }
                    />
                  </dl>
                ) : (
                  <div className="mt-4 rounded-lg border border-dashed border-slate-300 bg-slate-50/60 p-4 text-sm text-slate-600">
                    {erroResultadoFinalContexto
                      ? "O resultado final não pôde ser carregado. Consulte a aba Resultado final."
                      : String(
                            inventarioContexto.status,
                          ).toUpperCase() === "FINALIZADO"
                        ? "O inventário foi finalizado, mas o consolidado ainda não está disponível."
                        : "O resultado final será exibido quando o inventário for encerrado."}
                  </div>
                )}
              </article>
            </div>
          </section>
        )}

      {!idInventarioContexto &&
        aba === "inventarios" &&
        inventarios && (
        <section className="space-y-3">
          {!idInventarioContexto && (
            <div className="grid gap-2 sm:grid-cols-3">
              <Resumo
                titulo="Registros"
                valor={
                  inventarios.paginacao
                    .total_registros
                }
              />

              <Resumo
                titulo="Página"
                valor={`${inventarios.paginacao.page}/${inventarios.paginacao.total_paginas}`}
              />

              <Resumo
                titulo="Exibidos"
                valor={
                  inventarios.inventarios.length
                }
              />
            </div>
          )}

          {!idInventarioContexto && (
            <div className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-slate-50/70 px-3 py-2 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
              <span>
                Classifica\u00e7\u00e3o da p\u00e1gina atual:
                clique no cabe\u00e7alho para ordenar e
                arraste a borda para redimensionar.
              </span>

              <button
                type="button"
                onClick={() =>
                  setLargurasTabelaInventario({
                    ...LARGURAS_PADRAO_TABELA_INVENTARIO,
                  })
                }
                className="w-fit font-medium text-slate-600 transition hover:text-primary"
              >
                Restaurar larguras
              </button>
            </div>
          )}

          <div className="relative overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
            <table
              className="table-fixed border-separate border-spacing-0 text-left text-sm"
              style={{
                width:
                  larguraTotalTabelaInventario,
                minWidth:
                  larguraTotalTabelaInventario,
              }}
            >
            <thead>
              <tr>
                {renderCabecalhoInventario({
                  titulo: "ID",
                  coluna: "id",
                })}

                {renderCabecalhoInventario({
                  titulo: "C\u00f3digo",
                  coluna: "codigo",
                })}

                {renderCabecalhoInventario({
                  titulo: "Cliente",
                  coluna: "cliente",
                })}

                {renderCabecalhoInventario({
                  titulo: "Armaz\u00e9m",
                  coluna: "armazem",
                })}

                {renderCabecalhoInventario({
                  titulo: "Tipo",
                  coluna: "tipo",
                })}

                {renderCabecalhoInventario({
                  titulo: "Status",
                  coluna: "status",
                })}

                {renderCabecalhoInventario({
                  titulo: "Rodada",
                  coluna: "rodada",
                  alinhamento: "center",
                })}

                {renderCabecalhoInventario({
                  titulo: "In\u00edcio",
                  coluna: "inicio",
                })}

                {renderCabecalhoInventario({
                  titulo: "Fim",
                  coluna: "fim",
                })}

                {!idInventarioContexto &&
                  renderCabecalhoInventario({
                    titulo: "A\u00e7\u00e3o",
                    coluna: "acao",
                    ordenavel: false,
                    alinhamento: "right",
                  })}
              </tr>
            </thead>
            <tbody>
              {inventariosOrdenadosPagina.map((x) => (
                <tr
                  key={x.id_inventario}
                  className="group border-t border-slate-100 transition-colors odd:bg-white even:bg-slate-50/25 hover:bg-slate-50"
                >
                  <td className="whitespace-nowrap px-2.5 py-2 align-middle">
                    <Link
                      to="/inventarios/$idInventario"
                      params={{
                        idInventario: String(
                          x.id_inventario,
                        ),
                      }}
                      className="font-semibold text-primary hover:underline"
                    >
                      #{x.id_inventario}
                    </Link>
                  </td>

                  <td className="whitespace-nowrap py-2 pl-2.5 pr-1 align-middle">
                    <Link
                      to="/inventarios/$idInventario"
                      params={{
                        idInventario: String(
                          x.id_inventario,
                        ),
                      }}
                      className="font-semibold text-primary hover:underline"
                    >
                      {x.codigo_inventario}
                    </Link>
                  </td>

                  <td className="py-2 pl-1 pr-2.5 align-middle text-slate-800">
                    <div
                      className="w-full truncate font-medium"
                      title={x.cliente}
                    >
                      {x.cliente}
                    </div>
                  </td>

                  <td className="whitespace-nowrap px-2.5 py-2 align-middle font-medium text-slate-700">
                    {x.armazem ?? "-"}
                  </td>

                  <td className="whitespace-nowrap px-2.5 py-2 align-middle">
                    <span
                      className={
                        x.tipo === "OFICIAL"
                          ? "inline-flex rounded-full bg-violet-50 px-1.5 py-0.5 text-[11px] font-medium text-violet-700 ring-1 ring-inset ring-violet-200"
                          : "inline-flex rounded-full bg-sky-50 px-1.5 py-0.5 text-[11px] font-medium text-sky-700 ring-1 ring-inset ring-sky-200"
                      }
                    >
                      {x.tipo}
                    </span>
                  </td>

                  <td className="whitespace-nowrap px-2.5 py-2 align-middle">
                    <span
                      className={
                        x.status === "FINALIZADO"
                          ? "inline-flex rounded-full bg-emerald-50 px-1.5 py-0.5 text-[11px] font-medium text-emerald-700 ring-1 ring-inset ring-emerald-200"
                          : x.status === "CANCELADO"
                            ? "inline-flex rounded-full bg-red-50 px-1.5 py-0.5 text-[11px] font-medium text-red-700 ring-1 ring-inset ring-red-200"
                            : x.status === "ABERTO"
                              ? "inline-flex rounded-full bg-amber-50 px-1.5 py-0.5 text-[11px] font-medium text-amber-700 ring-1 ring-inset ring-amber-200"
                              : "inline-flex rounded-full bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-700 ring-1 ring-inset ring-slate-200"
                      }
                    >
                      {x.status}
                    </span>
                  </td>

                  <td className="whitespace-nowrap px-2.5 py-2 text-center align-middle tabular-nums text-slate-700">
                    {x.rodada_atual ?? "-"}
                  </td>

                  <td className="whitespace-nowrap px-2.5 py-2 align-middle text-xs tabular-nums text-slate-600">
                    {fmtData(x.data_hora_inicio)}
                  </td>

                  <td className="whitespace-nowrap px-2.5 py-2 align-middle text-xs tabular-nums text-slate-600">
                    {fmtData(x.data_hora_fim)}
                  </td>

                  {!idInventarioContexto && (
                    <td className="whitespace-nowrap border-l border-slate-100 bg-inherit px-2.5 py-2 text-right align-middle">
                      <Link
                        to="/historico"
                        search={{
                          inventario:
                            x.id_inventario,
                          aba: "visao-geral",
                        }}
                        className="inline-flex h-8 items-center justify-center gap-1 whitespace-nowrap rounded-md border border-slate-200 bg-white px-2 text-[11px] font-medium text-slate-600 transition hover:border-slate-300 hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/20"
                      >
                        <span>
                          {"Ver hist\u00f3rico"}
                        </span>

                        <span
                          className="text-slate-400"
                          aria-hidden="true"
                        >
                          {"\u2192"}
                        </span>
                      </Link>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          </div>

          {!idInventarioContexto && (
            <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
              <button
                type="button"
                className={buttonClass}
                disabled={
                  loading ||
                  !inventarios.paginacao
                    .possui_pagina_anterior
                }
                onClick={() =>
                  void carregarInventarios(
                    page - 1,
                  )
                }
              >
                Anterior
              </button>

              <span className="text-center text-sm font-medium text-slate-600">
                Página{" "}
                {inventarios.paginacao.page} de{" "}
                {
                  inventarios.paginacao
                    .total_paginas
                }
              </span>

              <button
                type="button"
                className={buttonClass}
                disabled={
                  loading ||
                  !inventarios.paginacao
                    .possui_proxima_pagina
                }
                onClick={() =>
                  void carregarInventarios(
                    page + 1,
                  )
                }
              >
                Próxima
              </button>
            </div>
          )}
        </section>
      )}

      {aba === "item" && (
        <section className="space-y-3">
          <div className="grid gap-3 md:grid-cols-2">
            <Resumo titulo="Inventários encontrados" valor={itemResponse?.paginacao?.total_registros ?? itens.length} />
            <Resumo titulo="Exibidos nesta página" valor={itemResponse?.paginacao?.registros_pagina ?? itens.length} />
          </div>
          <div className="space-y-3">
            {itens.map((x) => (
              <details key={x.id_inventario} className="rounded-lg border border-slate-200 bg-white p-4">
                <summary className="cursor-pointer font-medium text-slate-900">
                  #{x.id_inventario} · {x.codigo_inventario} · {x.tipo} · {x.status}
                  {x.consistencia?.status === "INCONSISTENTE" ? " · INCONSISTENTE" : ""}
                </summary>
                <div className="mt-4 grid gap-3 md:grid-cols-4 text-sm">
                  <Campo nome="Cliente" valor={x.cliente} />
                  <Campo nome="Armazém" valor={x.armazem ?? "-"} />
                  <Campo nome="Rodada atual" valor={x.rodada_atual ?? "-"} />
                  <Campo nome="Consistência" valor={x.consistencia?.status ?? "-"} />
                  <Campo nome="Snapshots" valor={x.snapshot?.length ?? 0} />
                  <Campo nome="Rodadas" valor={x.rodadas?.length ?? 0} />
                  <Campo nome="Decisões gestor" valor={x.decisoes_gestor?.length ?? 0} />
                  <Campo nome="Resultados finais" valor={x.resultado_final?.length ?? 0} />
                </div>
              </details>
            ))}
            {!loading && itens.length === 0 && (
              <p className="text-sm text-slate-500">Pesquise um código para consultar o histórico.</p>
            )}
          </div>
          {itemResponse?.paginacao && (
            <div className="flex items-center justify-between">
              <button className={buttonClass} disabled={loading || !itemResponse.paginacao.possui_pagina_anterior} onClick={() => void carregarItem(itemPage - 1)}>
                Anterior
              </button>
              <span className="text-sm text-slate-600">Página {itemResponse.paginacao.page} de {itemResponse.paginacao.total_paginas}</span>
              <button className={buttonClass} disabled={loading || !itemResponse.paginacao.possui_proxima_pagina} onClick={() => void carregarItem(itemPage + 1)}>
                Próxima
              </button>
            </div>
          )}
        </section>
      )}

      {aba === "localizacao" && (
        <section className="space-y-3">
          <div className="grid gap-3 md:grid-cols-2">
            <Resumo titulo="Inventários encontrados" valor={localizacoes?.paginacao?.total_registros ?? 0} />
            <Resumo titulo="Exibidos nesta página" valor={localizacoes?.paginacao?.registros_pagina ?? localizacoes?.inventarios?.length ?? 0} />
          </div>
          <div className="space-y-3">
            {(localizacoes?.inventarios ?? []).map((x) => (
              <details key={x.id_inventario} className="rounded-lg border border-slate-200 bg-white p-4">
                <summary className="cursor-pointer font-medium text-slate-900">
                  #{x.id_inventario} · {x.codigo_inventario} · {x.tipo} · {x.status}
                  {x.consistencia?.status === "INCONSISTENTE" ? " · INCONSISTENTE" : ""}
                </summary>
                <div className="mt-4 grid gap-3 md:grid-cols-4 text-sm">
                  <Campo nome="Cliente" valor={x.cliente} />
                  <Campo nome="Armazém" valor={x.armazem ?? "-"} />
                  <Campo nome="Rodada atual" valor={x.rodada_atual ?? "-"} />
                  <Campo nome="Consistência" valor={x.consistencia?.status ?? "-"} />
                  <Campo nome="Itens previstos" valor={x.snapshot?.itens_previstos ?? 0} />
                  <Campo nome="Rodadas" valor={x.rodadas?.length ?? 0} />
                  <Campo nome="Resultado final" valor={x.resultado_final?.itens ?? 0} />
                  <Campo nome="Início" valor={fmtData(x.data_hora_inicio)} />
                </div>
              </details>
            ))}
            {!loading && localizacoes && (localizacoes.inventarios?.length ?? 0) === 0 && (
              <p className="text-sm text-slate-500">Nenhum inventário encontrado para esta localização.</p>
            )}
          </div>
          {localizacoes?.paginacao && (
            <div className="flex items-center justify-between">
              <button className={buttonClass} disabled={loading || !localizacoes.paginacao.possui_pagina_anterior} onClick={() => void carregarLocalizacao(localizacaoPage - 1)}>
                Anterior
              </button>
              <span className="text-sm text-slate-600">Página {localizacoes.paginacao.page} de {localizacoes.paginacao.total_paginas}</span>
              <button className={buttonClass} disabled={loading || !localizacoes.paginacao.possui_proxima_pagina} onClick={() => void carregarLocalizacao(localizacaoPage + 1)}>
                Próxima
              </button>
            </div>
          )}
        </section>
      )}

      {aba === "divergencias" && divergencias && (
        <section className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <Resumo titulo="Inventários válidos" valor={divergencias.resumo.inventarios_validos} />
            <Resumo titulo="Com divergência" valor={divergencias.resumo.inventarios_com_divergencia} />
            <Resumo titulo="Combinações recorrentes" valor={divergencias.resumo.combinacoes_recorrentes} />
            <Resumo titulo="Taxa de recorrência" valor={`${fmtNumero(divergencias.resumo.taxa_recorrencia_percentual)}%`} />
            <Resumo titulo="Faltas" valor={divergencias.resumo.resultados_item_falta} />
            <Resumo titulo="Sobras" valor={divergencias.resumo.resultados_item_sobra} />
            <Resumo titulo="Qtd. faltante" valor={fmtNumero(divergencias.resumo.quantidade_faltante_total)} />
            <Resumo titulo="Qtd. sobrando" valor={fmtNumero(divergencias.resumo.quantidade_sobrando_total)} />
          </div>

          <Tabela>
            <thead>
              <tr>
                <Th>Localização</Th><Th>Código</Th><Th>Lote</Th><Th>Divergências</Th>
                <Th>Consecutivas</Th><Th>Taxa</Th><Th>Padrão</Th>
              </tr>
            </thead>
            <tbody>
              {divergencias.ranking_recorrencia.map((x, i) => (
                <tr key={`${x.localizacao}-${x.codigo}-${x.lote}-${i}`} className="border-t border-slate-100">
                  <Td>{x.localizacao}</Td><Td>{x.codigo}</Td><Td>{x.lote}</Td>
                  <Td>{x.divergencias}</Td><Td>{x.divergencias_consecutivas}</Td>
                  <Td>{fmtNumero(x.taxa_divergencia_percentual)}%</Td><Td>{x.padrao}</Td>
                </tr>
              ))}
            </tbody>
          </Tabela>
        </section>
      )}

      {!idInventarioContexto &&
        aba === "tratativas" &&
        podeVisualizarTratativas && (
          <TratativasHistorico
            integrado
            exibirCabecalho={false}
            exibirVoltarInventario={false}
            {...(tratativaInventario !== undefined
              ? { inventario: tratativaInventario }
              : {})}
            {...(ocorrenciaTratativa !== undefined
              ? { ocorrencia: ocorrenciaTratativa }
              : {})}
            onAtualizarContexto={
              atualizarContextoTratativas
            }
          />
        )}

      {idInventarioContexto &&
        aba === "rodadas" && (
          <SecaoHistoricoContextual
            titulo="Rodadas"
            descricao="Histórico das contagens e recontagens executadas neste inventário."
          >
            {carregandoRodadasContexto ? (
              <div className="rounded-lg border border-slate-200 bg-white p-5 text-sm text-slate-600">
                Carregando rodadas...
              </div>
            ) : erroRodadasContexto ? (
              <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                {erroRodadasContexto}
              </div>
            ) : rodadasContexto ? (
              <div className="space-y-4">
                <div className="grid gap-3 md:grid-cols-3">
                  <div className="rounded-lg border border-slate-200 bg-white p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                      Total de rodadas
                    </div>

                    <div className="mt-2 text-2xl font-semibold text-slate-900">
                      {rodadasContexto.total_rodadas}
                    </div>
                  </div>

                  <div className="rounded-lg border border-slate-200 bg-white p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                      Rodada final / atual
                    </div>

                    <div className="mt-2 text-2xl font-semibold text-slate-900">
                      R{rodadasContexto.rodada_atual}
                    </div>
                  </div>

                  <div className="rounded-lg border border-slate-200 bg-white p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                      Status do inventário
                    </div>

                    <div className="mt-2 text-lg font-semibold text-slate-900">
                      {rodadasContexto.status_inventario}
                    </div>
                  </div>
                </div>

                {rodadasContexto.rodadas.length > 0 ? (
                  <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
                    <table className="min-w-full text-left text-sm">
                      <thead className="bg-slate-50">
                        <tr>
                          <Th>Rodada</Th>
                          <Th>ID da rodada</Th>
                          <Th>Status</Th>
                          <Th>Referência</Th>
                        </tr>
                      </thead>

                      <tbody>
                        {[...rodadasContexto.rodadas]
                          .sort(
                            (a, b) =>
                              a.numero_rodada -
                              b.numero_rodada,
                          )
                          .map((rodada) => {
                            const atual =
                              rodada.numero_rodada ===
                              rodadasContexto.rodada_atual;

                            return (
                              <tr
                                key={rodada.id_rodada}
                                className="border-t border-slate-100"
                              >
                                <Td>
                                  <span className="font-semibold">
                                    R{rodada.numero_rodada}
                                  </span>
                                </Td>

                                <Td>
                                  #{rodada.id_rodada}
                                </Td>

                                <Td>
                                  <span
                                    className={
                                      rodada.status ===
                                      "FINALIZADA"
                                        ? "inline-flex rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700"
                                        : rodada.status ===
                                            "ABERTA"
                                          ? "inline-flex rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700"
                                          : "inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700"
                                    }
                                  >
                                    {rodada.status}
                                  </span>
                                </Td>

                                <Td>
                                  {atual
                                    ? "Rodada final / atual"
                                    : "Rodada anterior"}
                                </Td>
                              </tr>
                            );
                          })}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed border-slate-300 bg-white p-5 text-sm text-slate-600">
                    Nenhuma rodada registrada para este inventário.
                  </div>
                )}
              </div>
            ) : (
              <div className="rounded-lg border border-dashed border-slate-300 bg-white p-5 text-sm text-slate-600">
                Histórico de rodadas indisponível.
              </div>
            )}
          </SecaoHistoricoContextual>
        )}

      {idInventarioContexto &&
        aba === "itens-contexto" && (
          <SecaoHistoricoContextual
            titulo="Itens"
            descricao={
              "Resultado consolidado dos itens vinculados exclusivamente a este invent\u00e1rio."
            }
          >
            {carregandoItensContexto ? (
              <div className="rounded-lg border border-slate-200 bg-white p-5 text-sm text-slate-600">
                Carregando itens...
              </div>
            ) : erroItensContexto ? (
              <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                <div className="font-semibold">
                  {
                    "N\u00e3o foi poss\u00edvel carregar os itens."
                  }
                </div>

                <div className="mt-1">
                  {erroItensContexto}
                </div>
              </div>
            ) : (
              <div className="space-y-5">
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <div className="rounded-lg border border-slate-200 bg-white p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                      Total
                    </div>

                    <div className="mt-2 text-2xl font-semibold text-slate-900">
                      {itensContextoHistorico.length}
                    </div>
                  </div>

                  <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-emerald-700">
                      OK
                    </div>

                    <div className="mt-2 text-2xl font-semibold text-emerald-800">
                      {
                        itensContextoHistorico.filter(
                          (item) =>
                            item.diferenca === 0 &&
                            item.status !==
                              "AGUARDANDO_CONTAGEM",
                        ).length
                      }
                    </div>
                  </div>

                  <div className="rounded-lg border border-red-200 bg-red-50/50 p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-red-700">
                      {"Com diferen\u00e7a"}
                    </div>

                    <div className="mt-2 text-2xl font-semibold text-red-800">
                      {
                        itensContextoHistorico.filter(
                          (item) =>
                            item.diferenca !== 0,
                        ).length
                      }
                    </div>
                  </div>

                  <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-amber-700">
                      Aguardando contagem
                    </div>

                    <div className="mt-2 text-2xl font-semibold text-amber-800">
                      {
                        itensContextoHistorico.filter(
                          (item) =>
                            item.status ===
                            "AGUARDANDO_CONTAGEM",
                        ).length
                      }
                    </div>
                  </div>
                </div>

                {itensContextoHistorico.length > 0 ? (
                  <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
                    <table className="min-w-full text-sm">
                      <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                        <tr>
                          <th className="px-4 py-3">
                            {
                              "Localiza\u00e7\u00e3o"
                            }
                          </th>

                          <th className="px-4 py-3">
                            {"C\u00f3digo"}
                          </th>

                          <th className="px-4 py-3">
                            Lote
                          </th>

                          <th className="min-w-64 px-4 py-3">
                            {
                              "Descri\u00e7\u00e3o"
                            }
                          </th>

                          <th className="px-4 py-3 text-right">
                            Estoque
                          </th>

                          <th className="px-4 py-3 text-right">
                            Contado
                          </th>

                          <th className="px-4 py-3 text-right">
                            {
                              "Diferen\u00e7a"
                            }
                          </th>

                          <th className="px-4 py-3">
                            Status
                          </th>
                        </tr>
                      </thead>

                      <tbody className="divide-y divide-slate-100">
                        {itensContextoHistorico.map(
                          (item, indice) => (
                            <tr
                              key={`${item.chave}-${indice}`}
                              className="align-top hover:bg-slate-50/70"
                            >
                              <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-700">
                                {item.localizacao}
                              </td>

                              <td className="whitespace-nowrap px-4 py-3 font-semibold text-slate-900">
                                {item.codigo}
                              </td>

                              <td className="whitespace-nowrap px-4 py-3 text-slate-700">
                                {item.lote}
                              </td>

                              <td className="px-4 py-3 text-slate-700">
                                {item.descricao}
                              </td>

                              <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-slate-700">
                                {item.qtd_estoque.toLocaleString(
                                  "pt-BR",
                                )}
                              </td>

                              <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-slate-700">
                                {item.qtd_contada.toLocaleString(
                                  "pt-BR",
                                )}
                              </td>

                              <td
                                className={
                                  item.diferenca === 0
                                    ? "whitespace-nowrap px-4 py-3 text-right font-semibold tabular-nums text-emerald-700"
                                    : "whitespace-nowrap px-4 py-3 text-right font-semibold tabular-nums text-red-700"
                                }
                              >
                                {item.diferenca.toLocaleString(
                                  "pt-BR",
                                )}
                              </td>

                              <td className="whitespace-nowrap px-4 py-3">
                                <span
                                  className={
                                    item.status === "OK"
                                      ? "inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700"
                                      : item.status ===
                                          "AGUARDANDO_CONTAGEM"
                                        ? "inline-flex rounded-full border border-amber-200 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700"
                                        : "inline-flex rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-medium text-slate-700"
                                  }
                                >
                                  {
                                    item.status ===
                                    "AGUARDANDO_CONTAGEM"
                                      ? "N\u00e3o iniciado"
                                      : item.status
                                  }
                                </span>
                              </td>
                            </tr>
                          ),
                        )}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed border-slate-300 bg-white p-5 text-sm text-slate-600">
                    {
                      "Nenhum item foi encontrado para este invent\u00e1rio."
                    }
                  </div>
                )}
              </div>
            )}
          </SecaoHistoricoContextual>
        )}

      {idInventarioContexto &&
        aba === "localizacoes-contexto" && (
          <SecaoHistoricoContextual
            titulo={"Localiza\u00e7\u00f5es"}
            descricao={
              "Acompanhe os endere\u00e7os que participaram de cada rodada deste invent\u00e1rio."
            }
          >
            <div className="space-y-5">
              <div className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <div className="text-sm font-semibold text-slate-900">
                    Rodada consultada
                  </div>

                  <div className="mt-1 text-xs text-slate-500">
                    {
                      "Selecione uma rodada para consultar o progresso registrado em cada localiza\u00e7\u00e3o."
                    }
                  </div>
                </div>

                <label className="block min-w-44">
                  <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                    Rodada
                  </span>

                  <select
                    value={
                      rodadaLocalizacoesContexto ??
                      ""
                    }
                    disabled={
                      carregandoRodadasContexto ||
                      !rodadasContexto ||
                      rodadasContexto.rodadas
                        .length === 0
                    }
                    onChange={(evento) => {
                      const valor = Number(
                        evento.target.value,
                      );

                      setRodadaLocalizacoesContexto(
                        Number.isInteger(valor) &&
                          valor > 0
                          ? valor
                          : null,
                      );
                    }}
                    className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900 outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                  >
                    {!rodadaLocalizacoesContexto ? (
                      <option value="">
                        Selecione
                      </option>
                    ) : null}

                    {rodadasContexto
                      ? [
                          ...rodadasContexto.rodadas,
                        ]
                          .sort(
                            (a, b) =>
                              a.numero_rodada -
                              b.numero_rodada,
                          )
                          .map((rodada) => (
                            <option
                              key={
                                rodada.id_rodada
                              }
                              value={
                                rodada.numero_rodada
                              }
                            >
                              R
                              {
                                rodada.numero_rodada
                              }
                            </option>
                          ))
                      : null}
                  </select>
                </label>
              </div>

              {carregandoLocalizacoesContexto ? (
                <div className="rounded-lg border border-slate-200 bg-white p-5 text-sm text-slate-600">
                  {
                    "Carregando localiza\u00e7\u00f5es..."
                  }
                </div>
              ) : erroLocalizacoesContexto ? (
                <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                  <div className="font-semibold">
                    {
                      "N\u00e3o foi poss\u00edvel carregar as localiza\u00e7\u00f5es."
                    }
                  </div>

                  <div className="mt-1">
                    {erroLocalizacoesContexto}
                  </div>
                </div>
              ) : localizacoesContextoHistorico ? (
                <>
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                    <div className="rounded-lg border border-slate-200 bg-white p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                        Planejadas
                      </div>

                      <div className="mt-2 text-2xl font-semibold text-slate-900">
                        {
                          localizacoesContextoHistorico
                            .resumo
                            .localizacoes_planejadas
                        }
                      </div>
                    </div>

                    <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-emerald-700">
                        {
                          "Conclu\u00eddas"
                        }
                      </div>

                      <div className="mt-2 text-2xl font-semibold text-emerald-800">
                        {
                          localizacoesContextoHistorico
                            .resumo
                            .localizacoes_concluidas
                        }
                      </div>
                    </div>

                    <div className="rounded-lg border border-sky-200 bg-sky-50/50 p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-sky-700">
                        Em andamento
                      </div>

                      <div className="mt-2 text-2xl font-semibold text-sky-800">
                        {
                          localizacoesContextoHistorico
                            .resumo
                            .localizacoes_em_andamento
                        }
                      </div>
                    </div>

                    <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-amber-700">
                        Pendentes
                      </div>

                      <div className="mt-2 text-2xl font-semibold text-amber-800">
                        {
                          localizacoesContextoHistorico
                            .resumo
                            .localizacoes_pendentes
                        }
                      </div>
                    </div>

                    <div className="rounded-lg border border-slate-200 bg-white p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                        Progresso
                      </div>

                      <div className="mt-2 text-2xl font-semibold text-slate-900">
                        {Number(
                          localizacoesContextoHistorico
                            .resumo.percentual,
                        ).toLocaleString(
                          "pt-BR",
                          {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          },
                        )}
                        %
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                    <span>
                      Rodada R
                      {
                        localizacoesContextoHistorico
                          .numero_rodada
                      }
                    </span>

                    <span>
                      {"\u00b7"}
                    </span>

                    <span>
                      {
                        localizacoesContextoHistorico
                          .status_rodada
                      }
                    </span>

                    <span>
                      {"\u00b7"}
                    </span>

                    <span>
                      {
                        localizacoesContextoHistorico
                          .localizacoes.length
                      }{" "}
                      {
                        "localiza\u00e7\u00e3o(\u00f5es)"
                      }
                    </span>
                  </div>

                  {localizacoesContextoHistorico
                    .localizacoes.length > 0 ? (
                    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
                      <table className="min-w-full text-sm">
                        <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                          <tr>
                            <th className="px-4 py-3">
                              {
                                "Localiza\u00e7\u00e3o"
                              }
                            </th>

                            <th className="px-4 py-3">
                              Status
                            </th>

                            <th className="px-4 py-3 text-right">
                              Planejados
                            </th>

                            <th className="px-4 py-3 text-right">
                              Processados
                            </th>

                            <th className="px-4 py-3 text-right">
                              Pendentes
                            </th>

                            <th className="px-4 py-3 text-right">
                              Progresso
                            </th>

                            <th className="px-4 py-3 text-right">
                              Bipagens
                            </th>

                            <th className="px-4 py-3 text-right">
                              Quantidade
                            </th>

                            <th className="px-4 py-3">
                              Operadores
                            </th>

                            <th className="px-4 py-3">
                              {
                                "In\u00edcio"
                              }
                            </th>

                            <th className="px-4 py-3">
                              {
                                "\u00daltima atividade"
                              }
                            </th>

                            <th className="px-4 py-3">
                              Sem atividade
                            </th>
                          </tr>
                        </thead>

                        <tbody className="divide-y divide-slate-100">
                          {localizacoesContextoHistorico
                            .localizacoes.map(
                              (localizacao) => (
                                <tr
                                  key={
                                    localizacao.localizacao
                                  }
                                  className="align-top hover:bg-slate-50/70"
                                >
                                  <td className="whitespace-nowrap px-4 py-3 font-semibold text-slate-900">
                                    {
                                      localizacao.localizacao
                                    }
                                  </td>

                                  <td className="whitespace-nowrap px-4 py-3">
                                    <span
                                      className={
                                        localizacao.status ===
                                        "CONCLUIDA"
                                          ? "inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700"
                                          : localizacao.status ===
                                              "EM_ANDAMENTO"
                                            ? "inline-flex rounded-full border border-sky-200 bg-sky-50 px-2 py-1 text-xs font-medium text-sky-700"
                                            : "inline-flex rounded-full border border-amber-200 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700"
                                      }
                                    >
                                      {localizacao.status ===
                                      "CONCLUIDA"
                                        ? "Conclu\u00edda"
                                        : localizacao.status ===
                                            "EM_ANDAMENTO"
                                          ? "Em andamento"
                                          : "Pendente"}
                                    </span>
                                  </td>

                                  <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-slate-700">
                                    {
                                      localizacao.itens_planejados
                                    }
                                  </td>

                                  <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-slate-700">
                                    {
                                      localizacao.itens_processados
                                    }
                                  </td>

                                  <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-slate-700">
                                    {
                                      localizacao.itens_pendentes
                                    }
                                  </td>

                                  <td className="whitespace-nowrap px-4 py-3 text-right font-medium tabular-nums text-slate-700">
                                    {Number(
                                      localizacao.percentual,
                                    ).toLocaleString(
                                      "pt-BR",
                                      {
                                        minimumFractionDigits: 2,
                                        maximumFractionDigits: 2,
                                      },
                                    )}
                                    %
                                  </td>

                                  <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-slate-700">
                                    {
                                      localizacao.total_bipagens
                                    }
                                  </td>

                                  <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-slate-700">
                                    {Number(
                                      localizacao.quantidade_registrada,
                                    ).toLocaleString(
                                      "pt-BR",
                                    )}
                                  </td>

                                  <td className="min-w-44 px-4 py-3 text-slate-700">
                                    {localizacao
                                      .operadores.length >
                                    0
                                      ? localizacao.operadores.join(
                                          ", ",
                                        )
                                      : "-"}
                                  </td>

                                  <td className="whitespace-nowrap px-4 py-3 text-slate-700">
                                    {fmtData(
                                      localizacao.hora_inicio,
                                    )}
                                  </td>

                                  <td className="whitespace-nowrap px-4 py-3 text-slate-700">
                                    {fmtData(
                                      localizacao.ultima_atividade,
                                    )}
                                  </td>

                                  <td className="whitespace-nowrap px-4 py-3 text-slate-700">
                                    {
                                      localizacao.tempo_sem_atividade_formatado ||
                                      "-"
                                    }
                                  </td>
                                </tr>
                              ),
                            )}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="rounded-lg border border-dashed border-slate-300 bg-white p-5 text-sm text-slate-600">
                      {
                        "Nenhuma localiza\u00e7\u00e3o foi encontrada nesta rodada."
                      }
                    </div>
                  )}
                </>
              ) : rodadaLocalizacoesContexto ===
                null ? (
                <div className="rounded-lg border border-dashed border-slate-300 bg-white p-5 text-sm text-slate-600">
                  {
                    "Nenhuma rodada dispon\u00edvel para consulta."
                  }
                </div>
              ) : null}
            </div>
          </SecaoHistoricoContextual>
        )}

      {idInventarioContexto &&
        aba === "divergencias-contexto" && (
          <SecaoHistoricoContextual
            titulo={"Diverg\u00eancias"}
            descricao={
              "Diferen\u00e7as identificadas entre o estoque de refer\u00eancia e as quantidades registradas neste invent\u00e1rio."
            }
          >
            <div className="space-y-5">

              {inventarioContexto?.tipo ===
                "OFICIAL" ? (
                <div className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <div className="text-sm font-semibold text-slate-900">
                      Rodada consultada
                    </div>

                    <div className="mt-1 text-xs text-slate-500">
                      {
                        "Consulte separadamente as diverg\u00eancias registradas em cada rodada oficial."
                      }
                    </div>
                  </div>

                  <label className="block min-w-44">
                    <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                      Rodada
                    </span>

                    <select
                      value={
                        rodadaDivergenciasContexto ??
                        ""
                      }
                      disabled={
                        carregandoRodadasContexto ||
                        !rodadasContexto ||
                        rodadasContexto.rodadas
                          .length === 0
                      }
                      onChange={(evento) => {
                        const valor = Number(
                          evento.target.value,
                        );

                        setRodadaDivergenciasContexto(
                          Number.isInteger(valor) &&
                            valor > 0
                            ? valor
                            : null,
                        );
                      }}
                      className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900 outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                    >
                      {!rodadaDivergenciasContexto ? (
                        <option value="">
                          Selecione
                        </option>
                      ) : null}

                      {rodadasContexto
                        ? [
                            ...rodadasContexto.rodadas,
                          ]
                            .sort(
                              (a, b) =>
                                a.numero_rodada -
                                b.numero_rodada,
                            )
                            .map((rodada) => (
                              <option
                                key={
                                  rodada.id_rodada
                                }
                                value={
                                  rodada.numero_rodada
                                }
                              >
                                R
                                {
                                  rodada.numero_rodada
                                }
                              </option>
                            ))
                        : null}
                    </select>
                  </label>
                </div>
              ) : (
                <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
                  {
                    "Vis\u00e3o consolidada das diverg\u00eancias do invent\u00e1rio rotativo."
                  }
                </div>
              )}

              {carregandoDivergenciasContexto ? (
                <div className="rounded-lg border border-slate-200 bg-white p-5 text-sm text-slate-600">
                  {
                    "Carregando diverg\u00eancias..."
                  }
                </div>
              ) : erroDivergenciasContexto ? (
                <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                  <div className="font-semibold">
                    {
                      "N\u00e3o foi poss\u00edvel carregar as diverg\u00eancias."
                    }
                  </div>

                  <div className="mt-1">
                    {erroDivergenciasContexto}
                  </div>
                </div>
              ) : (
                <>
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">

                    <div className="rounded-lg border border-slate-200 bg-white p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                        {
                          "Diverg\u00eancias"
                        }
                      </div>

                      <div className="mt-2 text-2xl font-semibold text-slate-900">
                        {
                          divergenciasContextoHistorico.length
                        }
                      </div>
                    </div>

                    <div className="rounded-lg border border-red-200 bg-red-50/50 p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-red-700">
                        Faltas
                      </div>

                      <div className="mt-2 text-2xl font-semibold text-red-800">
                        {
                          divergenciasContextoHistorico.filter(
                            (item) =>
                              item.diferenca < 0,
                          ).length
                        }
                      </div>
                    </div>

                    <div className="rounded-lg border border-orange-200 bg-orange-50/50 p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-orange-700">
                        Sobras
                      </div>

                      <div className="mt-2 text-2xl font-semibold text-orange-800">
                        {
                          divergenciasContextoHistorico.filter(
                            (item) =>
                              item.diferenca > 0,
                          ).length
                        }
                      </div>
                    </div>

                    {inventarioContexto?.tipo ===
                    "ROTATIVO" ? (
                      <>
                        <div className="rounded-lg border border-sky-200 bg-sky-50/50 p-4">
                          <div className="text-xs font-medium uppercase tracking-wide text-sky-700">
                            Recontagem
                          </div>

                          <div className="mt-2 text-2xl font-semibold text-sky-800">
                            {
                              divergenciasContextoHistorico.filter(
                                (item) =>
                                  item.pendente_recontagem ===
                                  true,
                              ).length
                            }
                          </div>
                        </div>

                        <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-4">
                          <div className="text-xs font-medium uppercase tracking-wide text-amber-700">
                            {
                              "Aguardando decis\u00e3o"
                            }
                          </div>

                          <div className="mt-2 text-2xl font-semibold text-amber-800">
                            {
                              divergenciasContextoHistorico.filter(
                                (item) =>
                                  item.pendente_decisao ===
                                  true,
                              ).length
                            }
                          </div>
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-4">
                          <div className="text-xs font-medium uppercase tracking-wide text-emerald-700">
                            Definitivas
                          </div>

                          <div className="mt-2 text-2xl font-semibold text-emerald-800">
                            {
                              divergenciasContextoHistorico.filter(
                                (item) =>
                                  item.resultado_definitivo ===
                                  true,
                              ).length
                            }
                          </div>
                        </div>

                        <div className="rounded-lg border border-sky-200 bg-sky-50/50 p-4">
                          <div className="text-xs font-medium uppercase tracking-wide text-sky-700">
                            {
                              "Pr\u00e9vias"
                            }
                          </div>

                          <div className="mt-2 text-2xl font-semibold text-sky-800">
                            {
                              divergenciasContextoHistorico.filter(
                                (item) =>
                                  item.resultado_definitivo ===
                                  false,
                              ).length
                            }
                          </div>
                        </div>
                      </>
                    )}
                  </div>

                  {divergenciasContextoHistorico.length >
                  0 ? (
                    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
                      <table className="min-w-full text-sm">
                        <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                          <tr>
                            <th className="px-4 py-3">
                              Rodada
                            </th>

                            <th className="px-4 py-3">
                              {
                                "Localiza\u00e7\u00e3o"
                              }
                            </th>

                            <th className="px-4 py-3">
                              {"C\u00f3digo"}
                            </th>

                            <th className="px-4 py-3">
                              Lote
                            </th>

                            <th className="min-w-56 px-4 py-3">
                              {
                                "Descri\u00e7\u00e3o"
                              }
                            </th>

                            <th className="px-4 py-3 text-right">
                              Estoque
                            </th>

                            <th className="px-4 py-3 text-right">
                              Contado
                            </th>

                            <th className="px-4 py-3 text-right">
                              {
                                "Diferen\u00e7a"
                              }
                            </th>

                            <th className="px-4 py-3">
                              Status
                            </th>

                            <th className="px-4 py-3">
                              Tratamento
                            </th>

                            <th className="min-w-56 px-4 py-3">
                              Detalhe
                            </th>
                          </tr>
                        </thead>

                        <tbody className="divide-y divide-slate-100">
                          {divergenciasContextoHistorico.map(
                            (item, indice) => {
                              const tratamento =
                                item.pendente_recontagem ===
                                true
                                  ? "Recontagem"
                                  : item.pendente_decisao ===
                                      true
                                    ? "Aguardando decis\u00e3o"
                                    : item.resultado_definitivo ===
                                        true
                                      ? "Definitivo"
                                      : item.resultado_definitivo ===
                                          false
                                        ? "Pr\u00e9via"
                                        : "-";

                              return (
                                <tr
                                  key={`${item.chave}-${indice}`}
                                  className="align-top hover:bg-slate-50/70"
                                >
                                  <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-700">
                                    {item.rodada
                                      ? `R${item.rodada}`
                                      : "-"}
                                  </td>

                                  <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-700">
                                    {
                                      item.localizacao
                                    }
                                  </td>

                                  <td className="whitespace-nowrap px-4 py-3 font-semibold text-slate-900">
                                    {item.codigo}
                                  </td>

                                  <td className="whitespace-nowrap px-4 py-3 text-slate-700">
                                    {item.lote}
                                  </td>

                                  <td className="px-4 py-3 text-slate-700">
                                    {
                                      item.descricao
                                    }
                                  </td>

                                  <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-slate-700">
                                    {item.qtd_estoque.toLocaleString(
                                      "pt-BR",
                                    )}
                                  </td>

                                  <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-slate-700">
                                    {item.qtd_contada.toLocaleString(
                                      "pt-BR",
                                    )}
                                  </td>

                                  <td
                                    className={
                                      item.diferenca < 0
                                        ? "whitespace-nowrap px-4 py-3 text-right font-semibold tabular-nums text-red-700"
                                        : "whitespace-nowrap px-4 py-3 text-right font-semibold tabular-nums text-orange-700"
                                    }
                                  >
                                    {item.diferenca.toLocaleString(
                                      "pt-BR",
                                    )}
                                  </td>

                                  <td className="whitespace-nowrap px-4 py-3">
                                    <span className="inline-flex rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-medium text-slate-700">
                                      {item.status}
                                    </span>
                                  </td>

                                  <td className="whitespace-nowrap px-4 py-3 text-slate-700">
                                    {tratamento}
                                  </td>

                                  <td className="px-4 py-3 text-slate-600">
                                    {item.detalhe || "-"}
                                  </td>
                                </tr>
                              );
                            },
                          )}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-5 text-sm text-emerald-800">
                      {
                        "Nenhuma diverg\u00eancia foi encontrada para esta consulta."
                      }
                    </div>
                  )}
                </>
              )}
            </div>
          </SecaoHistoricoContextual>
        )}

      {idInventarioContexto &&
        aba === "decisoes" && (
          <SecaoHistoricoContextual
            titulo={"Decis\u00f5es"}
            descricao={
              "Decis\u00f5es e justificativas atualmente registradas para os itens que exigiram tratamento neste invent\u00e1rio."
            }
          >
            <div className="space-y-5">

              <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
                {inventarioContexto?.tipo ===
                "ROTATIVO"
                  ? "Decis\u00f5es operacionais registradas durante a an\u00e1lise c\u00edclica."
                  : "Decis\u00f5es gerenciais registradas para as diverg\u00eancias do invent\u00e1rio oficial."}
              </div>

              {carregandoDecisoesContexto ? (
                <div className="rounded-lg border border-slate-200 bg-white p-5 text-sm text-slate-600">
                  {
                    "Carregando decis\u00f5es..."
                  }
                </div>
              ) : erroDecisoesContexto ? (
                <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                  <div className="font-semibold">
                    {
                      "N\u00e3o foi poss\u00edvel carregar as decis\u00f5es."
                    }
                  </div>

                  <div className="mt-1">
                    {erroDecisoesContexto}
                  </div>
                </div>
              ) : (
                <>
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">

                    <div className="rounded-lg border border-slate-200 bg-white p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                        Itens tratados
                      </div>

                      <div className="mt-2 text-2xl font-semibold text-slate-900">
                        {
                          decisoesContextoHistorico.length
                        }
                      </div>
                    </div>

                    <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-emerald-700">
                        Registradas
                      </div>

                      <div className="mt-2 text-2xl font-semibold text-emerald-800">
                        {
                          decisoesContextoHistorico.filter(
                            (item) =>
                              item.possui_decisao,
                          ).length
                        }
                      </div>
                    </div>

                    <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-amber-700">
                        Pendentes
                      </div>

                      <div className="mt-2 text-2xl font-semibold text-amber-800">
                        {
                          decisoesContextoHistorico.filter(
                            (item) =>
                              item.pendente,
                          ).length
                        }
                      </div>
                    </div>

                    <div className="rounded-lg border border-sky-200 bg-sky-50/50 p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-sky-700">
                        Recontagem
                      </div>

                      <div className="mt-2 text-2xl font-semibold text-sky-800">
                        {
                          decisoesContextoHistorico.filter(
                            (item) =>
                              item.recontagem,
                          ).length
                        }
                      </div>
                    </div>

                    <div className="rounded-lg border border-violet-200 bg-violet-50/50 p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-violet-700">
                        Resolvidos
                      </div>

                      <div className="mt-2 text-2xl font-semibold text-violet-800">
                        {
                          decisoesContextoHistorico.filter(
                            (item) =>
                              item.resolvido,
                          ).length
                        }
                      </div>
                    </div>

                  </div>

                  {decisoesContextoHistorico.length >
                  0 ? (
                    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
                      <table className="min-w-full text-sm">
                        <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                          <tr>
                            <th className="px-4 py-3">
                              Rodada
                            </th>

                            <th className="px-4 py-3">
                              {
                                "Localiza\u00e7\u00e3o"
                              }
                            </th>

                            <th className="px-4 py-3">
                              {"C\u00f3digo"}
                            </th>

                            <th className="px-4 py-3">
                              Lote
                            </th>

                            <th className="min-w-56 px-4 py-3">
                              {
                                "Descri\u00e7\u00e3o"
                              }
                            </th>

                            <th className="px-4 py-3">
                              {
                                "Decis\u00e3o"
                              }
                            </th>

                            <th className="px-4 py-3 text-right">
                              Qtd. aprovada
                            </th>

                            <th className="min-w-64 px-4 py-3">
                              Justificativa
                            </th>

                            <th className="px-4 py-3">
                              {
                                "Usu\u00e1rio"
                              }
                            </th>

                            <th className="px-4 py-3">
                              Data / hora
                            </th>

                            <th className="px-4 py-3">
                              {
                                "Situa\u00e7\u00e3o"
                              }
                            </th>
                          </tr>
                        </thead>

                        <tbody className="divide-y divide-slate-100">
                          {decisoesContextoHistorico.map(
                            (item, indice) => (
                              <tr
                                key={`${item.chave}-${indice}`}
                                className="align-top hover:bg-slate-50/70"
                              >
                                <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-700">
                                  {item.rodada
                                    ? `R${item.rodada}`
                                    : "-"}
                                </td>

                                <td className="whitespace-nowrap px-4 py-3 text-slate-700">
                                  {
                                    item.localizacao
                                  }
                                </td>

                                <td className="whitespace-nowrap px-4 py-3 font-semibold text-slate-900">
                                  {item.codigo}
                                </td>

                                <td className="whitespace-nowrap px-4 py-3 text-slate-700">
                                  {item.lote}
                                </td>

                                <td className="px-4 py-3 text-slate-700">
                                  {
                                    item.descricao
                                  }
                                </td>

                                <td className="whitespace-nowrap px-4 py-3">
                                  {item.decisao ? (
                                    <span className="inline-flex rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-semibold text-slate-700">
                                      {item.decisao.replace(
                                        /_/g,
                                        " ",
                                      )}
                                    </span>
                                  ) : (
                                    <span className="text-slate-400">
                                      -
                                    </span>
                                  )}
                                </td>

                                <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-slate-700">
                                  {item.quantidade_aprovada !==
                                  null
                                    ? item.quantidade_aprovada.toLocaleString(
                                        "pt-BR",
                                      )
                                    : "-"}
                                </td>

                                <td className="px-4 py-3 text-slate-600">
                                  {item.justificativa ||
                                    "-"}
                                </td>

                                <td className="whitespace-nowrap px-4 py-3 text-slate-700">
                                  {item.usuario || "-"}
                                </td>

                                <td className="whitespace-nowrap px-4 py-3 text-slate-700">
                                  {fmtData(
                                    item.data_hora,
                                  )}
                                </td>

                                <td className="whitespace-nowrap px-4 py-3">
                                  <span
                                    className={
                                      item.pendente
                                        ? "inline-flex rounded-full border border-amber-200 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700"
                                        : item.recontagem
                                          ? "inline-flex rounded-full border border-sky-200 bg-sky-50 px-2 py-1 text-xs font-medium text-sky-700"
                                          : item.resolvido
                                            ? "inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700"
                                            : "inline-flex rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-medium text-slate-700"
                                    }
                                  >
                                    {item.status.replace(
                                      /_/g,
                                      " ",
                                    )}
                                  </span>
                                </td>
                              </tr>
                            ),
                          )}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="rounded-lg border border-dashed border-slate-300 bg-white p-5 text-sm text-slate-600">
                      {
                        "Nenhum item com necessidade de decis\u00e3o foi encontrado neste invent\u00e1rio."
                      }
                    </div>
                  )}

                  <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-4 text-xs leading-5 text-slate-600">
                    {
                      "Esta aba apresenta o estado atual das decis\u00f5es registradas por item. Altera\u00e7\u00f5es cronol\u00f3gicas e demais eventos permanecem dispon\u00edveis na aba Eventos."
                    }
                  </div>
                </>
              )}
            </div>
          </SecaoHistoricoContextual>
        )}


      {idInventarioContexto &&
        aba === "indicadores" && (
          <SecaoHistoricoContextual
            titulo="Indicadores"
            descricao={
              inventarioContexto?.tipo ===
              "OFICIAL"
                ? "Indicadores executivos, financeiros e operacionais consolidados do inventário oficial."
                : "Indicadores consolidados do inventário rotativo, respeitando as regras próprias do ciclo."
            }
          >
            {inventarioContexto?.tipo ===
            "OFICIAL" ? (
              <IndicadoresOficialHistorico
                analise={
                  analiseFinanceiraOficialContexto
                }
                carregando={
                  carregandoAnaliseFinanceiraOficialContexto
                }
                erro={
                  erroAnaliseFinanceiraOficialContexto
                }
                statusInventario={
                  inventarioContexto.status
                }
              />
            ) : (
              <IndicadoresRotativoHistorico
                resultadoFinal={
                  resultadoFinalContexto
                }
                carregandoResultadoFinal={
                  carregandoResultadoFinalContexto
                }
              />
            )}
          </SecaoHistoricoContextual>
        )}

      {idInventarioContexto &&
        aba === "resultado-final" && (
          <SecaoHistoricoContextual
            titulo="Resultado final"
            descricao={
              "Posi\u00e7\u00e3o consolidada ap\u00f3s o encerramento do invent\u00e1rio."
            }
          >
            {carregandoResultadoFinalContexto ? (
              <div className="rounded-lg border border-slate-200 bg-white p-5 text-sm text-slate-600">
                Carregando resultado final...
              </div>
            ) : erroResultadoFinalContexto ? (
              <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                <div className="font-semibold">
                  {
                    "N\u00e3o foi poss\u00edvel carregar o resultado final."
                  }
                </div>

                <div className="mt-1">
                  {erroResultadoFinalContexto}
                </div>
              </div>
            ) : resultadoFinalContexto ? (
              <div className="space-y-5">
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">

                  <div className="rounded-lg border border-slate-200 bg-white p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                      Acuracidade
                    </div>

                    <div className="mt-2 text-2xl font-semibold text-slate-900">
                      {Number(
                        resultadoFinalContexto.resumo
                          .acuracidade_percentual,
                      ).toLocaleString(
                        "pt-BR",
                        {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        },
                      )}
                      %
                    </div>
                  </div>

                  <div className="rounded-lg border border-slate-200 bg-white p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                      Total de itens
                    </div>

                    <div className="mt-2 text-2xl font-semibold text-slate-900">
                      {
                        resultadoFinalContexto.resumo
                          .total_itens
                      }
                    </div>
                  </div>

                  <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-emerald-700">
                      OK
                    </div>

                    <div className="mt-2 text-2xl font-semibold text-emerald-800">
                      {resultadoFinalContexto.resumo.ok}
                    </div>
                  </div>

                  <div className="rounded-lg border border-slate-200 bg-white p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                      NOK
                    </div>

                    <div className="mt-2 text-2xl font-semibold text-slate-900">
                      {resultadoFinalContexto.resumo.nok}
                    </div>
                  </div>

                  <div className="rounded-lg border border-red-200 bg-red-50/50 p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-red-700">
                      Faltas
                    </div>

                    <div className="mt-2 text-2xl font-semibold text-red-800">
                      {
                        resultadoFinalContexto.resumo
                          .faltas
                      }
                    </div>
                  </div>

                  <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-amber-700">
                      Sobras
                    </div>

                    <div className="mt-2 text-2xl font-semibold text-amber-800">
                      {
                        resultadoFinalContexto.resumo
                          .sobras
                      }
                    </div>
                  </div>

                  <div className="rounded-lg border border-slate-200 bg-white p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                      {"Diverg\u00eancias"}
                    </div>

                    <div className="mt-2 text-2xl font-semibold text-slate-900">
                      {
                        resultadoFinalContexto.resumo
                          .divergencias
                      }
                    </div>
                  </div>

                </div>

                <div className="rounded-lg border border-slate-200 bg-white">
                  <div className="border-b border-slate-100 px-4 py-3">
                    <div className="font-semibold text-slate-900">
                      Encerramento
                    </div>

                    <div className="mt-1 text-sm text-slate-500">
                      {
                        "Dados registrados na finaliza\u00e7\u00e3o do invent\u00e1rio."
                      }
                    </div>
                  </div>

                  <div className="grid gap-4 p-4 sm:grid-cols-3">
                    <div>
                      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                        Rodada final
                      </div>

                      <div className="mt-1 text-base font-semibold text-slate-900">
                        R{
                          resultadoFinalContexto
                            .rodada_final
                        }
                      </div>
                    </div>

                    <div>
                      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                        {
                          "Data / hora da finaliza\u00e7\u00e3o"
                        }
                      </div>

                      <div className="mt-1 text-base font-semibold text-slate-900">
                        {fmtData(
                          resultadoFinalContexto
                            .data_hora_finalizacao,
                        )}
                      </div>
                    </div>

                    <div>
                      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                        {
                          "Usu\u00e1rio que finalizou"
                        }
                      </div>

                      <div className="mt-1 text-base font-semibold text-slate-900">
                        {
                          resultadoFinalContexto
                            .finalizado_por ?? "-"
                        }
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ) : String(
                inventarioContexto?.status ?? "",
              )
                .trim()
                .toUpperCase() === "FINALIZADO" ? (
              <div className="rounded-lg border border-dashed border-slate-300 bg-white p-5 text-sm text-slate-600">
                {
                  "Resultado final ainda n\u00e3o dispon\u00edvel."
                }
              </div>
            ) : (
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-5 text-sm text-slate-600">
                {
                  "O resultado final ser\u00e1 disponibilizado ap\u00f3s a finaliza\u00e7\u00e3o do invent\u00e1rio."
                }
              </div>
            )}
          </SecaoHistoricoContextual>
        )}

      {idInventarioContexto &&
        aba === "eventos" && (
          <SecaoHistoricoContextual
            titulo="Eventos"
            descricao={
              "Linha do tempo audit\u00e1vel das a\u00e7\u00f5es registradas durante o ciclo deste invent\u00e1rio."
            }
          >
            {carregandoEventosContexto ? (
              <div className="rounded-lg border border-slate-200 bg-white p-5 text-sm text-slate-600">
                Carregando eventos...
              </div>
            ) : erroEventosContexto ? (
              <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                <div className="font-semibold">
                  {
                    "N\u00e3o foi poss\u00edvel carregar os eventos."
                  }
                </div>

                <div className="mt-1">
                  {erroEventosContexto}
                </div>
              </div>
            ) : auditoriaContexto ? (
              <div className="space-y-5">

                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-lg border border-slate-200 bg-white p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                      Total de eventos
                    </div>

                    <div className="mt-2 text-2xl font-semibold text-slate-900">
                      {
                        auditoriaContexto.resumo
                          .total_eventos
                      }
                    </div>
                  </div>

                  <div className="rounded-lg border border-slate-200 bg-white p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                      Primeiro evento
                    </div>

                    <div className="mt-2 text-sm font-semibold text-slate-900">
                      {fmtData(
                        auditoriaContexto.resumo
                          .primeiro_evento,
                      )}
                    </div>
                  </div>

                  <div className="rounded-lg border border-slate-200 bg-white p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                      {"\u00daltimo evento"}
                    </div>

                    <div className="mt-2 text-sm font-semibold text-slate-900">
                      {fmtData(
                        auditoriaContexto.resumo
                          .ultimo_evento,
                      )}
                    </div>
                  </div>
                </div>

                {auditoriaContexto.eventos.length >
                0 ? (
                  <div className="space-y-3">
                    {auditoriaContexto.eventos.map(
                      (evento, indice) => (
                        <article
                          key={`${evento.data_hora}-${evento.tipo_evento}-${evento.entidade_id ?? indice}`}
                          className="relative rounded-lg border border-slate-200 bg-white p-4"
                        >
                          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                            <div className="min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <h3 className="font-semibold text-slate-900">
                                  {evento.titulo ??
                                    evento.tipo_evento.replace(
                                      /_/g,
                                      " ",
                                    )}
                                </h3>

                                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                                  {evento.categoria}
                                </span>

                                {evento.status ? (
                                  <span className="rounded-full border border-slate-200 px-2 py-0.5 text-xs font-medium text-slate-600">
                                    {evento.status}
                                  </span>
                                ) : null}
                              </div>

                              <div className="mt-1 text-xs text-slate-500">
                                {fmtData(
                                  evento.data_hora,
                                )}
                              </div>
                            </div>

                            <div className="text-sm text-slate-600">
                              {evento.usuario
                                ? `Usu\u00e1rio: ${evento.usuario}`
                                : "Usu\u00e1rio n\u00e3o identificado"}
                            </div>
                          </div>

                          {evento.descricao ? (
                            <p className="mt-3 text-sm leading-6 text-slate-700">
                              {evento.descricao}
                            </p>
                          ) : null}

                          {evento.localizacao ||
                          evento.codigo ||
                          evento.lote ||
                          evento.entidade ? (
                            <div className="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-3 text-xs">
                              {evento.localizacao ? (
                                <span className="rounded-md bg-slate-50 px-2 py-1 text-slate-600">
                                  {
                                    "Localiza\u00e7\u00e3o"
                                  }
                                  :{" "}
                                  <strong className="text-slate-900">
                                    {
                                      evento.localizacao
                                    }
                                  </strong>
                                </span>
                              ) : null}

                              {evento.codigo ? (
                                <span className="rounded-md bg-slate-50 px-2 py-1 text-slate-600">
                                  C\u00f3digo:{" "}
                                  <strong className="text-slate-900">
                                    {evento.codigo}
                                  </strong>
                                </span>
                              ) : null}

                              {evento.lote ? (
                                <span className="rounded-md bg-slate-50 px-2 py-1 text-slate-600">
                                  Lote:{" "}
                                  <strong className="text-slate-900">
                                    {evento.lote}
                                  </strong>
                                </span>
                              ) : null}

                              {evento.entidade ? (
                                <span className="rounded-md bg-slate-50 px-2 py-1 text-slate-600">
                                  Entidade:{" "}
                                  <strong className="text-slate-900">
                                    {evento.entidade}
                                    {evento.entidade_id
                                      ? ` #${evento.entidade_id}`
                                      : ""}
                                  </strong>
                                </span>
                              ) : null}
                            </div>
                          ) : null}

                          {evento.motivo ||
                          evento.justificativa ? (
                            <div className="mt-4 grid gap-3 border-t border-slate-100 pt-3 md:grid-cols-2">
                              {evento.motivo ? (
                                <div>
                                  <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                                    Motivo
                                  </div>

                                  <div className="mt-1 text-sm text-slate-700">
                                    {evento.motivo}
                                  </div>
                                </div>
                              ) : null}

                              {evento.justificativa ? (
                                <div>
                                  <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                                    Justificativa
                                  </div>

                                  <div className="mt-1 text-sm text-slate-700">
                                    {
                                      evento.justificativa
                                    }
                                  </div>
                                </div>
                              ) : null}
                            </div>
                          ) : null}
                        </article>
                      ),
                    )}
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed border-slate-300 bg-white p-5 text-sm text-slate-600">
                    Nenhum evento de auditoria foi encontrado para este invent\u00e1rio.
                  </div>
                )}

                {auditoriaContexto.paginacao
                  .total_paginas > 1 ? (
                  <div className="flex flex-col gap-3 border-t border-slate-200 pt-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="text-sm text-slate-500">
                      P\u00e1gina{" "}
                      {
                        auditoriaContexto.paginacao
                          .page
                      }{" "}
                      de{" "}
                      {
                        auditoriaContexto.paginacao
                          .total_paginas
                      }
                      {" \u00b7 "}
                      {
                        auditoriaContexto.paginacao
                          .total_registros
                      }{" "}
                      evento(s)
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        className={buttonClass}
                        disabled={
                          carregandoEventosContexto ||
                          !auditoriaContexto
                            .paginacao.tem_anterior
                        }
                        onClick={() =>
                          setPaginaEventosContexto(
                            (pagina) =>
                              Math.max(
                                1,
                                pagina - 1,
                              ),
                          )
                        }
                      >
                        Anterior
                      </button>

                      <button
                        type="button"
                        className={buttonClass}
                        disabled={
                          carregandoEventosContexto ||
                          !auditoriaContexto
                            .paginacao.tem_proxima
                        }
                        onClick={() =>
                          setPaginaEventosContexto(
                            (pagina) =>
                              pagina + 1,
                          )
                        }
                      >
                        Pr\u00f3xima
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="rounded-lg border border-dashed border-slate-300 bg-white p-5 text-sm text-slate-600">
                Nenhum dado de auditoria dispon\u00edvel.
              </div>
            )}
          </SecaoHistoricoContextual>
        )}

    </div>
  );
}


function IndicadoresOficialHistorico({
  analise,
  carregando,
  erro,
  statusInventario,
}: {
  analise: AnaliseFinanceiraOficial | null;
  carregando: boolean;
  erro: string | null;
  statusInventario: string;
}) {
  if (carregando) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-5 text-sm text-slate-600">
        Carregando indicadores do inventário oficial...
      </div>
    );
  }

  if (
    String(statusInventario)
      .trim()
      .toUpperCase() !== "FINALIZADO"
  ) {
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-5 text-sm text-slate-600">
        Os indicadores financeiros do inventário oficial serão disponibilizados após a finalização.
      </div>
    );
  }

  if (erro) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        <div className="font-semibold">
          Não foi possível carregar os indicadores.
        </div>
        <div className="mt-1">{erro}</div>
      </div>
    );
  }

  if (!analise) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 bg-white p-5 text-sm text-slate-600">
        Indicadores consolidados ainda não disponíveis.
      </div>
    );
  }

  const financeiroDisponivel =
    analise.qualidade.financeiro_completo;

  const valorFinanceiro = (
    valor: number | null | undefined,
  ) =>
    financeiroDisponivel
      ? fmtMoeda(valor)
      : "N/D";

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Resumo
          titulo="Acuracidade por item"
          valor={fmtPercentual(
            analise.resumo
              .acuracidade_itens_percentual,
          )}
        />
        <Resumo
          titulo="Acuracidade por quantidade"
          valor={fmtPercentual(
            analise.resumo
              .acuracidade_quantidade_percentual,
          )}
        />
        <Resumo
          titulo="Divergência financeira"
          valor={
            analise.resumo
              .divergencia_financeira_percentual ===
            null
              ? "N/D"
              : fmtPercentual(
                  analise.resumo
                    .divergencia_financeira_percentual,
                )
          }
        />
        <Resumo
          titulo="Itens divergentes"
          valor={
            analise.resumo.itens_divergentes
          }
        />
      </div>

      <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div>
          <h3 className="font-semibold text-slate-900">
            Posição final do estoque
          </h3>
          <p className="mt-1 text-sm text-slate-500">
            Comparação entre o estoque congelado no snapshot e o resultado físico consolidado.
          </p>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">
                  Indicador
                </th>
                <th className="px-4 py-3 text-right">
                  Quantidade
                </th>
                <th className="px-4 py-3 text-right">
                  Valor
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              <LinhaQuantidadeValor
                titulo="Estoque Sistema"
                quantidade={
                  analise.estoque.sistema
                    .quantidade
                }
                valor={
                  valorFinanceiro(
                    analise.estoque.sistema
                      .valor,
                  )
                }
              />
              <LinhaQuantidadeValor
                titulo="Inventário Físico"
                quantidade={
                  analise.estoque
                    .inventario_fisico
                    .quantidade
                }
                valor={
                  valorFinanceiro(
                    analise.estoque
                      .inventario_fisico
                      .valor,
                  )
                }
              />
              <LinhaQuantidadeValor
                titulo="Diferença Líquida"
                quantidade={
                  analise.estoque
                    .diferenca_liquida
                    .quantidade
                }
                valor={
                  valorFinanceiro(
                    analise.estoque
                      .diferenca_liquida
                      .valor,
                  )
                }
                destaque
              />
            </tbody>
          </table>
        </div>
      </article>

      <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div>
          <h3 className="font-semibold text-slate-900">
            Divergências
          </h3>
          <p className="mt-1 text-sm text-slate-500">
            Faltas, sobras, divergência absoluta e saldo líquido do resultado final.
          </p>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">
                  Indicador
                </th>
                <th className="px-4 py-3 text-right">
                  Quantidade
                </th>
                <th className="px-4 py-3 text-right">
                  Valor
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              <LinhaQuantidadeValor
                titulo="Faltas"
                quantidade={
                  analise.divergencias.faltas
                    .quantidade
                }
                valor={
                  valorFinanceiro(
                    analise.divergencias.faltas
                      .valor,
                  )
                }
              />
              <LinhaQuantidadeValor
                titulo="Sobras"
                quantidade={
                  analise.divergencias.sobras
                    .quantidade
                }
                valor={
                  valorFinanceiro(
                    analise.divergencias.sobras
                      .valor,
                  )
                }
              />
              <LinhaQuantidadeValor
                titulo="Divergência Absoluta"
                quantidade={
                  analise.divergencias.absoluta
                    .quantidade
                }
                valor={
                  valorFinanceiro(
                    analise.divergencias.absoluta
                      .valor,
                  )
                }
              />
              <LinhaQuantidadeValor
                titulo="Saldo Líquido"
                quantidade={
                  analise.divergencias
                    .saldo_liquido
                    .quantidade
                }
                valor={
                  valorFinanceiro(
                    analise.divergencias
                      .saldo_liquido
                      .valor,
                  )
                }
                destaque
              />
            </tbody>
          </table>
        </div>
      </article>

      <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div>
          <h3 className="font-semibold text-slate-900">
            Indicadores complementares
          </h3>
          <p className="mt-1 text-sm text-slate-500">
            Qualidade da consolidação e disponibilidade do custo utilizado na análise financeira.
          </p>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
          <Resumo
            titulo="Itens analisados"
            valor={
              analise.resultado_final.resumo
                .total_itens
            }
          />
          <Resumo
            titulo="Itens OK"
            valor={
              analise.resultado_final.resumo.ok
            }
          />
          <Resumo
            titulo="Divergentes"
            valor={
              analise.resultado_final.resumo
                .divergencias
            }
          />
          <Resumo
            titulo="Com falta"
            valor={
              analise.resultado_final.resumo
                .faltas
            }
          />
          <Resumo
            titulo="Com sobra"
            valor={
              analise.resultado_final.resumo
                .sobras
            }
          />
          <Resumo
            titulo="Sem custo"
            valor={
              analise.qualidade.itens_sem_custo
            }
          />
          <Resumo
            titulo="Sem resultado final"
            valor={
              analise.qualidade
                .itens_sem_resultado_final
            }
          />
        </div>

        {analise.qualidade
          .itens_com_custo_fallback > 0 ? (
          <div className="mt-4 rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">
            {
              analise.qualidade
                .itens_com_custo_fallback
            }{" "}
            item(ns) utilizaram custo de fallback do histórico de recebimentos.
          </div>
        ) : null}

        {!financeiroDisponivel ? (
          <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            Existem itens sem custo disponível. Os valores financeiros dependentes desses custos são exibidos como N/D.
          </div>
        ) : null}
      </article>

      <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div>
          <h3 className="font-semibold text-slate-900">
            Movimentação dos últimos 12 meses
          </h3>
          <p className="mt-1 text-sm text-slate-500">
            Recebimentos e expedições apurados até a data de finalização do inventário.
          </p>
        </div>

        {analise.movimentacao ? (
          <>
            <div className="mt-4 grid gap-3 lg:grid-cols-3">
              <CardMovimentacao
                titulo="Recebimentos"
                documentos={
                  analise.movimentacao
                    .recebimentos.documentos
                }
                quantidade={
                  analise.movimentacao
                    .recebimentos.quantidade
                }
                valor={
                  analise.movimentacao
                    .recebimentos.valor
                }
              />
              <CardMovimentacao
                titulo="Expedições"
                documentos={
                  analise.movimentacao
                    .expedicoes.documentos
                }
                quantidade={
                  analise.movimentacao
                    .expedicoes.quantidade
                }
                valor={
                  analise.movimentacao
                    .expedicoes.valor
                }
              />
              <CardMovimentacao
                titulo="Total movimentado"
                documentos={
                  analise.movimentacao
                    .total.documentos
                }
                quantidade={
                  analise.movimentacao
                    .total.quantidade
                }
                valor={
                  analise.movimentacao
                    .total.valor_movimentado
                }
                destaque
              />
            </div>

            <div className="mt-3 text-xs text-slate-500">
              Período analisado:{" "}
              {fmtData(
                analise.movimentacao
                  .periodo.inicio,
              )}{" "}
              a{" "}
              {fmtData(
                analise.movimentacao
                  .periodo.fim,
              )}
            </div>
          </>
        ) : (
          <div className="mt-4 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
            Movimentação de 12 meses indisponível.
          </div>
        )}
      </article>

      <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div>
          <h3 className="font-semibold text-slate-900">
            Cálculo Allowance 0,5%
          </h3>
          <p className="mt-1 text-sm text-slate-500">
            Cobertura contratual calculada sobre movimentação e estoque, com impacto das divergências financeiras.
          </p>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">
                  Componente
                </th>
                <th className="px-4 py-3 text-right">
                  Valor
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              <LinhaAllowance
                titulo="Movimentação Expedição"
                valor={
                  analise.movimentacao
                    ?.expedicoes.valor ?? null
                }
              />
              <LinhaAllowance
                titulo="Movimentação Recebimento"
                valor={
                  analise.movimentacao
                    ?.recebimentos.valor ?? null
                }
              />
              <LinhaAllowance
                titulo="Volume Total Movimentado + Estoque"
                valor={
                  analise.allowance
                    .volume_total_movimentado_mais_estoque
                }
              />
              <LinhaAllowance
                titulo="Total de Perdas"
                valor={
                  analise.allowance.total_perdas
                }
              />
              <LinhaAllowance
                titulo="Total de Sobras"
                valor={
                  analise.allowance.total_sobras
                }
              />
              <LinhaAllowance
                titulo="Divergência para Allowance"
                valor={
                  analise.allowance
                    .divergencia_liquida
                }
              />
              <LinhaAllowance
                titulo="Cobertura Allowance 0,5%"
                valor={
                  analise.allowance.cobertura
                }
                destaque
              />
              <LinhaAllowance
                titulo="Penalidade de Inventário"
                valor={
                  analise.allowance.penalidade
                }
                destaque
              />
            </tbody>
          </table>
        </div>
      </article>

      <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="grid gap-4 sm:grid-cols-3">
          <CampoResumoExecutivo
            titulo="Rodada final"
            valor={`R${analise.resultado_final.rodada_final}`}
          />
          <CampoResumoExecutivo
            titulo="Finalizado em"
            valor={fmtData(
              analise.resultado_final
                .data_hora_finalizacao,
            )}
          />
          <CampoResumoExecutivo
            titulo="Finalizado por"
            valor={
              analise.resultado_final
                .finalizado_por ?? "-"
            }
          />
        </div>
      </article>
    </div>
  );
}

function IndicadoresRotativoHistorico({
  resultadoFinal,
  carregandoResultadoFinal,
}: {
  resultadoFinal: ResultadoFinalIndicadores | null;
  carregandoResultadoFinal: boolean;
}) {
  return (
    <div className="space-y-5">
      <div className="rounded-lg border border-sky-200 bg-sky-50 p-4 text-sm text-sky-900">
        O inventário rotativo utiliza regras próprias. A cobertura será calculada exclusivamente pela R1; recontagens da R2 serão apresentadas separadamente e não aumentarão a cobertura do ciclo.
      </div>

      {carregandoResultadoFinal ? (
        <div className="rounded-lg border border-slate-200 bg-white p-5 text-sm text-slate-600">
          Carregando resultado consolidado...
        </div>
      ) : resultadoFinal ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Resumo
            titulo="Acuracidade"
            valor={fmtPercentual(
              resultadoFinal.resumo
                .acuracidade_percentual,
            )}
          />
          <Resumo
            titulo="Itens"
            valor={
              resultadoFinal.resumo.total_itens
            }
          />
          <Resumo
            titulo="Divergências"
            valor={
              resultadoFinal.resumo.divergencias
            }
          />
          <Resumo
            titulo="Rodada final"
            valor={`R${resultadoFinal.rodada_final}`}
          />
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-5 text-sm text-slate-600">
          O resultado consolidado será exibido quando o ciclo estiver finalizado.
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="font-semibold text-slate-900">
            Cobertura do ciclo
          </h3>
          <p className="mt-2 text-sm text-slate-600">
            Localizações planejadas, concluídas e pendentes serão apuradas exclusivamente na R1.
          </p>
        </article>

        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="font-semibold text-slate-900">
            Recontagem direcionada
          </h3>
          <p className="mt-2 text-sm text-slate-600">
            Os itens da R2 serão exibidos separadamente, sem alterar a cobertura da R1.
          </p>
        </article>

        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="font-semibold text-slate-900">
            Divergências e tratativas
          </h3>
          <p className="mt-2 text-sm text-slate-600">
            A evolução por localização, código e lote será vinculada às decisões e tratativas do rotativo.
          </p>
        </article>
      </div>
    </div>
  );
}

function LinhaQuantidadeValor({
  titulo,
  quantidade,
  valor,
  destaque = false,
}: {
  titulo: string;
  quantidade: number;
  valor: string;
  destaque?: boolean;
}) {
  return (
    <tr
      className={
        destaque
          ? "bg-slate-50 font-semibold"
          : undefined
      }
    >
      <td className="px-4 py-3 text-slate-800">
        {titulo}
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-slate-800">
        {fmtNumero(quantidade)}
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-slate-800">
        {valor}
      </td>
    </tr>
  );
}

function CardMovimentacao({
  titulo,
  documentos,
  quantidade,
  valor,
  destaque = false,
}: {
  titulo: string;
  documentos: number;
  quantidade: number;
  valor: number | null;
  destaque?: boolean;
}) {
  return (
    <div
      className={
        destaque
          ? "rounded-xl border border-indigo-200 bg-indigo-50/60 p-4"
          : "rounded-xl border border-slate-200 bg-white p-4"
      }
    >
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {titulo}
      </div>

      <div className="mt-3 text-xl font-semibold text-slate-900">
        {fmtMoeda(valor)}
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
        <div>
          <div className="text-xs text-slate-500">
            Documentos
          </div>
          <div className="font-semibold text-slate-800">
            {fmtNumero(documentos)}
          </div>
        </div>

        <div>
          <div className="text-xs text-slate-500">
            Unidades
          </div>
          <div className="font-semibold text-slate-800">
            {fmtNumero(quantidade)}
          </div>
        </div>
      </div>
    </div>
  );
}

function LinhaAllowance({
  titulo,
  valor,
  destaque = false,
}: {
  titulo: string;
  valor: number | null;
  destaque?: boolean;
}) {
  return (
    <tr
      className={
        destaque
          ? "bg-slate-50 font-semibold"
          : undefined
      }
    >
      <td className="px-4 py-3 text-slate-800">
        {titulo}
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-slate-800">
        {fmtMoeda(
          valor !== null && Object.is(valor, -0)
            ? 0
            : valor,
        )}
      </td>
    </tr>
  );
}

function SecaoHistoricoContextual({
  titulo,
  descricao,
  children,
}: {
  titulo: string;
  descricao: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-slate-50/40 p-5">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-slate-900">
          {titulo}
        </h2>

        <p className="mt-1 text-sm text-slate-600">
          {descricao}
        </p>
      </div>

      {children}
    </section>
  );
}

function CampoContexto({
  titulo,
  valor,
}: {
  titulo: string;
  valor: string | number;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50/60 p-3">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
        {titulo}
      </div>

      <div className="mt-1 truncate text-sm font-semibold text-slate-900">
        {valor}
      </div>
    </div>
  );
}

function Resumo({
  titulo,
  valor,
}: {
  titulo: string;
  valor: string | number;
}) {
  return (
    <div className="group relative overflow-hidden rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm transition hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md">
      <div className="absolute inset-y-0 left-0 w-1 bg-primary/70 opacity-70 transition group-hover:opacity-100" />

      <div className="pl-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
        {titulo}
      </div>

      <div className="mt-1 pl-1 text-xl font-semibold text-slate-900">
        {valor}
      </div>
    </div>
  );
}

function Campo({ nome, valor }: { nome: string; valor: string | number }) {
  return (
    <div>
      <div className="text-slate-500">{nome}</div>
      <div className="font-medium text-slate-900">{valor}</div>
    </div>
  );
}

function CampoResumoExecutivo({
  titulo,
  valor,
}: {
  titulo: string;
  valor: ReactNode;
}) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {titulo}
      </dt>
      <dd className="mt-1 font-semibold text-slate-900">
        {valor}
      </dd>
    </div>
  );
}

function Tabela({
  children,
  minWidthClass = "min-w-[1180px]",
}: {
  children: ReactNode;
  minWidthClass?: string;
}) {
  return (
    <div className="relative overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <table
        className={`${minWidthClass} w-full border-separate border-spacing-0 text-left text-sm`}
      >
        {children}
      </table>
    </div>
  );
}

function Th({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <th className="sticky top-0 z-10 whitespace-nowrap border-b border-slate-200 bg-slate-50 px-3 py-3 text-xs font-semibold uppercase tracking-wide text-slate-600">
      {children}
    </th>
  );
}

function Td({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <td className="whitespace-nowrap px-3 py-3 text-slate-800">
      {children}
    </td>
  );
}

function fmtNumero(value: number | null | undefined) {
  if (value === null || value === undefined) return "-";
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(value);
}

function fmtMoeda(
  value: number | null | undefined,
) {
  if (value === null || value === undefined) {
    return "N/D";
  }

  return new Intl.NumberFormat(
    "pt-BR",
    {
      style: "currency",
      currency: "BRL",
    },
  ).format(value);
}

function fmtPercentual(
  value: number | null | undefined,
) {
  if (value === null || value === undefined) {
    return "-";
  }

  return `${Number(value).toLocaleString(
    "pt-BR",
    {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    },
  )}%`;
}

function fmtData(value: string | null | undefined) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("pt-BR");
}
