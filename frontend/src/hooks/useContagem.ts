import { useCallback, useMemo, useRef, useState } from "react";
import { z } from "zod";
import {
  cancelarContagem as cancelarContagemService,
  buscarProdutoContagem,
  encerrarLocalizacao as encerrarLocalizacaoService,
  iniciarLocalizacao as iniciarLocalizacaoService,
  listarItens,
  registrarItem,
  type ContagemAtualLocalizacao,
  type ConfiguracaoOperacionalInventario,
  type ProdutoContagem,
} from "@/services/contagemService";
import type {
  ContagemItem,
  ContextoContagem,
  Localizacao,
  ResumoContagem,
} from "@/types/inventory";

interface SalvarItemInput {
  codigo: string;
  lote: string;
  quantidade: string;
}

interface Resultado {
  ok: boolean;
  erro?: string;
}

interface ResultadoProduto extends Resultado {
  produto?: ProdutoContagem;
}

function primeiraMensagem(erro: unknown, fallback: string): string {
  if (erro instanceof z.ZodError) return erro.issues[0]?.message ?? fallback;
  if (erro instanceof Error) return erro.message || fallback;
  return fallback;
}

function chaveSessao(idInventario: number): string {
  return `sgi:contagem:${idInventario}:sessao`;
}

function guardarSessao(idInventario: number, localizacao: Localizacao): void {
  if (typeof window === "undefined") return;

  try {
    window.sessionStorage.setItem(
      chaveSessao(idInventario),
      JSON.stringify({
        idSessao: localizacao.idSessao,
        codigo: localizacao.codigo,
      }),
    );
  } catch {
    // A contagem continua funcionando quando o navegador bloqueia o storage.
  }
}

function removerSessaoGuardada(idInventario: number): void {
  if (typeof window === "undefined") return;

  try {
    window.sessionStorage.removeItem(chaveSessao(idInventario));
  } catch {
    // Nada a fazer quando o navegador bloqueia o storage.
  }
}

function lerSessaoGuardada(
  idInventario: number,
): { idSessao: number; codigo: string } | null {
  if (typeof window === "undefined") return null;

  try {
    const valor = window.sessionStorage.getItem(chaveSessao(idInventario));
    if (!valor) return null;

    const dados = JSON.parse(valor) as {
      idSessao?: unknown;
      codigo?: unknown;
    };
    const idSessao = Number(dados.idSessao);
    const codigo = typeof dados.codigo === "string" ? dados.codigo.trim() : "";

    if (!Number.isSafeInteger(idSessao) || idSessao <= 0 || !codigo) {
      removerSessaoGuardada(idInventario);
      return null;
    }

    return { idSessao, codigo };
  } catch {
    removerSessaoGuardada(idInventario);
    return null;
  }
}

export function useContagem(
  contexto: ContextoContagem | null,
  configuracao: ConfiguracaoOperacionalInventario | null,
) {
  const [localizacao, setLocalizacao] = useState<Localizacao | null>(null);
  const [itens, setItens] = useState<ContagemItem[]>([]);
  const [salvando, setSalvando] = useState(false);
  const [cancelando, setCancelando] = useState(false);
  const operacaoEmCurso = useRef(false);
  const restauracaoTentada = useRef<number | null>(null);

  const resumo: ResumoContagem = useMemo(
    () => ({
      itensRegistrados: itens.length,
      quantidadeTotal: itens.reduce(
        (total, item) => total + item.quantidade,
        0,
      ),
    }),
    [itens],
  );

  const iniciarLocalizacao = useCallback(
    async (valor: string): Promise<Resultado> => {
      if (!contexto) {
        return {
          ok: false,
          erro: "Contexto do inventário ainda não carregado.",
        };
      }

      try {
        const nova = await iniciarLocalizacaoService({
          idInventario: contexto.idInventario,
          idRodada: contexto.idRodada,
          localizacao: valor,
        });

        const itensExistentes = await listarItens(nova.idSessao);
        const localizacaoIniciada: Localizacao = {
          ...nova,
          tipoInventario: contexto.tipoInventario,
          rodada: contexto.numeroRodada,
        };
        setLocalizacao(localizacaoIniciada);
        setItens(itensExistentes);
        guardarSessao(contexto.idInventario, localizacaoIniciada);
        return { ok: true };
      } catch (erro) {
        return {
          ok: false,
          erro: primeiraMensagem(erro, "Localização inválida."),
        };
      }
    },
    [contexto],
  );

  const restaurarContagemAtual = useCallback(
    async (localizacoes: ContagemAtualLocalizacao[]): Promise<Resultado> => {
      if (!contexto || localizacao) return { ok: true };
      if (restauracaoTentada.current === contexto.idInventario) {
        return { ok: true };
      }

      restauracaoTentada.current = contexto.idInventario;
      const sessaoGuardada = lerSessaoGuardada(contexto.idInventario);
      if (!sessaoGuardada) return { ok: true };

      const sessaoAberta = localizacoes.find(
        (item) =>
          item.status === "EM_CONTAGEM" &&
          Number(item.id_sessao) === sessaoGuardada.idSessao &&
          item.localizacao.trim().toUpperCase() ===
            sessaoGuardada.codigo.toUpperCase(),
      );

      if (!sessaoAberta || !sessaoAberta.id_sessao) {
        removerSessaoGuardada(contexto.idInventario);
        return { ok: true };
      }

      try {
        const itensExistentes = await listarItens(sessaoAberta.id_sessao);
        const localizacaoRestaurada: Localizacao = {
          idSessao: sessaoAberta.id_sessao,
          codigo: sessaoAberta.localizacao,
          iniciadaEm: new Date().toISOString(),
          tipoInventario: contexto.tipoInventario,
          rodada: contexto.numeroRodada,
        };

        setLocalizacao(localizacaoRestaurada);
        setItens(itensExistentes);
        return { ok: true };
      } catch (erro) {
        removerSessaoGuardada(contexto.idInventario);
        return {
          ok: false,
          erro: primeiraMensagem(
            erro,
            "Não foi possível retomar a localização em andamento.",
          ),
        };
      }
    },
    [contexto, localizacao],
  );

  const validarCodigo = useCallback(
    async (codigo: string): Promise<ResultadoProduto> => {
      if (!contexto || !configuracao) {
        return { ok: false, erro: "Contexto da contagem ainda não carregado." };
      }

      const configuracaoAtual = configuracao;

      const codigoNormalizado = codigo.trim();

      if (!codigoNormalizado) {
        return configuracaoAtual.codigo.obrigatorio
          ? { ok: false, erro: "Informe o código do produto." }
          : { ok: true };
      }

      const deveConsultarProduto =
        configuracaoAtual.codigo.validar_estoque ||
        configuracaoAtual.lote.obrigatorio_quando_existir ||
        configuracaoAtual.lote.validar_codigo;

      if (!deveConsultarProduto) return { ok: true };

      try {
        const produto = await buscarProdutoContagem(
          contexto.idInventario,
          codigoNormalizado,
        );
        return { ok: true, produto };
      } catch (erro) {
        if (!configuracaoAtual.codigo.validar_estoque) {
          // Códigos fora do snapshot podem representar sobras físicas.
          // O POST continua responsável pela validação definitiva.
          return { ok: true };
        }

        return {
          ok: false,
          erro: primeiraMensagem(
            erro,
            "Produto não encontrado no estoque deste inventário.",
          ),
        };
      }
    },
    [configuracao, contexto],
  );

  const salvarItem = useCallback(
    async ({
      codigo,
      lote,
      quantidade,
    }: SalvarItemInput): Promise<Resultado> => {
      if (!localizacao)
        return { ok: false, erro: "Nenhuma localização ativa." };

      if (!configuracao) {
        return { ok: false, erro: "Configuração operacional não carregada." };
      }

      if (configuracao.codigo.obrigatorio && !codigo.trim()) {
        return { ok: false, erro: "Informe o código do produto." };
      }

      if (configuracao.quantidade.obrigatoria && !quantidade.trim()) {
        return { ok: false, erro: "Informe a quantidade." };
      }

      if (operacaoEmCurso.current)
        return { ok: false, erro: "Aguarde a operação em andamento." };
      operacaoEmCurso.current = true;
      const quantidadeNumerica = quantidade.trim()
        ? Number(String(quantidade).replace(",", "."))
        : 0;

      if (!Number.isFinite(quantidadeNumerica)) {
        operacaoEmCurso.current = false;
        return { ok: false, erro: "Quantidade inválida." };
      }

      if (
        quantidade.trim() &&
        quantidadeNumerica < configuracao.quantidade.minimo
      ) {
        operacaoEmCurso.current = false;
        return {
          ok: false,
          erro: `A quantidade mínima permitida é ${configuracao.quantidade.minimo}.`,
        };
      }

      if (
        quantidade.trim() &&
        quantidadeNumerica > configuracao.quantidade.maximo
      ) {
        operacaoEmCurso.current = false;
        return {
          ok: false,
          erro: `A quantidade máxima permitida é ${configuracao.quantidade.maximo}.`,
        };
      }

      setSalvando(true);

      try {
        const item = await registrarItem({
          idSessao: localizacao.idSessao,
          localizacao: localizacao.codigo,
          codigo,
          lote,
          quantidade: quantidadeNumerica,
        });
        setItens((atuais) => [item, ...atuais]);

        // O GET da sessão retorna o nome do produto no campo `produto`.
        // Se o refresh falhar, o registro salvo permanece visível na lista.
        try {
          const itensAtualizados = await listarItens(localizacao.idSessao);
          setItens(itensAtualizados);
        } catch {
          // O POST já foi concluído com sucesso.
        }

        return { ok: true };
      } catch (erro) {
        return {
          ok: false,
          erro: primeiraMensagem(erro, "Não foi possível salvar o item."),
        };
      } finally {
        operacaoEmCurso.current = false;
        setSalvando(false);
      }
    },
    [configuracao, localizacao],
  );

  const cancelarItem = useCallback(
    async (id: string): Promise<Resultado> => {
      if (
        !localizacao ||
        !itens.some(
          (item) => item.id === id && item.idSessao === localizacao.idSessao,
        )
      ) {
        return {
          ok: false,
          erro: "Registro não encontrado na localização ativa.",
        };
      }
      if (operacaoEmCurso.current)
        return { ok: false, erro: "Aguarde a operação em andamento." };
      operacaoEmCurso.current = true;
      setCancelando(true);
      try {
        await cancelarContagemService(id);
        // Atualiza somente após a confirmação da API. O resumo deriva desta lista.
        setItens((atuais) => atuais.filter((item) => item.id !== id));
        return { ok: true };
      } catch (erro) {
        return {
          ok: false,
          erro: primeiraMensagem(erro, "Não foi possível cancelar a contagem."),
        };
      } finally {
        operacaoEmCurso.current = false;
        setCancelando(false);
      }
    },
    [localizacao, itens],
  );

  const encerrarLocalizacao = useCallback(
    async (localizacaoVazia = false): Promise<Resultado> => {
      if (!localizacao) return { ok: true };
      if (operacaoEmCurso.current)
        return { ok: false, erro: "Aguarde a operação em andamento." };
      operacaoEmCurso.current = true;

      try {
        await encerrarLocalizacaoService(
          localizacao.idSessao,
          localizacaoVazia,
        );
        setLocalizacao(null);
        setItens([]);
        if (contexto) removerSessaoGuardada(contexto.idInventario);
        return { ok: true };
      } catch (erro) {
        return {
          ok: false,
          erro: primeiraMensagem(
            erro,
            "Não foi possível encerrar a localização.",
          ),
        };
      } finally {
        operacaoEmCurso.current = false;
      }
    },
    [contexto, localizacao],
  );

  return {
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
  };
}
