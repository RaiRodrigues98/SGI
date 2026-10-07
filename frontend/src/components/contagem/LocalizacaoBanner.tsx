interface LocalizacaoBannerProps {
  codigo: string;
}

export function LocalizacaoBanner({ codigo }: LocalizacaoBannerProps) {
  return (
    <div className="overflow-hidden rounded-lg border border-gold/60 bg-card shadow-xs">
      <p className="bg-gold px-4 py-2 text-xs font-bold uppercase tracking-widest text-gold-foreground">
        Localização ativa
      </p>
      <p className="break-all px-4 py-3 font-mono text-2xl font-bold leading-tight tracking-tight text-primary sm:text-3xl">
        {codigo}
      </p>
    </div>
  );
}
