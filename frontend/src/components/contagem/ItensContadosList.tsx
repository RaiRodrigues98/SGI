import { useMemo, useRef, useState } from "react";
import { Search, Trash2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import type { ContagemItem, ResumoContagem } from "@/types/inventory";

type OrdenacaoItens =
  | "ORDEM_ATUAL"
  | "MAIS_RECENTES"
  | "MAIS_ANTIGOS"
  | "CODIGO_ASC"
  | "CODIGO_DESC"
  | "QUANTIDADE_DESC"
  | "QUANTIDADE_ASC";

function normalizarBusca(valor: unknown): string {
  return String(valor ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLocaleLowerCase("pt-BR");
}

interface ItensContadosListProps {
  itens: ContagemItem[];
  resumo: ResumoContagem;
  bloqueado: boolean;
  onCancelar: (
    id: string,
  ) => Promise<{ ok: boolean; erro?: string }>;
}

export function ItensContadosList({
  itens,
  resumo,
  bloqueado,
  onCancelar,
}: ItensContadosListProps) {
  const [selecionado, setSelecionado] =
    useState<ContagemItem | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [filtroAberto, setFiltroAberto] = useState(false);
  const [busca, setBusca] = useState("");
  const [ordenacao, setOrdenacao] =
    useState<OrdenacaoItens>("ORDEM_ATUAL");
  const emCurso = useRef(false);

  const itensVisiveis = useMemo(() => {
    const termo = normalizarBusca(busca);

    const filtrados = termo
      ? itens.filter((item) => {
          const campos = [
            item.id,
            item.codigo,
            item.descricao,
            item.lote,
            item.quantidade,
          ];

          return campos.some((campo) =>
            normalizarBusca(campo).includes(termo),
          );
        })
      : [...itens];

    if (ordenacao === "ORDEM_ATUAL") {
      return filtrados;
    }

    return [...filtrados].sort((itemA, itemB) => {
      if (
        ordenacao === "MAIS_RECENTES" ||
        ordenacao === "MAIS_ANTIGOS"
      ) {
        const tempoA = Date.parse(
          String(itemA.registradoEm ?? ""),
        );

        const tempoB = Date.parse(
          String(itemB.registradoEm ?? ""),
        );

        const valorA = Number.isNaN(tempoA) ? 0 : tempoA;
        const valorB = Number.isNaN(tempoB) ? 0 : tempoB;

        return ordenacao === "MAIS_RECENTES"
          ? valorB - valorA
          : valorA - valorB;
      }

      if (
        ordenacao === "CODIGO_ASC" ||
        ordenacao === "CODIGO_DESC"
      ) {
        const comparacao = itemA.codigo.localeCompare(
          itemB.codigo,
          "pt-BR",
          {
            numeric: true,
            sensitivity: "base",
          },
        );

        return ordenacao === "CODIGO_ASC"
          ? comparacao
          : -comparacao;
      }

      if (ordenacao === "QUANTIDADE_DESC") {
        return itemB.quantidade - itemA.quantidade;
      }

      if (ordenacao === "QUANTIDADE_ASC") {
        return itemA.quantidade - itemB.quantidade;
      }

      return 0;
    });
  }, [busca, itens, ordenacao]);

  function alternarFiltro() {
    if (filtroAberto) {
      setBusca("");
      setOrdenacao("ORDEM_ATUAL");
    }

    setFiltroAberto((atual) => !atual);
  }

  async function confirmar() {
    if (!selecionado || bloqueado || emCurso.current) {
      return;
    }

    emCurso.current = true;
    setEnviando(true);
    setErro(null);

    try {
      const resultado = await onCancelar(selecionado.id);

      if (!resultado.ok) {
        setErro(
          resultado.erro ||
            "Não foi possível cancelar a contagem.",
        );
        return;
      }

      setSucesso(
        `Contagem #${selecionado.id} cancelada com sucesso.`,
      );
      setSelecionado(null);
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível cancelar a contagem.",
      );
    } finally {
      emCurso.current = false;
      setEnviando(false);
    }
  }

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-primary">
          Itens registrados nesta localização
        </h2>

        <div className="flex shrink-0 items-center gap-1.5">
          <span className="text-xs tabular-nums text-muted-foreground">
            {itens.length}
          </span>

          {itens.length > 0 ? (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-8 text-muted-foreground"
              onClick={alternarFiltro}
              aria-expanded={filtroAberto}
              aria-label={
                filtroAberto
                  ? "Fechar filtro dos itens contados"
                  : "Filtrar itens contados"
              }
              title={
                filtroAberto
                  ? "Fechar filtro"
                  : "Filtrar itens"
              }
            >
              {filtroAberto ? (
                <X
                  className="size-4"
                  aria-hidden="true"
                />
              ) : (
                <Search
                  className="size-4"
                  aria-hidden="true"
                />
              )}
            </Button>
          ) : null}
        </div>
      </div>

      {filtroAberto && itens.length > 0 ? (
        <div className="flex flex-col gap-2 rounded-md border border-border/60 bg-muted/20 p-2 sm:flex-row sm:items-center">
          <div className="relative min-w-0 flex-1">
            <Search
              className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />

            <input
              type="search"
              value={busca}
              onChange={(evento) =>
                setBusca(evento.target.value)
              }
              placeholder={
                "Buscar SKU, lote ou descrição..."
              }
              className="h-8 w-full rounded-md border border-input bg-background px-2 pl-8 text-sm outline-none placeholder:text-muted-foreground focus-visible:ring-1 focus-visible:ring-ring"
              aria-label="Buscar itens contados"
            />
          </div>

          <select
            value={ordenacao}
            onChange={(evento) =>
              setOrdenacao(
                evento.target.value as OrdenacaoItens,
              )
            }
            className="h-8 rounded-md border border-input bg-background px-2 text-xs text-foreground outline-none focus-visible:ring-1 focus-visible:ring-ring"
            aria-label="Classificar itens contados"
          >
            <option value="ORDEM_ATUAL">
              Ordem atual
            </option>

            <option value="MAIS_RECENTES">
              Mais recentes
            </option>

            <option value="MAIS_ANTIGOS">
              Mais antigos
            </option>

            <option value="CODIGO_ASC">
              {"Código A-Z"}
            </option>

            <option value="CODIGO_DESC">
              {"Código Z-A"}
            </option>

            <option value="QUANTIDADE_DESC">
              Maior quantidade
            </option>

            <option value="QUANTIDADE_ASC">
              Menor quantidade
            </option>
          </select>

          <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground">
            {itensVisiveis.length} / {itens.length}
          </span>
        </div>
      ) : null}

      {sucesso ? (
        <p role="status" className="text-sm text-primary">
          {sucesso}
        </p>
      ) : null}

      <AlertDialog
        open={selecionado !== null}
        onOpenChange={(aberto) => {
          if (!aberto && !emCurso.current) {
            setSelecionado(null);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Cancelar registro de contagem?
            </AlertDialogTitle>

            <AlertDialogDescription>
              Registro #{selecionado?.id} · Produto{" "}
              {selecionado?.codigo} · Lote{" "}
              {selecionado?.lote || "—"} · Quantidade{" "}
              {selecionado?.quantidade}. O registro será
              cancelado e deixará de compor os totais desta
              localização.
            </AlertDialogDescription>
          </AlertDialogHeader>

          {erro ? (
            <p role="alert" className="text-sm text-destructive">
              {erro}
            </p>
          ) : null}

          <AlertDialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={enviando}
              onClick={() => setSelecionado(null)}
            >
              Voltar
            </Button>

            <Button
              type="button"
              variant="destructive"
              disabled={bloqueado || enviando}
              onClick={() => void confirmar()}
            >
              {enviando
                ? "Cancelando..."
                : "Confirmar cancelamento"}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {itens.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border bg-card px-3 py-8 text-center text-sm text-muted-foreground">
          Nenhum item registrado ainda.
        </p>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {itensVisiveis.map((item) => (
            <li
              key={item.id}
              className="relative grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3 rounded-lg border border-border bg-card px-4 py-3 pr-14 shadow-xs"
            >
              <div className="min-w-0 space-y-1">
  <p className="break-words text-sm font-medium text-muted-foreground">
    <span className="font-semibold text-primary">SKU:</span>{" "}
    {item.codigo}
  </p>

  <p className="break-words text-sm font-medium text-muted-foreground">
    <span className="font-semibold text-primary">Lote:</span>{" "}
    {item.lote || "—"}
  </p>

  <p className="break-words text-sm font-medium text-muted-foreground">
    <span className="font-semibold text-primary">Descrição:</span>{" "}
    {item.descricao || "—"}
  </p>
</div>

              <div className="shrink-0 text-right">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Qtd.
                </p>

                <p className="font-mono text-xl font-bold text-gold">
                  {item.quantidade}
                </p>
              </div>

              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="absolute bottom-2 right-2 size-10 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                disabled={bloqueado || enviando}
                aria-label={`Cancelar contagem ${item.id} do produto ${item.codigo}`}
                title="Cancelar contagem"
                onClick={() => {
                  setErro(null);
                  setSucesso(null);
                  setSelecionado(item);
                }}
              >
                <Trash2
                  className="size-5"
                  aria-hidden="true"
                />
              </Button>
            </li>
          ))}
        </ul>
      )}

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg border border-border bg-card px-4 py-3">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Itens registrados
          </p>

          <p className="font-mono text-2xl font-bold text-primary">
            {resumo.itensRegistrados}
          </p>
        </div>

        <div className="rounded-lg border border-border bg-card px-4 py-3">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Quantidade total
          </p>

          <p className="font-mono text-2xl font-bold text-gold">
            {resumo.quantidadeTotal}
          </p>
        </div>
      </div>
    </section>
  );
}