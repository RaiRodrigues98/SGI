"""Suíte E2E do inventário ROTATIVO do SGI.

Uso (PowerShell):
  $env:SGI_BASE_URL='http://127.0.0.1:8000'
  $env:SGI_LOGIN='dev'
  $env:SGI_PASSWORD='SUA_SENHA'
  python teste_rotativo_e2e.py

A suíte cria inventários TESTE-E2E-* e usa somente a API pública do SGI.
Não apaga dados e não altera código/configurações do sistema.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

BASE = os.getenv("SGI_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
LOGIN = os.getenv("SGI_LOGIN", "")
PASSWORD = os.getenv("SGI_PASSWORD", "")
CLIENTE_ID = int(os.getenv("SGI_CLIENTE_ID", "53"))
CLIENTE = os.getenv("SGI_CLIENTE", "endress")
ARMAZEM = os.getenv("SGI_ARMAZEM", "ML007")
LOCALIZACAO = os.getenv("SGI_LOCALIZACAO", "01PLAQUETA").strip().upper()
TIMEOUT = float(os.getenv("SGI_TIMEOUT", "30"))


class ApiError(RuntimeError):
    def __init__(self, status: int, data: Any, method: str, path: str):
        self.status = status
        self.data = data
        self.method = method
        self.path = path
        super().__init__(f"HTTP {status} {method} {path}: {data}")


class API:
    def __init__(self):
        self.token = ""

    def request(self, method: str, path: str, body: Any = None, expected=(200, 201)) -> Any:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        raw = None
        if body is not None:
            raw = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(BASE + path, data=raw, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                data = json.loads(r.read().decode("utf-8") or "null")
                if r.status not in expected:
                    raise ApiError(r.status, data, method, path)
                return data
        except urllib.error.HTTPError as e:
            try:
                data = json.loads(e.read().decode("utf-8") or "null")
            except Exception:
                data = str(e)
            if e.code in expected:
                return data
            raise ApiError(e.code, data, method, path)

    def login(self):
        if not LOGIN or not PASSWORD:
            raise RuntimeError("Defina SGI_LOGIN e SGI_PASSWORD antes de executar.")
        r = self.request("POST", "/auth/login", {"login": LOGIN, "senha": PASSWORD})
        self.token = r["access_token"]


api = API()


@dataclass
class Report:
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    def ok(self, name: str):
        self.passed.append(name)
        print(f"[PASS] {name}")

    def fail(self, name: str, exc: Exception | str):
        msg = f"{name}: {exc}"
        self.failed.append(msg)
        print(f"[FAIL] {msg}")


R = Report()


def assert_true(value, msg):
    if not value:
        raise AssertionError(msg)


def expect_error(fn, statuses=(400, 409, 422), contains: str | None = None):
    try:
        fn()
    except ApiError as e:
        assert_true(e.status in statuses, f"status inesperado: {e.status}; retorno={e.data}")
        if contains:
            text = json.dumps(e.data, ensure_ascii=False).upper()
            assert_true(contains.upper() in text, f"mensagem não contém {contains!r}: {e.data}")
        return e
    raise AssertionError("A operação deveria ter sido bloqueada, mas foi aceita.")


def unique_code(tag: str) -> str:
    # CodigoInventario no banco aceita no máximo 30 caracteres.
    # Mantém o identificador legível e ainda suficientemente único para E2E.
    tag_curta = "".join(ch for ch in tag.upper() if ch.isalnum())[:8]
    sufixo = str(int(time.time() * 1000))[-10:]
    return f"E2E-{tag_curta}-{sufixo}"[:30]


def create_inventory(tag: str):
    r = api.request("POST", "/inventarios", {
        "codigo_inventario": unique_code(tag),
        "tipo": "ROTATIVO",
        "cliente_id": CLIENTE_ID,
        "cliente": CLIENTE,
        "descricao": f"E2E automático ROTATIVO - {tag}",
        "armazem": ARMAZEM,
    })
    return r["id_inventario"], r["id_rodada"]


def add_scope(iid: int):
    return api.request("POST", f"/inventarios/{iid}/escopo/localizacoes", {"localizacoes": [LOCALIZACAO]})


def snapshot(iid: int):
    return api.request("POST", f"/inventarios/{iid}/snapshot", {})


def analysis(iid: int):
    return api.request("GET", f"/inventarios/{iid}/analise-rotativo")


def snapshot_items(iid: int):
    a = analysis(iid)
    items = [x for x in a.get("itens", []) if str(x.get("localizacao", "")).strip().upper() == LOCALIZACAO]
    assert_true(items, f"Nenhum item encontrado na análise para {LOCALIZACAO}")
    return items


def start(iid: int, rid: int):
    return api.request("POST", "/localizacoes/iniciar", {"id_inventario": iid, "id_rodada": rid, "localizacao": LOCALIZACAO})


def count(sid: int, item: dict, qty: float):
    return api.request("POST", "/contagens", {
        "id_sessao": sid,
        "codigo": str(item["codigo"]),
        "lote": item.get("lote") or "",
        "quantidade": qty,
    })


def close(sid: int, empty=False):
    return api.request("POST", "/localizacoes/encerrar", {"id_sessao": sid, "localizacao_vazia": empty})


def next_round(iid: int):
    return api.request("POST", f"/inventarios/{iid}/rodadas/proxima")


def preview(iid: int):
    return api.request("GET", f"/inventarios/{iid}/rodadas/proxima-preview")


def decision(iid: int, rid: int, item: dict, kind: str, justification=None):
    body = {
        "id_rodada": rid,
        "localizacao": LOCALIZACAO,
        "codigo": str(item["codigo"]),
        "lote": item.get("lote") or "",
        "decisao": kind,
    }
    if justification is not None:
        body["justificativa"] = justification
    return api.request("POST", f"/inventarios/{iid}/decisoes-rotativo", body)


def final_result(iid: int):
    return api.request("GET", f"/inventarios/{iid}/resultado-final")


def qty_stock(item: dict) -> float:
    for k in ("qtd_estoque", "quantidade_estoque", "saldo_inventario"):
        if k in item and item[k] is not None:
            return float(item[k])
    raise AssertionError(f"Campo de estoque não localizado no item: {item}")


def count_all_correct(iid: int, rid: int):
    items = snapshot_items(iid)
    s = start(iid, rid)
    sid = s["id_sessao"]
    for it in items:
        q = qty_stock(it)
        if q > 0:
            count(sid, it, q)
    close(sid, empty=False)
    return items, sid


def prepare(tag: str):
    iid, r1 = create_inventory(tag)
    add_scope(iid)
    s = snapshot(iid)
    assert_true(int(s.get("registros_snapshot", 0)) > 0, "snapshot vazio")
    items = snapshot_items(iid)
    return iid, r1, items



def run(name, fn):
    try:
        fn()
        R.ok(name)
    except Exception as e:
        R.fail(name, str(e))




# ============================================================
# ESTÁGIO 4 - CONCORRÊNCIA LÓGICA E INTEGRIDADE OPERACIONAL
# ============================================================

def test_duplo_inicio_mesma_localizacao_reutiliza_sessao_aberta():
    iid, r1, items = prepare("DUPSTART")

    s1 = start(iid, r1)
    s2 = start(iid, r1)

    sid1 = s1["id_sessao"]
    sid2 = s2["id_sessao"]

    assert_true(
        sid1 == sid2,
        f"duplo início criou duas sessões abertas para a mesma localização: {sid1} e {sid2}"
    )

    # Fecha normalmente para não deixar inventário operacional pendente.
    for it in items:
        q = qty_stock(it)
        if q > 0:
            count(sid1, it, q)
    close(sid1)

    fin = next_round(iid)
    assert_true(
        fin["proxima_rodada"].get("status_inventario") == "FINALIZADO",
        f"duplo início interferiu na finalização: {fin}"
    )


def test_rodada_antiga_nao_pode_ser_operada_apos_criar_r2():
    iid, r1, items = prepare("OLDROUND")
    target = items[0]

    s = start(iid, r1)
    sid = s["id_sessao"]

    for it in items:
        q = qty_stock(it)
        if q <= 0:
            continue
        count(sid, it, q + 1 if it is target else q)

    close(sid)
    decision(iid, r1, target, "RECONTAR")

    nr = next_round(iid)
    r2 = nr["proxima_rodada"]["id_rodada"]

    # Depois de avançar para R2, não deve ser possível iniciar nova operação física na R1.
    expect_error(
        lambda: start(iid, r1),
        statuses=(400, 409)
    )

    # A R2 deve continuar operacional.
    s2 = start(iid, r2)
    sid2 = s2["id_sessao"]
    count(sid2, target, qty_stock(target))
    close(sid2)

    fin = next_round(iid)
    assert_true(
        fin["proxima_rodada"].get("status_inventario") == "FINALIZADO",
        f"R2 não finalizou após proteção da rodada antiga: {fin}"
    )


def test_reabertura_repetida_mantem_apenas_ultima_sessao_na_consolidacao():
    iid, r1, items = prepare("MULTIREO")
    target = items[0]

    # Sessão 1 - divergente.
    s1 = start(iid, r1)
    sid1 = s1["id_sessao"]
    for it in items:
        q = qty_stock(it)
        if q > 0:
            count(sid1, it, q + 2 if it is target else q)
    close(sid1)

    # Sessão 2 - ainda divergente.
    s2 = start(iid, r1)
    sid2 = s2["id_sessao"]
    assert_true(sid2 != sid1, "primeira reabertura não criou nova sessão")
    for it in items:
        q = qty_stock(it)
        if q > 0:
            count(sid2, it, q + 1 if it is target else q)
    close(sid2)

    # Sessão 3 - correta.
    s3 = start(iid, r1)
    sid3 = s3["id_sessao"]
    assert_true(
        sid3 not in (sid1, sid2),
        f"segunda reabertura reutilizou sessão antiga: {sid3}"
    )
    for it in items:
        q = qty_stock(it)
        if q > 0:
            count(sid3, it, q)
    close(sid3)

    # Se qualquer sessão anterior ainda estiver válida para consolidação,
    # o inventário ficará divergente.
    fin = next_round(iid)
    assert_true(
        fin["proxima_rodada"].get("status_inventario") == "FINALIZADO",
        f"sessões antigas interferiram após múltiplas reaberturas: {fin}"
    )


def test_decisao_nao_pode_ser_criada_para_item_sem_divergencia():
    iid, r1, items = prepare("DECOK")
    target = items[0]

    count_all_correct(iid, r1)

    expect_error(
        lambda: decision(iid, r1, target, "RECONTAR"),
        statuses=(400, 409, 422)
    )

    fin = next_round(iid)
    assert_true(
        fin["proxima_rodada"].get("status_inventario") == "FINALIZADO",
        f"decisão inválida interferiu no inventário correto: {fin}"
    )


def test_decisao_nao_pode_ser_criada_em_rodada_finalizada():
    iid, r1, items = prepare("DECLATE")
    target = items[0]

    count_all_correct(iid, r1)
    fin = next_round(iid)

    assert_true(
        fin["proxima_rodada"].get("status_inventario") == "FINALIZADO",
        f"inventário não finalizou: {fin}"
    )

    expect_error(
        lambda: decision(iid, r1, target, "RECONTAR"),
        statuses=(400, 409, 422)
    )


def test_resultado_final_sem_duplicidade_logica():
    iid, r1, items = prepare("UNIQRES")
    count_all_correct(iid, r1)

    fin = next_round(iid)
    assert_true(
        fin["proxima_rodada"].get("status_inventario") == "FINALIZADO",
        f"inventário não finalizou: {fin}"
    )

    rf = final_result(iid)
    finais = rf.get("itens", [])

    assert_true(len(finais) > 0, f"resultado final vazio: {rf}")

    def norm(v):
        return "" if v is None else str(v).strip().upper()

    keys = []
    for it in finais:
        loc = it.get("localizacao", it.get("Localizacao"))
        cod = it.get("codigo", it.get("Codigo"))
        lote = it.get("lote", it.get("Lote"))
        keys.append((norm(loc), norm(cod), norm(lote)))

    duplicadas = sorted({k for k in keys if keys.count(k) > 1})
    assert_true(
        not duplicadas,
        f"resultado final contém chave lógica duplicada Localização+Código+Lote: {duplicadas}"
    )


def main():
    print("=" * 72)
    print("SGI - ESTÁGIO 4 | CONCORRÊNCIA LÓGICA E INTEGRIDADE OPERACIONAL")
    print(f"API: {BASE} | Cliente: {CLIENTE_ID} | Armazém: {ARMAZEM} | Local: {LOCALIZACAO}")
    print("=" * 72)

    api.login()
    R.ok("Autenticação")

    run("Duplo início reutiliza a sessão aberta", test_duplo_inicio_mesma_localizacao_reutiliza_sessao_aberta)
    run("Rodada antiga fica bloqueada após criação da R2", test_rodada_antiga_nao_pode_ser_operada_apos_criar_r2)
    run("Reabertura repetida mantém somente a última sessão válida", test_reabertura_repetida_mantem_apenas_ultima_sessao_na_consolidacao)
    run("Não permite decisão para item sem divergência", test_decisao_nao_pode_ser_criada_para_item_sem_divergencia)
    run("Não permite decisão após rodada/inventário finalizado", test_decisao_nao_pode_ser_criada_em_rodada_finalizada)
    run("Resultado final não possui duplicidade lógica", test_resultado_final_sem_duplicidade_logica)

    print("\n" + "=" * 72)
    print(f"PASS: {len(R.passed)} | FAIL: {len(R.failed)}")
    if R.failed:
        print("RESULTADO: REPROVADO")
        for x in R.failed:
            print(" -", x)
        sys.exit(1)

    print("RESULTADO: APROVADO")
    print("=" * 72)


if __name__ == "__main__":
    main()
