from pathlib import Path
import py_compile
import shutil

PATCH_MARK = "PROTEÇÃO R2 ROTATIVO - ITEM AUTORIZADO"
PATCH = '\n        # ====================================================\n        # PROTEÇÃO R2 ROTATIVO - ITEM AUTORIZADO\n        # ====================================================\n\n        if (\n            _normalizar_upper(\n                sessao.TipoInventario\n            ) == "ROTATIVO"\n            and\n            int(\n                sessao.NumeroRodada\n            ) >= 2\n        ):\n\n            cursor.execute(\n                """\n                SELECT COUNT(*)\n                FROM dbo.RodadaItens\n                WHERE\n                    ID_Inventario = ?\n                    AND ID_Rodada = ?\n                    AND LTRIM(RTRIM(Codigo)) = ?\n                    AND ISNULL(\n                        LTRIM(RTRIM(Lote)),\n                        \'\'\n                    ) = ?\n                """,\n                (\n                    sessao.ID_Inventario,\n                    sessao.ID_Rodada,\n                    codigo,\n                    lote or ""\n                )\n            )\n\n            item_autorizado_na_r2 = (\n                cursor.fetchone()[0] > 0\n            )\n\n            if not item_autorizado_na_r2:\n\n                raise HTTPException(\n                    status_code=400,\n                    detail=(\n                        "Este item não pertence à "\n                        "recontagem desta rodada."\n                    )\n                )\n\n'


def project_root():
    here = Path(__file__).resolve().parent
    if here.name.lower() == "tests_e2e":
        return here.parent
    return here


def find_contagens(root: Path) -> Path:
    candidates = [
        root / "routes" / "contagens.py",
        root / "app" / "routes" / "contagens.py",
        root / "src" / "routes" / "contagens.py",
        root / "api" / "routes" / "contagens.py",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    found = [
        p for p in root.rglob("contagens.py")
        if ".venv" not in p.parts
        and "__pycache__" not in p.parts
    ]

    if len(found) == 1:
        return found[0]

    if not found:
        raise FileNotFoundError(
            "Não encontrei contagens.py dentro do projeto."
        )

    raise RuntimeError(
        "Encontrei mais de um contagens.py; patch cancelado:\n - "
        + "\n - ".join(str(p) for p in found)
    )


def main():
    root = project_root()
    target = find_contagens(root)

    print(f"Projeto: {root}")
    print(f"Arquivo: {target}")

    original = target.read_text(encoding="utf-8")

    if PATCH_MARK in original:
        print("[OK] Proteção R2 ROTATIVA já aplicada.")
        return

    start = original.find("I.Tipo AS TipoInventario")

    if start == -1:
        raise RuntimeError(
            "Estrutura esperada não encontrada: I.Tipo AS TipoInventario."
        )

    marker = (
        "        # ====================================================\n"
        "        # 6. VERIFICA CÓDIGO NO SNAPSHOT\n"
        "        # ====================================================\n"
    )

    insert_at = original.find(marker, start)

    if insert_at == -1:
        raise RuntimeError(
            "Ponto seguro de inserção não encontrado. Nenhuma alteração feita."
        )

    updated = original[:insert_at] + PATCH + original[insert_at:]

    backup = target.with_suffix(target.suffix + ".bak_r2_rotativo")
    shutil.copy2(target, backup)
    print(f"Backup: {backup}")

    target.write_text(updated, encoding="utf-8")

    try:
        py_compile.compile(str(target), doraise=True)
    except Exception:
        shutil.copy2(backup, target)
        print("[ERRO] Sintaxe inválida. Original restaurado.")
        raise

    print("[PASS] Patch aplicado.")
    print("[PASS] Sintaxe validada.")
    print("Reinicie a API antes dos testes.")


if __name__ == "__main__":
    main()
