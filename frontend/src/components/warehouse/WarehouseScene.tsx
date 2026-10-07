import {
  Html,
  OrbitControls,
} from "@react-three/drei";

import {
  Canvas,
  useFrame,
  useThree,
} from "@react-three/fiber";

import {
  useEffect,
  useRef,
  useState,
} from "react";

import * as THREE from "three";

import type {
  OrbitControls as OrbitControlsImpl,
} from "three-stdlib";

import {
  FACES,
  type WarehouseLocation,
} from "@/data/warehouseData";

import { DamageArea } from "./DamageArea";
import { LocationInstances } from "./LocationInstances";
import { RackFace } from "./RackFace";
import { WarehouseFloor } from "./WarehouseFloor";

import {
  AISLE_GUIDES,
  FACE_LENGTH,
  FACE_Z_MAP,
  RACK_DEPTH,
  RACK_X_OFFSET,
  faceZ,
  locationPosition,
} from "./layout";


/*
 * ============================================================
 * CAMERA INICIAL
 * ============================================================
 *
 * X negativo = frente física do galpão.
 *
 * Y = altura aproximada dos olhos.
 *
 * Z = inicia no corredor central.
 */

const WALK_EYE_HEIGHT = 2.35;

const START_AISLE_Z =
  AISLE_GUIDES[1] ?? 6.1;


export const DEFAULT_CAMERA:
  [number, number, number] = [
    -18,
    34,
    -12,
  ];


export const DEFAULT_TARGET:
  [number, number, number] = [
    1,
    3.5,
    7,
  ];


type CameraMode =
  | "overview"
  | "walk";


/*
 * ============================================================
 * CAMERA DE PERCURSO
 * ============================================================
 *
 * Entra pela frente física do galpão
 * no corredor da R01.
 */

const WALK_AISLE_Z =
  AISLE_GUIDES[0] ?? 14.75;


const WALK_CAMERA:
  [number, number, number] = [
    RACK_X_OFFSET -
      FACE_LENGTH / 2 -
      3.5,

    WALK_EYE_HEIGHT,

    WALK_AISLE_Z,
  ];


const WALK_TARGET:
  [number, number, number] = [
    RACK_X_OFFSET -
      FACE_LENGTH / 2 +
      8,

    WALK_EYE_HEIGHT,

    WALK_AISLE_Z,
  ];


/*
 * ============================================================
 * CONFIGURAÇÃO DO PASSEIO
 * ============================================================
 */

const WALK_SPEED = 6.5;

const WALK_FAST_SPEED = 11;


/*
 * Limites aproximados do piso navegável.
 *
 * Evitam que a câmera simplesmente saia
 * do galpão durante a navegação.
 */
const WALK_BOUNDS = {
  /*
   * Mantemos espaço suficiente
   * na frente e no fundo para permitir
   * a troca de corredor.
   */
  minX: -(FACE_LENGTH / 2 + 6),
  maxX: FACE_LENGTH / 2 + 6,

  /*
   * Grande área livre do lado da R03.
   */
  /*
   * Grande área livre do lado da R03.
   *
   * A parede física está aproximadamente
   * em Z = -26, então deixamos margem
   * para a câmera.
   */
  minZ: -24,

  /*
   * Parede direita, logo após R01 ímpar.
   */
  maxZ: 21.5,
};


/*
 * ============================================================
 * COLISÃO COM AS ESTRUTURAS
 * ============================================================
 */

const CAMERA_RADIUS = 0.38;

const RACK_COLLISION_MARGIN = 0.12;

const RACK_BLOCK_HALF_DEPTH =
  RACK_DEPTH / 2 +
  CAMERA_RADIUS +
  RACK_COLLISION_MARGIN;


/*
 * A colisão só existe enquanto estamos
 * longitudinalmente ao lado dos racks.
 *
 * Na frente e no fundo, a câmera fica livre
 * para trocar de corredor.
 */
const RACK_COLLISION_MIN_X =
  RACK_X_OFFSET -
  (
    FACE_LENGTH / 2 +
    CAMERA_RADIUS
  );

const RACK_COLLISION_MAX_X =
  RACK_X_OFFSET +
  FACE_LENGTH / 2 +
  CAMERA_RADIUS;


const RACK_FACE_POSITIONS =
  Object.values(
    FACE_Z_MAP,
  );


function collidesWithRack(
  x: number,
  z: number,
): boolean {
  const insideRackLength =
    x >= RACK_COLLISION_MIN_X &&
    x <= RACK_COLLISION_MAX_X;


  if (!insideRackLength) {
    return false;
  }


  return RACK_FACE_POSITIONS.some(
    (rackZ) =>
      Math.abs(
        z - rackZ,
      ) < RACK_BLOCK_HALF_DEPTH,
  );
}


interface Props {
  locations:
    WarehouseLocation[];

  /*
   * Mostra identificacao visual das
   * posicoes livres quando solicitado.
   */
  showFreeMarkers?: boolean;

  selected:
    WarehouseLocation | null;

  highlightedCode:
    string | null;

  damageLabel:
    string;

  damageSelected:
    boolean;

  cameraFocus:
    {
      position:
        [number, number, number];

      target:
        [number, number, number];
    } | null;

  onSelect:
    (
      location:
        WarehouseLocation,
    ) => void;

  onSelectDamage:
    () => void;

  onClear:
    () => void;
}


/*
 * ============================================================
 * CAMERA DE FOCO
 * ============================================================
 *
 * Mantém o funcionamento já existente:
 * pesquisa por localização / foco automático.
 */

function CameraRig({
  focus,
  controlsRef,
  mode,
}: {
  focus:
    Props["cameraFocus"];

  controlsRef:
    React.RefObject<
      OrbitControlsImpl | null
    >;

  mode:
    CameraMode;
}) {
  const {
    camera,
  } = useThree();


  const desiredPos =
    useRef(
      new THREE.Vector3(
        ...DEFAULT_CAMERA,
      ),
    );


  const desiredTarget =
    useRef(
      new THREE.Vector3(
        ...DEFAULT_TARGET,
      ),
    );


  const animating =
    useRef(false);


  /*
   * Troca suave entre visão geral
   * e percurso pelo galpão.
   */
  useEffect(() => {
    const position =
      mode === "overview"
        ? DEFAULT_CAMERA
        : WALK_CAMERA;


    const target =
      mode === "overview"
        ? DEFAULT_TARGET
        : WALK_TARGET;


    desiredPos.current.set(
      ...position,
    );


    desiredTarget.current.set(
      ...target,
    );


    animating.current =
      true;
  }, [
    mode,
  ]);


  /*
   * A pesquisa por localização continua
   * tendo prioridade quando houver foco.
   */
  useEffect(() => {
    if (!focus) {
      return;
    }


    desiredPos.current.set(
      ...focus.position,
    );


    desiredTarget.current.set(
      ...focus.target,
    );


    animating.current =
      true;
  }, [
    focus,
  ]);


  useFrame(() => {
    if (
      !animating.current
    ) {
      return;
    }


    const controls =
      controlsRef.current;


    camera.position.lerp(
      desiredPos.current,
      0.08,
    );


    if (controls) {
      controls.target.lerp(
        desiredTarget.current,
        0.08,
      );

      controls.update();
    }


    if (
      camera.position.distanceTo(
        desiredPos.current,
      ) < 0.05
    ) {
      animating.current =
        false;
    }
  });


  return null;
}


/*
 * ============================================================
 * NAVEGAÇÃO PELOS CORREDORES
 * ============================================================
 *
 * W / ↑ = frente
 * S / ↓ = trás
 * A / ← = esquerda
 * D / → = direita
 *
 * SHIFT = movimento rápido.
 *
 * A direção sempre acompanha a direção
 * em que o usuário está olhando.
 */

function WalkControls({
  controlsRef,
  enabled,
}: {
  controlsRef:
    React.RefObject<
      OrbitControlsImpl | null
    >;

  enabled:
    boolean;
}) {
  const {
    camera,
  } = useThree();


  const keys =
    useRef(
      new Set<string>(),
    );


  const forward =
    useRef(
      new THREE.Vector3(),
    );


  const right =
    useRef(
      new THREE.Vector3(),
    );


  const movement =
    useRef(
      new THREE.Vector3(),
    );


  const appliedMovement =
    useRef(
      new THREE.Vector3(),
    );


  const up =
    useRef(
      new THREE.Vector3(
        0,
        1,
        0,
      ),
    );


  useEffect(() => {
    if (!enabled) {
      keys.current.clear();
    }


    const isFormElement = (
      target: EventTarget | null,
    ) => {
      if (
        !(target instanceof HTMLElement)
      ) {
        return false;
      }


      return (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.tagName === "SELECT" ||
        target.isContentEditable
      );
    };


    const handleKeyDown = (
      event: KeyboardEvent,
    ) => {
      if (!enabled) {
        return;
      }
      if (
        isFormElement(
          event.target,
        )
      ) {
        return;
      }


      const key =
        event.key.toLowerCase();


      const navigationKeys =
        new Set([
          "w",
          "a",
          "s",
          "d",
          "arrowup",
          "arrowdown",
          "arrowleft",
          "arrowright",
          "shift",
        ]);


      if (
        !navigationKeys.has(
          key,
        )
      ) {
        return;
      }


      keys.current.add(key);


      /*
       * Impede as setas de rolarem
       * a página enquanto o usuário
       * navega no mapa.
       */
      if (
        key.startsWith(
          "arrow",
        )
      ) {
        event.preventDefault();
      }
    };


    const handleKeyUp = (
      event: KeyboardEvent,
    ) => {
      keys.current.delete(
        event.key.toLowerCase(),
      );
    };


    const handleBlur = () => {
      keys.current.clear();
    };


    window.addEventListener(
      "keydown",
      handleKeyDown,
    );


    window.addEventListener(
      "keyup",
      handleKeyUp,
    );


    window.addEventListener(
      "blur",
      handleBlur,
    );


    return () => {
      window.removeEventListener(
        "keydown",
        handleKeyDown,
      );


      window.removeEventListener(
        "keyup",
        handleKeyUp,
      );


      window.removeEventListener(
        "blur",
        handleBlur,
      );
    };
  }, [enabled]);


  useFrame(
    (
      _state,
      delta,
    ) => {
      if (!enabled) {
        return;
      }


      const controls =
        controlsRef.current;


      const pressed =
        keys.current;


      const moveForward =
        pressed.has("w") ||
        pressed.has("arrowup");


      const moveBackward =
        pressed.has("s") ||
        pressed.has("arrowdown");


      const moveLeft =
        pressed.has("a") ||
        pressed.has("arrowleft");


      const moveRight =
        pressed.has("d") ||
        pressed.has("arrowright");


      if (
        !moveForward &&
        !moveBackward &&
        !moveLeft &&
        !moveRight
      ) {
        return;
      }


      /*
       * Direção para onde a câmera
       * está olhando.
       */
      if (controls) {
        forward.current
          .copy(
            controls.target,
          )
          .sub(
            camera.position,
          );
      } else {
        camera.getWorldDirection(
          forward.current,
        );
      }


      /*
       * Caminhada sempre no piso.
       * Não voamos para cima/baixo.
       */
      forward.current.y = 0;


      if (
        forward.current.lengthSq() <
        0.0001
      ) {
        return;
      }


      forward.current.normalize();


      /*
       * Vetor lateral.
       */
      right.current
        .crossVectors(
          forward.current,
          up.current,
        )
        .normalize();


      movement.current.set(
        0,
        0,
        0,
      );


      if (moveForward) {
        movement.current.add(
          forward.current,
        );
      }


      if (moveBackward) {
        movement.current.sub(
          forward.current,
        );
      }


      if (moveRight) {
        movement.current.add(
          right.current,
        );
      }


      if (moveLeft) {
        movement.current.sub(
          right.current,
        );
      }


      if (
        movement.current.lengthSq() <
        0.0001
      ) {
        return;
      }


      const speed =
        pressed.has("shift")
          ? WALK_FAST_SPEED
          : WALK_SPEED;


      /*
       * Evita saltos muito grandes caso
       * haja queda momentânea de FPS.
       *
       * Também reduz risco de atravessar
       * uma estrutura por "tunneling".
       */
      const safeDelta =
        Math.min(
          delta,
          0.05,
        );


      movement.current
        .normalize()
        .multiplyScalar(
          speed * safeDelta,
        );


      const oldX =
        camera.position.x;

      const oldZ =
        camera.position.z;


      const proposedX =
        THREE.MathUtils.clamp(
          oldX +
            movement.current.x,

          WALK_BOUNDS.minX,
          WALK_BOUNDS.maxX,
        );


      const proposedZ =
        THREE.MathUtils.clamp(
          oldZ +
            movement.current.z,

          WALK_BOUNDS.minZ,
          WALK_BOUNDS.maxZ,
        );


      /*
       * Resolução por eixo.
       *
       * Isso faz a câmera deslizar ao longo
       * do rack em vez de travar completamente
       * quando encosta na estrutura.
       */
      let nextX =
        oldX;

      let nextZ =
        oldZ;


      /*
       * Primeiro tenta movimento longitudinal.
       */
      if (
        !collidesWithRack(
          proposedX,
          oldZ,
        )
      ) {
        nextX =
          proposedX;
      }


      /*
       * Depois tenta movimento lateral.
       */
      if (
        !collidesWithRack(
          nextX,
          proposedZ,
        )
      ) {
        nextZ =
          proposedZ;
      }


      /*
       * Movimento realmente aplicado depois
       * da colisão e dos limites do galpão.
       */
      appliedMovement.current.set(
        nextX - oldX,
        0,
        nextZ - oldZ,
      );


      camera.position.x =
        nextX;

      camera.position.z =
        nextZ;


      /*
       * Camera e alvo precisam mover juntos
       * para preservar a direção do olhar.
       */
      if (controls) {
        controls.target.add(
          appliedMovement.current,
        );

        controls.update();
      }
    },
  );


  return null;
}


function StreetPlate({
  rua,
  lado,
  extremidade,
}: {
  rua:
    string;

  lado:
    "impar" | "par";

  extremidade:
    "frente" | "fundo";
}) {
  const label =
    rua.replace(
      /^R/,
      "",
    );


  const plateX =
    RACK_X_OFFSET +
    (
      extremidade ===
      "frente"
        ? -(
            FACE_LENGTH / 2 +
            0.35
          )
        : FACE_LENGTH / 2 +
          0.35
    );


  const dir =
    lado === "impar"
      ? -1
      : 1;


  return (
    <group
      position={[
        plateX,
        3.15,
        faceZ(
          rua,
          lado,
        ) +
          0.08 * dir,
      ]}
    >
      <Html
        center
        distanceFactor={22}
        zIndexRange={[
          12,
          0,
        ]}
        occlude
      >
        <div
          className="
            pointer-events-none
            relative
            flex
            min-w-[40px]
            flex-col
            items-center
            justify-center
            overflow-hidden
            rounded
            border
            border-slate-400/70
            bg-white/95
            px-2
            py-1
            shadow-sm
          "
        >
          {/* PLACA_ALZARSI_LAYOUT_FINAL_V1 */}

          {/* Fundo institucional */}
          <svg
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
            aria-hidden="true"
            className="
              absolute
              inset-0
              h-full
              w-full
            "
          >
            {/* Faixa azul */}
            <path
              d="
                M0 0
                H30
                C21 18
                 16 39
                 16 59
                C16 78
                 21 92
                 28 100
                H0
                Z
              "
              fill="#263b70"
            />

            {/* Curva dourada principal */}
            <path
              d="
                M31 -5
                C18 18
                 12 40
                 13 61
                C14 80
                 20 94
                 29 105
              "
              fill="none"
              stroke="#d4b36d"
              strokeWidth="7"
            />

            {/* Curva clara */}
            <path
              d="
                M37 -5
                C25 19
                 19 41
                 20 62
                C21 81
                 27 95
                 35 105
              "
              fill="none"
              stroke="#f2e7cf"
              strokeWidth="1.5"
            />

            {/* Grafismo suave */}
            <ellipse
              cx="78"
              cy="70"
              rx="24"
              ry="30"
              fill="#d6bd83"
              opacity="0.08"
            />
          </svg>


          {/* Logo */}
          <div
            className="
              absolute
              right-[4px]
              top-[2px]
              z-10
              flex
              items-center
              gap-[1px]
              leading-none
            "
          >
            <span
              className="
                text-[3px]
                font-black
                text-[#c7a45c]
              "
            >
              A
            </span>

            <div
              className="
                flex
                flex-col
              "
            >
              <span
                className="
                  text-[2.5px]
                  font-extrabold
                  tracking-[0.02em]
                  text-[#263b70]
                "
              >
                ALZARSI
              </span>

              <span
                className="
                  text-[1.2px]
                  font-semibold
                  tracking-[0.12em]
                  text-slate-500
                "
              >
                {"LOG\u00cdSTICA"}
              </span>
            </div>
          </div>


          {/* Conteudo principal */}
          <div
            className="
              relative
              z-10
              flex
              flex-col
              items-center
              justify-center
              translate-x-[3px]
              translate-y-[1px]
            "
          >
            <span
              className="
                text-[7px]
                font-semibold
                leading-none
                tracking-[0.08em]
                text-[#c49e56]
              "
            >
              RUA
            </span>

            <span
              className="
                text-[15px]
                font-extrabold
                leading-none
                tracking-[0.02em]
                text-[#28447c]
              "
            >
              {label}
            </span>

            <span
              className="
                mt-0.5
                text-[6px]
                font-medium
                uppercase
                tracking-[0.12em]
                text-slate-400
              "
            >
              {lado === "impar"
                ? "\u00cdMPAR"
                : "PAR"}
            </span>
          </div>
        </div>
      </Html>
    </group>
  );
}


export function WarehouseScene(
  props: Props,
) {
  const {
    locations,
    showFreeMarkers = false,
    selected,
    highlightedCode,
    damageLabel,
    damageSelected,
    cameraFocus,
    onSelect,
    onSelectDamage,
    onClear,
  } = props;


  const controlsRef =
    useRef<
      OrbitControlsImpl | null
    >(null);


  const [
    hovered,
    setHovered,
  ] =
    useState<
      WarehouseLocation | null
    >(null);


  const [
    cameraMode,
    setCameraMode,
  ] =
    useState<CameraMode>(
      "overview",
    );


  return (
    <div
      className="
        relative
        h-full
        w-full
      "
    >
      <Canvas
        dpr={[
        1,
        1.25,
      ]}
      camera={{
        position:
          DEFAULT_CAMERA,

        fov: 50,

        near: 0.1,

        far: 300,
      }}
      onPointerMissed={() =>
        onClear()
      }
    >
      <color
        attach="background"
        args={[
          "#e1e4e5",
        ]}
      />

      <fog
        attach="fog"
        args={[
          "#e1e4e5",
          75,
          145,
        ]}
      />


      {/*
       * Luz ambiente geral do galpão.
       * Menos contrastada para simular
       * iluminação industrial distribuída.
       */}
      {/*
       * ======================================================
       * ILUMINACAO INDUSTRIAL FINAL
       * ======================================================
       *
       * Estrategia de performance:
       * - 1 hemisphere light para preenchimento geral
       * - 1 directional light principal sem sombra
       * - 1 directional light sem sombra
       * - nenhuma point light por luminaria
       *
       * As luminarias do teto continuam visiveis,
       * mas nao geram luz individualmente.
       */}


      <hemisphereLight
        args={[
          "#ffffff",
          "#9a9d9f",
          1.32,
        ]}
      />


      {/*
       * Luz principal do galpao.
       * Luz principal do galpao, sem sombra projetada.
       */}
      <directionalLight
        color="#f8fafb"
        position={[
          -10,
          28,
          -7,
        ]}
        intensity={0.82}
      />


      {/*
       * Preenchimento frio lateral.
       * Nao gera sombra.
       */}
      <directionalLight
        color="#eef3f7"
        position={[
          20,
          16,
          18,
        ]}
        intensity={0.42}
      />


      <WarehouseFloor
        onClearSelection={
          onClear
        }
      />


      {FACES.map(
        (face) => (
          <RackFace
            key={
              `${face.rua}-${face.lado}`
            }
            rua={
              face.rua
            }
            lado={
              face.lado
            }
          />
        ),
      )}


      {FACES.flatMap(
        (face) => [
          <StreetPlate
            key={
              `placa-${face.rua}-${face.lado}-frente`
            }
            rua={
              face.rua
            }
            lado={
              face.lado
            }
            extremidade="frente"
          />,

          <StreetPlate
            key={
              `placa-${face.rua}-${face.lado}-fundo`
            }
            rua={
              face.rua
            }
            lado={
              face.lado
            }
            extremidade="fundo"
          />,
        ],
      )}


      <LocationInstances
        locations={
          locations
        }
        showFreeMarkers={
          showFreeMarkers
        }
        selectedCode={
          selected?.code ??
          null
        }
        highlightedCode={
          highlightedCode
        }
        onHover={
          setHovered
        }
        onSelect={
          onSelect
        }
      />


      <DamageArea
        label={
          damageLabel
        }
        selected={
          damageSelected
        }
        onSelect={
          onSelectDamage
        }
      />


      {(hovered ?? selected) && (
        <Html
          position={(() => {
            const location =
              (
                hovered ??
                selected
              )!;


            const position =
              locationPosition(
                location,
              );


            return [
              position[0],
              position[1] +
                0.9,
              position[2],
            ];
          })()}
          center
          distanceFactor={20}
          zIndexRange={[
            20,
            0,
          ]}
        >
          <div
            className="
              pointer-events-none
              whitespace-nowrap
              rounded
              bg-black/85
              px-2
              py-1
              font-mono
              text-[11px]
              text-white
            "
          >
            {
              (
                hovered ??
                selected
              )!.code
            }
          </div>
        </Html>
      )}


      <CameraRig
        focus={
          cameraFocus
        }
        controlsRef={
          controlsRef
        }
        mode={
          cameraMode
        }
      />


      <WalkControls
        controlsRef={
          controlsRef
        }
        enabled={
          cameraMode ===
          "walk"
        }
      />


      <OrbitControls
        ref={
          controlsRef
        }
        target={
          DEFAULT_TARGET
        }
        enableDamping
        dampingFactor={0.07}

        rotateSpeed={
          cameraMode ===
          "overview"
            ? 0.75
            : 0.55
        }

        zoomSpeed={
          cameraMode ===
          "overview"
            ? 1.15
            : 0.8
        }

        panSpeed={
          cameraMode ===
          "overview"
            ? 1.0
            : 0.6
        }

        screenSpacePanning={
          cameraMode ===
          "overview"
        }

        /*
         * O teclado passa a fazer
         * o deslocamento pelo galpão.
         */
        enablePan={
          cameraMode ===
          "overview"
        }

        /*
         * Mantém zoom pelo mouse.
         */
        enableZoom

        /*
         * Permite olhar um pouco
         * para cima e para baixo.
         */
        minPolarAngle={
          cameraMode ===
          "overview"
            ? 0.03
            : Math.PI / 3.2
        }

        maxPolarAngle={
          cameraMode ===
          "overview"
            ? Math.PI / 2.01
            : Math.PI / 1.65
        }

        minDistance={
          cameraMode ===
          "overview"
            ? 3
            : 2
        }

        maxDistance={
          cameraMode ===
          "overview"
            ? 140
            : 45
        }

        makeDefault
      />
      </Canvas>


      {/* ===================================================
          SELETOR DE CAMERA
          =================================================== */}

      <div
        className="
          pointer-events-none
          absolute
          right-3
          top-3
          z-30
          flex
          flex-col
          items-end
          gap-2
        "
      >
        <div
          className="
            pointer-events-auto
            flex
            items-center
            rounded-lg
            border
            border-border/30
            bg-background/80
            p-1
            shadow-sm
            backdrop-blur-md
          "
        >
          <button
            type="button"
            aria-pressed={
              cameraMode ===
              "overview"
            }
            onClick={() =>
              setCameraMode(
                "overview",
              )
            }
            className={`rounded-md px-3 py-2 text-xs font-medium transition-colors ${
              cameraMode ===
              "overview"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-accent hover:text-foreground"
            }`}
          >
            Visão geral
          </button>


          <button
            type="button"
            aria-pressed={
              cameraMode ===
              "walk"
            }
            onClick={() =>
              setCameraMode(
                "walk",
              )
            }
            className={`rounded-md px-3 py-2 text-xs font-medium transition-colors ${
              cameraMode ===
              "walk"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-accent hover:text-foreground"
            }`}
          >
            Percorrer galpão
          </button>
        </div>


        {cameraMode ===
          "walk" && (
          <div
            className="
              rounded-md
              bg-background/70
              px-2.5
              py-1.5
              text-[10px]
              text-muted-foreground
              backdrop-blur-sm
            "
          >
            W/A/S/D para mover • Shift para acelerar
          </div>
        )}
      </div>
    </div>
  );
}

