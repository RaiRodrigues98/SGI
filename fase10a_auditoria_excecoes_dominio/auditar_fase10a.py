"""
FASE 10A - AUDITORIA DE EXCEÇÕES / ACOPLAMENTO HTTP

Somente leitura do código de produção.
Não altera arquivos do SGI e não conecta ao banco.

Objetivos:
1. localizar dependências FastAPI/Starlette dentro de services/domain/application;
2. localizar HTTPException fora dos routers;
3. inventariar ValueError/RuntimeError usados como regra de negócio;
4. detectar hierarquia de exceções já existente;
5. gerar o mapa para a Fase 10B.

Execute na raiz do SGI:

python .\fase10a_auditoria_excecoes_dominio\auditar_fase10a.py
"""

from pathlib import Path
import ast
import sys

ROOT = Path.cwd()

EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "node_modules",
}

EXCLUDED_PREFIXES = tuple(
    [f"fase{i}" for i in range(1, 11)]
)

TARGET_ROOTS = {
    "services",
    "domain",
    "application",
}

HTTP_MODULE_PREFIXES = (
    "fastapi",
    "starlette",
)

GENERIC_RULE_EXCEPTIONS = {
    "ValueError",
    "RuntimeError",
}

def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))

def excluded(path: Path) -> bool:
    parts = path.relative_to(ROOT).parts
    for part in parts:
        low = part.lower()
        if low in EXCLUDED_DIRS:
            return True
        if "_backup_" in low or low.startswith("backup"):
            return True
        if low.startswith(EXCLUDED_PREFIXES):
            return True
    if parts and parts[0].lower() in {"tests", "tests_e2e", "test"}:
        return True
    return False

def production_python_files():
    files = []
    for path in ROOT.rglob("*.py"):
        if not excluded(path):
            files.append(path)
    return sorted(files)

def layer(path: Path) -> str:
    parts = path.relative_to(ROOT).parts
    if not parts:
        return "root"
    return parts[0].lower()

def target_layer(path: Path) -> bool:
    return layer(path) in TARGET_ROOTS

def name_of_exception(expr):
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Call):
        return name_of_exception(expr.func)
    if isinstance(expr, ast.Attribute):
        return expr.attr
    return None

def import_names(tree):
    items = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                items.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = ",".join(alias.name for alias in node.names)
            items.append((module + ":" + names, node.lineno))
    return items

def function_for_line(tree, line):
    best = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            if node.lineno <= line <= end:
                if best is None or node.lineno >= best.lineno:
                    best = node
    return best.name if best else "<módulo>"

def exception_classes(tree):
    result = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(base.attr)
        if any(
            b.endswith("Error")
            or b.endswith("Exception")
            for b in bases
        ):
            result.append({
                "name": node.name,
                "bases": bases,
                "line": node.lineno,
            })
    return result

files = production_python_files()

syntax_errors = []
parsed = {}

for path in files:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="latin-1")
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        syntax_errors.append((path, exc))
        continue
    parsed[path] = (text, tree)

print()
print("=" * 78)
print("FASE 10A - AUDITORIA DE EXCEÇÕES / ACOPLAMENTO HTTP")
print("=" * 78)
print()
print(f"Arquivos Python de produção analisados: {len(files)}")

if syntax_errors:
    print("\n[ERRO] Arquivos com sintaxe inválida:")
    for path, exc in syntax_errors:
        print(f"  - {rel(path)}: {exc}")
    sys.exit(2)

http_imports = []
http_exception_raises = []
http_exception_handlers = []
generic_rule_raises = []
custom_exception_classes = []
target_files = []

for path, (text, tree) in parsed.items():
    if not target_layer(path):
        continue

    target_files.append(path)

    for imported, line in import_names(tree):
        base = imported.split(":", 1)[0]
        if base.startswith(HTTP_MODULE_PREFIXES):
            http_imports.append({
                "path": path,
                "line": line,
                "import": imported,
            })

    for node in ast.walk(tree):
        if isinstance(node, ast.Raise) and node.exc is not None:
            exc_name = name_of_exception(node.exc)
            fn = function_for_line(tree, node.lineno)

            if exc_name == "HTTPException":
                http_exception_raises.append({
                    "path": path,
                    "line": node.lineno,
                    "function": fn,
                })
            elif exc_name in GENERIC_RULE_EXCEPTIONS:
                generic_rule_raises.append({
                    "path": path,
                    "line": node.lineno,
                    "function": fn,
                    "exception": exc_name,
                })

        if isinstance(node, ast.ExceptHandler) and node.type is not None:
            exc_name = name_of_exception(node.type)
            if exc_name == "HTTPException":
                http_exception_handlers.append({
                    "path": path,
                    "line": node.lineno,
                    "function": function_for_line(tree, node.lineno),
                })

    for item in exception_classes(tree):
        custom_exception_classes.append({
            "path": path,
            **item,
        })

print()
print("[1/6] Escopo arquitetural")
print(f"      arquivos em services/domain/application: {len(target_files)}")

for root_name in sorted(TARGET_ROOTS):
    count = sum(1 for p in target_files if layer(p) == root_name)
    print(f"      {root_name}: {count}")

print()
print("[2/6] Dependências HTTP fora dos routers")
print(f"      imports FastAPI/Starlette: {len(http_imports)}")
print(f"      raise HTTPException: {len(http_exception_raises)}")
print(f"      except HTTPException: {len(http_exception_handlers)}")

print()
print("[3/6] Exceções genéricas candidatas a regra de negócio")
print(f"      ValueError/RuntimeError encontrados: {len(generic_rule_raises)}")

by_file = {}
for item in generic_rule_raises:
    key = rel(item["path"])
    by_file.setdefault(key, {"ValueError": 0, "RuntimeError": 0})
    by_file[key][item["exception"]] += 1

for name, counts in sorted(
    by_file.items(),
    key=lambda kv: -(kv[1]["ValueError"] + kv[1]["RuntimeError"])
):
    total = counts["ValueError"] + counts["RuntimeError"]
    print(
        f"      {name}: {total} "
        f"(ValueError={counts['ValueError']}, RuntimeError={counts['RuntimeError']})"
    )

print()
print("[4/6] Hierarquia de exceções já existente")
print(f"      classes customizadas encontradas: {len(custom_exception_classes)}")
for item in custom_exception_classes:
    print(
        f"      {rel(item['path'])}:{item['line']} "
        f"{item['name']}({', '.join(item['bases'])})"
    )

print()
print("[5/6] Bloqueadores HTTP detalhados")

if not http_imports and not http_exception_raises and not http_exception_handlers:
    print("      [OK] Nenhum acoplamento FastAPI/HTTPException em services/domain/application.")
else:
    for item in http_imports:
        print(
            f"      IMPORT  {rel(item['path'])}:{item['line']} -> {item['import']}"
        )
    for item in http_exception_raises:
        print(
            f"      RAISE   {rel(item['path'])}:{item['line']} "
            f"{item['function']} -> HTTPException"
        )
    for item in http_exception_handlers:
        print(
            f"      EXCEPT  {rel(item['path'])}:{item['line']} "
            f"{item['function']} -> HTTPException"
        )

print()
print("[6/6] Resultado")
print()

http_coupling = bool(
    http_imports
    or http_exception_raises
    or http_exception_handlers
)

if http_coupling:
    print("RESULTADO FASE 10A: ACOPLAMENTO HTTP ENCONTRADO")
    print()
    print(
        "A Fase 10B deve criar/usar a hierarquia de exceções "
        "e migrar os pontos HTTP identificados de forma incremental."
    )
else:
    print("RESULTADO FASE 10A: SEM ACOPLAMENTO HTTP DIRETO")
    print()
    print(
        "Services/domain/application já estão livres de FastAPI direto."
    )
    print(
        "A Fase 10B deve focar em substituir ValueError/RuntimeError "
        "de regras de negócio por exceções semânticas próprias."
    )

print()
print("MAPA PARA FASE 10B:")
print(f"  HTTP imports          : {len(http_imports)}")
print(f"  HTTPException raises  : {len(http_exception_raises)}")
print(f"  HTTPException handlers: {len(http_exception_handlers)}")
print(f"  ValueError/RuntimeError: {len(generic_rule_raises)}")
print(f"  Custom exception types: {len(custom_exception_classes)}")
print()
print(
    "Cole esta saída completa na conversa antes da Fase 10B."
)
