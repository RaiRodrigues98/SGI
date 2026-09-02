from pathlib import Path
import shutil
import py_compile
from datetime import datetime

ROOT = Path.cwd()
router = ROOT / "routers" / "rotativo_ciclos.py"

if not router.exists():
    raise FileNotFoundError(f"Não encontrado: {router}")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = router.with_name(
    f"{router.stem}_backup_imports_{timestamp}{router.suffix}"
)

shutil.copy2(router, backup)

try:
    texto = router.read_text(encoding="utf-8")

    bloco_ciclos_duplicado = '''from services.ciclos_rotativo import (
    abrir_ciclo_rotativo,
    consultar_ciclo_atual,
)

from services.ciclos_rotativo import (
    abrir_ciclo_rotativo,
    consultar_ciclo_atual,
    finalizar_ciclo_rotativo,
)
'''

    bloco_ciclos_limpo = '''from services.ciclos_rotativo import (
    abrir_ciclo_rotativo,
    consultar_ciclo_atual,
    finalizar_ciclo_rotativo,
)
'''

    if bloco_ciclos_duplicado not in texto:
        raise RuntimeError(
            "Bloco duplicado de services.ciclos_rotativo não encontrado."
        )

    texto = texto.replace(
        bloco_ciclos_duplicado,
        bloco_ciclos_limpo,
        1
    )

    bloco_tratativas_duplicado = '''from services.rotativo_tratativas import (
    consultar_tratativas_rotativo,
)
from services.rotativo_tratativas import (
    consultar_tratativas_rotativo,
    resolver_ocorrencia_rotativo,
)
'''

    bloco_tratativas_limpo = '''from services.rotativo_tratativas import (
    consultar_tratativas_rotativo,
    resolver_ocorrencia_rotativo,
)
'''

    if bloco_tratativas_duplicado not in texto:
        raise RuntimeError(
            "Bloco duplicado de services.rotativo_tratativas não encontrado."
        )

    texto = texto.replace(
        bloco_tratativas_duplicado,
        bloco_tratativas_limpo,
        1
    )

    router.write_text(texto, encoding="utf-8")

    py_compile.compile(
        str(router),
        doraise=True
    )

    texto_final = router.read_text(encoding="utf-8")

    if texto_final.count("from services.ciclos_rotativo import (") != 1:
        raise RuntimeError(
            "Ainda existe duplicidade no import de ciclos_rotativo."
        )

    if texto_final.count("from services.rotativo_tratativas import (") != 1:
        raise RuntimeError(
            "Ainda existe duplicidade no import de rotativo_tratativas."
        )

except Exception:
    shutil.copy2(backup, router)
    raise

print("APROVADO")
print()
print("Alterações:")
print("- consolidado import de services.ciclos_rotativo")
print("- consolidado import de services.rotativo_tratativas")
print("- nenhuma rota alterada")
print("- nenhuma regra de negócio alterada")
print("- py_compile aprovado")
print()
print(f"Backup: {backup}")
