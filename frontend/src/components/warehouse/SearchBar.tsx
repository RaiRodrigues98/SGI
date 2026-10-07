import { RotateCcw, Search } from "lucide-react";
import { useState, type FormEvent } from "react";

interface Props {
  onSearch: (query: string) => void;
  onResetCamera: () => void;
  feedback: { ok: boolean; message: string } | null;
}

export function SearchBar({
  onSearch,
  onResetCamera,
  feedback,
}: Props) {
  const [value, setValue] = useState("");

  const submit = (e: FormEvent) => {
    e.preventDefault();

    const query = value.trim();

    if (!query) {
      return;
    }

    onSearch(query);
  };

  return (
    <div className="space-y-1">
      <form
        onSubmit={submit}
        className="flex items-center gap-2"
      >
        <div className="relative w-[260px]">
          <Search
            className="
              pointer-events-none
              absolute
              left-3
              top-1/2
              size-4
              -translate-y-1/2
              text-muted-foreground
            "
          />

          <input
            value={value}
            onChange={(e) =>
              setValue(e.target.value)
            }
            placeholder="Pesquisar localização..."
            className="
              h-10
              w-full
              rounded-lg
              border
              border-input
              bg-background/90
              pl-9
              pr-10
              font-mono
              text-sm
              outline-none
              transition
              focus:ring-2
              focus:ring-ring
            "
          />

          <button
            type="submit"
            title="Pesquisar localização"
            aria-label="Pesquisar localização"
            className="
              absolute
              right-1
              top-1/2
              flex
              size-8
              -translate-y-1/2
              items-center
              justify-center
              rounded-md
              text-muted-foreground
              transition-colors
              hover:bg-accent
              hover:text-foreground
            "
          >
            <Search className="size-4" />
          </button>
        </div>

        <button
          type="button"
          onClick={onResetCamera}
          title="Restaurar câmera"
          aria-label="Restaurar câmera"
          className="
            flex
            size-10
            shrink-0
            items-center
            justify-center
            rounded-lg
            border
            border-input
            bg-background/90
            text-muted-foreground
            transition-colors
            hover:bg-accent
            hover:text-foreground
          "
        >
          <RotateCcw className="size-4" />
        </button>
      </form>

      {feedback ? (
        <p
          className={`text-[11px] font-medium ${
            feedback.ok
              ? "text-green-600"
              : "text-destructive"
          }`}
        >
          {feedback.message}
        </p>
      ) : null}
    </div>
  );
}
