import {
  SELECTED_COLOR,
  STATUS_COLORS,
  type LocationStatus,
} from "@/data/warehouseData";


type TipoVisualizacao =
  | "estoque-atual"
  | "estoque-inventario"
  | "divergencia";


interface Props {
  tipoVisualizacao: TipoVisualizacao;
  tipoInventario:
    | "ROTATIVO"
    | "OFICIAL"
    | null;
}


interface ItemLegenda {
  label: string;
  color: string;
}


function itemStatus(
  status: LocationStatus,
  label: string,
): ItemLegenda {
  return {
    label,
    color:
      STATUS_COLORS[
        status
      ],
  };
}


export function Legend({
  tipoVisualizacao,
  tipoInventario,
}: Props) {
  let titulo =
    "Legenda";

  let itens:
    ItemLegenda[] = [];


  /*
   * ESTOQUE DO ARMAZEM
   */
  if (
    tipoVisualizacao ===
    "estoque-atual"
  ) {
    titulo =
      "Estoque do armaz\u00e9m";

    itens = [
      itemStatus(
        "livre",
        "Livre",
      ),
      itemStatus(
        "ocupada",
        "Com estoque",
      ),
    ];
  }


  /*
   * ESTOQUE DO INVENTARIO
   */
  else if (
    tipoVisualizacao ===
    "estoque-inventario"
  ) {
    titulo =
      "Estoque do inventário";

    itens = [
      itemStatus(
        "ocupada",
        "No inventário",
      ),
    ];

    if (
      tipoInventario ===
      "ROTATIVO"
    ) {
      itens.push(
        itemStatus(
          "divergencia",
          "Divergência",
        ),
        itemStatus(
          "recontagem",
          "Recontagem",
        ),
      );
    }
  }


  /*
   * VISAO DE DIVERGENCIAS
   */
  else {
    titulo =
      "Divergências";

    itens = [
      itemStatus(
        "divergencia",
        "Divergência",
      ),
      itemStatus(
        "recontagem",
        "Recontagem",
      ),
    ];
  }


  /*
   * Selecionada e um estado visual,
   * nao um status operacional.
   */
  itens.push({
    label:
      "Selecionada",
    color:
      SELECTED_COLOR,
  });


  return (
    <div
      className="
        inline-flex
        max-w-full
        flex-wrap
        items-center
        gap-x-3
        gap-y-1.5
        rounded-md
        border
        border-border/60
        bg-background/80
        px-2.5
        py-1.5
        shadow-sm
        backdrop-blur-sm
      "
    >
      {/* LEGENDA_COMPACTA */}
      <span
        className="
          shrink-0
          text-[9px]
          font-semibold
          uppercase
          tracking-[0.1em]
          text-muted-foreground
        "
      >
        {titulo}
      </span>


      <span
        className="
          hidden
          h-3
          w-px
          shrink-0
          bg-border/70
          sm:block
        "
        aria-hidden="true"
      />


      <div
        className="
          flex
          min-w-0
          flex-wrap
          items-center
          gap-x-2.5
          gap-y-1
        "
      >
        {itens.map(
          (
            item,
          ) => (
            <div
              key={
                item.label
              }
              className="
                flex
                shrink-0
                items-center
                gap-1.5
                whitespace-nowrap
                text-[10px]
                font-medium
                text-foreground/85
              "
            >
              <span
                className="
                  size-2
                  shrink-0
                  rounded-[2px]
                  border
                  border-black/10
                "
                style={{
                  backgroundColor:
                    item.color,
                }}
                aria-hidden="true"
              />

              <span>
                {
                  item.label
                }
              </span>
            </div>
          ),
        )}
      </div>
    </div>
  );
}
