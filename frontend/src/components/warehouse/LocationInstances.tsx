import {
  useEffect,
  useMemo,
  useRef,
} from "react";

import type {
  ThreeEvent,
} from "@react-three/fiber";

import * as THREE from "three";

import {
  SELECTED_COLOR,
  STATUS_COLORS,
  type WarehouseLocation,
} from "@/data/warehouseData";

import {
  locationPosition,
} from "./layout";


const boxGeo =
  new THREE.BoxGeometry(
    1.06,
    0.82,
    0.82,
  );

/*
 * Pallet industrial.
 *
 * Em vez de um bloco unico, usamos:
 * - 5 tabuas superiores
 * - 9 blocos
 * - 3 reguas inferiores
 */
const palletGeo =
  new THREE.BoxGeometry(
    0.19,
    0.04,
    0.92,
  );


const palletBlockGeo =
  new THREE.BoxGeometry(
    0.16,
    0.09,
    0.16,
  );


const palletRunnerGeo =
  new THREE.BoxGeometry(
    1.08,
    0.035,
    0.11,
  );


const PALLET_BOARD_OFFSETS_X = [
  -0.46,
  -0.23,
  0,
  0.23,
  0.46,
];


const PALLET_BLOCK_OFFSETS_X = [
  -0.44,
  0,
  0.44,
];


const PALLET_BLOCK_OFFSETS_Z = [
  -0.32,
  0,
  0.32,
];


const PALLET_RUNNER_OFFSETS_Z = [
  -0.32,
  0,
  0.32,
];


/*
 * Camada visual ligeiramente maior que a carga.
 * Simula filme stretch / contorno da embalagem.
 */
const wrapGeo =
  new THREE.BoxGeometry(
    1.08,
    0.84,
    0.84,
  );

const hitGeo =
  new THREE.BoxGeometry(
    1.20,
    1.25,
    0.95,
  );


const boxMat =
  new THREE.MeshLambertMaterial({
    vertexColors: false,
  });

const palletMat =
  new THREE.MeshLambertMaterial({
    color: "#9a7148",
  });


const palletRunnerMat =
  new THREE.MeshLambertMaterial({
    color: "#765235",
  });


const wrapMat =
  new THREE.MeshBasicMaterial({
    color: "#ffffff",
    wireframe: true,
    transparent: true,
    opacity: 0.12,
    depthWrite: false,
  });

const hitMat =
  new THREE.MeshBasicMaterial({
    transparent: true,
    opacity: 0,
    depthWrite: false,
  });


const dummy =
  new THREE.Object3D();

const color =
  new THREE.Color();

const FREE_MARKER_COLOR =
  "#22d3ee";


interface Props {
  locations:
    WarehouseLocation[];

  selectedCode:
    string | null;

  highlightedCode:
    string | null;

  /*
   * Exibe um marcador simples no endereco
   * quando a posicao estiver livre.
   */
  showFreeMarkers?: boolean;

  onHover:
    (
      location:
        WarehouseLocation | null,
    ) => void;

  onSelect:
    (
      location:
        WarehouseLocation,
    ) => void;
}


type CargoProfile = {
  scaleX: number;
  scaleY: number;
  scaleZ: number;
  offsetY: number;
  palletScaleX: number;
  palletScaleZ: number;
};


/*
 * Perfil visual determinístico.
 *
 * Não altera saldo, status ou qualquer regra do SGI.
 * Serve apenas para quebrar a aparência repetitiva
 * das cargas no mapa.
 */
function cargoProfile(
  location: WarehouseLocation,
): CargoProfile {
  let hash = 0;

  for (
    let i = 0;
    i < location.code.length;
    i++
  ) {
    hash +=
      location.code.charCodeAt(i) *
      (i + 1);
  }

  const variant =
    Math.abs(hash) % 4;


  switch (variant) {
    case 0:
      // Pallet baixo
      return {
        scaleX: 0.98,
        scaleY: 0.58,
        scaleZ: 0.92,
        offsetY: -0.09,
        palletScaleX: 1,
        palletScaleZ: 1,
      };

    case 1:
      // Carga média
      return {
        scaleX: 1,
        scaleY: 0.88,
        scaleZ: 0.94,
        offsetY: 0.03,
        palletScaleX: 1,
        palletScaleZ: 1,
      };

    case 2:
      // Carga alta
      return {
        scaleX: 0.96,
        scaleY: 1.18,
        scaleZ: 0.90,
        offsetY: 0.15,
        palletScaleX: 1,
        palletScaleZ: 0.96,
      };

    default:
      // Carga mais estreita
      return {
        scaleX: 0.78,
        scaleY: 0.98,
        scaleZ: 0.80,
        offsetY: 0.07,
        palletScaleX: 0.90,
        palletScaleZ: 0.90,
      };
  }
}


export function LocationInstances({
  locations,
  selectedCode,
  highlightedCode,
  showFreeMarkers = false,
  onHover,
  onSelect,
}: Props) {
  const boxRef =
    useRef<THREE.InstancedMesh>(
      null,
    );

  const palletRef =
    useRef<THREE.InstancedMesh>(
      null,
    );


  const palletBlockRef =
    useRef<THREE.InstancedMesh>(
      null,
    );


  const palletRunnerRef =
    useRef<THREE.InstancedMesh>(
      null,
    );


  const wrapRef =
    useRef<THREE.InstancedMesh>(
      null,
    );

  const hitRef =
    useRef<THREE.InstancedMesh>(
      null,
    );


  const count =
    locations.length;


  const positions =
    useMemo(
      () =>
        locations.map(
          locationPosition,
        ),
      [locations],
    );

  useEffect(() => {
    /*
     * No filtro Posicoes livres, a propria
     * instancia da carga representa o volume
     * disponivel do endereco em wireframe.
     */
    boxMat.wireframe = showFreeMarkers;
    boxMat.needsUpdate = true;

    return () => {
      boxMat.wireframe = false;
      boxMat.needsUpdate = true;
    };
  }, [showFreeMarkers]);


  useEffect(() => {
    const boxes =
      boxRef.current;

    const pallets =
      palletRef.current;

    const palletBlocks =
      palletBlockRef.current;

    const palletRunners =
      palletRunnerRef.current;

    const wraps =
      wrapRef.current;

    const hits =
      hitRef.current;


    if (
      !boxes ||
      !pallets ||
      !palletBlocks ||
      !palletRunners ||
      !wraps ||
      !hits
    ) {
      return;
    }


    positions.forEach(
      (p, i) => {
        const location =
          locations[i];

        if (!location) {
          return;
        }


        const possuiCarga =
          location.status !==
          "livre";


        const profile =
          cargoProfile(location);


        // ====================================================
        // CARGA
        // ====================================================

        dummy.position.set(
          p[0],
          p[1] +
            0.08 +
            profile.offsetY,
          p[2],
        );

        dummy.rotation.set(
          0,
          0,
          0,
        );


        if (possuiCarga) {
          dummy.scale.set(
            profile.scaleX,
            profile.scaleY,
            profile.scaleZ,
          );
        } else if (
          showFreeMarkers
        ) {
          /*
           * POSICAO LIVRE
           *
           * Reutiliza a instancia da carga como
           * marcador discreto do endereco vazio.
           *
           * A cor continua sendo definida por
           * STATUS_COLORS.livre.
           */
          dummy.position.set(
            p[0],
            p[1],
            p[2],
          );

          dummy.scale.set(
            0.92,
            0.80,
            0.78,
          );
        } else {
          dummy.scale.setScalar(
            0.0001,
          );
        }


        dummy.updateMatrix();

        boxes.setMatrixAt(
          i,
          dummy.matrix,
        );


        /*
         * A camada de stretch usa exatamente
         * a mesma escala da carga.
         *
         * Em uma posicao livre, o marcador nao
         * representa uma carga. Por isso o wrap
         * permanece invisivel.
         */
        if (
          !possuiCarga &&
          showFreeMarkers
        ) {
          dummy.scale.setScalar(
            0.0001,
          );

          dummy.updateMatrix();
        }

        wraps.setMatrixAt(
          i,
          dummy.matrix,
        );


        // ====================================================
        // PALLET
        // ====================================================

        /*
         * Tabuas superiores.
         *
         * A altura foi calculada para deixar
         * a carga visualmente apoiada sobre
         * o pallet, sem alterar a posicao
         * logica da localizacao.
         */
        PALLET_BOARD_OFFSETS_X.forEach(
          (
            offsetX,
            boardIndex,
          ) => {
            const instanceIndex =
              i *
                PALLET_BOARD_OFFSETS_X.length +
              boardIndex;

            dummy.position.set(
              p[0] +
                offsetX *
                  profile.palletScaleX,
              p[1] - 0.30,
              p[2],
            );

            dummy.rotation.set(
              0,
              0,
              0,
            );

            if (possuiCarga) {
              dummy.scale.set(
                profile.palletScaleX,
                1,
                profile.palletScaleZ,
              );
            } else {
              dummy.scale.setScalar(
                0.0001,
              );
            }

            dummy.updateMatrix();

            pallets.setMatrixAt(
              instanceIndex,
              dummy.matrix,
            );
          },
        );


        /*
         * Nove blocos estruturais.
         */
        let blockIndex =
          i *
          (
            PALLET_BLOCK_OFFSETS_X.length *
            PALLET_BLOCK_OFFSETS_Z.length
          );

        PALLET_BLOCK_OFFSETS_X.forEach(
          (
            offsetX,
          ) => {
            PALLET_BLOCK_OFFSETS_Z.forEach(
              (
                offsetZ,
              ) => {
                dummy.position.set(
                  p[0] +
                    offsetX *
                      profile.palletScaleX,
                  p[1] - 0.365,
                  p[2] +
                    offsetZ *
                      profile.palletScaleZ,
                );

                dummy.rotation.set(
                  0,
                  0,
                  0,
                );

                if (possuiCarga) {
                  dummy.scale.set(
                    profile.palletScaleX,
                    1,
                    profile.palletScaleZ,
                  );
                } else {
                  dummy.scale.setScalar(
                    0.0001,
                  );
                }

                dummy.updateMatrix();

                palletBlocks.setMatrixAt(
                  blockIndex,
                  dummy.matrix,
                );

                blockIndex += 1;
              },
            );
          },
        );


        /*
         * Reguas inferiores.
         */
        PALLET_RUNNER_OFFSETS_Z.forEach(
          (
            offsetZ,
            runnerIndex,
          ) => {
            const instanceIndex =
              i *
                PALLET_RUNNER_OFFSETS_Z.length +
              runnerIndex;

            dummy.position.set(
              p[0],
              p[1] - 0.427,
              p[2] +
                offsetZ *
                  profile.palletScaleZ,
            );

            dummy.rotation.set(
              0,
              0,
              0,
            );

            if (possuiCarga) {
              dummy.scale.set(
                profile.palletScaleX,
                1,
                profile.palletScaleZ,
              );
            } else {
              dummy.scale.setScalar(
                0.0001,
              );
            }

            dummy.updateMatrix();

            palletRunners.setMatrixAt(
              instanceIndex,
              dummy.matrix,
            );
          },
        );


        // ====================================================
        // HITBOX INVISÍVEL
        // ====================================================

        dummy.position.set(
          p[0],
          p[1],
          p[2],
        );

        dummy.rotation.set(
          0,
          0,
          0,
        );

        dummy.scale.set(
          1,
          1,
          1,
        );

        dummy.updateMatrix();

        hits.setMatrixAt(
          i,
          dummy.matrix,
        );
      },
    );


    boxes.instanceMatrix.needsUpdate =
      true;

    pallets.instanceMatrix.needsUpdate =
      true;

    palletBlocks.instanceMatrix.needsUpdate =
      true;

    palletRunners.instanceMatrix.needsUpdate =
      true;

    wraps.instanceMatrix.needsUpdate =
      true;

    hits.instanceMatrix.needsUpdate =
      true;
  }, [
    locations,
    positions,
    showFreeMarkers,
  ]);


  useEffect(() => {
    const boxes =
      boxRef.current;

    if (!boxes) {
      return;
    }


    locations.forEach(
      (location, i) => {
        const active =
          location.code ===
            selectedCode ||
          location.code ===
            highlightedCode;


        const locationColor =
          showFreeMarkers &&
          location.status ===
            "livre"
            ? FREE_MARKER_COLOR
            : STATUS_COLORS[
                location.status
              ];

        color.set(
          active
            ? SELECTED_COLOR
            : locationColor,
        );


        boxes.setColorAt(
          i,
          color,
        );
      },
    );


    if (
      boxes.instanceColor
    ) {
      boxes.instanceColor
        .needsUpdate = true;
    }
  }, [
    locations,
    selectedCode,
    highlightedCode,
    showFreeMarkers,
  ]);


  const handleMove = (
    e:
      ThreeEvent<PointerEvent>,
  ) => {
    e.stopPropagation();

    const id =
      e.instanceId;

    if (
      id === undefined
    ) {
      return;
    }


    onHover(
      locations[id] ??
      null,
    );
  };


  const handleClick = (
    e:
      ThreeEvent<MouseEvent>,
  ) => {
    e.stopPropagation();

    const id =
      e.instanceId;

    if (
      id === undefined
    ) {
      return;
    }


    const location =
      locations[id];


    if (location) {
      onSelect(
        location,
      );
    }
  };


  return (
    <group>
      {/*
       * Tabuas superiores do pallet.
       */}
      <instancedMesh
        ref={palletRef}
        args={[
          palletGeo,
          palletMat,
          count *
            PALLET_BOARD_OFFSETS_X.length,
        ]}
        frustumCulled={false}
        castShadow
        receiveShadow
        raycast={() => null}
      />


      {/*
       * Blocos estruturais do pallet.
       */}
      <instancedMesh
        ref={palletBlockRef}
        args={[
          palletBlockGeo,
          palletMat,
          count *
            PALLET_BLOCK_OFFSETS_X.length *
            PALLET_BLOCK_OFFSETS_Z.length,
        ]}
        frustumCulled={false}
        castShadow
        receiveShadow
        raycast={() => null}
      />


      {/*
       * Reguas inferiores do pallet.
       */}
      <instancedMesh
        ref={palletRunnerRef}
        args={[
          palletRunnerGeo,
          palletRunnerMat,
          count *
            PALLET_RUNNER_OFFSETS_Z.length,
        ]}
        frustumCulled={false}
        castShadow
        receiveShadow
        raycast={() => null}
      />

      <instancedMesh
        ref={boxRef}
        args={[
          boxGeo,
          boxMat,
          count,
        ]}
        frustumCulled={false}
        castShadow
        receiveShadow
        raycast={() => null}
      />


      {/*
       * Contorno sutil da embalagem.
       * Não interfere com clique ou status.
       */}
      <instancedMesh
        ref={wrapRef}
        args={[
          wrapGeo,
          wrapMat,
          count,
        ]}
        frustumCulled={false}
        raycast={() => null}
      />

      <instancedMesh
        ref={hitRef}
        args={[
          hitGeo,
          hitMat,
          count,
        ]}
        frustumCulled={false}
        onPointerMove={
          handleMove
        }
        onPointerOut={() =>
          onHover(null)
        }
        onClick={
          handleClick
        }
      />
    </group>
  );
}
