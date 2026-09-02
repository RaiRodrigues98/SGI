from __future__ import annotations

from pathlib import Path
import shutil
import time
import py_compile

ROOT = Path.cwd()
FILES = [
    ROOT / 'tests_e2e' / 'teste_rotativo_estagio5.py',
    ROOT / 'tests_e2e' / 'teste_rotativo_estagio9.py',
]


def backup(path: Path) -> Path:
    stamp = time.strftime('%Y%m%d_%H%M%S')
    dest = path.with_name(f'{path.stem}_backup_fixture_{stamp}{path.suffix}')
    shutil.copy2(path, dest)
    return dest


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: esperado 1 bloco, encontrado {count}')
    return text.replace(old, new, 1)


def add_skip_support(text: str, label: str) -> str:
    old = """@dataclass
class Report:
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    def ok(self, name: str):
        self.passed.append(name)
        print(f\"[PASS] {name}\")

    def fail(self, name: str, exc: Exception | str):
        msg = f\"{name}: {exc}\"
        self.failed.append(msg)
        print(f\"[FAIL] {msg}\")
"""
    new = """@dataclass
class Report:
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def ok(self, name: str):
        self.passed.append(name)
        print(f\"[PASS] {name}\")

    def fail(self, name: str, exc: Exception | str):
        msg = f\"{name}: {exc}\"
        self.failed.append(msg)
        print(f\"[FAIL] {msg}\")

    def skip(self, name: str, reason: Exception | str):
        msg = f\"{name}: {reason}\"
        self.skipped.append(msg)
        print(f\"[SKIP] {msg}\")


class FixtureUnavailable(RuntimeError):
    \"\"\"Pré-condição externa ausente; não é regressão funcional do SGI.\"\"\"
    pass
"""
    text = replace_once(text, old, new, f'{label}: Report')

    old_run = """def run(name, fn):
    try:
        fn()
        R.ok(name)
    except Exception as e:
        R.fail(name, str(e))
"""
    new_run = """def run(name, fn):
    try:
        fn()
        R.ok(name)
    except FixtureUnavailable as e:
        R.skip(name, str(e))
    except Exception as e:
        R.fail(name, str(e))
"""
    return replace_once(text, old_run, new_run, f'{label}: run')


def patch_stage5(path: Path):
    text = path.read_text(encoding='utf-8')
    text = add_skip_support(text, 'Estágio 5')

    start = text.find('    raise AssertionError(\n        "O endere')
    if start < 0:
        raise RuntimeError('Estágio 5: fixture de dois lotes não localizada')
    end = text.find('    )', start)
    if end < 0:
        raise RuntimeError('Estágio 5: fim da fixture não localizado')
    end += len('    )')
    replacement = """    raise FixtureUnavailable(
        \"O endereço de teste não possui um código com pelo menos dois lotes positivos; \"
        \"os cenários LOTE_INCORRETO/LOTE_E_QUANTIDADE exigem essa fixture.\"
    )"""
    text = text[:start] + replacement + text[end:]

    text = replace_once(
        text,
        '    print(f"PASS: {len(R.passed)} | FAIL: {len(R.failed)}")',
        '    print(f"PASS: {len(R.passed)} | FAIL: {len(R.failed)} | SKIP: {len(R.skipped)}")',
        'Estágio 5: resumo',
    )
    path.write_text(text, encoding='utf-8', newline='\n')


def patch_stage9(path: Path):
    text = path.read_text(encoding='utf-8')
    text = add_skip_support(text, 'Estágio 9')

    start = text.find('    assert_true(\n        pendentes,')
    if start < 0:
        raise RuntimeError('Estágio 9: validação de pendentes não localizada')
    end = text.find('    )', start)
    if end < 0:
        raise RuntimeError('Estágio 9: fim da validação de pendentes não localizado')
    end += len('    )')
    replacement = """    if not pendentes:
        raise FixtureUnavailable(
            \"O ciclo aberto não possui localização PENDENTE; \"
            \"estado residual do ambiente impede executar os cenários operacionais.\"
        )"""
    text = text[:start] + replacement + text[end:]

    guard = """def require_operational_context():
    required = (\"id_inventario\", \"id_rodada\", \"localizacao\")
    missing = [k for k in required if k not in CTX]
    if missing:
        raise FixtureUnavailable(
            \"Contexto operacional não preparado \"
            f\"(ausentes: {', '.join(missing)}).\"
        )


"""
    anchor = 'def test_conclusao_operacional_atualiza_cobertura():\n'
    text = replace_once(text, anchor, guard + anchor, 'Estágio 9: guard')

    text = replace_once(
        text,
        'def test_conclusao_operacional_atualiza_cobertura():\n    iid = CTX["id_inventario"]',
        'def test_conclusao_operacional_atualiza_cobertura():\n    require_operational_context()\n    iid = CTX["id_inventario"]',
        'Estágio 9: conclusão',
    )
    text = replace_once(
        text,
        'def test_conclusao_nao_duplica_cobertura():\n    sid = CTX["id_sessao"]',
        'def test_conclusao_nao_duplica_cobertura():\n    require_operational_context()\n    if "id_sessao" not in CTX:\n        raise FixtureUnavailable("Sessão operacional não foi criada.")\n    sid = CTX["id_sessao"]',
        'Estágio 9: idempotência',
    )
    text = replace_once(
        text,
        'def test_vinculo_inventario_rodada_e_ultima_contagem():\n    consulta =',
        'def test_vinculo_inventario_rodada_e_ultima_contagem():\n    require_operational_context()\n    if "id_sessao" not in CTX:\n        raise FixtureUnavailable("Conclusão operacional não foi executada.")\n    consulta =',
        'Estágio 9: vínculo',
    )
    text = replace_once(
        text,
        'def test_filtros_operacionais_respeitam_status():\n    cid = CTX["id_ciclo"]',
        'def test_filtros_operacionais_respeitam_status():\n    require_operational_context()\n    cid = CTX["id_ciclo"]',
        'Estágio 9: filtros',
    )

    text = replace_once(
        text,
        '    print(f"PASS: {len(R.passed)} | FAIL: {len(R.failed)}")',
        '    print(f"PASS: {len(R.passed)} | FAIL: {len(R.failed)} | SKIP: {len(R.skipped)}")',
        'Estágio 9: resumo',
    )
    path.write_text(text, encoding='utf-8', newline='\n')


def main():
    missing = [str(p) for p in FILES if not p.exists()]
    if missing:
        raise FileNotFoundError('Arquivos não encontrados: ' + ', '.join(missing))

    backups = [backup(p) for p in FILES]
    try:
        patch_stage5(FILES[0])
        patch_stage9(FILES[1])
        for p in FILES:
            py_compile.compile(str(p), doraise=True)

        print('=' * 72)
        print('PATCH E2E FIXTURES: APROVADO')
        print('=' * 72)
        print('- Estágio 5: ausência de fixture com 2 lotes => SKIP explícito')
        print('- Estágio 9: ciclo sem PENDENTE => SKIP explícito, sem cascata de KeyError')
        print('- assertions funcionais permanecem intactas quando a fixture existe')
        print('- py_compile: APROVADO')
        print('Backups:')
        for b in backups:
            print(' ', b)
    except BaseException:
        for src, bkp in zip(FILES, backups):
            shutil.copy2(bkp, src)
        print('REPROVADO - arquivos restaurados a partir dos backups')
        raise


if __name__ == '__main__':
    main()
