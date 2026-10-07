import { createFileRoute } from "@tanstack/react-router";

import { InventarioDetalhePage } from "./inventarios.$idInventario";

export const Route = createFileRoute("/inventarios_/$idInventario/estoque-escopo")({
  head: () => ({
    meta: [
      {
        title: "Estoque e Escopo \u2014 SGI",
      },
    ],
  }),
  component: EstoqueEscopoInventarioRoutePage,
});

function EstoqueEscopoInventarioRoutePage() {
  const { idInventario } = Route.useParams();

  return <InventarioDetalhePage idInventario={idInventario} paginaEstoqueEscopo />;
}
