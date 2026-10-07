/** Geometria/layout do armazém 3D (somente apresentação). */

import type {
  Side,
  WarehouseLocation,
} from "@/data/warehouseData";


export const MODULE_WIDTH = 2.75;

export const MODULES_PER_FACE = 9;

export const LEVEL_HEIGHT = 1.55;

export const SLOT_OFFSET = 0.66;

export const RACK_DEPTH = 1.05;

export const FACE_LENGTH =
  MODULE_WIDTH * MODULES_PER_FACE;

export const FACE_START_X =
  -FACE_LENGTH / 2;


/**
 * Deslocamento longitudinal de todo o conjunto
 * de porta-paletes em direção ao fundo do galpão.
 *
 * Frente = X negativo
 * Fundo  = X positivo
 */
export const RACK_X_OFFSET = 6.0;


/**
 * Centro lógico aproximado de cada rua.
 *
 * Mantido também para elementos auxiliares
 * que ainda utilizam a referência da rua.
 */
export const AISLE_Z: Record<string, number> = {
  R01: 14.75,
  R02: 6.10,
  R03: 1.20,
};


/**
 * Centro visual dos dois corredores reais:
 *
 * R01 PAR <-> R02 ÍMPAR
 * R02 PAR <-> R03 ÍMPAR
 */
export const AISLE_GUIDES = [
  14.75,
  6.10,
];


/**
 * Posição lateral real de cada face.
 *
 * Ordem física olhando o galpão:
 *
 * parede direita
 * R01 ímpar
 * R01 par
 * corredor
 * R02 ímpar
 * R02 par
 * corredor
 * R03 ímpar
 * grande área livre
 */
export const FACE_Z_MAP: Record<
  string,
  number
> = {
  // Junto à parede direita
  "R01_impar": 18.50,

  // Corredor R01 mais largo
  "R01_par": 11.00,

  // Costas com costas
  "R02_impar": 9.85,

  // Corredor R02 mais largo
  "R02_par": 2.35,

  // Costas com costas
  "R03_impar": 1.20,
};


/**
 * Retorna a posição lateral real da face.
 */
export function faceZ(
  rua: string,
  lado: Side,
): number {
  return (
    FACE_Z_MAP[
      `${rua}_${lado}`
    ] ?? 0
  );
}


/**
 * Centro longitudinal de cada módulo.
 *
 * O módulo 001 permanece na frente
 * física do galpão.
 */
export function moduleCenterX(
  moduloIndex: number,
): number {
  return (
    FACE_START_X +
    RACK_X_OFFSET +
    moduloIndex * MODULE_WIDTH +
    MODULE_WIDTH / 2
  );
}


/**
 * Altura de cada nível.
 */
export function levelY(
  nivel: number,
): number {
  return (
    0.72 +
    (nivel - 1) *
      LEVEL_HEIGHT
  );
}


/**
 * Posição 3D de uma localização.
 *
 * A ordem das posições 01/02 é invertida
 * visualmente conforme o lado da estrutura.
 */
export function locationPosition(
  l: WarehouseLocation,
): [number, number, number] {
  const dir =
    l.lado === "impar"
      ? 1
      : -1;

  const offset =
    (
      l.posicao === 1
        ? -SLOT_OFFSET
        : SLOT_OFFSET
    ) * dir;

  return [
    moduleCenterX(
      l.moduloIndex,
    ) + offset,

    levelY(
      l.nivel,
    ),

    faceZ(
      l.rua,
      l.lado,
    ),
  ];
}


/**
 * Área de avaria no piso,
 * próxima da região da R02.
 */
export const DAMAGE_AREA_RECT = {
  x: FACE_START_X + RACK_X_OFFSET - 5.5,
  z: AISLE_Z["R02"] ?? 0,
  width: 6,
  depth: 7,
};


export const RACK_HEIGHT =
  levelY(8) +
  LEVEL_HEIGHT / 2;
