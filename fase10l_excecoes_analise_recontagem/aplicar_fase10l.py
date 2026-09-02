
"""
FASE 10L - DESACOPLAMENTO HTTP DE analise_recontagem

Alvo:
- services/analise_recontagem.py
- analisar_recontagem_oficial()

Estratégia adaptativa:
- lê o arquivo LOCAL REAL;
- exige que TODO raise HTTPException do arquivo esteja dentro de
  analisar_recontagem_oficial;
- aceita somente HTTP 400 e 404;
- converte:
    400 -> BusinessRuleViolation
    404 -> NotFoundError
- preserva cada detail via AST;
- remove FastAPI somente se não restar nenhum uso HTTP;
- constrói grafo de chamadas cross-module;
- rastreia consumers transitivos até routers;
- bloqueia service intermediário que transforme Exception em HTTPException;
- adapta todas as fronteiras HTTP reconhecidas;
- replica rollback/log do except HTTPException do router nos novos handlers.

Não altera SQL, regras de recontagem, services intermediários,
commits, abertura/fechamento de conexão, rotas ou retornos de sucesso.

Execute:
python .\\fase10l_excecoes_analise_recontagem\\aplicar_fase10l.py
"""

from pathlib import Path
from datetime import datetime
import ast
import py_compile
import shutil

ROOT = Path.cwd()
SERVICE = ROOT / 'services' / 'analise_recontagem.py'
DOMAIN = ROOT / 'domain' / 'exceptions.py'
PREV = ROOT / 'services' / 'analise_gestor.py'

TARGET_MODULE = 'services.analise_recontagem'
TARGET_FUNCTION = 'analisar_recontagem_oficial'
TARGET_NODE = (TARGET_MODULE, TARGET_FUNCTION)

EXC_BY_STATUS = {
    400: 'BusinessRuleViolation',
    404: 'NotFoundError',
}
STATUS_BY_EXC = {v: k for k, v in EXC_BY_STATUS.items()}

# A 10A inicial apontou 5 raises; uma cópia preservada na Library possui 4.
# O arquivo local é a autoridade, mas restringimos o perfil a um intervalo
# estreito e somente 400/404 para evitar migração ampla acidental.
MIN_HTTP_RAISES = 4
MAX_HTTP_RAISES = 5

EXCLUDED_DIRS = {
    '.git', '.venv', 'venv', '__pycache__', '.pytest_cache',
    '.mypy_cache', '.ruff_cache', 'node_modules',
}
EXCLUDED_PREFIXES = tuple(f'fase{i}' for i in range(1, 11))

# Rollback não entra aqui porque os novos handlers precisam replicá-lo.
PROTECTED_EXACT_TOKENS = [
    'get_connection()',
    'SqlServerUnitOfWork()',
    'uow.open()',
    'conn.cursor()',
    'uow.cursor',
    'cursor.close()',
    'conn.close()',
    'uow.close()',
    'conn.commit()',
    'uow.commit()',
]


def read_text(path):
    try:
        return path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        return path.read_text(encoding='latin-1')


def parse(text, name):
    try:
        return ast.parse(text)
    except SyntaxError as exc:
        raise RuntimeError(f'{name}: sintaxe inválida: {exc}')


def is_excluded(path):
    rel = path.relative_to(ROOT)
    for part in rel.parts:
        low = part.lower()
        if low in EXCLUDED_DIRS:
            return True
        if '_backup_' in low or low.startswith('backup'):
            return True
        if low.startswith(EXCLUDED_PREFIXES):
            return True
    if rel.parts and rel.parts[0].lower() in {'tests', 'tests_e2e', 'test'}:
        return True
    return False


def production_files():
    return sorted(p for p in ROOT.rglob('*.py') if not is_excluded(p))


def module_name_from_path(path):
    return '.'.join(path.relative_to(ROOT).with_suffix('').parts)


def package_of_module(module_name):
    return module_name.split('.')[:-1]


def resolve_import_module(current_module, node):
    module = node.module or ''
    if node.level == 0:
        return module
    package = package_of_module(current_module)
    ascend = node.level - 1
    if ascend > len(package):
        return None
    base = package[:len(package) - ascend]
    if module:
        base += module.split('.')
    return '.'.join(base)


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
        n.name: n for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def top_import_map(tree, module_name):
    result = {}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        resolved = resolve_import_module(module_name, node)
        if not resolved:
            continue
        for alias in node.names:
            if alias.name == '*':
                continue
            result[alias.asname or alias.name] = (resolved, alias.name)
    return result


def unsupported_target_module_imports(tree):
    result = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Import):
            continue
        for alias in node.names:
            if alias.name == TARGET_MODULE or alias.name.startswith(TARGET_MODULE + '.'):
                result.append((alias.name, node.lineno))
    return result


def call_names(fn):
    result = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            result.add(node.func.id)
    return result


def build_project_index():
    modules = {}
    syntax_errors = []
    for path in production_files():
        text = read_text(path)
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            syntax_errors.append((path, exc))
            continue
        module_name = module_name_from_path(path)
        modules[module_name] = {
            'path': path,
            'text': text,
            'tree': tree,
            'functions': top_functions(tree),
            'imports': top_import_map(tree, module_name),
            'unsupported_target_imports': unsupported_target_module_imports(tree),
        }
    if syntax_errors:
        details = '; '.join(
            f'{p.relative_to(ROOT)}: {exc}' for p, exc in syntax_errors
        )
        raise RuntimeError('Arquivos de produção com sintaxe inválida: ' + details)
    return modules


def build_call_graph(modules):
    graph = {}
    reverse = {}
    for module_name, info in modules.items():
        local_functions = set(info['functions'])
        imports = info['imports']
        for fn_name, fn in info['functions'].items():
            caller = (module_name, fn_name)
            graph.setdefault(caller, set())
            for called_name in call_names(fn):
                callee = None
                if called_name in local_functions:
                    callee = (module_name, called_name)
                elif called_name in imports:
                    imported_module, imported_name = imports[called_name]
                    if (
                        imported_module in modules
                        and imported_name in modules[imported_module]['functions']
                    ):
                        callee = (imported_module, imported_name)
                if callee is None:
                    continue
                graph[caller].add(callee)
                reverse.setdefault(callee, set()).add(caller)
    return graph, reverse


def transitive_callers(reverse):
    affected = {TARGET_NODE}
    frontier = [TARGET_NODE]
    while frontier:
        current = frontier.pop()
        for caller in reverse.get(current, set()):
            if caller in affected:
                continue
            affected.add(caller)
            frontier.append(caller)
    return affected


def target_function_node(text):
    tree = parse(text, 'services/analise_recontagem.py')
    fn = top_functions(tree).get(TARGET_FUNCTION)
    if fn is None:
        raise RuntimeError(f'{TARGET_FUNCTION} não encontrada.')
    return tree, fn


def all_http_raises(text):
    tree = parse(text, 'services/analise_recontagem.py')
    result = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        if not (
            isinstance(node.exc, ast.Call)
            and raised_name(node.exc) == 'HTTPException'
        ):
            continue
        result.append(node)
    return tree, result


def target_http_raises(text):
    tree, fn = target_function_node(text)
    result = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        if not (
            isinstance(node.exc, ast.Call)
            and raised_name(node.exc) == 'HTTPException'
        ):
            continue
        status = None
        detail = None
        for kw in node.exc.keywords:
            if kw.arg == 'status_code':
                status = kw.value
            elif kw.arg == 'detail':
                detail = kw.value
        if status is None or detail is None:
            raise RuntimeError('HTTPException sem status/detail.')
        if not (
            isinstance(status, ast.Constant)
            and isinstance(status.value, int)
        ):
            raise RuntimeError('status_code dinâmico não suportado.')
        detail_source = ast.get_source_segment(text, detail)
        if not detail_source:
            raise RuntimeError('detail não recuperado via AST.')
        result.append({
            'node': node,
            'status': status.value,
            'detail': detail_source,
        })
    return result


def target_domain_raises(text):
    _, fn = target_function_node(text)
    allowed = set(EXC_BY_STATUS.values())
    result = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        name = raised_name(node.exc)
        if name in allowed:
            result.append(name)
    return result


def total_http_handlers_file(text):
    tree = parse(text, 'services/analise_recontagem.py')
    return sum(
        1 for node in ast.walk(tree)
        if isinstance(node, ast.ExceptHandler)
        and handler_name(node) == 'HTTPException'
    )


def fastapi_starlette_imports(text):
    tree = parse(text, 'services/analise_recontagem.py')
    result = []
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        module = node.module or ''
        if (
            module in {'fastapi', 'starlette'}
            or module.startswith('fastapi.')
            or module.startswith('starlette.')
        ):
            result.append(node)
    return result


def service_state(text):
    _, all_http = all_http_raises(text)
    target_http = target_http_raises(text)
    domain = target_domain_raises(text)
    handlers = total_http_handlers_file(text)
    http_ids = {(n.lineno, n.col_offset) for n in all_http}
    target_ids = {
        (item['node'].lineno, item['node'].col_offset)
        for item in target_http
    }
    all_inside_target = http_ids == target_ids
    statuses = [item['status'] for item in target_http]
    supported = all(s in EXC_BY_STATUS for s in statuses)
    imports = fastapi_starlette_imports(text)

    if (
        MIN_HTTP_RAISES <= len(target_http) <= MAX_HTTP_RAISES
        and len(domain) == 0
        and all_inside_target
        and supported
        and handlers == 0
        and len(imports) == 1
        and (imports[0].module or '') == 'fastapi'
        and [a.name for a in imports[0].names] == ['HTTPException']
    ):
        return 'LEGADO', {
            'count': len(target_http),
            'statuses': statuses,
            'domain': domain,
            'all_inside_target': all_inside_target,
        }

    if (
        len(target_http) == 0
        and len(domain) >= MIN_HTTP_RAISES
        and len(domain) <= MAX_HTTP_RAISES
        and len(all_http) == 0
        and handlers == 0
        and len(imports) == 0
        and all(name in set(EXC_BY_STATUS.values()) for name in domain)
    ):
        return 'MIGRADO', {
            'count': len(domain),
            'statuses': [],
            'domain': domain,
            'all_inside_target': True,
        }

    return 'DESCONHECIDO', {
        'target_http_count': len(target_http),
        'all_http_count': len(all_http),
        'statuses': statuses,
        'domain': domain,
        'handlers': handlers,
        'http_imports': [
            ((n.module or ''), [a.name for a in n.names])
            for n in imports
        ],
        'all_inside_target': all_inside_target,
    }


def has_generic_http_wrapper(fn):
    for handler in [n for n in ast.walk(fn) if isinstance(n, ast.ExceptHandler)]:
        if handler_name(handler) != 'Exception':
            continue
        for inner in ast.walk(handler):
            if not isinstance(inner, ast.Raise):
                continue
            if (
                isinstance(inner.exc, ast.Call)
                and raised_name(inner.exc) == 'HTTPException'
            ):
                return True
    return False


def router_http_handler(fn):
    handlers = [
        n for n in ast.walk(fn)
        if isinstance(n, ast.ExceptHandler)
        and handler_name(n) == 'HTTPException'
    ]
    if len(handlers) != 1:
        raise RuntimeError(
            f'{fn.name}: esperado exatamente 1 except HTTPException, '
            f'encontrado {len(handlers)}.'
        )
    return handlers[0]


def handler_prefix_lines(text, handler):
    if not handler.body:
        raise RuntimeError('except HTTPException vazio.')
    last = handler.body[-1]
    if not (isinstance(last, ast.Raise) and last.exc is None):
        raise RuntimeError(
            'except HTTPException não termina com `raise` nu; baseline não segura.'
        )
    prefix_nodes = handler.body[:-1]
    if not prefix_nodes:
        return []
    lines = text.splitlines()
    return lines[prefix_nodes[0].lineno - 1: prefix_nodes[-1].end_lineno]


def handler_http_status(handler):
    for node in ast.walk(handler):
        if not isinstance(node, ast.Raise):
            continue
        if not (
            isinstance(node.exc, ast.Call)
            and raised_name(node.exc) == 'HTTPException'
        ):
            continue
        for kw in node.exc.keywords:
            if (
                kw.arg == 'status_code'
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, int)
            ):
                return kw.value.value
    return None


def router_existing_semantic_handler(fn, exc_name):
    handlers = [
        n for n in ast.walk(fn)
        if isinstance(n, ast.ExceptHandler)
        and handler_name(n) == exc_name
    ]
    if len(handlers) > 1:
        raise RuntimeError(f'{fn.name}: handler duplicado para {exc_name}.')
    return handlers[0] if handlers else None


def validate_router_function(text, fn, required_classes, require_all):
    http_handler = router_http_handler(fn)
    prefix = handler_prefix_lines(text, http_handler)
    for exc_name in required_classes:
        existing = router_existing_semantic_handler(fn, exc_name)
        if existing is None:
            if require_all:
                raise RuntimeError(f'{fn.name}: handler {exc_name} ausente.')
            continue
        expected_status = STATUS_BY_EXC[exc_name]
        actual_status = handler_http_status(existing)
        if actual_status != expected_status:
            raise RuntimeError(
                f'{fn.name}: {exc_name} traduz HTTP {actual_status}, '
                f'esperado {expected_status}.'
            )
    return http_handler, prefix


def add_domain_imports(text, required_classes):
    tree = parse(text, 'router')
    existing = set()
    for node in tree.body:
        if (
            isinstance(node, ast.ImportFrom)
            and (node.module or '') == 'domain.exceptions'
        ):
            existing.update(a.name for a in node.names)
    missing = [n for n in required_classes if n not in existing]
    if not missing:
        return text
    fastapi_import = None
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and (node.module or '') == 'fastapi':
            fastapi_import = node
            break
    if fastapi_import is None:
        raise RuntimeError('Router afetado sem import FastAPI reconhecido.')
    lines = text.splitlines()
    lines.insert(
        fastapi_import.end_lineno,
        'from domain.exceptions import ' + ', '.join(missing),
    )
    result = '\n'.join(lines)
    if text.endswith('\n'):
        result += '\n'
    return result


def build_translation_handler(exc_name, status, http_handler, prefix_lines):
    handler_indent = ' ' * http_handler.col_offset
    body_indent = ' ' * (http_handler.col_offset + 4)
    block = [f'{handler_indent}except {exc_name} as erro:']
    if prefix_lines:
        block.extend(prefix_lines)
        block.append('')
    block.extend([
        f'{body_indent}raise HTTPException(',
        f'{body_indent}    status_code={status},',
        f'{body_indent}    detail=str(erro)',
        f'{body_indent})',
        '',
    ])
    return block


def patch_router_file(text, affected_function_names, required_classes):
    before_exact = {token: text.count(token) for token in PROTECTED_EXACT_TOKENS}
    patched = add_domain_imports(text, required_classes)
    tree = parse(patched, 'router após import')
    functions = top_functions(tree)
    insertions = []
    for fn_name in sorted(affected_function_names):
        fn = functions.get(fn_name)
        if fn is None:
            raise RuntimeError(f'Função de router ausente: {fn_name}')
        http_handler, prefix_lines = validate_router_function(
            patched, fn, required_classes, require_all=False
        )
        blocks = []
        for exc_name in required_classes:
            if router_existing_semantic_handler(fn, exc_name) is not None:
                continue
            blocks.extend(build_translation_handler(
                exc_name,
                STATUS_BY_EXC[exc_name],
                http_handler,
                prefix_lines,
            ))
        if blocks:
            insertions.append((http_handler.lineno, blocks))
    lines = patched.splitlines()
    for line_no, block_lines in sorted(insertions, key=lambda x: x[0], reverse=True):
        lines[line_no - 1:line_no - 1] = block_lines
    result = '\n'.join(lines)
    if patched.endswith('\n'):
        result += '\n'
    final_tree = parse(result, 'router final')
    final_functions = top_functions(final_tree)
    for fn_name in affected_function_names:
        validate_router_function(
            result,
            final_functions[fn_name],
            required_classes,
            require_all=True,
        )
    after_exact = {token: result.count(token) for token in PROTECTED_EXACT_TOKENS}
    if before_exact != after_exact:
        diffs = {
            t: (before_exact[t], after_exact[t])
            for t in PROTECTED_EXACT_TOKENS
            if before_exact[t] != after_exact[t]
        }
        raise RuntimeError(f'Commit/conexão foi alterado: {diffs}')
    return result


def replace_fastapi_import_with_domain(text, required_classes):
    tree = parse(text, 'service após raises')
    candidates = []
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        if (
            (node.module or '') == 'fastapi'
            and [a.name for a in node.names] == ['HTTPException']
        ):
            candidates.append(node)
    if len(candidates) != 1:
        raise RuntimeError(
            'Esperado exatamente um import `from fastapi import HTTPException`.'
        )
    node = candidates[0]
    lines = text.splitlines()
    replacement = 'from domain.exceptions import ' + ', '.join(required_classes)
    lines[node.lineno - 1:node.end_lineno] = [replacement]
    result = '\n'.join(lines)
    if text.endswith('\n'):
        result += '\n'
    return result


def patch_service(text):
    state, diag = service_state(text)
    if state != 'LEGADO':
        raise RuntimeError(f'Service não está legado: {state} / {diag}')
    raises = target_http_raises(text)
    lines = text.splitlines()
    replacements = []
    required_classes = sorted(
        {EXC_BY_STATUS[item['status']] for item in raises},
        key=lambda name: STATUS_BY_EXC[name],
    )
    for item in raises:
        status = item['status']
        if status not in EXC_BY_STATUS:
            raise RuntimeError(f'Status {status} fora do escopo.')
        exc_name = EXC_BY_STATUS[status]
        node = item['node']
        indent = ' ' * node.col_offset
        replacement = (
            f'{indent}raise {exc_name}(\n'
            f'{indent}    {item["detail"]}\n'
            f'{indent})'
        )
        replacements.append((node.lineno, node.end_lineno, replacement))
    replacements.sort(key=lambda x: x[0])
    out = []
    current = 1
    for start, end, replacement in replacements:
        out.extend(lines[current - 1:start - 1])
        out.extend(replacement.splitlines())
        current = end + 1
    out.extend(lines[current - 1:])
    result = '\n'.join(out)
    if text.endswith('\n'):
        result += '\n'
    result = replace_fastapi_import_with_domain(result, required_classes)
    state2, diag2 = service_state(result)
    if state2 != 'MIGRADO':
        raise RuntimeError(f'Service pós-patch inválido: {diag2}')
    return result, required_classes


print('[0/14] Validando arquivos e pré-requisitos...')
for path in [SERVICE, DOMAIN, PREV]:
    if not path.exists():
        raise SystemExit(f'[ERRO] Arquivo ausente: {path}')

domain_text = read_text(DOMAIN)
for token in [
    'class BusinessRuleViolation(DomainError)',
    'class NotFoundError(DomainError)',
]:
    if token not in domain_text:
        raise SystemExit(f'[ERRO] Hierarquia de domínio incompleta: {token}')

prev_text = read_text(PREV)
if (
    'from fastapi import HTTPException' in prev_text
    or 'raise HTTPException' in prev_text
):
    raise SystemExit(
        '[ERRO] Fase 10K não reconhecida em services/analise_gestor.py.'
    )
print('      [OK] Fase 10K reconhecida.')

print('[1/14] Analisando baseline local de analise_recontagem...')
service_text = read_text(SERVICE)
s_state, s_diag = service_state(service_text)
print(f'      Estado: {s_state}')
print(f'      raises alvo: {s_diag.get("count", s_diag.get("target_http_count", 0))}')
print(f'      statuses: {s_diag.get("statuses", [])}')
print(f'      domain: {s_diag.get("domain", [])}')
if s_state == 'DESCONHECIDO':
    raise SystemExit(
        '[ERRO] Baseline de analise_recontagem desconhecida: '
        f'{s_diag}'
    )

print('[2/14] Indexando módulos de produção...')
modules = build_project_index()
print(f'      módulos analisados: {len(modules)}')
if TARGET_MODULE not in modules:
    raise SystemExit(f'[ERRO] Módulo {TARGET_MODULE} não indexado.')
for module_name, info in modules.items():
    if info['unsupported_target_imports']:
        raise SystemExit(
            '[ERRO] Import de módulo não suportado em '
            f'{info["path"].relative_to(ROOT)}: '
            f'{info["unsupported_target_imports"]}. '
            'Nenhum arquivo foi alterado.'
        )
print('      [OK] imports compatíveis com análise estática.')

print('[3/14] Construindo grafo de chamadas cross-module...')
_, reverse = build_call_graph(modules)
affected = transitive_callers(reverse)
print(f'      funções afetadas: {len(affected)}')
for module_name, fn_name in sorted(affected):
    print(f'      - {module_name}.{fn_name}')

print('[4/14] Classificando caminhos...')
affected_services = sorted(
    node for node in affected
    if node != TARGET_NODE and node[0].startswith('services.')
)
affected_routers = sorted(
    node for node in affected if node[0].startswith('routers.')
)
unexpected = sorted(
    node for node in affected
    if node != TARGET_NODE
    and not node[0].startswith('services.')
    and not node[0].startswith('routers.')
)
print(f'      services intermediários: {len(affected_services)}')
print(f'      funções de router: {len(affected_routers)}')
if unexpected:
    for node in unexpected:
        print(f'      [BLOQUEIO] {node[0]}.{node[1]}')
    raise SystemExit(
        '[ERRO] Caller fora de services/routers. Nenhum arquivo alterado.'
    )

print('[5/14] Verificando services intermediários...')
for module_name, fn_name in affected_services:
    fn = modules[module_name]['functions'][fn_name]
    if has_generic_http_wrapper(fn):
        print(
            f'      [BLOQUEIO] {module_name}.{fn_name} '
            'captura Exception e gera HTTPException.'
        )
        raise SystemExit(
            '[ERRO] DomainError seria convertido em HTTP por service '
            'intermediário. Nenhum arquivo alterado.'
        )
    print(f'      [OK] {module_name}.{fn_name}')

if not affected_routers:
    raise SystemExit(
        '[ERRO] Nenhuma fronteira HTTP alcançada pelo grafo. '
        'Nenhum arquivo alterado.'
    )

print('[6/14] Agrupando fronteiras HTTP...')
router_groups = {}
for module_name, fn_name in affected_routers:
    router_groups.setdefault(module_name, set()).add(fn_name)
for module_name, functions in sorted(router_groups.items()):
    print(f'      {module_name}: {sorted(functions)}')

required_classes = ['BusinessRuleViolation', 'NotFoundError']

print('[7/14] Validando handlers atuais...')
for module_name, function_names in router_groups.items():
    info = modules[module_name]
    for fn_name in function_names:
        validate_router_function(
            info['text'],
            info['functions'][fn_name],
            required_classes,
            require_all=(s_state == 'MIGRADO'),
        )
        print(f'      [OK] {module_name}.{fn_name}')

if s_state == 'MIGRADO':
    print('[8/14] Fase 10L já aplicada.')
    print('      [OK] service e fronteiras HTTP consistentes.')
    raise SystemExit(0)

print('[8/14] Confirmando perfil HTTP do arquivo local...')
raises = target_http_raises(service_text)
if not (MIN_HTTP_RAISES <= len(raises) <= MAX_HTTP_RAISES):
    raise SystemExit(
        f'[ERRO] Quantidade {len(raises)} fora do intervalo seguro '
        f'{MIN_HTTP_RAISES}-{MAX_HTTP_RAISES}.'
    )
for item in raises:
    if item['status'] not in EXC_BY_STATUS:
        raise SystemExit(f'[ERRO] HTTP {item["status"]} fora do escopo.')
    print(
        f'      HTTP {item["status"]} -> '
        f'{EXC_BY_STATUS[item["status"]]} | detail={item["detail"]}'
    )
print('      [OK] todos os erros são 400/404.')

print('[9/14] Preparando backups...')
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
paths_to_edit = {TARGET_MODULE: SERVICE}
for module_name in router_groups:
    paths_to_edit[module_name] = modules[module_name]['path']
backups = {}
for module_name, path in paths_to_edit.items():
    backup = path.parent / (
        path.stem + '_backup_fase10l_' + timestamp + '.py'
    )
    shutil.copy2(path, backup)
    backups[module_name] = backup
    print(f'      {path.relative_to(ROOT)} -> {backup.name}')

try:
    print('[10/14] Migrando analise_recontagem.py...')
    patched_service, required_classes = patch_service(service_text)
    SERVICE.write_text(patched_service, encoding='utf-8')
    py_compile.compile(str(SERVICE), doraise=True)
    print(
        f'      [OK] {len(raises)} HTTPException -> exceções semânticas.'
    )
    print('      [OK] import FastAPI removido.')

    print('[11/14] Adaptando fronteiras HTTP...')
    for module_name, function_names in router_groups.items():
        path = modules[module_name]['path']
        original_text = read_text(path)
        patched_router = patch_router_file(
            original_text,
            affected_function_names=function_names,
            required_classes=required_classes,
        )
        path.write_text(patched_router, encoding='utf-8')
        py_compile.compile(str(path), doraise=True)
        print(f'      [OK] {module_name}: {sorted(function_names)}')

    print('[12/14] Revalidando service...')
    final_service = read_text(SERVICE)
    final_state, final_diag = service_state(final_service)
    if final_state != 'MIGRADO':
        raise RuntimeError(f'Service final inválido: {final_diag}')
    print('      [OK] analise_recontagem sem FastAPI/HTTPException.')

    print('[13/14] Revalidando grafo e handlers...')
    final_modules = build_project_index()
    _, final_reverse = build_call_graph(final_modules)
    final_affected = transitive_callers(final_reverse)
    if final_affected != affected:
        raise RuntimeError('Grafo de consumidores mudou durante a migração.')
    for module_name, function_names in router_groups.items():
        info = final_modules[module_name]
        for fn_name in function_names:
            validate_router_function(
                info['text'],
                info['functions'][fn_name],
                required_classes,
                require_all=True,
            )
    print('      [OK] todas as fronteiras traduzem 400/404.')

    print('[14/14] Revalidando propagação por services...')
    for module_name, fn_name in affected_services:
        fn = final_modules[module_name]['functions'][fn_name]
        if has_generic_http_wrapper(fn):
            raise RuntimeError(
                f'{module_name}.{fn_name} passou a bloquear DomainError.'
            )
    print('      [OK] services intermediários permanecem transparentes.')

except Exception:
    print()
    print('[ERRO] Falha durante Fase 10L.')
    print('[INFO] Restaurando todos os arquivos...')
    for module_name, path in paths_to_edit.items():
        shutil.copy2(backups[module_name], path)
        print(f'      [OK] restaurado: {path.relative_to(ROOT)}')
    raise

print()
print('[OK] Fase 10L aplicada.')
print('[OK] services/analise_recontagem.py desacoplado de FastAPI.')
print('[OK] todos os HTTPException locais migrados para 400/404 semânticos.')
print('[OK] todos os callers transitivos foram rastreados.')
print('[OK] todas as fronteiras HTTP reconhecidas foram adaptadas.')
print('[OK] rollback/log dos routers foi preservado por caminho.')
print('[OK] services intermediários não foram alterados.')
print()
print('PRÓXIMO PASSO:')
print('1. Reinicie a API.')
print(r'2. python tests_e2e\\regressao_final_sgi.py')
print(r'3. python .\\fase10a_auditoria_excecoes_dominio\\auditar_fase10a.py')
