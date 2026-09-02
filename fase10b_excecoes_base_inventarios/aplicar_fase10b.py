
from pathlib import Path
from datetime import datetime
import ast
import py_compile
import shutil

ROOT = Path.cwd()

DOMAIN_DIR = ROOT / "domain"
DOMAIN_INIT = DOMAIN_DIR / "__init__.py"
DOMAIN_EXCEPTIONS = DOMAIN_DIR / "exceptions.py"

SERVICE = ROOT / "services" / "inventarios.py"
ROUTER = ROOT / "routers" / "inventarios.py"

DOMAIN_CONTENT = '"""Exceções independentes da camada HTTP."""\n\n\nclass DomainError(Exception):\n    """Base para erros semânticos do domínio/aplicação."""\n\n\nclass BusinessRuleViolation(DomainError):\n    """Regra de negócio ou validação semântica não atendida."""\n\n\nclass InvalidStateError(BusinessRuleViolation):\n    """Operação incompatível com o estado atual da entidade."""\n\n\nclass NotFoundError(DomainError):\n    """Entidade ou recurso de domínio não encontrado."""\n\n\nclass ConflictError(DomainError):\n    """Conflito semântico com estado ou recurso já existente."""\n'

EXPECTED_MESSAGES = [
    "Código do inventário obrigatório.",
    "Tipo de inventário inválido. ",
    "Valores permitidos: OFICIAL ou ROTATIVO.",
    "ClienteId inválido.",
    "Cliente obrigatório.",
    "Armazém obrigatório.",
    "Usuário responsável obrigatório.",
    "A Rodada 1 não está configurada ",
    "para este cliente e tipo de inventário.",
    "Já existe um inventário com ",
    "este código.",
]

EXPECTED_ROUTER_TOKENS = [
    '"/inventarios"',
    '"INVENTARIO_CRIAR"',
    "criar_inventario(",
    "SqlServerUnitOfWork",
    "uow.commit()",
]


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def parse(text, name):
    try:
        return ast.parse(text)
    except SyntaxError as exc:
        raise RuntimeError(f"{name}: sintaxe inválida: {exc}")


def raised_name(expr):
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Call):
        return raised_name(expr.func)
    if isinstance(expr, ast.Attribute):
        return expr.attr
    return None


def count_raises(text, exc_name):
    tree = parse(text, "arquivo")
    total = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        if raised_name(node.exc) == exc_name:
            total += 1
    return total


def service_state(text):
    http_import = "from fastapi import HTTPException" in text
    domain_import = (
        "from domain.exceptions import BusinessRuleViolation" in text
    )
    http_raises = count_raises(text, "HTTPException")
    business_raises = count_raises(text, "BusinessRuleViolation")

    if http_import and http_raises == 8 and business_raises == 0:
        return "LEGADO", {
            "http_raises": http_raises,
            "business_raises": business_raises,
        }

    if (
        not http_import
        and domain_import
        and http_raises == 0
        and business_raises == 8
    ):
        return "MIGRADO", {
            "http_raises": http_raises,
            "business_raises": business_raises,
        }

    return "DESCONHECIDO", {
        "http_import": http_import,
        "domain_import": domain_import,
        "http_raises": http_raises,
        "business_raises": business_raises,
    }


def exception_handler_count(text, name):
    tree = parse(text, "router")
    total = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if isinstance(node.type, ast.Name) and node.type.id == name:
            total += 1
    return total


def router_state(text):
    business_import = (
        "from domain.exceptions import BusinessRuleViolation" in text
    )
    business_handlers = exception_handler_count(
        text,
        "BusinessRuleViolation",
    )
    http_handlers = exception_handler_count(
        text,
        "HTTPException",
    )

    if (
        not business_import
        and business_handlers == 0
        and http_handlers >= 1
    ):
        return "LEGADO", {
            "business_handlers": business_handlers,
            "http_handlers": http_handlers,
        }

    if (
        business_import
        and business_handlers == 1
        and http_handlers >= 1
    ):
        return "MIGRADO", {
            "business_handlers": business_handlers,
            "http_handlers": http_handlers,
        }

    return "DESCONHECIDO", {
        "business_import": business_import,
        "business_handlers": business_handlers,
        "http_handlers": http_handlers,
    }


def validate_messages(text):
    for token in EXPECTED_MESSAGES:
        if token not in text:
            raise RuntimeError(
                "Mensagem esperada ausente em services/inventarios.py: "
                + repr(token)
            )


def validate_router_phase9(text, migrated=False):
    for token in EXPECTED_ROUTER_TOKENS:
        if token not in text:
            raise RuntimeError(
                "Contrato esperado ausente em routers/inventarios.py: "
                + repr(token)
            )

    if "get_connection()" in text:
        raise RuntimeError(
            "routers/inventarios.py regrediu para get_connection()."
        )

    if text.count("uow.commit()") != 1:
        raise RuntimeError(
            "Esperado exatamente 1 uow.commit() no router."
        )

    expected_rollbacks = 3 if migrated else 2

    if text.count("uow.rollback()") != expected_rollbacks:
        raise RuntimeError(
            "Quantidade inesperada de uow.rollback(): "
            f"{text.count('uow.rollback()')} "
            f"(esperado {expected_rollbacks})."
        )


def patch_service(text):
    state, diag = service_state(text)

    if state != "LEGADO":
        raise RuntimeError(
            f"Service não está em baseline legada: {state} / {diag}"
        )

    validate_messages(text)

    tree = parse(text, "services/inventarios.py")
    lines = text.splitlines()
    replacements = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue

        if not (
            isinstance(node.exc, ast.Call)
            and raised_name(node.exc) == "HTTPException"
        ):
            continue

        status_node = None
        detail_node = None

        for kw in node.exc.keywords:
            if kw.arg == "status_code":
                status_node = kw.value
            elif kw.arg == "detail":
                detail_node = kw.value

        if status_node is None or detail_node is None:
            raise RuntimeError(
                "HTTPException sem status_code/detail reconhecível."
            )

        if not (
            isinstance(status_node, ast.Constant)
            and status_node.value == 400
        ):
            raise RuntimeError(
                "Foi encontrado HTTPException com status diferente de 400 "
                "em services/inventarios.py."
            )

        detail_source = ast.get_source_segment(text, detail_node)

        if not detail_source:
            raise RuntimeError(
                "Não foi possível recuperar a expressão detail."
            )

        indent = " " * node.col_offset

        replacement = (
            f"{indent}raise BusinessRuleViolation(\n"
            f"{indent}    {detail_source}\n"
            f"{indent})"
        )

        replacements.append(
            (
                node.lineno,
                node.end_lineno,
                replacement,
            )
        )

    if len(replacements) != 8:
        raise RuntimeError(
            f"Esperados 8 raise HTTPException, encontrados {len(replacements)}."
        )

    replacements.sort(key=lambda item: item[0])

    out = []
    current = 1

    for start, end, replacement in replacements:
        out.extend(lines[current - 1:start - 1])
        out.extend(replacement.splitlines())
        current = end + 1

    out.extend(lines[current - 1:])

    patched = "\n".join(out)

    if text.endswith("\n"):
        patched += "\n"

    patched = patched.replace(
        "from fastapi import HTTPException",
        "from domain.exceptions import BusinessRuleViolation",
        1,
    )

    state2, diag2 = service_state(patched)

    if state2 != "MIGRADO":
        raise RuntimeError(
            f"Service pós-patch inválido: {state2} / {diag2}"
        )

    validate_messages(patched)

    return patched


def patch_router(text):
    state, diag = router_state(text)

    if state != "LEGADO":
        raise RuntimeError(
            f"Router não está em baseline legada: {state} / {diag}"
        )

    validate_router_phase9(text, migrated=False)

    anchor = "from dependencies.auth import ("

    if anchor not in text:
        raise RuntimeError(
            "Anchor de import do router não encontrado."
        )

    patched = text.replace(
        anchor,
        (
            "from domain.exceptions import BusinessRuleViolation\n\n"
            + anchor
        ),
        1,
    )

    marker = "    except HTTPException:"

    if patched.count(marker) != 1:
        raise RuntimeError(
            "Esperado exatamente 1 except HTTPException no router."
        )

    business_block = (
        "    except BusinessRuleViolation as erro:\n\n"
        "        uow.rollback()\n\n"
        "        raise HTTPException(\n"
        "            status_code=400,\n"
        "            detail=str(erro)\n"
        "        )\n\n"
    )

    patched = patched.replace(
        marker,
        business_block + marker,
        1,
    )

    state2, diag2 = router_state(patched)

    if state2 != "MIGRADO":
        raise RuntimeError(
            f"Router pós-patch inválido: {state2} / {diag2}"
        )

    validate_router_phase9(patched, migrated=True)

    return patched


print("[0/10] Validando arquivos...")

for path in [SERVICE, ROUTER]:
    if not path.exists():
        raise SystemExit(f"[ERRO] Arquivo ausente: {path}")

print("      [OK] arquivos encontrados.")


print("[1/10] Validando Fase 9 em routers/inventarios.py...")

router_text = read_text(ROUTER)
r_state, r_diag = router_state(router_text)

if r_state == "LEGADO":
    validate_router_phase9(router_text, migrated=False)
elif r_state == "MIGRADO":
    validate_router_phase9(router_text, migrated=True)
else:
    raise SystemExit(
        f"[ERRO] Router em baseline desconhecida: {r_diag}"
    )

print("      [OK] UoW/commit/rollback reconhecidos.")


print("[2/10] Analisando services/inventarios.py...")

service_text = read_text(SERVICE)
s_state, s_diag = service_state(service_text)

print(f"      Estado: {s_state}")
print(f"      HTTPException: {s_diag.get('http_raises', 0)}")
print(
    "      BusinessRuleViolation: "
    f"{s_diag.get('business_raises', 0)}"
)

if s_state == "DESCONHECIDO":
    raise SystemExit(
        f"[ERRO] Service em baseline desconhecida: {s_diag}"
    )


print("[3/10] Analisando tradução HTTP do router...")

print(f"      Estado: {r_state}")
print(
    "      BusinessRuleViolation handlers: "
    f"{r_diag.get('business_handlers', 0)}"
)
print(
    "      HTTPException handlers: "
    f"{r_diag.get('http_handlers', 0)}"
)


if s_state == "MIGRADO" and r_state == "MIGRADO":
    print("[4/10] Fase 10B já aplicada.")

    if not DOMAIN_EXCEPTIONS.exists():
        raise SystemExit(
            "[ERRO] domain/exceptions.py ausente."
        )

    print("      [OK] nenhuma alteração necessária.")
    raise SystemExit(0)


if not (
    s_state == "LEGADO"
    and r_state == "LEGADO"
):
    raise SystemExit(
        "[ERRO] Migração parcial detectada. "
        "Nenhum arquivo será alterado."
    )


print("[4/10] Validando/criando hierarchy de domínio...")

if DOMAIN_EXCEPTIONS.exists():
    existing = read_text(DOMAIN_EXCEPTIONS)

    for token in [
        "class DomainError(Exception)",
        "class BusinessRuleViolation(DomainError)",
        "class InvalidStateError(BusinessRuleViolation)",
        "class NotFoundError(DomainError)",
        "class ConflictError(DomainError)",
    ]:
        if token not in existing:
            raise SystemExit(
                "[ERRO] domain/exceptions.py já existe com "
                "estrutura incompatível. Nenhum arquivo alterado."
            )

    print("      [OK] hierarchy existente reconhecida.")
else:
    print("      [OK] hierarchy será criada.")


timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backups = {}

print("[5/10] Criando backups...")

for key, path in [
    ("service", SERVICE),
    ("router", ROUTER),
]:
    backup = (
        path.parent
        / f"{path.stem}_backup_fase10b_{timestamp}.py"
    )
    shutil.copy2(path, backup)
    backups[key] = backup
    print(f"      {path.name} -> {backup.name}")


domain_created = False
domain_init_created = False

try:
    print("[6/10] Criando domain/exceptions.py...")

    DOMAIN_DIR.mkdir(parents=True, exist_ok=True)

    if not DOMAIN_INIT.exists():
        DOMAIN_INIT.write_text(
            '"""Camada de domínio do SGI."""\n',
            encoding="utf-8",
        )
        domain_init_created = True

    if not DOMAIN_EXCEPTIONS.exists():
        DOMAIN_EXCEPTIONS.write_text(
            DOMAIN_CONTENT,
            encoding="utf-8",
        )
        domain_created = True

    py_compile.compile(
        str(DOMAIN_EXCEPTIONS),
        doraise=True,
    )

    print("      [OK] hierarchy independente de HTTP.")


    print("[7/10] Migrando services/inventarios.py...")

    patched_service = patch_service(service_text)

    SERVICE.write_text(
        patched_service,
        encoding="utf-8",
    )

    py_compile.compile(
        str(SERVICE),
        doraise=True,
    )

    print(
        "      [OK] 8 HTTPException -> BusinessRuleViolation."
    )


    print("[8/10] Adaptando routers/inventarios.py...")

    patched_router = patch_router(router_text)

    ROUTER.write_text(
        patched_router,
        encoding="utf-8",
    )

    py_compile.compile(
        str(ROUTER),
        doraise=True,
    )

    print(
        "      [OK] BusinessRuleViolation traduzido para HTTP 400."
    )
    print(
        "      [OK] HTTPException legado preservado."
    )


    print("[9/10] Validando comportamento estrutural...")

    final_service = read_text(SERVICE)
    final_router = read_text(ROUTER)

    s2, sd2 = service_state(final_service)
    r2, rd2 = router_state(final_router)

    if s2 != "MIGRADO":
        raise RuntimeError(
            f"Service final inválido: {sd2}"
        )

    if r2 != "MIGRADO":
        raise RuntimeError(
            f"Router final inválido: {rd2}"
        )

    if "fastapi" in final_service.lower():
        raise RuntimeError(
            "services/inventarios.py ainda depende de FastAPI."
        )

    if "HTTPException" in final_service:
        raise RuntimeError(
            "services/inventarios.py ainda contém HTTPException."
        )

    validate_messages(final_service)
    validate_router_phase9(final_router, migrated=True)

    for token in [
        '"INVENTARIO_CRIAR"',
        "status_code=400",
        "detail=str(erro)",
    ]:
        if token not in final_router:
            raise RuntimeError(
                f"Contrato perdido no router: {token}"
            )

    print("      [OK] mesmas mensagens preservadas.")
    print("      [OK] mesmo HTTP 400 preservado.")
    print("      [OK] 1 commit preservado.")
    print(
        "      [OK] 3 caminhos textuais de rollback: "
        "domínio, HTTP legado e erro inesperado."
    )
    print("      [OK] INVENTARIO_CRIAR preservado.")


    print("[10/10] Validando primeiro desacoplamento...")

    if count_raises(
        final_service,
        "BusinessRuleViolation",
    ) != 8:
        raise RuntimeError(
            "Quantidade final de BusinessRuleViolation inesperada."
        )

    print(
        "      [OK] services/inventarios.py não conhece FastAPI."
    )


except Exception:
    print()
    print("[ERRO] Falha durante a Fase 10B.")
    print("[INFO] Restaurando arquivos...")

    shutil.copy2(backups["service"], SERVICE)
    shutil.copy2(backups["router"], ROUTER)

    if domain_created and DOMAIN_EXCEPTIONS.exists():
        DOMAIN_EXCEPTIONS.unlink()

    if domain_init_created and DOMAIN_INIT.exists():
        others = [
            p
            for p in DOMAIN_DIR.glob("*.py")
            if p.name != "__init__.py"
        ]
        if not others:
            DOMAIN_INIT.unlink()

    print("[OK] Estado anterior restaurado.")
    raise


print()
print("[OK] Fase 10B aplicada.")
print("[OK] domain/exceptions.py criado.")
print("[OK] services/inventarios.py desacoplado de FastAPI.")
print("[OK] 8 regras migradas para BusinessRuleViolation.")
print("[OK] routers/inventarios.py mantém HTTP 400.")
print("[OK] compatibilidade com services legados preservada.")
print()
print("PRÓXIMO PASSO:")
print("1. Reinicie a API.")
print(r"2. python tests_e2e\regressao_final_sgi.py")
print(
    r"3. python .\fase10a_auditoria_excecoes_dominio\auditar_fase10a.py"
)
