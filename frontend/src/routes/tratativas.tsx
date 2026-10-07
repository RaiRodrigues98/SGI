import { createFileRoute, redirect } from "@tanstack/react-router";

interface OcorrenciasSearch {
  inventario?: number;
  ocorrencia?: number;
}

export const Route = createFileRoute("/tratativas")({
  head: () => ({
    meta: [{ title: "Tratativas Rotativas — SGI" }],
  }),
  validateSearch: (search: Record<string, unknown>): OcorrenciasSearch => {
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
  const numeroConvertido = Number(valor);
  return Number.isInteger(numeroConvertido) && numeroConvertido > 0
    ? numeroConvertido
    : null;
}
