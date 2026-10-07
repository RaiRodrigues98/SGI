import { useEffect, useRef, useState } from "react";
import { CircleAlert } from "lucide-react";

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
import type { ConfiguracaoOperacionalInventario } from "@/services/contagemService";

interface LocalizacaoFormProps {
  configuracao: ConfiguracaoOperacionalInventario["localizacao"];
  onIniciar: (valor: string) => Promise<{ ok: boolean; erro?: string }>;
}

export function LocalizacaoForm({
  configuracao,
  onIniciar,
}: LocalizacaoFormProps) {
  const [valor, setValor] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [erroAberto, setErroAberto] = useState(false);
  const [processando, setProcessando] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const somErroRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    inputRef.current?.focus();

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

  function mostrarErro(mensagem: string) {
    setErro(mensagem);
    setErroAberto(true);
    tocarSomErro();
  }

  function alterarPopup(aberto: boolean) {
    setErroAberto(aberto);

    if (!aberto) {
      window.setTimeout(() => {
        inputRef.current?.focus();
        inputRef.current?.select();
      }, 0);
    }
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();

    if (processando) return;

    setErro(null);

    if (configuracao.obrigatoria && !valor.trim()) {
      mostrarErro("Informe a localização.");
      return;
    }

    setProcessando(true);

    try {
      const resultado = await onIniciar(valor);

      if (resultado.ok) {
        setValor("");
        setErro(null);
        setErroAberto(false);
      } else {
        mostrarErro(resultado.erro ?? "Localização inválida.");
      }
    } catch (error) {
      mostrarErro(
        error instanceof Error
          ? error.message
          : "Não foi possível validar a localização.",
      );
    } finally {
      setProcessando(false);
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
              Erro na localização
            </AlertDialogTitle>

            <AlertDialogDescription className="text-center text-base">
              {erro ?? "Localização inválida."}
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
        <div className="space-y-1.5">
          <Label
            htmlFor="localizacao"
            className="text-sm font-semibold text-primary"
          >
            Localização {configuracao.obrigatoria ? "*" : "(opcional)"}
          </Label>

          <Input
            id="localizacao"
            ref={inputRef}
            value={valor}
            onChange={(event) => {
              setValor(event.target.value);
              setErro(null);
            }}
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            enterKeyHint="go"
            required={configuracao.obrigatoria}
            className="h-14 w-full font-mono text-xl uppercase focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-gold"
          />

        </div>

        <Button
          type="submit"
          disabled={processando}
          className="h-14 w-full bg-primary text-sm font-bold uppercase tracking-wide text-primary-foreground hover:bg-primary/85"
        >
          {processando ? "Validando..." : "Iniciar localização"}
        </Button>
      </form>
    </>
  );
}
