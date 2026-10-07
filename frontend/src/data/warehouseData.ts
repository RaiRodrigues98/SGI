/**
 * Dados simulados do Mapa 3D do Estoque.
 *
 * Tudo aqui é gerado automaticamente e de forma determinística.
 * Nenhum Math.random() é usado — o status depende apenas do código.
 *
 * Este arquivo é o único ponto de dados simulados do protótipo.
 * No SGI, ele será substituído pela fonte real (mantendo os mesmos tipos).
 */

export type LocationStatus = "livre" | "ocupada" | "divergencia" | "recontagem";

export type Side = "impar" | "par";

export interface WarehouseLocationStockItem {
  clienteId: number;
  cliente: string;

  codigo: string;
  descricao: string | null;
  lote: string | null;

  /**
   * Quantidade fisicamente armazenada.
   * Origem: q_armazenado.
   */
  quantidade: number;

  unidade: string | null;
  categoria: string | null;
  validade: string | null;

  reservado: number;
  bloqueado: number;
  estimado: number;
  disponivel: number;

  statusEstoque: string | null;
  tipoLocalizacao: string | null;
}


export interface WarehouseLocationCountedItem {
  codigo: string;
  descricao: string | null;
  lote: string | null;
  quantidade: number;
  status: string;
  qtdEstoque: number;
  diferenca: number;
}


export interface WarehouseLocation {
  /** Código completo, ex.: R0100100101 */
  code: string;
  /** Rua: R01 | R02 | R03 */
  rua: string;
  /** Lado do corredor */
  lado: Side;
  /** Módulo (1..18) */
  modulo: number;
  /** Índice físico do módulo dentro da face (0..8) */
  moduloIndex: number;
  /** Nível 1..8 (1 embaixo, 8 no alto) */
  nivel: number;
  /** Posição 1 ou 2 */
  posicao: number;
  status: LocationStatus;
  produto: string | null;
  lote: string | null;
  quantidade: number;

  /**
   * Itens fisicos existentes na localizacao.
   * Permite preservar cliente, produto e lote
   * quando uma posicao possui varios registros.
   */
  itensEstoque?: WarehouseLocationStockItem[];


  /**
   * Itens efetivamente contados nesta localizacao
   * na rodada atual do inventario.
   */
  itensContados?: WarehouseLocationCountedItem[];
}

export interface DamageArea {
  code: string;
  label: string;
  descricao: string;
}

export const RUAS = ["R01", "R02", "R03"] as const;

export const NIVEIS_POR_MODULO = 8;
export const POSICOES_POR_NIVEL = 2;
export const MODULOS_POR_FACE = 9;

/** Módulos de cada lado (9 por face). */
export const MODULOS_IMPAR = [1, 3, 5, 7, 9, 11, 13, 15, 17];
export const MODULOS_PAR = [2, 4, 6, 8, 10, 12, 14, 16, 18];

/** Faces físicas existentes: R03 só possui lado ímpar. */
export const FACES: { rua: string; lado: Side }[] = [
  { rua: "R01", lado: "impar" },
  { rua: "R01", lado: "par" },
  { rua: "R02", lado: "impar" },
  { rua: "R02", lado: "par" },
  { rua: "R03", lado: "impar" },
];

export function buildLocationCode(
  rua: string,
  modulo: number,
  nivel: number,
  posicao: number,
): string {
  return [
    rua,
    String(modulo).padStart(3, "0"),
    String(nivel).padStart(3, "0"),
    String(posicao).padStart(2, "0"),
  ].join("");
}

/** Hash estável (FNV-1a simplificado) para gerar dados determinísticos. */
function hashCode(value: string): number {
  let h = 2166136261;
  for (let i = 0; i < value.length; i++) {
    h ^= value.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return Math.abs(h);
}

const PRODUTOS = [
  "Caixa Papelão 40x30",
  "Filme Stretch 500mm",
  "Parafuso Sextavado M8",
  "Tinta Acrílica 18L",
  "Cabo Flexível 2,5mm",
  "Rolamento 6204",
  "Óleo Lubrificante 20L",
  "Chapa Galvanizada 1mm",
  "Fita Adesiva 48mm",
  "Luva Nitrílica CA 28",
];

function statusFromHash(h: number): LocationStatus {
  const bucket = h % 100;
  if (bucket < 34) return "livre";
  if (bucket < 84) return "ocupada";
  if (bucket < 92) return "divergencia";
  return "recontagem";
}

function buildLocation(
  rua: string,
  lado: Side,
  modulo: number,
  moduloIndex: number,
  nivel: number,
  posicao: number,
): WarehouseLocation {
  const code = buildLocationCode(rua, modulo, nivel, posicao);
  const h = hashCode(code);
  const status = statusFromHash(h);
  const ocupada = status !== "livre";

  return {
    code,
    rua,
    lado,
    modulo,
    moduloIndex,
    nivel,
    posicao,
    status,
    produto: ocupada ? (PRODUTOS[h % PRODUTOS.length] ?? PRODUTOS[0]!) : null,
    lote: ocupada ? `LT${String((h % 90000) + 10000)}` : null,
    quantidade: ocupada ? (h % 240) + 12 : 0,
  };
}

/** Gera as 720 posições (nenhuma escrita manualmente). */
export function generateLocations(): WarehouseLocation[] {
  const locations: WarehouseLocation[] = [];

  for (const face of FACES) {
    const modulos = face.lado === "impar" ? MODULOS_IMPAR : MODULOS_PAR;
    modulos.forEach((modulo, moduloIndex) => {
      for (let nivel = 1; nivel <= NIVEIS_POR_MODULO; nivel++) {
        for (let posicao = 1; posicao <= POSICOES_POR_NIVEL; posicao++) {
          locations.push(
            buildLocation(face.rua, face.lado, modulo, moduloIndex, nivel, posicao),
          );
        }
      }
    });
  }

  return locations;
}

export const DAMAGE_AREA: DamageArea = {
  code: "R02AVARIA",
  label: "R02AVARIA",
  descricao: "Área de avaria da Rua R02 (não contabilizada nas 720 posições).",
};

export const STATUS_LABELS: Record<LocationStatus, string> = {
  livre: "Livre",
  ocupada: "Ocupada",
  divergencia: "Divergência",
  recontagem: "Recontagem",
};

export const STATUS_COLORS: Record<LocationStatus, string> = {
  livre: "#9ca3af",
  ocupada: "#22c55e",
  divergencia: "#ef4444",
  recontagem: "#facc15",
};

export const SELECTED_COLOR = "#3b82f6";
