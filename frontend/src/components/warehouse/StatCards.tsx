interface Props {
  totalPosicoes: number;
  totalModulos: number;
  porRua: Record<string, number>;
}

function Card({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums text-card-foreground">{value}</p>
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

export function StatCards({ totalPosicoes, totalModulos, porRua }: Props) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Card label="Posições" value={String(totalPosicoes)} hint="720 esperadas" />
      <Card label="Módulos" value={String(totalModulos)} hint="45 esperados" />
      <Card
        label="R01 / R02"
        value={`${porRua["R01"] ?? 0} / ${porRua["R02"] ?? 0}`}
        hint="dois lados"
      />
      <Card label="R03" value={String(porRua["R03"] ?? 0)} hint="somente lado ímpar" />
    </div>
  );
}
