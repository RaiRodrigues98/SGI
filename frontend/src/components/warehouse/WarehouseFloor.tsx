import * as THREE from "three";

import {
  DAMAGE_AREA_RECT,
  FACE_LENGTH,
  FACE_Z_MAP,
  RACK_DEPTH,
  RACK_HEIGHT,
  RACK_X_OFFSET,
} from "./layout";


const FLOOR_W = 58;
const FLOOR_D = 46;

/*
 * Centro lateral do galpão.
 *
 * O deslocamento negativo mantém a parede
 * direita próxima da R01 e cria uma área
 * bem maior do lado da R03.
 */
const WAREHOUSE_CENTER_Z = -1;


const WAREHOUSE_HEIGHT =
  RACK_HEIGHT + 5.3;


/*
 * ============================================================
 * DEMARCACAO DO PISO
 * ============================================================
 *
 * As linhas agora seguem as faces reais dos racks,
 * e nao apenas o centro teorico do corredor.
 */

const FLOOR_LINE_WIDTH = 0.08;

const FLOOR_LINE_OFFSET =
  RACK_DEPTH / 2 + 0.42;


const CORRIDOR_LINES = [
  {
    id: "R01",

    /*
     * Corredor entre:
     * R01 impar <-> R01 par
     */
    z1:
      (FACE_Z_MAP["R01_impar"] ?? 0) -
      FLOOR_LINE_OFFSET,

    z2:
      (FACE_Z_MAP["R01_par"] ?? 0) +
      FLOOR_LINE_OFFSET,
  },

  {
    id: "R02",

    /*
     * Corredor entre:
     * R02 impar <-> R02 par
     */
    z1:
      (FACE_Z_MAP["R02_impar"] ?? 0) -
      FLOOR_LINE_OFFSET,

    z2:
      (FACE_Z_MAP["R02_par"] ?? 0) +
      FLOOR_LINE_OFFSET,
  },
];


const concreteMat =
  new THREE.MeshStandardMaterial({
    /*
     * Concreto industrial sem textura.
     * Roughness alta evita reflexo plastico.
     */
    color: "#9fa3a4",
    roughness: 0.97,
    metalness: 0,
  });


const wallMat =
  new THREE.MeshStandardMaterial({
    /*
     * Pintura industrial fosca.
     * A propria box representa a casca interna
     * do galpao, incluindo paredes e teto.
     */
    color: "#d3d6d7",
    roughness: 0.91,
    metalness: 0,
    side: THREE.BackSide,
  });


const ceilingBeamMat =
  new THREE.MeshStandardMaterial({
    /*
     * Estrutura metalica fosca.
     * Contraste suficiente para leitura sem ficar preta.
     */
    color: "#858b8f",
    roughness: 0.78,
    metalness: 0.16,
  });


const lightFixtureMat =
  new THREE.MeshBasicMaterial({
    /*
     * Branco industrial neutro.
     *
     * Continua sendo apenas visual:
     * nao gera luz, sombra ou calculo adicional.
     */
    color: "#f6f7f2",
    toneMapped: false,
  });


/**
 * Piso, circulação, paredes e teto do galpão.
 *
 * Esta camada é somente visual.
 * Não interfere nas localizações ou no inventário.
 */
/*
 * ============================================================
 * PAREDES_GALPAO_REAL_MATERIAIS
 * ============================================================
 *
 * Referencia visual do galpao real.
 *
 * Sem texturas.
 * Sem normal maps.
 * Sem novas luzes.
 * Sem sombras.
 */


const realConcreteWallMat =
  new THREE.MeshLambertMaterial({
    /*
     * Concreto mais claro.
     * Continua reagindo a luz, mas sem ficar pesado.
     */
    color: "#bcbdb9",
    emissive: "#181818",
  });


const realConcreteJointMat =
  new THREE.MeshBasicMaterial({
    color: "#b2b3af",
  });


const realMetalWallMat =
  new THREE.MeshBasicMaterial({
    /*
     * Parede lateral direita branca.
     *
     * Material independente da iluminacao para
     * permanecer branco como no galpao real.
     */
    color: "#f0f1ef",
  });


const realMetalRibMat =
  new THREE.MeshBasicMaterial({
    color: "#e7e8e6",
  });


const realMetalBaseMat =
  new THREE.MeshBasicMaterial({
    color: "#e3e4e2",
  });


const realBackWallMat =
  new THREE.MeshLambertMaterial({
    color: "#bcbdb9",
    emissive: "#181818",
  });


const realClerestoryMat =
  new THREE.MeshBasicMaterial({
    color: "#eeeeea",
    transparent: true,
    opacity: 0.88,
    toneMapped: false,
  });


const LEFT_REAL_WALL_Z =
  WAREHOUSE_CENTER_Z -
  FLOOR_D / 2 +
  0.04;


const RIGHT_REAL_WALL_Z =
  WAREHOUSE_CENTER_Z +
  FLOOR_D / 2 -
  0.04;


const BACK_REAL_WALL_X =
  FLOOR_W / 2 -
  0.04;


/*
 * ============================================================
 * ESTRUTURA_CONCRETO_REAL_MATERIAL
 * ============================================================
 *
 * Pilares e vigas inspirados na parede estrutural
 * do galpao real.
 *
 * Sem textura.
 * Sem sombra.
 * Sem nova iluminacao.
 */
const realConcreteStructureMat =
  new THREE.MeshLambertMaterial({
    color: "#b8b9b5",
  });


const realConcreteBaseMat =
  new THREE.MeshLambertMaterial({
    color: "#afb0ad",
  });


export function WarehouseFloor({
  onClearSelection,
}: {
  onClearSelection: () => void;
}) {
  return (
    <group>
      {/* =====================================================
          PISO
          ===================================================== */}

      <mesh
        rotation-x={-Math.PI / 2}
        position={[
          0,
          0.006,
          WAREHOUSE_CENTER_Z,
        ]}
        material={concreteMat}
        receiveShadow
        onClick={(event) => {
          event.stopPropagation();
          onClearSelection();
        }}
      >
        <planeGeometry
          args={[
            FLOOR_W,
            FLOOR_D,
          ]}
        />
      </mesh>


      {/* =====================================================
          FAIXAS DOS CORREDORES
          ===================================================== */}

      {CORRIDOR_LINES.flatMap(
        (corredor) =>
          [
            corredor.z1,
            corredor.z2,
          ].map(
            (z, index) => (
              <mesh
                key={`${corredor.id}-linha-${index}`}
                rotation-x={
                  -Math.PI / 2
                }
                position={[
                  RACK_X_OFFSET,
                  0.014,
                  z,
                ]}
              >
                <planeGeometry
                  args={[
                    FACE_LENGTH + 1.2,
                    FLOOR_LINE_WIDTH,
                  ]}
                />

                <meshBasicMaterial
                  color="#d2b619"
                />
              </mesh>
            ),
          ),
      )}


      {/* =====================================================
          CASCA DO GALPAO
          ===================================================== */}

      <mesh
        position={[
          0,
          WAREHOUSE_HEIGHT / 2,
          WAREHOUSE_CENTER_Z,
        ]}
        material={wallMat}
      >
        <boxGeometry
          args={[
            FLOOR_W,
            WAREHOUSE_HEIGHT,
            FLOOR_D,
          ]}
        />
      </mesh>


            {/* =====================================================
          PAREDES_GALPAO_REAL
          =====================================================

          Referencia do galpao real:
          - concreto aparente de um lado
          - fechamento metalico claro do outro
          - fundo em concreto
          - faixa clara superior

          Elementos exclusivamente visuais.
          ===================================================== */}


      {/*
       * ======================================================
       * PAREDE DE CONCRETO
       * ======================================================
       */}
      <mesh
        position={[
          0,
          WAREHOUSE_HEIGHT / 2,
          LEFT_REAL_WALL_Z,
        ]}
        material={
          realConcreteWallMat
        }
      >
        <planeGeometry
          args={[
            FLOOR_W,
            WAREHOUSE_HEIGHT,
          ]}
        />
      </mesh>


      {/*
       * Juntas verticais do concreto.
       *
       * Poucas linhas grandes para reproduzir
       * os paineis estruturais sem pesar.
       */}
      {[
        -19,
        -9.5,
        0,
        9.5,
        19,
      ].map(
        (x) => (
          <mesh
            key={
              `concrete-v-${x}`
            }
            position={[
              x,
              WAREHOUSE_HEIGHT / 2,
              LEFT_REAL_WALL_Z +
                0.01,
            ]}
            material={
              realConcreteJointMat
            }
          >
            <planeGeometry
              args={[
                0.055,
                WAREHOUSE_HEIGHT -
                  0.5,
              ]}
            />
          </mesh>
        ),
      )}


      {/*
       * Juntas horizontais dos paineis de concreto.
       */}
      {[
        5.1,
        10.2,
        15.3,
      ].map(
        (y) => (
          <mesh
            key={
              `concrete-h-${y}`
            }
            position={[
              0,
              y,
              LEFT_REAL_WALL_Z +
                0.011,
            ]}
            material={
              realConcreteJointMat
            }
          >
            <planeGeometry
              args={[
                FLOOR_W -
                  0.5,
                0.055,
              ]}
            />
          </mesh>
        ),
      )}


      {/*
       * ======================================================
       * PAREDE METALICA CLARA
       * ======================================================
       *
       * Inspirada no fechamento lateral branco/cinza
       * visivel na fotografia do galpao.
       */}
      <mesh
        rotation-y={
          Math.PI
        }
        position={[
          0,
          WAREHOUSE_HEIGHT / 2,
          RIGHT_REAL_WALL_Z,
        ]}
        material={
          realMetalWallMat
        }
      >
        <planeGeometry
          args={[
            FLOOR_W,
            WAREHOUSE_HEIGHT,
          ]}
        />
      </mesh>


      {/*
       * Frisos verticais da chapa.
       *
       * Apenas 13 elementos:
       * suficiente para dar leitura metalica sem
       * multiplicar excessivamente a geometria.
       */}
      {Array.from(
        {
          length: 13,
        },
        (
          _,
          index,
        ) =>
          -24 +
          index * 4,
      ).map(
        (x) => (
          <mesh
            key={
              `metal-rib-${x}`
            }
            rotation-y={
              Math.PI
            }
            position={[
              x,
              WAREHOUSE_HEIGHT / 2,
              RIGHT_REAL_WALL_Z -
                0.01,
            ]}
            material={
              realMetalRibMat
            }
          >
            <planeGeometry
              args={[
                0.07,
                WAREHOUSE_HEIGHT -
                  0.3,
              ]}
            />
          </mesh>
        ),
      )}


      {/*
       * Faixa inferior escura encontrada
       * na parede metalica real.
       */}
      <mesh
        rotation-y={
          Math.PI
        }
        position={[
          0,
          1.05,
          RIGHT_REAL_WALL_Z -
            0.012,
        ]}
        material={
          realMetalBaseMat
        }
      >
        <planeGeometry
          args={[
            FLOOR_W,
            2.1,
          ]}
        />
      </mesh>


      {/*
       * ======================================================
       * FUNDO DO GALPAO
       * ======================================================
       */}
      <mesh
        rotation-y={
          -Math.PI / 2
        }
        position={[
          BACK_REAL_WALL_X,
          WAREHOUSE_HEIGHT / 2,
          WAREHOUSE_CENTER_Z,
        ]}
        material={
          realBackWallMat
        }
      >
        <planeGeometry
          args={[
            FLOOR_D,
            WAREHOUSE_HEIGHT,
          ]}
        />
      </mesh>


      {/*
       * Faixa superior clara.
       *
       * Simula a area transl?cida/entrada de luz
       * natural observada no fundo do galpao.
       *
       * Nao e uma fonte de luz.
       */}
      <mesh
        rotation-y={
          -Math.PI / 2
        }
        position={[
          BACK_REAL_WALL_X -
            0.012,
          WAREHOUSE_HEIGHT -
            4.0,
          WAREHOUSE_CENTER_Z,
        ]}
        material={
          realClerestoryMat
        }
      >
        <planeGeometry
          args={[
            FLOOR_D *
              0.62,
            2.8,
          ]}
        />
      </mesh>


      {/* =====================================================
          ESTRUTURA_CONCRETO_REAL
          =====================================================

          Refinamento visual leve:
          - 4 pilares
          - 1 viga superior
          - 1 faixa inferior

          Nenhum elemento participa de sombra.
          ===================================================== */}


      {/*
       * PILARES VERTICAIS
       *
       * Criam a leitura estrutural observada
       * na parede de concreto real.
       */}
      {[
        -21,
        -7,
        7,
        21,
      ].map(
        (x) => (
          <mesh
            key={
              `concrete-column-${x}`
            }
            position={[
              x,
              WAREHOUSE_HEIGHT /
                2,
              LEFT_REAL_WALL_Z +
                0.12,
            ]}
            material={
              realConcreteStructureMat
            }
          >
            <boxGeometry
              args={[
                0.42,
                WAREHOUSE_HEIGHT -
                  0.4,
                0.22,
              ]}
            />
          </mesh>
        ),
      )}


      {/*
       * VIGA HORIZONTAL SUPERIOR
       */}
      <mesh
        position={[
          0,
          WAREHOUSE_HEIGHT -
            2.6,
          LEFT_REAL_WALL_Z +
            0.13,
        ]}
        material={
          realConcreteStructureMat
        }
      >
        <boxGeometry
          args={[
            FLOOR_W -
              2,
            0.48,
            0.24,
          ]}
        />
      </mesh>


      {/*
       * FAIXA INFERIOR DA PAREDE
       *
       * Evita que a parede pareca um plano
       * uniforme do piso ao teto.
       */}
      <mesh
        position={[
          0,
          1.25,
          LEFT_REAL_WALL_Z +
            0.025,
        ]}
        material={
          realConcreteBaseMat
        }
      >
        <boxGeometry
          args={[
            FLOOR_W -
              0.5,
            2.5,
            0.045,
          ]}
        />
      </mesh>


{/* =====================================================
          VIGAS PRINCIPAIS DO TETO
          ===================================================== */}

      {[
        -12,
        0,
        12,
      ].map(
        (z) => (
          <mesh
            key={`viga-z-${z}`}
            position={[
              0,
              WAREHOUSE_HEIGHT - 0.8,
              z,
            ]}
            material={
              ceilingBeamMat
            }
          >
            <boxGeometry
              args={[
                FLOOR_W - 4,
                0.20,
                0.20,
              ]}
            />
          </mesh>
        ),
      )}


      {[
        -18,
        -6,
        6,
        18,
      ].map(
        (x) => (
          <mesh
            key={`viga-x-${x}`}
            position={[
              x,
              WAREHOUSE_HEIGHT - 0.65,
              WAREHOUSE_CENTER_Z,
            ]}
            material={
              ceilingBeamMat
            }
          >
            <boxGeometry
              args={[
                0.16,
                0.16,
                FLOOR_D - 4,
              ]}
            />
          </mesh>
        ),
      )}


      {/* =====================================================
          LUMINARIAS INDUSTRIAIS
          ===================================================== */}

      {[
        -16,
        -8,
        0,
        8,
        16,
      ].flatMap(
        (x) =>
          [
            -6,
            5,
            14,
          ].map(
            (z) => (
              <mesh
                key={`luz-${x}-${z}`}
                rotation-x={
                  Math.PI / 2
                }
                position={[
                  x,
                  WAREHOUSE_HEIGHT - 1,
                  z,
                ]}
                material={
                  lightFixtureMat
                }
              >
                <planeGeometry
                  args={[
                    3.2,
                    0.22,
                  ]}
                />
              </mesh>
            ),
          ),
      )}


      {/* =====================================================
          AREA LIVRE DA R03
          ===================================================== */}

      {/*
       * Mantemos a grande área livre do lado da R03.
       * Do lado da R01 também existe espaço suficiente
       * para visualizar a estrutura por trás.
       */}


      {/* =====================================================
          AREA DE AVARIA - REFERENCIA INVISIVEL
          ===================================================== */}

      <mesh
        rotation-x={
          -Math.PI / 2
        }
        position={[
          DAMAGE_AREA_RECT.x,
          0.01,
          DAMAGE_AREA_RECT.z,
        ]}
        visible={false}
      >
        <planeGeometry
          args={[
            1,
            1,
          ]}
        />
      </mesh>
    </group>
  );
}
