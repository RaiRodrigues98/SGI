export type TipoInventarioAtual =
  | "ROTATIVO"
  | "OFICIAL";

export const EVENTO_INVENTARIO_ATUAL_ALTERADO =
  "sgi:inventario-atual-alterado";

const CHAVE_INVENTARIO_ATUAL =
  "sgi_inventario_atual";

const CHAVE_TIPO_INVENTARIO_ATUAL =
  "sgi_tipo_inventario_atual";

function possuiWindow(): boolean {
  return typeof window !== "undefined";
}

function idValido(
  valor: string | null,
): number | null {
  if (!valor) {
    return null;
  }

  const idInventario = Number(valor);

  return Number.isInteger(idInventario) &&
    idInventario > 0
    ? idInventario
    : null;
}

function normalizarTipo(
  valor: string | null | undefined,
): TipoInventarioAtual | null {
  const tipo = valor
    ?.trim()
    .toUpperCase();

  return tipo === "ROTATIVO" ||
    tipo === "OFICIAL"
    ? tipo
    : null;
}

function obterValor(
  chave: string,
): string | null {
  if (!possuiWindow()) {
    return null;
  }

  try {
    return (
      window.sessionStorage.getItem(chave) ??
      window.localStorage.getItem(chave)
    );
  } catch {
    return null;
  }
}

function salvarValor(
  chave: string,
  valor: string,
): void {
  window.localStorage.setItem(
    chave,
    valor,
  );

  window.sessionStorage.setItem(
    chave,
    valor,
  );
}

function removerValor(
  chave: string,
): void {
  window.localStorage.removeItem(chave);
  window.sessionStorage.removeItem(chave);
}

function notificarAlteracao(): void {
  window.dispatchEvent(
    new Event(
      EVENTO_INVENTARIO_ATUAL_ALTERADO,
    ),
  );
}

export function salvarInventarioAtual(
  idInventario: number,
  tipo?: TipoInventarioAtual | string,
): void {
  if (
    !possuiWindow() ||
    !Number.isInteger(idInventario) ||
    idInventario <= 0
  ) {
    return;
  }

  try {
    const idAnterior =
      obterInventarioAtual();

    salvarValor(
      CHAVE_INVENTARIO_ATUAL,
      String(idInventario),
    );

    const tipoNormalizado =
      normalizarTipo(tipo);

    if (tipoNormalizado) {
      salvarValor(
        CHAVE_TIPO_INVENTARIO_ATUAL,
        tipoNormalizado,
      );
    } else if (
      idAnterior !== null &&
      idAnterior !== idInventario
    ) {
      removerValor(
        CHAVE_TIPO_INVENTARIO_ATUAL,
      );
    }

    notificarAlteracao();
  } catch {
    // A URL continua sendo uma alternativa.
  }
}

export function obterInventarioAtual():
  number | null {
  return idValido(
    obterValor(
      CHAVE_INVENTARIO_ATUAL,
    ),
  );
}

export function obterTipoInventarioAtual():
  TipoInventarioAtual | null {
  return normalizarTipo(
    obterValor(
      CHAVE_TIPO_INVENTARIO_ATUAL,
    ),
  );
}

export function limparInventarioAtual(): void {
  if (!possuiWindow()) {
    return;
  }

  try {
    removerValor(
      CHAVE_INVENTARIO_ATUAL,
    );

    removerValor(
      CHAVE_TIPO_INVENTARIO_ATUAL,
    );

    notificarAlteracao();
  } catch {
    // Nao impede o logout.
  }
}
