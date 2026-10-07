import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

interface EncerrarDialogProps {
  aberto: boolean;
  localizacao: string;
  onOpenChange: (aberto: boolean) => void;
  onConfirmar: () => void;
}

export function EncerrarDialog({
  aberto,
  localizacao,
  onOpenChange,
  onConfirmar,
}: EncerrarDialogProps) {
  return (
    <AlertDialog open={aberto} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Encerrar localização</AlertDialogTitle>
          <AlertDialogDescription>
            Tem certeza que deseja encerrar a localização {localizacao}?
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel className="h-14 text-base font-bold uppercase">
            Cancelar
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirmar}
            className="h-14 bg-destructive text-base font-bold uppercase text-destructive-foreground hover:bg-destructive/90"
          >
            Encerrar
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
