import { createFileRoute, redirect } from "@tanstack/react-router";

interface PesquisaLegada {
  inventario?: number;
  ocorrencia?: number;
}

export const Route = createFileRoute("/tratativas_/Ocorrencias")({
  head: () => ({
    meta: [{ title: "Ocorr\u00eancias Rotativas \u2014 SGI" }],
  }),
  validateSearch: (search: Record<string, unknown>): PesquisaLegada => {
    const inventario = inteiroPositivo(search["inventario"]);
    const ocorrencia = inteiroPositivo(search["ocorrencia"]);

    return {
      ...(inventario !== null ? { inventario } : {}),
      ...(ocorrencia !== null ? { ocorrencia } : {}),
    };
  },
  beforeLoad: ({ search }) => {
    throw redirect({
      to: "/historico",
      search: {
        aba: "tratativas",
        ...(search.inventario !== undefined
          ? { tratativa_inventario: search.inventario }
          : {}),
        ...(search.ocorrencia !== undefined
          ? { ocorrencia: search.ocorrencia }
          : {}),
      },
      replace: true,
    });
  },
});

function inteiroPositivo(valor: unknown): number | null {
  const numero = Number(valor);
  return Number.isInteger(numero) && numero > 0 ? numero : null;
}
