"""
FASE 9H v2 - AUDITORIA FINAL CORRIGIDA DA CAMADA TRANSACIONAL

Correções em relação à v1:
1. cursor.execute(...) NÃO é mais confundido com SQL EXEC/EXECUTE.
   O auditor lê a string SQL real enviada ao cursor.
2. Routers que delegam conn/cursor para services com commit/rollback
   são reconhecidos como "service-owned".
3. Se um router service-owned ainda usar get_connection(), ele bloqueia.
4. Se já usa SqlServerUnitOfWork e o service continua dono da transação,
   ele é considerado válido.

Esta etapa é SOMENTE LEITURA:
- não altera arquivos;
- não cria backup;
- não executa SQL;
- não conecta ao banco.

Execute na raiz do SGI:

python .\fase9h_v2_auditoria_final_transacoes\auditar_fase9h_v2.py
"""

from pathlib import Path
import ast
import re
import sys

ROOT = Path.cwd()

EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
}

EXCLUDED_PREFIXES = (
    "fase1",
    "fase2",
    "fase3",
    "fase4",
    "fase5",
    "fase6",
    "fase7",
    "fase8",
    "fase9",
)

EXPECTED_UOW_ROUTERS = [
    ROOT / "routers" / "analise.py",
    ROOT / "routers" / "rotativo_ciclos.py",
    ROOT / "routers" / "rotativo_cobertura.py",
    ROOT / "routers" / "rotativo_fluxo.py",
    ROOT / "routers" / "rotativo_priorizacao.py",
]

WRITE_KINDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "MERGE",
    "TRUNCATE",
    "CREATE",
    "ALTER",
    "DROP",
    "EXEC",
    "EXECUTE",
}

READ_KINDS = {
    "SELECT",
}

SQL_TOKEN_RE = re.compile(
    r"\b("
    r"SELECT|INSERT|UPDATE|DELETE|MERGE|TRUNCATE|"
    r"CREATE|ALTER|DROP|EXECUTE|EXEC"
    r")\b",
    re.IGNORECASE,
)


def is_excluded(path: Path) -> bool:

    rel = path.relative_to(ROOT)

    for part in rel.parts:

        low = part.lower()

        if low in EXCLUDED_DIR_NAMES:
            return True

        if low.startswith("backup"):
            return True

        if "_backup_" in low:
            return True

        if low.startswith(EXCLUDED_PREFIXES):
            return True

    if rel.parts and rel.parts[0].lower() in {
        "tests",
        "tests_e2e",
        "test",
    }:
        return True

    return False


def read_text(path: Path) -> str:

    try:
        return path.read_text(
            encoding="utf-8"
        )
    except UnicodeDecodeError:
        return path.read_text(
            encoding="latin-1"
        )


def python_files():

    result = []

    for path in ROOT.rglob("*.py"):

        if is_excluded(path):
            continue

        result.append(path)

    return sorted(result)


def rel(path: Path):

    return str(
        path.relative_to(ROOT)
    )


def is_router(path: Path):

    parts = [
        item.lower()
        for item in path.relative_to(ROOT).parts
    ]

    return (
        len(parts) >= 2
        and
        parts[0] == "routers"
    )


def is_service(path: Path):

    parts = [
        item.lower()
        for item in path.relative_to(ROOT).parts
    ]

    return (
        len(parts) >= 2
        and
        parts[0] == "services"
    )


def is_infrastructure(path: Path):

    parts = [
        item.lower()
        for item in path.relative_to(ROOT).parts
    ]

    return (
        "infrastructure" in parts
        or
        (
            len(parts) >= 1
            and
            parts[0] in {
                "database",
                "db",
            }
        )
    )


def strip_sql_comments(sql: str) -> str:

    # Remove /* ... */
    sql = re.sub(
        r"/\*.*?\*/",
        " ",
        sql,
        flags=re.DOTALL,
    )

    # Remove -- ...
    sql = re.sub(
        r"--[^\n\r]*",
        " ",
        sql,
    )

    return sql.strip()


def sql_kind(sql: str) -> str:

    cleaned = strip_sql_comments(
        sql
    )

    if not cleaned:
        return "EMPTY"

    match = SQL_TOKEN_RE.search(
        cleaned
    )

    if not match:
        return "UNKNOWN"

    return match.group(1).upper()


def constant_string(node):

    if isinstance(node, ast.Constant):

        if isinstance(
            node.value,
            str,
        ):
            return node.value

    if isinstance(node, ast.JoinedStr):
        # SQL construído com f-string é dinâmico.
        return None

    return None


def is_cursor_execute_call(node):

    return (
        isinstance(node, ast.Call)
        and
        isinstance(
            node.func,
            ast.Attribute,
        )
        and
        node.func.attr in {
            "execute",
            "executemany",
        }
        and
        isinstance(
            node.func.value,
            ast.Name,
        )
        and
        node.func.value.id == "cursor"
    )


def sql_usage_in_function(
    fn_node
):

    usages = []

    for node in ast.walk(
        fn_node
    ):

        if not is_cursor_execute_call(
            node
        ):
            continue

        if not node.args:

            usages.append(
                {
                    "line":
                        node.lineno,

                    "kind":
                        "DYNAMIC",

                    "sql":
                        None,
                }
            )
            continue

        sql = constant_string(
            node.args[0]
        )

        if sql is None:

            usages.append(
                {
                    "line":
                        node.lineno,

                    "kind":
                        "DYNAMIC",

                    "sql":
                        None,
                }
            )
            continue

        usages.append(
            {
                "line":
                    node.lineno,

                "kind":
                    sql_kind(
                        sql
                    ),

                "sql":
                    sql,
            }
        )

    return usages


def function_nodes(
    tree
):

    return [
        node
        for node in tree.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    ]


def count_call(
    fn_node,
    object_name,
    method_name
):

    total = 0

    for node in ast.walk(
        fn_node
    ):

        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if not isinstance(
            node.func,
            ast.Attribute,
        ):
            continue

        if (
            node.func.attr
            != method_name
        ):
            continue

        if not isinstance(
            node.func.value,
            ast.Name,
        ):
            continue

        if (
            node.func.value.id
            != object_name
        ):
            continue

        total += 1

    return total


def count_named_call(
    fn_node,
    name
):

    total = 0

    for node in ast.walk(
        fn_node
    ):

        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if (
            isinstance(
                node.func,
                ast.Name,
            )
            and
            node.func.id == name
        ):
            total += 1

    return total


def service_import_map(
    tree
):

    """
    Retorna:
    local_name -> (module, original_name)
    """

    result = {}

    for node in tree.body:

        if not isinstance(
            node,
            ast.ImportFrom,
        ):
            continue

        module = (
            node.module
            or ""
        )

        if not module.startswith(
            "services."
        ):
            continue

        for alias in node.names:

            local = (
                alias.asname
                or
                alias.name
            )

            result[
                local
            ] = (
                module,
                alias.name,
            )

    return result


def module_to_service_path(
    module
):

    # services.foo.bar -> services/foo/bar.py
    parts = module.split(".")

    path = (
        ROOT
        / Path(
            *parts
        )
    ).with_suffix(
        ".py"
    )

    return path


def analyze_service_file(
    path
):

    text = read_text(
        path
    )

    tree = ast.parse(
        text
    )

    result = {}

    for fn in function_nodes(
        tree
    ):

        conn_commit = count_call(
            fn,
            "conn",
            "commit",
        )

        conn_rollback = count_call(
            fn,
            "conn",
            "rollback",
        )

        uow_commit = count_call(
            fn,
            "uow",
            "commit",
        )

        uow_rollback = count_call(
            fn,
            "uow",
            "rollback",
        )

        result[
            fn.name
        ] = {
            "commits":
                conn_commit
                + uow_commit,

            "rollbacks":
                conn_rollback
                + uow_rollback,
        }

    return result


def build_service_index(
    files
):

    index = {}

    for path in files:

        if not is_service(
            path
        ):
            continue

        try:

            data = analyze_service_file(
                path
            )

        except SyntaxError:
            continue

        # services/foo.py -> services.foo
        relative = (
            path.relative_to(ROOT)
            .with_suffix("")
        )

        module = ".".join(
            relative.parts
        )

        index[
            module
        ] = data

    return index


def service_calls_in_router_function(
    fn_node,
    imports,
    service_index
):

    calls = []

    for node in ast.walk(
        fn_node
    ):

        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if not isinstance(
            node.func,
            ast.Name,
        ):
            continue

        local_name = (
            node.func.id
        )

        if (
            local_name
            not in imports
        ):
            continue

        (
            module,
            original_name,
        ) = imports[
            local_name
        ]

        service_data = (
            service_index
            .get(
                module,
                {}
            )
            .get(
                original_name
            )
        )

        # Confirma se conn/cursor são realmente passados.
        passes_conn = False
        passes_cursor = False

        for keyword in node.keywords:

            if (
                keyword.arg == "conn"
                and
                isinstance(
                    keyword.value,
                    ast.Name,
                )
                and
                keyword.value.id == "conn"
            ):
                passes_conn = True

            if (
                keyword.arg == "cursor"
                and
                isinstance(
                    keyword.value,
                    ast.Name,
                )
                and
                keyword.value.id == "cursor"
            ):
                passes_cursor = True

        if not (
            passes_conn
            or
            passes_cursor
        ):
            # Não classificamos como delegação
            # transacional sem passagem explícita.
            continue

        calls.append(
            {
                "line":
                    node.lineno,

                "local_name":
                    local_name,

                "module":
                    module,

                "function":
                    original_name,

                "passes_conn":
                    passes_conn,

                "passes_cursor":
                    passes_cursor,

                "service_data":
                    service_data,
            }
        )

    return calls


def router_function_info(
    fn_node,
    imports,
    service_index
):

    legacy_conn = count_named_call(
        fn_node,
        "get_connection",
    )

    uow_ctor = count_named_call(
        fn_node,
        "SqlServerUnitOfWork",
    )

    router_commits = (
        count_call(
            fn_node,
            "conn",
            "commit",
        )
        +
        count_call(
            fn_node,
            "uow",
            "commit",
        )
    )

    router_rollbacks = (
        count_call(
            fn_node,
            "conn",
            "rollback",
        )
        +
        count_call(
            fn_node,
            "uow",
            "rollback",
        )
    )

    sql_usages = (
        sql_usage_in_function(
            fn_node
        )
    )

    write_sql = [
        usage
        for usage in sql_usages
        if usage["kind"]
        in WRITE_KINDS
    ]

    dynamic_sql = [
        usage
        for usage in sql_usages
        if usage["kind"]
        == "DYNAMIC"
    ]

    read_sql = [
        usage
        for usage in sql_usages
        if usage["kind"]
        in READ_KINDS
    ]

    delegated_calls = (
        service_calls_in_router_function(
            fn_node,
            imports,
            service_index,
        )
    )

    delegated_transactional = [
        call
        for call in delegated_calls
        if (
            call["service_data"]
            and
            (
                call[
                    "service_data"
                ][
                    "commits"
                ]
                > 0
                or
                call[
                    "service_data"
                ][
                    "rollbacks"
                ]
                > 0
            )
        )
    ]

    delegated_unknown = [
        call
        for call in delegated_calls
        if (
            call["service_data"]
            is None
        )
    ]

    return {
        "legacy_conn":
            legacy_conn,

        "uow_ctor":
            uow_ctor,

        "router_commits":
            router_commits,

        "router_rollbacks":
            router_rollbacks,

        "write_sql":
            write_sql,

        "dynamic_sql":
            dynamic_sql,

        "read_sql":
            read_sql,

        "delegated_transactional":
            delegated_transactional,

        "delegated_unknown":
            delegated_unknown,
    }


print()
print("=" * 78)
print("FASE 9H v2 - AUDITORIA FINAL CORRIGIDA")
print("=" * 78)
print()

files = python_files()

if not files:

    raise SystemExit(
        "[ERRO] Nenhum arquivo Python "
        "de produção encontrado."
    )

print(
    f"Arquivos Python analisados: "
    f"{len(files)}"
)
print()


# ============================================================
# SINTAXE
# ============================================================

print(
    "[1/9] Validando sintaxe dos arquivos..."
)

syntax_errors = []

parsed = {}

for path in files:

    text = read_text(
        path
    )

    try:

        tree = ast.parse(
            text
        )

    except SyntaxError as exc:

        syntax_errors.append(
            (
                path,
                exc,
            )
        )

        continue

    parsed[
        path
    ] = (
        text,
        tree,
    )


if syntax_errors:

    for path, exc in syntax_errors:

        print(
            f"      [ERRO] "
            f"{rel(path)}: "
            f"{exc}"
        )

    raise SystemExit(
        "Auditoria abortada por "
        "erro de sintaxe."
    )

print(
    "      [OK] sintaxe válida."
)
print()


# ============================================================
# ÍNDICE DOS SERVICES
# ============================================================

print(
    "[2/9] Mapeando ownership "
    "transacional nos services..."
)

service_index = (
    build_service_index(
        files
    )
)

service_owners = []

for module, functions in (
    service_index.items()
):

    for fn_name, data in (
        functions.items()
    ):

        if (
            data["commits"] > 0
            or
            data["rollbacks"] > 0
        ):

            service_owners.append(
                {
                    "module":
                        module,

                    "function":
                        fn_name,

                    "commits":
                        data["commits"],

                    "rollbacks":
                        data["rollbacks"],
                }
            )


print(
    "      services/funções com "
    "commit ou rollback explícito: "
    f"{len(service_owners)}"
)
print()


# ============================================================
# ROUTERS
# ============================================================

print(
    "[3/9] Auditando routers..."
)

blockers = []
legacy_reads = []
uow_router_owned = []
uow_service_owned = []
uow_reads = []
dynamic_reviews = []
unknown_service_reviews = []

for path, (
    text,
    tree,
) in parsed.items():

    if not is_router(
        path
    ):
        continue

    imports = service_import_map(
        tree
    )

    for fn in function_nodes(
        tree
    ):

        info = router_function_info(
            fn,
            imports,
            service_index,
        )

        has_connection = (
            info["legacy_conn"] > 0
            or
            info["uow_ctor"] > 0
        )

        if not has_connection:
            continue

        item = {
            "path":
                path,

            "function":
                fn.name,

            "line":
                fn.lineno,

            **info,
        }

        legacy = (
            info["legacy_conn"] > 0
        )

        uow = (
            info["uow_ctor"] > 0
        )

        router_tx = (
            info["router_commits"] > 0
            or
            info["router_rollbacks"] > 0
        )

        direct_write = (
            len(
                info["write_sql"]
            )
            > 0
        )

        delegated_tx = (
            len(
                info[
                    "delegated_transactional"
                ]
            )
            > 0
        )

        if info["dynamic_sql"]:

            dynamic_reviews.append(
                item
            )

        if info["delegated_unknown"]:

            unknown_service_reviews.append(
                item
            )

        if legacy:

            if (
                router_tx
                or
                direct_write
                or
                delegated_tx
            ):

                blockers.append(
                    item
                )

            else:

                legacy_reads.append(
                    item
                )

        elif uow:

            if router_tx:

                uow_router_owned.append(
                    item
                )

            elif delegated_tx:

                uow_service_owned.append(
                    item
                )

            else:

                uow_reads.append(
                    item
                )


print(
    "      blockers legados reais: "
    f"{len(blockers)}"
)

print(
    "      leituras legadas permitidas: "
    f"{len(legacy_reads)}"
)

print(
    "      UoW com transação no router: "
    f"{len(uow_router_owned)}"
)

print(
    "      UoW com transação delegada ao service: "
    f"{len(uow_service_owned)}"
)

print(
    "      UoW somente leitura: "
    f"{len(uow_reads)}"
)
print()


# ============================================================
# EXPECTED UOW APÓS 9I/9J
# ============================================================

print(
    "[4/9] Validando Fases 9I/9J..."
)

phase_blockers = []

for path in EXPECTED_UOW_ROUTERS:

    if not path.exists():

        phase_blockers.append(
            (
                path,
                "arquivo ausente",
            )
        )

        print(
            f"      [ERRO] "
            f"{rel(path)} ausente."
        )

        continue

    text = read_text(
        path
    )

    has_uow = (
        "SqlServerUnitOfWork"
        in text
    )

    has_legacy = (
        "get_connection()"
        in text
    )

    if (
        not has_uow
        or
        has_legacy
    ):

        phase_blockers.append(
            (
                path,
                "UoW não consolidado",
            )
        )

        print(
            f"      [ERRO] "
            f"{rel(path)} ainda não "
            "está consolidado em UoW."
        )

    else:

        print(
            f"      [OK] "
            f"{rel(path)}"
        )

print()


# ============================================================
# COMMIT/ROLLBACK FORA DAS CAMADAS
# ============================================================

print(
    "[5/9] Procurando transações "
    "em camadas inesperadas..."
)

unexpected_tx = []

for path, (
    text,
    tree,
) in parsed.items():

    if (
        is_router(path)
        or
        is_service(path)
        or
        is_infrastructure(path)
    ):
        continue

    has_tx = False

    for fn in function_nodes(
        tree
    ):

        if (
            count_call(
                fn,
                "conn",
                "commit",
            )
            or
            count_call(
                fn,
                "conn",
                "rollback",
            )
            or
            count_call(
                fn,
                "uow",
                "commit",
            )
            or
            count_call(
                fn,
                "uow",
                "rollback",
            )
        ):

            has_tx = True
            break

    if has_tx:

        unexpected_tx.append(
            path
        )


print(
    "      arquivos inesperados: "
    f"{len(unexpected_tx)}"
)
print()


# ============================================================
# MAIN.PY
# ============================================================

print(
    "[6/9] Verificando main.py..."
)

main_blocker = False

main_path = (
    ROOT
    / "main.py"
)

if main_path.exists():

    main_text = read_text(
        main_path
    )

    main_tree = ast.parse(
        main_text
    )

    for fn in function_nodes(
        main_tree
    ):

        legacy_conn = count_named_call(
            fn,
            "get_connection",
        )

        if legacy_conn <= 0:
            continue

        usages = sql_usage_in_function(
            fn
        )

        writes = [
            usage
            for usage in usages
            if usage["kind"]
            in WRITE_KINDS
        ]

        if writes:

            main_blocker = True

            print(
                f"      [ERRO] "
                f"main.py/{fn.name} "
                "usa conexão direta "
                "com SQL de escrita."
            )

        else:

            print(
                f"      [OK] "
                f"main.py/{fn.name}: "
                "conexão direta somente leitura."
            )

    if "get_connection()" not in main_text:

        print(
            "      [OK] main.py "
            "sem get_connection()."
        )

else:

    print(
        "      main.py não encontrado."
    )

print()


# ============================================================
# RELATÓRIO DETALHADO
# ============================================================

print(
    "[7/9] Relatório detalhado"
)
print()


if blockers:

    print(
        "BLOQUEADORES - ROUTERS LEGADOS "
        "COM TRANSAÇÃO/ESCRITA REAL"
    )

    for item in blockers:

        reasons = []

        if (
            item["router_commits"]
            or
            item["router_rollbacks"]
        ):

            reasons.append(
                "router_commit_rollback"
            )

        if item["write_sql"]:

            kinds = sorted(
                {
                    usage["kind"]
                    for usage
                    in item["write_sql"]
                }
            )

            reasons.append(
                "sql="
                + ",".join(
                    kinds
                )
            )

        if item[
            "delegated_transactional"
        ]:

            service_names = [
                (
                    call["module"]
                    + "."
                    + call["function"]
                )
                for call
                in item[
                    "delegated_transactional"
                ]
            ]

            reasons.append(
                "service_tx="
                + ",".join(
                    service_names
                )
            )

        print(
            "  - "
            f"{rel(item['path'])}:"
            f"{item['line']} "
            f"{item['function']} | "
            + " | ".join(
                reasons
            )
        )

    print()


if legacy_reads:

    print(
        "LEITURAS LEGADAS PERMITIDAS "
        "NESTA FASE"
    )

    for item in legacy_reads:

        print(
            "  - "
            f"{rel(item['path'])}:"
            f"{item['line']} "
            f"{item['function']}"
        )

    print()


if uow_service_owned:

    print(
        "UOW COM OWNERSHIP "
        "TRANSACIONAL DELEGADO AO SERVICE"
    )

    for item in uow_service_owned:

        services = [
            (
                call["module"]
                + "."
                + call["function"]
            )
            for call
            in item[
                "delegated_transactional"
            ]
        ]

        print(
            "  - "
            f"{rel(item['path'])}:"
            f"{item['line']} "
            f"{item['function']} -> "
            + ", ".join(
                services
            )
        )

    print()


if service_owners:

    print(
        "OWNERSHIP TRANSACIONAL "
        "INTENCIONAL EM SERVICES"
    )

    for item in service_owners:

        print(
            "  - "
            f"{item['module']}."
            f"{item['function']} | "
            f"commit={item['commits']} | "
            f"rollback={item['rollbacks']}"
        )

    print()


if dynamic_reviews:

    print(
        "SQL DINÂMICO - REVISÃO INFORMATIVA"
    )

    for item in dynamic_reviews:

        print(
            "  - "
            f"{rel(item['path'])}:"
            f"{item['line']} "
            f"{item['function']}"
        )

    print(
        "  O auditor não classifica SQL "
        "dinâmico como escrita automaticamente."
    )
    print()


if unknown_service_reviews:

    print(
        "DELEGAÇÕES PARA SERVICE "
        "NÃO RESOLVIDAS ESTATICAMENTE"
    )

    for item in unknown_service_reviews:

        print(
            "  - "
            f"{rel(item['path'])}:"
            f"{item['line']} "
            f"{item['function']}"
        )

    print()


if unexpected_tx:

    print(
        "TRANSAÇÕES FORA DAS CAMADAS "
        "ESPERADAS"
    )

    for path in unexpected_tx:

        print(
            f"  - {rel(path)}"
        )

    print()


# ============================================================
# VALIDAÇÃO DO BUG DA v1
# ============================================================

print(
    "[8/9] Confirmando correções da auditoria v1..."
)

analise_path = (
    ROOT
    / "routers"
    / "analise.py"
)

if analise_path.exists():

    text = read_text(
        analise_path
    )

    tree = ast.parse(
        text
    )

    analise_writes = []

    for fn in function_nodes(
        tree
    ):

        if fn.name not in {
            "analisar_sessao",
            "analisar_rodada",
            "consultar_analise_rotativo",
        }:
            continue

        usages = sql_usage_in_function(
            fn
        )

        for usage in usages:

            if (
                usage["kind"]
                in WRITE_KINDS
            ):

                analise_writes.append(
                    (
                        fn.name,
                        usage,
                    )
                )

    if analise_writes:

        print(
            "      [ATENÇÃO] "
            "analise.py contém SQL real "
            "de escrita:"
        )

        for fn_name, usage in (
            analise_writes
        ):

            print(
                f"        {fn_name}: "
                f"{usage['kind']} "
                f"linha {usage['line']}"
            )

    else:

        print(
            "      [OK] cursor.execute() "
            "de analise.py não foi "
            "confundido com SQL EXECUTE."
        )

else:

    print(
        "      analise.py não encontrado."
    )

delegated_detected = (
    len(
        uow_service_owned
    )
    > 0
)

if delegated_detected:

    print(
        "      [OK] ownership delegado "
        "a service foi detectado."
    )

else:

    print(
        "      [INFO] nenhum router UoW "
        "service-owned foi detectado."
    )

print()


# ============================================================
# RESULTADO
# ============================================================

print(
    "[9/9] Resultado"
)
print()

blocking = (
    bool(blockers)
    or
    bool(phase_blockers)
    or
    bool(unexpected_tx)
    or
    main_blocker
)


if blocking:

    print(
        "RESULTADO FASE 9H v2: "
        "PENDÊNCIAS ENCONTRADAS"
    )

    print()

    if phase_blockers:

        print(
            "Fases 9I/9J ainda não "
            "estão consolidadas em todos "
            "os arquivos esperados."
        )

    if blockers:

        print(
            "Ainda existem routers legados "
            "com escrita/transação real."
        )

    if unexpected_tx:

        print(
            "Existem transações em camada "
            "inesperada."
        )

    if main_blocker:

        print(
            "main.py possui escrita com "
            "conexão direta."
        )

    print()
    print(
        "A Fase 9 NÃO deve ser "
        "encerrada ainda."
    )

    sys.exit(1)


print(
    "RESULTADO FASE 9H v2: APROVADO"
)

print()
print(
    "Critérios atendidos:"
)

print(
    "  [OK] nenhum router legado "
    "remanescente controla escrita/transação;"
)

print(
    "  [OK] cursor.execute() é analisado "
    "pela string SQL real;"
)

print(
    "  [OK] routers service-owned usam "
    "UoW sem assumir commit/rollback;"
)

print(
    "  [OK] ownership transacional "
    "intencional em services foi identificado;"
)

print(
    "  [OK] nenhuma transação inesperada "
    "fora das camadas previstas;"
)

print(
    "  [OK] Fases 9I/9J reconhecidas."
)

print()
print(
    "FASE 9 - UNIT OF WORK / TRANSAÇÕES:"
)

print(
    "APTA PARA ENCERRAMENTO, condicionada "
    "à regressão final do SGI permanecer verde."
)

print()
print(
    "PRÓXIMO PASSO:"
)

print(
    r"python tests_e2e\regressao_final_sgi.py"
)
