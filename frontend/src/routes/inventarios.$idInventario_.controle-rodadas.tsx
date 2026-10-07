import { createFileRoute } from "@tanstack/react-router";
import { InventarioDetalhePage } from "./inventarios.$idInventario";

export const Route = createFileRoute(
  "/inventarios/$idInventario_/controle-rodadas",
)({
  head: () => ({ meta: [{ title: "Controle de rodadas — SGI" }] }),
  component: ControleRodadasPage,
});

function ControleRodadasPage() {
  const { idInventario } = Route.useParams();
  return (
    <InventarioDetalhePage idInventario={idInventario} paginaControleRodadas />
  );
}
