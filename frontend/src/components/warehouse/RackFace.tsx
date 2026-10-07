import {
  useMemo,
} from "react";

import * as THREE from "three";

import type {
  Side,
} from "@/data/warehouseData";

import {
  FACE_LENGTH,
  FACE_START_X,
  LEVEL_HEIGHT,
  MODULES_PER_FACE,
  MODULE_WIDTH,
  RACK_DEPTH,
  RACK_HEIGHT,
  RACK_X_OFFSET,
  faceZ,
  levelY,
} from "./layout";


/*
 * ============================================================
 * GEOMETRIA PRINCIPAL
 * ============================================================
 */

const UPRIGHT_WIDTH =
  0.085;

const UPRIGHT_DEPTH =
  0.075;

const UPRIGHT_Z =
  RACK_DEPTH / 2 -
  UPRIGHT_DEPTH / 2;


const uprightGeo =
  new THREE.BoxGeometry(
    UPRIGHT_WIDTH,
    RACK_HEIGHT,
    UPRIGHT_DEPTH,
  );


/*
 * A longarina agora termina na face
 * interna dos montantes.
 */
const BEAM_LENGTH =
  MODULE_WIDTH -
  UPRIGHT_WIDTH;


const BEAM_END_X =
  MODULE_WIDTH / 2 -
  UPRIGHT_WIDTH / 2;


const beamGeo =
  new THREE.BoxGeometry(
    BEAM_LENGTH,
    0.115,
    0.055,
  );


/*
 * Chapa de encaixe da longarina
 * no montante.
 */
const beamConnectorGeo =
  new THREE.BoxGeometry(
    0.06,
    0.18,
    0.10,
  );


const guardGeo =
  new THREE.BoxGeometry(
    0.15,
    0.42,
    0.14,
  );


/*
 * Travessa horizontal da cabeceira.
 * Liga frente e fundo do rack.
 */
const sideBarGeo =
  new THREE.BoxGeometry(
    0.045,
    0.045,
    RACK_DEPTH -
      UPRIGHT_DEPTH,
  );


/*
 * Diagonal da cabeceira.
 *
 * O comprimento real será controlado
 * pela escala Y de cada mesh.
 */
const diagonalGeo =
  new THREE.BoxGeometry(
    0.04,
    1,
    0.04,
  );


/*
 * Sapata metálica dos montantes.
 */
const footPlateGeo =
  new THREE.BoxGeometry(
    0.22,
    0.025,
    0.18,
  );


/*
 * ============================================================
 * MATERIAIS
 * ============================================================
 */

const blueMat =
  new THREE.MeshLambertMaterial({
    color: "#245493",
  });


const orangeMat =
  new THREE.MeshLambertMaterial({
    color: "#e77b24",
  });


/*
 * Tom ligeiramente mais escuro para
 * destacar a chapa de engate.
 */
const connectorMat =
  new THREE.MeshLambertMaterial({
    color: "#c8661e",
  });


const yellowMat =
  new THREE.MeshLambertMaterial({
    color: "#d8b51c",
  });


const footMat =
  new THREE.MeshLambertMaterial({
    color: "#5f6872",
  });


/*
 * ============================================================
 * CABECEIRAS / DIAGONAIS
 * ============================================================
 */

const SIDE_FRAME_X = [
  FACE_START_X,
  FACE_START_X + FACE_LENGTH,
];


/*
 * Uma diagonal a cada dois níveis.
 *
 * Evita excesso visual e se aproxima
 * da estrutura de um porta-palete real.
 */
const BRACE_SEGMENT_HEIGHT =
  LEVEL_HEIGHT * 2;


export function RackFace({
  rua,
  lado,
}: {
  rua: string;
  lado: Side;
}) {
  const z =
    faceZ(
      rua,
      lado,
    );


  const dir =
    lado === "impar"
      ? 1
      : -1;


  /*
   * ==========================================================
   * MONTANTES
   * ==========================================================
   */

  const uprights =
    useMemo(
      () =>
        Array.from(
          {
            length:
              MODULES_PER_FACE + 1,
          },
          (
            _,
            index,
          ) =>
            FACE_START_X +
            index *
              MODULE_WIDTH,
        ),
      [],
    );


  /*
   * ==========================================================
   * LONGARINAS
   * ==========================================================
   */

  const beams =
    useMemo(
      () => {
        const items: {
          x: number;
          y: number;
        }[] = [];


        for (
          let module = 0;
          module <
          MODULES_PER_FACE;
          module++
        ) {
          for (
            let level = 1;
            level <= 8;
            level++
          ) {
            items.push({
              x:
                FACE_START_X +
                module *
                  MODULE_WIDTH +
                MODULE_WIDTH /
                  2,

              y:
                levelY(
                  level,
                ) -
                LEVEL_HEIGHT /
                  2 +
                0.05,
            });
          }
        }


        return items;
      },
      [],
    );


  /*
   * ==========================================================
   * TRAVESSAS DAS CABECEIRAS
   * ==========================================================
   */

  const sideBars =
    useMemo(
      () =>
        Array.from(
          {
            length: 8,
          },
          (
            _,
            index,
          ) => ({
            y:
              levelY(
                index + 1,
              ) -
              LEVEL_HEIGHT /
                2 +
              0.05,
          }),
        ),
      [],
    );


  /*
   * ==========================================================
   * DIAGONAIS DAS CABECEIRAS
   * ==========================================================
   */

  const diagonals =
    useMemo(
      () => {
        const items: {
          x: number;
          y: number;
          length: number;
          angle: number;
        }[] = [];


        const usableDepth =
          RACK_DEPTH -
          0.16;


        const segments =
          Math.ceil(
            RACK_HEIGHT /
              BRACE_SEGMENT_HEIGHT,
          );


        SIDE_FRAME_X.forEach(
          (
            x,
          ) => {
            for (
              let segment = 0;
              segment <
              segments;
              segment++
            ) {
              const yStart =
                segment *
                BRACE_SEGMENT_HEIGHT;


              const yEnd =
                Math.min(
                  yStart +
                    BRACE_SEGMENT_HEIGHT,
                  RACK_HEIGHT,
                );


              const height =
                yEnd -
                yStart;


              if (
                height <= 0
              ) {
                continue;
              }


              const length =
                Math.sqrt(
                  height *
                    height +
                  usableDepth *
                    usableDepth,
                );


              const baseAngle =
                Math.atan2(
                  usableDepth,
                  height,
                );


              /*
               * Alterna o sentido das diagonais
               * formando o desenho estrutural.
               */
              const angle =
                segment %
                  2 ===
                0
                  ? baseAngle
                  : -baseAngle;


              items.push({
                x,

                y:
                  yStart +
                  height / 2,

                length,

                angle,
              });
            }
          },
        );


        return items;
      },
      [],
    );


  return (
    <group
      position={[
        RACK_X_OFFSET,
        0,
        z,
      ]}
    >
      {/* ====================================================
          MONTANTES AZUIS
          ==================================================== */}

      {uprights.map(
        (
          x,
        ) => (
          <group
            key={`upright-${x}`}
          >
            <mesh
              geometry={
                uprightGeo
              }
              material={
                blueMat
              }
              position={[
                x,
                RACK_HEIGHT /
                  2,
                -UPRIGHT_Z,
              ]}
              castShadow
              receiveShadow
            />

            <mesh
              geometry={
                uprightGeo
              }
              material={
                blueMat
              }
              position={[
                x,
                RACK_HEIGHT /
                  2,
                UPRIGHT_Z,
              ]}
              castShadow
              receiveShadow
            />
          </group>
        ),
      )}


      {/* ====================================================
          LONGARINAS LARANJAS
          ==================================================== */}

      {beams.map(
        (
          beam,
          index,
        ) => (
          <group
            key={
              `beam-${index}`
            }
          >
            {/*
             * Longarina frontal.
             */}
            <mesh
              geometry={
                beamGeo
              }
              material={
                orangeMat
              }
              position={[
                beam.x,
                beam.y,
                -RACK_DEPTH /
                  2 +
                  0.07,
              ]}
              castShadow
              receiveShadow
            />

            {/*
             * Longarina traseira.
             */}
            <mesh
              geometry={
                beamGeo
              }
              material={
                orangeMat
              }
              position={[
                beam.x,
                beam.y,
                RACK_DEPTH /
                  2 -
                  0.07,
              ]}
              castShadow
              receiveShadow
            />

            {/*
             * Chapas de encaixe nas duas
             * extremidades das longarinas.
             */}
            {[
              -1,
              1,
            ].flatMap(
              (
                sideX,
              ) => [
                <mesh
                  key={
                    `connector-front-${sideX}`
                  }
                  geometry={
                    beamConnectorGeo
                  }
                  material={
                    connectorMat
                  }
                  position={[
                    beam.x +
                      sideX *
                        BEAM_END_X,
                    beam.y,
                    -RACK_DEPTH /
                      2 +
                      0.07,
                  ]}
                  receiveShadow
                />,

                <mesh
                  key={
                    `connector-back-${sideX}`
                  }
                  geometry={
                    beamConnectorGeo
                  }
                  material={
                    connectorMat
                  }
                  position={[
                    beam.x +
                      sideX *
                        BEAM_END_X,
                    beam.y,
                    RACK_DEPTH /
                      2 -
                      0.07,
                  ]}
                  receiveShadow
                />,
              ],
            )}
          </group>
        ),
      )}


      {/* ====================================================
          TRAVESSAS DAS DUAS CABECEIRAS
          ==================================================== */}

      {SIDE_FRAME_X.flatMap(
        (
          x,
        ) =>
          sideBars.map(
            (
              bar,
              index,
            ) => (
              <mesh
                key={
                  `sidebar-${x}-${index}`
                }
                geometry={
                  sideBarGeo
                }
                material={
                  blueMat
                }
                position={[
                  x,
                  bar.y,
                  0,
                ]}
                receiveShadow
              />
            ),
          ),
      )}


      {/* ====================================================
          DIAGONAIS AZUIS DAS CABECEIRAS
          ==================================================== */}

      {diagonals.map(
        (
          brace,
          index,
        ) => (
          <mesh
            key={
              `diagonal-${index}`
            }
            geometry={
              diagonalGeo
            }
            material={
              blueMat
            }
            position={[
              brace.x,
              brace.y,
              0,
            ]}
            rotation={[
              brace.angle,
              0,
              0,
            ]}
            scale={[
              1,
              brace.length,
              1,
            ]}
            receiveShadow
          />
        ),
      )}


      {/* ====================================================
          SAPATAS DOS MONTANTES
          ==================================================== */}

      {uprights.flatMap(
        (
          x,
        ) => [
          <mesh
            key={
              `foot-front-${x}`
            }
            geometry={
              footPlateGeo
            }
            material={
              footMat
            }
            position={[
              x,
              0.013,
              -UPRIGHT_Z,
            ]}
            receiveShadow
          />,

          <mesh
            key={
              `foot-back-${x}`
            }
            geometry={
              footPlateGeo
            }
            material={
              footMat
            }
            position={[
              x,
              0.013,
              UPRIGHT_Z,
            ]}
            receiveShadow
          />,
        ],
      )}


      {/* ====================================================
          PROTETORES AMARELOS
          ==================================================== */}

      {uprights.map(
        (
          x,
        ) => (
          <mesh
            key={
              `guard-${x}`
            }
            geometry={
              guardGeo
            }
            material={
              yellowMat
            }
            position={[
              x,
              0.22,
              (
                RACK_DEPTH /
                  2 +
                0.10
              ) * dir,
            ]}
            receiveShadow
          />
        ),
      )}


      {/* ====================================================
          FAIXA AMARELA NA BASE
          ==================================================== */}

      <mesh
        rotation-x={
          -Math.PI / 2
        }
        position={[
          0,
          0.02,
          (
            RACK_DEPTH /
              2 +
            0.32
          ) * dir,
        ]}
        receiveShadow
      >
        <planeGeometry
          args={[
            FACE_LENGTH,
            0.16,
          ]}
        />

        <meshBasicMaterial
          color="#d8b51c"
        />
      </mesh>
    </group>
  );
}
