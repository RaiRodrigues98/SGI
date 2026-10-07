import { useEffect, useRef, useState } from "react";
import { CircleAlert, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type {
  ConfiguracaoOperacionalInventario,
  ProdutoContagem,
} from "@/services/contagemService";

interface ItemFormProps {
  salvando: boolean;
  configuracao: ConfiguracaoOperacionalInventario;
  onValidarCodigo: (
    codigo: string,
  ) => Promise<{ ok: boolean; produto?: ProdutoContagem; erro?: string }>;
  onSalvar: (dados: {
    codigo: string;
    lote: string;
    quantidade: string;
  }) => Promise<{ ok: boolean; erro?: string }>;
}

type CampoContagem = "codigo" | "lote" | "quantidade";
type ResultadoValidacaoCodigo = {
  ok: boolean;
  produto?: ProdutoContagem;
};

const classesInput =
  "h-14 w-full font-mono text-xl focus-visible:ring-2 focus-visible:ring-gold focus-visible:border-primary";

export function ItemForm({
  salvando,
  configuracao,
  onValidarCodigo,
  onSalvar,
}: ItemFormProps) {
  const [codigo, setCodigo] = useState("");
  const [lote, setLote] = useState("");
  const [quantidade, setQuantidade] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [erroAberto, setErroAberto] = useState(false);
  const [campoErro, setCampoErro] = useState<CampoContagem>("codigo");
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [produtoValidado, setProdutoValidado] =
    useState<ProdutoContagem | null>(null);
  const [validandoCodigo, setValidandoCodigo] = useState(false);

  const codigoRef = useRef<HTMLInputElement>(null);
  const loteRef = useRef<HTMLInputElement>(null);
  const quantidadeRef = useRef<HTMLInputElement>(null);
  const somErroRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    codigoRef.current?.focus();

    const audio = new Audio("/sounds/erro.mp3");
    audio.preload = "auto";
    audio.volume = 1;
    audio.load();

    somErroRef.current = audio;

    return () => {
      audio.pause();
      audio.currentTime = 0;
      somErroRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!sucesso) return;

    const temporizador = window.setTimeout(() => {
      setSucesso(null);
    }, 1800);

    return () => {
      window.clearTimeout(temporizador);
    };
  }, [sucesso]);

  function tocarSomErro() {
    const audio = somErroRef.current;

    if (audio) {
      audio.pause();
      audio.currentTime = 0;
      audio.volume = 1;

      void audio.play().catch(() => {
        // O popup continua funcionando caso o navegador bloqueie o som.
      });
    }

    if (typeof navigator !== "undefined" && "vibrate" in navigator) {
      navigator.vibrate([120, 60, 120]);
    }
  }

  function identificarCampoErro(mensagem: string): CampoContagem {
    const texto = mensagem
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase();

    if (texto.includes("lote")) {
      return "lote";
    }

    if (texto.includes("quantidade") || texto.includes("qtd")) {
      return "quantidade";
    }

    return "codigo";
  }

  function focarCampo(campo: CampoContagem) {
    const referencias = {
      codigo: codigoRef,
      lote: loteRef,
      quantidade: quantidadeRef,
    };

    const input = referencias[campo].current;

    input?.focus();
    input?.select();
  }

  function mostrarErro(mensagem: string, campo?: CampoContagem) {
    const campoIdentificado = campo ?? identificarCampoErro(mensagem);

    setErro(mensagem);
    setCampoErro(campoIdentificado);
    setErroAberto(true);
    tocarSomErro();
  }

  function alterarPopup(aberto: boolean) {
    setErroAberto(aberto);

    if (!aberto) {
      window.setTimeout(() => {
        focarCampo(campoErro);
      }, 0);
    }
  }

  function avancar(
    event: React.KeyboardEvent<HTMLInputElement>,
    proximo: HTMLInputElement | null,
  ) {
    if (
      event.key !== "Enter" ||
      event.repeat ||
      event.nativeEvent.isComposing
    ) {
      return;
    }

    event.preventDefault();
    proximo?.focus();
    proximo?.select();
  }

  function salvarAoPressionarEnter(
    event: React.KeyboardEvent<HTMLInputElement>,
  ) {
    if (
      event.key !== "Enter" ||
      event.repeat ||
      event.nativeEvent.isComposing
    ) {
      return;
    }

    event.preventDefault();

    if (
      salvando ||
      validandoCodigo
    ) {
      return;
    }

    event.currentTarget.form?.requestSubmit();
  }

  async function validarCodigoAtual(): Promise<ResultadoValidacaoCodigo> {
    if (validandoCodigo) return { ok: false as const };

    const codigoAtual = codigo.trim();

    if (configuracao.codigo.obrigatorio && !codigoAtual) {
      mostrarErro("Informe o código.", "codigo");
      return { ok: false as const };
    }

    setValidandoCodigo(true);
    setErro(null);

    try {
      const resultado = await onValidarCodigo(codigoAtual);

      if (!resultado.ok) {
        setProdutoValidado(null);
        mostrarErro(
          resultado.erro ??
            "Produto não encontrado no estoque deste inventário.",
          "codigo",
        );
        return { ok: false as const };
      }

      const produto = resultado.produto ?? null;
      setProdutoValidado(produto);

      if (produto && !produto.possui_lote) setLote("");

      return produto ? { ok: true as const, produto } : { ok: true as const };
    } catch (falha: unknown) {
      setProdutoValidado(null);
      mostrarErro(
        falha instanceof Error
          ? falha.message
          : "Não foi possível validar o produto.",
        "codigo",
      );
      return { ok: false as const };
    } finally {
      setValidandoCodigo(false);
    }
  }

  async function validarCodigoEAvancar() {
    const resultado = await validarCodigoAtual();
    if (!resultado.ok) return;

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        loteRef.current?.focus();
        loteRef.current?.select();
      });
    });
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();

    if (salvando) return;

    setErro(null);
    setSucesso(null);

    if (configuracao.codigo.obrigatorio && !codigo.trim()) {
      mostrarErro("Informe o código.", "codigo");
      return;
    }

    const codigoValidadoCorresponde =
      produtoValidado?.codigo.trim().toLocaleUpperCase("pt-BR") ===
      codigo.trim().toLocaleUpperCase("pt-BR");

    let produtoAtual = codigoValidadoCorresponde ? produtoValidado : null;

    if (codigo.trim() && !codigoValidadoCorresponde) {
      const validacao = await validarCodigoAtual();
      if (!validacao.ok) return;
      produtoAtual = validacao.produto ?? null;
    }

    if (
      produtoAtual?.possui_lote &&
      configuracao.lote.obrigatorio_quando_existir &&
      !lote.trim()
    ) {
      mostrarErro("Informe o lote do produto.", "lote");
      return;
    }

    if (
      produtoAtual?.possui_lote &&
      configuracao.lote.validar_codigo &&
      lote.trim() &&
      !produtoAtual.lotes.some(
        (loteCadastrado) =>
          loteCadastrado.toLocaleUpperCase("pt-BR") ===
          lote.trim().toLocaleUpperCase("pt-BR"),
      )
    ) {
      mostrarErro(
        "Lote não encontrado para este código no inventário.",
        "lote",
      );
      return;
    }

    if (configuracao.quantidade.obrigatoria && !quantidade.trim()) {
      mostrarErro("Informe a quantidade.", "quantidade");
      return;
    }

    const quantidadeNumerica = quantidade.trim()
      ? Number(quantidade.replace(",", "."))
      : 0;

    if (!Number.isFinite(quantidadeNumerica)) {
      mostrarErro("Informe uma quantidade válida.", "quantidade");
      return;
    }

    if (
      quantidade.trim() &&
      quantidadeNumerica < configuracao.quantidade.minimo
    ) {
      mostrarErro(
        `A quantidade mínima permitida é ${configuracao.quantidade.minimo}.`,
        "quantidade",
      );
      return;
    }

    if (
      quantidade.trim() &&
      quantidadeNumerica > configuracao.quantidade.maximo
    ) {
      mostrarErro(
        `A quantidade máxima permitida é ${configuracao.quantidade.maximo}.`,
        "quantidade",
      );
      return;
    }

    const codigoSalvo = codigo;

    try {
      const resultado = await onSalvar({
        codigo: codigo.trim(),
        lote: lote.trim(),
        quantidade: quantidade.trim(),
      });

      if (resultado.ok) {
        setSucesso(
          codigoSalvo.trim()
            ? `Item ${codigoSalvo} registrado.`
            : "Contagem registrada.",
        );
        setCodigo("");
        setLote("");
        setQuantidade("");
        setProdutoValidado(null);
        setErro(null);
        setErroAberto(false);

        window.setTimeout(() => {
          codigoRef.current?.focus();
        }, 0);
      } else {
        setSucesso(null);

        mostrarErro(resultado.erro ?? "Não foi possível salvar o item.");
      }
    } catch (error) {
      setSucesso(null);

      mostrarErro(
        error instanceof Error
          ? error.message
          : "Não foi possível salvar o item.",
      );
    }
  }

  return (
    <>
      <AlertDialog open={erroAberto} onOpenChange={alterarPopup}>
        <AlertDialogContent className="max-w-md text-center">
          <AlertDialogHeader className="items-center text-center">
            <div className="flex size-14 items-center justify-center rounded-full bg-destructive/10 text-destructive">
              <CircleAlert className="size-8" aria-hidden="true" />
            </div>

            <AlertDialogTitle className="text-xl text-destructive">
              Erro na contagem
            </AlertDialogTitle>

            <AlertDialogDescription className="text-center text-base">
              {erro ?? "Não foi possível validar os dados da contagem."}
            </AlertDialogDescription>
          </AlertDialogHeader>

          <AlertDialogFooter className="sm:justify-center">
            <Button
              type="button"
              className="h-12 min-w-32 bg-primary font-bold uppercase"
              onClick={() => alterarPopup(false)}
              autoFocus
            >
              Entendi
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="space-y-1.5">
            <Label
              htmlFor="codigo"
              className="text-sm font-semibold text-primary"
            >
              Código {configuracao.codigo.obrigatorio ? "*" : "(opcional)"}
            </Label>

            <Input
              id="codigo"
              ref={codigoRef}
              value={codigo}
              onChange={(event) => {
                setCodigo(event.target.value);
                setProdutoValidado(null);
              }}
              onKeyDown={(event) => {
                if (
                  event.key !== "Enter" ||
                  event.repeat ||
                  event.nativeEvent.isComposing
                ) {
                  return;
                }

                event.preventDefault();
                void validarCodigoEAvancar();
              }}
              disabled={salvando || validandoCodigo}
              autoComplete="off"
              spellCheck={false}
              enterKeyHint="next"
              required={configuracao.codigo.obrigatorio}
              className={classesInput}
            />
            {validandoCodigo && (
              <p className="flex items-center gap-1 text-xs text-primary">
                <Loader2 className="size-3.5 animate-spin" />
                Validando produto...
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label
              htmlFor="lote"
              className="text-sm font-semibold text-primary"
            >
              Lote
            </Label>

            <Input
              id="lote"
              ref={loteRef}
              value={lote}
              onChange={(event) => setLote(event.target.value)}
              onKeyDown={(event) => avancar(event, quantidadeRef.current)}
              autoComplete="off"
              spellCheck={false}
              enterKeyHint="next"
              disabled={salvando || validandoCodigo}
              className={classesInput}
            />
          </div>

          <div className="space-y-1.5">
            <Label
              htmlFor="quantidade"
              className="text-sm font-semibold text-primary"
            >
              Quantidade{" "}
              {configuracao.quantidade.obrigatoria ? "*" : "(opcional)"}
            </Label>

            <Input
              id="quantidade"
              ref={quantidadeRef}
              value={quantidade}
              onChange={(event) => setQuantidade(event.target.value)}
              inputMode="decimal"
              min={configuracao.quantidade.minimo}
              max={configuracao.quantidade.maximo}
              required={configuracao.quantidade.obrigatoria}
              autoComplete="off"
              enterKeyHint="done"
              onKeyDown={salvarAoPressionarEnter}
              className={classesInput}
            />
          </div>
        </div>

        {sucesso ? (
          <p
            role="status"
            className="rounded-md border border-gold/60 bg-gold-light/40 px-3 py-2 text-sm font-medium text-primary"
          >
            {sucesso}
          </p>
        ) : null}

        <Button
          type="submit"
          disabled={salvando || validandoCodigo}
          className="h-14 w-full bg-primary text-sm font-bold uppercase tracking-wide text-primary-foreground hover:bg-primary/85 lg:w-auto lg:px-10"
        >
          {validandoCodigo
            ? "Validando produto..."
            : salvando
              ? "Salvando..."
              : "Salvar item"}
        </Button>
      </form>
    </>
  );
}
