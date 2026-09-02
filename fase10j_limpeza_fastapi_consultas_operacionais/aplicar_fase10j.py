
"""
FASE 10J - FECHAMENTO DO DESACOPLAMENTO DE consultas_operacionais

Escopo:
- services/consultas_operacionais.py

Objetivo:
Depois das Fases 10G, 10H e 10I, todos os HTTPException
identificados pela auditoria 10A nesse service devem ter sido
substituídos por exceções semânticas.

A 10J:
1. valida os perfis migrados das funções tratadas;
2. varre o arquivo inteiro via AST;
3. exige ZERO raise HTTPException;
4. exige ZERO except HTTPException;
5. exige que HTTPException apareça somente no import legado;
6. remove `from fastapi import HTTPException`;
7. recompila e valida que o service ficou sem dependência FastAPI.

Não altera router, SQL, UoW, conexão, cursor ou transações.

Execute:
python .\fase10j_limpeza_fastapi_consultas_operacionais\aplicar_fase10j.py
"""

from pathlib import Path
from datetime import datetime
import ast
import py_compile
import shutil

ROOT = Path.cwd()

SERVICE = ROOT / "services" / "consultas_operacionais.py"
DOMAIN = ROOT / "domain" / "exceptions.py"

EXPECTED_DOMAIN_COUNTS = {
    # Fase 10G
    "consultar_inventario": {
        "NotFoundError": 1,
    },
    "consultar_rodada_atual": {
        "NotFoundError": 2,
    },

    # Fase 10H
    "consultar_detalhe_localizacao": {
        "__TOTAL_SEMANTIC__": 5,
    },

    # Fase 10I
    "buscar_produto_contagem": {
        "__TOTAL_SEMANTIC__": 2,
    },
    "validar_lote_contagem": {
        "__TOTAL_SEMANTIC__": 3,
    },
}

SEMANTIC_EXCEPTIONS = {
    "BusinessRuleViolation",
    "NotFoundError",
    "ConflictError",
    "InvalidStateError",
}


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def parse(text, name):
    try:
        return ast.parse(text)
    except SyntaxError as exc:
        raise RuntimeError(
            f"{name}: sintaxe inválida: {exc}"
        )


def raised_name(expr):
    if isinstance(expr, ast.Name):
        return expr.id

    if isinstance(expr, ast.Call):
        return raised_name(expr.func)

    if isinstance(expr, ast.Attribute):
        return expr.attr

    return None


def handler_name(node):
    if node.type is None:
        return None

    if isinstance(node.type, ast.Name):
        return node.type.id

    if isinstance(node.type, ast.Attribute):
        return node.type.attr

    return None


def top_functions(tree):
    return {
        node.name: node
        for node in tree.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    }


def get_function(tree, name):
    functions = top_functions(tree)

    fn = functions.get(name)

    if fn is None:
        raise RuntimeError(
            f"Função esperada ausente: {name}"
        )

    return fn


def direct_raise_names(fn):
    result = []

    for node in ast.walk(fn):
        if not isinstance(node, ast.Raise):
            continue

        if node.exc is None:
            continue

        result.append(
            raised_name(node.exc)
        )

    return result


def validate_phase_profiles(text):
    tree = parse(
        text,
        "services/consultas_operacionais.py",
    )

    diagnostics = {}

    for function_name, expected in EXPECTED_DOMAIN_COUNTS.items():
        fn = get_function(
            tree,
            function_name,
        )

        raises = direct_raise_names(fn)

        http_count = sum(
            1
            for name in raises
            if name == "HTTPException"
        )

        semantic = [
            name
            for name in raises
            if name in SEMANTIC_EXCEPTIONS
        ]

        diagnostics[function_name] = {
            "http": http_count,
            "semantic": semantic,
        }

        if http_count != 0:
            raise RuntimeError(
                f"{function_name}: ainda possui "
                f"{http_count} HTTPException."
            )

        if "__TOTAL_SEMANTIC__" in expected:
            total_expected = expected[
                "__TOTAL_SEMANTIC__"
            ]

            if len(semantic) != total_expected:
                raise RuntimeError(
                    f"{function_name}: esperado "
                    f"{total_expected} raises semânticos, "
                    f"encontrados {len(semantic)}: "
                    f"{semantic}"
                )

        else:
            for exc_name, expected_count in expected.items():
                actual = sum(
                    1
                    for name in semantic
                    if name == exc_name
                )

                if actual != expected_count:
                    raise RuntimeError(
                        f"{function_name}: "
                        f"{exc_name} esperado "
                        f"{expected_count}, encontrado "
                        f"{actual}."
                    )

    return diagnostics


def file_http_usage(text):
    tree = parse(
        text,
        "services/consultas_operacionais.py",
    )

    raises = 0
    handlers = 0
    name_loads = 0
    imports = []

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Raise)
            and
            node.exc is not None
            and
            raised_name(node.exc)
            == "HTTPException"
        ):
            raises += 1

        if (
            isinstance(node, ast.ExceptHandler)
            and
            handler_name(node)
            == "HTTPException"
        ):
            handlers += 1

        if (
            isinstance(node, ast.Name)
            and
            node.id == "HTTPException"
            and
            isinstance(node.ctx, ast.Load)
        ):
            name_loads += 1

    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue

        module = node.module or ""

        if module in {"fastapi", "starlette"} or module.startswith(
            "fastapi."
        ) or module.startswith("starlette."):
            imports.append(
                {
                    "node": node,
                    "module": module,
                    "names": [
                        alias.name
                        for alias in node.names
                    ],
                }
            )

    return {
        "raises": raises,
        "handlers": handlers,
        "name_loads": name_loads,
        "imports": imports,
    }


def classify_state(text):
    usage = file_http_usage(text)

    fastapi_imports = usage["imports"]

    if (
        usage["raises"] == 0
        and
        usage["handlers"] == 0
        and
        usage["name_loads"] == 0
        and
        len(fastapi_imports) == 1
        and
        fastapi_imports[0]["module"] == "fastapi"
        and
        fastapi_imports[0]["names"] == ["HTTPException"]
    ):
        return "PRONTO_PARA_LIMPEZA", usage

    if (
        usage["raises"] == 0
        and
        usage["handlers"] == 0
        and
        usage["name_loads"] == 0
        and
        len(fastapi_imports) == 0
    ):
        return "LIMPO", usage

    return "DESCONHECIDO", usage


def remove_http_import(text):
    tree = parse(
        text,
        "services/consultas_operacionais.py",
    )

    import_node = None

    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue

        if (
            (node.module or "") == "fastapi"
            and
            [alias.name for alias in node.names]
            == ["HTTPException"]
        ):
            import_node = node
            break

    if import_node is None:
        raise RuntimeError(
            "Import legado exato "
            "`from fastapi import HTTPException` "
            "não foi encontrado via AST."
        )

    lines = text.splitlines()

    start = import_node.lineno
    end = import_node.end_lineno

    result_lines = (
        lines[: start - 1]
        + lines[end:]
    )

    # Remove no máximo uma linha vazia excedente no início,
    # sem reformatar o restante do arquivo.
    while (
        len(result_lines) >= 2
        and
        result_lines[0] == ""
        and
        result_lines[1] == ""
    ):
        result_lines.pop(0)

    result = "\n".join(result_lines)

    if text.endswith("\n"):
        result += "\n"

    return result


print(
    "[0/9] Validando arquivos..."
)

for path in [
    SERVICE,
    DOMAIN,
]:
    if not path.exists():
        raise SystemExit(
            f"[ERRO] Arquivo ausente: {path}"
        )

domain_text = read_text(DOMAIN)

for token in [
    "class BusinessRuleViolation(DomainError)",
    "class NotFoundError(DomainError)",
    "class ConflictError(DomainError)",
]:
    if token not in domain_text:
        raise SystemExit(
            "[ERRO] Hierarquia de domínio incompleta: "
            f"{token}"
        )

print(
    "      [OK] arquivos e hierarchy reconhecidos."
)


print(
    "[1/9] Validando perfis 10G/10H/10I..."
)

service_text = read_text(SERVICE)

try:
    profiles = validate_phase_profiles(
        service_text
    )
except Exception as exc:
    raise SystemExit(
        "[ERRO] Pré-requisitos 10G/10H/10I "
        f"não reconhecidos: {exc}"
    )

for function_name, info in profiles.items():
    print(
        f"      {function_name}: "
        f"HTTP={info['http']} "
        f"semantic={info['semantic']}"
    )

print(
    "      [OK] funções migradas reconhecidas."
)


print(
    "[2/9] Auditando HTTPException no arquivo inteiro..."
)

state, usage = classify_state(
    service_text
)

print(
    f"      Estado: {state}"
)
print(
    f"      raise HTTPException: {usage['raises']}"
)
print(
    f"      except HTTPException: {usage['handlers']}"
)
print(
    f"      usos HTTPException em expressão: "
    f"{usage['name_loads']}"
)
print(
    f"      imports FastAPI/Starlette: "
    f"{len(usage['imports'])}"
)

for item in usage["imports"]:
    print(
        f"        - {item['module']}: "
        f"{item['names']}"
    )

if state == "LIMPO":
    print(
        "[3/9] Fase 10J já aplicada."
    )
    print(
        "      [OK] services/consultas_operacionais.py "
        "já não depende de FastAPI."
    )
    raise SystemExit(0)

if state != "PRONTO_PARA_LIMPEZA":
    print()
    print(
        "[ERRO] O service ainda não está seguro "
        "para remoção do import."
    )
    print(
        "[INFO] Nenhum arquivo foi alterado."
    )
    raise SystemExit(1)

print(
    "      [OK] HTTPException existe somente "
    "como import legado não utilizado."
)


print(
    "[3/9] Confirmando ausência de FastAPI funcional..."
)

if (
    usage["raises"] != 0
    or
    usage["handlers"] != 0
    or
    usage["name_loads"] != 0
):
    raise SystemExit(
        "[ERRO] Uso funcional de HTTPException detectado."
    )

print(
    "      [OK] nenhuma regra depende de HTTPException."
)


print(
    "[4/9] Criando backup..."
)

timestamp = (
    datetime.now()
    .strftime("%Y%m%d_%H%M%S")
)

backup = (
    SERVICE.parent
    / (
        SERVICE.stem
        + "_backup_fase10j_"
        + timestamp
        + ".py"
    )
)

shutil.copy2(
    SERVICE,
    backup,
)

print(
    f"      {SERVICE.name} -> {backup.name}"
)


try:
    print(
        "[5/9] Removendo import FastAPI..."
    )

    patched = remove_http_import(
        service_text
    )

    SERVICE.write_text(
        patched,
        encoding="utf-8",
    )

    print(
        "      [OK] import removido."
    )


    print(
        "[6/9] Validando sintaxe..."
    )

    py_compile.compile(
        str(SERVICE),
        doraise=True,
    )

    print(
        "      [OK] compilação concluída."
    )


    print(
        "[7/9] Reauditando dependências HTTP..."
    )

    final_text = read_text(
        SERVICE
    )

    final_state, final_usage = classify_state(
        final_text
    )

    print(
        f"      Estado final: {final_state}"
    )
    print(
        f"      raise HTTPException: "
        f"{final_usage['raises']}"
    )
    print(
        f"      except HTTPException: "
        f"{final_usage['handlers']}"
    )
    print(
        f"      imports FastAPI/Starlette: "
        f"{len(final_usage['imports'])}"
    )

    if final_state != "LIMPO":
        raise RuntimeError(
            "Service ainda possui dependência HTTP: "
            f"{final_usage}"
        )


    print(
        "[8/9] Revalidando perfis semânticos..."
    )

    final_profiles = validate_phase_profiles(
        final_text
    )

    if final_profiles != profiles:
        raise RuntimeError(
            "Perfis semânticos mudaram durante a limpeza."
        )

    print(
        "      [OK] exceções semânticas inalteradas."
    )


    print(
        "[9/9] Validando escopo da alteração..."
    )

    before_without_import = remove_http_import(
        service_text
    )

    if final_text != before_without_import:
        raise RuntimeError(
            "Conteúdo além do import foi alterado."
        )

    print(
        "      [OK] única alteração funcional: "
        "remoção do import FastAPI."
    )


except Exception:
    print()
    print(
        "[ERRO] Falha durante a Fase 10J."
    )
    print(
        "[INFO] Restaurando arquivo original..."
    )

    shutil.copy2(
        backup,
        SERVICE,
    )

    print(
        "[OK] Estado anterior restaurado."
    )

    raise


print()
print(
    "[OK] Fase 10J aplicada."
)
print(
    "[OK] services/consultas_operacionais.py "
    "sem dependência FastAPI/Starlette."
)
print(
    "[OK] 0 raise HTTPException."
)
print(
    "[OK] 0 except HTTPException."
)
print(
    "[OK] regras semânticas das Fases "
    "10G/10H/10I preservadas."
)
print(
    "[OK] nenhuma alteração em router, SQL "
    "ou transações."
)
print()
print(
    "PRÓXIMO PASSO:"
)
print(
    "1. Reinicie a API."
)
print(
    r"2. python tests_e2e\regressao_final_sgi.py"
)
print(
    r"3. python .\fase10a_auditoria_excecoes_dominio\auditar_fase10a.py"
)
