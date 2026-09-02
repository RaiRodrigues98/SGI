from pathlib import Path
import shutil
import py_compile
from datetime import datetime

ROOT = Path.cwd()
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

TARGETS = [
    ROOT / "services" / "ciclos_rotativo.py",
    ROOT / "services" / "rotativo_cobertura.py",
    ROOT / "services" / "rotativo_contexto.py",
    ROOT / "services" / "rotativo_fluxo.py",
    ROOT / "services" / "rotativo_orquestrador.py",
    ROOT / "services" / "rotativo_painel.py",
    ROOT / "services" / "rotativo_priorizacao.py",
    ROOT / "services" / "rotativo_sugestoes.py",
    ROOT / "services" / "rotativo_tendencia.py",
    ROOT / "services" / "rotativo_tratativas.py",
    ROOT / "routers" / "rotativo_ciclos.py",
    ROOT / "routers" / "rotativo_cobertura.py",
    ROOT / "routers" / "rotativo_fluxo.py",
    ROOT / "routers" / "rotativo_priorizacao.py",
]

for arq in TARGETS:
    if not arq.exists():
        raise FileNotFoundError(f"Arquivo obrigatório não encontrado: {arq}")

backup_dir = ROOT / "_backup_fase12_consolidado" / timestamp
backup_dir.mkdir(parents=True, exist_ok=True)

for arq in TARGETS:
    rel = arq.relative_to(ROOT)
    destino = backup_dir / rel
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(arq, destino)


def restore_all():
    for arq in TARGETS:
        rel = arq.relative_to(ROOT)
        origem = backup_dir / rel
        if origem.exists():
            shutil.copy2(origem, arq)


def compile_file(path):
    py_compile.compile(str(path), doraise=True)


def ensure_brv_import(path):
    texto = path.read_text(encoding="utf-8")
    if "from domain.exceptions import BusinessRuleViolation" in texto:
        return texto

    # Prefer insertion after UoW in routers.
    marker = "from infrastructure.database.unit_of_work import SqlServerUnitOfWork\n"
    if marker in texto:
        return texto.replace(
            marker,
            marker + "\nfrom domain.exceptions import BusinessRuleViolation\n",
            1,
        )

    return "from domain.exceptions import BusinessRuleViolation\n" + texto


def semantic_service(path, expected_old):
    texto = path.read_text(encoding="utf-8")
    qtd_old = texto.count("raise ValueError(")
    qtd_brv = texto.count("raise BusinessRuleViolation(")

    if qtd_old == expected_old:
        texto = ensure_brv_import(path)
        texto = texto.replace("raise ValueError(", "raise BusinessRuleViolation(")
        path.write_text(texto, encoding="utf-8")
        compile_file(path)
        print(f"CORRIGIDO  {path.relative_to(ROOT)}: {expected_old} ValueError -> BRV")
        return

    if qtd_old == 0 and qtd_brv >= expected_old:
        compile_file(path)
        print(f"OK         {path.relative_to(ROOT)}: já corrigido")
        return

    raise RuntimeError(
        f"Estado intermediário inesperado em {path.relative_to(ROOT)}: "
        f"ValueError={qtd_old}, BRV={qtd_brv}, esperado antigo={expected_old}."
    )


def semantic_router(path, expected_old_catches=None, replace_all=False):
    texto = path.read_text(encoding="utf-8")
    old = texto.count("except ValueError as erro:")
    brv = texto.count("except BusinessRuleViolation as erro:")

    if replace_all:
        if old:
            texto = ensure_brv_import(path)
            texto = texto.replace(
                "except ValueError as erro:",
                "except BusinessRuleViolation as erro:",
            )
            path.write_text(texto, encoding="utf-8")
            compile_file(path)
            print(f"CORRIGIDO  {path.relative_to(ROOT)}: {old} catches -> BRV")
        else:
            compile_file(path)
            print(f"OK         {path.relative_to(ROOT)}: sem ValueError catches")
        return

    if expected_old_catches is None:
        raise RuntimeError("expected_old_catches obrigatório")

    if old == expected_old_catches:
        texto = ensure_brv_import(path)
        texto = texto.replace(
            "except ValueError as erro:",
            "except BusinessRuleViolation as erro:",
        )
        path.write_text(texto, encoding="utf-8")
        compile_file(path)
        print(f"CORRIGIDO  {path.relative_to(ROOT)}: catches -> BRV")
        return

    if old == 0 and brv >= expected_old_catches:
        compile_file(path)
        print(f"OK         {path.relative_to(ROOT)}: já corrigido")
        return

    raise RuntimeError(
        f"Estado inesperado em {path.relative_to(ROOT)}: "
        f"ValueError catches={old}, BRV catches={brv}."
    )


def run_embedded(nome, codigo):
    print()
    print("=" * 72)
    print(nome)
    print("=" * 72)
    ns = {"__name__": "__main__"}
    exec(compile(codigo, nome, "exec"), ns, ns)


HELPER_FLUXO = 'from pathlib import Path\nimport shutil\nimport py_compile\nimport re\nfrom datetime import datetime\n\nROOT = Path.cwd()\nservice = ROOT / "services" / "rotativo_fluxo.py"\nrouter = ROOT / "routers" / "rotativo_fluxo.py"\n\nfor arq in (service, router):\n    if not arq.exists():\n        raise FileNotFoundError(f"Não encontrado: {arq}")\n\ntimestamp = datetime.now().strftime("%Y%m%d_%H%M%S")\nbackups = {}\n\nfor arq in (service, router):\n    backup = arq.with_name(f"{arq.stem}_backup_uow_{timestamp}{arq.suffix}")\n    shutil.copy2(arq, backup)\n    backups[arq] = backup\n\ntry:\n    texto = service.read_text(encoding="utf-8")\n\n    qtd_value_error = texto.count("raise ValueError(")\n    if qtd_value_error != 9:\n        raise RuntimeError(\n            f"rotativo_fluxo.py: esperados 9 ValueError; encontrados {qtd_value_error}."\n        )\n\n    if "from domain.exceptions import BusinessRuleViolation" not in texto:\n        texto = "from domain.exceptions import BusinessRuleViolation\\n" + texto\n\n    texto = texto.replace("raise ValueError(", "raise BusinessRuleViolation(")\n\n    texto, n1 = re.subn(\n        r"def iniciar_localizacao_rotativo\\(\\n    conn,\\n    cursor,",\n        "def iniciar_localizacao_rotativo(\\n    cursor,",\n        texto,\n        count=1,\n    )\n    if n1 != 1:\n        raise RuntimeError("Não foi possível remover conn da função iniciar.")\n\n    texto, n2 = re.subn(\n        r"def ignorar_localizacao_rotativo\\(\\n    conn,\\n    cursor,",\n        "def ignorar_localizacao_rotativo(\\n    cursor,",\n        texto,\n        count=1,\n    )\n    if n2 != 1:\n        raise RuntimeError("Não foi possível remover conn da função ignorar.")\n\n    padrao_tx = re.compile(\n        r"(?ms)^    try:\\n"\n        r"(?P<body>(?:^        .*\\n|^$\\n)+?)"\n        r"^    except Exception:\\n"\n        r"^        conn\\.rollback\\(\\)\\n"\n        r"^        raise\\n"\n    )\n\n    encontrados = list(padrao_tx.finditer(texto))\n    if len(encontrados) != 2:\n        raise RuntimeError(\n            f"Esperados 2 blocos transacionais try/except; encontrados {len(encontrados)}."\n        )\n\n    def remover_wrapper(match):\n        body = match.group("body")\n        saida = []\n        for linha in body.splitlines(True):\n            if linha.startswith("        "):\n                linha = linha[4:]\n            saida.append(linha)\n        return "".join(saida)\n\n    texto = padrao_tx.sub(remover_wrapper, texto)\n\n    qtd_commit = texto.count("    conn.commit()\\n")\n    if qtd_commit != 2:\n        raise RuntimeError(\n            f"Esperados 2 commits no service; encontrados {qtd_commit}."\n        )\n\n    texto = texto.replace("    conn.commit()\\n", "")\n\n    if "conn.commit()" in texto or "conn.rollback()" in texto:\n        raise RuntimeError("Ainda existe commit/rollback no service.")\n\n    if "raise ValueError(" in texto:\n        raise RuntimeError("Ainda existe ValueError no service.")\n\n    service.write_text(texto, encoding="utf-8")\n\n    texto = router.read_text(encoding="utf-8")\n\n    marcador = "from infrastructure.database.unit_of_work import SqlServerUnitOfWork\\n"\n    if marcador not in texto:\n        raise RuntimeError("Import do SqlServerUnitOfWork não encontrado.")\n\n    if "from domain.exceptions import BusinessRuleViolation" not in texto:\n        texto = texto.replace(\n            marcador,\n            marcador + "\\nfrom domain.exceptions import BusinessRuleViolation\\n",\n            1,\n        )\n\n    antigo = """        return iniciar_localizacao_rotativo(\n            conn=conn,\n            cursor=cursor,\n"""\n    novo = """        resultado = iniciar_localizacao_rotativo(\n            cursor=cursor,\n"""\n    if texto.count(antigo) != 1:\n        raise RuntimeError("Chamada de iniciar_localizacao_rotativo não encontrada.")\n    texto = texto.replace(antigo, novo, 1)\n\n    antigo = """            usuario=dados.usuario\n        )\n\n    except ValueError as erro:\n"""\n    novo = """            usuario=dados.usuario\n        )\n\n        uow.commit()\n        return resultado\n\n    except BusinessRuleViolation as erro:\n        if conn:\n            uow.rollback()\n\n"""\n    if texto.count(antigo) < 1:\n        raise RuntimeError("Fechamento do endpoint iniciar não encontrado.")\n    texto = texto.replace(antigo, novo, 1)\n\n    antigo = """        return ignorar_localizacao_rotativo(\n            conn=conn,\n            cursor=cursor,\n"""\n    novo = """        resultado = ignorar_localizacao_rotativo(\n            cursor=cursor,\n"""\n    if texto.count(antigo) != 1:\n        raise RuntimeError("Chamada de ignorar_localizacao_rotativo não encontrada.")\n    texto = texto.replace(antigo, novo, 1)\n\n    antigo = """            usuario=dados.usuario\n        )\n\n    except ValueError as erro:\n"""\n    novo = """            usuario=dados.usuario\n        )\n\n        uow.commit()\n        return resultado\n\n    except BusinessRuleViolation as erro:\n        if conn:\n            uow.rollback()\n\n"""\n    if texto.count(antigo) != 1:\n        raise RuntimeError("Fechamento do endpoint ignorar não encontrado.")\n    texto = texto.replace(antigo, novo, 1)\n\n    bloco_generico = """    except Exception as erro:\n        raise HTTPException(\n            status_code=500,\n            detail=str(erro)\n        )\n"""\n    bloco_generico_novo = """    except Exception as erro:\n        if conn:\n            uow.rollback()\n\n        raise HTTPException(\n            status_code=500,\n            detail=str(erro)\n        )\n"""\n\n    if texto.count(bloco_generico) != 2:\n        raise RuntimeError(\n            f"Esperados 2 blocos Exception no router; encontrados {texto.count(bloco_generico)}."\n        )\n\n    texto = texto.replace(bloco_generico, bloco_generico_novo)\n\n    if "except ValueError as erro:" in texto:\n        raise RuntimeError("Ainda existe catch de ValueError no router.")\n\n    if texto.count("uow.commit()") != 2:\n        raise RuntimeError(\n            f"Esperados 2 commits no router; encontrados {texto.count(\'uow.commit()\')}."\n        )\n\n    if texto.count("uow.rollback()") != 4:\n        raise RuntimeError(\n            f"Esperados 4 rollbacks no router; encontrados {texto.count(\'uow.rollback()\')}."\n        )\n\n    router.write_text(texto, encoding="utf-8")\n\n    py_compile.compile(str(service), doraise=True)\n    py_compile.compile(str(router), doraise=True)\n\nexcept Exception:\n    for arq, backup in backups.items():\n        shutil.copy2(backup, arq)\n    raise\n\nprint("APROVADO")\nprint()\nprint("Alterações:")\nprint("- 9 ValueError -> BusinessRuleViolation")\nprint("- commit/rollback removidos de services/rotativo_fluxo.py")\nprint("- parâmetro conn removido das 2 funções do service")\nprint("- 2 commits movidos para routers/rotativo_fluxo.py")\nprint("- rollback no router para erro de negócio e erro técnico")\nprint("- HTTP 400/500 preservados")\nprint("- py_compile aprovado")\nprint()\nprint("Backups:")\nfor backup in backups.values():\n    print(backup)\n'
HELPER_CICLOS = 'from pathlib import Path\nimport ast\nimport shutil\nimport py_compile\nimport re\nfrom datetime import datetime\n\nROOT = Path.cwd()\nservice = ROOT / "services" / "ciclos_rotativo.py"\nrouter = ROOT / "routers" / "rotativo_ciclos.py"\n\nfor arq in (service, router):\n    if not arq.exists():\n        raise FileNotFoundError(f"Não encontrado: {arq}")\n\ntimestamp = datetime.now().strftime("%Y%m%d_%H%M%S")\nbackups = {}\nfor arq in (service, router):\n    backup = arq.with_name(f"{arq.stem}_backup_uow_{timestamp}{arq.suffix}")\n    shutil.copy2(arq, backup)\n    backups[arq] = backup\n\n\ndef defs_por_nome(texto, nome):\n    tree = ast.parse(texto)\n    return [\n        n for n in tree.body\n        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))\n        and n.name == nome\n    ]\n\n\ndef substituir_funcao(texto, node, novo_trecho):\n    linhas = texto.splitlines(True)\n    ini = node.lineno - 1\n    fim = node.end_lineno\n    return "".join(linhas[:ini]) + novo_trecho + "".join(linhas[fim:])\n\n\ndef extrair_funcao(texto, node):\n    linhas = texto.splitlines(True)\n    return "".join(linhas[node.lineno - 1:node.end_lineno])\n\n\ndef remover_wrapper_transacional(func_texto, nome_funcao):\n    padrao = re.compile(\n        r"(?ms)^    try:\\n"\n        r"(?P<body>.*?)"\n        r"^    except Exception:\\n"\n        r"        conn\\.rollback\\(\\)\\n"\n        r"        raise\\n"\n    )\n    matches = list(padrao.finditer(func_texto))\n    if len(matches) != 1:\n        raise RuntimeError(\n            f"{nome_funcao}: esperado 1 wrapper try/except transacional; "\n            f"encontrados {len(matches)}."\n        )\n\n    def repl(match):\n        body = match.group("body")\n        saida = []\n        for linha in body.splitlines(True):\n            if linha.startswith("        "):\n                linha = linha[4:]\n            saida.append(linha)\n        return "".join(saida)\n\n    return padrao.sub(repl, func_texto, count=1)\n\n\ndef localizar_funcao_router_por_chamada(texto, chamada):\n    tree = ast.parse(texto)\n    achadas = []\n    for fn in ast.walk(tree):\n        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):\n            continue\n        for n in ast.walk(fn):\n            if (\n                isinstance(n, ast.Call)\n                and isinstance(n.func, ast.Name)\n                and n.func.id == chamada\n            ):\n                achadas.append(fn)\n                break\n    if len(achadas) != 1:\n        raise RuntimeError(\n            f"Router: esperada 1 função chamando {chamada}; "\n            f"encontradas {len(achadas)}."\n        )\n    return achadas[0]\n\n\ndef transformar_endpoint(func_texto, chamada, ja_tem_resultado=False):\n    # Remove conn=conn apenas da chamada alvo.\n    padrao_call = re.compile(\n        rf"(?ms)(?P<prefix>^[ \\t]*(?:return |resultado = ){re.escape(chamada)}\\(\\n)"\n        r"(?P<body>.*?)"\n        r"(?P<close>^[ \\t]*\\)\\n)"\n    )\n    m = padrao_call.search(func_texto)\n    if not m:\n        raise RuntimeError(f"Chamada {chamada} não localizada no endpoint.")\n\n    bloco = m.group(0)\n    if bloco.count("conn=conn,") != 1:\n        raise RuntimeError(\n            f"{chamada}: esperado exatamente 1 argumento conn=conn."\n        )\n\n    bloco_novo = bloco.replace("            conn=conn,\\n", "", 1)\n\n    if not ja_tem_resultado:\n        bloco_novo = bloco_novo.replace(\n            f"        return {chamada}(",\n            f"        resultado = {chamada}(",\n            1\n        )\n\n    # Commit deve ocorrer imediatamente após o service e antes do retorno.\n    if ja_tem_resultado:\n        alvo_retorno = "\\n        return resultado"\n        if alvo_retorno not in func_texto[m.end():]:\n            raise RuntimeError(\n                f"{chamada}: return resultado não encontrado após a chamada."\n            )\n        # Primeiro substitui a chamada.\n        func_texto = func_texto[:m.start()] + bloco_novo + func_texto[m.end():]\n        # Insere commit no primeiro return resultado posterior.\n        pos_busca = func_texto.find("        return resultado", m.start())\n        func_texto = (\n            func_texto[:pos_busca]\n            + "        uow.commit()\\n\\n"\n            + func_texto[pos_busca:]\n        )\n    else:\n        bloco_novo = bloco_novo.rstrip("\\n") + "\\n\\n        uow.commit()\\n        return resultado\\n"\n        func_texto = func_texto[:m.start()] + bloco_novo + func_texto[m.end():]\n\n    # Contrato semântico 400 da Fase 11.\n    if "except ValueError as erro:" not in func_texto:\n        raise RuntimeError(\n            f"{chamada}: except ValueError esperado não encontrado."\n        )\n    func_texto = func_texto.replace(\n        "except ValueError as erro:",\n        "except BusinessRuleViolation as erro:",\n        1\n    )\n\n    # Rollback em todos os caminhos de exceção do endpoint.\n    bloco_business = """    except BusinessRuleViolation as erro:\n        raise HTTPException(\n"""\n    bloco_business_novo = """    except BusinessRuleViolation as erro:\n        if conn:\n            uow.rollback()\n\n        raise HTTPException(\n"""\n    if bloco_business not in func_texto:\n        raise RuntimeError(\n            f"{chamada}: bloco BusinessRuleViolation não localizado."\n        )\n    func_texto = func_texto.replace(\n        bloco_business, bloco_business_novo, 1\n    )\n\n    bloco_http = """    except HTTPException:\n        raise\n"""\n    bloco_http_novo = """    except HTTPException:\n        if conn:\n            uow.rollback()\n\n        raise\n"""\n    if bloco_http not in func_texto:\n        raise RuntimeError(\n            f"{chamada}: bloco HTTPException não localizado."\n        )\n    func_texto = func_texto.replace(bloco_http, bloco_http_novo, 1)\n\n    bloco_exc = """    except Exception as erro:\n        raise HTTPException(\n"""\n    bloco_exc_novo = """    except Exception as erro:\n        if conn:\n            uow.rollback()\n\n        raise HTTPException(\n"""\n    if bloco_exc not in func_texto:\n        raise RuntimeError(\n            f"{chamada}: bloco Exception não localizado."\n        )\n    func_texto = func_texto.replace(bloco_exc, bloco_exc_novo, 1)\n\n    return func_texto\n\n\ntry:\n    # ========================================================\n    # SERVICE: REPARO E OWNERSHIP\n    # ========================================================\n    texto = service.read_text(encoding="utf-8")\n\n    # Fase 11: este arquivo tinha 9 ValueError migrados.\n    qtd_value = texto.count("raise ValueError(")\n    if qtd_value != 9:\n        raise RuntimeError(\n            f"ciclos_rotativo.py: esperados 9 ValueError da versão regredida; "\n            f"encontrados {qtd_value}. Nenhuma alteração aplicada."\n        )\n\n    if "from domain.exceptions import BusinessRuleViolation" not in texto:\n        # Mantém imports existentes e adiciona apenas o necessário.\n        texto = "from domain.exceptions import BusinessRuleViolation\\n" + texto\n\n    texto = texto.replace("raise ValueError(", "raise BusinessRuleViolation(")\n\n    # Remove a primeira definição duplicada de finalizar_ciclo_rotativo.\n    finais = defs_por_nome(texto, "finalizar_ciclo_rotativo")\n    if len(finais) != 2:\n        raise RuntimeError(\n            f"Esperadas 2 definições de finalizar_ciclo_rotativo; "\n            f"encontradas {len(finais)}."\n        )\n\n    linhas = texto.splitlines(True)\n    primeiro = finais[0]\n    texto = (\n        "".join(linhas[:primeiro.lineno - 1])\n        + "".join(linhas[primeiro.end_lineno:])\n    )\n\n    # Reparse após remoção.\n    finais = defs_por_nome(texto, "finalizar_ciclo_rotativo")\n    aberturas = defs_por_nome(texto, "abrir_ciclo_rotativo")\n    if len(finais) != 1 or len(aberturas) != 1:\n        raise RuntimeError(\n            "Estrutura após remoção da duplicidade ficou inesperada."\n        )\n\n    # Transformar ABRIR.\n    node = aberturas[0]\n    trecho = extrair_funcao(texto, node)\n\n    sig = """def abrir_ciclo_rotativo(\n    conn,\n    cursor,"""\n    if sig not in trecho:\n        raise RuntimeError("Assinatura esperada de abrir_ciclo_rotativo não encontrada.")\n    trecho = trecho.replace(\n        sig,\n        """def abrir_ciclo_rotativo(\n    cursor,""",\n        1\n    )\n\n    trecho = remover_wrapper_transacional(\n        trecho, "abrir_ciclo_rotativo"\n    )\n\n    if trecho.count("conn.commit()") != 1:\n        raise RuntimeError(\n            "abrir_ciclo_rotativo: esperado 1 commit interno."\n        )\n    trecho = trecho.replace("    conn.commit()\\n", "", 1)\n\n    # Node original ainda vale para substituição neste texto.\n    texto = substituir_funcao(texto, node, trecho)\n\n    # Reparse antes da finalização.\n    final_node = defs_por_nome(texto, "finalizar_ciclo_rotativo")[0]\n    trecho = extrair_funcao(texto, final_node)\n\n    sig = """def finalizar_ciclo_rotativo(\n    conn,\n    cursor,"""\n    if sig not in trecho:\n        raise RuntimeError(\n            "Assinatura esperada de finalizar_ciclo_rotativo não encontrada."\n        )\n    trecho = trecho.replace(\n        sig,\n        """def finalizar_ciclo_rotativo(\n    cursor,""",\n        1\n    )\n\n    trecho = remover_wrapper_transacional(\n        trecho, "finalizar_ciclo_rotativo"\n    )\n\n    # Após remover o wrapper, sobra o rollback concorrencial explícito.\n    commits = trecho.count("conn.commit()")\n    rollbacks = trecho.count("conn.rollback()")\n    if commits != 1 or rollbacks != 1:\n        raise RuntimeError(\n            "finalizar_ciclo_rotativo: esperados 1 commit e 1 rollback "\n            f"remanescentes; encontrados commit={commits}, rollback={rollbacks}."\n        )\n\n    trecho = trecho.replace("        conn.rollback()\\n\\n", "", 1)\n    trecho = trecho.replace("    conn.commit()\\n", "", 1)\n\n    texto = substituir_funcao(texto, final_node, trecho)\n\n    if texto.count("def finalizar_ciclo_rotativo(") != 1:\n        raise RuntimeError("Duplicidade de finalizar_ciclo_rotativo ainda existe.")\n\n    if "conn.commit()" in texto or "conn.rollback()" in texto:\n        raise RuntimeError(\n            "Ainda existe commit/rollback em services/ciclos_rotativo.py."\n        )\n\n    if "raise ValueError(" in texto:\n        raise RuntimeError(\n            "Ainda existe ValueError em services/ciclos_rotativo.py."\n        )\n\n    service.write_text(texto, encoding="utf-8")\n\n    # ========================================================\n    # ROUTER\n    # ========================================================\n    texto = router.read_text(encoding="utf-8")\n\n    # Restaura contrato Fase 11 de todo este router.\n    if "from domain.exceptions import BusinessRuleViolation" not in texto:\n        marcador = (\n            "from infrastructure.database.unit_of_work import "\n            "SqlServerUnitOfWork\\n"\n        )\n        if marcador not in texto:\n            raise RuntimeError("Import do SqlServerUnitOfWork não encontrado.")\n        texto = texto.replace(\n            marcador,\n            marcador + "\\nfrom domain.exceptions import BusinessRuleViolation\\n",\n            1\n        )\n\n    # Todas as capturas ValueError deste router eram contrato 400.\n    texto = texto.replace(\n        "except ValueError as erro:",\n        "except BusinessRuleViolation as erro:"\n    )\n\n    # Para transformar endpoints, temporariamente recoloca o marcador apenas\n    # dentro deles para a rotina exigir/validar o ponto correto.\n    # Endpoint abrir.\n    fn = localizar_funcao_router_por_chamada(\n        texto, "abrir_ciclo_rotativo"\n    )\n    trecho = extrair_funcao(texto, fn)\n\n    # Como o replace global já ocorreu, a rotina espera ValueError.\n    trecho = trecho.replace(\n        "except BusinessRuleViolation as erro:",\n        "except ValueError as erro:",\n        1\n    )\n    trecho = transformar_endpoint(\n        trecho,\n        "abrir_ciclo_rotativo",\n        ja_tem_resultado=False\n    )\n    texto = substituir_funcao(texto, fn, trecho)\n\n    # Endpoint finalizar.\n    fn = localizar_funcao_router_por_chamada(\n        texto, "finalizar_ciclo_rotativo"\n    )\n    trecho = extrair_funcao(texto, fn)\n    trecho = trecho.replace(\n        "except BusinessRuleViolation as erro:",\n        "except ValueError as erro:",\n        1\n    )\n    trecho = transformar_endpoint(\n        trecho,\n        "finalizar_ciclo_rotativo",\n        ja_tem_resultado=True\n    )\n    texto = substituir_funcao(texto, fn, trecho)\n\n    # Nenhum ValueError catch deve restar neste router.\n    if "except ValueError as erro:" in texto:\n        raise RuntimeError(\n            "Ainda existe except ValueError em routers/rotativo_ciclos.py."\n        )\n\n    # As duas chamadas não recebem mais conn.\n    for chamada in ("abrir_ciclo_rotativo", "finalizar_ciclo_rotativo"):\n        tree = ast.parse(texto)\n        calls = [\n            n for n in ast.walk(tree)\n            if isinstance(n, ast.Call)\n            and isinstance(n.func, ast.Name)\n            and n.func.id == chamada\n        ]\n        if len(calls) != 1:\n            raise RuntimeError(\n                f"Esperada 1 chamada de {chamada}; encontradas {len(calls)}."\n            )\n        if any(kw.arg == "conn" for kw in calls[0].keywords):\n            raise RuntimeError(\n                f"{chamada}: argumento conn ainda presente no router."\n            )\n\n    router.write_text(texto, encoding="utf-8")\n\n    # ========================================================\n    # VALIDAÇÃO\n    # ========================================================\n    py_compile.compile(str(service), doraise=True)\n    py_compile.compile(str(router), doraise=True)\n\n    service_final = service.read_text(encoding="utf-8")\n    router_final = router.read_text(encoding="utf-8")\n\n    assert service_final.count("def finalizar_ciclo_rotativo(") == 1\n    assert "raise ValueError(" not in service_final\n    assert "conn.commit()" not in service_final\n    assert "conn.rollback()" not in service_final\n    assert router_final.count("uow.commit()") >= 2\n\nexcept Exception:\n    for arq, backup in backups.items():\n        shutil.copy2(backup, arq)\n    raise\n\nprint("APROVADO")\nprint()\nprint("services/ciclos_rotativo.py")\nprint("- primeira implementação duplicada de finalizar_ciclo_rotativo removida")\nprint("- 9 ValueError -> BusinessRuleViolation")\nprint("- conn removido de abrir_ciclo_rotativo/finalizar_ciclo_rotativo")\nprint("- commit/rollback removidos do service")\nprint()\nprint("routers/rotativo_ciclos.py")\nprint("- catches ValueError restaurados para BusinessRuleViolation")\nprint("- abertura do ciclo: commit no UoW")\nprint("- finalização do ciclo: commit no UoW")\nprint("- rollback em BusinessRuleViolation, HTTPException e Exception")\nprint("- chamadas dos services sem conn")\nprint()\nprint("py_compile: APROVADO")\nprint()\nprint("Backups:")\nfor backup in backups.values():\n    print(backup)\n'
HELPER_IMPORTS = 'from pathlib import Path\nimport shutil\nimport py_compile\nfrom datetime import datetime\n\nROOT = Path.cwd()\nrouter = ROOT / "routers" / "rotativo_ciclos.py"\n\nif not router.exists():\n    raise FileNotFoundError(f"Não encontrado: {router}")\n\ntimestamp = datetime.now().strftime("%Y%m%d_%H%M%S")\nbackup = router.with_name(\n    f"{router.stem}_backup_imports_{timestamp}{router.suffix}"\n)\n\nshutil.copy2(router, backup)\n\ntry:\n    texto = router.read_text(encoding="utf-8")\n\n    bloco_ciclos_duplicado = \'\'\'from services.ciclos_rotativo import (\n    abrir_ciclo_rotativo,\n    consultar_ciclo_atual,\n)\n\nfrom services.ciclos_rotativo import (\n    abrir_ciclo_rotativo,\n    consultar_ciclo_atual,\n    finalizar_ciclo_rotativo,\n)\n\'\'\'\n\n    bloco_ciclos_limpo = \'\'\'from services.ciclos_rotativo import (\n    abrir_ciclo_rotativo,\n    consultar_ciclo_atual,\n    finalizar_ciclo_rotativo,\n)\n\'\'\'\n\n    if bloco_ciclos_duplicado not in texto:\n        raise RuntimeError(\n            "Bloco duplicado de services.ciclos_rotativo não encontrado."\n        )\n\n    texto = texto.replace(\n        bloco_ciclos_duplicado,\n        bloco_ciclos_limpo,\n        1\n    )\n\n    bloco_tratativas_duplicado = \'\'\'from services.rotativo_tratativas import (\n    consultar_tratativas_rotativo,\n)\nfrom services.rotativo_tratativas import (\n    consultar_tratativas_rotativo,\n    resolver_ocorrencia_rotativo,\n)\n\'\'\'\n\n    bloco_tratativas_limpo = \'\'\'from services.rotativo_tratativas import (\n    consultar_tratativas_rotativo,\n    resolver_ocorrencia_rotativo,\n)\n\'\'\'\n\n    if bloco_tratativas_duplicado not in texto:\n        raise RuntimeError(\n            "Bloco duplicado de services.rotativo_tratativas não encontrado."\n        )\n\n    texto = texto.replace(\n        bloco_tratativas_duplicado,\n        bloco_tratativas_limpo,\n        1\n    )\n\n    router.write_text(texto, encoding="utf-8")\n\n    py_compile.compile(\n        str(router),\n        doraise=True\n    )\n\n    texto_final = router.read_text(encoding="utf-8")\n\n    if texto_final.count("from services.ciclos_rotativo import (") != 1:\n        raise RuntimeError(\n            "Ainda existe duplicidade no import de ciclos_rotativo."\n        )\n\n    if texto_final.count("from services.rotativo_tratativas import (") != 1:\n        raise RuntimeError(\n            "Ainda existe duplicidade no import de rotativo_tratativas."\n        )\n\nexcept Exception:\n    shutil.copy2(backup, router)\n    raise\n\nprint("APROVADO")\nprint()\nprint("Alterações:")\nprint("- consolidado import de services.ciclos_rotativo")\nprint("- consolidado import de services.rotativo_tratativas")\nprint("- nenhuma rota alterada")\nprint("- nenhuma regra de negócio alterada")\nprint("- py_compile aprovado")\nprint()\nprint(f"Backup: {backup}")\n'

try:
    # ============================================================
    # 1. SERVICES SEMÂNTICOS / INTENTIONAL BOUNDARIES
    # ============================================================
    semantic_service(ROOT / "services" / "rotativo_tratativas.py", 16)
    semantic_service(ROOT / "services" / "rotativo_priorizacao.py", 4)
    semantic_service(ROOT / "services" / "rotativo_cobertura.py", 7)
    semantic_service(ROOT / "services" / "rotativo_contexto.py", 5)
    semantic_service(ROOT / "services" / "rotativo_orquestrador.py", 5)
    semantic_service(ROOT / "services" / "rotativo_painel.py", 3)
    semantic_service(ROOT / "services" / "rotativo_sugestoes.py", 5)
    semantic_service(ROOT / "services" / "rotativo_tendencia.py", 3)

    # Preservar comportamento tolerante do orquestrador para contexto.
    orq = ROOT / "services" / "rotativo_orquestrador.py"
    texto = orq.read_text(encoding="utf-8")
    if "except ValueError as erro:" in texto:
        if "from domain.exceptions import BusinessRuleViolation" not in texto:
            texto = ensure_brv_import(orq)
        texto = texto.replace(
            "except ValueError as erro:",
            "except (ValueError, BusinessRuleViolation) as erro:",
        )
        orq.write_text(texto, encoding="utf-8")
        compile_file(orq)

    # Routers simples.
    semantic_router(ROOT / "routers" / "rotativo_cobertura.py", 1)
    semantic_router(ROOT / "routers" / "rotativo_priorizacao.py", 1)

    # ============================================================
    # 2. ROTATIVO_FLUXO - OLD -> MIGRA UOW; CORRECT -> SKIP
    # ============================================================
    fluxo = ROOT / "services" / "rotativo_fluxo.py"
    ft = fluxo.read_text(encoding="utf-8")
    fv = ft.count("raise ValueError(")
    fc = ft.count("conn.commit()")
    fr = ft.count("conn.rollback()")

    if fv == 9 and fc == 2 and fr == 2:
        run_embedded("patch_rotativo_fluxo_uow_fase12.py", HELPER_FLUXO)
    elif fv == 0 and fc == 0 and fr == 0:
        if ft.count("raise BusinessRuleViolation(") < 9:
            raise RuntimeError("rotativo_fluxo parece migrado, mas BRVs estão incompletos.")
        print("OK         services/rotativo_fluxo.py: UoW já migrado")
    else:
        raise RuntimeError(
            "Estado intermediário inesperado em rotativo_fluxo.py: "
            f"ValueError={fv}, commit={fc}, rollback={fr}."
        )

    # ============================================================
    # 3. CICLOS - OLD -> MIGRA UOW; CORRECT -> SKIP
    # ============================================================
    ciclos = ROOT / "services" / "ciclos_rotativo.py"
    ct = ciclos.read_text(encoding="utf-8")
    cv = ct.count("raise ValueError(")
    cdefs = ct.count("def finalizar_ciclo_rotativo(")
    cc = ct.count("conn.commit()")
    cr = ct.count("conn.rollback()")

    if cv == 9 and cdefs == 2 and cc == 2 and cr == 3:
        run_embedded("patch_ciclos_uow_fase12.py", HELPER_CICLOS)
    elif cv == 0 and cdefs == 1 and cc == 0 and cr == 0:
        # Estado correto após remoção da implementação duplicada:
        # restam 6 regras de negócio reais no único finalizador/fluxo ativo.
        if ct.count("raise BusinessRuleViolation(") < 6:
            raise RuntimeError("ciclos_rotativo parece migrado, mas BRVs estão incompletos.")
        print("OK         services/ciclos_rotativo.py: UoW já migrado")
    else:
        raise RuntimeError(
            "Estado intermediário inesperado em ciclos_rotativo.py: "
            f"ValueError={cv}, finalizers={cdefs}, commit={cc}, rollback={cr}."
        )

    # Agora que todos os services chamados pelo router de ciclos foram
    # restaurados para BRV, é seguro eliminar catches ValueError restantes.
    semantic_router(
        ROOT / "routers" / "rotativo_ciclos.py",
        replace_all=True,
    )

    # ============================================================
    # 4. IMPORTS DUPLICADOS - CORRIGE SOMENTE SE EXISTIREM
    # ============================================================
    rc = ROOT / "routers" / "rotativo_ciclos.py"
    rct = rc.read_text(encoding="utf-8")
    ciclos_imports = rct.count("from services.ciclos_rotativo import (")
    trat_imports = rct.count("from services.rotativo_tratativas import (")

    if ciclos_imports == 2 and trat_imports == 2:
        run_embedded("patch_imports_rotativo_ciclos.py", HELPER_IMPORTS)
    elif ciclos_imports == 1 and trat_imports == 1:
        print("OK         routers/rotativo_ciclos.py: imports já consolidados")
    else:
        raise RuntimeError(
            "Estado inesperado nos imports de rotativo_ciclos.py: "
            f"ciclos={ciclos_imports}, tratativas={trat_imports}."
        )

    # ============================================================
    # 5. AUDITORIA FINAL
    # ============================================================
    erros = []

    for base_dir in (
        ROOT / "services",
        ROOT / "domain",
        ROOT / "application",
    ):
        for arq in base_dir.rglob("*.py"):
            if "backup" in str(arq).lower():
                continue

            texto = arq.read_text(encoding="utf-8", errors="ignore")
            if "raise ValueError(" in texto:
                rel = arq.relative_to(ROOT).as_posix()
                if rel not in (
                    "services/seguranca.py",
                    "services/regras_inventario.py",
                ):
                    erros.append(f"ValueError inesperado: {rel}")

    # Transaction ownership.
    ciclos_t = (ROOT / "services" / "ciclos_rotativo.py").read_text(encoding="utf-8")
    fluxo_t = (ROOT / "services" / "rotativo_fluxo.py").read_text(encoding="utf-8")
    trat_t = (ROOT / "services" / "rotativo_tratativas.py").read_text(encoding="utf-8")
    prior_t = (ROOT / "services" / "rotativo_priorizacao.py").read_text(encoding="utf-8")
    cob_t = (ROOT / "services" / "rotativo_cobertura.py").read_text(encoding="utf-8")

    if ciclos_t.count("def finalizar_ciclo_rotativo(") != 1:
        erros.append("ciclos_rotativo: finalizar_ciclo_rotativo != 1")
    if "conn.commit()" in ciclos_t or "conn.rollback()" in ciclos_t:
        erros.append("ciclos_rotativo ainda possui transação interna")
    if "conn.commit()" in fluxo_t or "conn.rollback()" in fluxo_t:
        erros.append("rotativo_fluxo ainda possui transação interna")

    if trat_t.count("conn.commit()") != 1 or trat_t.count("conn.rollback()") != 2:
        erros.append("rotativo_tratativas: fronteira intencional inválida")
    if prior_t.count("conn.commit()") != 1 or prior_t.count("conn.rollback()") != 1:
        erros.append("rotativo_priorizacao: fronteira intencional inválida")
    if cob_t.count("conn.commit()") != 1 or cob_t.count("conn.rollback()") != 1:
        erros.append("rotativo_cobertura: fronteira intencional inválida")

    # Router catches.
    for arq in (
        ROOT / "routers" / "rotativo_ciclos.py",
        ROOT / "routers" / "rotativo_cobertura.py",
        ROOT / "routers" / "rotativo_fluxo.py",
        ROOT / "routers" / "rotativo_priorizacao.py",
    ):
        texto = arq.read_text(encoding="utf-8")
        if "except ValueError as erro:" in texto:
            erros.append(
                f"ValueError catch inesperado: {arq.relative_to(ROOT)}"
            )

    # Compile completo.
    for pasta in ("services", "domain", "application", "routers"):
        for arq in (ROOT / pasta).rglob("*.py"):
            if "backup" in str(arq).lower():
                continue
            compile_file(arq)

    if erros:
        raise RuntimeError(
            "Auditoria consolidada reprovada:\n- " + "\n- ".join(erros)
        )

except Exception:
    print()
    print("REPROVADO - restaurando TODOS os arquivos do lote...")
    restore_all()
    print(f"Backup global preservado em: {backup_dir}")
    raise

print()
print("=" * 72)
print("FASE 12 CONSOLIDADA V2: APROVADO")
print("=" * 72)
print("- aceita arquivos antigos ou já corrigidos")
print("- rejeita estados intermediários inesperados")
print("- ValueErrors de negócio -> BusinessRuleViolation")
print("- ciclos_rotativo: 1 finalizador e UoW no router")
print("- rotativo_fluxo: UoW no router")
print("- tratativas/priorizacao/cobertura: intentional boundaries preservadas")
print("- compile global: APROVADO")
print()
print(f"Backup global: {backup_dir}")
print()
print("Pendente fora deste patch:")
print("- auditar 3 repositories em services/rodadas/repositories com FastAPI/HTTPException")
