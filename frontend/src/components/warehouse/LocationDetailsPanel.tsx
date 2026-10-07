import {
  STATUS_COLORS,
  STATUS_LABELS,
  type DamageArea,
  type WarehouseLocation,
} from "@/data/warehouseData";

interface Props {
  location: WarehouseLocation | null;
  damage: DamageArea | null;
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border/60 py-1.5 text-sm last:border-0">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium text-card-foreground">{value}</span>
    </div>
  );
}

export function LocationDetailsPanel({ location, damage }: Props) {
  if (damage) {
    return (
      <div className="rounded-lg border-2 border-red-500 bg-card p-4">
        <h2 className="font-mono text-lg font-bold text-card-foreground">{damage.code}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{damage.descricao}</p>
      </div>
    );
  }

  if (!location) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-card p-4">
        <h2 className="text-sm font-semibold text-card-foreground">Detalhes da posição</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Clique em uma posição na cena 3D ou pesquise um código para ver os detalhes.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-mono text-lg font-bold text-card-foreground">{location.code}</h2>
        <span
          className="rounded-full px-2 py-0.5 text-xs font-semibold text-black/80"
          style={{ backgroundColor: STATUS_COLORS[location.status] }}
        >
          {STATUS_LABELS[location.status]}
        </span>
      </div>
      <div className="mt-3">
        <Row label="Rua" value={location.rua} />
        <Row label="Lado" value={location.lado === "impar" ? "Ímpar" : "Par"} />
        <Row label="Módulo" value={String(location.modulo).padStart(3, "0")} />
        <Row label="Nível" value={String(location.nivel).padStart(3, "0")} />
        <Row label="Posição" value={String(location.posicao).padStart(2, "0")} />
        <Row label="Produto" value={location.produto ?? "—"} />
        <Row label="Lote" value={location.lote ?? "—"} />
        <Row label="Quantidade" value={location.quantidade ? `${location.quantidade} un` : "0"} />
      </div>
    </div>
  );
}
