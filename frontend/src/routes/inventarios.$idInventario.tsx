import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  ArrowLeft,
  Ban,
  Boxes,
  Loader2,
  MapPin,
  Settings2,
  ShieldCheck,
  User,
} from "lucide-react";

import { obterUsuarioSalvo } from "@/services/authService";
import {
  buscarAnaliseGestor,
  type AnaliseGestor,
} from "@/services/gestorService";
import {
  buscarAuditoriaInventario,
  type AuditoriaResponse,
} from "@/services/auditoriaService";
import { salvarInventarioAtual } from "@/lib/inventarioAtual";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

import {
  consultarConfiguracaoPorInventario,
  consultarEscopoInventario,
  cancelarInventario,
  consultarInventarioDetalhe,
  consultarSnapshotInventario,
  consultarStatusSnapshot,
  consultarStatusEscopoInventario,
  gerarSnapshot,
  listarEstoqueCandidatos,
  listarLocalizacoesCandidatas,
  salvarLocalizacoesEscopo,
} from "@/services/inventarioService";
import {
  buscarPreviewProximaRodada,
  buscarRodadaAtual,
  gerarProximaRodada,
  sincronizarLocalizacoesRodada,
  type PreviewProximaRodadaResposta,
  type RodadaAtual,
} from "@/services/rodadasService";

import {
  buscarSugestoesCicloRotativo,
  consultarContextoLocalizacaoRotativa,
  consultarLocalizacoesPendentesCicloRotativo,
  ignorarLocalizacaoCicloRotativo,
} from "@/services/rotativoService";
import type {
  ContextoLocalizacaoRotativaResposta,
  SugestaoCicloRotativo,
  SugestoesCicloRotativoResposta,
} from "@/services/rotativoService";
import type {
  ConfiguracaoInventarioAplicada,
  EscopoInventario,
  EstoqueCandidatosInventario,
  InventarioDetalhe,
  LocalizacoesCandidatasInventario,
  StatusSnapshotInventario,
  StatusEscopoInventario,
} from "@/types/inventory";

import { OcorrenciasInventario } from "@/components/tratativas/OcorrenciasInventario";

import { PainelFluxoInventario } from "@/components/inventarios/PainelFluxoInventario";

export const Route = createFileRoute("/inventarios/$idInventario")({
  head: () => ({
    meta: [
      {
        title: "Detalhes do Invent\u00e1rio \u2014 SGI",
      },
    ],
  }),
  component: InventarioDetalheRoutePage,
});

function InventarioDetalheRoutePage() {
  const { idInventario } = Route.useParams();

  return <InventarioDetalhePage idInventario={idInventario} />;
}

interface InventarioDetalhePageProps {
  idInventario: string;
  paginaEstoqueEscopo?: boolean;
  paginaControleRodadas?: boolean;
}

export function InventarioDetalhePage({
  idInventario,
  paginaEstoqueEscopo = false,
  paginaControleRodadas = false,
}: InventarioDetalhePageProps) {
  const navigate = useNavigate();
  const consultaAutomaticaExecutada = useRef(false);
  const contextoLocalizacaoRef = useRef<HTMLDivElement | null>(null);

  const [inventario, setInventario] = useState<InventarioDetalhe | null>(null);

  const [configuracaoInventario, setConfiguracaoInventario] =
    useState<ConfiguracaoInventarioAplicada | null>(null);

  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const [estoqueCandidato, setEstoqueCandidato] =
    useState<LocalizacoesCandidatasInventario | null>(null);

  const [estoqueDetalhado, setEstoqueDetalhado] =
    useState<EstoqueCandidatosInventario | null>(null);

  const [consultandoEstoque, setConsultandoEstoque] = useState(false);

  const [erroEstoque, setErroEstoque] = useState<string | null>(null);

  const [escopo, setEscopo] = useState<EscopoInventario | null>(null);

  const [modoEscopo, setModoEscopo] = useState<
    "SUGESTOES" | "COMPLETO" | "ESPECIFICAS"
  >("ESPECIFICAS");

  const [localizacoesSelecionadas, setLocalizacoesSelecionadas] = useState<
    string[]
  >([]);

  const [sugestoesCiclo, setSugestoesCiclo] =
    useState<SugestoesCicloRotativoResposta | null>(null);

  const [localizacoesCiclo, setLocalizacoesCiclo] = useState<Awaited<
    ReturnType<typeof consultarLocalizacoesPendentesCicloRotativo>
  > | null>(null);

  const [contextoLocalizacaoRotativa, setContextoLocalizacaoRotativa] =
    useState<ContextoLocalizacaoRotativaResposta | null>(null);

  const [consultandoContextoLocalizacao, setConsultandoContextoLocalizacao] =
    useState<string | null>(null);

  const [erroContextoLocalizacao, setErroContextoLocalizacao] = useState<
    string | null
  >(null);

  const [localizacaoParaIgnorar, setLocalizacaoParaIgnorar] = useState<{
    idCicloLocalizacao: number;
    localizacao: string;
  } | null>(null);
  const [motivoIgnorarLocalizacao, setMotivoIgnorarLocalizacao] = useState("");
  const [ignorandoLocalizacao, setIgnorandoLocalizacao] = useState(false);
  const [erroIgnorarLocalizacao, setErroIgnorarLocalizacao] = useState<
    string | null
  >(null);

  const [filtroLocalizacao, setFiltroLocalizacao] = useState("");

  const [salvandoEscopo, setSalvandoEscopo] = useState(false);

  const [erroEscopo, setErroEscopo] = useState<string | null>(null);

  const [statusSnapshot, setStatusSnapshot] =
    useState<StatusSnapshotInventario | null>(null);

  const [statusEscopoInventario, setStatusEscopoInventario] =
    useState<StatusEscopoInventario | null>(null);

  const [gerandoSnapshot, setGerandoSnapshot] = useState(false);

  const [rodadaOficial, setRodadaOficial] = useState<RodadaAtual | null>(null);

  const [previewRodadaOficial, setPreviewRodadaOficial] =
    useState<PreviewProximaRodadaResposta | null>(null);

  const [carregandoRodadaOficial, setCarregandoRodadaOficial] = useState(false);

  const [processandoRodadaOficial, setProcessandoRodadaOficial] =
    useState(false);

  const [erroRodadaOficial, setErroRodadaOficial] = useState<string | null>(
    null,
  );

  const [confirmacaoGeracaoRodadaAberta, setConfirmacaoGeracaoRodadaAberta] =
    useState(false);

  const [erroSnapshot, setErroSnapshot] = useState<string | null>(null);

  const [cancelamentoAberto, setCancelamentoAberto] = useState(false);

  const [motivoCancelamento, setMotivoCancelamento] = useState("");

  const [cancelandoInventario, setCancelandoInventario] = useState(false);

  const [analiseGestor, setAnaliseGestor] = useState<AnaliseGestor | null>(
    null,
  );

  const [carregandoAnaliseGestor, setCarregandoAnaliseGestor] = useState(false);

  const [erroAnaliseGestor, setErroAnaliseGestor] = useState<string | null>(
    null,
  );

  const [auditoriaResumo, setAuditoriaResumo] =
    useState<AuditoriaResponse | null>(null);

  const [carregandoAuditoria, setCarregandoAuditoria] = useState(false);

  const [erroAuditoria, setErroAuditoria] = useState<string | null>(null);

  useEffect(() => {
    if (paginaEstoqueEscopo || paginaControleRodadas || !inventario) {
      setAuditoriaResumo(null);
      setErroAuditoria(null);
      setCarregandoAuditoria(false);
      return;
    }

    const controller = new AbortController();

    setCarregandoAuditoria(true);
    setErroAuditoria(null);

    void buscarAuditoriaInventario(
      inventario.id_inventario,
      1,
      5,
      controller.signal,
    )
      .then((resposta) => {
        if (!controller.signal.aborted) {
          setAuditoriaResumo(resposta);
        }
      })
      .catch((falha: unknown) => {
        if (controller.signal.aborted) {
          return;
        }

        setAuditoriaResumo(null);
        setErroAuditoria(
          falha instanceof Error
            ? falha.message
            : "N\u00e3o foi poss\u00edvel carregar a auditoria.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setCarregandoAuditoria(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [inventario, paginaEstoqueEscopo, paginaControleRodadas]);

  useEffect(() => {
    if (
      paginaEstoqueEscopo ||
      paginaControleRodadas ||
      !inventario ||
      inventario.tipo !== "OFICIAL" ||
      !inventario.em_analise_gestor
    ) {
      setAnaliseGestor(null);
      setErroAnaliseGestor(null);
      setCarregandoAnaliseGestor(false);
      return;
    }

    const controller = new AbortController();

    setCarregandoAnaliseGestor(true);
    setErroAnaliseGestor(null);

    void buscarAnaliseGestor(inventario.id_inventario, controller.signal)
      .then((resposta) => {
        if (!controller.signal.aborted) {
          setAnaliseGestor(resposta);
        }
      })
      .catch((falha: unknown) => {
        if (controller.signal.aborted) {
          return;
        }

        setAnaliseGestor(null);
        setErroAnaliseGestor(
          falha instanceof Error
            ? falha.message
            : "N\u00e3o foi poss\u00edvel carregar o resumo gerencial.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setCarregandoAnaliseGestor(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [inventario, paginaEstoqueEscopo, paginaControleRodadas]);

  useEffect(() => {
    const id = Number(idInventario);

    if (Number.isInteger(id) && id > 0) {
      salvarInventarioAtual(id);
    }

    async function carregar() {
      if (!Number.isInteger(id) || id <= 0) {
        setErro("Inventário inválido.");
        setCarregando(false);
        return;
      }

      setCarregando(true);
      setErro(null);

      try {
        const [
          dados,
          statusSnapshotAtual,
          configuracaoAtual,
          statusEscopoAtual,
        ] = await Promise.all([
          consultarInventarioDetalhe(id),
          consultarStatusSnapshot(id),
          consultarConfiguracaoPorInventario(id),
          consultarStatusEscopoInventario(id),
        ]);

        setInventario(dados);

        salvarInventarioAtual(dados.id_inventario, dados.tipo);
        setStatusSnapshot(statusSnapshotAtual);
        setConfiguracaoInventario(configuracaoAtual);
        setStatusEscopoInventario(statusEscopoAtual);

        if (statusSnapshotAtual.snapshot_gerado) {
          const [snapshotAtual, escopoAtual] = await Promise.all([
            consultarSnapshotInventario(id),
            consultarEscopoInventario(id),
          ]);

          const resumoPorLocalizacao = new Map<
            string,
            {
              registros: number;
              itens: Set<string>;
              lotes: Set<string>;
              quantidade_total: number;
            }
          >();

          for (const item of snapshotAtual.itens) {
            let resumo = resumoPorLocalizacao.get(item.localizacao);

            if (!resumo) {
              resumo = {
                registros: 0,
                itens: new Set<string>(),
                lotes: new Set<string>(),
                quantidade_total: 0,
              };

              resumoPorLocalizacao.set(item.localizacao, resumo);
            }

            resumo.registros += 1;
            resumo.itens.add(item.codigo);

            if (item.lote !== null) {
              resumo.lotes.add(item.lote);
            }

            resumo.quantidade_total += item.saldo_inventario;
          }

          const localizacoes = Array.from(resumoPorLocalizacao.entries())
            .map(([localizacao, resumo]) => ({
              localizacao,
              registros: resumo.registros,
              itens_distintos: resumo.itens.size,
              lotes_distintos: resumo.lotes.size,
              quantidade_total: resumo.quantidade_total,
            }))
            .sort((a, b) =>
              a.localizacao.localeCompare(b.localizacao, "pt-BR"),
            );

          const resumoSnapshot: LocalizacoesCandidatasInventario = {
            id_inventario: snapshotAtual.id_inventario,
            codigo_inventario: snapshotAtual.codigo_inventario,
            tipo: snapshotAtual.tipo,
            cliente: snapshotAtual.cliente,
            cliente_id: snapshotAtual.cliente_id,
            c_armazem: snapshotAtual.c_armazem,
            total_localizacoes: localizacoes.length,
            localizacoes,
          };

          setEstoqueDetalhado(snapshotAtual);

          setEstoqueCandidato(resumoSnapshot);

          setEscopo(escopoAtual);

          setLocalizacoesSelecionadas([]);
          setFiltroLocalizacao("");
          setModoEscopo("ESPECIFICAS");
        }
      } catch (e) {
        setErro(
          e instanceof Error ? e.message : "Erro ao consultar o inventário.",
        );
      } finally {
        setCarregando(false);
      }
    }

    void carregar();
  }, [idInventario]);

  useEffect(() => {
    if (!inventario || inventario.tipo !== "OFICIAL") {
      setRodadaOficial(null);
      setPreviewRodadaOficial(null);
      setErroRodadaOficial(null);
      return;
    }

    void carregarControleRodadasOficial();
  }, [inventario?.id_inventario, inventario?.tipo, inventario?.status]);

  const inventarioEncerrado =
    inventario?.status === "FINALIZADO" || inventario?.status === "CANCELADO";

  const escopoBloqueado =
    inventarioEncerrado ||
    statusEscopoInventario?.pode_alterar_escopo === false;

  async function carregarControleRodadasOficial() {
    if (!inventario || inventario.tipo !== "OFICIAL") {
      return;
    }

    setCarregandoRodadaOficial(true);
    setErroRodadaOficial(null);

    try {
      const rodada = await buscarRodadaAtual(inventario.id_inventario);

      setRodadaOficial(rodada);
      const detalheAtual = await consultarInventarioDetalhe(
        inventario.id_inventario,
      );
      setInventario(detalheAtual);

      if (inventario.status === "ABERTO") {
        try {
          const preview = await buscarPreviewProximaRodada(
            inventario.id_inventario,
          );

          setPreviewRodadaOficial(preview);
        } catch (e) {
          setPreviewRodadaOficial(null);

          setErroRodadaOficial(
            e instanceof Error
              ? e.message
              : "Erro ao consultar a proxima rodada.",
          );
        }
      } else {
        setPreviewRodadaOficial(null);
      }
    } catch (e) {
      setRodadaOficial(null);
      setPreviewRodadaOficial(null);

      setErroRodadaOficial(
        e instanceof Error ? e.message : "Erro ao consultar a rodada atual.",
      );
    } finally {
      setCarregandoRodadaOficial(false);
    }
  }

  async function sincronizarLocalizacoesOficial() {
    if (!inventario || inventario.tipo !== "OFICIAL" || !rodadaOficial) {
      return;
    }

    setProcessandoRodadaOficial(true);
    setErroRodadaOficial(null);

    try {
      const resposta = await sincronizarLocalizacoesRodada(
        inventario.id_inventario,
        rodadaOficial.id_rodada,
      );

      toast.success(
        `${resposta.resultado.localizacoes_geradas} localizacao(oes) sincronizada(s).`,
      );

      await carregarControleRodadasOficial();
    } catch (e) {
      const mensagem =
        e instanceof Error ? e.message : "Erro ao sincronizar localizacoes.";

      setErroRodadaOficial(mensagem);
      toast.error(mensagem);
    } finally {
      setProcessandoRodadaOficial(false);
    }
  }

  async function gerarProximaRodadaOficial() {
    if (
      !inventario ||
      carregandoRodadaOficial ||
      processandoRodadaOficial ||
      inventario.tipo !== "OFICIAL" ||
      !previewRodadaOficial?.preview.pode_criar
    ) {
      return;
    }

    setProcessandoRodadaOficial(true);
    setErroRodadaOficial(null);

    try {
      const resposta = await gerarProximaRodada(inventario.id_inventario);

      const proxima = resposta.proxima_rodada;

      toast.success(
        proxima.criada
          ? `Rodada ${proxima.numero_rodada} gerada com sucesso.`
          : (proxima.mensagem ?? "A proxima rodada ja existe."),
      );

      await carregarControleRodadasOficial();
    } catch (e) {
      const mensagem =
        e instanceof Error ? e.message : "Erro ao gerar a proxima rodada.";

      setErroRodadaOficial(mensagem);
      toast.error(mensagem);
    } finally {
      setProcessandoRodadaOficial(false);
    }
  }

  async function cancelarInventarioAtual() {
    if (!inventario || inventario.status !== "ABERTO") {
      return;
    }

    const motivo = motivoCancelamento.trim();

    if (!motivo) {
      toast.error("Informe o motivo do cancelamento.");
      return;
    }

    setCancelandoInventario(true);

    try {
      const resposta = await cancelarInventario(inventario.id_inventario, {
        motivo,
      });

      const inventarioAtualizado = await consultarInventarioDetalhe(
        inventario.id_inventario,
      );

      setInventario(inventarioAtualizado);
      setCancelamentoAberto(false);
      setMotivoCancelamento("");

      toast.success(resposta.mensagem || "Inventário cancelado com sucesso.");
    } catch (e) {
      const mensagem =
        e instanceof Error
          ? e.message
          : "Não foi possível cancelar o inventário.";

      toast.error(mensagem);
    } finally {
      setCancelandoInventario(false);
    }
  }

  async function consultarEstoque() {
    if (!inventario) {
      return;
    }

    setConsultandoEstoque(true);
    setErroEstoque(null);
    setContextoLocalizacaoRotativa(null);
    setErroContextoLocalizacao(null);

    try {
      const [
        dados,
        escopoAtual,
        estoqueAtual,
        cicloRotativoAtual,
        sugestoesRotativoAtual,
      ] = await Promise.all([
        listarLocalizacoesCandidatas(inventario.id_inventario),
        consultarEscopoInventario(inventario.id_inventario),
        listarEstoqueCandidatos(inventario.id_inventario),
        inventario.tipo === "ROTATIVO"
          ? consultarLocalizacoesPendentesCicloRotativo(
              inventario.cliente_id,
              inventario.armazem,
            )
          : Promise.resolve(null),
        inventario.tipo === "ROTATIVO"
          ? buscarSugestoesCicloRotativo(
              inventario.cliente_id,
              inventario.armazem,
              20,
            )
          : Promise.resolve(null),
      ]);

      setLocalizacoesCiclo(cicloRotativoAtual);

      let dadosDisponiveis = dados;
      let estoqueDisponivel = estoqueAtual;

      if (inventario.tipo === "ROTATIVO") {
        if (
          !cicloRotativoAtual ||
          !cicloRotativoAtual.possui_ciclo ||
          !cicloRotativoAtual.ciclo
        ) {
          throw new Error(
            "O inventario ROTATIVO exige um ciclo rotativo aberto.",
          );
        }

        const localizacoesPendentes = new Set(
          cicloRotativoAtual.localizacoes.map((item) =>
            item.localizacao.trim().toUpperCase(),
          ),
        );

        const localizacoesFiltradas = dados.localizacoes.filter((item) =>
          localizacoesPendentes.has(item.localizacao.trim().toUpperCase()),
        );

        const itensFiltrados = estoqueAtual.itens.filter((item) =>
          localizacoesPendentes.has(item.localizacao.trim().toUpperCase()),
        );

        dadosDisponiveis = {
          ...dados,
          total_localizacoes: localizacoesFiltradas.length,
          localizacoes: localizacoesFiltradas,
        };

        estoqueDisponivel = {
          ...estoqueAtual,
          total: itensFiltrados.length,
          itens: itensFiltrados,
        };
      }

      setSugestoesCiclo(
        inventario.tipo === "ROTATIVO" ? sugestoesRotativoAtual : null,
      );

      setEstoqueCandidato(dadosDisponiveis);

      setEstoqueDetalhado(estoqueDisponivel);

      setEscopo(escopoAtual);
      setLocalizacoesSelecionadas([]);
      setFiltroLocalizacao("");
      setModoEscopo("ESPECIFICAS");
      setErroEscopo(null);
    } catch (e) {
      setEstoqueCandidato(null);
      setEstoqueDetalhado(null);

      setErroEstoque(
        e instanceof Error
          ? e.message
          : "Erro ao consultar o estoque candidato.",
      );
    } finally {
      setConsultandoEstoque(false);
    }
  }

  useEffect(() => {
    if (
      !paginaEstoqueEscopo ||
      !inventario ||
      consultaAutomaticaExecutada.current
    ) {
      return;
    }

    consultaAutomaticaExecutada.current = true;

    if (estoqueCandidato || statusSnapshot?.snapshot_gerado) {
      return;
    }

    void consultarEstoque();
  }, [
    paginaEstoqueEscopo,
    inventario?.id_inventario,
    estoqueCandidato,
    statusSnapshot?.snapshot_gerado,
  ]);

  function localizacaoJaSalva(localizacao: string) {
    const normalizada = localizacao.trim().toUpperCase();

    return Boolean(
      escopo?.localizacoes.some(
        (item) =>
          item.selecionado &&
          item.localizacao.trim().toUpperCase() === normalizada,
      ),
    );
  }

  function obterSugestoesAtivas(): SugestaoCicloRotativo[] {
    if (!sugestoesCiclo) {
      return [];
    }

    return [
      sugestoesCiclo.sugestao_principal,
      ...sugestoesCiclo.proximas_sugestoes,
    ].filter((item): item is SugestaoCicloRotativo => item !== null);
  }

  function abrirIgnorarLocalizacaoRotativa(
    idCicloLocalizacao: number,
    localizacao: string,
  ) {
    setLocalizacaoParaIgnorar({
      idCicloLocalizacao,
      localizacao,
    });
    setMotivoIgnorarLocalizacao("");
    setErroIgnorarLocalizacao(null);
  }

  function fecharIgnorarLocalizacaoRotativa() {
    if (ignorandoLocalizacao) {
      return;
    }

    setLocalizacaoParaIgnorar(null);
    setMotivoIgnorarLocalizacao("");
    setErroIgnorarLocalizacao(null);
  }

  async function confirmarIgnorarLocalizacaoRotativa() {
    if (!localizacaoParaIgnorar) {
      return;
    }

    const motivo = motivoIgnorarLocalizacao.trim();

    if (!motivo) {
      setErroIgnorarLocalizacao(
        "Informe o motivo para ignorar esta localizacao.",
      );
      return;
    }

    const usuario = obterUsuarioSalvo();

    if (!usuario?.login) {
      setErroIgnorarLocalizacao(
        "Nao foi possivel identificar o usuario autenticado.",
      );
      return;
    }

    setIgnorandoLocalizacao(true);
    setErroIgnorarLocalizacao(null);

    try {
      const resposta = await ignorarLocalizacaoCicloRotativo({
        id_ciclo_localizacao: localizacaoParaIgnorar.idCicloLocalizacao,
        motivo,
        usuario: usuario.login,
      });

      const localizacaoNormalizada = localizacaoParaIgnorar.localizacao
        .trim()
        .toUpperCase();

      setLocalizacoesCiclo((atual) =>
        atual
          ? {
              ...atual,
              localizacoes: atual.localizacoes.filter(
                (item) =>
                  item.id_ciclo_localizacao !==
                  localizacaoParaIgnorar.idCicloLocalizacao,
              ),
              ...(atual.ciclo && resposta.ciclo
                ? {
                    ciclo: {
                      ...atual.ciclo,
                      status: resposta.ciclo.ciclo_concluido
                        ? "CONCLUIDO"
                        : atual.ciclo.status,
                      total_localizacoes: resposta.ciclo.total_localizacoes,
                      localizacoes_contadas:
                        resposta.ciclo.localizacoes_contadas,
                      localizacoes_ignoradas:
                        resposta.ciclo.localizacoes_ignoradas,
                      localizacoes_processadas:
                        resposta.ciclo.localizacoes_processadas,
                      localizacoes_pendentes:
                        resposta.ciclo.localizacoes_pendentes,
                      percentual_cobertura: resposta.ciclo.percentual_cobertura,
                    },
                  }
                : {}),
            }
          : atual,
      );

      setLocalizacoesSelecionadas((atuais) =>
        atuais.filter(
          (localizacao) =>
            localizacao.trim().toUpperCase() !== localizacaoNormalizada,
        ),
      );

      setEstoqueCandidato((atual) => {
        if (!atual) return atual;

        const localizacoes = atual.localizacoes.filter(
          (item) =>
            item.localizacao.trim().toUpperCase() !== localizacaoNormalizada,
        );

        return {
          ...atual,
          total_localizacoes: localizacoes.length,
          localizacoes,
        };
      });

      setEstoqueDetalhado((atual) => {
        if (!atual) return atual;

        const itens = atual.itens.filter(
          (item) =>
            item.localizacao.trim().toUpperCase() !== localizacaoNormalizada,
        );

        return {
          ...atual,
          total: itens.length,
          itens,
        };
      });

      setLocalizacaoParaIgnorar(null);
      setMotivoIgnorarLocalizacao("");

      toast.success(
        resposta.ciclo?.ciclo_concluido
          ? "Localizacao ignorada e ciclo concluido automaticamente."
          : resposta.atualizado
            ? "Localizacao ignorada no ciclo com sucesso."
            : "A localizacao ja estava ignorada.",
      );
    } catch (e) {
      setErroIgnorarLocalizacao(
        e instanceof Error
          ? e.message
          : "Nao foi possivel ignorar a localizacao.",
      );
    } finally {
      setIgnorandoLocalizacao(false);
    }
  }

  async function abrirContextoLocalizacaoRotativa(localizacao: string) {
    if (!inventario || inventario.tipo !== "ROTATIVO") {
      return;
    }

    const localizacaoNormalizada = localizacao.trim().toUpperCase();

    setConsultandoContextoLocalizacao(localizacaoNormalizada);
    setErroContextoLocalizacao(null);
    setContextoLocalizacaoRotativa(null);

    try {
      const resposta = await consultarContextoLocalizacaoRotativa({
        clienteId: inventario.cliente_id,
        armazem: inventario.armazem,
        localizacao: localizacaoNormalizada,
        limiteHistorico: 10,
      });

      setContextoLocalizacaoRotativa(resposta);

      requestAnimationFrame(() => {
        contextoLocalizacaoRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      });
    } catch (e) {
      setErroContextoLocalizacao(
        e instanceof Error
          ? e.message
          : "Erro ao consultar o contexto da localização.",
      );
    } finally {
      setConsultandoContextoLocalizacao(null);
    }
  }

  function selecionarModo(modo: "SUGESTOES" | "COMPLETO" | "ESPECIFICAS") {
    setModoEscopo(modo);
    setErroEscopo(null);

    if (modo !== "SUGESTOES") {
      setContextoLocalizacaoRotativa(null);
      setErroContextoLocalizacao(null);
    }

    if (!estoqueCandidato) {
      setLocalizacoesSelecionadas([]);
      return;
    }

    if (modo === "SUGESTOES") {
      setLocalizacoesSelecionadas([]);
      return;
    }

    if (modo === "COMPLETO") {
      const pendentes = estoqueCandidato.localizacoes
        .map((item) => item.localizacao)
        .filter((localizacao) => !localizacaoJaSalva(localizacao));

      setLocalizacoesSelecionadas(pendentes);
      return;
    }

    setLocalizacoesSelecionadas([]);
  }

  function alternarLocalizacao(localizacao: string) {
    if (localizacaoJaSalva(localizacao)) {
      return;
    }

    setModoEscopo("ESPECIFICAS");
    setErroEscopo(null);

    setLocalizacoesSelecionadas((atuais) =>
      atuais.includes(localizacao)
        ? atuais.filter((item) => item !== localizacao)
        : [...atuais, localizacao],
    );
  }

  function selecionarTodasFiltradas() {
    if (!estoqueCandidato) {
      return;
    }

    const termo = filtroLocalizacao.trim().toUpperCase();

    const novas = estoqueCandidato.localizacoes
      .filter((item) => item.localizacao.toUpperCase().includes(termo))
      .map((item) => item.localizacao)
      .filter((localizacao) => !localizacaoJaSalva(localizacao));

    setModoEscopo("ESPECIFICAS");
    setErroEscopo(null);
    setLocalizacoesSelecionadas(Array.from(new Set(novas)));
  }

  function limparSelecao() {
    setModoEscopo("ESPECIFICAS");
    setLocalizacoesSelecionadas([]);
    setErroEscopo(null);
  }

  async function salvarEscopo() {
    if (!inventario) {
      return;
    }

    if (localizacoesSelecionadas.length === 0) {
      setErroEscopo("Selecione pelo menos uma nova localização.");
      return;
    }

    const usuario = obterUsuarioSalvo();

    if (!usuario?.login) {
      setErroEscopo("Não foi possível identificar o usuário autenticado.");
      return;
    }

    setSalvandoEscopo(true);
    setErroEscopo(null);

    try {
      const resposta = await salvarLocalizacoesEscopo(
        inventario.id_inventario,
        {
          localizacoes: localizacoesSelecionadas,
          criado_por: usuario.login,
        },
      );

      const [escopoAtualizado, statusSnapshotAtualizado] = await Promise.all([
        consultarEscopoInventario(inventario.id_inventario),
        consultarStatusSnapshot(inventario.id_inventario),
      ]);

      setEscopo(escopoAtualizado);
      setStatusSnapshot(statusSnapshotAtualizado);
      setLocalizacoesSelecionadas([]);
      setModoEscopo("ESPECIFICAS");

      toast.success(resposta.mensagem || "Escopo atualizado com sucesso.");
    } catch (e) {
      const mensagem =
        e instanceof Error ? e.message : "Erro ao salvar o escopo.";

      setErroEscopo(mensagem);
      toast.error(mensagem);
    } finally {
      setSalvandoEscopo(false);
    }
  }

  async function gerarSnapshotInventario() {
    if (!inventario) {
      return;
    }

    if ((escopo?.resumo.selecionadas ?? 0) === 0) {
      const mensagem =
        "Salve pelo menos uma localização no escopo antes de gerar o snapshot.";

      setErroSnapshot(mensagem);
      toast.error(mensagem);
      return;
    }

    if (localizacoesSelecionadas.length > 0) {
      const mensagem =
        "Salve as novas localizações selecionadas antes de gerar o snapshot.";

      setErroSnapshot(mensagem);
      toast.error(mensagem);
      return;
    }

    if (inventarioEncerrado) {
      return;
    }

    if (statusSnapshot?.snapshot_gerado) {
      return;
    }

    setGerandoSnapshot(true);
    setErroSnapshot(null);

    try {
      const resposta = await gerarSnapshot(inventario.id_inventario);

      const [
        statusAtualizado,
        snapshotAtual,
        escopoAtualizado,
        statusEscopoAtualizado,
      ] = await Promise.all([
        consultarStatusSnapshot(inventario.id_inventario),
        consultarSnapshotInventario(inventario.id_inventario),
        consultarEscopoInventario(inventario.id_inventario),
        consultarStatusEscopoInventario(inventario.id_inventario),
      ]);

      const resumoPorLocalizacao = new Map<
        string,
        {
          registros: number;
          itens: Set<string>;
          lotes: Set<string>;
          quantidade_total: number;
        }
      >();

      for (const item of snapshotAtual.itens) {
        let resumo = resumoPorLocalizacao.get(item.localizacao);

        if (!resumo) {
          resumo = {
            registros: 0,
            itens: new Set<string>(),
            lotes: new Set<string>(),
            quantidade_total: 0,
          };

          resumoPorLocalizacao.set(item.localizacao, resumo);
        }

        resumo.registros += 1;
        resumo.itens.add(item.codigo);

        if (item.lote !== null) {
          resumo.lotes.add(item.lote);
        }

        resumo.quantidade_total += item.saldo_inventario;
      }

      const localizacoes = Array.from(resumoPorLocalizacao.entries())
        .map(([localizacao, resumo]) => ({
          localizacao,
          registros: resumo.registros,
          itens_distintos: resumo.itens.size,
          lotes_distintos: resumo.lotes.size,
          quantidade_total: resumo.quantidade_total,
        }))
        .sort((a, b) => a.localizacao.localeCompare(b.localizacao, "pt-BR"));

      const resumoSnapshot: LocalizacoesCandidatasInventario = {
        id_inventario: snapshotAtual.id_inventario,
        codigo_inventario: snapshotAtual.codigo_inventario,
        tipo: snapshotAtual.tipo,
        cliente: snapshotAtual.cliente,
        cliente_id: snapshotAtual.cliente_id,
        c_armazem: snapshotAtual.c_armazem,
        total_localizacoes: localizacoes.length,
        localizacoes,
      };

      setStatusSnapshot(statusAtualizado);

      setEstoqueDetalhado(snapshotAtual);

      setEstoqueCandidato(resumoSnapshot);

      setEscopo(escopoAtualizado);

      setStatusEscopoInventario(statusEscopoAtualizado);

      setLocalizacoesSelecionadas([]);
      setFiltroLocalizacao("");
      setModoEscopo("ESPECIFICAS");

      toast.success(
        resposta.mensagem || "Snapshot do estoque gerado com sucesso.",
      );

      await navigate({
        to: "/inventarios/$idInventario",
        params: {
          idInventario: String(inventario.id_inventario),
        },
      });
    } catch (e) {
      const mensagem =
        e instanceof Error ? e.message : "Erro ao gerar o snapshot.";

      setErroSnapshot(mensagem);
      toast.error(mensagem);
    } finally {
      setGerandoSnapshot(false);
    }
  }

  if (carregando) {
    return (
      <main className="flex min-h-[50vh] items-center justify-center p-6">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-5 animate-spin" />
          Carregando inventário...
        </div>
      </main>
    );
  }

  if (erro || !inventario) {
    return (
      <main className="space-y-4 p-4 sm:p-6">
        <Link
          to="/controle-inventarios"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Voltar para Controle de Inventário
        </Link>

        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {erro ?? "Inventário não encontrado."}
        </div>
      </main>
    );
  }

  const usuarioAtual = obterUsuarioSalvo();

  const permissoesUsuario = new Set(
    (usuarioAtual?.permissoes ?? [])
      .map((permissao) =>
        typeof permissao === "string" ? permissao : permissao.codigo,
      )
      .filter(Boolean),
  );

  const podeExecutarContagemUsuario =
    permissoesUsuario.has("CONTAGEM_EXECUTAR") &&
    ![
      "ANALISE_VISUALIZAR",
      "CONFIGURACAO_EDITAR",
      "CONFIGURACAO_VISUALIZAR",
      "GESTOR_DECIDIR",
      "INVENTARIO_CRIAR",
      "INVENTARIO_FINALIZAR",
      "INVENTARIO_ROTATIVO_DECIDIR",
      "PLANO_ACAO_GERENCIAR",
      "PLANO_ACAO_VISUALIZAR",
      "RODADA_GERAR",
      "USUARIO_GERENCIAR",
    ].some((permissao) => permissoesUsuario.has(permissao));

  // MODULOS_INTELIGENTES_V1
  const faseModulos = (
    inventario.fase_operacional ?? ""
  )
    .trim()
    .toUpperCase();

  const statusModulos = (
    inventario.status ?? ""
  )
    .trim()
    .toUpperCase();

  const snapshotProntoModulos = Boolean(
    statusSnapshot?.snapshot_gerado,
  );

  const canceladoModulos =
    statusModulos === "CANCELADO";

  const finalizadoModulos =
    statusModulos === "FINALIZADO" ||
    statusModulos === "ENCERRADO";

  const encerradoModulos =
    canceladoModulos ||
    finalizadoModulos;

  const gestorModulos =
    inventario.tipo === "OFICIAL" &&
    !encerradoModulos &&
    (
      inventario.em_analise_gestor ||
      faseModulos === "AGUARDANDO_GESTOR" ||
      faseModulos === "AGUARDANDO_DECISAO"
    );

  const prontoFinalizarModulos =
    !encerradoModulos &&
    (
      inventario.pode_finalizar ||
      faseModulos === "PRONTO_FINALIZAR"
    );

  const recontagemModulos =
    !encerradoModulos &&
    (
      [
        "AGUARDANDO_RECONTAGEM",
        "EM_RECONTAGEM",
        "RECONTAGEM_PENDENTE",
      ].includes(faseModulos) ||
      (inventario.recontagens_pendentes ?? 0) > 0
    );

  const rodadaConcluidaModulos =
    !encerradoModulos &&
    snapshotProntoModulos &&
    (inventario.total_localizacoes ?? 0) > 0 &&
    (inventario.localizacoes_pendentes ?? 0) === 0 &&
    (inventario.localizacoes_em_contagem ?? 0) === 0;

  const analiseOficialModulos =
    inventario.tipo === "OFICIAL" &&
    rodadaConcluidaModulos &&
    !gestorModulos &&
    !prontoFinalizarModulos &&
    !recontagemModulos;

  const analiseRotativaModulos =
    inventario.tipo === "ROTATIVO" &&
    !encerradoModulos &&
    (
      (inventario.divergencias_sem_decisao ?? 0) > 0 ||
      (
        rodadaConcluidaModulos &&
        (inventario.total_divergencias ?? 0) > 0
      )
    ) &&
    !recontagemModulos;

  const operacaoModulos =
    !encerradoModulos &&
    snapshotProntoModulos &&
    !gestorModulos &&
    !prontoFinalizarModulos &&
    !analiseOficialModulos &&
    !analiseRotativaModulos;

  let rotaPrincipalModulos:
    | "/acompanhamento-contagem"
    | "/analise-ciclica"
    | "/analise-estoque"
    | "/analise-gestor"
    | "/analise-oficial"
    | "/auditoria"
    | "/indicadores"
    | "/recontagem"
    | null = null;

  if (encerradoModulos) {
    rotaPrincipalModulos = "/auditoria";
  } else if (gestorModulos) {
    rotaPrincipalModulos = "/analise-gestor";
  } else if (prontoFinalizarModulos) {
    rotaPrincipalModulos = inventario.tipo === "OFICIAL"
      ? "/analise-gestor"
      : "/analise-ciclica";
  } else if (recontagemModulos) {
    rotaPrincipalModulos = "/recontagem";
  } else if (analiseOficialModulos) {
    rotaPrincipalModulos = "/analise-oficial";
  } else if (analiseRotativaModulos) {
    rotaPrincipalModulos = "/analise-ciclica";
  } else if (
    snapshotProntoModulos &&
    operacaoModulos
  ) {
    rotaPrincipalModulos =
      "/acompanhamento-contagem";
  }

  const contextoModulos = encerradoModulos
    ? {
        titulo: finalizadoModulos
          ? "Invent\u00e1rio encerrado"
          : "Invent\u00e1rio cancelado",
        descricao:
          "O fluxo operacional foi encerrado. Priorize auditoria, resultados e rastreabilidade.",
      }
    : gestorModulos
      ? {
          titulo: "Decis\u00e3o gerencial",
          descricao:
            "A opera\u00e7\u00e3o foi conclu\u00edda. Priorize a an\u00e1lise gerencial e a revis\u00e3o das diverg\u00eancias.",
        }
      : prontoFinalizarModulos
        ? {
            titulo: "Pronto para finalizar",
            descricao:
              "As etapas obrigat\u00f3rias foram conclu\u00eddas. Revise o resultado antes do encerramento.",
          }
        : recontagemModulos
          ? {
              titulo: `R${inventario.rodada_atual} \u2014 Recontagem`,
              descricao:
                "Priorize a recontagem e acompanhe o progresso operacional da rodada atual.",
            }
          : analiseOficialModulos
            ? {
                titulo: `R${inventario.rodada_atual} conclu\u00edda`,
                descricao:
                  "A contagem terminou. Analise a concilia\u00e7\u00e3o antes de definir o pr\u00f3ximo passo.",
              }
            : analiseRotativaModulos
              ? {
                  titulo: "Diverg\u00eancias do ciclo",
                  descricao:
                    "A cobertura foi executada. Priorize as decis\u00f5es e tratativas do invent\u00e1rio rotativo.",
                }
              : snapshotProntoModulos
                ? {
                    titulo: `R${inventario.rodada_atual} em execu\u00e7\u00e3o`,
                    descricao:
                      "Acompanhe a opera\u00e7\u00e3o e utilize as consultas de apoio da rodada atual.",
                  }
                : {
                    titulo: "Prepara\u00e7\u00e3o",
                    descricao:
                      "Configure as regras, o estoque e o escopo antes de liberar a opera\u00e7\u00e3o.",
                  };

  /*
   * A configuração aplicada faz parte da rastreabilidade.
   * Ela permanece consultável em qualquer fase; a página de
   * configuração decide se o usuário pode editar ou apenas visualizar.
   */
  const mostrarRegrasModulo = true;

  const modulosInventario = [
    {
      nome: "Acompanhamento da Contagem",
      descricao:
        recontagemModulos
          ? "Acompanhar o progresso operacional da recontagem atual."
          : "Acompanhar progresso, volume e produtividade da rodada.",
      to: "/acompanhamento-contagem" as const,
      permissao: "ANALISE_VISUALIZAR",
      disponivel:
        snapshotProntoModulos &&
        !encerradoModulos &&
        !gestorModulos &&
        !prontoFinalizarModulos,
      modo: "operacao" as const,
      ordem: 20,
    },
    {
      nome: "An\u00e1lise de Estoque",
      descricao:
        encerradoModulos
          ? "Consultar o resultado consolidado de itens, faltas e sobras."
          : "Consultar itens, diverg\u00eancias, faltas e sobras.",
      to: "/analise-estoque" as const,
      permissao: "ANALISE_VISUALIZAR",
      disponivel:
        snapshotProntoModulos,
      modo: "consulta" as const,
      ordem: 40,
    },
    {
      nome: "Indicadores",
      descricao:
        encerradoModulos
          ? "Consultar os indicadores consolidados deste invent\u00e1rio."
          : "Consultar desempenho, risco e acuracidade.",
      to: "/indicadores" as const,
      permissao: "ANALISE_VISUALIZAR",
      disponivel:
        snapshotProntoModulos ||
        encerradoModulos,
      modo: "consulta" as const,
      ordem: 50,
    },
    {
      nome: "Recontagem",
      descricao:
        recontagemModulos
          ? `Executar e comparar os resultados da R${inventario.rodada_atual}.`
          : "Consultar e comparar os resultados das rodadas.",
      to: "/recontagem" as const,
      permissao: "RODADA_GERAR",
      disponivel:
        !encerradoModulos &&
        (
          recontagemModulos ||
          (inventario.rodada_atual ?? 0) >= 2
        ),
      modo:
        recontagemModulos
          ? ("operacao" as const)
          : ("consulta" as const),
      ordem: 30,
    },
    {
      nome: "Hist\u00f3rico completo",
      descricao:
        "Consultar vis\u00e3o geral, rodadas, itens, localiza\u00e7\u00f5es, diverg\u00eancias, decis\u00f5es, resultado final e eventos.",
      to: "/historico" as const,
      permissao: "ANALISE_VISUALIZAR",
      disponivel: true,
      modo: "consulta" as const,
      ordem: 80,
    },
    {
      nome: "Auditoria",
      descricao:
        encerradoModulos
          ? "Consultar evid\u00eancias, eventos e toda a rastreabilidade do processo."
          : "Visualizar toda a linha do tempo do invent\u00e1rio.",
      to: "/auditoria" as const,
      permissao: "ANALISE_VISUALIZAR",
      disponivel: true,
      modo: "consulta" as const,
      ordem: 90,
    },
    {
      nome: "An\u00e1lise C\u00edclica",
      descricao:
        analiseRotativaModulos
          ? "Tratar as diverg\u00eancias e decis\u00f5es pendentes do ciclo."
          : "Consultar as decis\u00f5es do invent\u00e1rio rotativo.",
      to: "/analise-ciclica" as const,
      permissao: "INVENTARIO_ROTATIVO_DECIDIR",
      disponivel:
        inventario.tipo === "ROTATIVO" &&
        !encerradoModulos &&
        snapshotProntoModulos,
      modo:
        analiseRotativaModulos
          ? ("operacao" as const)
          : ("consulta" as const),
      ordem: 35,
    },
    {
      nome: "An\u00e1lise Oficial",
      descricao:
        analiseOficialModulos
          ? `Revisar a concilia\u00e7\u00e3o da R${inventario.rodada_atual} e definir o pr\u00f3ximo passo.`
          : "Consultar a concilia\u00e7\u00e3o e os resultados das rodadas oficiais.",
      to: "/analise-oficial" as const,
      permissao: "ANALISE_VISUALIZAR",
      disponivel:
        inventario.tipo === "OFICIAL" &&
        snapshotProntoModulos &&
        !canceladoModulos,
      modo:
        analiseOficialModulos
          ? ("operacao" as const)
          : ("consulta" as const),
      ordem: 35,
    },
    {
      nome:
        finalizadoModulos
          ? "Resultado Gerencial"
          : "An\u00e1lise Gerencial",
      descricao:
        finalizadoModulos
          ? "Consultar o resultado final e o hist\u00f3rico das decis\u00f5es gerenciais."
          : prontoFinalizarModulos
            ? "Revisar o resultado consolidado e concluir o invent\u00e1rio."
            : "Analisar diverg\u00eancias e registrar as decis\u00f5es gerenciais.",
      to: "/analise-gestor" as const,
      permissao: "ANALISE_VISUALIZAR",
      disponivel:
        inventario.tipo === "OFICIAL" &&
        !canceladoModulos &&
        (
          gestorModulos ||
          prontoFinalizarModulos ||
          finalizadoModulos
        ),
      modo:
        gestorModulos ||
        prontoFinalizarModulos
          ? ("operacao" as const)
          : ("consulta" as const),
      ordem: 10,
    },
  ]
    .filter(
      (modulo) =>
        modulo.disponivel &&
        permissoesUsuario.has(
          modulo.permissao,
        ),
    )
    .map((modulo) => ({
      ...modulo,
      recomendado:
        modulo.to === rotaPrincipalModulos,
    }))
    .sort((a, b) => {
      if (
        a.recomendado !==
        b.recomendado
      ) {
        return a.recomendado ? -1 : 1;
      }

      return a.ordem - b.ordem;
    });

  // MODULOS_INTELIGENTES_V2
  const modulosPrincipais =
    modulosInventario.filter(
      (modulo) =>
        modulo.recomendado ||
        modulo.modo === "operacao",
    );

  const modulosSecundarios =
    modulosInventario.filter(
      (modulo) =>
        !modulo.recomendado &&
        modulo.modo === "consulta",
    );

  const podeVerRegrasModulo =
    mostrarRegrasModulo &&
    (
      permissoesUsuario.has(
        "ANALISE_VISUALIZAR",
      ) ||
      permissoesUsuario.has(
        "CONFIGURACAO_VISUALIZAR",
      ) ||
      permissoesUsuario.has(
        "CONFIGURACAO_EDITAR",
      )
    );

  const totalConsultasSecundarias =
    modulosSecundarios.length +
    (snapshotProntoModulos ? 1 : 0) +
    (podeVerRegrasModulo ? 1 : 0);

  const secaoPreparacao = (
    <section
      id="estoque-escopo"
      className="rounded-lg border bg-card p-5 shadow-xs"
    >
      {paginaEstoqueEscopo && (
        <Link
          to="/inventarios/$idInventario"
          params={{ idInventario }}
          className="mb-5 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          {"Voltar ao invent\u00e1rio"}
        </Link>
      )}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="font-semibold">
            {statusSnapshot?.snapshot_gerado
              ? "Snapshot do inventário"
              : "Preparação do inventário"}
          </h2>

          <p className="mt-1 text-sm text-muted-foreground">
            {statusSnapshot?.snapshot_gerado ? (
              <>
                Consulte o estoque congelado utilizado como referência deste
                  inventário.
              </>
            ) : (
              <>
                Consulte o estoque disponível para definir quais localizações
                farão parte deste inventário.
              </>
            )}
          </p>
        </div>

        {paginaEstoqueEscopo ? (
          !inventarioEncerrado &&
          !statusSnapshot?.snapshot_gerado && (
            <button
              type="button"
              onClick={() => void consultarEstoque()}
              disabled={consultandoEstoque}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {consultandoEstoque && (
                <Loader2 className="size-4 animate-spin" />
              )}
              Atualizar estoque
            </button>
          )
        ) : (
          <Link
            to="/inventarios/$idInventario/estoque-escopo"
            params={{ idInventario }}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition hover:opacity-90"
          >
            {statusSnapshot?.snapshot_gerado
                ? "Consultar snapshot"
                : "Consultar estoque"}
          </Link>
        )}
      </div>

      {paginaEstoqueEscopo && (
        <>
          {inventario.status === "FINALIZADO" && (
            <div className="mt-4 rounded-md border border-dashed p-4 text-sm text-muted-foreground">
              Este inventário está finalizado. As etapas de preparação não estão
              mais disponíveis para edição.
            </div>
          )}

          {inventario.status === "CANCELADO" && (
            <div className="mt-4 rounded-md border border-dashed p-4 text-sm text-muted-foreground">
              Este inventário está cancelado. As etapas de preparação e contagem
              não estão mais disponíveis para alteração.
            </div>
          )}

          {erroEstoque && (
            <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              {erroEstoque}
            </div>
          )}

          {estoqueCandidato && (
            <div className="mt-5 space-y-5">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Resumo
                  titulo="Localizações"
                  valor={estoqueCandidato.total_localizacoes}
                />

                <Resumo
                  titulo="Itens distintos"
                  valor={estoqueCandidato.localizacoes.reduce(
                    (total, item) => total + item.itens_distintos,
                    0,
                  )}
                />

                <Resumo
                  titulo="Lotes distintos"
                  valor={estoqueCandidato.localizacoes.reduce(
                    (total, item) => total + item.lotes_distintos,
                    0,
                  )}
                />

                <Resumo
                  titulo="Quantidade"
                  valor={estoqueCandidato.localizacoes.reduce(
                    (total, item) => total + item.quantidade_total,
                    0,
                  )}
                />
              </div>

              {estoqueDetalhado && (
                <div>
                  <div className="mb-3">
                    <h3 className="font-medium">
                      {statusSnapshot?.snapshot_gerado
                        ? "Estoque congelado do inventário"
                        : "Estoque candidato detalhado"}
                    </h3>

                    <p className="mt-1 text-sm text-muted-foreground">
                      {statusSnapshot?.snapshot_gerado ? (
                        <>
                          {estoqueDetalhado.total} linha(s) congelada(s) no
                          snapshot deste inventário.
                        </>
                      ) : (
                        <>
                          {estoqueDetalhado.total} linha(s) de estoque
                          encontrada(s) para este inventário.
                        </>
                      )}
                    </p>
                  </div>

                  {estoqueDetalhado.itens.length === 0 ? (
                    <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                      Nenhum item de estoque foi encontrado.
                    </div>
                  ) : (
                    <div className="max-h-[520px] overflow-auto rounded-md border">
                      <table className="min-w-[1400px] w-full text-sm">
                        <thead className="sticky top-0 z-10 bg-muted">
                          <tr className="border-b text-left">
                            <th className="px-4 py-3 font-medium">
                              Localização
                            </th>

                            <th className="px-4 py-3 font-medium">Código</th>

                            <th className="px-4 py-3 font-medium">Descrição</th>

                            <th className="px-4 py-3 font-medium">Lote</th>

                            <th className="px-4 py-3 text-right font-medium">
                              Valor Un.
                            </th>

                            <th className="px-4 py-3 text-right font-medium">
                              Valor Total
                            </th>

                            <th className="px-4 py-3 text-right font-medium">
                              Armazenado
                            </th>

                            <th className="px-4 py-3 text-right font-medium">
                              Separando
                            </th>

                            <th className="px-4 py-3 text-right font-medium">
                              Bloqueado
                            </th>

                            <th className="px-4 py-3 text-right font-medium">
                              Recebimento
                            </th>
                          </tr>
                        </thead>

                        <tbody>
                          {estoqueDetalhado.itens.map((item) => (
                            <tr
                              key={item.id_origem}
                              className="border-b last:border-b-0"
                            >
                              <td className="whitespace-nowrap px-4 py-3 font-medium">
                                {item.localizacao}
                              </td>

                              <td className="whitespace-nowrap px-4 py-3">
                                {item.codigo}
                              </td>

                              <td className="min-w-[260px] px-4 py-3">
                                {item.descricao}
                              </td>

                              <td className="whitespace-nowrap px-4 py-3">
                                {item.lote || "-"}
                              </td>

                              <td className="whitespace-nowrap px-4 py-3 text-right">
                                {formatarValor(item.valor_unitario)}
                              </td>

                              <td className="whitespace-nowrap px-4 py-3 text-right">
                                {formatarValor(item.valor_total)}
                              </td>

                              <td className="px-4 py-3 text-right">
                                {formatarQuantidade(item.q_armazenado)}
                              </td>

                              <td className="px-4 py-3 text-right">
                                {formatarQuantidade(item.q_separando)}
                              </td>

                              <td className="px-4 py-3 text-right">
                                {formatarQuantidade(item.q_bloqueado)}
                              </td>

                              <td className="px-4 py-3 text-right">
                                {formatarQuantidade(item.q_recebimento)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              <div className="rounded-lg border p-4">
                <div>
                  <h3 className="font-medium">Definir estoque a inventariar</h3>

                  <p className="mt-1 text-sm text-muted-foreground">
                    Escolha todo o estoque disponível ou selecione localizações
                    específicas.
                  </p>
                </div>

                <div className="mt-4 grid gap-3 md:grid-cols-3">
                  {inventario?.tipo === "ROTATIVO" && (
                    <label className="flex cursor-pointer items-start gap-3 rounded-md border p-4">
                      <input
                        type="radio"
                        name="modoEscopo"
                        checked={modoEscopo === "SUGESTOES"}
                        disabled={
                          escopoBloqueado || obterSugestoesAtivas().length === 0
                        }
                        onChange={() => selecionarModo("SUGESTOES")}
                        className="mt-1 size-4"
                      />

                      <div>
                        <div className="font-medium">Sugestões do ciclo</div>

                        <div className="mt-1 text-sm text-muted-foreground">
                          Analise todas as localizações pendentes e veja as
                          prioridades do ciclo.
                        </div>

                        <div className="mt-2 text-xs font-medium text-muted-foreground">
                          {obterSugestoesAtivas().length} localização(ões)
                          sugerida(s)
                        </div>
                      </div>
                    </label>
                  )}

                  <label className="flex cursor-pointer items-start gap-3 rounded-md border p-4">
                    <input
                      type="radio"
                      name="modoEscopo"
                      checked={modoEscopo === "COMPLETO"}
                      disabled={escopoBloqueado}
                      onChange={() => selecionarModo("COMPLETO")}
                      className="mt-1 size-4"
                    />

                    <div>
                      <div className="font-medium">Estoque completo</div>

                      <div className="mt-1 text-sm text-muted-foreground">
                        Incluir todas as localizações candidatas.
                      </div>
                    </div>
                  </label>

                  <label className="flex cursor-pointer items-start gap-3 rounded-md border p-4">
                    <input
                      type="radio"
                      name="modoEscopo"
                      checked={modoEscopo === "ESPECIFICAS"}
                      disabled={escopoBloqueado}
                      onChange={() => selecionarModo("ESPECIFICAS")}
                      className="mt-1 size-4"
                    />

                    <div>
                      <div className="font-medium">
                        Localizações específicas
                      </div>

                      <div className="mt-1 text-sm text-muted-foreground">
                        Escolher manualmente quais localizações incluir.
                      </div>
                    </div>
                  </label>
                </div>

                <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_auto_auto]">
                  <input
                    type="text"
                    value={filtroLocalizacao}
                    disabled={escopoBloqueado}
                    onChange={(event) =>
                      setFiltroLocalizacao(event.target.value)
                    }
                    placeholder="Pesquisar localização..."
                    className="h-10 rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
                  />

                  {modoEscopo === "SUGESTOES" ? (
                    <button
                      type="button"
                      onClick={() => {
                        if (!estoqueCandidato) {
                          return;
                        }

                        const candidatas = new Set(
                          estoqueCandidato.localizacoes.map((item) =>
                            item.localizacao.trim().toUpperCase(),
                          ),
                        );

                        const sugeridas = obterSugestoesAtivas()
                          .map((item) => item.localizacao)
                          .filter(
                            (localizacao) =>
                              candidatas.has(
                                localizacao.trim().toUpperCase(),
                              ) && !localizacaoJaSalva(localizacao),
                          );

                        setLocalizacoesSelecionadas(sugeridas);
                      }}
                      disabled={
                        escopoBloqueado || obterSugestoesAtivas().length === 0
                      }
                      className="inline-flex h-10 items-center justify-center rounded-md border px-4 text-sm font-medium hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Selecionar {obterSugestoesAtivas().length} sugeridas
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={selecionarTodasFiltradas}
                      disabled={escopoBloqueado}
                      className="inline-flex h-10 items-center justify-center rounded-md border px-4 text-sm font-medium hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Selecionar exibidas
                    </button>
                  )}

                  <button
                    type="button"
                    onClick={limparSelecao}
                    disabled={
                      escopoBloqueado || localizacoesSelecionadas.length === 0
                    }
                    className="inline-flex h-10 items-center justify-center rounded-md border px-4 text-sm font-medium hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Limpar seleção
                  </button>
                </div>

                <div className="mt-4 flex flex-col gap-3 rounded-md bg-muted/30 p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="text-sm">
                    <div>
                      <span className="font-semibold">
                        {escopo?.resumo.selecionadas ?? 0}
                      </span>{" "}
                      localização(ões) já salva(s) no escopo
                    </div>

                    <div className="mt-1 text-muted-foreground">
                      <span className="font-semibold text-foreground">
                        {localizacoesSelecionadas.length}
                      </span>{" "}
                      nova(s) localização(ões) selecionada(s)
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => void salvarEscopo()}
                    disabled={
                      escopoBloqueado ||
                      salvandoEscopo ||
                      localizacoesSelecionadas.length === 0
                    }
                    className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {salvandoEscopo && (
                      <Loader2 className="size-4 animate-spin" />
                    )}

                    {(escopo?.resumo.selecionadas ?? 0) > 0
                      ? "Adicionar ao escopo"
                      : "Salvar escopo"}
                  </button>
                </div>

                {erroEscopo && (
                  <div className="mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                    {erroEscopo}
                  </div>
                )}

                {statusSnapshot && (
                  <div className="mt-4 rounded-md border p-4">
                    {statusSnapshot.snapshot_gerado ? (
                      <div>
                        <div className="font-medium text-green-700">
                          Snapshot gerado
                        </div>

                        <p className="mt-1 text-sm text-muted-foreground">
                          O estoque de referência deste inventário já foi
                          congelado.{" "}
                          {statusEscopoInventario?.motivo_bloqueio ===
                          "CONTAGEM_INICIADA" ? (
                            <>
                              A contagem já foi iniciada. O escopo está
                              bloqueado e não pode mais ser alterado.
                            </>
                          ) : statusEscopoInventario?.pode_alterar_escopo ? (
                            <>
                              A configuração permite incluir novas localizações
                              enquanto a contagem não tiver sido iniciada. Se o
                              escopo for alterado, este snapshot será invalidado
                              e deverá ser gerado novamente.
                            </>
                          ) : (
                            <>
                              O escopo não pode mais ser alterado após a geração
                              do snapshot.
                            </>
                          )}
                        </p>

                        <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-sm">
                          <div>
                            <span className="font-semibold">
                              {statusSnapshot.registros_snapshot}
                            </span>{" "}
                            registro(s)
                          </div>

                          <div>
                            <span className="font-semibold">
                              {statusSnapshot.localizacoes_snapshot}
                            </span>{" "}
                            localização(ões)
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                          <div className="font-medium">Gerar snapshot</div>

                          <p className="mt-1 text-sm text-muted-foreground">
                            Congele o estoque de referência após finalizar a
                            definição do escopo.
                          </p>
                        </div>

                        <button
                          type="button"
                          onClick={() => void gerarSnapshotInventario()}
                          disabled={
                            inventarioEncerrado ||
                            gerandoSnapshot ||
                            (escopo?.resumo.selecionadas ?? 0) === 0 ||
                            localizacoesSelecionadas.length > 0
                          }
                          className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {gerandoSnapshot && (
                            <Loader2 className="size-4 animate-spin" />
                          )}
                          Gerar snapshot
                        </button>
                      </div>
                    )}

                    {erroSnapshot && (
                      <div className="mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                        {erroSnapshot}
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div>
                <div className="mb-3">
                  <h3 className="font-medium">
                    {statusSnapshot?.snapshot_gerado
                      ? "Localizações do snapshot"
                      : "Localizações disponíveis"}
                  </h3>

                  <p className="mt-1 text-sm text-muted-foreground">
                    {statusSnapshot?.snapshot_gerado
                      ? "Localizações e quantidades congeladas no snapshot."
                      : "Estoque atual disponível para composição do escopo."}
                  </p>
                </div>

                {modoEscopo === "SUGESTOES" && localizacoesCiclo ? (
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-md bg-muted/30 p-3 text-sm">
                      <div>
                        <span className="font-semibold">
                          {localizacoesCiclo.localizacoes.length}
                        </span>{" "}
                        localização(ões) pendente(s) no ciclo
                      </div>

                      <div>
                        <span className="font-semibold">
                          {
                            localizacoesCiclo.localizacoes.filter(
                              (item) => item.sugerida,
                            ).length
                          }
                        </span>{" "}
                        recomendada(s) no Top 20 atual
                      </div>
                    </div>

                    <AlertDialog
                      open={localizacaoParaIgnorar !== null}
                      onOpenChange={(aberto) => {
                        if (!aberto) {
                          fecharIgnorarLocalizacaoRotativa();
                        }
                      }}
                    >
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>
                            Ignorar localizacao no ciclo
                          </AlertDialogTitle>
                          <AlertDialogDescription>
                            A localizacao{" "}
                            {localizacaoParaIgnorar?.localizacao ?? "-"}
                            sera retirada das pendencias deste ciclo. Esta acao
                            nao registra uma contagem.
                          </AlertDialogDescription>
                        </AlertDialogHeader>

                        <div className="space-y-2">
                          <label
                            htmlFor="motivo-ignorar-localizacao"
                            className="text-sm font-medium"
                          >
                            Motivo obrigatorio
                          </label>
                          <textarea
                            id="motivo-ignorar-localizacao"
                            value={motivoIgnorarLocalizacao}
                            disabled={ignorandoLocalizacao}
                            maxLength={500}
                            rows={4}
                            placeholder="Explique por que esta localizacao nao sera contada neste ciclo."
                            onChange={(evento) => {
                              setMotivoIgnorarLocalizacao(evento.target.value);
                              setErroIgnorarLocalizacao(null);
                            }}
                            className="w-full resize-y rounded-md border bg-background p-3 text-sm outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
                          />
                          <div className="text-right text-xs text-muted-foreground">
                            {motivoIgnorarLocalizacao.length}/500
                          </div>
                        </div>

                        {erroIgnorarLocalizacao ? (
                          <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                            {erroIgnorarLocalizacao}
                          </div>
                        ) : null}

                        <AlertDialogFooter>
                          <AlertDialogCancel
                            disabled={ignorandoLocalizacao}
                            onClick={fecharIgnorarLocalizacaoRotativa}
                          >
                            Cancelar
                          </AlertDialogCancel>
                          <button
                            type="button"
                            disabled={
                              ignorandoLocalizacao ||
                              !motivoIgnorarLocalizacao.trim()
                            }
                            onClick={() =>
                              void confirmarIgnorarLocalizacaoRotativa()
                            }
                            className="inline-flex h-10 items-center justify-center rounded-md bg-red-600 px-4 text-sm font-medium text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {ignorandoLocalizacao
                              ? "Ignorando..."
                              : "Confirmar ignoracao no ciclo"}
                          </button>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>

                    <div className="overflow-x-auto rounded-md border">
                      <table className="w-full min-w-[1000px] text-sm">
                        <thead className="bg-muted/50">
                          <tr className="border-b text-left">
                            <th className="w-[6%] px-2 py-3 text-center font-medium">
                              Sel.
                            </th>

                            <th className="w-[8%] px-2 py-3 text-center font-medium">
                              Prior.
                            </th>

                            <th className="w-[17%] px-4 py-3 font-medium">
                              Localização
                            </th>

                            <th className="w-[10%] px-2 py-3 text-center font-medium">
                              Score
                            </th>

                            <th className="w-[13%] px-2 py-3 text-center font-medium">
                              Criticidade
                            </th>

                            <th className="w-[12%] px-2 py-3 text-center font-medium">
                              Recomendação
                            </th>

                            <th className="w-[22%] px-4 py-3 font-medium">
                              Motivo
                            </th>

                            <th className="w-[12%] px-2 py-3 text-center font-medium">
                              Contexto
                            </th>

                            <th className="w-[12%] px-2 py-3 text-center font-medium">
                              Acoes
                            </th>
                          </tr>
                        </thead>

                        <tbody>
                          {localizacoesCiclo.localizacoes
                            .filter((item) =>
                              item.localizacao
                                .toUpperCase()
                                .includes(
                                  filtroLocalizacao.trim().toUpperCase(),
                                ),
                            )
                            .map((item) => {
                              const disponivelNoEstoque =
                                estoqueCandidato.localizacoes.some(
                                  (candidata) =>
                                    candidata.localizacao
                                      .trim()
                                      .toUpperCase() ===
                                    item.localizacao.trim().toUpperCase(),
                                );

                              const jaSalva = localizacaoJaSalva(
                                item.localizacao,
                              );

                              const selecionada = localizacoesSelecionadas.some(
                                (localizacao) =>
                                  localizacao.trim().toUpperCase() ===
                                  item.localizacao.trim().toUpperCase(),
                              );

                              return (
                                <tr
                                  key={item.id_ciclo_localizacao}
                                  className={
                                    item.sugerida
                                      ? "border-b bg-blue-50/50 last:border-b-0"
                                      : "border-b last:border-b-0"
                                  }
                                >
                                  <td className="px-2 py-3 text-center">
                                    <input
                                      type="checkbox"
                                      checked={jaSalva || selecionada}
                                      disabled={
                                        escopoBloqueado ||
                                        jaSalva ||
                                        !disponivelNoEstoque
                                      }
                                      onChange={() =>
                                        alternarLocalizacao(item.localizacao)
                                      }
                                      className="size-4"
                                    />
                                  </td>

                                  <td className="px-2 py-3 text-center font-semibold tabular-nums">
                                    {item.prioridade ?? "—"}
                                  </td>

                                  <td className="px-4 py-3 font-medium">
                                    {item.localizacao}
                                  </td>

                                  <td className="px-2 py-3 text-center tabular-nums">
                                    {item.score_risco !== null
                                      ? item.score_risco
                                          .toFixed(2)
                                          .replace(".", ",")
                                      : "—"}
                                  </td>

                                  <td className="px-2 py-3 text-center">
                                    <span className="rounded-md bg-muted px-2 py-1 text-xs font-semibold">
                                      {item.classificacao_risco ?? "—"}
                                    </span>
                                  </td>

                                  <td className="px-2 py-3 text-center">
                                    {item.sugerida ? (
                                      <span className="rounded-md bg-blue-100 px-2 py-1 text-xs font-semibold text-blue-700">
                                        Top 20
                                      </span>
                                    ) : (
                                      <span className="text-xs font-medium text-muted-foreground">
                                        Disponível
                                      </span>
                                    )}
                                  </td>

                                  <td className="px-4 py-3 text-xs">
                                    <div>
                                      {item.motivos.length > 0
                                        ? item.motivos.join(" • ")
                                        : "Sem motivo adicional."}
                                    </div>

                                    {!disponivelNoEstoque && (
                                      <div className="mt-1 font-medium text-muted-foreground">
                                        Sem estoque candidato nesta localização.
                                      </div>
                                    )}
                                  </td>

                                  <td className="px-2 py-3 text-center">
                                    <button
                                      type="button"
                                      disabled={
                                        consultandoContextoLocalizacao !== null
                                      }
                                      onClick={() =>
                                        void abrirContextoLocalizacaoRotativa(
                                          item.localizacao,
                                        )
                                      }
                                      className="inline-flex h-9 items-center justify-center gap-2 rounded-md border bg-background px-3 text-xs font-medium transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                                    >
                                      {consultandoContextoLocalizacao ===
                                      item.localizacao.trim().toUpperCase() ? (
                                        <Loader2 className="size-3.5 animate-spin" />
                                      ) : null}
                                      Abrir
                                    </button>
                                  </td>

                                  <td className="px-2 py-3 text-center">
                                    <button
                                      type="button"
                                      disabled={
                                        ignorandoLocalizacao ||
                                        jaSalva ||
                                        selecionada
                                      }
                                      title={
                                        jaSalva || selecionada
                                          ? "Remova a localizacao do escopo antes de ignora-la."
                                          : "Ignorar esta localizacao no ciclo"
                                      }
                                      onClick={() =>
                                        abrirIgnorarLocalizacaoRotativa(
                                          item.id_ciclo_localizacao,
                                          item.localizacao,
                                        )
                                      }
                                      className="inline-flex h-9 items-center justify-center rounded-md border border-red-200 px-3 text-xs font-medium text-red-700 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                                    >
                                      Ignorar no ciclo
                                    </button>
                                  </td>
                                </tr>
                              );
                            })}
                        </tbody>
                      </table>
                    </div>

                    {erroContextoLocalizacao ? (
                      <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                        {erroContextoLocalizacao}
                      </div>
                    ) : null}

                    {contextoLocalizacaoRotativa ? (
                      <div ref={contextoLocalizacaoRef} className="scroll-mt-6">
                        <PainelContextoLocalizacaoRotativa
                          contexto={contextoLocalizacaoRotativa}
                          fechar={() => setContextoLocalizacaoRotativa(null)}
                        />
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <>
                    {estoqueCandidato.localizacoes.length === 0 ? (
                      <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                        Nenhuma localização com saldo foi encontrada.
                      </div>
                    ) : (
                      <div className="overflow-x-auto rounded-md border">
                        <table className="w-full table-fixed text-sm">
                          <thead className="bg-muted/50">
                            <tr className="border-b text-left">
                              <th className="w-[6%] px-2 py-3 text-center font-medium">
                                Sel.
                              </th>

                              <th className="w-[28%] px-4 py-3 text-left font-medium">
                                Localização
                              </th>

                              <th className="w-[11%] px-2 py-3 text-center font-medium">
                                Registros
                              </th>
                              <th className="w-[9%] px-2 py-3 text-center font-medium">
                                Itens
                              </th>
                              <th className="w-[9%] px-2 py-3 text-center font-medium">
                                Lotes
                              </th>
                              <th className="w-[14%] px-2 py-3 text-center font-medium">
                                Quantidade
                              </th>

                              <th className="w-[23%] px-4 py-3 text-left font-medium">
                                Situação
                              </th>
                            </tr>
                          </thead>

                          <tbody>
                            {estoqueCandidato.localizacoes
                              .filter((localizacao) =>
                                localizacao.localizacao
                                  .toUpperCase()
                                  .includes(
                                    filtroLocalizacao.trim().toUpperCase(),
                                  ),
                              )
                              .map((localizacao) => (
                                <tr
                                  key={localizacao.localizacao}
                                  className="border-b last:border-b-0"
                                >
                                  <td className="px-2 py-3 text-center">
                                    <input
                                      type="checkbox"
                                      checked={
                                        localizacaoJaSalva(
                                          localizacao.localizacao,
                                        ) ||
                                        localizacoesSelecionadas.includes(
                                          localizacao.localizacao,
                                        )
                                      }
                                      disabled={
                                        escopoBloqueado ||
                                        localizacaoJaSalva(
                                          localizacao.localizacao,
                                        )
                                      }
                                      onChange={() =>
                                        alternarLocalizacao(
                                          localizacao.localizacao,
                                        )
                                      }
                                      className="size-4"
                                    />
                                  </td>

                                  <td className="px-4 py-3 text-left font-medium">
                                    {localizacao.localizacao}
                                  </td>

                                  <td className="px-2 py-3 text-center tabular-nums">
                                    {localizacao.registros}
                                  </td>

                                  <td className="px-2 py-3 text-center tabular-nums">
                                    {localizacao.itens_distintos}
                                  </td>

                                  <td className="px-2 py-3 text-center tabular-nums">
                                    {localizacao.lotes_distintos}
                                  </td>

                                  <td className="px-2 py-3 text-center tabular-nums">
                                    {formatarQuantidade(
                                      localizacao.quantidade_total,
                                    )}
                                  </td>

                                  <td className="px-4 py-3 text-left">
                                    {localizacaoJaSalva(
                                      localizacao.localizacao,
                                    ) ? (
                                      <span className="text-xs font-semibold text-violet-600">
                                        Já incluída
                                      </span>
                                    ) : localizacoesSelecionadas.includes(
                                        localizacao.localizacao,
                                      ) ? (
                                      <span className="text-xs font-semibold text-blue-600">
                                        Selecionada
                                      </span>
                                    ) : (
                                      <span className="text-xs font-semibold text-green-600">
                                        Disponível
                                      </span>
                                    )}
                                  </td>
                                </tr>
                              ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );

  if (paginaEstoqueEscopo) {
    return <main className="space-y-6 p-4 sm:p-6">{secaoPreparacao}</main>;
  }

  if (paginaControleRodadas) {
    return (
      <main className="mx-auto w-full max-w-6xl space-y-6 p-4 sm:p-6">
        <Link
          to="/inventarios/$idInventario"
          params={{ idInventario }}
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Voltar ao inventário
        </Link>
        <header>
          <p className="text-sm text-muted-foreground">
            {inventario.codigo_inventario}
          </p>
          <h1 className="text-2xl font-bold tracking-tight">
            Controle de rodadas
          </h1>
        </header>
        {inventario.tipo !== "OFICIAL" ? (
          <p role="alert" className="rounded-lg border p-5">
            Controle disponível somente para inventários oficiais.
          </p>
        ) : !permissoesUsuario.has("RODADA_GERAR") ? (
          <p role="alert" className="rounded-lg border p-5">
            Você não possui permissão para controlar as rodadas deste
            inventário.
          </p>
        ) : null}
        {inventario.tipo === "OFICIAL" &&
          permissoesUsuario.has("RODADA_GERAR") && (
            <section className="rounded-lg border bg-card p-5 shadow-xs">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h2 className="font-semibold">
                    Controle de rodadas do inventário oficial
                  </h2>

                  <p className="mt-1 text-sm text-muted-foreground">
                    Acompanhe a sequência configurada e libere a próxima etapa
                    conforme o resultado da rodada atual.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => void carregarControleRodadasOficial()}
                  disabled={carregandoRodadaOficial || processandoRodadaOficial}
                  className="inline-flex h-10 items-center justify-center rounded-md border px-4 text-sm font-medium transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {carregandoRodadaOficial ? "Atualizando..." : "Atualizar"}
                </button>
              </div>

              {erroRodadaOficial && (
                <div
                  role="alert"
                  className="mt-4 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/20 dark:text-red-300"
                >
                  {erroRodadaOficial}
                </div>
              )}

              {carregandoRodadaOficial && !rodadaOficial ? (
                <div className="mt-4 flex items-center gap-2 rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                  <Loader2 className="size-4 animate-spin" />
                  Consultando o fluxo de rodadas...
                </div>
              ) : rodadaOficial ? (
                <>
                  <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <Resumo
                      titulo="Rodada atual"
                      valor={`R${rodadaOficial.numero_rodada}`}
                    />

                    <Resumo
                      titulo="Rodadas previstas"
                      valor={
                        configuracaoInventario?.max_rodadas ??
                        previewRodadaOficial?.preview.configuracao
                          ?.max_rodadas ??
                        "-"
                      }
                    />

                    <Resumo
                      titulo="Rodadas iniciais"
                      valor={
                        configuracaoInventario?.rodadas_iniciais ??
                        previewRodadaOficial?.preview.configuracao
                          ?.rodadas_iniciais ??
                        "-"
                      }
                    />

                    <Resumo
                      titulo="Itens para a próxima etapa"
                      valor={previewRodadaOficial?.preview.candidatos ?? 0}
                    />
                  </div>

                  <div className="mt-5">
                    <div className="mb-3">
                      <h3 className="text-sm font-semibold">
                        Fluxo configurado
                      </h3>

                      <p className="mt-1 text-xs text-muted-foreground">
                        Esta sequência pertence exclusivamente a este
                        inventário.
                      </p>
                    </div>

                    {configuracaoInventario?.rodadas?.length ? (
                      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                        {configuracaoInventario.rodadas
                          .filter((rodada) => rodada.ativa)
                          .sort((a, b) => a.numero_rodada - b.numero_rodada)
                          .map((rodadaConfigurada) => {
                            const concluida =
                              rodadaConfigurada.numero_rodada <
                              rodadaOficial.numero_rodada;

                            const atual =
                              rodadaConfigurada.numero_rodada ===
                              rodadaOficial.numero_rodada;

                            const proxima =
                              rodadaConfigurada.numero_rodada ===
                              previewRodadaOficial?.preview
                                .numero_proxima_rodada;

                            return (
                              <div
                                key={rodadaConfigurada.id_configuracao_rodada}
                                className={
                                  atual
                                    ? "rounded-lg border-2 border-primary bg-primary/5 p-4"
                                    : concluida
                                      ? "rounded-lg border border-emerald-300 bg-emerald-50/60 p-4 dark:border-emerald-900 dark:bg-emerald-950/20"
                                      : proxima
                                        ? "rounded-lg border border-amber-300 bg-amber-50/60 p-4 dark:border-amber-900 dark:bg-amber-950/20"
                                        : "rounded-lg border bg-muted/15 p-4"
                                }
                              >
                                <div className="flex items-start justify-between gap-3">
                                  <div>
                                    <div className="text-lg font-bold text-primary">
                                      R{rodadaConfigurada.numero_rodada}
                                    </div>

                                    <div className="mt-1 text-sm font-semibold">
                                      {rotuloTipoRodada(
                                        rodadaConfigurada.tipo_rodada,
                                      )}
                                    </div>
                                  </div>

                                  <span
                                    className={
                                      atual
                                        ? "rounded-full bg-primary px-2.5 py-1 text-xs font-semibold text-primary-foreground"
                                        : concluida
                                          ? "rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200"
                                          : proxima
                                            ? "rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-800 dark:bg-amber-950 dark:text-amber-200"
                                            : "rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground"
                                    }
                                  >
                                    {atual
                                      ? "Atual"
                                      : concluida
                                        ? "Concluída"
                                        : proxima
                                          ? "Próxima"
                                          : "Aguardando"}
                                  </span>
                                </div>

                                <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
                                  {descricaoTipoRodada(
                                    rodadaConfigurada.tipo_rodada,
                                  )}
                                </p>
                              </div>
                            );
                          })}
                      </div>
                    ) : (
                      <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                        A sequência de rodadas não foi carregada.
                      </div>
                    )}
                  </div>

                  <div
                    className={`mt-5 rounded-lg border p-4 ${
                      previewRodadaOficial?.preview.pode_criar
                        ? "border-emerald-300 bg-emerald-50/60 dark:border-emerald-900 dark:bg-emerald-950/20"
                        : "bg-muted/20"
                    }`}
                  >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                          Situação operacional
                        </div>

                        <p className="mt-1 text-sm font-medium">
                          {mensagemSituacaoRodada(
                            previewRodadaOficial?.preview ?? null,
                          )}
                        </p>

                        {previewRodadaOficial?.preview
                          .numero_proxima_rodada && (
                          <p className="mt-2 text-xs text-muted-foreground">
                            Próxima etapa:{" "}
                            <strong>
                              R
                              {
                                previewRodadaOficial.preview
                                  .numero_proxima_rodada
                              }{" "}
                              ·{" "}
                              {rotuloTipoRodada(
                                previewRodadaOficial.preview
                                  .tipo_proxima_rodada,
                              )}
                            </strong>
                          </p>
                        )}
                      </div>

                      <div className="shrink-0">
                        <StatusBadge status={rodadaOficial.status} />
                      </div>
                    </div>
                  </div>

                  {inventario.status === "ABERTO" && (
                    <div className="mt-5 flex flex-col-reverse gap-2 border-t pt-5 sm:flex-row sm:justify-end">
                      {rodadaOficial.numero_rodada >= 2 && (
                        <button
                          type="button"
                          onClick={() => void sincronizarLocalizacoesOficial()}
                          disabled={processandoRodadaOficial}
                          className="inline-flex h-11 items-center justify-center rounded-md border px-4 text-sm font-medium transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Sincronizar localizações
                        </button>
                      )}

                      {previewRodadaOficial?.preview.tipo_proxima_rodada ===
                      "GESTOR" ? (
                        permissoesUsuario.has("ANALISE_VISUALIZAR") ? (
                          <Link
                            to="/analise-oficial"
                            search={{
                              inventario: inventario.id_inventario,
                            }}
                            className="inline-flex h-11 items-center justify-center rounded-md bg-amber-700 px-5 text-sm font-semibold text-white transition hover:bg-amber-800"
                          >
                            Avaliar envio ao gestor
                          </Link>
                        ) : (
                          <button
                            type="button"
                            disabled
                            className="inline-flex h-11 items-center justify-center rounded-md bg-primary px-5 text-sm font-semibold text-primary-foreground opacity-50"
                          >
                            Próxima etapa: gestor
                          </button>
                        )
                      ) : (
                        <AlertDialog
                          open={confirmacaoGeracaoRodadaAberta}
                          onOpenChange={(aberto) => {
                            if (!processandoRodadaOficial) {
                              setConfirmacaoGeracaoRodadaAberta(aberto);
                            }
                          }}
                        >
                          <AlertDialogTrigger asChild>
                            <button
                              type="button"
                              disabled={
                                processandoRodadaOficial ||
                                carregandoRodadaOficial ||
                                !previewRodadaOficial?.preview.pode_criar
                              }
                              title={mensagemSituacaoRodada(
                                previewRodadaOficial?.preview ?? null,
                              )}
                              className="inline-flex h-11 items-center justify-center rounded-md bg-primary px-5 text-sm font-semibold text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {processandoRodadaOficial
                                ? "Gerando rodada..."
                                : previewRodadaOficial?.preview
                                      .numero_proxima_rodada
                                  ? `Gerar R${previewRodadaOficial.preview.numero_proxima_rodada}`
                                  : previewRodadaOficial?.preview
                                        .tipo_proxima_rodada === "FINALIZADO"
                                    ? "Rodadas concluídas"
                                    : "Gerar próxima rodada"}
                            </button>
                          </AlertDialogTrigger>

                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>
                                Gerar{" "}
                                {previewRodadaOficial?.preview
                                  .numero_proxima_rodada
                                  ? `R${previewRodadaOficial.preview.numero_proxima_rodada}`
                                  : "a próxima rodada"}
                                ?
                              </AlertDialogTitle>

                              <AlertDialogDescription>
                                A nova rodada será criada como{" "}
                                <strong>
                                  {rotuloTipoRodada(
                                    previewRodadaOficial?.preview
                                      .tipo_proxima_rodada,
                                  )}
                                </strong>
                                .{" "}
                                {descricaoTipoRodada(
                                  previewRodadaOficial?.preview
                                    .tipo_proxima_rodada,
                                )}
                              </AlertDialogDescription>
                            </AlertDialogHeader>

                            <div className="rounded-md border bg-muted/30 p-4 text-sm">
                              <div className="flex justify-between gap-4">
                                <span className="text-muted-foreground">
                                  Itens selecionados
                                </span>

                                <strong>
                                  {previewRodadaOficial?.preview.candidatos ??
                                    0}
                                </strong>
                              </div>
                            </div>

                            <AlertDialogFooter>
                              <AlertDialogCancel
                                disabled={processandoRodadaOficial}
                              >
                                Cancelar
                              </AlertDialogCancel>

                              <button
                                type="button"
                                disabled={
                                  processandoRodadaOficial ||
                                  carregandoRodadaOficial ||
                                  !previewRodadaOficial?.preview.pode_criar
                                }
                                onClick={() => {
                                  setConfirmacaoGeracaoRodadaAberta(false);

                                  void gerarProximaRodadaOficial();
                                }}
                                className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                              >
                                Confirmar geração
                              </button>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      )}
                    </div>
                  )}
                </>
              ) : (
                !erroRodadaOficial && (
                  <div className="mt-4 rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                    Nenhuma rodada foi localizada para este inventário.
                  </div>
                )
              )}
            </section>
          )}
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-7xl space-y-6 p-4 sm:p-6">
      <Link
        to="/controle-inventarios"
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Voltar para Controle de Inventário
      </Link>

      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <Boxes
            className="mt-0.5 size-7 shrink-0 text-primary"
            aria-hidden="true"
          />

          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-primary">
                {inventario.codigo_inventario}
              </h1>

              <StatusBadge status={inventario.status} />

              {inventario.tipo === "OFICIAL" &&
                inventario.em_analise_gestor && (
                  <span className="inline-flex items-center gap-1 rounded-full border border-amber-300 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-800 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
                    <ShieldCheck className="size-3.5" aria-hidden="true" />
                    Em análise gerencial
                  </span>
                )}
            </div>

            <p className="mt-1 text-sm text-muted-foreground">
              Inventário #{inventario.id_inventario}
            </p>
          </div>
        </div>

        {inventario.status === "ABERTO" && (
          <AlertDialog
            open={cancelamentoAberto}
            onOpenChange={(aberto) => {
              if (cancelandoInventario) {
                return;
              }

              setCancelamentoAberto(aberto);

              if (!aberto) {
                setMotivoCancelamento("");
              }
            }}
          >
            <AlertDialogTrigger asChild>
              <button
                type="button"
                className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-md border border-red-200 px-4 text-sm font-medium text-red-700 transition hover:bg-red-50"
              >
                <Ban className="size-4" />
                Cancelar inventário
              </button>
            </AlertDialogTrigger>

            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Cancelar inventário</AlertDialogTitle>

                <AlertDialogDescription>
                  Esta ação encerra o inventário e impede novas contagens ou
                  alterações operacionais. O histórico existente será
                  preservado.
                </AlertDialogDescription>
              </AlertDialogHeader>

              <div className="space-y-2">
                <label
                  htmlFor="motivo-cancelamento"
                  className="text-sm font-medium"
                >
                  Motivo do cancelamento
                </label>

                <textarea
                  id="motivo-cancelamento"
                  value={motivoCancelamento}
                  onChange={(event) =>
                    setMotivoCancelamento(event.target.value)
                  }
                  disabled={cancelandoInventario}
                  rows={4}
                  placeholder="Informe por que este inventário está sendo cancelado."
                  className="w-full resize-none rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                />

                <p className="text-xs text-muted-foreground">
                  O motivo ficará registrado para rastreabilidade.
                </p>
              </div>

              <AlertDialogFooter>
                <AlertDialogCancel disabled={cancelandoInventario}>
                  Voltar
                </AlertDialogCancel>

                <button
                  type="button"
                  onClick={() => void cancelarInventarioAtual()}
                  disabled={cancelandoInventario || !motivoCancelamento.trim()}
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-red-600 px-4 text-sm font-medium text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {cancelandoInventario && (
                    <Loader2 className="size-4 animate-spin" />
                  )}
                  Confirmar cancelamento
                </button>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        )}
      </header>

      <section className="rounded-lg border bg-card p-5 shadow-xs">
        <div>
          <h2 className="font-semibold">Informações gerais</h2>

          <p className="mt-1 text-sm text-muted-foreground">
            Dados principais deste inventário.
          </p>
        </div>

        <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          <Info
            icone={<User className="size-4" />}
            titulo="Cliente"
            valor={inventario.cliente}
          />

          <Info
            icone={<MapPin className="size-4" />}
            titulo="Armazém"
            valor={inventario.armazem}
          />

          <Info
            icone={<Boxes className="size-4" />}
            titulo="Tipo"
            valor={formatarTipo(inventario.tipo)}
          />

          <Info
            icone={<Boxes className="size-4" />}
            titulo="Rodada atual"
            valor={String(inventario.rodada_atual)}
          />
        </div>

        <div className="mt-5 border-t pt-5">
          <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Descrição
          </div>

          <div className="mt-1 text-sm">
            {inventario.descricao || "Sem descrição informada."}
          </div>
        </div>
      </section>

      <PainelFluxoInventario
        inventario={inventario}
        previewRodada={previewRodadaOficial?.preview ?? null}
        carregandoPreview={carregandoRodadaOficial}
        erroPreview={erroRodadaOficial}
        podeControlarRodadas={permissoesUsuario.has("RODADA_GERAR")}
        snapshotGerado={Boolean(statusSnapshot?.snapshot_gerado)}
        statusSnapshotCarregado={statusSnapshot !== null}
        podeExecutarContagem={podeExecutarContagemUsuario}
      />

      {inventario.tipo === "OFICIAL" && inventario.em_analise_gestor && (
        <section className="rounded-lg border border-amber-300 bg-amber-50/60 p-5 shadow-xs dark:border-amber-800 dark:bg-amber-950/20">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex items-start gap-3">
              <ShieldCheck
                className="mt-0.5 size-6 shrink-0 text-amber-700 dark:text-amber-300"
                aria-hidden="true"
              />

              <div>
                <h2 className="font-semibold text-amber-900 dark:text-amber-200">
                  {"Decis\u00e3o gerencial"}
                </h2>

                <p className="mt-1 text-sm text-amber-800/90 dark:text-amber-200/80">
                  {
                    "Acompanhe as diverg\u00eancias e as decis\u00f5es registradas pelo gestor."
                  }
                </p>

                {(inventario.encaminhado_gestor_por ||
                  inventario.data_hora_encaminhamento_gestor) && (
                  <p className="mt-2 text-xs text-amber-800/80 dark:text-amber-300/80">
                    Encaminhado
                    {inventario.encaminhado_gestor_por
                      ? ` por ${inventario.encaminhado_gestor_por}`
                      : ""}
                    {inventario.data_hora_encaminhamento_gestor
                      ? ` em ${formatarData(
                          inventario.data_hora_encaminhamento_gestor,
                        )}`
                      : ""}
                    .
                  </p>
                )}
              </div>
            </div>

            {permissoesUsuario.has("ANALISE_VISUALIZAR") ? (
              <Link
                to="/analise-gestor"
                search={{
                  inventario: inventario.id_inventario,
                }}
                className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-md bg-amber-700 px-4 text-sm font-semibold text-white transition hover:bg-amber-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-600"
              >
                <ShieldCheck className="size-4" aria-hidden="true" />

                {analiseGestor?.operacao_concluida
                  ? "Consultar resultado"
                  : analiseGestor && analiseGestor.resumo.itens_sem_decisao > 0
                    ? "Registrar decis\u00f5es"
                    : "Abrir an\u00e1lise"}
              </Link>
            ) : (
              <p className="text-xs font-medium text-amber-800 dark:text-amber-300">
                {"Permiss\u00e3o ANALISE_VISUALIZAR necess\u00e1ria."}
              </p>
            )}
          </div>

          {carregandoAnaliseGestor && (
            <div className="mt-4 flex items-center gap-2 rounded-md border border-amber-200 bg-background/60 px-4 py-3 text-sm text-muted-foreground dark:border-amber-900">
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              {"Carregando resumo gerencial..."}
            </div>
          )}

          {erroAnaliseGestor && (
            <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">
              {erroAnaliseGestor}
            </div>
          )}

          {analiseGestor && !carregandoAnaliseGestor && (
            <>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <ResumoGerencial
                  titulo={"Diverg\u00eancias"}
                  valor={analiseGestor.resumo.divergencias}
                />

                <ResumoGerencial
                  titulo={"Sem decis\u00e3o"}
                  valor={analiseGestor.resumo.itens_sem_decisao}
                  destaque={analiseGestor.resumo.itens_sem_decisao > 0}
                />

                <ResumoGerencial
                  titulo={"Resolvidos pelo gestor"}
                  valor={analiseGestor.resumo.itens_resolvidos_gestor}
                />

                <ResumoGerencial
                  titulo={"Rodadas em aberto"}
                  valor={analiseGestor.resumo.rodadas_nao_finalizadas}
                  destaque={analiseGestor.resumo.rodadas_nao_finalizadas > 0}
                />
              </div>

              <div
                className={`mt-4 rounded-md border px-4 py-3 text-sm ${
                  analiseGestor.pode_finalizar_inventario
                    ? "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-300"
                    : "border-amber-300 bg-amber-100/60 text-amber-900 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200"
                }`}
              >
                {analiseGestor.pode_finalizar_inventario
                  ? "Todas as pend\u00eancias gerenciais foram resolvidas. O invent\u00e1rio est\u00e1 pronto para finaliza\u00e7\u00e3o."
                  : analiseGestor.resumo.rodadas_nao_finalizadas > 0
                    ? "Finalize as rodadas em aberto antes de concluir a an\u00e1lise gerencial."
                    : `${analiseGestor.resumo.itens_sem_decisao} item(ns) ainda aguardam decis\u00e3o do gestor.`}
              </div>
            </>
          )}
        </section>
      )}

      {inventario.tipo === "ROTATIVO" &&
        permissoesUsuario.has("PLANO_ACAO_VISUALIZAR") && (
          <OcorrenciasInventario idInventario={inventario.id_inventario} />
        )}
      {(modulosPrincipais.length > 0 ||
        totalConsultasSecundarias > 0) && (
        <section className="rounded-lg border bg-card p-5 shadow-xs">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="font-semibold">
                {"M\u00f3dulos do invent\u00e1rio"}
              </h2>

              <p className="mt-1 text-sm text-muted-foreground">
                {contextoModulos.descricao}
              </p>
            </div>

            <span className="inline-flex w-fit shrink-0 rounded-full border bg-muted/40 px-3 py-1 text-xs font-semibold text-muted-foreground">
              {contextoModulos.titulo}
            </span>
          </div>

          {modulosPrincipais.length > 0 && (
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {modulosPrincipais.map(
                (modulo) => (
                  <Link
                    key={modulo.to}
                    to={modulo.to}
                    search={{
                      inventario:
                        inventario.id_inventario,
                    }}
                    className={`group relative flex min-h-36 flex-col justify-between rounded-lg border p-4 transition ${
                      modulo.recomendado
                        ? "border-primary/50 bg-primary/5 shadow-sm ring-1 ring-primary/10 hover:border-primary"
                        : "bg-background hover:border-primary hover:bg-muted/30"
                    }`}
                  >
                    <div>
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <h3
                          className={`font-semibold ${
                            modulo.recomendado
                              ? "text-primary"
                              : "text-foreground group-hover:text-primary"
                          }`}
                        >
                          {modulo.nome}
                        </h3>

                        {modulo.recomendado ? (
                          <span className="rounded-full bg-primary px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-primary-foreground">
                            Recomendado agora
                          </span>
                        ) : (
                          <span className="rounded-full border bg-muted/30 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                            {"Opera\u00e7\u00e3o"}
                          </span>
                        )}
                      </div>

                      <p className="mt-2 text-sm text-muted-foreground">
                        {modulo.descricao}
                      </p>
                    </div>

                    <span className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-primary">
                      {modulo.recomendado
                        ? "Abrir etapa"
                        : "Abrir opera\u00e7\u00e3o"}
                      <span aria-hidden="true">
                        {" \u2192"}
                      </span>
                    </span>
                  </Link>
                ),
              )}
            </div>
          )}

          {totalConsultasSecundarias > 0 && (
            <details className="group mt-4 overflow-hidden rounded-lg border bg-muted/10">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-3 transition hover:bg-muted/30">
                <div>
                  <div className="text-sm font-semibold text-foreground">
                    Outras consultas
                  </div>

                  <div className="mt-0.5 text-xs text-muted-foreground">
                    {totalConsultasSecundarias}{" "}
                    {totalConsultasSecundarias === 1
                      ? "acesso dispon\u00edvel"
                      : "acessos dispon\u00edveis"}
                  </div>
                </div>

                <span className="shrink-0 text-xs font-semibold text-primary">
                  Expandir
                </span>
              </summary>

              <div className="border-t p-3">
                <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                  {modulosSecundarios.map(
                    (modulo) => (
                      <Link
                        key={modulo.to}
                        to={modulo.to}
                        search={{
                          inventario:
                            inventario.id_inventario,
                        }}
                        className="group flex min-h-28 flex-col justify-between rounded-md border bg-background p-3 transition hover:border-primary hover:bg-muted/30"
                      >
                        <div>
                          <div className="flex items-start justify-between gap-2">
                            <h3 className="text-sm font-semibold text-foreground group-hover:text-primary">
                              {modulo.nome}
                            </h3>

                            <span className="shrink-0 rounded-full border bg-muted/30 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                              Consulta
                            </span>
                          </div>

                          <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                            {modulo.descricao}
                          </p>
                        </div>

                        <span className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-primary">
                          Consultar
                          <span aria-hidden="true">
                            {" \u2192"}
                          </span>
                        </span>
                      </Link>
                    ),
                  )}

                  {snapshotProntoModulos && (
                    <Link
                      to="/inventarios/$idInventario/estoque-escopo"
                      params={{ idInventario }}
                      className="group flex min-h-28 flex-col justify-between rounded-md border bg-background p-3 transition hover:border-primary hover:bg-muted/30"
                    >
                      <div>
                        <div className="flex items-start justify-between gap-2">
                          <h3 className="text-sm font-semibold text-foreground group-hover:text-primary">
                            Snapshot do inventário
                          </h3>

                          <span className="shrink-0 rounded-full border bg-muted/30 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                            Somente leitura
                          </span>
                        </div>

                        <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                          Consultar o estoque congelado utilizado como referência deste inventário.
                        </p>
                      </div>

                      <span className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-primary">
                        Consultar snapshot
                        <span aria-hidden="true">
                          {" →"}
                        </span>
                      </span>
                    </Link>
                  )}
                  {podeVerRegrasModulo && (
                    <Link
                      to="/inventarios/$idInventario/configuracao"
                      params={{ idInventario }}
                      className="group flex min-h-28 flex-col justify-between rounded-md border bg-background p-3 transition hover:border-primary hover:bg-muted/30"
                    >
                      <div>
                        <div className="flex items-start justify-between gap-2">
                          <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground group-hover:text-primary">
                            <Settings2 className="size-4" />
                            {"Configura\u00e7\u00e3o aplicada"}
                          </h3>

                          <span className="shrink-0 rounded-full border bg-muted/30 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                            {encerradoModulos ||
                            !permissoesUsuario.has(
                              "CONFIGURACAO_EDITAR",
                            )
                              ? "Somente leitura"
                              : "Configura\u00e7\u00e3o"}
                          </span>
                        </div>

                        <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                          {encerradoModulos
                            ? "Consultar as regras e o hist\u00f3rico preservados no encerramento deste invent\u00e1rio."
                            : "Consultar as regras exclusivas e as permiss\u00f5es de edi\u00e7\u00e3o deste invent\u00e1rio."}
                        </p>
                      </div>

                      <span className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-primary">
                        Consultar configuração
                        <span aria-hidden="true">
                          {" \u2192"}
                        </span>
                      </span>
                    </Link>
                  )}
                </div>
              </div>
            </details>
          )}
        </section>
      )}

      <section className="rounded-lg border border-border bg-card p-5 shadow-xs">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="font-semibold text-foreground">
              {"Linha do tempo do invent\u00e1rio"}
            </h2>

            <p className="mt-1 text-sm text-muted-foreground">
              {
                "Acompanhe os eventos mais recentes e a rastreabilidade operacional."
              }
            </p>
          </div>

          <Link
            to="/auditoria"
            search={{
              inventario: inventario.id_inventario,
            }}
            className="inline-flex h-10 shrink-0 items-center justify-center rounded-md border border-border bg-background px-4 text-sm font-medium text-foreground transition hover:border-primary hover:bg-muted"
          >
            {"Ver auditoria completa"}
          </Link>
        </div>

        {carregandoAuditoria && (
          <div className="mt-4 flex items-center gap-2 rounded-md border border-border bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            {"Carregando linha do tempo..."}
          </div>
        )}

        {erroAuditoria && (
          <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">
            {erroAuditoria}
          </div>
        )}

        {auditoriaResumo && !carregandoAuditoria && (
          <>
            <div className="mt-4 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              <span className="inline-flex rounded-full border border-border bg-muted/40 px-3 py-1 font-medium text-foreground">
                {auditoriaResumo.resumo.total_eventos}{" "}
                {auditoriaResumo.resumo.total_eventos === 1
                  ? "evento registrado"
                  : "eventos registrados"}
              </span>

              {auditoriaResumo.resumo.ultimo_evento && (
                <span>
                  {"\u00daltimo evento: "}
                  <strong className="font-medium text-foreground">
                    {formatarData(auditoriaResumo.resumo.ultimo_evento)}
                  </strong>
                </span>
              )}
            </div>

            {auditoriaResumo.eventos.length === 0 ? (
              <div className="mt-4 rounded-md border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
                {
                  "Nenhum evento de auditoria foi encontrado para este invent\u00e1rio."
                }
              </div>
            ) : (
              <div className="relative mt-5 space-y-4 before:absolute before:bottom-3 before:left-[7px] before:top-3 before:w-px before:bg-border">
                {auditoriaResumo.eventos.map((evento, indice) => (
                  <div
                    key={`${evento.data_hora}-${evento.tipo_evento}-${evento.entidade_id ?? indice}`}
                    className="relative pl-7"
                  >
                    <span
                      className="absolute left-0 top-2 size-[15px] rounded-full border-4 border-card bg-primary"
                      aria-hidden="true"
                    />

                    <div className="rounded-md border border-border bg-muted/15 px-4 py-3">
                      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <div className="font-medium text-foreground">
                            {evento.titulo ||
                              formatarEventoAuditoria(evento.tipo_evento)}
                          </div>

                          <div className="mt-0.5 text-xs text-muted-foreground">
                            {formatarEventoAuditoria(evento.tipo_evento)}

                            {evento.categoria
                              ? ` \u00b7 ${evento.categoria}`
                              : ""}
                          </div>
                        </div>

                        <time className="shrink-0 text-xs text-muted-foreground">
                          {formatarData(evento.data_hora)}
                        </time>
                      </div>

                      {evento.descricao && (
                        <p className="mt-2 text-sm text-muted-foreground">
                          {evento.descricao}
                        </p>
                      )}

                      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                        {evento.usuario && (
                          <span>
                            {"Usu\u00e1rio: "}
                            <strong className="font-medium text-foreground">
                              {evento.usuario}
                            </strong>
                          </span>
                        )}

                        {evento.localizacao && (
                          <span>
                            {"Localiza\u00e7\u00e3o: "}
                            <strong className="font-medium text-foreground">
                              {evento.localizacao}
                            </strong>
                          </span>
                        )}

                        {evento.codigo && (
                          <span>
                            {"C\u00f3digo: "}
                            <strong className="font-medium text-foreground">
                              {evento.codigo}
                            </strong>
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </section>
    </main>
  );
}

function rotuloTipoRodada(tipo: string | null | undefined) {
  const rotulos: Record<string, string> = {
    COMPLETA: "Completa",
    DIVERGENCIAS: "Divergências",
    GESTOR: "Gestor",
    FINALIZADO: "Finalizado",
    NAO_CONFIGURADA: "Não configurada",
  };

  return rotulos[String(tipo ?? "").toUpperCase()] ?? tipo ?? "-";
}

function descricaoTipoRodada(tipo: string | null | undefined) {
  const descricoes: Record<string, string> = {
    COMPLETA: "Todos os itens e localizações previstos entram nesta rodada.",

    DIVERGENCIAS: "Somente os itens divergentes seguem para recontagem.",

    GESTOR: "As divergências seguem para análise e decisão gerencial.",

    FINALIZADO: "Não existem outras rodadas configuradas.",

    NAO_CONFIGURADA:
      "A próxima rodada não foi configurada para este inventário.",
  };

  return (
    descricoes[String(tipo ?? "").toUpperCase()] ??
    "Etapa configurada para o inventário."
  );
}

function mensagemSituacaoRodada(
  preview: PreviewProximaRodadaResposta["preview"] | null,
) {
  if (!preview) {
    return "A situação da próxima rodada ainda não foi carregada.";
  }

  if (preview.pode_criar) {
    const numero = preview.numero_proxima_rodada
      ? `R${preview.numero_proxima_rodada}`
      : "A próxima rodada";

    return `${numero} está liberada para geração.`;
  }

  const mensagens: Record<string, string> = {
    MAX_RODADAS_ATINGIDO:
      "O inventário atingiu o número máximo de rodadas configurado.",

    FLUXO_FINALIZADO: "Todas as rodadas configuradas foram executadas.",

    PROXIMA_RODADA_NAO_CONFIGURADA:
      "Não existe uma próxima rodada configurada.",

    SESSOES_ABERTAS:
      "Existem localizações em contagem. Encerre todas as sessões antes de gerar a próxima rodada.",

    RODADA_JA_EXISTE:
      "A próxima rodada já foi criada. Atualize o controle para visualizar a rodada atual.",

    RODADA_OPERACIONAL_NAO_CONCLUIDA:
      "A rodada atual ainda possui contagens pendentes.",

    PROXIMA_ETAPA_GESTOR:
      "A próxima etapa é a análise gerencial das divergências.",

    TIPO_NAO_SUPORTADO:
      "O tipo configurado para a próxima rodada não pode ser gerado automaticamente.",

    SEM_CANDIDATOS: "Não existem divergências elegíveis para uma nova rodada.",

    INVENTARIO_NAO_ABERTO:
      "O inventário não está aberto para gerar outra rodada.",

    R2_ROTATIVO_PRONTA_PARA_ENCERRAR:
      "A segunda rodada está concluída e o inventário pode ser finalizado.",

    R2_ROTATIVO_NAO_CONCLUIDA:
      "A segunda rodada ainda possui contagens pendentes.",
  };

  if (preview.motivo && mensagens[preview.motivo]) {
    if (preview.motivo === "SESSOES_ABERTAS" && preview.sessoes_abertas) {
      return (
        `${mensagens[preview.motivo]} ` +
        `Sessões abertas: ${preview.sessoes_abertas}.`
      );
    }

    return mensagens[preview.motivo];
  }

  return preview.motivo
    ? preview.motivo.replaceAll("_", " ").toLocaleLowerCase("pt-BR")
    : "A próxima rodada ainda não está disponível.";
}

function PainelContextoLocalizacaoRotativa({
  contexto,
  fechar,
}: {
  contexto: ContextoLocalizacaoRotativaResposta;
  fechar: () => void;
}) {
  const historico = contexto.historico.resumo;
  const cicloLocalizacao = contexto.ciclo?.localizacao;

  return (
    <section className="space-y-5 rounded-lg border-2 border-primary/20 bg-background p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Contexto gerencial da localização
          </div>
          <h4 className="mt-1 font-mono text-xl font-semibold">
            {contexto.localizacao}
          </h4>
          <div className="mt-2 flex flex-wrap gap-2">
            <StatusBadge status={contexto.cadastro.status} />
            {contexto.ciclo ? (
              <StatusBadge
                status={
                  contexto.ciclo.localizacao_pertence_ciclo
                    ? `Ciclo: ${contexto.ciclo.status}`
                    : "Fora do ciclo atual"
                }
              />
            ) : (
              <StatusBadge status="Sem ciclo aberto" />
            )}
            {contexto.divergencias.possui_recorrencia ? (
              <span className="rounded-full bg-violet-100 px-2.5 py-1 text-xs font-semibold text-violet-700">
                Divergência recorrente
              </span>
            ) : null}
          </div>
        </div>

        <button
          type="button"
          onClick={fechar}
          className="inline-flex h-9 items-center justify-center rounded-md border bg-background px-3 text-sm font-medium hover:bg-muted"
        >
          Fechar
        </button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <ContextoResumo
          titulo="Score de risco"
          valor={
            contexto.risco.score === null
              ? "-"
              : formatarValor(contexto.risco.score)
          }
        />
        <ContextoResumo titulo="Contagens" valor={historico.contagens} />
        <ContextoResumo
          titulo="Com divergência"
          valor={historico.contagens_com_divergencia}
        />
        <ContextoResumo
          titulo="Ocorrências pendentes"
          valor={contexto.divergencias.ocorrencias_pendentes}
        />
      </div>

      <div className="grid gap-4 rounded-md bg-muted/25 p-4 sm:grid-cols-2 lg:grid-cols-4">
        <ContextoInfo
          titulo="Classificação de risco"
          valor={contexto.risco.classificacao ?? "-"}
        />
        <ContextoInfo
          titulo="Prioridade"
          valor={contexto.priorizacao.prioridade ?? "-"}
        />
        <ContextoInfo
          titulo="Tipo de sugestão"
          valor={contexto.priorizacao.tipo_sugestao ?? "-"}
        />
        <ContextoInfo
          titulo="Taxa de divergência"
          valor={`${formatarValor(historico.taxa_divergencia_percentual)}%`}
        />
        <ContextoInfo
          titulo="Divergências consecutivas"
          valor={historico.divergencias_consecutivas}
        />
        <ContextoInfo
          titulo="Última contagem"
          valor={formatarData(historico.ultima_contagem)}
        />
        <ContextoInfo
          titulo="Última divergência"
          valor={formatarData(historico.ultima_divergencia)}
        />
        <ContextoInfo
          titulo="Situação no ciclo"
          valor={cicloLocalizacao?.status ?? "Não pertence ao ciclo"}
        />
      </div>

      <div className="space-y-3">
        <div>
          <h5 className="font-medium">Histórico de contagens</h5>
          <p className="text-sm text-muted-foreground">
            Últimas {contexto.historico.contagens.length} contagens retornadas.
          </p>
        </div>

        {contexto.historico.contagens.length === 0 ? (
          <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
            A localização ainda não possui histórico de contagem.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="bg-muted/50 text-left">
                <tr className="border-b">
                  <th className="px-3 py-2.5 font-medium">Data</th>
                  <th className="px-3 py-2.5 font-medium">Inventário</th>
                  <th className="px-3 py-2.5 font-medium">Rodada</th>
                  <th className="px-3 py-2.5 font-medium">Usuário</th>
                  <th className="px-3 py-2.5 text-center font-medium">Itens</th>
                  <th className="px-3 py-2.5 text-center font-medium">
                    Divergentes
                  </th>
                  <th className="px-3 py-2.5 text-center font-medium">
                    Resultado
                  </th>
                </tr>
              </thead>
              <tbody>
                {contexto.historico.contagens.map((contagem) => (
                  <tr
                    key={contagem.id_historico}
                    className="border-b last:border-b-0"
                  >
                    <td className="px-3 py-2.5">
                      {formatarData(contagem.data_hora_contagem)}
                    </td>
                    <td className="px-3 py-2.5">
                      {contagem.id_inventario ?? "-"}
                    </td>
                    <td className="px-3 py-2.5">{contagem.id_rodada ?? "-"}</td>
                    <td className="px-3 py-2.5">{contagem.usuario ?? "-"}</td>
                    <td className="px-3 py-2.5 text-center">
                      {contagem.quantidade_itens ?? 0}
                    </td>
                    <td className="px-3 py-2.5 text-center">
                      {contagem.quantidade_itens_divergentes ?? 0}
                    </td>
                    <td className="px-3 py-2.5 text-center">
                      <span
                        className={
                          contagem.possui_divergencia
                            ? "font-semibold text-red-600"
                            : "font-semibold text-green-600"
                        }
                      >
                        {contagem.possui_divergencia ? "Divergente" : "OK"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h5 className="font-medium">Divergências e tratativas</h5>
            <p className="text-sm text-muted-foreground">
              Agrupadas por código e lote na localização.
            </p>
          </div>
          <div className="text-sm text-muted-foreground">
            {contexto.divergencias.grupos_recorrentes} recorrente(s) ·{" "}
            {contexto.divergencias.grupos_pendentes} pendente(s)
          </div>
        </div>

        {contexto.divergencias.grupos.length === 0 ? (
          <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
            Nenhuma divergência registrada para esta localização.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="bg-muted/50 text-left">
                <tr className="border-b">
                  <th className="px-3 py-2.5 font-medium">Código</th>
                  <th className="px-3 py-2.5 font-medium">Lote</th>
                  <th className="px-3 py-2.5 text-center font-medium">
                    Ocorrências
                  </th>
                  <th className="px-3 py-2.5 text-center font-medium">
                    Pendentes
                  </th>
                  <th className="px-3 py-2.5 text-center font-medium">
                    Recorrência
                  </th>
                  <th className="px-3 py-2.5 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {contexto.divergencias.grupos.map((grupo) => (
                  <tr
                    key={`${grupo.localizacao}-${grupo.codigo}-${grupo.lote ?? ""}`}
                    className="border-b last:border-b-0"
                  >
                    <td className="px-3 py-2.5 font-mono font-medium">
                      {grupo.codigo}
                    </td>
                    <td className="px-3 py-2.5">{grupo.lote || "-"}</td>
                    <td className="px-3 py-2.5 text-center">
                      {grupo.ocorrencias}
                    </td>
                    <td className="px-3 py-2.5 text-center">
                      {grupo.resumo.pendentes}
                    </td>
                    <td className="px-3 py-2.5 text-center">
                      {grupo.recorrente ? "Sim" : "Não"}
                    </td>
                    <td className="px-3 py-2.5">
                      <StatusBadge
                        status={formatarStatusTecnico(grupo.status_tratativa)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {contexto.eficacia.resolucoes.length > 0 ? (
        <div className="space-y-3">
          <h5 className="font-medium">Eficácia das resoluções</h5>
          <div className="grid gap-3 md:grid-cols-2">
            {contexto.eficacia.resolucoes.map((resolucao) => (
              <div
                key={resolucao.id_ocorrencia}
                className="rounded-md border p-3 text-sm"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-mono font-medium">
                    {resolucao.codigo} · {resolucao.lote || "Sem lote"}
                  </span>
                  <StatusBadge
                    status={formatarStatusTecnico(
                      resolucao.eficacia?.classificacao ?? "SEM_AVALIACAO",
                    )}
                  />
                </div>
                <p className="mt-2 text-muted-foreground">
                  {resolucao.eficacia?.motivo ??
                    "Resolução ainda sem avaliação."}
                </p>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function ContextoInfo({
  titulo,
  valor,
}: {
  titulo: string;
  valor: string | number;
}) {
  return (
    <div>
      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {titulo}
      </div>
      <div className="mt-1 text-sm font-semibold">{valor}</div>
    </div>
  );
}

function ContextoResumo({
  titulo,
  valor,
}: {
  titulo: string;
  valor: string | number;
}) {
  return (
    <div className="rounded-md border bg-muted/20 p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {titulo}
      </div>
      <div className="mt-1 text-xl font-semibold">{valor}</div>
    </div>
  );
}

function Info({
  icone,
  titulo,
  valor,
}: {
  icone: React.ReactNode;
  titulo: string;
  valor: string;
}) {
  return (
    <div>
      <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {icone}
        {titulo}
      </div>

      <div className="mt-1 text-sm font-medium">{valor}</div>
    </div>
  );
}

function Resumo({ titulo, valor }: { titulo: string; valor: number | string }) {
  return (
    <div className="rounded-md border bg-muted/20 p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {titulo}
      </div>

      <div className="mt-1 text-xl font-semibold">
        {typeof valor === "number" ? formatarQuantidade(valor) : valor}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className="rounded-full border bg-muted px-2.5 py-1 text-xs font-medium">
      {status}
    </span>
  );
}

function formatarTipo(tipo: string) {
  if (tipo === "ROTATIVO") {
    return "Rotativo";
  }

  if (tipo === "OFICIAL") {
    return "Oficial";
  }

  return tipo;
}

function formatarStatusTecnico(status: string) {
  return status.replaceAll("_", " ");
}

function formatarValor(valor: number | null) {
  if (valor === null) {
    return "-";
  }

  return new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 6,
  }).format(valor);
}

function formatarQuantidade(valor: number | null) {
  if (valor === null) {
    return "-";
  }

  return new Intl.NumberFormat("pt-BR", {
    maximumFractionDigits: 3,
  }).format(valor);
}

function formatarEventoAuditoria(valor: string) {
  return valor
    .replaceAll("_", " ")
    .toLocaleLowerCase("pt-BR")
    .replace(/(^|\s)\S/g, (letra) => letra.toLocaleUpperCase("pt-BR"));
}

function ResumoGerencial({
  titulo,
  valor,
  destaque = false,
}: {
  titulo: string;
  valor: number;
  destaque?: boolean;
}) {
  return (
    <div
      className={`rounded-md border bg-background/70 px-4 py-3 ${
        destaque ? "border-amber-400" : "border-border"
      }`}
    >
      <div className="text-xs font-medium text-muted-foreground">{titulo}</div>

      <div
        className={`mt-1 text-xl font-bold ${
          destaque ? "text-amber-700 dark:text-amber-300" : "text-foreground"
        }`}
      >
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

  return Number.isNaN(data.getTime()) ? valor : data.toLocaleString("pt-BR");
}
